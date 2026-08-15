"""Rauchtest: lädt jede Dashboard-Seite und meldet Ausnahmen.

Ergänzt die Unit-Tests um den Teil, den sie nicht abdecken - ob die
Streamlit-Seiten überhaupt fehlerfrei durchlaufen. Läuft auch ohne
Datenbank: die Seiten steigen dann geordnet mit einer Meldung aus, was
genau das erwartete Verhalten ist.

Aufruf:
    python tools/check_pages.py
"""

import glob
import logging
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

from streamlit.testing.v1 import AppTest  # noqa: E402

WURZEL = Path(__file__).parent.parent


def main() -> int:
    seiten = [WURZEL / "app" / "dashboard.py"]
    seiten += sorted(Path(p) for p in glob.glob(str(WURZEL / "app" / "pages" / "*.py")))

    fehler = 0
    for seite in seiten:
        name = seite.relative_to(WURZEL).as_posix()
        try:
            lauf = AppTest.from_file(str(seite), default_timeout=300).run()
        except Exception as ausnahme:  # noqa: BLE001
            print(f"FEHLER  {name}: {type(ausnahme).__name__}: {ausnahme}")
            fehler += 1
            continue

        if lauf.exception:
            print(f"FEHLER  {name}: {lauf.exception[0].value}")
            fehler += 1
        else:
            print(f"ok      {name}")

    print()
    if fehler:
        print(f"{fehler} von {len(seiten)} Seiten mit Fehlern.")
        return 1

    print(f"Alle {len(seiten)} Seiten laden fehlerfrei.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
