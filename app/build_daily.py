"""Berechnet die Tagesaggregate aus den Rohdaten neu.

Aufruf:
    python app/build_daily.py

Füllt `daily_metrics` (pro Tag und Messwert-Typ: Anzahl/Summe/Schnitt/Min/Max)
und `daily_sleep` (pro Nacht: Schlafphasen in Minuten, Zubettgeh- und
Aufwachzeit).

Nach jedem Import einmal ausführen. Läuft ein paar Sekunden und ersetzt
den bisherigen Inhalt der Aggregattabellen vollständig.
"""

import sqlite3
from collections import defaultdict
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "health.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# Messwerte, die über den Tag aufsummiert gehören (Schritte, Kalorien, ...)
# statt gemittelt. Nur für die Auswahl der sinnvollen Standardspalte im
# Dashboard relevant - berechnet werden immer alle Kennzahlen.
CUMULATIVE_HINTS = (
    "StepCount",
    "Distance",
    "EnergyBurned",
    "FlightsClimbed",
    "AppleExerciseTime",
    "AppleStandTime",
    "TimeInDaylight",
    "SwimmingStrokeCount",
)

SLEEP_PHASES = {
    "HKCategoryValueSleepAnalysisInBed": "in_bed_min",
    "HKCategoryValueSleepAnalysisAsleepCore": "core_min",
    "HKCategoryValueSleepAnalysisAsleepDeep": "deep_min",
    "HKCategoryValueSleepAnalysisAsleepREM": "rem_min",
    "HKCategoryValueSleepAnalysisAsleepUnspecified": "asleep_unspecified",
    "HKCategoryValueSleepAnalysisAwake": "awake_min",
}


def build_daily_metrics(conn: sqlite3.Connection) -> int:
    """Numerische Messwerte pro Tag und Typ zusammenfassen.

    Das Datum kommt direkt aus den ersten 10 Zeichen von start_date -
    Apple exportiert bereits in lokaler Zeit, damit stimmen Tagesgrenzen
    ohne Zeitzonen-Umrechnung.
    """
    print("Berechne daily_metrics ...")
    conn.execute("DELETE FROM daily_metrics")
    conn.execute(
        """
        INSERT INTO daily_metrics (date, type, unit, n, total, avg, min, max)
        SELECT
            substr(start_date, 1, 10) AS date,
            type,
            MIN(unit),
            COUNT(value),
            SUM(value),
            AVG(value),
            MIN(value),
            MAX(value)
        FROM records
        WHERE value IS NOT NULL
        GROUP BY date, type
        """
    )
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0]


_TS_FORMAT = "%Y-%m-%d %H:%M:%S %z"

ASLEEP_COLUMNS = ("core_min", "deep_min", "rem_min", "asleep_unspecified")


def _parse_ts(ts: str):
    from datetime import datetime

    try:
        return datetime.strptime(ts, _TS_FORMAT)
    except ValueError:
        return None


def _merged_minutes(intervals) -> float:
    """Gesamtdauer einer Intervall-Liste in Minuten, Überlappungen nur einmal.

    Nötig, weil in manchen Nächten Watch, iPhone und Drittanbieter-Apps
    parallel getrackt haben. Ein simples Aufsummieren der Segmentdauern
    würde diese Nächte massiv überschätzen.
    """
    if not intervals:
        return 0.0

    total = 0.0
    ordered = sorted(intervals)
    current_start, current_end = ordered[0]

    for start, end in ordered[1:]:
        if start > current_end:
            total += (current_end - current_start).total_seconds()
            current_start, current_end = start, end
        elif end > current_end:
            current_end = end

    total += (current_end - current_start).total_seconds()
    return total / 60.0


def build_daily_sleep(conn: sqlite3.Connection) -> int:
    """Schlafsegmente zu Nächten zusammenfassen.

    Eine Nacht wird dem Morgen des Aufwachens zugeordnet: Segmente, die
    ab 18:00 beginnen, zählen zum Folgetag. So ist eine Nacht genau eine
    Zeile und lässt sich direkt mit dem Folgetag verknüpfen.
    """
    print("Berechne daily_sleep ...")
    conn.execute("DELETE FROM daily_sleep")

    rows = conn.execute(
        """
        SELECT value_text, start_date, end_date
        FROM records
        WHERE type = 'HKCategoryTypeIdentifierSleepAnalysis'
        ORDER BY start_date
        """
    ).fetchall()

    nights = defaultdict(lambda: defaultdict(list))
    bounds = {}

    for value_text, start, end in rows:
        column = SLEEP_PHASES.get(value_text)
        if column is None:
            continue

        start_dt, end_dt = _parse_ts(start), _parse_ts(end)
        if start_dt is None or end_dt is None or end_dt <= start_dt:
            continue

        # Ab 18:00 gehört das Segment zur Nacht des Folgetags
        if start_dt.hour >= 18:
            from datetime import timedelta

            night = (start_dt.date() + timedelta(days=1)).isoformat()
        else:
            night = start_dt.date().isoformat()

        nights[night][column].append((start_dt, end_dt))

        # Zubettgehzeit = frühestes Segment, Aufwachzeit = spätestes Ende
        current = bounds.get(night)
        if current is None:
            bounds[night] = {"bedtime": start, "wake_time": end}
        else:
            if start < current["bedtime"]:
                current["bedtime"] = start
            if end > current["wake_time"]:
                current["wake_time"] = end

    payload = []
    for night, phases in nights.items():
        # Schlafzeit über alle Schlafphasen hinweg vereinigen, damit sich
        # überlappende Quellen nicht addieren
        asleep_intervals = [iv for col in ASLEEP_COLUMNS for iv in phases.get(col, ())]

        payload.append(
            (
                night,
                _merged_minutes(phases.get("in_bed_min", [])) or None,
                _merged_minutes(asleep_intervals) or None,
                _merged_minutes(phases.get("core_min", [])) or None,
                _merged_minutes(phases.get("deep_min", [])) or None,
                _merged_minutes(phases.get("rem_min", [])) or None,
                _merged_minutes(phases.get("awake_min", [])) or None,
                bounds[night]["bedtime"][11:16],
                bounds[night]["wake_time"][11:16],
            )
        )

    conn.executemany(
        """
        INSERT OR REPLACE INTO daily_sleep
            (date, in_bed_min, asleep_min, core_min, deep_min, rem_min,
             awake_min, bedtime, wake_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        payload,
    )
    conn.commit()
    return len(payload)


def main() -> None:
    if not DB_PATH.exists():
        print(f"Keine Datenbank gefunden unter {DB_PATH}")
        print("Erst einen Export importieren: python app/import_export.py ...")
        raise SystemExit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    n_metrics = build_daily_metrics(conn)
    n_sleep = build_daily_sleep(conn)

    print(f"Fertig: {n_metrics} Tages-Kennzahlen, {n_sleep} Naechte.")
    conn.close()


if __name__ == "__main__":
    main()
