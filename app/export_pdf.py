"""Erzeugt einen PDF-Bericht zur Mitnahme zum Arzt.

Aufruf:
    python app/export_pdf.py                  # letzte 12 Monate
    python app/export_pdf.py --monate 6
    python app/export_pdf.py --ausgabe C:/Pfad/bericht.pdf

Aufbau des Berichts:
    1. Deckblatt mit Datenherkunft und Einordnung
    2. Übersichtstabelle aller Kennzahlen gegen die Referenzbereiche
    3. Je Kennzahl eine Seite mit Verlauf, Referenzband und Einordnung
    4. Auffälligkeiten und Serien
    5. Methodik und Quellen

Der Bericht ist bewusst so aufgebaut, dass die Messmethode und ihre
Grenzen vor den Zahlen stehen - ein Arzt muss einordnen können, wie die
Werte zustande kommen, bevor er sie liest.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pdf_data as pd_data
import profil as profil_modul
from reference_ranges import METRICS, SCHWELLE_STANDARD, referenzbereich
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Farben aus dem Dashboard-Theme "Klinik", damit Bericht und Bildschirm
# dieselbe Sprache sprechen
FARBE_TEXT = colors.HexColor("#22303C")
FARBE_GEDAEMPFT = colors.HexColor("#647585")
FARBE_LINIE = colors.HexColor("#2C5F8A")
FARBE_RASTER = colors.HexColor("#DCE3EA")
FARBE_FLAECHE = colors.HexColor("#F7F9FB")
FARBE_ABWEICHUNG = colors.HexColor("#CC4B37")

MPL_LINIE = "#2C5F8A"
MPL_PUNKTE = "#A9BECD"
MPL_BASELINE = "#7FA8C9"
MPL_POPULATION = "#8FBF9F"
MPL_ABWEICHUNG = "#CC4B37"
MPL_RASTER = "#DCE3EA"
MPL_TEXT = "#22303C"
MPL_GEDAEMPFT = "#647585"

BERICHT_METRIKEN = [
    "resting_hr",
    "hrv",
    "vo2max",
    "respiratory_rate",
    "spo2",
    "sleep_hours",
    "steps",
    "exercise_min",
]


# ------------------------------------------------------------------
# Formatvorlagen
# ------------------------------------------------------------------


def stile() -> dict:
    basis = getSampleStyleSheet()
    return {
        "titel": ParagraphStyle(
            "Titel",
            parent=basis["Title"],
            fontSize=20,
            leading=25,
            textColor=FARBE_TEXT,
            spaceAfter=6,
            alignment=0,
        ),
        "untertitel": ParagraphStyle(
            "Untertitel",
            parent=basis["Normal"],
            fontSize=11,
            leading=15,
            textColor=FARBE_GEDAEMPFT,
            spaceAfter=18,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=basis["Heading2"],
            fontSize=14,
            leading=18,
            textColor=FARBE_TEXT,
            spaceBefore=14,
            spaceAfter=8,
        ),
        "h3": ParagraphStyle(
            "H3",
            parent=basis["Heading3"],
            fontSize=11.5,
            leading=15,
            textColor=FARBE_TEXT,
            spaceBefore=10,
            spaceAfter=5,
        ),
        "text": ParagraphStyle(
            "Text",
            parent=basis["Normal"],
            fontSize=9.5,
            leading=13.5,
            textColor=FARBE_TEXT,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "klein": ParagraphStyle(
            "Klein",
            parent=basis["Normal"],
            fontSize=8,
            leading=11,
            textColor=FARBE_GEDAEMPFT,
            alignment=TA_JUSTIFY,
            spaceAfter=4,
        ),
        "hinweis": ParagraphStyle(
            "Hinweis",
            parent=basis["Normal"],
            fontSize=8.5,
            leading=12,
            textColor=FARBE_TEXT,
            alignment=TA_JUSTIFY,
            backColor=FARBE_FLAECHE,
            borderPadding=8,
            borderColor=FARBE_RASTER,
            borderWidth=0.6,
            spaceAfter=8,
        ),
    }


# ------------------------------------------------------------------
# Diagramme
# ------------------------------------------------------------------


def verlaufsdiagramm(df: pd.DataFrame, key: str, pfad: Path, bereich=None) -> Path:
    """Verlauf mit Referenzband, Baseline-Korridor und Abweichungen."""
    spec = METRICS[key]
    fig, ax = plt.subplots(figsize=(7.2, 2.5), dpi=200)

    fig.patch.set_facecolor("white")
    ax.set_facecolor("#FCFDFE")

    if bereich:
        low, high = bereich
        ax.axhspan(
            low, high, color=MPL_POPULATION, alpha=0.16, zorder=0, label="Referenzbereich Literatur"
        )

    if "baseline_low" in df.columns and df["baseline_low"].notna().any():
        ax.fill_between(
            df["date"],
            df["baseline_low"],
            df["baseline_high"],
            color=MPL_BASELINE,
            alpha=0.22,
            zorder=1,
            label="individuelle Baseline (±2 SD)",
        )

    ax.plot(
        df["date"],
        df["value"],
        ".",
        color=MPL_PUNKTE,
        markersize=2.2,
        alpha=0.65,
        zorder=2,
        label="Tageswerte",
    )

    if "mean_30" in df.columns and df["mean_30"].notna().any():
        ax.plot(
            df["date"],
            df["mean_30"],
            "-",
            color=MPL_LINIE,
            linewidth=1.7,
            zorder=3,
            label="30-Tage-Mittel",
        )

    if "z" in df.columns:
        auf = df[df["z"].abs() >= SCHWELLE_STANDARD]
        if not auf.empty:
            ax.plot(
                auf["date"],
                auf["value"],
                "o",
                color=MPL_ABWEICHUNG,
                markersize=4,
                zorder=4,
                label=f"Abweichung > {SCHWELLE_STANDARD:.0f} SD",
            )

    ax.set_ylabel(spec["einheit"], fontsize=8, color=MPL_TEXT)
    ax.grid(True, color=MPL_RASTER, linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)

    for kante in ("top", "right"):
        ax.spines[kante].set_visible(False)
    for kante in ("left", "bottom"):
        ax.spines[kante].set_color(MPL_GEDAEMPFT)
        ax.spines[kante].set_linewidth(0.8)

    ax.tick_params(labelsize=7.5, colors=MPL_GEDAEMPFT)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"))
    ax.legend(
        fontsize=6.5,
        loc="upper left",
        ncol=5,
        frameon=False,
        bbox_to_anchor=(0, 1.22),
        labelcolor=MPL_GEDAEMPFT,
    )

    fig.tight_layout()
    fig.savefig(pfad, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return pfad


def schlafdiagramm(schlaf: pd.DataFrame, pfad: Path) -> Path:
    """Gestapelte Schlafphasen."""
    fig, ax = plt.subplots(figsize=(7.2, 2.3), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#FCFDFE")

    unten = np.zeros(len(schlaf))
    for spalte, label, farbe in [
        ("deep_min", "Tiefschlaf", "#1F3A5F"),
        ("core_min", "Leichtschlaf", "#5B8FF9"),
        ("rem_min", "REM", "#9DC6FF"),
    ]:
        werte = (schlaf[spalte].fillna(0) / 60).to_numpy()
        ax.bar(
            schlaf["date"], werte, bottom=unten, width=1.0, color=farbe, label=label, linewidth=0
        )
        unten += werte

    ax.set_ylabel("Stunden", fontsize=8, color=MPL_TEXT)
    ax.grid(True, axis="y", color=MPL_RASTER, linewidth=0.7)
    ax.set_axisbelow(True)
    for kante in ("top", "right"):
        ax.spines[kante].set_visible(False)
    for kante in ("left", "bottom"):
        ax.spines[kante].set_color(MPL_GEDAEMPFT)
        ax.spines[kante].set_linewidth(0.8)
    ax.tick_params(labelsize=7.5, colors=MPL_GEDAEMPFT)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%y"))
    ax.legend(
        fontsize=6.5,
        loc="upper left",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0, 1.2),
        labelcolor=MPL_GEDAEMPFT,
    )

    fig.tight_layout()
    fig.savefig(pfad, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return pfad


# ------------------------------------------------------------------
# Tabellen
# ------------------------------------------------------------------


def tabellenstil(kopfzeile: bool = True) -> TableStyle:
    befehle = [
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), FARBE_TEXT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, FARBE_RASTER),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, FARBE_FLAECHE]),
    ]
    if kopfzeile:
        befehle += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF3")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, FARBE_LINIE),
        ]
    return TableStyle(befehle)


def ekg_kurve(kurve: dict, bilder: Path) -> dict:
    """EKG-Streifen als Bild für den Bericht."""
    import ecg as ecg_modul
    import ecg_plot

    r_zacken = ecg_modul.finde_r_zacken(
        ecg_modul.filtere(kurve["signal"], kurve["messrate"]), kurve["messrate"]
    )

    figur = ecg_plot.streifen(kurve["signal"], kurve["messrate"], r_zacken=r_zacken)
    pfad = bilder / f"ekg_{kurve['id']}.png"
    figur.savefig(pfad, dpi=150, bbox_inches="tight", facecolor="white")

    breite, hoehe = figur.get_size_inches()
    plt.close(figur)

    return {"pfad": pfad, "verhaeltnis": float(hoehe / breite)}


def notizstil(zeilen: int) -> TableStyle:
    """Tabellenstil mit hervorgehobener, leerer Notizspalte rechts."""
    return TableStyle(
        [
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 0), (-1, -1), FARBE_TEXT),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, FARBE_RASTER),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF3")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, FARBE_LINIE),
            # Notizspalte: weiss lassen und deutlich abgrenzen, damit klar
            # ist, dass dort von Hand geschrieben wird
            ("BACKGROUND", (-1, 1), (-1, -1), colors.white),
            ("LINEBEFORE", (-1, 0), (-1, -1), 0.9, FARBE_LINIE),
            ("ROWBACKGROUNDS", (0, 1), (-2, -1), [colors.white, FARBE_FLAECHE]),
        ]
    )


def phasentabelle(phasen: list, s: dict) -> Table:
    """Auffällige Phasen einer Kennzahl mit leerer Notizspalte."""
    zeilen = [
        ["Zeitraum", "Tage", "Richtung", "Mittelwert", "Normalwert", "Was war in dieser Zeit?"]
    ]
    for p in phasen:
        zeilen.append(
            [
                p["zeitraum"],
                p["tage"],
                p["richtung"],
                p["mittel"],
                p["baseline"],
                "",
            ]
        )

    tab = Table(
        zeilen,
        colWidths=[3.0 * cm, 1.0 * cm, 1.9 * cm, 2.3 * cm, 2.3 * cm, 5.5 * cm],
        rowHeights=[0.65 * cm] + [1.15 * cm] * len(phasen),
        repeatRows=1,
    )
    tab.setStyle(notizstil(len(phasen)))
    return tab


# ------------------------------------------------------------------
# Bericht
# ------------------------------------------------------------------


def baue_bericht(monate: int, ausgabe: Path, bilder: Path) -> Path:
    s = stile()
    daten = pd_data.sammle(BERICHT_METRIKEN, monate)
    heute = date.today()
    von, bis = daten["zeitraum"]

    doc = SimpleDocTemplate(
        str(ausgabe),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="Gesundheitsdaten - Auswertung tragbarer Sensoren",
        author="Selbstauswertung",
    )

    inhalt = []

    # ---------------- Deckblatt ----------------
    inhalt.append(Paragraph("Auswertung von Gesundheitsdaten", s["titel"]))
    inhalt.append(Paragraph("Selbstaufzeichnung mit Apple Watch und iPhone", s["untertitel"]))

    kopf = [
        ["Person", profil_modul.beschreibung(daten.get("profil"))],
        ["Auswertungszeitraum", f"{von:%d.%m.%Y} bis {bis:%d.%m.%Y}"],
        ["Erstellt am", f"{heute:%d.%m.%Y}"],
        ["Datenquelle", "Apple Watch, iPhone (Apple Health Export)"],
        ["Ausgewertete Tageswerte", f"{daten['anzahl_tageswerte']:,}".replace(",", ".")],
    ]
    tab = Table(kopf, colWidths=[4.5 * cm, 11.5 * cm])
    tab.setStyle(tabellenstil(kopfzeile=False))
    inhalt.append(tab)
    inhalt.append(Spacer(1, 14))

    inhalt.append(
        Paragraph(
            "<b>Hinweis zur Einordnung dieser Daten</b><br/><br/>"
            "Die hier dargestellten Werte stammen aus Consumer-Wearables und "
            "nicht aus medizinischer Messtechnik. Sie sind nicht diagnostisch "
            "verwertbar und ersetzen keine ärztliche Untersuchung. Die "
            "Messverfahren weichen teilweise erheblich von den klinischen "
            "Verfahren ab, aus denen die angegebenen Referenzbereiche stammen; "
            "die jeweilige Abweichung ist bei jeder Kennzahl vermerkt.<br/><br/>"
            "Der Nutzen dieser Auswertung liegt weniger im Absolutwert als in "
            "der Länge und Dichte der Zeitreihe: Sie zeigt Verläufe und "
            "Abweichungen vom individuellen Normalzustand über einen Zeitraum, "
            "der in einer Praxismessung nicht abbildbar ist.",
            s["hinweis"],
        )
    )

    inhalt.append(Paragraph("Zusammenfassung", s["h2"]))

    zeilen = [["Kennzahl", "Mittelwert", "Bereich (5.-95. Perz.)", "Referenzbereich", "Lage"]]
    for eintrag in daten["uebersicht"]:
        zeilen.append(
            [
                Paragraph(eintrag["label"], s["klein"]),
                eintrag["mittel"],
                eintrag["spanne"],
                Paragraph(eintrag["referenz"], s["klein"]),
                Paragraph(eintrag["lage"], s["klein"]),
            ]
        )

    tab = Table(zeilen, colWidths=[4.1 * cm, 2.3 * cm, 3.2 * cm, 3.2 * cm, 3.2 * cm], repeatRows=1)
    tab.setStyle(tabellenstil())
    inhalt.append(tab)
    inhalt.append(Spacer(1, 8))
    inhalt.append(
        Paragraph(
            'Die Spalte "Lage" beschreibt das Verhältnis zum '
            "Populations-Referenzbereich. Eine Lage ausserhalb des Bereichs ist "
            "nicht gleichbedeutend mit einem Befund - bei mehreren Kennzahlen ist "
            "eine Abweichung bei sportlich aktiven Personen der Regelfall.",
            s["klein"],
        )
    )

    # ---------------- Auffälligkeiten ----------------
    inhalt.append(PageBreak())
    inhalt.append(Paragraph("Auffällige Phasen", s["h2"]))
    inhalt.append(
        Paragraph(
            "Als auffällig gilt eine Abweichung von mehr als "
            f"{SCHWELLE_STANDARD:.0f} robusten Standardabweichungen vom "
            "individuellen 90-Tage-Median. Aufgeführt sind nur zusammenhängende "
            "Phasen von mindestens zwei aufeinanderfolgenden Tagen in derselben "
            "Richtung - einzelne Ausreisser sind bei dieser Datenmenge zu "
            "erwarten und meist messtechnisch bedingt.",
            s["text"],
        )
    )
    inhalt.append(
        Paragraph(
            "Die Tabelle beschränkt sich auf physiologische Kennzahlen. "
            "Ausschläge bei Aktivitätsgrössen (Schritte, Trainingsminuten, "
            "geschätzte VO2max) bilden Wanderungen oder Trainingsphasen ab und "
            f"sind hier nicht aufgeführt; im Zeitraum betrifft das "
            f"{daten['aktivitaets_serien']} weitere Phasen.",
            s["klein"],
        )
    )

    if daten["serien"]:
        zeilen = [
            ["Zeitraum", "Kennzahl", "Tage", "Mittelwert", "Normalwert", "Was war in dieser Zeit?"]
        ]
        for serie in daten["serien"]:
            zeilen.append(
                [
                    serie["zeitraum"],
                    Paragraph(
                        f"{serie['label']}<br/><font size=7>{serie['richtung']}</font>", s["klein"]
                    ),
                    str(serie["tage"]),
                    serie["mittel"],
                    serie["baseline"],
                    "",
                ]
            )
        tab = Table(
            zeilen,
            colWidths=[2.9 * cm, 3.3 * cm, 1.0 * cm, 2.2 * cm, 2.2 * cm, 4.4 * cm],
            rowHeights=[0.65 * cm] + [1.25 * cm] * len(daten["serien"]),
            repeatRows=1,
        )
        tab.setStyle(notizstil(len(daten["serien"])))
        inhalt.append(tab)
        inhalt.append(Spacer(1, 5))
        inhalt.append(
            Paragraph(
                "Die rechte Spalte ist bewusst leer: Sie ist zum handschriftlichen "
                "Eintragen gedacht, was im jeweiligen Zeitraum los war - etwa "
                "Infekt, Reise, Zeitumstellung, ungewohnte Belastung, Medikamente "
                "oder Alkohol. Diese Zuordnung kann die Auswertung selbst nicht "
                "leisten, ist für die Deutung der Werte aber entscheidend.",
                s["klein"],
            )
        )
    else:
        inhalt.append(
            Paragraph("Im Auswertungszeitraum keine Phasen über der Schwelle.", s["text"])
        )

    # ---------------- Kennzahlen im Einzelnen ----------------
    for eintrag in daten["details"]:
        inhalt.append(PageBreak())
        spec = METRICS[eintrag["key"]]

        inhalt.append(Paragraph(spec["label"], s["h2"]))

        bild = verlaufsdiagramm(
            eintrag["df"],
            eintrag["key"],
            bilder / f"verlauf_{eintrag['key']}.png",
            bereich=referenzbereich(eintrag["key"], daten.get("profil"))["bereich"],
        )
        inhalt.append(Image(str(bild), width=16 * cm, height=16 * cm * 0.36))
        inhalt.append(Spacer(1, 6))

        werte = [
            ["Mittelwert", eintrag["mittel"], "Median", eintrag["median"]],
            ["Minimum", eintrag["min"], "Maximum", eintrag["max"]],
            ["Tage mit Daten", eintrag["n"], "Referenzbereich", eintrag["referenz"]],
        ]
        tab = Table(werte, colWidths=[3.4 * cm, 4.6 * cm, 3.4 * cm, 4.6 * cm])
        tab.setStyle(tabellenstil(kopfzeile=False))
        inhalt.append(tab)
        inhalt.append(Spacer(1, 8))

        inhalt.append(Paragraph("Messverfahren und Vergleichbarkeit", s["h3"]))
        inhalt.append(Paragraph(spec["messhinweis"], s["hinweis"]))

        inhalt.append(Paragraph("Herkunft des Referenzbereichs", s["h3"]))
        inhalt.append(Paragraph(spec["quelle"], s["text"]))

        inhalt.append(Paragraph("Beobachtungen im Zeitraum", s["h3"]))
        if eintrag.get("trend"):
            inhalt.append(Paragraph(eintrag["trend"], s["text"]))

        if eintrag["phasen"]:
            inhalt.append(phasentabelle(eintrag["phasen"], s))
            inhalt.append(Spacer(1, 4))
            inhalt.append(
                Paragraph(
                    "Die rechte Spalte ist zum Eintragen von Hand vorgesehen: "
                    "was in dem jeweiligen Zeitraum los war (Krankheit, Reise, "
                    "Belastung, Medikamente, Alkohol).",
                    s["klein"],
                )
            )
        else:
            inhalt.append(
                Paragraph(
                    f"Keine zusammenhängende Phase über {SCHWELLE_STANDARD:.0f} "
                    "Standardabweichungen im Zeitraum.",
                    s["text"],
                )
            )

    # ---------------- Schlaf ----------------
    if daten["schlaf"] is not None and not daten["schlaf"].empty:
        inhalt.append(PageBreak())
        inhalt.append(Paragraph("Schlafstruktur", s["h2"]))

        bild = schlafdiagramm(daten["schlaf"], bilder / "schlaf.png")
        inhalt.append(Image(str(bild), width=16 * cm, height=16 * cm * 0.33))
        inhalt.append(Spacer(1, 8))

        tab = Table(daten["schlaf_tabelle"], colWidths=[5.5 * cm, 4.0 * cm, 6.5 * cm])
        tab.setStyle(tabellenstil())
        inhalt.append(tab)
        inhalt.append(Spacer(1, 8))
        inhalt.append(
            Paragraph(
                "Die Stadienzuordnung eines Wearables beruht auf Bewegung und "
                "Herzfrequenz und stimmt mit der Polysomnographie nur "
                "eingeschränkt überein; insbesondere Tief- und REM-Schlaf werden "
                "nur mässig zuverlässig getrennt. Die Gesamtschlafzeit ist "
                "belastbarer als die Aufteilung. Überlappende Aufzeichnungen "
                "mehrerer Geräte wurden zusammengeführt, um Doppelzählungen zu "
                "vermeiden.",
                s["hinweis"],
            )
        )

    # ---------------- EKG ----------------
    ekg_daten = daten.get("ekg", {})
    if ekg_daten.get("vorhanden"):
        inhalt.append(PageBreak())
        inhalt.append(Paragraph("EKG-Aufzeichnungen", s["h2"]))

        inhalt.append(
            Paragraph(
                "<b>Art der Aufzeichnung</b><br/><br/>"
                "Die Apple Watch zeichnet eine EINZELNE Ableitung auf, die etwa "
                "der Ableitung I nach Einthoven entspricht, über jeweils 30 "
                "Sekunden bei 512 Hz. Ein klinisches Ruhe-EKG umfasst 12 "
                "Ableitungen. Die Zulassung des Verfahrens betrifft die "
                "Unterscheidung von Sinusrhythmus und Vorhofflimmern; die "
                "Erkennung von Myokardinfarkten, Erregungsleitungsstörungen oder "
                "sonstigen Rhythmusstörungen ist ausdrücklich nicht Gegenstand "
                "der Zulassung. Ein unauffälliges Ergebnis schliesst eine "
                "Herzerkrankung nicht aus.<br/><br/>"
                "Die in diesem Bericht angegebenen Frequenz- und Abstandswerte "
                "stammen aus einer automatischen R-Zacken-Erkennung dieser "
                "Auswertung, nicht von Apple. Eine Beurteilung der Kurvenform "
                "wurde bewusst nicht vorgenommen.",
                s["hinweis"],
            )
        )

        inhalt.append(
            Paragraph(
                f"Vorliegend sind {ekg_daten['anzahl']} Aufzeichnungen aus dem "
                f"Zeitraum {ekg_daten['von']:%m/%Y} bis {ekg_daten['bis']:%m/%Y} "
                "(gesamter Datenbestand, unabhängig vom Auswertungszeitraum "
                "dieses Berichts).",
                s["text"],
            )
        )

        tab = Table(
            ekg_daten["tabelle"],
            colWidths=[2.4 * cm, 1.8 * cm, 4.6 * cm, 2.5 * cm, 2.3 * cm, 2.4 * cm],
            repeatRows=1,
        )
        tab.setStyle(tabellenstil())
        inhalt.append(tab)
        inhalt.append(Spacer(1, 8))

        inhalt.append(
            Paragraph(
                '"Schwankung" bezeichnet den Variationskoeffizienten der '
                "RR-Abstände - ein deskriptives Streuungsmass, kein "
                "Rhythmusbefund; eine atemabhängige Schwankung ist bei jüngeren "
                'Gesunden physiologisch. "Signalqualität" gibt an, wie '
                "zuverlässig die automatische Schlagerkennung arbeiten konnte; "
                'bei der Einstufung "unzuverlässig" sind die abgeleiteten '
                "Messwerte der betreffenden Zeile nicht belastbar.",
                s["klein"],
            )
        )

        for klasse, erklaerung in ekg_daten["erklaerungen"].items():
            inhalt.append(Paragraph(f"<b>{klasse}</b>: {erklaerung}", s["klein"]))

        for kurve in ekg_daten["kurven"]:
            inhalt.append(PageBreak())
            inhalt.append(Paragraph(f"EKG vom {kurve['titel']}", s["h3"]))

            kopf = [
                [
                    "Einstufung",
                    kurve["klassifikation"] or "-",
                    "Herzfrequenz",
                    f"{kurve['hf']:.0f}/min" if kurve["hf"] else "-",
                ],
                [
                    "Signalqualität",
                    kurve["qualitaet"] or "-",
                    "Symptome",
                    kurve["symptome"] or "Ohne",
                ],
            ]
            tab = Table(kopf, colWidths=[3.2 * cm, 4.8 * cm, 3.2 * cm, 4.8 * cm])
            tab.setStyle(tabellenstil(kopfzeile=False))
            inhalt.append(tab)
            inhalt.append(Spacer(1, 6))

            bild = ekg_kurve(kurve, bilder)
            # Massstabsgetreu: 10 s Zeile entspricht 250 mm, auf die
            # nutzbare Breite von 160 mm skaliert
            inhalt.append(
                Image(str(bild["pfad"]), width=16 * cm, height=16 * cm * bild["verhaeltnis"])
            )
            inhalt.append(Spacer(1, 4))
            inhalt.append(
                Paragraph(
                    "Ableitung I, 30 Sekunden in drei Zeilen zu je 10 Sekunden. "
                    "Raster im Massstab 25 mm/s und 10 mm/mV (kleines Kästchen "
                    "40 ms und 0,1 mV); durch die Anpassung an die Seitenbreite "
                    "ist der Ausdruck nicht exakt massstabsgetreu. Dreiecke "
                    "markieren die automatisch erkannten R-Zacken.",
                    s["klein"],
                )
            )

    # ---------------- Methodik ----------------
    inhalt.append(PageBreak())
    inhalt.append(Paragraph("Methodik", s["h2"]))

    inhalt.append(Paragraph("Datengrundlage", s["h3"]))
    inhalt.append(
        Paragraph(
            f"Grundlage ist der vollständige Apple-Health-Export vom "
            f"{heute:%d.%m.%Y} mit {daten['anzahl_gesamt']:,}".replace(",", ".")
            + " Einzelmesswerten seit 2020. Für diesen Bericht wurden daraus "
            "Tageswerte gebildet (Mittelwert bei Momentanwerten wie Puls, Summe "
            "bei kumulativen Grössen wie Schritten).",
            s["text"],
        )
    )

    inhalt.append(Paragraph("Individuelle Baseline", s["h3"]))
    inhalt.append(
        Paragraph(
            "Als individueller Normalwert dient der gleitende Median der "
            "vorangegangenen 90 Tage; als Streuungsmass die mediane absolute "
            "Abweichung (MAD), skaliert mit dem Faktor 1,4826. Median und MAD "
            "statt Mittelwert und Standardabweichung, weil einzelne Ausreisser "
            "(Krankheitstage, Messartefakte) die Referenz sonst mitverschieben. "
            "Der jeweilige Tag geht nicht in seine eigene Baseline ein.",
            s["text"],
        )
    )

    inhalt.append(Paragraph("Schwellenwert für Auffälligkeiten", s["h3"]))
    inhalt.append(
        Paragraph(
            f"Die Schwelle liegt bei {SCHWELLE_STANDARD:.0f} Standardabweichungen. "
            "Bei normalverteilten Daten wären mit 2 Standardabweichungen etwa 5 "
            "Prozent der Tage auffällig; in diesem Datensatz sind es rund 10 "
            "Prozent, da die Verteilungen breitere Ränder aufweisen. Die höhere "
            "Schwelle markiert etwa 3 Prozent der Tage.",
            s["text"],
        )
    )

    inhalt.append(Paragraph("Grenzen dieser Auswertung", s["h3"]))
    inhalt.append(
        Paragraph(
            "Die Daten entstehen im Alltag ohne standardisierte Messbedingungen. "
            "Fehlende Tage bedeuten nicht das Fehlen eines Ereignisses, sondern "
            "meist ein nicht getragenes Gerät. Kein Wert dieser Auswertung ist "
            "für sich genommen diagnostisch verwertbar. Zusammenhänge zwischen "
            "Kennzahlen sind Beobachtungen und belegen keine Ursache-Wirkung.",
            s["text"],
        )
    )

    inhalt.append(Paragraph("Verwendete Referenzbereiche", s["h3"]))
    if daten.get("profil"):
        inhalt.append(
            Paragraph(
                "Alters- und geschlechtsabhängige Bereiche (VO2max, Schlafdauer, "
                f"Schritte) sind auf das Profil {profil_modul.beschreibung(daten['profil'])} "
                "angepasst.",
                s["klein"],
            )
        )
    else:
        inhalt.append(
            Paragraph(
                "Kein Profil hinterlegt - alters- und geschlechtsabhängige "
                "Bereiche konnten nicht angepasst werden und zeigen die Werte "
                "für Erwachsene mittleren Alters.",
                s["klein"],
            )
        )
    for key in BERICHT_METRIKEN:
        spec = METRICS[key]
        inhalt.append(Paragraph(f"<b>{spec['label']}</b>: {spec['quelle']}", s["klein"]))

    def fusszeile(canvas, dokument):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(FARBE_GEDAEMPFT)
        canvas.drawString(
            2 * cm,
            1.1 * cm,
            "Selbstaufzeichnung Consumer-Wearable - kein Medizinprodukt, "
            "nicht diagnostisch verwertbar",
        )
        canvas.drawRightString(19 * cm, 1.1 * cm, f"Seite {dokument.page}")
        canvas.setStrokeColor(FARBE_RASTER)
        canvas.setLineWidth(0.5)
        canvas.line(2 * cm, 1.5 * cm, 19 * cm, 1.5 * cm)
        canvas.restoreState()

    doc.build(inhalt, onFirstPage=fusszeile, onLaterPages=fusszeile)
    return ausgabe


def main() -> None:
    parser = argparse.ArgumentParser(description="PDF-Bericht für den Arztbesuch")
    parser.add_argument(
        "--monate", type=int, default=12, help="Auswertungszeitraum in Monaten (Standard: 12)"
    )
    parser.add_argument(
        "--ausgabe",
        type=Path,
        default=None,
        help="Zieldatei (Standard: exports/Gesundheitsbericht_<Datum>.pdf)",
    )
    args = parser.parse_args()

    basis = Path(__file__).parent.parent
    ausgabe = args.ausgabe or (
        basis / "exports" / f"Gesundheitsbericht_{date.today():%Y-%m-%d}.pdf"
    )
    ausgabe.parent.mkdir(parents=True, exist_ok=True)

    bilder = basis / "exports" / ".bilder"
    bilder.mkdir(parents=True, exist_ok=True)

    print(f"Erzeuge Bericht über {args.monate} Monate ...")
    pfad = baue_bericht(args.monate, ausgabe, bilder)
    groesse = pfad.stat().st_size / 1024
    print(f"Fertig: {pfad}  ({groesse:.0f} KB)")


if __name__ == "__main__":
    main()
