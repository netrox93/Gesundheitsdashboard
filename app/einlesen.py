"""Health-Export in einem Schritt einlesen (Kommandozeile).

Aufruf:
    python app/einlesen.py                       # sucht in imports/
    python app/einlesen.py C:/Pfad/Export.zip
    python app/einlesen.py C:/Pfad/apple_health_export

Erledigt alles: entpacken, Profil lesen, Messwerte importieren,
Tagesaggregate berechnen, EKGs einlesen.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pipeline
import profil as profil_modul


def main() -> None:
    quelle = Path(sys.argv[1]) if len(sys.argv) > 1 else pipeline.IMPORT_ORDNER

    if not quelle.exists():
        print(f"Pfad nicht gefunden: {quelle}")
        print("Die Export.zip in den Ordner 'imports' legen oder den Pfad angeben.")
        raise SystemExit(1)

    def melde(text: str, anteil: float) -> None:
        print(f"[{anteil * 100:3.0f} %] {text}")

    try:
        ergebnis = pipeline.einlesen(quelle, fortschritt=melde)
    except pipeline.EinleseFehler as fehler:
        print(f"\nFehler: {fehler}")
        raise SystemExit(1) from fehler

    zahlen = ergebnis["messwerte"]
    print()
    print(f"Messwerte gelesen:   {zahlen['seen']:,}".replace(",", "."))
    print(f"davon neu:           {zahlen['records']:,}".replace(",", "."))
    print(f"Trainings:           {zahlen['workouts']}")
    print(f"Aktivitätstage:      {zahlen['summaries']}")
    print(f"Tageswerte:          {ergebnis['tageswerte']:,}".replace(",", "."))
    print(f"Nächte:              {ergebnis['naechte']}")

    if ergebnis.get("ekg"):
        print(f"EKG-Aufzeichnungen:  {ergebnis['ekg']['neu']} neu")

    if ergebnis.get("profil"):
        alter = profil_modul.alter_am(ergebnis["profil"]["geburtsdatum"])
        geschlecht = profil_modul.GESCHLECHT_LABEL.get(
            ergebnis["profil"].get("geschlecht"), "ohne Angabe"
        )
        print(f"Profil:              {geschlecht}, {alter} Jahre")
    else:
        print("Profil:              nicht im Export enthalten - im Dashboard nachtragen")

    print("\nDashboard starten:  python -m streamlit run app/dashboard.py")


if __name__ == "__main__":
    main()
