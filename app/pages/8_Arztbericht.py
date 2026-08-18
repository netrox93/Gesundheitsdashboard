"""Seite 6: PDF-Bericht erzeugen und herunterladen."""

import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import data_access as da
import streamlit as st
from reference_ranges import SCHWELLE_STANDARD

st.set_page_config(page_title="Arztbericht", layout="wide")
st.title("Bericht für den Arztbesuch")

if not da.db_exists():
    st.error("Keine Datenbank gefunden. Erst importieren und `build_daily.py` ausführen.")
    st.stop()

st.markdown(
    "Erzeugt ein PDF zum Ausdrucken oder Mitschicken. Der Bericht stellt "
    "die Messverfahren und ihre Grenzen vor die Zahlen, damit die Werte "
    "einordenbar sind."
)

c1, c2 = st.columns([1, 2])
with c1:
    monate = st.selectbox(
        "Auswertungszeitraum",
        [3, 6, 12, 24],
        index=2,
        format_func=lambda m: f"Letzte {m} Monate",
    )

with c2:
    st.caption(
        "Ein längerer Zeitraum zeigt Trends deutlicher, ein kürzerer die "
        "aktuelle Situation genauer. 12 Monate fangen zusätzlich die "
        "jahreszeitlichen Schwankungen ein."
    )

with st.expander("Was steht im Bericht?"):
    st.markdown(
        f"""
1. **Deckblatt** mit Datenherkunft und Hinweis zur Einordnung
2. **Zusammenfassung**: alle Kennzahlen gegen ihre Referenzbereiche, mit
   Angabe, wie die Werte zum Bereich liegen
3. **Auffällige Phasen**: zusammenhängende Abweichungen von mehr als
   {SCHWELLE_STANDARD:.0f} Standardabweichungen vom individuellen
   90-Tage-Median, beschränkt auf physiologische Kennzahlen
4. **Je Kennzahl eine Seite**: Verlauf mit Referenzband und Baseline-Korridor,
   Messverfahren, Herkunft des Referenzbereichs, Beobachtung im Zeitraum
5. **Schlafstruktur** mit Phasenverteilung
6. **Methodik**: Baseline-Berechnung, Schwellenwert, Grenzen der Auswertung,
   alle Quellenangaben
"""
    )

st.info(
    "Der Bericht enthält Geburtsjahr, Alter und Geschlecht sowie die "
    "Gesundheitsdaten des gewählten Zeitraums. Vor dem Weitergeben prüfen, "
    "ob das so gewünscht ist."
)

if st.button("Bericht erzeugen", type="primary"):
    with st.spinner("Erzeuge Bericht - das dauert einen Moment ..."):
        import export_pdf

        ziel = Path(tempfile.gettempdir()) / f"Gesundheitsbericht_{date.today():%Y-%m-%d}.pdf"
        bilder = Path(tempfile.mkdtemp())

        try:
            export_pdf.baue_bericht(monate, ziel, bilder)
        except Exception as fehler:  # noqa: BLE001
            st.error(f"Bericht konnte nicht erzeugt werden: {fehler}")
            st.stop()

        st.session_state["bericht"] = ziel.read_bytes()
        st.session_state["bericht_name"] = ziel.name
        st.session_state["bericht_monate"] = monate

if "bericht" in st.session_state:
    groesse = len(st.session_state["bericht"]) / 1024
    st.success(
        f"Bericht über {st.session_state['bericht_monate']} Monate erstellt ({groesse:.0f} KB)."
    )
    st.download_button(
        "PDF herunterladen",
        data=st.session_state["bericht"],
        file_name=st.session_state["bericht_name"],
        mime="application/pdf",
    )

st.divider()
st.caption("Alternativ auf der Kommandozeile: `python app/export_pdf.py --monate 12`")
