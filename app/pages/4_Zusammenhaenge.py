"""Seite 4: Zusammenhänge zwischen zwei Kennzahlen, mit Zeitversatz.

Der Zeitversatz ist der eigentliche Punkt: Schlechter Schlaf wirkt auf
den Folgetag, Training auf die Nacht danach. Ohne Versatz bleiben genau
diese Zusammenhänge unsichtbar.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import altair as alt
import data_access as da
import pandas as pd
import streamlit as st
from charts import FARBE_BASELINE, FARBE_LINIE, infobox
from reference_ranges import DISCLAIMER, METRICS

st.set_page_config(page_title="Zusammenhänge", layout="wide")
st.title("Zusammenhänge")

start, end = da.datenbestand_oder_stopp()

with st.sidebar:
    st.header("Kennzahlen")
    key_x = st.selectbox(
        "Einflussgrösse (X)",
        list(METRICS.keys()),
        index=list(METRICS.keys()).index("sleep_hours"),
        format_func=lambda k: METRICS[k]["label"],
    )
    key_y = st.selectbox(
        "Zielgrösse (Y)",
        list(METRICS.keys()),
        index=list(METRICS.keys()).index("resting_hr"),
        format_func=lambda k: METRICS[k]["label"],
    )

    st.header("Zeitversatz")
    versatz = st.slider(
        "Tage zwischen X und Y",
        min_value=-7,
        max_value=7,
        value=0,
        help="Positiv: X wirkt auf einen späteren Tag von Y. "
        "Beispiel +1 vergleicht den Schlaf einer Nacht mit dem Ruhepuls am Folgetag.",
    )

    st.header("Zeitraum")
    jahre_zurueck = st.selectbox(
        "Bereich", [1, 2, 3, 6], index=1, format_func=lambda j: f"Letzte {j} Jahre"
    )

if key_x == key_y:
    st.warning("Bitte zwei verschiedene Kennzahlen wählen.")
    st.stop()

grenze = pd.Timestamp(end) - pd.Timedelta(days=365 * jahre_zurueck)

df_x = da.load_metric(key_x).rename(columns={"value": "x"})
df_y = da.load_metric(key_y).rename(columns={"value": "y"})

if df_x.empty or df_y.empty:
    st.warning("Für mindestens eine der Kennzahlen liegen keine Daten vor.")
    st.stop()

# Versatz anwenden: X um `versatz` Tage nach vorn schieben
df_x = df_x.copy()
df_x["date"] = df_x["date"] + pd.Timedelta(days=versatz)

paare = pd.merge(df_x, df_y, on="date", how="inner")
paare = paare[paare["date"] >= grenze].dropna(subset=["x", "y"])

spec_x, spec_y = METRICS[key_x], METRICS[key_y]

if len(paare) < 20:
    st.warning(
        f"Nur {len(paare)} gemeinsame Tage im gewählten Zeitraum - "
        "für eine belastbare Aussage zu wenig."
    )
    st.stop()

# ------------------------------------------------------------------
# Korrelation
# ------------------------------------------------------------------

r = paare["x"].corr(paare["y"])
# Spearman = Pearson auf den Rängen. Selbst gerechnet, damit scipy keine
# zusätzliche Abhängigkeit wird.
r_spearman = paare["x"].rank().corr(paare["y"].rank())

c1, c2, c3 = st.columns(3)
c1.metric("Korrelation (Pearson)", f"{r:+.2f}")
c2.metric("Korrelation (Spearman)", f"{r_spearman:+.2f}")
c3.metric("Gemeinsame Tage", f"{len(paare)}")


def staerke(wert: float) -> str:
    a = abs(wert)
    if a < 0.1:
        return "kein erkennbarer Zusammenhang"
    if a < 0.3:
        return "sehr schwacher Zusammenhang"
    if a < 0.5:
        return "schwacher bis mittlerer Zusammenhang"
    if a < 0.7:
        return "mittlerer bis starker Zusammenhang"
    return "starker Zusammenhang"


richtung = (
    "gleichsinnig (beide steigen gemeinsam)"
    if r > 0
    else "gegenläufig (eins steigt, das andere fällt)"
)

versatz_text = {
    0: "am selben Tag",
}.get(versatz, f"mit {abs(versatz)} Tag(en) Versatz ({'X vor Y' if versatz > 0 else 'Y vor X'})")

st.markdown(
    f"**{spec_x['label']}** und **{spec_y['label']}** {versatz_text}: {staerke(r)}, {richtung}."
)

st.caption(
    "Pearson misst lineare Zusammenhänge, Spearman auch nichtlineare "
    "Rangzusammenhänge - weichen beide stark voneinander ab, ist der "
    "Zusammenhang vermutlich nicht linear. Wichtig: Eine Korrelation belegt "
    "keinen ursächlichen Zusammenhang. Beide Werte können auch von einer "
    "dritten Grösse abhängen (etwa Krankheit, Urlaub oder Jahreszeit)."
)

# ------------------------------------------------------------------
# Streudiagramm
# ------------------------------------------------------------------

punkte = (
    alt.Chart(paare)
    .mark_circle(size=42, opacity=0.45, color=FARBE_BASELINE)
    .encode(
        x=alt.X(
            "x:Q", scale=alt.Scale(zero=False), title=f"{spec_x['label']} ({spec_x['einheit']})"
        ),
        y=alt.Y(
            "y:Q", scale=alt.Scale(zero=False), title=f"{spec_y['label']} ({spec_y['einheit']})"
        ),
        tooltip=[
            alt.Tooltip("date:T", title="Datum"),
            alt.Tooltip("x:Q", title=spec_x["label"], format=".1f"),
            alt.Tooltip("y:Q", title=spec_y["label"], format=".1f"),
        ],
    )
)

trend = punkte.transform_regression("x", "y").mark_line(color=FARBE_LINIE, strokeWidth=2.5)

st.altair_chart((punkte + trend).properties(height=420).interactive(), use_container_width=True)

st.divider()

# ------------------------------------------------------------------
# Versatz-Profil: bei welchem Zeitversatz ist der Zusammenhang am stärksten?
# ------------------------------------------------------------------

st.subheader("Welcher Zeitversatz passt am besten?")
st.caption(
    "Korrelation für jeden Versatz von -7 bis +7 Tagen. Ein Ausschlag bei "
    "einem bestimmten Versatz ist ein Hinweis darauf, wie schnell sich die "
    "eine Grösse auf die andere auswirkt."
)

profil = []
basis_x = da.load_metric(key_x).rename(columns={"value": "x"})
for v in range(-7, 8):
    verschoben = basis_x.copy()
    verschoben["date"] = verschoben["date"] + pd.Timedelta(days=v)
    zusammen = pd.merge(verschoben, df_y, on="date", how="inner")
    zusammen = zusammen[zusammen["date"] >= grenze].dropna(subset=["x", "y"])
    if len(zusammen) >= 20:
        profil.append({"Versatz": v, "r": zusammen["x"].corr(zusammen["y"]), "n": len(zusammen)})

if profil:
    profil_df = pd.DataFrame(profil)
    balken = (
        alt.Chart(profil_df)
        .mark_bar(color=FARBE_BASELINE)
        .encode(
            x=alt.X("Versatz:O", title="Zeitversatz in Tagen"),
            y=alt.Y("r:Q", title="Korrelation"),
            tooltip=[
                alt.Tooltip("Versatz:O"),
                alt.Tooltip("r:Q", format="+.3f"),
                alt.Tooltip("n:Q", title="Tage"),
            ],
        )
        .properties(height=260)
    )
    st.altair_chart(balken, use_container_width=True)

    bester = profil_df.loc[profil_df["r"].abs().idxmax()]
    st.markdown(
        f"Stärkster Zusammenhang bei **{int(bester['Versatz']):+d} Tagen** "
        f"(r = {bester['r']:+.2f}, {int(bester['n'])} Tage)."
    )
    st.caption(
        "Vorsicht bei der Deutung: Wer 15 Versätze durchprobiert, findet "
        "auch in Zufallsdaten irgendwo einen Ausschlag. Belastbar wird ein "
        "Muster erst, wenn es inhaltlich plausibel ist und über mehrere "
        "Zeiträume stabil bleibt."
    )

st.divider()

col1, col2 = st.columns(2)
with col1:
    infobox(key_x)
with col2:
    infobox(key_y)

st.caption(DISCLAIMER)
