"""Bereitet die Inhalte für den PDF-Bericht auf.

Getrennt vom Layout in `export_pdf.py`, damit die Auswahl- und
Formulierungslogik testbar bleibt.
"""

from pathlib import Path

import metrics_core as core
import pandas as pd
import profil as profil_modul
from reference_ranges import METRICS, SCHWELLE_STANDARD, referenz_text, referenzbereich

# Nur diese Kennzahlen erscheinen in der Tabelle "Auffällige Phasen".
#
# Aktivitätsgrössen (Schritte, Trainingsminuten, VO2max) sind bewusst
# ausgenommen: Ein Ausschlag nach oben bedeutet dort eine Wanderung oder
# eine Trainingswoche, nicht einen Befund. In einer Auffälligkeitsliste
# für den Arzt wäre das nur Rauschen, das die physiologischen Signale
# überdeckt.
PHYSIO_METRIKEN = {
    "resting_hr",
    "hrv",
    "respiratory_rate",
    "spo2",
    "sleep_hours",
    "walking_hr",
    "hr_recovery",
    "deep_share",
    "rem_share",
}


def _lage(df: pd.DataFrame, spec: dict, bereich=None) -> str:
    """Beschreibt, wie die Werte zum Populations-Referenzbereich liegen."""
    bereich = bereich if bereich is not None else spec.get("population")
    if not bereich:
        return "kein Populationsbereich anwendbar"

    low, high = bereich
    innerhalb = df["value"].between(low, high).mean() * 100
    darunter = (df["value"] < low).mean() * 100
    darueber = (df["value"] > high).mean() * 100

    if innerhalb >= 80:
        return f"überwiegend im Referenzbereich ({innerhalb:.0f} %)"
    if darunter >= 50:
        zusatz = (
            " (bei Ausdauertrainierten erwartbar)" if spec["richtung"] == "niedriger_besser" else ""
        )
        return f"überwiegend unterhalb ({darunter:.0f} %){zusatz}"
    if darueber >= 50:
        zusatz = " (günstige Richtung)" if spec["richtung"] == "hoeher_besser" else ""
        return f"überwiegend oberhalb ({darueber:.0f} %){zusatz}"
    return f"{innerhalb:.0f} % innerhalb, {darunter:.0f} % darunter, {darueber:.0f} % darüber"


def _trendtext(df: pd.DataFrame, key: str) -> str:
    """Beobachtender Satz zum Verlauf - ohne Bewertung."""
    spec = METRICS[key]
    teile = []

    # Trendvergleich: erstes gegen letztes Drittel
    if len(df) >= 60:
        drittel = len(df) // 3
        anfang = df["value"].iloc[:drittel].mean()
        ende = df["value"].iloc[-drittel:].mean()
        differenz = ende - anfang
        if abs(differenz) > 0.02 * abs(anfang) and abs(anfang) > 1e-9:
            richtung = "höher" if differenz > 0 else "niedriger"
            teile.append(
                f"Im letzten Drittel des Zeitraums liegt der Mittelwert "
                f"{abs(differenz):.1f} {spec['einheit']} {richtung} als im ersten "
                f"({core.format_value(key, anfang)} zu {core.format_value(key, ende)})."
            )
        else:
            teile.append("Über den Zeitraum zeigt sich kein wesentlicher Trend.")

    warnung = core.coverage_warning(df, min_tage=30)
    if warnung:
        teile.append(warnung)

    return " ".join(teile)


def _phasentabelle(key: str, serien: list) -> list:
    """Auffällige Phasen einer Kennzahl als Tabellenzeilen.

    Die letzte Spalte bleibt leer - dort trägt der Nutzer von Hand ein,
    was in dem Zeitraum los war. Genau diese Zuordnung kann die Auswertung
    selbst nicht leisten, sie ist aber der interessanteste Teil.
    """
    eigene = [s for s in serien if s["key"] == key]
    return [
        {
            "zeitraum": f"{s['start']:%d.%m.} - {s['ende']:%d.%m.%Y}",
            "tage": f"{s['tage']}",
            "richtung": s["richtung"],
            "mittel": core.format_value(key, s["mittel"]),
            "baseline": core.format_value(key, s["baseline"]),
            "abweichung": f"{s['max_z']:.1f} SD",
        }
        for s in eigene
    ]


