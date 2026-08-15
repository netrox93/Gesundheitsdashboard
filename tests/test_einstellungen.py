"""Tests für Konfiguration und Datenbank-Prüfung.

Die Prüfung ist wichtig, weil ein falsch gewählter Pfad sonst erst
später als unverständlicher Fehler im Dashboard auftaucht.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

APP = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(APP))

import einstellungen  # noqa: E402


@pytest.fixture(autouse=True)
def eigene_konfig(tmp_path, monkeypatch):
    """Konfiguration und Standardpfad in ein temporäres Verzeichnis legen,
    damit die Tests die echte Installation nicht anfassen."""
    monkeypatch.setattr(einstellungen, "KONFIG_DATEI", tmp_path / "einstellungen.json")
    monkeypatch.setattr(einstellungen, "STANDARD_DB", tmp_path / "data" / "health.db")
    return tmp_path


def baue_datenbank(pfad: Path, mit_tabellen=("records", "daily_metrics")) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(pfad)
    for tabelle in mit_tabellen:
        if tabelle == "daily_metrics":
            conn.execute("CREATE TABLE daily_metrics (date TEXT, type TEXT, avg REAL)")
            conn.execute("INSERT INTO daily_metrics VALUES ('2025-01-01', 'x', 1.0)")
            conn.execute("INSERT INTO daily_metrics VALUES ('2025-06-30', 'x', 2.0)")
        else:
            conn.execute(f"CREATE TABLE {tabelle} (id INTEGER)")
            conn.execute(f"INSERT INTO {tabelle} VALUES (1)")
    conn.commit()
    conn.close()
    return pfad


# ------------------------------------------------------------------
# Pfad-Konfiguration
# ------------------------------------------------------------------


def test_standardpfad_ohne_konfiguration():
    assert einstellungen.db_pfad() == einstellungen.STANDARD_DB
    assert einstellungen.ist_standardpfad()


def test_eigener_pfad_wird_gemerkt(tmp_path):
    ziel = tmp_path / "woanders" / "health.db"
    einstellungen.setze_db_pfad(ziel)

    assert einstellungen.db_pfad() == ziel.resolve()
    assert not einstellungen.ist_standardpfad()


def test_zuruecksetzen_stellt_standard_wieder_her(tmp_path):
    einstellungen.setze_db_pfad(tmp_path / "anders.db")
    einstellungen.zuruecksetzen()

    assert einstellungen.db_pfad() == einstellungen.STANDARD_DB
    assert einstellungen.ist_standardpfad()


def test_kaputte_konfiguration_blockiert_nicht(eigene_konfig):
    einstellungen.KONFIG_DATEI.parent.mkdir(parents=True, exist_ok=True)
    einstellungen.KONFIG_DATEI.write_text("{kein gueltiges json", encoding="utf-8")

    # Fällt auf den Standard zurück, statt eine Ausnahme zu werfen
    assert einstellungen.db_pfad() == einstellungen.STANDARD_DB


def test_andere_einstellungen_bleiben_erhalten(tmp_path):
    einstellungen.setze_db_pfad(tmp_path / "a.db")
    konfig = einstellungen._lade_konfig()
    konfig["etwas_anderes"] = 42
    einstellungen._speichere_konfig(konfig)

    einstellungen.setze_db_pfad(tmp_path / "b.db")
    assert einstellungen._lade_konfig()["etwas_anderes"] == 42


# ------------------------------------------------------------------
# Datenbank-Prüfung
# ------------------------------------------------------------------


def test_gueltige_datenbank_wird_erkannt(tmp_path):
    pfad = baue_datenbank(tmp_path / "health.db")
    ergebnis = einstellungen.pruefe_datenbank(pfad)

    assert ergebnis["gueltig"]
    assert ergebnis["tabellen"]["records"] == 1
    assert ergebnis["tabellen"]["daily_metrics"] == 2
    assert ergebnis["zeitraum"] == ("2025-01-01", "2025-06-30")


def test_fehlende_datei(tmp_path):
    ergebnis = einstellungen.pruefe_datenbank(tmp_path / "gibtsnicht.db")
    assert not ergebnis["gueltig"]
    assert "existiert nicht" in ergebnis["meldung"]


def test_ordner_statt_datei(tmp_path):
    ergebnis = einstellungen.pruefe_datenbank(tmp_path)
    assert not ergebnis["gueltig"]
    assert "Ordner" in ergebnis["meldung"]


def test_keine_sqlite_datei(tmp_path):
    pfad = tmp_path / "falsch.db"
    pfad.write_text("das ist nur Text", encoding="utf-8")

    ergebnis = einstellungen.pruefe_datenbank(pfad)
    assert not ergebnis["gueltig"]
    assert "keine SQLite" in ergebnis["meldung"]


def test_fremde_sqlite_datenbank(tmp_path):
    """Eine SQLite-Datei aus einem anderen Programm darf nicht durchgehen."""
    pfad = tmp_path / "fremd.db"
    conn = sqlite3.connect(pfad)
    conn.execute("CREATE TABLE irgendwas (a INTEGER)")
    conn.commit()
    conn.close()

    ergebnis = einstellungen.pruefe_datenbank(pfad)
    assert not ergebnis["gueltig"]
    assert "nicht aus diesem Projekt" in ergebnis["meldung"]
    assert "records" in ergebnis["meldung"]


def test_unvollstaendige_datenbank(tmp_path):
    pfad = baue_datenbank(tmp_path / "halb.db", mit_tabellen=("records",))
    ergebnis = einstellungen.pruefe_datenbank(pfad)

    assert not ergebnis["gueltig"]
    assert "daily_metrics" in ergebnis["meldung"]


def test_pruefung_meldet_groesse(tmp_path):
    pfad = baue_datenbank(tmp_path / "health.db")
    assert einstellungen.pruefe_datenbank(pfad)["groesse_mb"] > 0


def test_pruefung_veraendert_die_datei_nicht(tmp_path):
    """Geöffnet wird nur lesend - eine verknüpfte Datenbank darf durch das
    blosse Prüfen nicht angefasst werden."""
    pfad = baue_datenbank(tmp_path / "health.db")
    vorher = pfad.stat().st_mtime_ns

    einstellungen.pruefe_datenbank(pfad)

    assert pfad.stat().st_mtime_ns == vorher
    assert not (tmp_path / "health.db-wal").exists()


# ------------------------------------------------------------------
# Zusammenspiel mit dem Rechenkern
# ------------------------------------------------------------------


def test_connect_folgt_der_konfiguration(tmp_path):
    import metrics_core as core

    ziel = baue_datenbank(tmp_path / "verknuepft.db")
    einstellungen.setze_db_pfad(ziel)

    conn = core.connect()
    anzahl = conn.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0]
    conn.close()

    assert anzahl == 2
    assert core.db_exists()
