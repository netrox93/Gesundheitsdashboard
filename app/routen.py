"""Einlesen und Auswerten der GPX-Routen aus dem Health-Export.

Apple legt zu jedem Outdoor-Training eine GPX-Datei im Ordner
`workout-routes` ab. Enthalten sind Trackpoints mit Länge, Breite, Höhe
und Zeit; in den Extensions zusätzlich Geschwindigkeit, Kurs und die
GPS-Genauigkeit.

Zwei Dinge, die beim Umgang mit diesen Dateien wichtig sind:

* **Genauigkeit schwankt.** Direkt nach dem Start und in Häuserschluchten
  liegen einzelne Punkte hunderte Meter daneben. Ungefilterte Distanzen
  sind dadurch systematisch zu lang.
* **Der Startpunkt ist die Wohnadresse.** Deshalb lässt sich ein
  Heimatpunkt hinterlegen, um dessen Umkreis Punkte abgeschnitten werden
  (siehe `kuerze_um_heimat`).
"""

import math
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ERDRADIUS_M = 6371000.0

# Punkte mit schlechterer horizontaler Genauigkeit als dieser Wert gehen
# nicht in die Distanzberechnung ein. 50 m ist grosszügig - GPS liefert
# im Freien meist 3-10 m, in Häuserschluchten deutlich mehr.
MAX_GENAUIGKEIT_M = 50.0

# Sprünge über diese Geschwindigkeit hinaus sind Messfehler und keine
# Fortbewegung (150 km/h - deckt auch Abfahrten auf Ski ab).
MAX_TEMPO_MS = 42.0

GPX_NS = {
    "gpx": "http://www.topografix.com/GPX/1/1",
    "gpxtpx": "http://www.garmin.com/xmlschemas/TrackPointExtension/v1",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS routen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datei TEXT NOT NULL UNIQUE,
    workout_id INTEGER,
    start_zeit TEXT,
    ende_zeit TEXT,
    punkte INTEGER,
    distanz_km REAL,
    dauer_min REAL,
    aufstieg_m REAL,
    abstieg_m REAL,
    hoehe_min REAL,
    hoehe_max REAL,
    lat_min REAL,
    lat_max REAL,
    lon_min REAL,
    lon_max REAL,
    FOREIGN KEY (workout_id) REFERENCES workouts (id)
);

