"""Einlesen und Vermessen der EKG-Aufzeichnungen der Apple Watch.

Wichtig zur Einordnung: Die Apple Watch zeichnet eine EINZELNE Ableitung
auf (entspricht etwa Ableitung I nach Einthoven) über 30 Sekunden. Das
klinische Ruhe-EKG hat 12 Ableitungen. Die Zulassung (FDA/CE) umfasst die
Unterscheidung von Sinusrhythmus und Vorhofflimmern - nicht die Erkennung
von Herzinfarkten, Blockbildern oder anderen Rhythmusstörungen.

Dieses Modul interpretiert die Kurve deshalb NICHT. Es liest sie ein,
stellt sie massstabsgetreu dar und misst, was sich objektiv messen lässt:
Herzfrequenz und die Abstände zwischen den Herzschlägen. Die Beurteilung
der Kurve bleibt der Ärztin oder dem Arzt vorbehalten.
"""

import io
import re
import sqlite3
import zlib
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import signal

# Feste Kopfzeilen der von Apple exportierten CSV-Dateien (deutsche Fassung)
KOPF_FELDER = {
    "Aufzeichnungsdatum": "aufnahme",
    "Klassifizierung": "klassifikation",
    "Symptome": "symptome",
    "Softwareversion": "software",
    "Gerät": "geraet",
    "Messrate": "messrate",
    "Einheit": "einheit",
}

# Apple-Klassifikationen mit Erklärung. Der Text beschreibt, was die
# Klassifikation bedeutet - er stellt keine Diagnose dar.
KLASSIFIKATIONEN = {
    "Sinusrhythmus": (
        "Regelmässiger Herzrhythmus im Bereich von 50-100 Schlägen pro "
        "Minute, wie er bei Gesunden erwartet wird. Die Einstufung schliesst "
        "andere Herzerkrankungen ausdrücklich nicht aus."
    ),
    "Vorhofflimmern": (
        "Hinweis auf einen unregelmässigen Rhythmus, der auf Vorhofflimmern "
        "hindeuten kann. Ein solcher Befund gehört ärztlich abgeklärt."
    ),
    "Hohe Herzfrequenz": (
        "Die Herzfrequenz lag über 100 Schlägen pro Minute. In diesem Bereich "
        "kann die Uhr nicht auf Vorhofflimmern prüfen. Nach Belastung, bei "
        "Aufregung, Fieber oder Koffein ist eine hohe Frequenz erwartbar."
    ),
    "Niedrige Herzfrequenz": (
        "Die Herzfrequenz lag unter 50 Schlägen pro Minute. In diesem Bereich "
        "ist keine Prüfung auf Vorhofflimmern möglich. Bei Ausdauertrainierten "
        "sind niedrige Frequenzen häufig."
    ),
    "Schlechte Aufzeichnung": (
        "Die Signalqualität reichte für eine Auswertung nicht aus, meist durch "
        "Bewegung, losen Sitz der Uhr oder trockene Haut. Kein Befund - die "
        "Messung ist schlicht nicht verwertbar."
    ),
    "Nicht klassifiziert": (
        "Die Aufzeichnung liess sich keiner der vorgesehenen Kategorien zuordnen."
    ),
}


# ------------------------------------------------------------------
# Einlesen
# ------------------------------------------------------------------


def _zahl(text: str) -> float:
    """'512 Hertz' -> 512.0, '57,992' -> 57.992 (deutsches Dezimalkomma)."""
    treffer = re.search(r"-?[\d.,]+", text)
    if not treffer:
        return float("nan")
    roh = treffer.group().replace(".", "").replace(",", ".")
    try:
        return float(roh)
    except ValueError:
        return float("nan")


