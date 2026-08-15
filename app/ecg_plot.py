"""Darstellung der EKG-Kurve im klinisch gewohnten Massstab.

Ein Arzt liest ein EKG über das Millimeterraster: 25 mm pro Sekunde
Vorschub, 10 mm pro Millivolt Auslenkung. Ein kleines Kästchen entspricht
damit 40 ms und 0,1 mV, ein grosses 200 ms und 0,5 mV. Nur in diesem
Massstab lassen sich Zeiten und Amplituden direkt ablesen - deshalb wird
hier nicht auf die Fensterbreite skaliert, sondern massstabsgetreu
gezeichnet.
"""

import matplotlib

matplotlib.use("Agg")

import ecg
import matplotlib.pyplot as plt
import numpy as np

# Klassische EKG-Papierfarben
FARBE_RASTER_FEIN = "#F4C7C3"
FARBE_RASTER_GROB = "#E38C87"
FARBE_KURVE = "#1A1A1A"
FARBE_R_ZACKE = "#2C5F8A"

MM_PRO_SEKUNDE = 25.0
MM_PRO_MV = 10.0
ZOLL_PRO_MM = 1 / 25.4


def _raster(ax, dauer_s: float, mv_bereich: tuple) -> None:
    """Millimeterraster wie auf EKG-Papier."""
    unten, oben = mv_bereich

    # Feines Raster: 40 ms und 0,1 mV
    for x in np.arange(0, dauer_s + 1e-9, 0.04):
        ax.axvline(x, color=FARBE_RASTER_FEIN, linewidth=0.3, zorder=0)
    for y in np.arange(np.floor(unten * 10) / 10, oben + 1e-9, 0.1):
        ax.axhline(y, color=FARBE_RASTER_FEIN, linewidth=0.3, zorder=0)

    # Grobes Raster: 200 ms und 0,5 mV
    for x in np.arange(0, dauer_s + 1e-9, 0.2):
        ax.axvline(x, color=FARBE_RASTER_GROB, linewidth=0.6, zorder=0)
    for y in np.arange(np.floor(unten * 2) / 2, oben + 1e-9, 0.5):
        ax.axhline(y, color=FARBE_RASTER_GROB, linewidth=0.6, zorder=0)


def streifen(
    signal_uv: np.ndarray,
    messrate: float,
    sekunden_pro_zeile: float = 10.0,
    r_zacken: np.ndarray = None,
    titel: str = None,
):
    """EKG als mehrzeiliger Streifen im Massstab 25 mm/s, 10 mm/mV.

    Gibt eine matplotlib-Figure zurück, die sowohl im Dashboard als auch
    im PDF verwendet wird.
    """
    gefiltert = ecg.filtere(signal_uv, messrate)
    mv = gefiltert / 1000.0  # Mikrovolt -> Millivolt

    gesamt_s = len(mv) / messrate
    zeilen = max(1, int(np.ceil(gesamt_s / sekunden_pro_zeile)))

    # Y-Bereich auf ein halbes Grosskästchen runden, mit Rand
    spanne = float(np.nanmax(np.abs(mv))) if len(mv) else 1.0
    grenze = max(0.75, np.ceil((spanne * 1.25) * 2) / 2)
    mv_bereich = (-grenze, grenze)

    breite_mm = sekunden_pro_zeile * MM_PRO_SEKUNDE
    hoehe_mm = (mv_bereich[1] - mv_bereich[0]) * MM_PRO_MV

    fig, achsen = plt.subplots(
        zeilen,
        1,
        figsize=(breite_mm * ZOLL_PRO_MM, zeilen * hoehe_mm * ZOLL_PRO_MM + 0.5),
        dpi=150,
    )
    if zeilen == 1:
        achsen = [achsen]

    fig.patch.set_facecolor("white")

    for i, ax in enumerate(achsen):
        von = int(i * sekunden_pro_zeile * messrate)
        bis = min(len(mv), int((i + 1) * sekunden_pro_zeile * messrate))
        abschnitt = mv[von:bis]
        zeit = np.arange(len(abschnitt)) / messrate

        ax.set_facecolor("white")
        _raster(ax, sekunden_pro_zeile, mv_bereich)
        ax.plot(zeit, abschnitt, color=FARBE_KURVE, linewidth=0.7, zorder=3)

        if r_zacken is not None and len(r_zacken):
            im_abschnitt = r_zacken[(r_zacken >= von) & (r_zacken < bis)]
            if len(im_abschnitt):
                ax.plot(
                    (im_abschnitt - von) / messrate,
                    mv[im_abschnitt],
                    "v",
                    color=FARBE_R_ZACKE,
                    markersize=3.5,
                    zorder=4,
                )

        ax.set_xlim(0, sekunden_pro_zeile)
        ax.set_ylim(*mv_bereich)
        ax.set_yticks([])
        ax.set_xticks(np.arange(0, sekunden_pro_zeile + 0.1, 1.0))
        ax.set_xticklabels(
            [f"{int(i * sekunden_pro_zeile + s)}" for s in range(int(sekunden_pro_zeile) + 1)],
            fontsize=6,
            color="#647585",
        )
        ax.tick_params(length=2, pad=1)
        for kante in ax.spines.values():
            kante.set_visible(False)

        if i == zeilen - 1:
            ax.set_xlabel("Sekunden", fontsize=7, color="#647585")

    if titel:
        fig.suptitle(titel, fontsize=9, color="#22303C", y=0.995)

    fig.tight_layout(h_pad=0.4)
    return fig


def massstab_hinweis() -> str:
    return (
        "Massstab 25 mm/s und 10 mm/mV wie auf klassischem EKG-Papier: "
        "ein kleines Kästchen entspricht 40 ms und 0,1 mV, ein grosses "
        "200 ms und 0,5 mV. Dreiecke markieren die automatisch erkannten "
        "R-Zacken."
    )