def sammle(keys: list, monate: int, db_path: Path = None) -> dict:
    """Alle Inhalte für den Bericht einsammeln."""
    conn = core.connect(db_path) if db_path else core.connect()
    profil = profil_modul.lade(conn)

    _, ende = core.data_range(conn)
    if ende is None:
        raise RuntimeError("Keine Tagesdaten vorhanden - erst build_daily.py ausführen.")

    beginn = pd.Timestamp(ende) - pd.DateOffset(months=monate)

    uebersicht = []
    details = []
    alle_serien = []
    messwerte_im_zeitraum = 0

    for key in keys:
        spec = METRICS[key]
        roh = core.load_metric(conn, key)
        if roh.empty:
            continue

        # Baseline auf der vollen Reihe rechnen, damit der Korridor am
        # Anfang des Berichtszeitraums bereits vorliegt
        voll = core.add_rolling_means(core.add_baseline(roh))
        df = core.filter_range(voll, beginn, ende)
        if df.empty:
            continue

        messwerte_im_zeitraum += len(df)

        for serie in core.find_runs(df, SCHWELLE_STANDARD):
            serie["key"] = key
            serie["label"] = spec["label"]
            alle_serien.append(serie)

        bereich = referenzbereich(key, profil)["bereich"]
        referenz = referenz_text(key, profil)

        uebersicht.append(
            {
                "label": spec["label"],
                "mittel": core.format_value(key, df["value"].mean()),
                "spanne": (
                    f"{core.format_value(key, df['value'].quantile(0.05))} - "
                    f"{core.format_value(key, df['value'].quantile(0.95))}"
                ),
                "referenz": referenz,
                "lage": _lage(df, spec, bereich),
            }
        )

        details.append(
            {
                "key": key,
                "df": df,
                "mittel": core.format_value(key, df["value"].mean()),
                "median": core.format_value(key, df["value"].median()),
                "min": core.format_value(key, df["value"].min()),
                "max": core.format_value(key, df["value"].max()),
                "n": str(len(df)),
                "referenz": referenz,
            }
        )

    alle_serien.sort(key=lambda s: s["start"], reverse=True)

    for eintrag in details:
        eintrag["trend"] = _trendtext(eintrag["df"], eintrag["key"])
        eintrag["phasen"] = _phasentabelle(eintrag["key"], alle_serien)

    # Für die Arzt-Tabelle nur physiologische Kennzahlen, siehe
    # Begründung bei PHYSIO_METRIKEN
    serien_tabelle = [
        {
            "zeitraum": f"{s['start']:%d.%m.} - {s['ende']:%d.%m.%Y}",
            "label": s["label"],
            "tage": s["tage"],
            "richtung": s["richtung"],
            "mittel": core.format_value(s["key"], s["mittel"]),
            "baseline": core.format_value(s["key"], s["baseline"]),
        }
        for s in alle_serien
        if s["key"] in PHYSIO_METRIKEN
    ]

    aktivitaets_serien = sum(1 for s in alle_serien if s["key"] not in PHYSIO_METRIKEN)

    # Schlaf
    schlaf = core.load_sleep(conn)
    schlaf_tabelle = None
    if not schlaf.empty:
        schlaf = schlaf[
            (schlaf["date"] >= beginn)
            & (schlaf["date"] <= pd.Timestamp(ende))
            & schlaf["asleep_min"].notna()
        ]
        if not schlaf.empty:
            gesamt = schlaf["asleep_min"].sum()
            schlaf_tabelle = [
                ["Kennwert", "Wert", "Einordnung"],
                ["Nächte mit Phasenerfassung", f"{len(schlaf)}", "Grundlage der Auswertung"],
                [
                    "Schlafdauer im Mittel",
                    f"{schlaf['asleep_min'].mean() / 60:.1f} h",
                    "Empfehlung Erwachsene: 7-9 h",
                ],
                [
                    "Tiefschlaf-Anteil",
                    f"{100 * schlaf['deep_min'].sum() / gesamt:.0f} %",
                    "typisch 13-23 % der Gesamtschlafzeit",
                ],
                [
                    "REM-Anteil",
                    f"{100 * schlaf['rem_min'].sum() / gesamt:.0f} %",
                    "typisch 20-25 % der Gesamtschlafzeit",
                ],
                [
                    "Kürzeste / längste Nacht",
                    f"{schlaf['asleep_min'].min() / 60:.1f} / "
                    f"{schlaf['asleep_min'].max() / 60:.1f} h",
                    "Spannweite im Zeitraum",
                ],
            ]

    ekg = _sammle_ekg(conn)

    gesamt_records = core.record_count(conn)
    conn.close()

    return {
        "zeitraum": (beginn, pd.Timestamp(ende)),
        "uebersicht": uebersicht,
        "details": details,
        "serien": serien_tabelle,
        "schlaf": schlaf if schlaf_tabelle else None,
        "schlaf_tabelle": schlaf_tabelle,
        "anzahl_tageswerte": messwerte_im_zeitraum,
        "aktivitaets_serien": aktivitaets_serien,
        "anzahl_gesamt": gesamt_records,
        "profil": profil,
        "ekg": ekg,
    }


