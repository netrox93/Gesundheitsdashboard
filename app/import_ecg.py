"""Importiert die EKG-Aufzeichnungen aus dem Apple-Health-Export.

Aufruf:
    python app/import_ecg.py imports/apple_health_export/electrocardiograms

Ohne Argument wird der Standardpfad im imports-Ordner verwendet.

Der Personenname und das Geburtsdatum aus den CSV-Dateien werden bewusst
nicht übernommen - für die Auswertung werden sie nicht gebraucht.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import ecg
import metrics_core as core

STANDARD_ORDNER = (
    Path(__file__).parent.parent / "imports" / "apple_health_export" / "electrocardiograms"
)


def main() -> None:
    ordner = Path(sys.argv[1]) if len(sys.argv) > 1 else STANDARD_ORDNER

    if not ordner.exists():
        print(f"Ordner nicht gefunden: {ordner}")
        print("Der Export enthält die EKGs unter apple_health_export/electrocardiograms.")
        raise SystemExit(1)

    if not core.db_exists():
        print("Keine Datenbank gefunden - erst import_export.py ausführen.")
        raise SystemExit(1)

    conn = core.connect()
    print(f"Lese EKGs aus {ordner} ...")
    ergebnis = ecg.importiere(ordner, conn)

    uebersicht = ecg.lade_uebersicht(conn)
    conn.close()

    print(
        f"Fertig: {ergebnis['dateien']} Dateien gelesen, "
        f"{ergebnis['neu']} neu aufgenommen, "
        f"{ergebnis['uebersprungen']} übersprungen."
    )

    if not uebersicht.empty:
        print(f"\nInsgesamt {len(uebersicht)} Aufzeichnungen in der Datenbank:")
        for klasse, anzahl in uebersicht["klassifikation"].value_counts().items():
            print(f"  {anzahl:>3}x {klasse}")


if __name__ == "__main__":
    main()
