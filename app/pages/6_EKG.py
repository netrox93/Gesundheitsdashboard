"""Seite 6: EKG-Aufzeichnungen ansehen und vermessen."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import altair as alt
import data_access as da
import ecg
import ecg_plot
import metrics_core as core
import pandas as pd
import streamlit as st
from reference_ranges import DISCLAIMER

st.set_page_config(page_title="EKG", layout="wide")
st.title("EKG-Aufzeichnungen")

if not da.db_exists():
    st.error("Keine Datenbank gefunden. Erst importieren und `build_daily.py` ausführen.")
    st.stop()


@st.cache_resource
def _conn():
    return core.connect()


conn = _conn()

if not ecg.tabelle_existiert(conn):
    st.warning(
        "Noch keine EKG-Daten importiert. Der Health-Export enthält sie im "
        "Ordner `apple_health_export/electrocardiograms`:\n\n"
        "`python app/import_ecg.py`"
    )
    st.stop()


@st.cache_data(ttl=3600)
def _uebersicht() -> pd.DataFrame:
    return ecg.lade_uebersicht(_conn())


df = _uebersicht()

if df.empty:
    st.warning("Die EKG-Tabelle ist leer. `python app/import_ecg.py` ausführen.")
    st.stop()

st.info(
    "**Was die Apple Watch aufzeichnet:** eine einzelne Ableitung "
    "(entspricht etwa Ableitung I) über 30 Sekunden. Ein klinisches "
    "Ruhe-EKG hat 12 Ableitungen. Die Zulassung umfasst die Unterscheidung "
    "von Sinusrhythmus und Vorhofflimmern - **nicht** die Erkennung von "
    "Herzinfarkten, Blockbildern oder anderen Rhythmusstörungen. Ein "
    "unauffälliges Ergebnis schliesst eine Herzerkrankung nicht aus. "
    "Die Beurteilung der Kurve gehört in ärztliche Hand; diese Seite "
    "stellt sie massstabsgetreu dar und misst Frequenz und Schlagabstände."
)

# ------------------------------------------------------------------
# Übersicht
# ------------------------------------------------------------------

c1, c2, c3, c4 = st.columns(4)
c1.metric("Aufzeichnungen", f"{len(df)}")
c2.metric("Zeitraum", f"{df['datum'].min():%m/%Y} - {df['datum'].max():%m/%Y}")
c3.metric("Sinusrhythmus", f"{(df['klassifikation'] == 'Sinusrhythmus').sum()}")
auffaellig = df[~df["klassifikation"].isin(["Sinusrhythmus", "Schlechte Aufzeichnung"])]
c4.metric("Andere Einstufung", f"{len(auffaellig)}")

st.subheader("Einstufungen durch die Uhr")

verteilung = df["klassifikation"].value_counts().reset_index()
verteilung.columns = ["Klassifikation", "Anzahl"]

balken = (
    alt.Chart(verteilung)
    .mark_bar(color="#2C5F8A")
    .encode(
        x=alt.X("Anzahl:Q", title="Anzahl"),
        y=alt.Y("Klassifikation:N", sort="-x", title=None),
        tooltip=["Klassifikation", "Anzahl"],
    )
    .properties(height=max(140, 34 * len(verteilung)))
)
st.altair_chart(balken, use_container_width=True)

for klasse in verteilung["Klassifikation"]:
    erklaerung = ecg.KLASSIFIKATIONEN.get(klasse)
    if erklaerung:
        with st.expander(f"Was bedeutet '{klasse}'?"):
            st.write(erklaerung)

st.divider()

# ------------------------------------------------------------------
# Tabelle aller Aufzeichnungen
# ------------------------------------------------------------------

st.subheader("Alle Aufzeichnungen")

tabelle = pd.DataFrame(
    {
        "Datum": df["datum"].dt.strftime("%d.%m.%Y"),
        "Uhrzeit": df["aufnahme"].str[11:16],
        "Einstufung": df["klassifikation"],
        "Symptome": df["symptome"].fillna("Ohne"),
        "Herzfrequenz": df["hf_mittel"].map(lambda v: f"{v:.0f}/min" if pd.notna(v) else "-"),
        "Spanne": df.apply(
            lambda r: f"{r['hf_min']:.0f}-{r['hf_max']:.0f}" if pd.notna(r["hf_min"]) else "-",
            axis=1,
        ),
        "Schwankung": df["unregelmaessigkeit"].map(lambda v: f"{v:.1f} %" if pd.notna(v) else "-"),
        "Signalqualität": df["qualitaet"],
    }
)
st.dataframe(tabelle, use_container_width=True, hide_index=True)

st.caption(
    '"Schwankung" ist der Variationskoeffizient der Abstände zwischen den '
    "Herzschlägen - ein rein beschreibendes Mass der Streuung, kein "
    "Rhythmusbefund. Bei gesunden jungen Erwachsenen ist eine atemabhängige "
    'Schwankung normal und sogar erwünscht. "Signalqualität" bewertet, wie '
    "zuverlässig die automatische Schlagerkennung war; bei "
    '"unzuverlässig" sind die Messwerte dieser Zeile nicht belastbar.'
)

st.divider()

# ------------------------------------------------------------------
# Einzelne Aufzeichnung
# ------------------------------------------------------------------

st.subheader("Einzelne Aufzeichnung ansehen")

auswahl = st.selectbox(
    "Aufzeichnung",
    df["id"].tolist(),
    format_func=lambda i: (
        f"{df.loc[df['id'] == i, 'aufnahme'].iloc[0][:16]} - "
        f"{df.loc[df['id'] == i, 'klassifikation'].iloc[0]}"
    ),
)

zeile = df[df["id"] == auswahl].iloc[0]

k1, k2, k3, k4 = st.columns(4)
k1.metric("Einstufung durch die Uhr", zeile["klassifikation"])
k2.metric("Herzfrequenz", f"{zeile['hf_mittel']:.0f}/min" if pd.notna(zeile["hf_mittel"]) else "-")
k3.metric("Erkannte Schläge", f"{int(zeile['schlaege'])}")
k4.metric("Signalqualität", zeile["qualitaet"])

if zeile["qualitaet"] == "unzuverlässig":
    st.warning(
        f"Bei dieser Aufzeichnung wurden "
        f"{zeile['verworfen_anteil'] * 100:.0f} % der Schlagabstände als "
        "unplausibel verworfen - die automatische Erkennung hat Schläge "
        "übersehen oder Artefakte mitgezählt. Die abgeleiteten Messwerte "
        "sind hier nicht belastbar; die Kurve selbst bleibt ansehbar."
    )
elif zeile["qualitaet"] == "eingeschränkt":
    st.info(
        f"{zeile['verworfen_anteil'] * 100:.0f} % der Schlagabstände wurden "
        "verworfen. Die Messwerte sind mit Vorbehalt zu lesen."
    )

if zeile["symptome"] and zeile["symptome"] != "Ohne":
    st.info(f"Bei der Aufzeichnung angegebene Symptome: **{zeile['symptome']}**")

erklaerung = ecg.KLASSIFIKATIONEN.get(zeile["klassifikation"])
if erklaerung:
    st.caption(erklaerung)

signal_uv, messrate = ecg.lade_signal(conn, int(auswahl))

if len(signal_uv) == 0:
    st.warning("Für diese Aufzeichnung ist kein Signal gespeichert.")
    st.stop()

zeige_r = st.checkbox("Erkannte R-Zacken markieren", value=True)
r_zacken = ecg.finde_r_zacken(ecg.filtere(signal_uv, messrate), messrate) if zeige_r else None

figur = ecg_plot.streifen(
    signal_uv,
    messrate,
    r_zacken=r_zacken,
    titel=f"Ableitung I - {zeile['aufnahme'][:16]} - {messrate:.0f} Hz",
)
st.pyplot(figur, use_container_width=False)
st.caption(ecg_plot.massstab_hinweis())

with st.expander("Messwerte dieser Aufzeichnung"):
    werte = pd.DataFrame(
        {
            "Kennwert": [
                "Dauer",
                "Erkannte Schläge",
                "Herzfrequenz (Median)",
                "Niedrigste / höchste Frequenz",
                "Mittlerer Schlagabstand (RR)",
                "Streuung der Schlagabstände",
                "RMSSD",
                "Verworfene Abstände",
            ],
            "Wert": [
                f"{zeile['dauer_s']:.0f} s",
                f"{int(zeile['schlaege'])}",
                f"{zeile['hf_mittel']:.0f}/min" if pd.notna(zeile["hf_mittel"]) else "-",
                f"{zeile['hf_min']:.0f} / {zeile['hf_max']:.0f}/min"
                if pd.notna(zeile["hf_min"])
                else "-",
                f"{zeile['rr_mittel_ms']:.0f} ms" if pd.notna(zeile["rr_mittel_ms"]) else "-",
                f"{zeile['rr_streuung_ms']:.0f} ms" if pd.notna(zeile["rr_streuung_ms"]) else "-",
                f"{zeile['rmssd_ms']:.0f} ms" if pd.notna(zeile["rmssd_ms"]) else "-",
                f"{zeile['verworfen_anteil'] * 100:.0f} %"
                if pd.notna(zeile["verworfen_anteil"])
                else "-",
            ],
        }
    )
    st.dataframe(werte, use_container_width=True, hide_index=True)
    st.caption(
        "RMSSD ist die Wurzel aus dem Mittel der quadrierten Differenzen "
        "aufeinanderfolgender Schlagabstände - ein gängiges Kurzzeitmass der "
        "Herzratenvariabilität. Aus 30 Sekunden berechnet und damit nicht "
        "mit den 24-Stunden-Werten der Fachliteratur vergleichbar."
    )

st.caption(DISCLAIMER)
