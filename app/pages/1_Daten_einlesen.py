"""Seite 1: Health-Export einlesen und Profil pflegen.

Erste Anlaufstelle für neue Nutzer - deshalb bewusst ohne
Kommandozeile: Datei auswählen, Knopf drücken, fertig.
"""

import contextlib
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import data_access as da
import metrics_core as core
import pandas as pd
import pipeline
import profil as profil_modul
import streamlit as st

st.set_page_config(page_title="Daten einlesen", layout="wide")
st.title("Daten einlesen")

BASIS = Path(__file__).parent.parent.parent

# ------------------------------------------------------------------
# Anleitung
# ------------------------------------------------------------------

with st.expander("Wie komme ich an meinen Export?", expanded=not da.db_exists()):
    st.markdown(
        """
1. Auf dem iPhone die **Health-App** öffnen (weisses Symbol mit rotem Herz)
2. Oben rechts auf das **Profilbild** tippen
3. Ganz unten **"Alle Gesundheitsdaten exportieren"** wählen
4. Der Export dauert einige Minuten. Danach die Datei **`Export.zip`**
   auf diesen Rechner übertragen - per AirDrop, Mail an sich selbst,
   Kabel oder Cloud-Ordner
5. Unten die ZIP-Datei auswählen und einlesen

Die Daten bleiben dabei vollständig auf diesem Rechner. Es wird nichts
hochgeladen oder verschickt.
"""
    )

# ------------------------------------------------------------------
# Einlesen
# ------------------------------------------------------------------

st.subheader("Export einlesen")

quelle_art = st.radio(
    "Woher kommen die Daten?",
    ["ZIP-Datei hochladen", "Pfad auf diesem Rechner angeben"],
    horizontal=True,
)

quelle = None

if quelle_art == "ZIP-Datei hochladen":
    hochgeladen = st.file_uploader(
        "Export.zip auswählen",
        type=["zip"],
        help="Die unveränderte Datei aus der Health-App.",
    )
    if hochgeladen is not None:
        ziel = BASIS / "imports" / "Export.zip"
        ziel.parent.mkdir(parents=True, exist_ok=True)
        with open(ziel, "wb") as datei:
            datei.write(hochgeladen.getbuffer())
        quelle = ziel
        st.success(f"Datei übernommen ({ziel.stat().st_size / 1024**2:.0f} MB).")
else:
    eingabe = st.text_input(
        "Pfad zur Export.zip oder zum entpackten Ordner",
        value=str(BASIS / "imports"),
        help="Zum Beispiel C:\\Users\\Name\\Downloads\\Export.zip",
    )
    if eingabe:
        pfad = Path(eingabe)
        if pfad.exists():
            quelle = pfad
        else:
            st.error("Pfad nicht gefunden.")

mit_ekg = st.checkbox("EKG-Aufzeichnungen mit einlesen", value=True)

if quelle and st.button("Daten einlesen", type="primary"):
    balken = st.progress(0.0)
    status = st.empty()

    def melde(text: str, anteil: float) -> None:
        status.write(text)
        balken.progress(min(1.0, anteil))

    try:
        ergebnis = pipeline.einlesen(quelle, fortschritt=melde, mit_ekg=mit_ekg)
    except pipeline.EinleseFehler as fehler:
        balken.empty()
        status.empty()
        st.error(str(fehler))
        st.stop()
    except Exception as fehler:  # noqa: BLE001
        balken.empty()
        status.empty()
        st.error(f"Beim Einlesen ist ein Fehler aufgetreten: {fehler}")
        st.stop()

    st.cache_data.clear()
    balken.empty()
    status.empty()

    zahlen = ergebnis["messwerte"]
    st.success(
        f"{zahlen['seen']:,} Messwerte gelesen, davon {zahlen['records']:,} neu. "
        f"{zahlen['workouts']} Trainings, {zahlen['summaries']} Aktivitätstage, "
        f"{ergebnis['tageswerte']:,} Tageswerte, {ergebnis['naechte']} Nächte.".replace(",", ".")
    )

    if ergebnis.get("ekg"):
        st.success(f"{ergebnis['ekg']['neu']} EKG-Aufzeichnungen eingelesen.")

    if ergebnis.get("profil"):
        st.success("Profil aus dem Export übernommen.")
    else:
        st.warning(
            "Im Export standen keine Angaben zu Geburtsdatum und Geschlecht. "
            "Bitte unten von Hand eintragen, damit die alters- und "
            "geschlechtsabhängigen Referenzbereiche stimmen."
        )

    st.info("Die Auswertung ist jetzt in der linken Navigation verfügbar.")

