"""Seite 2: Einzelne Kennzahl im Detail - Verlauf, Referenzbereiche, Langzeittrend."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import data_access as da
import pandas as pd
import streamlit as st
from charts import infobox, jahresvergleich, legende, metric_chart
from reference_ranges import (
    DISCLAIMER,
    KATEGORIEN,
    METRICS,
    metrics_by_category,
    referenzbereich,
)

st.set_page_config(page_title="Kennzahl im Detail", layout="wide")
st.title("Kennzahl im Detail")

if not da.db_exists():
    st.error("Keine Datenbank gefunden. Erst importieren und `build_daily.py` ausführen.")
    st.stop()

start, end = da.data_range()
profil = da.load_profil()

# ------------------------------------------------------------------
# Auswahl
# ------------------------------------------------------------------

with st.sidebar:
    st.header("Auswahl")
    kategorie = st.selectbox("Kategorie", KATEGORIEN)
    verfuegbar = metrics_by_category(kategorie)
    key = st.selectbox(
        "Kennzahl",
        list(verfuegbar.keys()),
        format_func=lambda k: METRICS[k]["label"],
    )

    st.header("Zeitraum")
    zeitraum = st.radio(
        "Bereich",
        [
            "Letzte 90 Tage",
            "Letztes Jahr",
            "Letzte 3 Jahre",
            "Gesamter Zeitraum",
            "Eigener Bereich",
        ],
        index=1,
    )

    if zeitraum == "Eigener Bereich":
        gewaehlt = st.date_input("Von / bis", value=(start.date(), end.date()))
        von, bis = (
            gewaehlt
            if isinstance(gewaehlt, tuple) and len(gewaehlt) == 2
            else (start.date(), end.date())
        )
    else:
        tage = {"Letzte 90 Tage": 90, "Letztes Jahr": 365, "Letzte 3 Jahre": 1095}.get(zeitraum)
        von = (end - pd.Timedelta(days=tage)).date() if tage else start.date()
        bis = end.date()

    st.header("Darstellung")
    glaettung = st.select_slider(
        "Glättung", options=["Keine", "7 Tage", "30 Tage", "90 Tage"], value="30 Tage"
    )
    zeige_population = st.checkbox("Referenzbereich aus Literatur", value=True)
    zeige_baseline = st.checkbox("Persönliche Baseline", value=True)

spec = METRICS[key]

# ------------------------------------------------------------------
# Daten
# ------------------------------------------------------------------

roh = da.load_metric(key)
if roh.empty:
    st.warning(f"Keine Daten für '{spec['label']}' vorhanden.")
    st.stop()

# Baseline auf der vollen Reihe rechnen, damit der Korridor am Anfang
# des gewählten Zeitraums nicht fehlt
mit_baseline = da.add_rolling_means(da.add_baseline(roh))
df = da.filter_range(mit_baseline, von, bis)

if df.empty:
    st.warning("Im gewählten Zeitraum liegen keine Daten.")
    st.stop()

st.subheader(spec["label"])

warnung = da.coverage_warning(roh)
if warnung:
    st.warning(warnung)

smoothing_map = {"Keine": None, "7 Tage": "mean_7", "30 Tage": "mean_30", "90 Tage": "mean_90"}

st.altair_chart(
    metric_chart(
        df,
        key,
        show_population=zeige_population,
        show_baseline=zeige_baseline,
        smoothing=smoothing_map[glaettung],
        profil=profil,
    ),
    use_container_width=True,
)
referenz = referenzbereich(key, profil)
legende(zeige_population, bool(referenz["bereich"]))

# ------------------------------------------------------------------
# Kennzahlen zum gewählten Zeitraum
# ------------------------------------------------------------------

c1, c2, c3, c4 = st.columns(4)
c1.metric("Mittelwert", da.format_value(key, df["value"].mean()))
c2.metric("Median", da.format_value(key, df["value"].median()))
c3.metric("Minimum", da.format_value(key, df["value"].min()))
c4.metric("Maximum", da.format_value(key, df["value"].max()))

if referenz["bereich"]:
    low, high = referenz["bereich"]
    innerhalb = df["value"].between(low, high).mean() * 100
    darunter = (df["value"] < low).mean() * 100
    darueber = (df["value"] > high).mean() * 100

    st.caption(
        f"{innerhalb:.0f} % der Tage im gewählten Zeitraum liegen im "
        f"Referenzbereich ({referenz['label']}), "
        f"{darunter:.0f} % darunter, {darueber:.0f} % darüber."
    )

    # Systematisch ausserhalb liegende Werte einordnen, statt sie als
    # Auffälligkeit stehen zu lassen. Bei Trainierten ist etwa ein
    # Ruhepuls unter 60/min der Regelfall, nicht der Befund.
    if darunter > 50 and spec["richtung"] == "niedriger_besser":
        st.info(
            "Deine Werte liegen überwiegend **unterhalb** des "
            "Literaturbereichs. Bei dieser Kennzahl ist das kein "
            "Warnzeichen: niedrigere Werte gelten als günstiger, und der "
            "Referenzbereich bildet die Allgemeinbevölkerung ab, nicht "
            "Ausdauertrainierte. Für die Beurteilung von Veränderungen ist "
            "hier die persönliche Baseline massgeblich."
        )
    elif darueber > 50 and spec["richtung"] == "hoeher_besser":
        st.info(
            "Deine Werte liegen überwiegend **oberhalb** des "
            "Literaturbereichs. Bei dieser Kennzahl gelten höhere Werte als "
            "günstiger - der Referenzbereich bildet die "
            "Allgemeinbevölkerung ab."
        )
    elif innerhalb < 50:
        st.caption(
            "Ein Wert ausserhalb des Referenzbereichs bedeutet nicht "
            "automatisch einen Befund - Messverfahren und Referenzbereich "
            "stammen aus unterschiedlichen Zusammenhängen, siehe Messhinweis."
        )
else:
    st.caption(
        "Für diese Kennzahl ist bewusst kein Populations-Referenzbereich "
        "hinterlegt - Begründung in der Infobox."
    )

if referenz["hinweis"]:
    st.caption(referenz["hinweis"])

infobox(key, expanded=True, profil=profil)

st.divider()

# ------------------------------------------------------------------
# Langzeittrend
# ------------------------------------------------------------------

st.subheader("Langzeitentwicklung")
st.caption(
    "Verteilung pro Kalenderjahr über den gesamten Datenbestand, unabhängig "
    "vom oben gewählten Zeitraum. Box = mittlere 50 % der Tage, Linie = Median."
)
st.altair_chart(jahresvergleich(mit_baseline, key), use_container_width=True)

jahre = mit_baseline.copy()
jahre["Jahr"] = jahre["date"].dt.year
tabelle = jahre.groupby("Jahr")["value"].agg(["count", "mean", "median", "std"]).reset_index()
tabelle.columns = ["Jahr", "Tage mit Daten", "Mittelwert", "Median", "Streuung"]
for spalte in ("Mittelwert", "Median", "Streuung"):
    tabelle[spalte] = tabelle[spalte].round(1)
st.dataframe(tabelle, use_container_width=True, hide_index=True)

st.caption(
    "Hinweis zur Interpretation: Jahre mit deutlich weniger Tagen sind nur "
    "eingeschränkt vergleichbar, weil einzelne Phasen dann stärker durchschlagen."
)

st.caption(DISCLAIMER)
