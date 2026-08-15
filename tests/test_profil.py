"""Tests für Profil und die alters-/geschlechtsabhängigen Referenzbereiche.

Wichtig für die Weitergabe an andere Personen: die Bereiche müssen sich
tatsächlich am jeweiligen Profil ausrichten und dürfen ohne Profil keine
falschen Werte vortäuschen.
"""

import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

APP = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(APP))

import profil as profil_modul  # noqa: E402
from reference_ranges import (  # noqa: E402
    METRICS,
    referenz_text,
    referenzbereich,
)

ME_ZEILE = (
    '<Me HKCharacteristicTypeIdentifierDateOfBirth="1985-06-15" '
    'HKCharacteristicTypeIdentifierBiologicalSex="HKBiologicalSexFemale" '
    'HKCharacteristicTypeIdentifierBloodType="HKBloodTypeNotSet"/>'
)


def export_datei(tmp_path: Path, me: str = ME_ZEILE) -> Path:
    pfad = tmp_path / "Export.xml"
    pfad.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<HealthData locale="de_DE">\n'
        f'<ExportDate value="2026-01-01 10:00:00 +0100"/>\n{me}\n</HealthData>',
        encoding="utf-8",
    )
    return pfad


# ------------------------------------------------------------------
# Profil aus dem Export
# ------------------------------------------------------------------


def test_liest_geburtsdatum_und_geschlecht(tmp_path):
    ergebnis = profil_modul.lies_aus_export(export_datei(tmp_path))
    assert ergebnis["geburtsdatum"] == "1985-06-15"
    assert ergebnis["geschlecht"] == "w"


def test_maennlich_wird_erkannt(tmp_path):
    me = ME_ZEILE.replace("HKBiologicalSexFemale", "HKBiologicalSexMale")
    assert profil_modul.lies_aus_export(export_datei(tmp_path, me))["geschlecht"] == "m"


def test_nicht_gesetztes_geschlecht_bleibt_leer(tmp_path):
    me = ME_ZEILE.replace("HKBiologicalSexFemale", "HKBiologicalSexNotSet")
    ergebnis = profil_modul.lies_aus_export(export_datei(tmp_path, me))
    assert "geschlecht" not in ergebnis
    assert ergebnis["geburtsdatum"] == "1985-06-15"


def test_fehlendes_me_element_gibt_leeres_profil(tmp_path):
    pfad = tmp_path / "Export.xml"
    pfad.write_text("<HealthData></HealthData>", encoding="utf-8")
    assert profil_modul.lies_aus_export(pfad) == {}


# ------------------------------------------------------------------
# Alter
# ------------------------------------------------------------------


def test_alter_vor_dem_geburtstag():
    assert profil_modul.alter_am("1990-08-23", date(2026, 8, 22)) == 35


def test_alter_am_geburtstag():
    assert profil_modul.alter_am("1990-08-23", date(2026, 8, 23)) == 36


def test_alter_akzeptiert_deutsches_format():
    assert profil_modul.alter_am("04.11.1988", date(2026, 12, 1)) == 38


def test_alter_bei_unlesbarem_datum():
    assert profil_modul.alter_am("keine Ahnung") is None


# ------------------------------------------------------------------
# Speichern
# ------------------------------------------------------------------


def test_profil_speichern_und_laden(tmp_path):
    conn = sqlite3.connect(tmp_path / "p.db")
    profil_modul.speichere(conn, "1985-06-15", "w")
    geladen = profil_modul.lade(conn)
    conn.close()

    assert geladen["geburtsdatum"] == "1985-06-15"
    assert geladen["geschlecht"] == "w"
    assert geladen["alter"] == profil_modul.alter_am("1985-06-15")


def test_profil_wird_ueberschrieben_statt_dupliziert(tmp_path):
    conn = sqlite3.connect(tmp_path / "p.db")
    profil_modul.speichere(conn, "1985-06-15", "w")
    profil_modul.speichere(conn, "1990-01-01", "m")

    anzahl = conn.execute("SELECT COUNT(*) FROM profil").fetchone()[0]
    geladen = profil_modul.lade(conn)
    conn.close()

    assert anzahl == 1
    assert geladen["geburtsdatum"] == "1990-01-01"


