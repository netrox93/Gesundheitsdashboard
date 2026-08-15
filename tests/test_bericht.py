"""Tests für Serien-Erkennung und Berichtsaufbereitung.

Arbeiten auf einer temporären Datenbank mit konstruierten Daten, damit
die Tests unabhängig vom echten Export laufen.
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

APP = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(APP))

import metrics_core as core  # noqa: E402
from pdf_data import PHYSIO_METRIKEN, _lage, _phasentabelle  # noqa: E402
from reference_ranges import METRICS  # noqa: E402


def reihe(werte, start="2024-01-01") -> pd.DataFrame:
    return pd.DataFrame(
        {"date": pd.date_range(start, periods=len(werte), freq="D"), "value": werte}
    )


# ------------------------------------------------------------------
# Serien
# ------------------------------------------------------------------


def test_einzelner_ausreisser_ist_keine_serie():
    werte = [50.0] * 100 + [90.0] + [50.0] * 5
    runs = core.find_runs(core.add_baseline(reihe(werte)), schwelle=3)
    assert runs == []


def test_zwei_tage_in_folge_sind_eine_serie():
    werte = [50.0, 51.0, 49.0, 50.5] * 25 + [90.0, 91.0] + [50.0] * 3
    runs = core.find_runs(core.add_baseline(reihe(werte)), schwelle=3)
    assert len(runs) == 1
    assert runs[0]["tage"] == 2
    assert runs[0]["richtung"] == "erhöht"


def test_richtungswechsel_trennt_serien():
    """Ein Sprung nach oben und direkt danach nach unten ist nicht eine
    durchgehende Phase, sondern zwei getrennte Ereignisse."""
    werte = [50.0, 51.0, 49.0, 50.5] * 25 + [90.0, 91.0, 10.0, 9.0] + [50.0] * 3
    runs = core.find_runs(core.add_baseline(reihe(werte)), schwelle=3)
    assert len(runs) == 2
    assert {r["richtung"] for r in runs} == {"erhöht", "erniedrigt"}


def test_datumsluecke_trennt_serien():
    basis = reihe([50.0, 51.0, 49.0, 50.5] * 25)
    ausschlag = pd.DataFrame(
        {
            "date": [
                pd.Timestamp("2024-04-10"),
                pd.Timestamp("2024-04-11"),
                pd.Timestamp("2024-04-20"),
                pd.Timestamp("2024-04-21"),
            ],
            "value": [90.0, 91.0, 92.0, 90.5],
        }
    )
    df = pd.concat([basis, ausschlag], ignore_index=True)
    runs = core.find_runs(core.add_baseline(df), schwelle=3)
    assert len(runs) == 2


def test_serie_liefert_mittelwert_und_baseline():
    werte = [50.0, 51.0, 49.0, 50.5] * 25 + [90.0, 92.0] + [50.0] * 3
    runs = core.find_runs(core.add_baseline(reihe(werte)), schwelle=3)
    assert runs[0]["mittel"] == pytest.approx(91.0)
    assert runs[0]["baseline"] == pytest.approx(50.0, abs=1.5)


# ------------------------------------------------------------------
# Lage zum Referenzbereich
# ------------------------------------------------------------------


def test_lage_ohne_populationsbereich():
    spec = {"population": None, "richtung": "hoeher_besser"}
    assert "kein Populationsbereich" in _lage(reihe([50.0] * 10), spec)


def test_lage_ueberwiegend_innerhalb():
    spec = {"population": (60, 100), "richtung": "niedriger_besser"}
    assert "überwiegend im Referenzbereich" in _lage(reihe([70.0] * 10), spec)


def test_lage_unterhalb_nennt_trainingszustand():
    """Bei niedriger-ist-besser soll die Einordnung erklären, statt nur
    'ausserhalb' zu melden."""
    spec = {"population": (60, 100), "richtung": "niedriger_besser"}
    text = _lage(reihe([50.0] * 10), spec)
    assert "unterhalb" in text and "Ausdauertrainierten" in text


def test_lage_oberhalb_bei_hoeher_besser():
    spec = {"population": (8000, 10000), "richtung": "hoeher_besser"}
    text = _lage(reihe([16000.0] * 10), spec)
    assert "oberhalb" in text and "günstige Richtung" in text


# ------------------------------------------------------------------
# Phasentabelle mit Notizspalte
# ------------------------------------------------------------------


def _serie(key, start, ende, tage, richtung="erhöht", mittel=72.5, baseline=53.0, z=3.4):
    return {
        "key": key,
        "start": pd.Timestamp(start),
        "ende": pd.Timestamp(ende),
        "tage": tage,
        "richtung": richtung,
        "mittel": mittel,
        "baseline": baseline,
        "max_z": z,
        "label": METRICS[key]["label"],
    }


def test_phasentabelle_filtert_nach_kennzahl():
    serien = [
        _serie("resting_hr", "2026-05-26", "2026-05-27", 2),
        _serie("spo2", "2025-12-08", "2025-12-09", 2),
    ]
    zeilen = _phasentabelle("resting_hr", serien)
    assert len(zeilen) == 1
    assert zeilen[0]["zeitraum"] == "26.05. - 27.05.2026"


def test_phasentabelle_formatiert_werte_mit_einheit():
    zeilen = _phasentabelle("resting_hr", [_serie("resting_hr", "2026-05-26", "2026-05-27", 2)])
    assert zeilen[0]["mittel"] == "72.5 /min"
    assert zeilen[0]["baseline"] == "53.0 /min"
    assert zeilen[0]["abweichung"] == "3.4 SD"


def test_phasentabelle_leer_ohne_treffer():
    assert _phasentabelle("hrv", [_serie("resting_hr", "2026-05-26", "2026-05-27", 2)]) == []


# ------------------------------------------------------------------
# Auswahl der Kennzahlen für die Arzt-Tabelle
# ------------------------------------------------------------------


def test_physio_metriken_existieren_alle():
    unbekannt = PHYSIO_METRIKEN - set(METRICS)
    assert not unbekannt, f"Unbekannte Kennzahlen: {unbekannt}"


def test_aktivitaetsgroessen_nicht_in_arzttabelle():
    """Erhöhte Schritte sind eine Wanderung, kein Befund."""
    for key in ("steps", "exercise_min", "vo2max", "flights"):
        assert key not in PHYSIO_METRIKEN


# ------------------------------------------------------------------
# Laden gegen eine echte kleine Datenbank
# ------------------------------------------------------------------


@pytest.fixture
def mini_db(tmp_path) -> Path:
    pfad = tmp_path / "mini.db"
    conn = sqlite3.connect(pfad)
    conn.executescript((APP / "schema.sql").read_text(encoding="utf-8"))

    zeilen = [
        (
            f"2024-01-{tag:02d}",
            "HKQuantityTypeIdentifierRestingHeartRate",
            "count/min",
            30,
            None,
            55.0 + tag % 3,
            50.0,
            60.0,
        )
        for tag in range(1, 29)
    ]
    conn.executemany(
        "INSERT INTO daily_metrics (date, type, unit, n, total, avg, min, max) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        zeilen,
    )
    conn.commit()
    conn.close()
    return pfad


def test_load_metric_liest_tageswerte(mini_db):
    conn = core.connect(mini_db)
    df = core.load_metric(conn, "resting_hr")
    conn.close()
    assert len(df) == 28
    assert df["value"].between(55, 57).all()


def test_load_metric_leer_bei_fehlender_kennzahl(mini_db):
    conn = core.connect(mini_db)
    df = core.load_metric(conn, "vo2max")
    conn.close()
    assert df.empty


def test_skalierung_wird_angewendet(tmp_path):
    """SpO2 liegt als Anteil in der DB und muss als Prozent herauskommen."""
    pfad = tmp_path / "spo2.db"
    conn = sqlite3.connect(pfad)
    conn.executescript((APP / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO daily_metrics (date, type, unit, n, total, avg, min, max) "
        "VALUES ('2024-01-01', 'HKQuantityTypeIdentifierOxygenSaturation', "
        "'%', 10, 9.7, 0.97, 0.95, 0.99)"
    )
    conn.commit()
    conn.close()

    conn = core.connect(pfad)
    df = core.load_metric(conn, "spo2")
    conn.close()
    assert df["value"].iloc[0] == pytest.approx(97.0)
