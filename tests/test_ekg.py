"""Tests für das Einlesen und Vermessen der EKG-Daten.

Arbeiten mit synthetisch erzeugten Signalen bekannter Frequenz, damit
sich die Messung gegen einen bekannten Sollwert prüfen lässt.
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pytest

APP = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(APP))

import ecg  # noqa: E402

MESSRATE = 512.0


def kunst_ekg(
    hf: float,
    dauer_s: float = 30.0,
    amplitude: float = 1000.0,
    polaritaet: int = 1,
    rauschen: float = 0.0,
    basislinie: float = 0.0,
) -> np.ndarray:
    """Synthetisches EKG mit definierter Herzfrequenz.

    Bewusst vereinfacht: eine schmale R-Zacke, eine gegenläufige S-Zacke
    und eine breite T-Welle - genug, um die Schlagerkennung zu prüfen.
    """
    n = int(dauer_s * MESSRATE)
    signal = np.zeros(n, dtype=np.float64)
    rr = 60.0 / hf

    for schlag in np.arange(rr / 2, dauer_s, rr):
        mitte = int(schlag * MESSRATE)

        r_breite = int(0.012 * MESSRATE)
        for i in range(-r_breite, r_breite + 1):
            if 0 <= mitte + i < n:
                signal[mitte + i] += polaritaet * amplitude * (1 - abs(i) / (r_breite + 1))

        s_pos = mitte + int(0.03 * MESSRATE)
        s_breite = int(0.02 * MESSRATE)
        for i in range(-s_breite, s_breite + 1):
            if 0 <= s_pos + i < n:
                signal[s_pos + i] -= polaritaet * amplitude * 0.35 * (1 - abs(i) / (s_breite + 1))

        t_pos = mitte + int(0.22 * MESSRATE)
        t_breite = int(0.07 * MESSRATE)
        for i in range(-t_breite, t_breite + 1):
            if 0 <= t_pos + i < n:
                signal[t_pos + i] += (
                    polaritaet * amplitude * 0.22 * np.cos(np.pi * i / (2 * t_breite))
                )

    if basislinie:
        signal += basislinie * np.sin(2 * np.pi * 0.15 * np.arange(n) / MESSRATE)
    if rauschen:
        signal += np.random.default_rng(1).normal(0, rauschen, n)

    return signal.astype(np.float32)


def messe(signal: np.ndarray) -> dict:
    return ecg.vermesse({"signal": signal, "messrate": MESSRATE})


# ------------------------------------------------------------------
# Schlagerkennung
# ------------------------------------------------------------------


@pytest.mark.parametrize("hf", [50, 60, 75, 100, 120])
def test_herzfrequenz_wird_getroffen(hf):
    ergebnis = messe(kunst_ekg(hf))
    assert ergebnis["hf_mittel"] == pytest.approx(hf, rel=0.05)


def test_schlagzahl_passt_zur_dauer():
    ergebnis = messe(kunst_ekg(60, dauer_s=30))
    assert 28 <= ergebnis["schlaege"] <= 32


def test_negative_polaritaet_wird_erkannt():
    """Bei nach unten gerichteter Hauptzacke muss die Frequenz trotzdem
    stimmen - sonst springt die Erkennung zwischen R und S."""
    ergebnis = messe(kunst_ekg(70, polaritaet=-1))
    assert ergebnis["hf_mittel"] == pytest.approx(70, rel=0.05)


def test_polaritaet_bleibt_ueber_die_aufzeichnung_gleich():
    """Der eigentliche Fehlerfall: markiert die Erkennung mal die R-, mal
    die S-Zacke, schwanken die Abstände stark, obwohl der Rhythmus
    vollkommen regelmässig ist."""
    ergebnis = messe(kunst_ekg(70, polaritaet=-1))
    assert ergebnis["unregelmaessigkeit"] < 5


def test_basislinienschwankung_stoert_nicht():
    ergebnis = messe(kunst_ekg(65, basislinie=400))
    assert ergebnis["hf_mittel"] == pytest.approx(65, rel=0.06)


def test_regelmaessiges_signal_hat_geringe_schwankung():
    ergebnis = messe(kunst_ekg(70))
    assert ergebnis["unregelmaessigkeit"] < 3
    assert ergebnis["qualitaet"] == "gut"


def test_zu_kurzes_signal_gibt_keine_werte():
    ergebnis = messe(np.zeros(100, dtype=np.float32))
    assert ergebnis["hf_mittel"] is None
    assert ergebnis["qualitaet"] == "nicht auswertbar"


def test_reines_rauschen_liefert_keine_plausible_frequenz():
    rauschen = np.random.default_rng(0).normal(0, 50, int(30 * MESSRATE)).astype(np.float32)
    ergebnis = messe(rauschen)
    # Entweder gar nicht auswertbar oder als unzuverlässig gekennzeichnet
    assert ergebnis["hf_mittel"] is None or ergebnis["qualitaet"] != "gut"


# ------------------------------------------------------------------
# Filter
# ------------------------------------------------------------------


def test_filter_entfernt_basisliniendrift():
    signal = kunst_ekg(60, basislinie=800)
    gefiltert = ecg.filtere(signal, MESSRATE)
    # Nach dem Hochpass sollte das Signal um null pendeln
    assert abs(float(np.mean(gefiltert))) < abs(float(np.mean(signal))) + 1
    assert abs(float(np.mean(gefiltert))) < 20


def test_filter_bei_zu_kurzem_signal_unveraendert():
    kurz = np.ones(10, dtype=np.float32)
    assert np.array_equal(ecg.filtere(kurz, MESSRATE), kurz)


# ------------------------------------------------------------------
# CSV einlesen
# ------------------------------------------------------------------


CSV_INHALT = """Name,Max Mustermann
Geburtstag,"01.01.1990"
Aufzeichnungsdatum,2025-03-01 10:15:00 +0100
Klassifizierung,Sinusrhythmus
Symptome,Ohne
Softwareversion,2.0
Gerät,"Watch6,7"
Messrate,512 Hertz


