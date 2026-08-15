"""Profil der auswertenden Person: Geburtsdatum und Geschlecht.

Beides steht im `<Me>`-Element des Apple-Health-Exports und wird beim
Import ausgelesen. Es wird gebraucht, weil ein Teil der Referenzbereiche
alters- und geschlechtsabhängig ist (VO2max, Schlafdauer, Schritte).

Fehlen die Angaben im Export, kann das Profil im Dashboard von Hand
gesetzt werden. Ohne Profil zeigt das Dashboard nur die
alters-unabhängigen Referenzbereiche.
"""

import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS profil (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    geburtsdatum TEXT,
    geschlecht TEXT,
    quelle TEXT,
    aktualisiert TEXT
);
"""

# Apple-Werte auf die im Code verwendeten Kürzel abbilden
GESCHLECHT_AUS_APPLE = {
    "HKBiologicalSexMale": "m",
    "HKBiologicalSexFemale": "w",
    "HKBiologicalSexOther": "divers",
    "HKBiologicalSexNotSet": None,
}

GESCHLECHT_LABEL = {
    "m": "männlich",
    "w": "weiblich",
    "divers": "divers",
}


def lies_aus_export(xml_pfad: Path) -> dict:
    """Geburtsdatum und Geschlecht aus dem <Me>-Element lesen.

    Liest nur den Anfang der Datei - das Element steht direkt hinter dem
    Kopf, und der Export ist mehrere Gigabyte gross.
    """
    with open(xml_pfad, encoding="utf-8", errors="replace") as datei:
        anfang = datei.read(200_000)

    treffer = re.search(r"<Me\b[^>]*>", anfang)
    if not treffer:
        return {}

    block = treffer.group()
    geburtstag = re.search(r'HKCharacteristicTypeIdentifierDateOfBirth\s*=\s*"([^"]*)"', block)
    geschlecht = re.search(r'HKCharacteristicTypeIdentifierBiologicalSex\s*=\s*"([^"]*)"', block)

    ergebnis = {}
    if geburtstag and geburtstag.group(1).strip():
        ergebnis["geburtsdatum"] = geburtstag.group(1).strip()
    if geschlecht:
        ergebnis["geschlecht"] = GESCHLECHT_AUS_APPLE.get(geschlecht.group(1).strip())

    return {k: v for k, v in ergebnis.items() if v}


def speichere(
    conn: sqlite3.Connection, geburtsdatum: str, geschlecht: str, quelle: str = "Health-Export"
) -> None:
    conn.executescript(SCHEMA)
    conn.execute(
        """
        INSERT INTO profil (id, geburtsdatum, geschlecht, quelle, aktualisiert)
        VALUES (1, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            geburtsdatum = excluded.geburtsdatum,
            geschlecht = excluded.geschlecht,
            quelle = excluded.quelle,
            aktualisiert = excluded.aktualisiert
        """,
        (geburtsdatum, geschlecht, quelle, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()


def lade(conn: sqlite3.Connection) -> dict:
    """Profil aus der Datenbank; leeres Dict, wenn keins hinterlegt ist."""
    conn.executescript(SCHEMA)
    zeile = conn.execute(
        "SELECT geburtsdatum, geschlecht, quelle FROM profil WHERE id = 1"
    ).fetchone()

    if not zeile or not zeile[0]:
        return {}

    return {
        "geburtsdatum": zeile[0],
        "geschlecht": zeile[1],
        "quelle": zeile[2],
        "alter": alter_am(zeile[0]),
    }


def alter_am(geburtsdatum: str, stichtag: date = None) -> int:
    """Alter in Jahren, korrekt gerundet auf den letzten Geburtstag."""
    stichtag = stichtag or date.today()

    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            geboren = datetime.strptime(geburtsdatum.strip(), fmt).date()
            break
        except (ValueError, AttributeError):
            continue
    else:
        return None

    return (
        stichtag.year
        - geboren.year
        - ((stichtag.month, stichtag.day) < (geboren.month, geboren.day))
    )


def beschreibung(profil: dict) -> str:
    """Kurztext fürs Dashboard und den Bericht."""
    if not profil:
        return "kein Profil hinterlegt"

    teile = []
    geschlecht = GESCHLECHT_LABEL.get(profil.get("geschlecht"))
    if geschlecht:
        teile.append(geschlecht)
    if profil.get("alter") is not None:
        teile.append(f"{profil['alter']} Jahre")

    return ", ".join(teile) if teile else "Profil unvollständig"
