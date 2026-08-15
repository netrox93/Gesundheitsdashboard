"""Gesundheitsdashboard - Startseite mit Statusübersicht.

Starten mit:
    ../../.venv/Scripts/python.exe -m streamlit run app/dashboard.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import data_access as da
import pandas as pd
import profil as profil_modul
import streamlit as st
from charts import bewertung, infobox
from reference_ranges import (
    DISCLAIMER,
    METRICS,
    SCHWELLE_STANDARD,
    STATUS_METRICS,
)

st.set_page_config(page_title="Gesundheitsdashboard", page_icon="", layout="wide")

st.title("Gesundheitsdashboard")

if not da.db_exists():
    st.error(
        "Keine Datenbank gefunden. Erst den Export importieren:\n\n"
        "`python app/import_export.py imports/apple_health_export/Export.xml`\n\n"
        "und anschliessend `python app/build_daily.py` ausführen."
    )
    st.stop()

start, end = da.data_range()
if start is None:
    st.warning("Die Datenbank enthält noch keine Tageswerte. `app/build_daily.py` ausführen.")
    st.stop()

profil = da.load_profil()

st.caption(
    f"Datenbestand {start:%d.%m.%Y} bis {end:%d.%m.%Y} · "
    f"Profil: {profil_modul.beschreibung(profil)}"
)

if not profil:
    st.info(
        "Kein Profil hinterlegt. Alters- und geschlechtsabhängige "
        "Referenzbereiche (VO2max, Schlafdauer, Schritte) können deshalb "
        "nicht angepasst werden - auf der Seite **Daten einlesen** "
        "nachtragen."
    )

# ------------------------------------------------------------------
# Statuskacheln: letzte 7 Tage gegen die persönliche 90-Tage-Baseline
# ------------------------------------------------------------------

st.subheader("Aktueller Status")
st.caption(
    "Mittelwert der letzten 7 Tage mit Daten, verglichen mit deiner "
    "persönlichen Baseline der vorangegangenen 90 Tage."
)

zeilen = []
for key in STATUS_METRICS:
    df = da.add_baseline(da.load_metric(key))
    if df.empty or df["baseline"].isna().all():
        continue

    letzte = df.dropna(subset=["baseline"]).tail(7)
    if letzte.empty:
        continue

    aktuell = letzte["value"].mean()
    basis = letzte["baseline"].iloc[-1]
    streuung = letzte["spread"].iloc[-1]
    z = (aktuell - basis) / streuung if streuung and streuung > 1e-9 else None

    zeilen.append(
        {
            "key": key,
            "aktuell": aktuell,
            "baseline": basis,
            "z": z,
            "stand": letzte["date"].max(),
        }
    )

spalten = st.columns(3)
for i, zeile in enumerate(zeilen):
    spec = METRICS[zeile["key"]]
    text, farbe, symbol = bewertung(zeile["key"], zeile["z"])
    delta = zeile["aktuell"] - zeile["baseline"]

    with spalten[i % 3]:
        st.metric(
            spec["label"],
            da.format_value(zeile["key"], zeile["aktuell"]),
            delta=f"{delta:+.1f} vs. Baseline" if abs(delta) >= 0.05 else "unverändert",
            delta_color="off",
        )
        st.markdown(
            f"<span style='color:{farbe}'>{symbol} {text}</span>",
            unsafe_allow_html=True,
        )
        st.caption(f"Baseline: {da.format_value(zeile['key'], zeile['baseline'])}")

if not zeilen:
    st.info("Noch nicht genug Daten für eine Baseline (mindestens 20 Tage nötig).")

st.divider()

# ------------------------------------------------------------------
# Auffälligkeiten der letzten 30 Tage
# ------------------------------------------------------------------

st.subheader("Auffälligkeiten der letzten 30 Tage")

grenze = pd.Timestamp(end) - pd.Timedelta(days=30)
auffaellig = []

for key in METRICS:
    df = da.add_baseline(da.load_metric(key))
    if df.empty or "z" not in df.columns:
        continue
    letzte = df[(df["date"] >= grenze) & (df["z"].abs() >= SCHWELLE_STANDARD)]
    for _, row in letzte.iterrows():
        auffaellig.append(
            {
                "Datum": row["date"].strftime("%d.%m.%Y"),
                "Kennzahl": METRICS[key]["label"],
                "Wert": da.format_value(key, row["value"]),
                "Baseline": da.format_value(key, row["baseline"]),
                "Abweichung": f"{row['z']:+.1f} SD",
                "_sort": row["date"],
            }
        )

if auffaellig:
    tabelle = pd.DataFrame(auffaellig).sort_values("_sort", ascending=False).drop(columns="_sort")
    st.dataframe(tabelle, use_container_width=True, hide_index=True)
    st.caption(
        f"Gezeigt werden Tage, die mehr als {SCHWELLE_STANDARD:.0f} "
        "Standardabweichungen von der eigenen Baseline abweichen. Einzelne "
        "solcher Tage sind statistisch zu erwarten und meist harmlos - "
        "relevant sind Häufungen und Serien über mehrere Tage. Details und "
        "möglicher Kontext auf der Seite 'Abweichungen'."
    )
else:
    st.success(
        f"Keine Werte ausserhalb von {SCHWELLE_STANDARD:.0f} "
        "Standardabweichungen in den letzten 30 Tagen."
    )

st.divider()

with st.expander("Kennzahlen erklärt"):
    for key in STATUS_METRICS:
        infobox(key, profil=profil)

st.caption(DISCLAIMER)
