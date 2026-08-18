"""Kompletter Einlese-Vorgang in einem Aufruf.

Nimmt eine exportierte ZIP-Datei oder einen entpackten Export-Ordner und
erledigt alles: entpacken, Profil lesen, Messwerte importieren,
Tagesaggregate berechnen, EKGs einlesen.

Wird sowohl vom Dashboard (Seite "Daten einlesen") als auch von der
Kommandozeile (`python app/einlesen.py`) verwendet.
"""

import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import build_daily
import ecg
import import_export
import metrics_core as core
import profil as profil_modul
import routen as routen_modul

BASIS = Path(__file__).parent.parent
IMPORT_ORDNER = BASIS / "imports"


class EinleseFehler(Exception):
    """Verständlicher Fehler für die Anzeige im Dashboard."""


def finde_export(pfad: Path) -> dict:
    """Export.xml und EKG-Ordner in einem entpackten Export finden.

    Apple legt den Export je nach Version und Sprache unterschiedlich ab
    (`apple_health_export/`, `Export.xml` oder `export.xml`), deshalb
    wird gesucht statt fest verdrahtet.
    """
    pfad = Path(pfad)

    kandidaten = [
        pfad / "Export.xml",
        pfad / "export.xml",
        pfad / "apple_health_export" / "Export.xml",
        pfad / "apple_health_export" / "export.xml",
    ]
    xml = next((k for k in kandidaten if k.exists()), None)

    if xml is None:
        # Tiefer suchen, aber nur ein paar Ebenen
        for tiefe in ("*/Export.xml", "*/export.xml", "*/*/Export.xml", "*/*/export.xml"):
            treffer = sorted(pfad.glob(tiefe))
            if treffer:
                xml = treffer[0]
                break

    if xml is None:
        raise EinleseFehler(
            "In den Daten wurde keine Export.xml gefunden. Erwartet wird der "
            "Ordner 'apple_health_export' aus dem Health-Export."
        )

    ekg_ordner = xml.parent / "electrocardiograms"
    routen_ordner = xml.parent / "workout-routes"
    return {
        "xml": xml,
        "ekg": ekg_ordner if ekg_ordner.is_dir() else None,
        "routen": routen_ordner if routen_ordner.is_dir() else None,
    }


def entpacke(zip_pfad: Path, ziel: Path = None) -> Path:
    """ZIP des Health-Exports entpacken."""
    ziel = ziel or (IMPORT_ORDNER / "entpackt")

    if ziel.exists():
        shutil.rmtree(ziel)
    ziel.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_pfad) as archiv:
            archiv.extractall(ziel)
    except zipfile.BadZipFile as fehler:
        raise EinleseFehler(
            "Die Datei liess sich nicht als ZIP öffnen. Bitte die aus der "
            "Health-App exportierte Datei unverändert auswählen."
        ) from fehler

    return ziel


def einlesen(quelle: Path, fortschritt=None, mit_ekg: bool = True) -> dict:
    """Kompletter Vorgang. `fortschritt` ist eine Funktion (text, anteil)."""

    def melde(text: str, anteil: float) -> None:
        if fortschritt:
            fortschritt(text, anteil)

    quelle = Path(quelle)
    if not quelle.exists():
        raise EinleseFehler(f"Pfad nicht gefunden: {quelle}")

    if quelle.is_file() and quelle.suffix.lower() == ".zip":
        melde("Entpacke Export ...", 0.05)
        quelle = entpacke(quelle)

    melde("Suche Export-Dateien ...", 0.12)
    gefunden = finde_export(quelle)

    ergebnis = {"xml": str(gefunden["xml"])}

    melde("Lese Profil ...", 0.15)
    conn = import_export.get_connection()
    profil_daten = profil_modul.lies_aus_export(gefunden["xml"])
    if profil_daten.get("geburtsdatum"):
        profil_modul.speichere(
            conn,
            profil_daten["geburtsdatum"],
            profil_daten.get("geschlecht"),
            quelle="Health-Export",
        )
        ergebnis["profil"] = profil_daten
    else:
        ergebnis["profil"] = None

    melde("Lese Messwerte ein - das dauert bei grossen Exporten einige Minuten ...", 0.2)
    zahlen = import_export.import_file(gefunden["xml"], conn)
    import_export.protokolliere(conn, gefunden["xml"], zahlen)
    conn.close()
    ergebnis["messwerte"] = zahlen

    melde("Berechne Tageswerte ...", 0.75)
    conn = core.connect()
    conn.executescript((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))
    ergebnis["tageswerte"] = build_daily.build_daily_metrics(conn)
    ergebnis["naechte"] = build_daily.build_daily_sleep(conn)

    if mit_ekg and gefunden["ekg"]:
        melde("Lese EKG-Aufzeichnungen ein ...", 0.90)
        ergebnis["ekg"] = ecg.importiere(gefunden["ekg"], conn)
    else:
        ergebnis["ekg"] = None

    if gefunden["routen"]:
        melde("Lese aufgezeichnete Routen ein ...", 0.95)
        ergebnis["routen"] = routen_modul.importiere(gefunden["routen"], conn)
    else:
        ergebnis["routen"] = None

    conn.close()
    melde("Fertig.", 1.0)
    return ergebnis