def lies_csv(pfad: Path) -> dict:
    """Eine EKG-CSV in Metadaten und Messwerte zerlegen.

    Der Personenname aus der Datei wird bewusst NICHT übernommen - er wird
    für die Auswertung nicht gebraucht und hat in der Datenbank nichts
    verloren.
    """
    text = pfad.read_text(encoding="utf-8-sig", errors="replace")
    meta = {"datei": pfad.name}
    werte = []

    for zeile in io.StringIO(text):
        zeile = zeile.strip()
        if not zeile:
            continue

        feld, _, rest = zeile.partition(",")
        feld = feld.strip()
        rest = rest.strip().strip('"')

        if feld in KOPF_FELDER:
            meta[KOPF_FELDER[feld]] = rest
            continue
        if feld in ("Name", "Geburtstag", "Ableitung"):
            continue  # Name und Geburtstag bewusst verwerfen

        # Ab hier reine Messwerte
        wert = _zahl(zeile)
        if not np.isnan(wert):
            werte.append(wert)

    meta["messrate"] = _zahl(meta.get("messrate", "512")) or 512.0
    meta["signal"] = np.asarray(werte, dtype=np.float32)

    roh_datum = meta.get("aufnahme", "")
    meta["zeitpunkt"] = _parse_zeit(roh_datum)
    return meta


def _parse_zeit(text: str):
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


# ------------------------------------------------------------------
# Signalverarbeitung
# ------------------------------------------------------------------


def filtere(rohsignal: np.ndarray, messrate: float) -> np.ndarray:
    """Basislinienschwankung und hochfrequentes Rauschen entfernen.

    Bandpass 0,5-40 Hz - der übliche Bereich für die Darstellung eines
    Ruhe-EKG. Unterhalb von 0,5 Hz liegt die Atem- und
    Bewegungs-Basislinie, oberhalb von 40 Hz im Wesentlichen Muskel- und
    Netzbrummen.
    """
    if len(rohsignal) < 100:
        return rohsignal

    nyquist = messrate / 2
    hoch = 0.5 / nyquist
    tief = min(40.0 / nyquist, 0.99)

    sos = signal.butter(3, [hoch, tief], btype="bandpass", output="sos")
    return signal.sosfiltfilt(sos, rohsignal).astype(np.float32)


def finde_r_zacken(gefiltert: np.ndarray, messrate: float) -> np.ndarray:
    """R-Zacken über Energie-Schwelle mit Refraktärzeit.

    Vorgehen angelehnt an das Verfahren von Pan und Tompkins: Ableitung,
    Quadrierung, gleitendes Fenster - dadurch treten die steilen R-Zacken
    gegenüber P- und T-Wellen deutlich hervor. Die Refraktärzeit von 200 ms
    verhindert, dass eine T-Welle als zweiter Schlag gezählt wird.
    """
    if len(gefiltert) < int(messrate):
        return np.array([], dtype=int)

    ableitung = np.diff(gefiltert, prepend=gefiltert[0])
    energie = ableitung**2
    fenster = max(1, int(0.12 * messrate))
    geglaettet = np.convolve(energie, np.ones(fenster) / fenster, mode="same")

    schwelle = np.mean(geglaettet) + 1.2 * np.std(geglaettet)
    mindestabstand = int(0.2 * messrate)

    spitzen, _ = signal.find_peaks(geglaettet, height=schwelle, distance=mindestabstand)
    if len(spitzen) == 0:
        return np.array([], dtype=int)

    fein = max(1, int(0.05 * messrate))
    fenster = [(max(0, s - fein), min(len(gefiltert), s + fein)) for s in spitzen]
    fenster = [(von, bis) for von, bis in fenster if bis > von]
    if not fenster:
        return np.array([], dtype=int)

    # Polarität einmal für die gesamte Aufzeichnung festlegen.
    #
    # Bei manchen Ableitungen ist die S-Zacke tiefer als die R-Zacke hoch.
    # Nimmt man je Schlag einfach den grössten Betrag, springt der
    # markierte Punkt zwischen R und S hin und her - die Abstände werden
    # dadurch systematisch verzerrt. Deshalb wird global entschieden, ob
    # nach oben oder nach unten gesucht wird, und diese Richtung dann für
    # alle Schläge beibehalten.
    hoch = np.median([np.max(gefiltert[von:bis]) for von, bis in fenster])
    tief = np.median([np.min(gefiltert[von:bis]) for von, bis in fenster])
    nach_oben = abs(hoch) >= abs(tief)

    genaue = [
        von + int(np.argmax(gefiltert[von:bis]) if nach_oben else np.argmin(gefiltert[von:bis]))
        for von, bis in fenster
    ]

    return np.unique(genaue)


