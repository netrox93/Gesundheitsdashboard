"""Tests für das Finden des Exports und die Aufbereitung von Pfadeingaben.

Der häufigste Stolperstein beim Einlesen ist der Pfad: aus Windows
kopiert kommt er in Anführungszeichen, aus dem Browser als file:///-URL.
Beides muss durchgehen, sonst steht der Nutzer vor einem "nicht
gefunden", obwohl die Datei da ist.
"""

import sys
import zipfile
from pathlib import Path

APP = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(APP))

import dateiauswahl  # noqa: E402

# ------------------------------------------------------------------
# Pfadeingaben
# ------------------------------------------------------------------


def test_leere_eingabe():
    assert dateiauswahl.bereinige_pfad("") == ""
    assert dateiauswahl.bereinige_pfad(None) == ""


def test_leerzeichen_werden_entfernt():
    assert dateiauswahl.bereinige_pfad("  C:/x/Export.zip  ") == "C:/x/Export.zip"


def test_doppelte_anfuehrungszeichen():
    """Windows' 'Als Pfad kopieren' liefert den Pfad in Anführungszeichen."""
    assert dateiauswahl.bereinige_pfad('"C:\\Users\\x\\Export.zip"') == "C:\\Users\\x\\Export.zip"


def test_einfache_anfuehrungszeichen():
    assert dateiauswahl.bereinige_pfad("'D:/a.zip'") == "D:/a.zip"


def test_file_url_windows():
    assert dateiauswahl.bereinige_pfad("file:///C:/Users/x/Export.zip") == "C:/Users/x/Export.zip"


def test_file_url_mit_leerzeichen():
    ergebnis = dateiauswahl.bereinige_pfad("file:///home/u/Export%20neu.zip")
    assert ergebnis == "/home/u/Export neu.zip"


def test_tilde_wird_aufgeloest():
    ergebnis = dateiauswahl.bereinige_pfad("~/Downloads/Export.zip")
    assert "~" not in ergebnis
    assert ergebnis.endswith("Downloads/Export.zip")


def test_normaler_pfad_bleibt_unveraendert():
    assert dateiauswahl.bereinige_pfad("C:/Daten/Export.zip") == "C:/Daten/Export.zip"


# ------------------------------------------------------------------
# Export finden
# ------------------------------------------------------------------


def baue_zip(pfad: Path) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pfad, "w") as archiv:
        archiv.writestr("apple_health_export/Export.xml", "<HealthData/>")
    return pfad


def test_findet_zip_im_suchort(tmp_path, monkeypatch):
    baue_zip(tmp_path / "Export.zip")
    monkeypatch.setattr(dateiauswahl, "_suchorte", lambda: [tmp_path])

    treffer = dateiauswahl.finde_exporte()
    assert len(treffer) == 1
    assert treffer[0]["pfad"].name == "Export.zip"
    assert treffer[0]["art"] == "ZIP-Datei"


def test_findet_entpackten_ordner(tmp_path, monkeypatch):
    ordner = tmp_path / "apple_health_export"
    ordner.mkdir()
    (ordner / "Export.xml").write_text("<HealthData/>", encoding="utf-8")
    monkeypatch.setattr(dateiauswahl, "_suchorte", lambda: [tmp_path])

    treffer = dateiauswahl.finde_exporte()
    assert len(treffer) == 1
    assert treffer[0]["art"] == "Ordner"


def test_ordner_ohne_export_xml_zaehlt_nicht(tmp_path, monkeypatch):
    """Ein leerer Ordner mit passendem Namen ist kein Export."""
    (tmp_path / "apple_health_export").mkdir()
    monkeypatch.setattr(dateiauswahl, "_suchorte", lambda: [tmp_path])

    assert dateiauswahl.finde_exporte() == []


def test_neueste_zuerst(tmp_path, monkeypatch):
    import os
    import time

    alt = baue_zip(tmp_path / "alt_export.zip")
    neu = baue_zip(tmp_path / "neu_export.zip")

    frueher = time.time() - 100_000
    os.utime(alt, (frueher, frueher))

    monkeypatch.setattr(dateiauswahl, "_suchorte", lambda: [tmp_path])

    treffer = dateiauswahl.finde_exporte()
    assert [t["pfad"].name for t in treffer] == [neu.name, alt.name]


def test_doppelte_treffer_werden_zusammengefasst(tmp_path, monkeypatch):
    """Derselbe Ordner kann über mehrere Suchorte erreichbar sein."""
    baue_zip(tmp_path / "Export.zip")
    monkeypatch.setattr(dateiauswahl, "_suchorte", lambda: [tmp_path, tmp_path])

    assert len(dateiauswahl.finde_exporte()) == 1


def test_treffer_werden_begrenzt(tmp_path, monkeypatch):
    for nummer in range(12):
        baue_zip(tmp_path / f"export_{nummer}.zip")
    monkeypatch.setattr(dateiauswahl, "_suchorte", lambda: [tmp_path])

    assert len(dateiauswahl.finde_exporte(max_treffer=5)) == 5


def test_unlesbarer_suchort_bricht_nicht_ab(tmp_path, monkeypatch):
    """Ein nicht verbundenes Netzlaufwerk darf die Suche nicht sprengen."""
    baue_zip(tmp_path / "Export.zip")
    monkeypatch.setattr(dateiauswahl, "_suchorte", lambda: [Path("Z:/gibtsnicht"), tmp_path])

    assert len(dateiauswahl.finde_exporte()) == 1


def test_beschreibung_enthaelt_groesse_und_datum(tmp_path, monkeypatch):
    baue_zip(tmp_path / "Export.zip")
    monkeypatch.setattr(dateiauswahl, "_suchorte", lambda: [tmp_path])

    eintrag = dateiauswahl.finde_exporte()[0]
    assert eintrag["groesse_mb"] >= 0
    assert eintrag["geaendert"] is not None


# ------------------------------------------------------------------
# Datei-Dialog
# ------------------------------------------------------------------


def test_dialog_ohne_oberflaeche_nicht_verfuegbar(monkeypatch):
    monkeypatch.setattr(dateiauswahl.os, "name", "posix")
    monkeypatch.delenv("DISPLAY", raising=False)

    assert not dateiauswahl.dialog_verfuegbar()


def test_waehle_datei_ohne_dialog_gibt_leer(monkeypatch):
    monkeypatch.setattr(dateiauswahl, "dialog_verfuegbar", lambda: False)
    assert dateiauswahl.waehle_datei() == ""
