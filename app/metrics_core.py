"""Rechenkern: Laden, Baseline, Serien - ohne Streamlit-Abhängigkeit.

Bewusst getrennt von `data_access.py`, damit derselbe Code sowohl im
Dashboard als auch im PDF-Export (Kommandozeile) läuft.
"""

import sqlite3
from pathlib import Path

import einstellungen
import numpy as np
import pandas as pd
from reference_ranges import METRICS

# Skalierung der MAD zu einem Schätzer für die Standardabweichung
# einer Normalverteilung
MAD_TO_SD = 1.4826

BASELINE_WINDOW = 90
MIN_BASELINE_DAYS = 20


def connect(db_path: Path = None) -> sqlite3.Connection:
    """Verbindung zur konfigurierten Datenbank.

    Der Pfad wird bei jedem Aufruf frisch geholt, damit ein Wechsel der
    Datenbank im Dashboard sofort wirkt.
    """
    pfad = Path(db_path) if db_path else einstellungen.db_pfad()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(pfad, check_same_thread=False)


def db_exists(db_path: Path = None) -> bool:
    pfad = Path(db_path) if db_path else einstellungen.db_pfad()
    return pfad.exists()


# ------------------------------------------------------------------
# Laden
# ------------------------------------------------------------------


def load_metric(conn: sqlite3.Connection, key: str) -> pd.DataFrame:
    spec = METRICS[key]

    if spec.get("hk_type"):
        column = "total" if spec["agg"] == "sum" else "avg"
        df = pd.read_sql(
            f"SELECT date, {column} AS value FROM daily_metrics "
            "WHERE type = ? AND value IS NOT NULL ORDER BY date",
            conn,
            params=[spec["hk_type"]],
        )
    else:
        df = _load_sleep_metric(conn, spec)

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])
    df["value"] = df["value"] * spec.get("scale", 1)
    return df.dropna(subset=["value"]).reset_index(drop=True)


def _load_sleep_metric(conn: sqlite3.Connection, spec: dict) -> pd.DataFrame:
    column = spec["sleep_column"]

    if column in ("deep_share", "rem_share"):
        phase = "deep_min" if column == "deep_share" else "rem_min"
        return pd.read_sql(
            f"SELECT date, 100.0 * {phase} / asleep_min AS value FROM daily_sleep "
            f"WHERE asleep_min > 0 AND {phase} IS NOT NULL ORDER BY date",
            conn,
        )

    if column == "bedtime_minutes":
        # Uhrzeit in Minuten seit Mitternacht, um Mitternacht entfaltet:
        # 23:00 -> -60, 01:00 -> 60. Ohne das läge der Mittelwert aus
        # 23:30 und 00:30 mittags statt um Mitternacht.
        df = pd.read_sql(
            "SELECT date, bedtime FROM daily_sleep WHERE bedtime IS NOT NULL ORDER BY date",
            conn,
        )
        if df.empty:
            return df
        parts = df["bedtime"].str.split(":", expand=True).astype(float)
        minutes = parts[0] * 60 + parts[1]
        df["value"] = np.where(minutes > 12 * 60, minutes - 24 * 60, minutes)
        return df[["date", "value"]]

    return pd.read_sql(
        f"SELECT date, {column} AS value FROM daily_sleep WHERE {column} IS NOT NULL ORDER BY date",
        conn,
    )


def load_sleep(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM daily_sleep ORDER BY date", conn)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def load_workouts(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql(
        """
        SELECT REPLACE(activity_type, 'HKWorkoutActivityType', '') AS typ,
               source_name, duration_min, distance_km, energy_kcal,
               substr(start_date, 1, 10) AS date
        FROM workouts ORDER BY start_date
        """,
        conn,
    )
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def load_activity_summaries(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM activity_summaries ORDER BY date", conn)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def data_range(conn: sqlite3.Connection) -> tuple:
    row = conn.execute("SELECT MIN(date), MAX(date) FROM daily_metrics").fetchone()
    return (pd.to_datetime(row[0]), pd.to_datetime(row[1])) if row and row[0] else (None, None)


def record_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]


# ------------------------------------------------------------------
# Baseline und Abweichungen
# ------------------------------------------------------------------