CREATE TABLE IF NOT EXISTS routen_punkte (
    routen_id INTEGER NOT NULL,
    nummer INTEGER NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    hoehe REAL,
    zeit TEXT,
    tempo_ms REAL,
    genauigkeit_m REAL,
    PRIMARY KEY (routen_id, nummer),
    FOREIGN KEY (routen_id) REFERENCES routen (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_routen_start ON routen (start_zeit);
CREATE INDEX IF NOT EXISTS idx_punkte_route ON routen_punkte (routen_id);
"""


# ------------------------------------------------------------------
# Geometrie
# ------------------------------------------------------------------


def entfernung_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Entfernung zweier Punkte in Metern (Haversine).

    Für Distanzen im Bereich einzelner Trackpoints völlig ausreichend;
    die Abweichung durch die Kugelannahme liegt weit unter der
    GPS-Ungenauigkeit.
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * ERDRADIUS_M * math.asin(math.sqrt(min(1.0, a)))


# ------------------------------------------------------------------
# GPX lesen
# ------------------------------------------------------------------


def _zeit(text: str):
    if not text:
        return None
    text = text.strip().replace("Z", "+00:00")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _zahl(text):
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _erweiterung(punkt, name: str):
    """Wert aus den <extensions> holen, unabhängig vom Namensraum.

    Apple und Garmin benennen dieselben Felder unterschiedlich und
    verwenden eigene Namensräume - deshalb wird über den lokalen Namen
    gesucht statt über einen festen Pfad.
    """
    for kind in punkt.iter():
        lokal = kind.tag.rsplit("}", 1)[-1]
        if lokal == name:
            return _zahl(kind.text)
    return None


def lies_gpx(pfad: Path) -> dict:
    """Eine GPX-Datei in Metadaten und Punktliste zerlegen."""
    try:
        baum = ET.parse(pfad)
    except ET.ParseError as fehler:
        raise ValueError(f"GPX-Datei nicht lesbar: {fehler}") from fehler

    wurzel = baum.getroot()
    punkte = []

    # Über den lokalen Namen suchen: GPX 1.0 und 1.1 nutzen verschiedene
    # Namensräume, beide kommen in Exporten vor
    for element in wurzel.iter():
        if element.tag.rsplit("}", 1)[-1] != "trkpt":
            continue

        lat = _zahl(element.get("lat"))
        lon = _zahl(element.get("lon"))
        if lat is None or lon is None:
            continue

        hoehe = None
        zeit = None
        for kind in element:
            lokal = kind.tag.rsplit("}", 1)[-1]
            if lokal == "ele":
                hoehe = _zahl(kind.text)
            elif lokal == "time":
                zeit = _zeit(kind.text)

        punkte.append(
            {
                "lat": lat,
                "lon": lon,
                "hoehe": hoehe,
                "zeit": zeit,
                "tempo_ms": _erweiterung(element, "speed"),
                "genauigkeit_m": _erweiterung(element, "hAcc"),
            }
        )

    return {"datei": Path(pfad).name, "punkte": punkte}


# ------------------------------------------------------------------
# Auswerten
# ------------------------------------------------------------------


def vermesse(punkte: list) -> dict:
    """Kennzahlen einer Route.

    Punkte mit schlechter GPS-Genauigkeit und unplausible Sprünge werden
    für die Distanz übersprungen - sonst summieren sich Messfehler zu
    Kilometern auf, besonders am Anfang einer Aufzeichnung.
    """
    ergebnis = {
        "punkte": len(punkte),
        "distanz_km": 0.0,
        "dauer_min": None,
        "aufstieg_m": 0.0,
        "abstieg_m": 0.0,
        "hoehe_min": None,
        "hoehe_max": None,
        "lat_min": None,
        "lat_max": None,
        "lon_min": None,
        "lon_max": None,
        "start_zeit": None,
        "ende_zeit": None,
        "verworfen": 0,
    }

    if not punkte:
        return ergebnis

    lats = [p["lat"] for p in punkte]
    lons = [p["lon"] for p in punkte]
    ergebnis.update(
        {
            "lat_min": min(lats),
            "lat_max": max(lats),
            "lon_min": min(lons),
            "lon_max": max(lons),
        }
    )

    zeiten = [p["zeit"] for p in punkte if p["zeit"]]
    if zeiten:
        ergebnis["start_zeit"] = min(zeiten)
        ergebnis["ende_zeit"] = max(zeiten)
        ergebnis["dauer_min"] = (max(zeiten) - min(zeiten)).total_seconds() / 60.0

    hoehen = [p["hoehe"] for p in punkte if p["hoehe"] is not None]
    if hoehen:
        ergebnis["hoehe_min"] = min(hoehen)
        ergebnis["hoehe_max"] = max(hoehen)

    brauchbar = [
        p for p in punkte if p["genauigkeit_m"] is None or p["genauigkeit_m"] <= MAX_GENAUIGKEIT_M
    ]
    ergebnis["verworfen"] = len(punkte) - len(brauchbar)

    strecke = 0.0
    for vorher, jetzt in zip(brauchbar, brauchbar[1:]):
        abstand = entfernung_m(vorher["lat"], vorher["lon"], jetzt["lat"], jetzt["lon"])

        if vorher["zeit"] and jetzt["zeit"]:
            sekunden = (jetzt["zeit"] - vorher["zeit"]).total_seconds()
            if sekunden > 0 and abstand / sekunden > MAX_TEMPO_MS:
                continue  # Sprung, keine Fortbewegung

        strecke += abstand

    ergebnis["distanz_km"] = strecke / 1000.0
    ergebnis.update(_hoehenmeter(brauchbar))
    return ergebnis


def _hoehenmeter(punkte: list, schwelle_m: float = 5.0) -> dict:
    """Auf- und Abstieg mit Schwelle gegen Höhenrauschen.

    Barometrische und GPS-Höhen schwanken typischerweise um ein bis drei
    Meter. Ohne Schwelle summiert sich das Rauschen bei einer langen Tour
    zu tausenden Höhenmetern auf, die nie gefahren wurden.

    Verglichen wird gegen die zuletzt *übernommene* Höhe, nicht gegen den
    Vorgängerpunkt. Dadurch geht auch ein flacher, aber stetiger Anstieg
    vollständig ein: die kleinen Schritte werden übersprungen, bis ihre
    Summe die Schwelle überschreitet.
    """
    auf = ab = 0.0
    letzte = None

    for punkt in punkte:
        if punkt["hoehe"] is None:
            continue
        if letzte is None:
            letzte = punkt["hoehe"]
            continue

        differenz = punkt["hoehe"] - letzte
        if abs(differenz) < schwelle_m:
            continue

        if differenz > 0:
            auf += differenz
        else:
            ab -= differenz
        letzte = punkt["hoehe"]

    return {"aufstieg_m": auf, "abstieg_m": ab}


# ------------------------------------------------------------------
# Datenschutz
# ------------------------------------------------------------------


def kuerze_um_heimat(punkte: list, heimat: tuple, radius_m: float = 500.0) -> list:
    """Punkte im Umkreis eines Heimatpunkts entfernen.

    Schneidet nur an Anfang und Ende, nicht in der Mitte: Wer an seinem
    Wohnort vorbeifährt, soll keine zerrissene Route bekommen. Genau
    Anfang und Ende sind der Teil, der die Adresse verrät.
    """
    if not punkte or not heimat:
        return punkte

    lat_heim, lon_heim = heimat

    def nah(punkt) -> bool:
        return entfernung_m(punkt["lat"], punkt["lon"], lat_heim, lon_heim) <= radius_m

    start = 0
    while start < len(punkte) and nah(punkte[start]):
        start += 1

    ende = len(punkte)
    while ende > start and nah(punkte[ende - 1]):
        ende -= 1

    return punkte[start:ende]


# ------------------------------------------------------------------
# Datenbank
# ------------------------------------------------------------------


def tabelle_existiert(conn: sqlite3.Connection) -> bool:
    return bool(
        conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='routen'"
        ).fetchone()
    )


def _finde_workout(conn: sqlite3.Connection, start_zeit, toleranz_min: float = 20.0):
    """Passendes Training über den Startzeitpunkt suchen.

    Die GPX-Aufzeichnung startet nicht auf die Sekunde genau mit dem
    Training, deshalb ein Zeitfenster statt exakter Übereinstimmung.
    """
    if start_zeit is None:
        return None

    zeile = conn.execute(
        """
        SELECT id, start_date,
               ABS(julianday(?) - julianday(substr(start_date, 1, 19))) * 24 * 60 AS abstand
        FROM workouts
        ORDER BY abstand
        LIMIT 1
        """,
        (start_zeit.strftime("%Y-%m-%d %H:%M:%S"),),
    ).fetchone()

    if zeile and zeile[2] is not None and zeile[2] <= toleranz_min:
        return zeile[0]
    return None


def importiere(ordner: Path, conn: sqlite3.Connection) -> dict:
    """Alle GPX-Dateien eines Ordners einlesen."""
    conn.executescript(SCHEMA)

    dateien = sorted(Path(ordner).glob("*.gpx"))
    zaehler = {"dateien": len(dateien), "neu": 0, "uebersprungen": 0, "punkte": 0}

    vorhanden = {zeile[0] for zeile in conn.execute("SELECT datei FROM routen")}

    for pfad in dateien:
        if pfad.name in vorhanden:
            zaehler["uebersprungen"] += 1
            continue

        try:
            gelesen = lies_gpx(pfad)
        except ValueError:
            zaehler["uebersprungen"] += 1
            continue

        punkte = gelesen["punkte"]
        if not punkte:
            zaehler["uebersprungen"] += 1
            continue

        werte = vermesse(punkte)
        workout_id = _finde_workout(conn, werte["start_zeit"])

        cursor = conn.execute(
            """
            INSERT INTO routen
                (datei, workout_id, start_zeit, ende_zeit, punkte, distanz_km,
                 dauer_min, aufstieg_m, abstieg_m, hoehe_min, hoehe_max,
                 lat_min, lat_max, lon_min, lon_max)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pfad.name,
                workout_id,
                werte["start_zeit"].isoformat() if werte["start_zeit"] else None,
                werte["ende_zeit"].isoformat() if werte["ende_zeit"] else None,
                werte["punkte"],
                werte["distanz_km"],
                werte["dauer_min"],
                werte["aufstieg_m"],
                werte["abstieg_m"],
                werte["hoehe_min"],
                werte["hoehe_max"],
                werte["lat_min"],
                werte["lat_max"],
                werte["lon_min"],
                werte["lon_max"],
            ),
        )
        routen_id = cursor.lastrowid

        conn.executemany(
            """
            INSERT INTO routen_punkte
                (routen_id, nummer, lat, lon, hoehe, zeit, tempo_ms, genauigkeit_m)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    routen_id,
                    nummer,
                    p["lat"],
                    p["lon"],
                    p["hoehe"],
                    p["zeit"].isoformat() if p["zeit"] else None,
                    p["tempo_ms"],
                    p["genauigkeit_m"],
                )
                for nummer, p in enumerate(punkte)
            ],
        )

        zaehler["neu"] += 1
        zaehler["punkte"] += len(punkte)

    conn.commit()
    return zaehler


def lade_uebersicht(conn: sqlite3.Connection):
    import pandas as pd

    df = pd.read_sql(
        """
        SELECT r.id, r.datei, r.start_zeit, r.punkte, r.distanz_km, r.dauer_min,
               r.aufstieg_m, r.hoehe_min, r.hoehe_max,
               r.lat_min, r.lat_max, r.lon_min, r.lon_max,
               REPLACE(w.activity_type, 'HKWorkoutActivityType', '') AS sportart
        FROM routen r
        LEFT JOIN workouts w ON w.id = r.workout_id
        ORDER BY r.start_zeit DESC
        """,
        conn,
    )
    if not df.empty:
        df["start_zeit"] = pd.to_datetime(df["start_zeit"], format="mixed", utc=True)
        df["sportart"] = df["sportart"].fillna("ohne Zuordnung")
    return df


def lade_punkte(conn: sqlite3.Connection, routen_id: int):
    import pandas as pd

    return pd.read_sql(
        "SELECT nummer, lat, lon, hoehe, zeit, tempo_ms, genauigkeit_m "
        "FROM routen_punkte WHERE routen_id = ? ORDER BY nummer",
        conn,
        params=[routen_id],
    )


def als_gpx(punkte, name: str = "Route") -> str:
    """Punktliste als GPX-Datei ausgeben - für andere Werkzeuge."""
    zeilen = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="Gesundheitsdashboard" '
        'xmlns="http://www.topografix.com/GPX/1/1">',
        "  <trk>",
        f"    <name>{name}</name>",
        "    <trkseg>",
    ]

    for punkt in punkte:
        zeilen.append(f'      <trkpt lat="{punkt["lat"]:.7f}" lon="{punkt["lon"]:.7f}">')
        if punkt.get("hoehe") is not None:
            zeilen.append(f"        <ele>{punkt['hoehe']:.1f}</ele>")
        if punkt.get("zeit"):
            zeilen.append(f"        <time>{punkt['zeit']}</time>")
        zeilen.append("      </trkpt>")

    zeilen += ["    </trkseg>", "  </trk>", "</gpx>"]
    return "\n".join(zeilen)
