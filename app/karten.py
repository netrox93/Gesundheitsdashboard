"""Karten aus den aufgezeichneten Routen.

Verwendet folium (Leaflet) mit Kacheln von OpenStreetMap. Die Karte wird
als eigenständiges HTML erzeugt und im Dashboard eingebettet - dadurch
braucht es keine zusätzliche Streamlit-Komponente.

Die Kacheln werden von den OSM-Servern geladen, dafür ist eine
Internetverbindung nötig. Die Routendaten selbst verlassen den Rechner
nicht: sie stehen direkt im HTML, es wird nichts hochgeladen.
"""

import folium
from folium.plugins import Fullscreen, HeatMap, MiniMap

# Farben je Sportart, angelehnt an das Klinik-Schema des Dashboards
FARBEN = {
    "Cycling": "#2C5F8A",
    "Running": "#CC4B37",
    "Walking": "#4C9F70",
    "Hiking": "#7A5C3E",
    "Snowboarding": "#6B4E9E",
    "DownhillSkiing": "#6B4E9E",
    "Swimming": "#1F8A96",
    "PaddleSports": "#1F8A96",
}
FARBE_STANDARD = "#647585"

OSM_KACHELN = "OpenStreetMap"
OSM_HINWEIS = "&copy; OpenStreetMap-Mitwirkende"


def farbe_fuer(sportart: str) -> str:
    return FARBEN.get(sportart, FARBE_STANDARD)


def _grenzen(routen: list) -> list:
    """Umschliessendes Rechteck aller Routen, für den Startausschnitt."""
    lats = [p[0] for route in routen for p in route["punkte"]]
    lons = [p[1] for route in routen for p in route["punkte"]]
    if not lats:
        return None
    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def _grundkarte(zentrum=None) -> folium.Map:
    karte = folium.Map(
        location=zentrum or [51.16, 10.45],
        zoom_start=6,
        tiles=OSM_KACHELN,
        attr=OSM_HINWEIS,
        control_scale=True,
    )
    Fullscreen(title="Vollbild", title_cancel="Vollbild beenden").add_to(karte)
    MiniMap(toggle_display=True, minimized=True).add_to(karte)
    return karte


def routenkarte(routen: list, zeige_marker: bool = True) -> str:
    """Karte mit einer oder mehreren Routen als Linien.

    `routen` ist eine Liste von Dicts mit `punkte` (Liste von
    (lat, lon)-Paaren), `name` und `sportart`.
    """
    karte = _grundkarte()

    for route in routen:
        if not route["punkte"]:
            continue

        farbe = farbe_fuer(route.get("sportart", ""))

        folium.PolyLine(
            route["punkte"],
            color=farbe,
            weight=3.5,
            opacity=0.8,
            tooltip=route.get("name", ""),
        ).add_to(karte)

        if zeige_marker:
            folium.CircleMarker(
                route["punkte"][0],
                radius=5,
                color=farbe,
                fill=True,
                fill_opacity=1.0,
                tooltip=f"Start: {route.get('name', '')}",
            ).add_to(karte)
            folium.CircleMarker(
                route["punkte"][-1],
                radius=5,
                color="#22303C",
                fill=True,
                fill_opacity=1.0,
                tooltip=f"Ziel: {route.get('name', '')}",
            ).add_to(karte)

    grenzen = _grenzen(routen)
    if grenzen:
        karte.fit_bounds(grenzen, padding=(20, 20))

    return karte.get_root().render()


def heatmap(routen: list, radius: int = 6, unschaerfe: int = 8) -> str:
    """Alle Routen übereinander als Dichtekarte.

    Zeigt, welche Strecken oft gefahren werden. Bewusst mit kleinem
    Radius: bei grossen Werten verschmelfen benachbarte Strassen zu einem
    Fleck, und genau die Unterscheidung ist hier interessant.
    """
    karte = _grundkarte()

    punkte = [p for route in routen for p in route["punkte"]]
    if punkte:
        HeatMap(
            punkte,
            radius=radius,
            blur=unschaerfe,
            min_opacity=0.35,
            gradient={0.2: "#7FA8C9", 0.5: "#2C5F8A", 0.8: "#CC4B37", 1.0: "#7A1F14"},
        ).add_to(karte)

        grenzen = _grenzen(routen)
        if grenzen:
            karte.fit_bounds(grenzen, padding=(20, 20))

    return karte.get_root().render()


def ausduennen(punkte: list, max_punkte: int = 2000) -> list:
    """Punktzahl begrenzen, damit die Karte flüssig bleibt.

    Nimmt jeden n-ten Punkt. Für die Darstellung reicht das; die
    Kennzahlen werden ohnehin auf den vollständigen Daten berechnet.
    """
    if len(punkte) <= max_punkte:
        return punkte

    schritt = len(punkte) // max_punkte + 1
    ausgeduennt = punkte[::schritt]

    # Endpunkt behalten, sonst endet die Linie sichtbar zu früh
    if ausgeduennt[-1] != punkte[-1]:
        ausgeduennt.append(punkte[-1])

    return ausgeduennt
