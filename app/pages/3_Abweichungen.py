"""Seite 3: Auffällige Tage finden und einordnen.

Kernidee: Ein auffälliger Tag allein sagt wenig. Interessant wird er
durch den Kontext - was war an dem Tag und den Tagen davor sonst noch
ungewöhnlich? Genau dort docken später Kalender, Wetter und Raumklima an.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import data_access as da
import pandas as pd
import streamlit as st
from charts import infobox
from reference_ranges import DISCLAIMER, KONTEXT_METRICS, METRICS, SCHWELLE_STANDARD

st.set_page_config(page_title="Abweichungen", layout="wide")
st.title("Abweichungen")

if not da.db_exists():
    st.error("Keine Datenbank gefunden. Erst importieren und `build_daily.py` ausführen.")
    st.stop()

start, end = da.data_range()

st.markdown(
    "Ein Tag gilt hier als auffällig, wenn er stark von **deiner eigenen** "
    "Baseline der vorangegangenen 90 Tage abweicht - nicht vom "
    "Literaturbereich. Für die Abweichungserkennung ist die persönliche "
    "Baseline das empfindlichere Mass."
)

with st.sidebar:
    st.header("Filter")
    schwelle = st.slider(
        "Schwelle (Standardabweichungen)",
        min_value=1.5,
        max_value=4.0,
        value=SCHWELLE_STANDARD,
        step=0.5,
        help="Voreinstellung 3 SD. Bei normalverteilten Daten wären mit 2 SD "
        "etwa 5 % der Tage auffällig - in diesen Daten sind es rund 10 %, "
        "weil die Verteilungen breitere Ränder haben als eine "
        "Normalverteilung. 3 SD liefert mit ca. 3 % der Tage ein "
        "brauchbares Signal-Rausch-Verhältnis.",
    )
    tage_zurueck = st.selectbox(
        "Zeitraum", [90, 180, 365, 1095], index=2, format_func=lambda t: f"Letzte {t} Tage"
    )
    gewaehlte_metriken = st.multiselect(
        "Kennzahlen",
        list(METRICS.keys()),
        default=["resting_hr", "hrv", "sleep_hours", "respiratory_rate"],
        format_func=lambda k: METRICS[k]["label"],
    )

grenze = pd.Timestamp(end) - pd.Timedelta(days=tage_zurueck)

# ------------------------------------------------------------------
# Alle Reihen einmal laden - auch für das Kontext-Panel
# ------------------------------------------------------------------


@st.cache_data(ttl=3600)
def alle_reihen() -> dict:
    return {k: da.add_baseline(da.load_metric(k)) for k in METRICS}


reihen = alle_reihen()

treffer = []
for key in gewaehlte_metriken:
    df = reihen.get(key)
    if df is None or df.empty or "z" not in df.columns:
        continue
    auffaellig = df[(df["date"] >= grenze) & (df["z"].abs() >= schwelle)]
    for _, row in auffaellig.iterrows():
        treffer.append(
            {
                "datum": row["date"],
                "key": key,
                "kennzahl": METRICS[key]["label"],
                "wert": row["value"],
                "baseline": row["baseline"],
                "z": row["z"],
            }
        )

if not treffer:
    st.success(
        f"Keine Abweichungen über {schwelle} Standardabweichungen in den "
        f"letzten {tage_zurueck} Tagen."
    )
    st.stop()

treffer_df = pd.DataFrame(treffer).sort_values("datum", ascending=False)

# ------------------------------------------------------------------
# Tage mit mehreren auffälligen Kennzahlen zuerst
# ------------------------------------------------------------------

haeufung = treffer_df.groupby("datum").size().reset_index(name="anzahl")
mehrfach = haeufung[haeufung["anzahl"] >= 2].sort_values("datum", ascending=False)

st.subheader(f"{len(treffer_df)} Auffälligkeiten an {treffer_df['datum'].nunique()} Tagen")

if not mehrfach.empty:
    st.warning(
        f"An {len(mehrfach)} Tagen sind mehrere Kennzahlen gleichzeitig "
        "auffällig. Solche Tage sind aussagekräftiger als einzelne Ausreisser, "
        "weil zufällige Messfehler selten mehrere Kennzahlen gleichzeitig treffen."
    )

# ------------------------------------------------------------------
# Serien: mehrere Tage in Folge in dieselbe Richtung
# ------------------------------------------------------------------

serien = []
for key in gewaehlte_metriken:
    df = reihen.get(key)
    if df is None or df.empty:
        continue
    for run in da.find_runs(df[df["date"] >= grenze], schwelle):
        serien.append(
            {
                "Zeitraum": f"{run['start']:%d.%m.} - {run['ende']:%d.%m.%Y}",
                "Kennzahl": METRICS[key]["label"],
                "Tage": run["tage"],
                "Richtung": run["richtung"],
                "Mittelwert": da.format_value(key, run["mittel"]),
                "_sort": run["start"],
            }
        )

if serien:
    st.markdown("#### Serien über mehrere Tage")
    st.caption(
        "Mehrere aufeinanderfolgende Tage in dieselbe Richtung. Fachlich der "
        "aussagekräftigere Befund - einzelne Ausreisser sind häufig "
        "Messartefakte, eine Serie deutet eher auf ein tatsächliches "
        "Geschehen hin (etwa Infekt, Belastungsphase, Reise)."
    )
    serien_df = pd.DataFrame(serien).sort_values("_sort", ascending=False).drop(columns="_sort")
    st.dataframe(serien_df, use_container_width=True, hide_index=True)
    st.markdown("#### Einzelne auffällige Tage")

uebersicht = treffer_df.copy()
uebersicht["Datum"] = uebersicht["datum"].dt.strftime("%d.%m.%Y")
uebersicht["Wert"] = [da.format_value(r["key"], r["wert"]) for _, r in uebersicht.iterrows()]
uebersicht["Baseline"] = [
    da.format_value(r["key"], r["baseline"]) for _, r in uebersicht.iterrows()
]
uebersicht["Abweichung"] = uebersicht["z"].map(lambda z: f"{z:+.1f} SD")

st.dataframe(
    uebersicht[["Datum", "kennzahl", "Wert", "Baseline", "Abweichung"]].rename(
        columns={"kennzahl": "Kennzahl"}
    ),
    use_container_width=True,
    hide_index=True,
)

st.divider()

# ------------------------------------------------------------------
# Kontext-Panel für einen ausgewählten Tag
# ------------------------------------------------------------------

st.subheader("Einzelnen Tag einordnen")

tage = sorted(treffer_df["datum"].unique(), reverse=True)
gewaehlter_tag = st.selectbox(
    "Auffälliger Tag",
    tage,
    format_func=lambda d: (
        f"{pd.Timestamp(d):%d.%m.%Y} - "
        + ", ".join(treffer_df[treffer_df["datum"] == d]["kennzahl"].tolist())
    ),
)

tag = pd.Timestamp(gewaehlter_tag)

st.markdown(f"### {tag:%A, %d.%m.%Y}")

betroffen = treffer_df[treffer_df["datum"] == tag]
for _, row in betroffen.iterrows():
    richtung = "über" if row["z"] > 0 else "unter"
    st.markdown(
        f"- **{row['kennzahl']}**: {da.format_value(row['key'], row['wert'])} "
        f"({abs(row['z']):.1f} SD {richtung} deiner Baseline von "
        f"{da.format_value(row['key'], row['baseline'])})"
    )

st.markdown("#### Was war an diesem Tag und den Tagen davor sonst noch ungewöhnlich?")
st.caption(
    "Alle Kontext-Kennzahlen für Tag 0 bis 3 Tage davor, jeweils als "
    "Abweichung von der eigenen Baseline. Damit lässt sich eingrenzen, "
    "was zeitlich zusammenfällt - ein Zusammenhang ist damit noch nicht bewiesen."
)

kontext_zeilen = []
for versatz in range(0, 4):
    datum = tag - pd.Timedelta(days=versatz)
    zeile = {"Tag": "Tag 0" if versatz == 0 else f"-{versatz} Tage", "_datum": datum}

    for key in KONTEXT_METRICS:
        df = reihen.get(key)
        if df is None or df.empty:
            zeile[METRICS[key]["label"]] = "-"
            continue
        eintrag = df[df["date"] == datum]
        if eintrag.empty:
            zeile[METRICS[key]["label"]] = "-"
            continue

        wert = eintrag["value"].iloc[0]
        z = eintrag["z"].iloc[0]
        text = da.format_value(key, wert)
        if pd.notna(z) and abs(z) >= 1.5:
            text += f"  ({z:+.1f} SD)"
        zeile[METRICS[key]["label"]] = text

    kontext_zeilen.append(zeile)

kontext_df = pd.DataFrame(kontext_zeilen).drop(columns="_datum")
st.dataframe(kontext_df, use_container_width=True, hide_index=True)

# Workouts im Umfeld
workouts = da.load_workouts()
if not workouts.empty:
    fenster = workouts[(workouts["date"] >= tag - pd.Timedelta(days=3)) & (workouts["date"] <= tag)]
    st.markdown("#### Trainings in diesem Zeitfenster")
    if fenster.empty:
        st.caption("Keine aufgezeichneten Trainingseinheiten in den 3 Tagen davor.")
    else:
        anzeige = fenster.copy()
        anzeige["Datum"] = anzeige["date"].dt.strftime("%d.%m.%Y")
        anzeige["Dauer"] = anzeige["duration_min"].round(0).astype("Int64").astype(str) + " min"
        anzeige["Distanz"] = anzeige["distance_km"].round(1).fillna(0).astype(str) + " km"
        anzeige["Kalorien"] = anzeige["energy_kcal"].round(0).fillna(0).astype(int).astype(str)
        st.dataframe(
            anzeige[["Datum", "typ", "Dauer", "Distanz", "Kalorien"]].rename(
                columns={"typ": "Art"}
            ),
            use_container_width=True,
            hide_index=True,
        )

st.info(
    "**Später ergänzbar:** An dieser Stelle sind Kalendereinträge, "
    "Wetterdaten und Raumklima als weitere Kontextzeilen vorgesehen - "
    "die Tagesstruktur der Aggregattabellen ist bereits darauf ausgelegt."
)

st.divider()

with st.expander("Kennzahlen dieses Tages erklärt"):
    for key in betroffen["key"].unique():
        infobox(key)

st.caption(DISCLAIMER)