def test_leere_datenbank_gibt_leeres_profil(tmp_path):
    conn = sqlite3.connect(tmp_path / "p.db")
    assert profil_modul.lade(conn) == {}
    conn.close()


# ------------------------------------------------------------------
# Referenzbereiche nach Alter und Geschlecht
# ------------------------------------------------------------------


def test_vo2max_sinkt_mit_dem_alter():
    jung = referenzbereich("vo2max", {"geschlecht": "m", "alter": 25})["bereich"]
    alt = referenzbereich("vo2max", {"geschlecht": "m", "alter": 65})["bereich"]
    assert jung[0] > alt[0] and jung[1] > alt[1]


def test_vo2max_unterscheidet_geschlecht():
    mann = referenzbereich("vo2max", {"geschlecht": "m", "alter": 40})["bereich"]
    frau = referenzbereich("vo2max", {"geschlecht": "w", "alter": 40})["bereich"]
    assert mann != frau
    assert mann[0] > frau[0]


def test_vo2max_ohne_geschlecht_umspannt_beide():
    """Ohne eindeutige Angabe darf niemand faelschlich als auffaellig gelten."""
    divers = referenzbereich("vo2max", {"geschlecht": "divers", "alter": 40})["bereich"]
    mann = referenzbereich("vo2max", {"geschlecht": "m", "alter": 40})["bereich"]
    frau = referenzbereich("vo2max", {"geschlecht": "w", "alter": 40})["bereich"]

    assert divers[0] <= min(mann[0], frau[0])
    assert divers[1] >= max(mann[1], frau[1])


def test_vo2max_ohne_profil_kein_bereich():
    referenz = referenzbereich("vo2max", {})
    assert referenz["bereich"] is None
    assert referenz["hinweis"]


def test_schlafdauer_aeltere_bekommen_engeren_bereich():
    jung = referenzbereich("sleep_hours", {"alter": 30})["bereich"]
    alt = referenzbereich("sleep_hours", {"alter": 70})["bereich"]
    assert jung == (7, 9)
    assert alt == (7, 8)


def test_schlafdauer_jugendliche():
    assert referenzbereich("sleep_hours", {"alter": 16})["bereich"] == (8, 10)


def test_schritte_ab_60_niedriger():
    jung = referenzbereich("steps", {"alter": 40})["bereich"]
    alt = referenzbereich("steps", {"alter": 65})["bereich"]
    assert jung == (8000, 10000)
    assert alt == (6000, 8000)


@pytest.mark.parametrize("key", ["resting_hr", "respiratory_rate", "spo2", "exercise_min"])
def test_altersunabhaengige_bereiche_bleiben_konstant(key):
    jung = referenzbereich(key, {"geschlecht": "m", "alter": 20})["bereich"]
    alt = referenzbereich(key, {"geschlecht": "w", "alter": 80})["bereich"]
    ohne = referenzbereich(key, {})["bereich"]
    assert jung == alt == ohne


def test_hrv_bleibt_ohne_bereich():
    """Für HRV ist bewusst kein Populationsbereich hinterlegt - das darf
    sich auch mit Profil nicht ändern."""
    assert referenzbereich("hrv", {"geschlecht": "m", "alter": 30})["bereich"] is None


def test_referenz_text_ohne_bereich():
    assert referenz_text("hrv", {"alter": 30}) == "nicht anwendbar"


def test_referenz_text_mit_einheit():
    assert referenz_text("resting_hr", {"alter": 30}) == "60-100 /min"


def test_alle_kennzahlen_liefern_gueltige_struktur():
    """Jede Kennzahl muss mit und ohne Profil eine Antwort liefern."""
    for key in METRICS:
        for p in ({}, {"geschlecht": "w", "alter": 55}):
            referenz = referenzbereich(key, p)
            assert set(referenz) == {"bereich", "label", "angepasst", "hinweis"}
            if referenz["bereich"]:
                assert referenz["bereich"][0] < referenz["bereich"][1]
