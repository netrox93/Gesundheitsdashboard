"""Tests für GPX-Einlesen, Streckenberechnung und Datenschutz-Kürzung.

Arbeitet mit erzeugten GPX-Dateien im Apple-Format. Die Strecken sind so
gewählt, dass sich das Ergebnis von Hand nachrechnen lässt.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

APP = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(APP))

import routen  # noqa: E402

# 0,001 Grad Breite entsprechen rund 111,2 m
GRAD_LAT_M = 111195.0


def gpx_datei(pfad: Path, punkte, mit_extensions=False) -> Path:
    """GPX im Apple-Format erzeugen."""
    zeilen = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="Apple Health Export" '
        'xmlns="http://www.topografix.com/GPX/1/1">',
        "<trk><name>Test</name><trkseg>",
    ]
    for p in punkte:
        zeilen.append(f'<trkpt lat="{p["lat"]}" lon="{p["lon"]}">')
        if p.get("ele") is not None:
            zeilen.append(f"<ele>{p['ele']}</ele>")
        if p.get("time"):
            zeilen.append(f"<time>{p['time']}</time>")
        if mit_extensions:
            zeilen.append(
                "<extensions>"
                f"<speed>{p.get('speed', 5.0)}</speed>"
                f"<hAcc>{p.get('hAcc', 5.0)}</hAcc>"
                "</extensions>"
            )
        zeilen.append("</trkpt>")
    zeilen += ["</trkseg></trk></gpx>"]

    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("\n".join(zeilen), encoding="utf-8")
    return pfad


def gerade_strecke(anzahl=5, schritt=0.001, hoehe_start=100.0, steigung=0.0):
    """Punkte auf einem Längengrad, je `schritt` Grad auseinander."""
    return [
        {
            "lat": 53.5 + i * schritt,
            "lon": 10.0,
            "ele": hoehe_start + i * steigung,
            "time": f"2025-06-01T10:{i:02d}:00Z",
        }
        for i in range(anzahl)
    ]


# ------------------------------------------------------------------
# Entfernung
# ------------------------------------------------------------------


def test_entfernung_null():
    assert routen.entfernung_m(53.5, 10.0, 53.5, 10.0) == pytest.approx(0.0)


def test_entfernung_ein_tausendstel_grad():
    abstand = routen.entfernung_m(53.5, 10.0, 53.501, 10.0)
    assert abstand == pytest.approx(111.2, abs=1.0)


def test_entfernung_ist_symmetrisch():
    hin = routen.entfernung_m(53.5, 10.0, 53.6, 10.1)
    zurueck = routen.entfernung_m(53.6, 10.1, 53.5, 10.0)
    assert hin == pytest.approx(zurueck)


def test_entfernung_hamburg_berlin():
    """Bekannte Strecke als Plausibilitaetspruefung: rund 255 km."""
    abstand = routen.entfernung_m(53.5511, 9.9937, 52.5200, 13.4050)
    assert 250_000 < abstand < 260_000


# ------------------------------------------------------------------
# GPX lesen
# ------------------------------------------------------------------


def test_liest_alle_punkte(tmp_path):
    pfad = gpx_datei(tmp_path / "a.gpx", gerade_strecke(5))
    assert len(routen.lies_gpx(pfad)["punkte"]) == 5


def test_liest_hoehe_und_zeit(tmp_path):
    pfad = gpx_datei(tmp_path / "a.gpx", gerade_strecke(3))
    punkt = routen.lies_gpx(pfad)["punkte"][0]

    assert punkt["hoehe"] == pytest.approx(100.0)
    assert punkt["zeit"] is not None
    assert punkt["zeit"].year == 2025


def test_liest_extensions(tmp_path):
    """Apple legt Tempo und GPS-Genauigkeit in die Extensions."""
    pfad = gpx_datei(tmp_path / "a.gpx", gerade_strecke(3), mit_extensions=True)
    punkt = routen.lies_gpx(pfad)["punkte"][0]

    assert punkt["tempo_ms"] == pytest.approx(5.0)
    assert punkt["genauigkeit_m"] == pytest.approx(5.0)


def test_datei_ohne_punkte(tmp_path):
    pfad = gpx_datei(tmp_path / "leer.gpx", [])
    assert routen.lies_gpx(pfad)["punkte"] == []


def test_kaputte_datei_wirft_klaren_fehler(tmp_path):
    pfad = tmp_path / "kaputt.gpx"
    pfad.write_text("<gpx><trkseg>", encoding="utf-8")

    with pytest.raises(ValueError, match="nicht lesbar"):
        routen.lies_gpx(pfad)


# ------------------------------------------------------------------
# Vermessung
# ------------------------------------------------------------------


def test_distanz_gerade_strecke(tmp_path):
    """4 Abschnitte zu je rund 111 m ergeben etwa 445 m."""
    pfad = gpx_datei(tmp_path / "a.gpx", gerade_strecke(5))
    werte = routen.vermesse(routen.lies_gpx(pfad)["punkte"])

    assert werte["distanz_km"] == pytest.approx(4 * GRAD_LAT_M / 1000 / 1000, rel=0.01)


def test_dauer_aus_zeitstempeln(tmp_path):
    pfad = gpx_datei(tmp_path / "a.gpx", gerade_strecke(5))
    werte = routen.vermesse(routen.lies_gpx(pfad)["punkte"])
    assert werte["dauer_min"] == pytest.approx(4.0)


def test_grenzen_werden_erfasst(tmp_path):
    pfad = gpx_datei(tmp_path / "a.gpx", gerade_strecke(5))
    werte = routen.vermesse(routen.lies_gpx(pfad)["punkte"])

    assert werte["lat_min"] == pytest.approx(53.5)
    assert werte["lat_max"] == pytest.approx(53.504)
    assert werte["lon_min"] == werte["lon_max"] == pytest.approx(10.0)


def test_aufstieg_wird_summiert(tmp_path):
    pfad = gpx_datei(tmp_path / "a.gpx", gerade_strecke(5, steigung=10.0))
    werte = routen.vermesse(routen.lies_gpx(pfad)["punkte"])

    assert werte["aufstieg_m"] == pytest.approx(40.0)
    assert werte["abstieg_m"] == pytest.approx(0.0)


def test_hoehenrauschen_wird_nicht_als_aufstieg_gezaehlt(tmp_path):
    """Ohne Schwelle summieren sich schwankende Hoehenwerte zu
    Hoehenmetern auf, die nie gefahren wurden."""
    punkte = gerade_strecke(20)
    for i, punkt in enumerate(punkte):
        punkt["ele"] = 100.0 + (1.5 if i % 2 else -1.5)

    pfad = gpx_datei(tmp_path / "a.gpx", punkte)
    werte = routen.vermesse(routen.lies_gpx(pfad)["punkte"])

    assert werte["aufstieg_m"] == pytest.approx(0.0)


def test_echter_anstieg_ueberwindet_die_schwelle(tmp_path):
    punkte = gerade_strecke(4, steigung=25.0)
    pfad = gpx_datei(tmp_path / "a.gpx", punkte)
    werte = routen.vermesse(routen.lies_gpx(pfad)["punkte"])

    assert werte["aufstieg_m"] == pytest.approx(75.0)


def test_ungenaue_punkte_werden_verworfen(tmp_path):
    """Ein Ausreisser mit schlechter GPS-Genauigkeit darf die Distanz
    nicht in die Hoehe treiben."""
    punkte = gerade_strecke(5)
    punkte[2]["lat"] = 54.5  # rund 110 km daneben
    punkte[2]["hAcc"] = 500.0

    pfad = gpx_datei(tmp_path / "a.gpx", punkte, mit_extensions=True)
    werte = routen.vermesse(routen.lies_gpx(pfad)["punkte"])

    assert werte["verworfen"] == 1
    assert werte["distanz_km"] < 1.0


def test_zeitsprung_wird_uebersprungen(tmp_path):
    """Ein Sprung mit unmoeglicher Geschwindigkeit ist ein Messfehler."""
    punkte = gerade_strecke(4)
    punkte[2]["lat"] = 54.5  # 110 km in einer Minute

    pfad = gpx_datei(tmp_path / "a.gpx", punkte)
    werte = routen.vermesse(routen.lies_gpx(pfad)["punkte"])

    assert werte["distanz_km"] < 1.0


def test_leere_punktliste():
    werte = routen.vermesse([])
    assert werte["punkte"] == 0
    assert werte["distanz_km"] == 0.0
    assert werte["lat_min"] is None


# ------------------------------------------------------------------
# Datenschutz
# ------------------------------------------------------------------


def test_kuerzt_start_und_ende(tmp_path):
    """Die ersten und letzten Punkte am Wohnort verschwinden."""
    punkte = routen.lies_gpx(gpx_datei(tmp_path / "a.gpx", gerade_strecke(9)))["punkte"]
    heimat = (53.5, 10.0)

    gekuerzt = routen.kuerze_um_heimat(punkte, heimat, radius_m=250)

    assert len(gekuerzt) < len(punkte)
    assert routen.entfernung_m(gekuerzt[0]["lat"], gekuerzt[0]["lon"], *heimat) > 250


def test_kuerzt_nicht_in_der_mitte(tmp_path):
    """Wer am Wohnort vorbeifaehrt, soll keine zerrissene Route bekommen."""
    punkte = routen.lies_gpx(gpx_datei(tmp_path / "a.gpx", gerade_strecke(9)))["punkte"]
    # Heimat in der Mitte der Strecke
    heimat = (punkte[4]["lat"], punkte[4]["lon"])

    gekuerzt = routen.kuerze_um_heimat(punkte, heimat, radius_m=200)

    assert len(gekuerzt) == len(punkte)


def test_ohne_heimat_bleibt_alles(tmp_path):
    punkte = routen.lies_gpx(gpx_datei(tmp_path / "a.gpx", gerade_strecke(5)))["punkte"]
    assert routen.kuerze_um_heimat(punkte, None) == punkte


def test_route_komplett_im_radius_wird_leer(tmp_path):
    punkte = routen.lies_gpx(gpx_datei(tmp_path / "a.gpx", gerade_strecke(3)))["punkte"]
    assert routen.kuerze_um_heimat(punkte, (53.5, 10.0), radius_m=100_000) == []


# ------------------------------------------------------------------
# Import
# ------------------------------------------------------------------


def leere_datenbank(pfad: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(pfad)
    conn.executescript((APP / "schema.sql").read_text(encoding="utf-8"))
    return conn


def test_import_legt_route_und_punkte_an(tmp_path):
    ordner = tmp_path / "routes"
    gpx_datei(ordner / "route_1.gpx", gerade_strecke(5))

    conn = leere_datenbank(tmp_path / "test.db")
    zaehler = routen.importiere(ordner, conn)

    assert zaehler["neu"] == 1
    assert zaehler["punkte"] == 5
    assert conn.execute("SELECT COUNT(*) FROM routen_punkte").fetchone()[0] == 5
    conn.close()


def test_import_ist_wiederholbar(tmp_path):
    ordner = tmp_path / "routes"
    gpx_datei(ordner / "route_1.gpx", gerade_strecke(5))

    conn = leere_datenbank(tmp_path / "test.db")
    routen.importiere(ordner, conn)
    zweiter = routen.importiere(ordner, conn)
    conn.close()

    assert zweiter["neu"] == 0
    assert zweiter["uebersprungen"] == 1


def test_import_verknuepft_mit_workout(tmp_path):
    ordner = tmp_path / "routes"
    gpx_datei(ordner / "route_1.gpx", gerade_strecke(5))

    conn = leere_datenbank(tmp_path / "test.db")
    conn.execute(
        "INSERT INTO workouts (activity_type, source_name, start_date, end_date) "
        "VALUES ('HKWorkoutActivityTypeCycling', 'Watch', "
        "'2025-06-01 10:00:05 +0000', '2025-06-01 10:30:00 +0000')"
    )
    conn.commit()

    routen.importiere(ordner, conn)
    verknuepft = conn.execute("SELECT workout_id FROM routen").fetchone()[0]
    conn.close()

    assert verknuepft is not None


def test_import_ohne_passendes_workout(tmp_path):
    ordner = tmp_path / "routes"
    gpx_datei(ordner / "route_1.gpx", gerade_strecke(5))

    conn = leere_datenbank(tmp_path / "test.db")
    conn.execute(
        "INSERT INTO workouts (activity_type, source_name, start_date, end_date) "
        "VALUES ('HKWorkoutActivityTypeCycling', 'Watch', "
        "'2024-01-01 08:00:00 +0000', '2024-01-01 09:00:00 +0000')"
    )
    conn.commit()

    routen.importiere(ordner, conn)
    verknuepft = conn.execute("SELECT workout_id FROM routen").fetchone()[0]
    conn.close()

    assert verknuepft is None


def test_kaputte_datei_stoppt_den_import_nicht(tmp_path):
    ordner = tmp_path / "routes"
    gpx_datei(ordner / "gut.gpx", gerade_strecke(5))
    (ordner / "kaputt.gpx").write_text("<gpx><trkseg>", encoding="utf-8")

    conn = leere_datenbank(tmp_path / "test.db")
    zaehler = routen.importiere(ordner, conn)
    conn.close()

    assert zaehler["neu"] == 1
    assert zaehler["uebersprungen"] == 1


# ------------------------------------------------------------------
# GPX schreiben
# ------------------------------------------------------------------


def test_gpx_ausgabe_ist_wieder_lesbar(tmp_path):
    """Was das Projekt schreibt, muss es auch wieder einlesen koennen."""
    punkte = routen.lies_gpx(gpx_datei(tmp_path / "a.gpx", gerade_strecke(5)))["punkte"]

    ziel = tmp_path / "raus.gpx"
    ziel.write_text(routen.als_gpx(punkte, "Testtour"), encoding="utf-8")

    zurueck = routen.lies_gpx(ziel)["punkte"]
    assert len(zurueck) == len(punkte)
    assert zurueck[0]["lat"] == pytest.approx(punkte[0]["lat"])


def test_flacher_stetiger_anstieg_geht_vollstaendig_ein(tmp_path):
    """Kleine Schritte unterhalb der Schwelle duerfen nicht verloren
    gehen - sonst faellt ein langer flacher Anstieg unter den Tisch."""
    punkte = gerade_strecke(21, steigung=2.0)  # 20 x 2 m = 40 m
    pfad = gpx_datei(tmp_path / "a.gpx", punkte)
    werte = routen.vermesse(routen.lies_gpx(pfad)["punkte"])

    assert werte["aufstieg_m"] == pytest.approx(40.0, abs=6.0)
