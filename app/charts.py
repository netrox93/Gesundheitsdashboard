"""Wiederverwendbare Diagramme und Erklär-Bausteine.

Diagramme mit Altair statt st.line_chart, weil nur so Referenzbänder,
Baseline-Korridor und markierte Abweichungen in einer Grafik liegen.
"""

import altair as alt
import pandas as pd
import streamlit as st
from reference_ranges import METRICS, referenzbereich

FARBE_POPULATION = "#4C9F70"
FARBE_BASELINE = "#5B8FF9"
FARBE_LINIE = "#1F3A5F"
FARBE_ABWEICHUNG = "#D1495B"


def infobox(key: str, expanded: bool = False, profil: dict = None) -> None:
    """Erklärkasten zu einer Kennzahl: was sie aussagt, was Abweichungen
    bedeuten, wie gemessen wird und woher der Referenzbereich stammt."""
    spec = METRICS[key]
    referenz = referenzbereich(key, profil)

    with st.expander(f"Was sagt '{spec['label']}' aus?", expanded=expanded):
        st.markdown(f"**Bedeutung**  \n{spec['erklaerung']}")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Wenn der Wert hoch ist**  \n{spec['hoch']}")
        with col2:
            st.markdown(f"**Wenn der Wert niedrig ist**  \n{spec['niedrig']}")

        if referenz["bereich"]:
            low, high = referenz["bereich"]
            zusatz = " - an dein Profil angepasst" if referenz["angepasst"] else ""
            st.markdown(
                f"**Referenzbereich**  \n{referenz['label']} "
                f"({low}-{high} {spec['einheit']}){zusatz}"
            )
        else:
            st.markdown(
                "**Referenzbereich**  \nKein Populationsbereich hinterlegt - "
                "Beurteilung nur gegen die eigene Baseline."
            )

        if referenz["hinweis"]:
            st.caption(referenz["hinweis"])

        st.markdown(f"**Quelle**  \n{spec['quelle']}")
        st.info(f"**Messhinweis:** {spec['messhinweis']}")


def bewertung(key: str, z: float) -> tuple:
    """Ampel-Einordnung eines z-Werts gegen die persönliche Baseline.

    Rückgabe: (Text, Farbe, Symbol). Bewertet wird die Grösse der
    Abweichung, nicht ihre Richtung - was 'gut' ist, hängt von der
    Kennzahl ab und steht in den Infoboxen.
    """
    if z is None or pd.isna(z):
        return ("zu wenig Daten", "grey", "•")
    if abs(z) < 1:
        return ("im gewohnten Bereich", "green", "●")
    if abs(z) < 2:
        return ("leicht abweichend", "orange", "▲" if z > 0 else "▼")
    return ("deutlich abweichend", "red", "▲" if z > 0 else "▼")


def metric_chart(
    df: pd.DataFrame,
    key: str,
    show_population: bool = True,
    show_baseline: bool = True,
    smoothing: str = "mean_7",
    height: int = 380,
    profil: dict = None,
) -> alt.LayerChart:
    """Zeitreihe mit Referenzband, Baseline-Korridor und Abweichungen."""
    spec = METRICS[key]
    referenz = referenzbereich(key, profil)
    layers = []

    y_title = f"{spec['label']} ({spec['einheit']})"
    y_scale = alt.Scale(zero=False)

    # 1. Populations-Referenzband als blasser Hintergrund
    if show_population and referenz["bereich"]:
        low, high = referenz["bereich"]
        band = pd.DataFrame({"low": [low], "high": [high]})
        layers.append(
            alt.Chart(band)
            .mark_rect(opacity=0.13, color=FARBE_POPULATION)
            .encode(y=alt.Y("low:Q", scale=y_scale), y2="high:Q")
        )

    # 2. Persönlicher Baseline-Korridor (Median +/- 2 robuste SD)
    if show_baseline and "baseline_low" in df.columns:
        layers.append(
            alt.Chart(df)
            .mark_area(opacity=0.18, color=FARBE_BASELINE)
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y("baseline_low:Q", scale=y_scale, title=y_title),
                y2="baseline_high:Q",
            )
        )

    # 3. Tageswerte, dezent im Hintergrund
    layers.append(
        alt.Chart(df)
        .mark_circle(size=9, opacity=0.28, color=FARBE_LINIE)
        .encode(
            x=alt.X("date:T", title=None),
            y=alt.Y("value:Q", scale=y_scale, title=y_title),
            tooltip=[
                alt.Tooltip("date:T", title="Datum"),
                alt.Tooltip("value:Q", title=spec["label"], format=".1f"),
            ],
        )
    )

    # 4. Geglättete Trendlinie
    if smoothing and smoothing in df.columns:
        layers.append(
            alt.Chart(df)
            .mark_line(strokeWidth=2.4, color=FARBE_LINIE)
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y(f"{smoothing}:Q", scale=y_scale, title=y_title),
                tooltip=[
                    alt.Tooltip("date:T", title="Datum"),
                    alt.Tooltip(f"{smoothing}:Q", title="Trend", format=".1f"),
                ],
            )
        )

    # 5. Auffällige Tage hervorheben
    if "z" in df.columns:
        auffaellig = df[df["z"].abs() >= 2]
        if not auffaellig.empty:
            layers.append(
                alt.Chart(auffaellig)
                .mark_point(size=48, color=FARBE_ABWEICHUNG, filled=True, opacity=0.85)
                .encode(
                    x=alt.X("date:T", title=None),
                    y=alt.Y("value:Q", scale=y_scale, title=y_title),
                    tooltip=[
                        alt.Tooltip("date:T", title="Datum"),
                        alt.Tooltip("value:Q", title=spec["label"], format=".1f"),
                        alt.Tooltip("z:Q", title="Abweichung (SD)", format=".1f"),
                    ],
                )
            )

    return alt.layer(*layers).properties(height=height).interactive(bind_y=False)


def legende(show_population: bool, has_population: bool) -> None:
    teile = []
    if show_population and has_population:
        teile.append(f"<span style='color:{FARBE_POPULATION}'>■</span> Referenzbereich Literatur")
    teile.append(f"<span style='color:{FARBE_BASELINE}'>■</span> deine Baseline (±2 SD)")
    teile.append(f"<span style='color:{FARBE_LINIE}'>—</span> Trend")
    teile.append(f"<span style='color:{FARBE_ABWEICHUNG}'>●</span> auffälliger Tag")
    st.caption(" &nbsp;&nbsp; ".join(teile), unsafe_allow_html=True)


def jahresvergleich(df: pd.DataFrame, key: str) -> alt.Chart:
    """Boxplot pro Jahr - zeigt Verschiebungen im Langzeitverlauf."""
    spec = METRICS[key]
    data = df.copy()
    data["Jahr"] = data["date"].dt.year.astype(str)

    return (
        alt.Chart(data)
        .mark_boxplot(extent="min-max", size=34, color=FARBE_BASELINE)
        .encode(
            x=alt.X("Jahr:N", title=None),
            y=alt.Y("value:Q", scale=alt.Scale(zero=False), title=spec["einheit"]),
        )
        .properties(height=260)
    )