Ableitung,Ableitung I
Einheit,µV

57,992
62,414
-66,502
"""


def test_csv_liest_metadaten(tmp_path):
    pfad = tmp_path / "ecg_test.csv"
    pfad.write_text(CSV_INHALT, encoding="utf-8")

    meta = ecg.lies_csv(pfad)
    assert meta["klassifikation"] == "Sinusrhythmus"
    assert meta["messrate"] == 512.0
    assert meta["zeitpunkt"].strftime("%Y-%m-%d %H:%M") == "2025-03-01 10:15"


def test_csv_uebernimmt_keinen_namen(tmp_path):
    """Personenname und Geburtsdatum haben in der Datenbank nichts zu suchen."""
    pfad = tmp_path / "ecg_test.csv"
    pfad.write_text(CSV_INHALT, encoding="utf-8")

    meta = ecg.lies_csv(pfad)
    assert "Mustermann" not in str(meta)
    assert "1990" not in str(meta.get("aufnahme", ""))


def test_csv_liest_messwerte_mit_dezimalkomma(tmp_path):
    pfad = tmp_path / "ecg_test.csv"
    pfad.write_text(CSV_INHALT, encoding="utf-8")

    meta = ecg.lies_csv(pfad)
    assert len(meta["signal"]) == 3
    assert meta["signal"][0] == pytest.approx(57.992)
    assert meta["signal"][2] == pytest.approx(-66.502)


# ------------------------------------------------------------------
# Speichern
# ------------------------------------------------------------------


def test_signal_ueberlebt_packen_und_entpacken():
    original = kunst_ekg(70)
    zurueck = ecg.entpacke_signal(ecg.packe_signal(original))
    assert np.allclose(original, zurueck)


def test_import_ist_wiederholbar(tmp_path):
    ordner = tmp_path / "ekg"
    ordner.mkdir()
    (ordner / "ecg_1.csv").write_text(CSV_INHALT, encoding="utf-8")

    conn = sqlite3.connect(tmp_path / "test.db")
    erst = ecg.importiere(ordner, conn)
    zweit = ecg.importiere(ordner, conn)
    conn.close()

    assert erst["neu"] == 1
    assert zweit["neu"] == 0  # Duplikat wird übersprungen
