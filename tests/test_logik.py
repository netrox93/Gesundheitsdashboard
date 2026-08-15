"""Tests für die Rechenlogik.

Schwerpunkt auf den Stellen, an denen stille Fehler entstehen: die
Vereinigung überlappender Schlafsegmente, die Baseline-Berechnung und
die Serien-Erkennung.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

APP = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(APP))

from build_daily import _merged_minutes, _parse_ts  # noqa: E402


def ts(tag: int, stunde: int, minute: int = 0) -> datetime:
    return datetime(2025, 3, tag, stunde, minute, tzinfo=timezone.utc)


# ------------------------------------------------------------------
# Vereinigung von Intervallen
# ------------------------------------------------------------------


def test_merged_leere_liste():
    assert _merged_minutes([]) == 0.0


def test_merged_einzelnes_intervall():
    assert _merged_minutes([(ts(1, 22), ts(1, 23))]) == 60.0


def test_merged_disjunkte_intervalle_werden_addiert():
    intervalle = [(ts(1, 22), ts(1, 23)), (ts(2, 1), ts(2, 2))]
    assert _merged_minutes(intervalle) == 120.0


def test_merged_ueberlappung_zaehlt_nur_einmal():
    """Der eigentliche Fehlerfall: Watch und Pillow tracken dieselbe Nacht."""
    intervalle = [(ts(1, 22), ts(2, 6)), (ts(1, 23), ts(2, 5))]
    assert _merged_minutes(intervalle) == 8 * 60


def test_merged_teilueberlappung():
    intervalle = [(ts(1, 22), ts(2, 2)), (ts(2, 1), ts(2, 4))]
    assert _merged_minutes(intervalle) == 6 * 60


def test_merged_reihenfolge_egal():
    a = [(ts(2, 1), ts(2, 4)), (ts(1, 22), ts(2, 2))]
    b = [(ts(1, 22), ts(2, 2)), (ts(2, 1), ts(2, 4))]
    assert _merged_minutes(a) == _merged_minutes(b)


def test_merged_aneinandergrenzend_wird_zusammengefasst():
    intervalle = [(ts(1, 22), ts(1, 23)), (ts(1, 23), ts(2, 0))]
    assert _merged_minutes(intervalle) == 120.0


# ------------------------------------------------------------------
# Zeitstempel
# ------------------------------------------------------------------


def test_parse_ts_mit_zeitzone():
    parsed = _parse_ts("2024-03-01 23:50:17 +0100")
    assert parsed.year == 2024 and parsed.hour == 23 and parsed.minute == 50


def test_parse_ts_ungueltig_gibt_none():
    assert _parse_ts("kaputt") is None


# ------------------------------------------------------------------
# Baseline und Serien - ohne Streamlit-Abhängigkeit nachgebaut
# ------------------------------------------------------------------

MAD_TO_SD = 1.4826


def baseline(df: pd.DataFrame, window: int = 90, min_periods: int = 20) -> pd.DataFrame:
    out = df.copy().sort_values("date").reset_index(drop=True)
    rolling = out["value"].rolling(window=window, min_periods=min_periods, closed="left")
    out["baseline"] = rolling.median()
    mad = rolling.apply(lambda s: np.nanmedian(np.abs(s - np.nanmedian(s))), raw=True)
    out["spread"] = mad * MAD_TO_SD
    valid = out["spread"] > 1e-9
    out["z"] = np.where(valid, (out["value"] - out["baseline"]) / out["spread"], np.nan)
    return out


def reihe(werte, start="2024-01-01") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range(start, periods=len(werte), freq="D"),
            "value": werte,
        }
    )


def test_baseline_schliesst_aktuellen_tag_aus():
    """Der Tag selbst darf seine eigene Baseline nicht beeinflussen -
    sonst zieht ein Ausreisser seine eigene Referenz mit hoch."""
    werte = [50.0] * 40 + [90.0]
    ergebnis = baseline(reihe(werte))
    assert ergebnis["baseline"].iloc[-1] == pytest.approx(50.0)


def test_baseline_erkennt_ausreisser():
    rng = np.random.default_rng(42)
    werte = list(rng.normal(55, 3, 120)) + [95.0]
    ergebnis = baseline(reihe(werte))
    assert abs(ergebnis["z"].iloc[-1]) > 5


def test_baseline_ohne_streuung_gibt_kein_z():
    """Konstante Phase: die Streuung ist 0, ein z-Wert wäre unendlich."""
    ergebnis = baseline(reihe([50.0] * 40))
    assert ergebnis["z"].iloc[-1] != ergebnis["z"].iloc[-1]  # NaN


def test_baseline_zu_wenige_daten_bleibt_leer():
    ergebnis = baseline(reihe([50.0] * 10))
    assert ergebnis["baseline"].isna().all()


# ------------------------------------------------------------------
# Zubettgehzeit um Mitternacht
# ------------------------------------------------------------------


def entfalte(minuten: float) -> float:
    return minuten - 24 * 60 if minuten > 12 * 60 else minuten


def test_zubettgehzeit_vor_mitternacht_wird_negativ():
    assert entfalte(23 * 60 + 30) == -30


def test_zubettgehzeit_nach_mitternacht_bleibt_positiv():
    assert entfalte(30) == 30


def test_zubettgehzeit_mittelwert_liegt_um_mitternacht():
    """Ohne Entfaltung läge der Mittelwert aus 23:30 und 00:30 mittags."""
    mittel = np.mean([entfalte(23 * 60 + 30), entfalte(30)])
    assert mittel == pytest.approx(0.0)