# Anzahl der EKG-Kurven, die als Bild in den Bericht kommen. Mehr würde
# den Bericht aufblähen, ohne mehr auszusagen - die Messwerte aller
# Aufzeichnungen stehen ohnehin in der Tabelle.
MAX_EKG_KURVEN = 3


def _sammle_ekg(conn) -> dict:
    """EKG-Aufzeichnungen für den Bericht.

    Bewusst über den gesamten Datenbestand und nicht nur über den
    Berichtszeitraum: Es sind wenige Aufzeichnungen, und für die
    ärztliche Einordnung ist die vollständige Historie relevanter als ein
    Ausschnitt.
    """
    import ecg as ecg_modul

    if not ecg_modul.tabelle_existiert(conn):
        return {"vorhanden": False}

    df = ecg_modul.lade_uebersicht(conn)
    if df.empty:
        return {"vorhanden": False}

    tabelle = [
        [
            "Datum",
            "Uhrzeit",
            "Einstufung durch die Uhr",
            "Herzfrequenz",
            "Schwankung",
            "Signalqualität",
        ]
    ]
    for _, r in df.iterrows():
        tabelle.append(
            [
                f"{r['datum']:%d.%m.%Y}",
                r["aufnahme"][11:16],
                r["klassifikation"] or "-",
                f"{r['hf_mittel']:.0f}/min" if pd.notna(r["hf_mittel"]) else "-",
                f"{r['unregelmaessigkeit']:.1f} %" if pd.notna(r["unregelmaessigkeit"]) else "-",
                r["qualitaet"] or "-",
            ]
        )

    # Auswahl der abgebildeten Kurven: die jüngste Aufzeichnung ist immer
    # dabei (zeigt den aktuellen Zustand), die übrigen Plätze gehen an
    # Aufzeichnungen mit abweichender Einstufung
    auswahl = [df["id"].iloc[0]]
    abweichend = df[~df["klassifikation"].isin(["Sinusrhythmus"])]
    for kandidat in abweichend["id"]:
        if len(auswahl) >= MAX_EKG_KURVEN:
            break
        if kandidat not in auswahl:
            auswahl.append(kandidat)

    kurven = []
    for ecg_id in auswahl:
        zeile = df[df["id"] == ecg_id].iloc[0]
        signal_uv, messrate = ecg_modul.lade_signal(conn, int(ecg_id))
        if len(signal_uv) == 0:
            continue
        kurven.append(
            {
                "id": int(ecg_id),
                "titel": f"{zeile['aufnahme'][:16]} - {zeile['klassifikation']}",
                "signal": signal_uv,
                "messrate": messrate,
                "klassifikation": zeile["klassifikation"],
                "hf": zeile["hf_mittel"],
                "qualitaet": zeile["qualitaet"],
                "symptome": zeile["symptome"],
            }
        )

    verteilung = df["klassifikation"].value_counts().to_dict()

    return {
        "vorhanden": True,
        "anzahl": len(df),
        "von": df["datum"].min(),
        "bis": df["datum"].max(),
        "tabelle": tabelle,
        "kurven": kurven,
        "verteilung": verteilung,
        "erklaerungen": {
            k: ecg_modul.KLASSIFIKATIONEN[k] for k in verteilung if k in ecg_modul.KLASSIFIKATIONEN
        },
    }
