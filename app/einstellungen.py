"""Einstellungen des Projekts, vor allem der Ort der Datenbank.

Standardmässig liegt die Datenbank unter `data/health.db` im
Projektordner. Sie lässt sich aber auch woanders ablegen und von hier aus
verknüpfen - etwa auf einer externen Platte, in einem Cloud-Ordner oder
auf einem Netzlaufwerk. Das ist der Weg, eine bestehende Auswertung auf
einen anderen Rechner mitzunehmen, ohne den Export erneut einzulesen.

Die Einstellungen liegen in `config/einstellungen.json` und sind von der
Versionskontrolle ausgeschlossen - der Pfad ist rechnerabhängig.
"""

import json
import sqlite3
from pathlib import Path

PROJEKT = Path(__file__).parent.parent
KONFIG_DATEI = PROJEKT / "config" / "einstellungen.json"
STANDARD_DB = PROJEKT / "data" / "health.db"

# Tabellen, die eine gültige Datenbank dieses Projekts enthalten muss
PFLICHT_TABELLEN = {"records", "daily_metrics"}


def _lade_konfig() -> dict:
    if not KONFIG_DATEI.exists():
        return {}
    try:
        return json.loads(KONFIG_DATEI.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Eine kaputte Konfiguration darf das Dashboard nicht blockieren
        return {}


def _speichere_konfig(konfig: dict) -> None:
    KONFIG_DATEI.parent.mkdir(parents=True, exist_ok=True)
    KONFIG_DATEI.write_text(json.dumps(konfig, indent=2, ensure_ascii=False), encoding="utf-8")


def db_pfad() -> Path:
    """Aktuell verwendete Datenbank."""
    eigener = _lade_konfig().get("db_pfad")
    return Path(eigener) if eigener else STANDARD_DB


def ist_standardpfad() -> bool:
    return db_pfad() == STANDARD_DB


def setze_db_pfad(pfad) -> None:
    konfig = _lade_konfig()
    konfig["db_pfad"] = str(Path(pfad).resolve())
    _speichere_konfig(konfig)


def zuruecksetzen() -> None:
    """Wieder die Datenbank im Projektordner verwenden."""
    konfig = _lade_konfig()
    konfig.pop("db_pfad", None)
    _speichere_konfig(konfig)


def lade_heimat() -> dict:
    """Heimatpunkt für die Datenschutz-Kürzung von Routen.

    Standardmässig aktiv: GPX-Tracks beginnen fast immer an der
    Wohnadresse, und das ist der heikelste Teil dieser Daten.
    """
    konfig = _lade_konfig().get("heimat", {})
    return {
        "lat": konfig.get("lat"),
        "lon": konfig.get("lon"),
        "radius_m": konfig.get("radius_m", 500),
        "aktiv": konfig.get("aktiv", True),
    }


def speichere_heimat(lat, lon, radius_m: float = 500, aktiv: bool = True) -> None:
    konfig = _lade_konfig()
    konfig["heimat"] = {
        "lat": lat,
        "lon": lon,
        "radius_m": radius_m,
        "aktiv": aktiv,
    }
    _speichere_konfig(konfig)


def pruefe_datenbank(pfad) -> dict:
    """Prüft, ob eine Datei eine brauchbare Datenbank dieses Projekts ist.

    Wird vor dem Verknüpfen aufgerufen, damit eine falsch ausgewählte
    Datei sofort auffällt und nicht erst später als unverständlicher
    Fehler im Dashboard auftaucht.
    """
    pfad = Path(pfad)
    ergebnis = {"gueltig": False, "meldung": "", "tabellen": {}, "groesse_mb": 0.0}

    if not pfad.exists():
        ergebnis["meldung"] = "Die Datei existiert nicht."
        return ergebnis

    if not pfad.is_file():
        ergebnis["meldung"] = "Der Pfad zeigt auf einen Ordner, nicht auf eine Datei."
        return ergebnis

    ergebnis["groesse_mb"] = pfad.stat().st_size / 1024**2

    # SQLite-Dateien beginnen mit einer festen Kennung
    try:
        with open(pfad, "rb") as datei:
            if datei.read(16) != b"SQLite format 3\x00":
                ergebnis["meldung"] = (
                    "Die Datei ist keine SQLite-Datenbank. Erwartet wird eine "
                    "Datei wie 'health.db' aus diesem Projekt."
                )
                return ergebnis
    except OSError as fehler:
        ergebnis["meldung"] = f"Die Datei liess sich nicht lesen: {fehler}"
        return ergebnis

    try:
        conn = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
        vorhanden = {
            zeile[0] for zeile in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

        fehlend = PFLICHT_TABELLEN - vorhanden
        if fehlend:
            conn.close()
            ergebnis["meldung"] = (
                "Die Datei ist zwar eine SQLite-Datenbank, stammt aber nicht "
                f"aus diesem Projekt (es fehlt: {', '.join(sorted(fehlend))})."
            )
            return ergebnis

        for tabelle in ("records", "daily_metrics", "daily_sleep", "workouts", "ecg"):
            if tabelle in vorhanden:
                anzahl = conn.execute(f"SELECT COUNT(*) FROM {tabelle}").fetchone()[0]
                ergebnis["tabellen"][tabelle] = anzahl

        zeitraum = conn.execute("SELECT MIN(date), MAX(date) FROM daily_metrics").fetchone()
        ergebnis["zeitraum"] = zeitraum if zeitraum and zeitraum[0] else None
        conn.close()
    except sqlite3.DatabaseError as fehler:
        ergebnis["meldung"] = f"Die Datenbank liess sich nicht öffnen: {fehler}"
        return ergebnis

    ergebnis["gueltig"] = True
    ergebnis["meldung"] = "Gültige Datenbank dieses Projekts."
    return ergebnis