QUALITAET_GUT = 0.08
QUALITAET_EINGESCHRAENKT = 0.20


def vermesse(meta: dict) -> dict:
    """Objektiv messbare Kennwerte einer Aufzeichnung.

    Bewusst nur Frequenz und Schlagabstände - alles, was eine Deutung der
    Kurvenform wäre (ST-Strecke, QT-Zeit, Blockbilder), gehört in
    ärztliche Hand und wird hier nicht berechnet.

    Die automatische R-Zacken-Erkennung verpasst bei unruhigem Signal
    einzelne Schläge oder zählt Artefakte mit. Ein verpasster Schlag
    verdoppelt den gemessenen Abstand und erzeugt scheinbar dramatische
    Werte. Deshalb werden Abstände gegen den Median geprüft, alle
    Kennwerte robust aus den verbliebenen berechnet und der Anteil der
    verworfenen Abstände als Qualitätsmass mitgeführt - eine unsichere
    Messung soll als solche erkennbar sein und nicht als Befund
    durchgehen.
    """
    messrate = meta["messrate"]
    gefiltert = filtere(meta["signal"], messrate)
    r_zacken = finde_r_zacken(gefiltert, messrate)

    ergebnis = {
        "dauer_s": len(meta["signal"]) / messrate if messrate else 0.0,
        "schlaege": len(r_zacken),
        "hf_mittel": None,
        "hf_min": None,
        "hf_max": None,
        "rr_mittel_ms": None,
        "rr_streuung_ms": None,
        "rmssd_ms": None,
        "unregelmaessigkeit": None,
        "verworfen_anteil": None,
        "qualitaet": "nicht auswertbar",
    }

    if len(r_zacken) < 4:
        return ergebnis

    rr_ms = np.diff(r_zacken) / messrate * 1000.0
    rr_ms = rr_ms[(rr_ms > 200) & (rr_ms < 3000)]
    if len(rr_ms) < 3:
        return ergebnis

    # Abstände, die stark vom Median abweichen, stammen fast immer aus
    # verpassten oder zusätzlich erkannten Zacken
    median_rr = float(np.median(rr_ms))
    gueltig = rr_ms[(rr_ms > 0.55 * median_rr) & (rr_ms < 1.75 * median_rr)]
    if len(gueltig) < 3:
        return ergebnis

    verworfen = 1.0 - len(gueltig) / len(rr_ms)
    if verworfen <= QUALITAET_GUT:
        qualitaet = "gut"
    elif verworfen <= QUALITAET_EINGESCHRAENKT:
        qualitaet = "eingeschränkt"
    else:
        qualitaet = "unzuverlässig"

    hf = 60000.0 / gueltig
    ergebnis.update(
        {
            # Median statt Mittelwert: unempfindlich gegen die
            # verbliebenen Fehlerkennungen
            "hf_mittel": float(np.median(hf)),
            "hf_min": float(np.min(hf)),
            "hf_max": float(np.max(hf)),
            "rr_mittel_ms": float(np.median(gueltig)),
            "rr_streuung_ms": float(np.std(gueltig)),
            "rmssd_ms": float(np.sqrt(np.mean(np.diff(gueltig) ** 2))),
            # Variationskoeffizient: Streuung im Verhältnis zum Mittel.
            # Rein deskriptiv, ausdrücklich kein Rhythmusbefund.
            "unregelmaessigkeit": float(np.std(gueltig) / np.mean(gueltig) * 100),
            "verworfen_anteil": float(verworfen),
            "qualitaet": qualitaet,
        }
    )
    return ergebnis