def add_baseline(df: pd.DataFrame, window: int = BASELINE_WINDOW) -> pd.DataFrame:
    """Rollierende persönliche Baseline und robuster z-Wert.

    Median und MAD statt Mittelwert und Standardabweichung, weil einzelne
    Ausreisser (Krankheitstage, Messfehler) die Baseline sonst mitziehen.

    Das Fenster ist nach hinten geschlossen (closed='left'): der Tag selbst
    geht nicht in seine eigene Baseline ein.
    """
    if df.empty:
        return df

    out = df.copy().sort_values("date").reset_index(drop=True)
    rolling = out["value"].rolling(window=window, min_periods=MIN_BASELINE_DAYS, closed="left")

    out["baseline"] = rolling.median()
    mad = rolling.apply(lambda s: np.nanmedian(np.abs(s - np.nanmedian(s))), raw=True)
    out["spread"] = mad * MAD_TO_SD

    # Fällt die Streuung auf ~0 (konstante Phase), wäre jeder Wert
    # unendlich auffällig - solche Tage bleiben ohne z-Wert.
    valid = out["spread"] > 1e-9
    out["z"] = np.where(valid, (out["value"] - out["baseline"]) / out["spread"], np.nan)

    out["baseline_low"] = out["baseline"] - 2 * out["spread"]
    out["baseline_high"] = out["baseline"] + 2 * out["spread"]
    return out


def add_rolling_means(df: pd.DataFrame, windows=(7, 30, 90)) -> pd.DataFrame:
    out = df.copy()
    for w in windows:
        out[f"mean_{w}"] = out["value"].rolling(window=w, min_periods=max(3, w // 4)).mean()
    return out


def find_runs(df: pd.DataFrame, schwelle: float, min_laenge: int = 2) -> list:
    """Zusammenhängende Serien auffälliger Tage.

    Fachlich der interessantere Befund: Ein einzelner Ausreisser ist meist
    Rauschen oder Messartefakt, mehrere Tage in Folge in dieselbe Richtung
    deuten auf ein tatsächliches Geschehen hin.
    """
    if df.empty or "z" not in df.columns:
        return []

    data = df.dropna(subset=["z"]).sort_values("date").reset_index(drop=True)
    auffaellig = data["z"].abs() >= schwelle

    runs = []
    lauf = []
    for i, ist_auffaellig in enumerate(auffaellig):
        if not ist_auffaellig:
            if len(lauf) >= min_laenge:
                runs.append(lauf)
            lauf = []
            continue

        zeile = data.iloc[i]

        # Eine Serie endet, wenn die Abweichung die Richtung wechselt
        # (dann sind es zwei getrennte Ereignisse) oder wenn ein Tag ohne
        # Daten dazwischenliegt
        richtungswechsel = bool(lauf) and np.sign(zeile["z"]) != np.sign(lauf[-1]["z"])
        luecke = bool(lauf) and (zeile["date"] - lauf[-1]["date"]).days > 1

        if richtungswechsel or luecke:
            if len(lauf) >= min_laenge:
                runs.append(lauf)
            lauf = []

        lauf.append(zeile)

    if len(lauf) >= min_laenge:
        runs.append(lauf)

    return [
        {
            "start": r[0]["date"],
            "ende": r[-1]["date"],
            "tage": len(r),
            "richtung": "erhöht" if r[0]["z"] > 0 else "erniedrigt",
            "max_z": max(abs(x["z"]) for x in r),
            "mittel": sum(x["value"] for x in r) / len(r),
            "baseline": r[0]["baseline"],
        }
        for r in runs
    ]


# ------------------------------------------------------------------
# Abdeckung und Formatierung
# ------------------------------------------------------------------


def coverage_by_year(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Jahr", "Tage"])
    jahre = df.copy()
    jahre["Jahr"] = jahre["date"].dt.year
    return jahre.groupby("Jahr").size().reset_index(name="Tage")


def coverage_warning(df: pd.DataFrame, min_tage: int = 60) -> str:
    abdeckung = coverage_by_year(df)
    if abdeckung.empty:
        return ""

    duenn = abdeckung[abdeckung["Tage"] < min_tage]
    if duenn.empty:
        return ""

    teile = ", ".join(f"{int(r['Jahr'])} ({int(r['Tage'])} Tage)" for _, r in duenn.iterrows())
    return (
        f"Eingeschränkte Datenabdeckung in: {teile}. "
        "Kennzahlen dieser Jahre beruhen auf wenigen Tagen und sind nur "
        "eingeschränkt mit Volljahren vergleichbar."
    )


def filter_range(df: pd.DataFrame, start, end) -> pd.DataFrame:
    if df.empty:
        return df
    mask = (df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))
    return df.loc[mask].reset_index(drop=True)


def format_value(key: str, value: float) -> str:
    if value is None or pd.isna(value):
        return "-"

    spec = METRICS[key]
    if spec.get("sleep_column") == "bedtime_minutes":
        minutes = int(round(value)) % (24 * 60)
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    einheit = spec["einheit"]
    if einheit.startswith("Schritte"):
        return f"{value:,.0f}".replace(",", ".")
    if abs(value) >= 100:
        return f"{value:.0f} {einheit}"
    return f"{value:.1f} {einheit}"