st.divider()

# ------------------------------------------------------------------
# Profil
# ------------------------------------------------------------------

st.subheader("Profil")
st.caption(
    "Alter und Geschlecht werden für einen Teil der Referenzbereiche "
    "gebraucht: VO2max-Normwerte sind nach Alter und Geschlecht gestaffelt, "
    "die empfohlene Schlafdauer und der Schritt-Richtwert nach Alter. Alle "
    "übrigen Bereiche gelten für Erwachsene unabhängig davon."
)

if not da.db_exists():
    st.info("Noch keine Datenbank - erst einen Export einlesen.")
    st.stop()

conn = core.connect()
aktuell = profil_modul.lade(conn)

if aktuell:
    st.write(
        f"Hinterlegt: **{profil_modul.beschreibung(aktuell)}** "
        f"(Geburtsdatum {aktuell['geburtsdatum']}, Quelle: {aktuell['quelle']})"
    )
else:
    st.warning("Kein Profil hinterlegt.")

with st.form("profil"):
    spalte1, spalte2 = st.columns(2)

    with spalte1:
        vorgabe = date(1990, 1, 1)
        if aktuell and aktuell.get("geburtsdatum"):
            with contextlib.suppress(ValueError, TypeError):
                vorgabe = pd.to_datetime(aktuell["geburtsdatum"]).date()

        geburtsdatum = st.date_input(
            "Geburtsdatum",
            value=vorgabe,
            min_value=date(1900, 1, 1),
            max_value=date.today(),
        )

    with spalte2:
        optionen = ["m", "w", "divers"]
        index = (
            optionen.index(aktuell["geschlecht"])
            if (aktuell and aktuell.get("geschlecht") in optionen)
            else 0
        )
        geschlecht = st.selectbox(
            "Geschlecht",
            optionen,
            index=index,
            format_func=lambda g: profil_modul.GESCHLECHT_LABEL[g],
            help="Wird nur für die VO2max-Normwerte verwendet.",
        )

    if st.form_submit_button("Profil speichern"):
        profil_modul.speichere(
            conn, geburtsdatum.isoformat(), geschlecht, quelle="manuell eingetragen"
        )
        st.cache_data.clear()
        st.success("Profil gespeichert.")
        st.rerun()

st.divider()

# ------------------------------------------------------------------
# Datenbestand
# ------------------------------------------------------------------

st.subheader("Datenbestand")

start, ende = core.data_range(conn)
if start is None:
    st.info("Noch keine Tageswerte berechnet.")
else:
    c1, c2, c3 = st.columns(3)
    c1.metric("Zeitraum", f"{start:%m/%Y} - {ende:%m/%Y}")
    c2.metric("Messwerte", f"{core.record_count(conn):,}".replace(",", "."))
    c3.metric(
        "Tage mit Daten",
        f"{conn.execute('SELECT COUNT(DISTINCT date) FROM daily_metrics').fetchone()[0]:,}".replace(
            ",", "."
        ),
    )

    verlauf = pd.read_sql(
        "SELECT file_name, imported_at, records_seen, records_inserted "
        "FROM imports ORDER BY id DESC LIMIT 5",
        conn,
    )
    if not verlauf.empty:
        verlauf["imported_at"] = pd.to_datetime(verlauf["imported_at"]).dt.strftime(
            "%d.%m.%Y %H:%M"
        )
        verlauf.columns = ["Datei", "Eingelesen am", "Gelesen", "Neu"]
        with st.expander("Bisherige Importe"):
            st.dataframe(verlauf, use_container_width=True, hide_index=True)

st.caption(
    "Ein erneuter Import mit einem neueren Export ergänzt nur die neuen "
    "Werte - bereits vorhandene werden übersprungen."
)