# ------------------------------------------------------------------
# Datenbank
# ------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS ecg (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aufnahme TEXT NOT NULL UNIQUE,
    datum TEXT NOT NULL,
    klassifikation TEXT,
    symptome TEXT,
    geraet TEXT,
    software TEXT,
    messrate REAL,
    dauer_s REAL,
    schlaege INTEGER,
    hf_mittel REAL,
    hf_min REAL,
    hf_max REAL,
    rr_mittel_ms REAL,
    rr_streuung_ms REAL,
    rmssd_ms REAL,
    unregelmaessigkeit REAL,
    verworfen_anteil REAL,
    qualitaet TEXT,
    signal BLOB
);

CREATE INDEX IF NOT EXISTS idx_ecg_datum ON ecg (datum);
"""


def packe_signal(werte: np.ndarray) -> bytes:
    return zlib.compress(werte.astype(np.float32).tobytes(), level=6)


def entpacke_signal(blob: bytes) -> np.ndarray:
    return np.frombuffer(zlib.decompress(blob), dtype=np.float32)


def importiere(ordner: Path, conn: sqlite3.Connection) -> dict:
    """Alle EKG-CSVs eines Ordners einlesen und vermessen."""
    conn.executescript(SCHEMA)

    dateien = sorted(Path(ordner).glob("*.csv"))
    neu = uebersprungen = 0

    for pfad in dateien:
        meta = lies_csv(pfad)
        if meta["zeitpunkt"] is None or len(meta["signal"]) == 0:
            uebersprungen += 1
            continue

        werte = vermesse(meta)
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO ecg
                (aufnahme, datum, klassifikation, symptome, geraet, software,
                 messrate, dauer_s, schlaege, hf_mittel, hf_min, hf_max,
                 rr_mittel_ms, rr_streuung_ms, rmssd_ms, unregelmaessigkeit,
                 verworfen_anteil, qualitaet, signal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                meta["aufnahme"],
                meta["zeitpunkt"].strftime("%Y-%m-%d"),
                meta.get("klassifikation"),
                meta.get("symptome") or "Ohne",
                meta.get("geraet"),
                meta.get("software"),
                meta["messrate"],
                werte["dauer_s"],
                werte["schlaege"],
                werte["hf_mittel"],
                werte["hf_min"],
                werte["hf_max"],
                werte["rr_mittel_ms"],
                werte["rr_streuung_ms"],
                werte["rmssd_ms"],
                werte["unregelmaessigkeit"],
                werte["verworfen_anteil"],
                werte["qualitaet"],
                packe_signal(meta["signal"]),
            ),
        )
        neu += cursor.rowcount

    conn.commit()
    return {"dateien": len(dateien), "neu": neu, "uebersprungen": uebersprungen}


def lade_uebersicht(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql(
        "SELECT id, aufnahme, datum, klassifikation, symptome, geraet, "
        "dauer_s, schlaege, hf_mittel, hf_min, hf_max, rr_mittel_ms, "
        "rr_streuung_ms, rmssd_ms, unregelmaessigkeit, verworfen_anteil, "
        "qualitaet FROM ecg ORDER BY aufnahme DESC",
        conn,
    )
    if not df.empty:
        df["datum"] = pd.to_datetime(df["datum"])
    return df


def lade_signal(conn: sqlite3.Connection, ecg_id: int) -> tuple:
    zeile = conn.execute("SELECT signal, messrate FROM ecg WHERE id = ?", (ecg_id,)).fetchone()
    if not zeile:
        return np.array([]), 512.0
    return entpacke_signal(zeile[0]), zeile[1]


def tabelle_existiert(conn: sqlite3.Connection) -> bool:
    return bool(
        conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ecg'").fetchone()
    )
