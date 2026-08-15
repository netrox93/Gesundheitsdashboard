"""Importiert einen Apple-Health-Export (Export.xml) in die lokale SQLite-DB.

Aufruf:
    python app/import_export.py /pfad/zu/Export.xml

Importiert werden:
  <Record>          Einzelmesswerte (Puls, Schritte, Schlaf, ...)
  <Workout>         Trainingseinheiten
  <ActivitySummary> Aktivitätsringe pro Tag inkl. Tagesziele

Der Export kann mehrfach importiert werden (z.B. nach jedem manuellen
Export aus der Health-App) - Duplikate werden über UNIQUE-Constraints
automatisch übersprungen.

Danach `python app/build_daily.py` ausführen, um die Tagesaggregate
neu zu berechnen.
"""

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import iterparse

import einstellungen

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# Einheiten-Umrechnung für Workout-Distanzen auf km
_DISTANCE_TO_KM = {"km": 1.0, "mi": 1.609344, "m": 0.001, "yd": 0.0009144}


# Spalten, die zu einer bestehenden Tabelle nachträglich dazugekommen sind.
# CREATE TABLE IF NOT EXISTS ergänzt bei einer schon vorhandenen DB keine
# Spalten, deshalb hier einzeln nachziehen.
MIGRATIONS = {
    "imports": {
        "workouts_inserted": "INTEGER",
        "summaries_inserted": "INTEGER",
    },
}


def apply_migrations(conn: sqlite3.Connection) -> None:
    for table, columns in MIGRATIONS.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if not existing:
            continue  # Tabelle wurde gerade frisch angelegt
        for name, coltype in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {coltype}")
    conn.commit()


def get_connection() -> sqlite3.Connection:
    pfad = einstellungen.db_pfad()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(pfad)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    apply_migrations(conn)
    return conn


def _to_float(raw):
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _workout_distance_km(attrib, stats):
    """Distanz in km, entweder aus den Workout-Attributen oder aus
    den <WorkoutStatistics>-Kindelementen neuerer Exports."""
    value = _to_float(attrib.get("totalDistance"))
    unit = attrib.get("totalDistanceUnit")
    if value is None:
        for stat in stats:
            if "Distance" in stat.get("type", ""):
                value = _to_float(stat.get("sum"))
                unit = stat.get("unit")
                break
    if value is None:
        return None
    return value * _DISTANCE_TO_KM.get(unit, 1.0)


def _workout_energy_kcal(attrib, stats):
    value = _to_float(attrib.get("totalEnergyBurned"))
    if value is None:
        for stat in stats:
            if stat.get("type", "").endswith("ActiveEnergyBurned"):
                value = _to_float(stat.get("sum"))
                break
    return value


def import_file(xml_path: Path, conn: sqlite3.Connection) -> dict:
    counts = {"seen": 0, "records": 0, "workouts": 0, "summaries": 0}
    cur = conn.cursor()
    pending_stats = []

    for _, elem in iterparse(xml_path, events=("end",)):
        tag = elem.tag

        if tag == "Record":
            counts["seen"] += 1
            attrib = elem.attrib
            value_raw = attrib.get("value")

            cur.execute(
                """
                INSERT OR IGNORE INTO records
                    (type, source_name, unit, value, value_text,
                     start_date, end_date, creation_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attrib.get("type"),
                    attrib.get("sourceName"),
                    attrib.get("unit"),
                    _to_float(value_raw),
                    value_raw,
                    attrib.get("startDate"),
                    attrib.get("endDate"),
                    attrib.get("creationDate"),
                ),
            )
            counts["records"] += cur.rowcount

            if counts["seen"] % 500_000 == 0:
                print(f"  ... {counts['seen']} Records verarbeitet")

        elif tag == "WorkoutStatistics":
            # Kindelement - kommt vor dem End-Event des Workouts, deshalb puffern
            pending_stats.append(dict(elem.attrib))
            continue

        elif tag == "Workout":
            attrib = elem.attrib
            duration = _to_float(attrib.get("duration"))
            if duration is not None and attrib.get("durationUnit") == "sec":
                duration /= 60.0

            cur.execute(
                """
                INSERT OR IGNORE INTO workouts
                    (activity_type, source_name, duration_min, distance_km,
                     energy_kcal, start_date, end_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attrib.get("workoutActivityType"),
                    attrib.get("sourceName"),
                    duration,
                    _workout_distance_km(attrib, pending_stats),
                    _workout_energy_kcal(attrib, pending_stats),
                    attrib.get("startDate"),
                    attrib.get("endDate"),
                ),
            )
            counts["workouts"] += cur.rowcount
            pending_stats = []

        elif tag == "ActivitySummary":
            attrib = elem.attrib
            cur.execute(
                """
                INSERT OR REPLACE INTO activity_summaries
                    (date, active_energy_kcal, active_energy_goal, exercise_min,
                     exercise_goal, stand_hours, stand_goal, move_min, move_goal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attrib.get("dateComponents"),
                    _to_float(attrib.get("activeEnergyBurned")),
                    _to_float(attrib.get("activeEnergyBurnedGoal")),
                    _to_float(attrib.get("appleExerciseTime")),
                    _to_float(attrib.get("appleExerciseTimeGoal")),
                    _to_float(attrib.get("appleStandHours")),
                    _to_float(attrib.get("appleStandHoursGoal")),
                    _to_float(attrib.get("appleMoveTime")),
                    _to_float(attrib.get("appleMoveTimeGoal")),
                ),
            )
            counts["summaries"] += 1

        else:
            continue

        elem.clear()

    conn.commit()
    return counts


def protokolliere(conn: sqlite3.Connection, xml_path: Path, counts: dict) -> None:
    """Import in der Tabelle `imports` festhalten."""
    conn.execute(
        """
        INSERT INTO imports
            (file_name, imported_at, records_seen, records_inserted,
             workouts_inserted, summaries_inserted)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            Path(xml_path).name,
            datetime.now(timezone.utc).isoformat(),
            counts["seen"],
            counts["records"],
            counts["workouts"],
            counts["summaries"],
        ),
    )
    conn.commit()


def main() -> None:
    if len(sys.argv) != 2:
        print("Nutzung: python app/import_export.py /pfad/zu/Export.xml")
        sys.exit(1)

    xml_path = Path(sys.argv[1])
    if not xml_path.exists():
        print(f"Datei nicht gefunden: {xml_path}")
        sys.exit(1)

    conn = get_connection()
    print(f"Importiere {xml_path} ...")
    counts = import_file(xml_path, conn)

    protokolliere(conn, xml_path, counts)
    conn.close()

    print(
        f"Fertig: {counts['seen']} Records gelesen, {counts['records']} neu; "
        f"{counts['workouts']} Workouts neu, {counts['summaries']} Aktivitaetstage."
    )
    print(f"DB liegt unter: {einstellungen.db_pfad()}")
    print("Naechster Schritt: python app/build_daily.py")


if __name__ == "__main__":
    main()
