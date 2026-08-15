"""Seite 5: Trainingsbelastung und Schlafstruktur."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import altair as alt
import data_access as da
import pandas as pd
import streamlit as st
from charts import FARBE_BASELINE, FARBE_LINIE, infobox
from reference_ranges import DISCLAIMER

st.set_page_config(page_title="Sport und Schlaf", layout="wide")
st.title("Sport und Schlaf")

start, end = da.datenbestand_oder_stopp()

tab_sport, tab_schlaf = st.tabs(["Sport", "Schlaf"])

# ==================================================================
# Sport
# ==================================================================

with tab_sport:
    workouts = da.load_workouts()

    if workouts.empty:
        st.info("Keine aufgezeichneten Trainingseinheiten im Export.")
    else:
        jahre = st.selectbox(
            "Zeitraum",
            [1, 2, 3, 6],
            index=3,
            format_func=lambda j: f"Letzte {j} Jahre",
            key="sport_zeitraum",
        )
        grenze = pd.Timestamp(end) - pd.Timedelta(days=365 * jahre)
        gefiltert = workouts[workouts["date"] >= grenze]

        if gefiltert.empty:
            st.warning("Keine Trainings im gewählten Zeitraum.")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Einheiten", f"{len(gefiltert)}")
            c2.metric("Gesamtdauer", f"{gefiltert['duration_min'].sum() / 60:.0f} h")
            c3.metric("Distanz gesamt", f"{gefiltert['distance_km'].sum():.0f} km")

            st.subheader("Nach Sportart")
            nach_art = (
                gefiltert.groupby("typ")
                .agg(
                    Einheiten=("typ", "size"),
                    Stunden=("duration_min", lambda s: round(s.sum() / 60, 1)),
                    Distanz_km=("distance_km", lambda s: round(s.sum(), 1)),
                )
                .reset_index()
                .sort_values("Stunden", ascending=False)
            )

            balken = (
                alt.Chart(nach_art)
                .mark_bar(color=FARBE_BASELINE)
                .encode(
                    x=alt.X("Stunden:Q", title="Stunden gesamt"),
                    y=alt.Y("typ:N", sort="-x", title=None),
                    tooltip=["typ", "Einheiten", "Stunden", "Distanz_km"],
                )
                .properties(height=max(220, 26 * len(nach_art)))
            )
            st.altair_chart(balken, use_container_width=True)
            st.dataframe(
                nach_art.rename(columns={"typ": "Sportart", "Distanz_km": "Distanz (km)"}),
                use_container_width=True,
                hide_index=True,
            )

            st.subheader("Trainingsbelastung über die Zeit")
            st.caption(
                "Trainingsminuten pro Woche aus den Apple-Trainingsminuten. "
                "Die WHO empfiehlt 150-300 Minuten moderate Aktivität pro Woche "
                "(grünes Band)."
            )

            training = da.load_metric("exercise_min")
            if not training.empty:
                woche = training.set_index("date").resample("W")["value"].sum().reset_index()
                woche = woche[woche["date"] >= grenze]

                band = pd.DataFrame({"low": [150], "high": [300]})
                flaeche = (
                    alt.Chart(band)
                    .mark_rect(opacity=0.15, color="#4C9F70")
                    .encode(y=alt.Y("low:Q", scale=alt.Scale(zero=False)), y2="high:Q")
                )
                linie = (
                    alt.Chart(woche)
                    .mark_line(color=FARBE_LINIE, strokeWidth=2)
                    .encode(
                        x=alt.X("date:T", title=None),
                        y=alt.Y(
                            "value:Q",
                            title="Trainingsminuten pro Woche",
                            scale=alt.Scale(zero=False),
                        ),
                        tooltip=[
                            alt.Tooltip("date:T", title="Woche"),
                            alt.Tooltip("value:Q", title="Minuten", format=".0f"),
                        ],
                    )
                )
                st.altair_chart(
                    (flaeche + linie).properties(height=340).interactive(bind_y=False),
                    use_container_width=True,
                )
                anteil = (woche["value"] >= 150).mean() * 100
                st.caption(
                    f"In {anteil:.0f} % der Wochen im gewählten Zeitraum lag die "
                    "Trainingszeit bei mindestens 150 Minuten."
                )

            infobox("exercise_min")

# ==================================================================
# Schlaf
# ==================================================================

with tab_schlaf:
    schlaf = da.load_sleep()

    if schlaf.empty:
        st.info("Keine Schlafdaten vorhanden.")
    else:
        jahre_s = st.selectbox(
            "Zeitraum",
            [1, 2, 3, 6],
            index=0,
            format_func=lambda j: f"Letzte {j} Jahre",
            key="schlaf_zeitraum",
        )
        grenze_s = pd.Timestamp(end) - pd.Timedelta(days=365 * jahre_s)
        s = schlaf[schlaf["date"] >= grenze_s].copy()

        if s.empty:
            st.warning("Keine Schlafdaten im gewählten Zeitraum.")
            st.stop()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Nächte erfasst", f"{s['asleep_min'].notna().sum()}")
        c2.metric("Schlaf im Schnitt", f"{s['asleep_min'].mean() / 60:.1f} h")
        c3.metric("Tiefschlaf-Anteil", f"{100 * s['deep_min'].sum() / s['asleep_min'].sum():.0f} %")
        c4.metric("REM-Anteil", f"{100 * s['rem_min'].sum() / s['asleep_min'].sum():.0f} %")

        st.subheader("Schlafphasen")
        st.caption(
            "Gestapelte Phasendauer pro Nacht. Die Stadieneinteilung eines "
            "Wearables weicht von der Polysomnographie ab - der Verlauf ist "
            "aussagekräftiger als die Absolutwerte einer einzelnen Nacht."
        )

        phasen = s.melt(
            id_vars="date",
            value_vars=["deep_min", "core_min", "rem_min", "awake_min"],
            var_name="Phase",
            value_name="Minuten",
        ).dropna(subset=["Minuten"])
        phasen["Phase"] = phasen["Phase"].map(
            {
                "deep_min": "Tiefschlaf",
                "core_min": "Leichtschlaf",
                "rem_min": "REM",
                "awake_min": "Wach",
            }
        )
        phasen["Stunden"] = phasen["Minuten"] / 60

        flaechen = (
            alt.Chart(phasen)
            .mark_bar()
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y("Stunden:Q", title="Stunden"),
                color=alt.Color(
                    "Phase:N",
                    scale=alt.Scale(
                        domain=["Tiefschlaf", "Leichtschlaf", "REM", "Wach"],
                        range=["#1F3A5F", "#5B8FF9", "#9DC6FF", "#D9D9D9"],
                    ),
                ),
                tooltip=[
                    alt.Tooltip("date:T", title="Nacht"),
                    "Phase",
                    alt.Tooltip("Stunden:Q", format=".1f"),
                ],
            )
            .properties(height=340)
            .interactive(bind_y=False)
        )
        st.altair_chart(flaechen, use_container_width=True)

        st.subheader("Regelmässigkeit der Schlafenszeit")
        st.caption(
            "Jeder Punkt ist eine Nacht. Eine geringe Streuung spricht für "
            "einen stabilen zirkadianen Rhythmus - Studien zur "
            "Schlafregelmässigkeit zeigen, dass die Streuung unabhängig von "
            "der Schlafdauer mit der Gesundheit zusammenhängt."
        )

        zeiten = da.load_metric("bedtime_var")
        zeiten = zeiten[zeiten["date"] >= grenze_s]

        if not zeiten.empty:
            punkte = (
                alt.Chart(zeiten)
                .mark_circle(size=32, opacity=0.5, color=FARBE_BASELINE)
                .encode(
                    x=alt.X("date:T", title=None),
                    y=alt.Y(
                        "value:Q",
                        title="Zubettgehzeit (Minuten um Mitternacht)",
                        scale=alt.Scale(zero=False),
                    ),
                    tooltip=[alt.Tooltip("date:T", title="Nacht")],
                )
                .properties(height=300)
                .interactive(bind_y=False)
            )
            st.altair_chart(punkte, use_container_width=True)
            st.caption(
                f"Streuung der Zubettgehzeit im gewählten Zeitraum: "
                f"±{zeiten['value'].std():.0f} Minuten. "
                "Negative Werte auf der Achse bedeuten vor Mitternacht."
            )

        col1, col2 = st.columns(2)
        with col1:
            infobox("sleep_hours")
            infobox("deep_share")
        with col2:
            infobox("rem_share")
            infobox("bedtime_var")

st.caption(DISCLAIMER)
