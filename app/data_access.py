"""Datenzugriff fürs Dashboard - Streamlit-Caching um den Rechenkern.

Die eigentliche Logik liegt in `metrics_core.py`, damit derselbe Code
auch im PDF-Export ohne Streamlit läuft. Diese Datei ergänzt nur das
Caching und hält die im Dashboard genutzte Schnittstelle stabil.

Alle Abfragen laufen gegen die Aggregattabellen (`daily_metrics`,
`daily_sleep`), nicht gegen die Rohdaten - `records` hat mehrere
Millionen Zeilen und ist für interaktive Abfragen zu langsam.
"""

import metrics_core as core
import pandas as pd
import streamlit as st

# Für bestehende Importe aus den Seiten weiterhin verfügbar
from metrics_core import (  # noqa: F401
    BASELINE_WINDOW,
    DB_PATH,
    MAD_TO_SD,
    MIN_BASELINE_DAYS,
    add_baseline,
    add_rolling_means,
    coverage_by_year,
    coverage_warning,
    filter_range,
    find_runs,
    format_value,
)


@st.cache_resource
def get_connection():
    return core.connect()


def db_exists() -> bool:
    return core.db_exists()


@st.cache_data(ttl=3600)
def load_metric(key: str) -> pd.DataFrame:
    return core.load_metric(get_connection(), key)


@st.cache_data(ttl=3600)
def load_workouts() -> pd.DataFrame:
    return core.load_workouts(get_connection())


@st.cache_data(ttl=3600)
def load_sleep() -> pd.DataFrame:
    return core.load_sleep(get_connection())


@st.cache_data(ttl=3600)
def load_activity_summaries() -> pd.DataFrame:
    return core.load_activity_summaries(get_connection())


@st.cache_data(ttl=3600)
def data_range() -> tuple:
    return core.data_range(get_connection())


@st.cache_data(ttl=60)
def load_profil() -> dict:
    """Profil (Geburtsdatum, Geschlecht) für die Referenzbereiche.

    Kurze Cache-Dauer, damit eine Änderung auf der Einlese-Seite ohne
    Neustart wirkt.
    """
    import profil as profil_modul

    return profil_modul.lade(get_connection())
