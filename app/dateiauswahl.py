"""Den Health-Export finden, ohne dass jemand einen Pfad tippen muss.

Drei Wege, in dieser Reihenfolge:

1. **Automatisch suchen** - in Downloads, auf dem Schreibtisch, in
   Dokumenten und auf angeschlossenen Wechseldatenträgern. In den
   allermeisten Fällen liegt der Export dort und muss nur bestätigt werden.
2. **Datei-Dialog** - der gewohnte Auswahldialog des Betriebssystems.
   Läuft in einem eigenen Prozess, damit er den Streamlit-Server nicht
   blockiert.
3. **Pfad eintippen** - letzter Ausweg, mit toleranter Aufbereitung der
   Eingabe (Anführungszeichen aus "Als Pfad kopieren", file:///-URLs).
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

# Ordner, in denen Exporte üblicherweise landen
SUCHORTE_RELATIV = [
    "Downloads",
    "Desktop",
    "Documents",
    "Dokumente",
    "Schreibtisch",
    "OneDrive/Downloads",
    "OneDrive/Desktop",
    "OneDrive/Dokumente",
    "OneDrive/Documents",
]

ZIP_MUSTER = ["Export.zip", "export.zip", "*export*.zip", "*health*.zip", "*Health*.zip"]
ORDNER_MUSTER = ["apple_health_export", "*/apple_health_export"]


def bereinige_pfad(eingabe: str) -> str:
    """Tippfehlerfreundliche Aufbereitung einer Pfadeingabe.

    Windows' "Als Pfad kopieren" liefert den Pfad in Anführungszeichen,
    ein aus dem Browser gezogener Pfad kommt als file:///-URL. Beides
    würde sonst als "nicht gefunden" abgewiesen.
    """
    if not eingabe:
        return ""

    text = eingabe.strip()

    for zeichen in ('"', "'"):
        if text.startswith(zeichen) and text.endswith(zeichen) and len(text) > 1:
            text = text[1:-1]

    if text.lower().startswith("file:"):
        zerlegt = urlparse(text)
        text = unquote(zerlegt.path)
        # file:///C:/... -> /C:/... : führenden Schrägstrich entfernen
        if len(text) > 2 and text[0] == "/" and text[2] == ":":
            text = text[1:]

    return os.path.expanduser(text.strip())


def _beschreibe(pfad: Path) -> dict:
    if pfad.is_dir():
        groesse = sum(f.stat().st_size for f in pfad.rglob("*") if f.is_file())
        art = "Ordner"
    else:
        groesse = pfad.stat().st_size
        art = "ZIP-Datei"

    return {
        "pfad": pfad,
        "art": art,
        "groesse_mb": groesse / 1024**2,
        "geaendert": datetime.fromtimestamp(pfad.stat().st_mtime),
    }


def _suchorte() -> list:
    orte = []
    heim = Path.home()

    for relativ in SUCHORTE_RELATIV:
        ort = heim / relativ
        if ort.is_dir():
            orte.append(ort)

    orte.append(heim)

    # Wechseldatenträger: Laufwerksbuchstaben durchgehen. Der Export liegt
    # dort oft im Wurzelverzeichnis eines USB-Sticks.
    if os.name == "nt":
        for buchstabe in "DEFGHIJKLMNOPQRSTUVWXYZ":
            laufwerk = Path(f"{buchstabe}:/")
            try:
                if laufwerk.is_dir():
                    orte.append(laufwerk)
            except OSError:
                continue
    else:
        for basis in ("/media", "/mnt", "/Volumes"):
            wurzel = Path(basis)
            if wurzel.is_dir():
                orte.extend(p for p in wurzel.iterdir() if p.is_dir())

    return orte


def finde_exporte(max_treffer: int = 8) -> list:
    """Sucht an den üblichen Orten nach Health-Exporten.

    Sucht bewusst flach (Ordner selbst und eine Ebene darunter) - eine
    vollständige Suche über die Festplatte würde je nach Rechner Minuten
    dauern und den Nutzer im Ungewissen lassen.
    """
    gefunden = {}

    for ort in _suchorte():
        for muster in ZIP_MUSTER:
            try:
                treffer = list(ort.glob(muster))
            except OSError:
                continue
            for pfad in treffer:
                if pfad.is_file():
                    gefunden.setdefault(pfad.resolve(), pfad)

        for muster in ORDNER_MUSTER:
            try:
                treffer = list(ort.glob(muster))
            except OSError:
                continue
            for pfad in treffer:
                if pfad.is_dir() and any(
                    (pfad / name).exists() for name in ("Export.xml", "export.xml")
                ):
                    gefunden.setdefault(pfad.resolve(), pfad)

    ergebnisse = []
    for pfad in gefunden.values():
        try:
            ergebnisse.append(_beschreibe(pfad))
        except OSError:
            continue

    # Neueste zuerst - wer gerade exportiert hat, findet seinen Export oben
    ergebnisse.sort(key=lambda e: e["geaendert"], reverse=True)
    return ergebnisse[:max_treffer]


# ------------------------------------------------------------------
# Datei-Dialog des Betriebssystems
# ------------------------------------------------------------------

_DIALOG_SKRIPT = """
import sys
import tkinter as tk
from tkinter import filedialog

wurzel = tk.Tk()
wurzel.withdraw()
wurzel.attributes("-topmost", True)

if sys.argv[1] == "ordner":
    ergebnis = filedialog.askdirectory(title=sys.argv[2])
else:
    ergebnis = filedialog.askopenfilename(
        title=sys.argv[2],
        filetypes=[("Health-Export", "*.zip"), ("Datenbank", "*.db"), ("Alle Dateien", "*.*")],
    )

wurzel.destroy()
print(ergebnis or "")
"""


def dialog_verfuegbar() -> bool:
    """Ob sich ein Datei-Dialog öffnen lässt.

    Auf einem Server ohne grafische Oberfläche gibt es keinen - dann
    bleiben Suche und Eingabefeld.
    """
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return False

    # Ohne grafische Oberflaeche gibt es keinen Dialog
    return os.name == "nt" or bool(os.environ.get("DISPLAY"))


def waehle_datei(titel: str = "Health-Export auswählen", ordner: bool = False) -> str:
    """Öffnet den Auswahldialog des Betriebssystems.

    Läuft in einem eigenen Prozess: tkinter im Streamlit-Server zu starten
    führt je nach Thread zu Abstürzen oder blockiert den Server.
    """
    if not dialog_verfuegbar():
        return ""

    try:
        ergebnis = subprocess.run(
            [sys.executable, "-c", _DIALOG_SKRIPT, "ordner" if ordner else "datei", titel],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""

    return ergebnis.stdout.strip()
