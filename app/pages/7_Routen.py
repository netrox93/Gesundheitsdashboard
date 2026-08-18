"""Seite 7: Aufgezeichnete Routen auf einer OpenStreetMap-Karte."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import altair as alt
import data_access as da
import einstellungen
import karten
import metrics_core as core
import pandas as pd
import routen as routen_modul
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Routen", layout="wide")
st.title("Routen")

if not da.db_exists():
    st.error("Noch keine Daten. Auf der Seite **Daten einlesen** den Export einlesen.")
    st.stop()


@st.cache_resource
def _conn():
    return core.connect()


conn = _conn()

if not routen_modul.tabelle_existiert(conn):
    st.warning(
        "Noch keine Routen eingelesen. Der Health-Export enthält sie im Ordner "
        "`workout-routes`; sie werden beim normalen Einlesen automatisch "
        "übernommen. Falls die Daten von einem älteren Import stammen, den "
        "Export auf der Seite **Daten einlesen** noch einmal einlesen."
    )
    st.stop()


@st.cache_data(ttl=3600)
def _uebersicht() -> pd.DataFrame:
    return routen_modul.lade_uebersicht(_conn())


df = _uebersicht()

if df.empty:
    st.warning("Die Routen-Tabelle ist leer.")
    st.stop()

# ------------------------------------------------------------------
# Datenschutz-Einstellungen
# ------------------------------------------------------------------

konfig = einstellungen.lade_heimat()

with st.sidebar:
    st.header("Datenschutz")

    heimat_an = st.checkbox(
        "Umkreis des Heimatpunkts ausblenden",
        value=konfig.get("aktiv", True),
        help="Schneidet Anfang und Ende jeder Route ab, solange sie im "
        "Umkreis liegen. Fahrten, die nur vorbeiführen, bleiben ganz.",
    )

    heimat = None
    if heimat_an:
        vorschlag = konfig.get("lat"), konfig.get("lon")
        if vorschlag[0] is None:
            # Häufigster Startpunkt ist in aller Regel die Wohnadresse
            vorschlag = (
                float(df["lat_min"].median()),
                float(df["lon_min"].median()),
            )

        lat = st.number_input("Breitengrad", value=float(vorschlag[0]), format="%.5f")
        lon = st.number_input("Längengrad", value=float(vorschlag[1]), format="%.5f")
        radius = st.slider(
            "Radius in Metern",
            min_value=100,
            max_value=3000,
            value=int(konfig.get("radius_m", 500)),
            step=100,
        )
        heimat = (lat, lon)

        if st.button("Als Standard speichern"):
            einstellungen.speichere_heimat(lat, lon, radius, aktiv=True)
            st.success("Gespeichert.")
    else:
        radius = 0
        if konfig.get("aktiv"):
            einstellungen.speichere_heimat(
                konfig.get("lat"),
                konfig.get("lon"),
                konfig.get("radius_m", 500),
                aktiv=False,
            )

    st.header("Auswahl")
    sportarten = sorted(df["sportart"].unique())
    gewaehlte_sportarten = st.multiselect("Sportart", sportarten, default=sportarten)

    jahre = sorted(df["start_zeit"].dt.year.dropna().unique(), reverse=True)
    gewaehlte_jahre = st.multiselect("Jahr", jahre, default=jahre)

gefiltert = df[
    df["sportart"].isin(gewaehlte_sportarten) & df["start_zeit"].dt.year.isin(gewaehlte_jahre)
]

if gefiltert.empty:
    st.warning("Keine Routen in dieser Auswahl.")
    st.stop()

# ------------------------------------------------------------------
# Überblick
# ------------------------------------------------------------------

c1, c2, c3, c4 = st.columns(4)
c1.metric("Routen", f"{len(gefiltert)}")
c2.metric("Strecke gesamt", f"{gefiltert['distanz_km'].sum():,.0f} km".replace(",", "."))
c3.metric("Höhenmeter", f"{gefiltert['aufstieg_m'].sum():,.0f} m".replace(",", "."))
c4.metric("Längste Tour", f"{gefiltert['distanz_km'].max():.0f} km")

if heimat_an:
    st.caption(
        f"Anfang und Ende jeder Route werden im Umkreis von {radius} m um "
        f"{heimat[0]:.4f}, {heimat[1]:.4f} abgeschnitten - auch beim Export."
    )


@st.cache_data(ttl=3600)
def _punkte_fuer(routen_ids: tuple, heimat: tuple, radius: float, max_punkte: int) -> list:
    """Punktlisten der gewählten Routen, gekürzt und ausgedünnt."""
    verbindung = _conn()
    ergebnis = []

    for routen_id in routen_ids:
        punkte_df = routen_modul.lade_punkte(verbindung, int(routen_id))
        if punkte_df.empty:
            continue

        punkte = punkte_df.to_dict("records")
        if heimat:
            punkte = routen_modul.kuerze_um_heimat(punkte, heimat, radius)
        if not punkte:
            continue

        ergebnis.append(
            {
                "id": int(routen_id),
                "punkte": karten.ausduennen([(p["lat"], p["lon"]) for p in punkte], max_punkte),
            }
        )

    return ergebnis


tab_karte, tab_heatmap, tab_einzeln, tab_tabelle = st.tabs(
    ["Karte", "Heatmap", "Einzelne Tour", "Tabelle"]
)

# ------------------------------------------------------------------
# Karte
# ------------------------------------------------------------------

with tab_karte:
    st.caption("Alle Routen der Auswahl. Farbe nach Sportart, Punkte markieren Start und Ziel.")

    grenze = st.slider(
        "Höchstens so viele Routen zeichnen",
        5,
        200,
        min(50, len(gefiltert)),
        step=5,
        help="Viele Linien machen die Karte langsam - neueste zuerst.",
    )
    auswahl = gefiltert.head(grenze)

    with st.spinner("Erzeuge Karte ..."):
        punktlisten = _punkte_fuer(tuple(auswahl["id"]), heimat, radius, 800)
        nach_id = {p["id"]: p["punkte"] for p in punktlisten}

        eintraege = [
            {
                "punkte": nach_id[int(zeile["id"])],
                "name": f"{zeile['sportart']} am {zeile['start_zeit']:%d.%m.%Y} "
                f"({zeile['distanz_km']:.1f} km)",
                "sportart": zeile["sportart"],
            }
            for _, zeile in auswahl.iterrows()
            if int(zeile["id"]) in nach_id
        ]

        if eintraege:
            components.html(karten.routenkarte(eintraege), height=600, scrolling=False)
        else:
            st.warning("Keine darstellbaren Punkte - liegt der Heimat-Radius zu weit?")

    legende = " &nbsp; ".join(
        f"<span style='color:{karten.farbe_fuer(s)}'>&#9632;</span> {s}"
        for s in sorted(auswahl["sportart"].unique())
    )
    st.markdown(legende, unsafe_allow_html=True)

# ------------------------------------------------------------------
# Heatmap
# ------------------------------------------------------------------

with tab_heatmap:
    st.caption(
        "Alle Routen übereinander. Je häufiger eine Strecke befahren wurde, "
        "desto kräftiger die Farbe - der direkte Weg zu den eigenen "
        "Standardstrecken."
    )

    spalte_radius, spalte_unschaerfe = st.columns(2)
    with spalte_radius:
        radius_heat = st.slider("Punktgrösse", 2, 20, 6)
    with spalte_unschaerfe:
        unschaerfe = st.slider("Weichzeichnung", 2, 25, 8)

    with st.spinner("Erzeuge Heatmap ..."):
        punktlisten = _punkte_fuer(tuple(gefiltert["id"]), heimat, radius, 1500)
        if punktlisten:
            components.html(
                karten.heatmap(punktlisten, radius_heat, unschaerfe),
                height=600,
                scrolling=False,
            )
            gesamt = sum(len(p["punkte"]) for p in punktlisten)
            st.caption(f"{gesamt:,} Punkte aus {len(punktlisten)} Routen.".replace(",", "."))
        else:
            st.warning("Keine darstellbaren Punkte.")

# ------------------------------------------------------------------
# Einzelne Tour
# ------------------------------------------------------------------

with tab_einzeln:
    auswahl_id = st.selectbox(
        "Tour",
        gefiltert["id"].tolist(),
        format_func=lambda i: (
            f"{gefiltert.loc[gefiltert['id'] == i, 'start_zeit'].iloc[0]:%d.%m.%Y} - "
            f"{gefiltert.loc[gefiltert['id'] == i, 'sportart'].iloc[0]} - "
            f"{gefiltert.loc[gefiltert['id'] == i, 'distanz_km'].iloc[0]:.1f} km"
        ),
    )

    zeile = gefiltert[gefiltert["id"] == auswahl_id].iloc[0]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Strecke", f"{zeile['distanz_km']:.1f} km")
    k2.metric("Dauer", f"{zeile['dauer_min']:.0f} min" if pd.notna(zeile["dauer_min"]) else "-")
    k3.metric("Aufstieg", f"{zeile['aufstieg_m']:.0f} m")
    k4.metric("Punkte", f"{int(zeile['punkte'])}")

    punkte_df = routen_modul.lade_punkte(conn, int(auswahl_id))
    punkte = punkte_df.to_dict("records")
    if heimat:
        punkte = routen_modul.kuerze_um_heimat(punkte, heimat, radius)

    if not punkte:
        st.warning("Diese Route liegt vollständig im ausgeblendeten Umkreis.")
    else:
        components.html(
            karten.routenkarte(
                [
                    {
                        "punkte": karten.ausduennen([(p["lat"], p["lon"]) for p in punkte], 3000),
                        "name": f"{zeile['sportart']} am {zeile['start_zeit']:%d.%m.%Y}",
                        "sportart": zeile["sportart"],
                    }
                ]
            ),
            height=520,
        )

        hoehen = pd.DataFrame(punkte).dropna(subset=["hoehe"])
        if not hoehen.empty and len(hoehen) > 5:
            st.subheader("Höhenprofil")
            hoehen = hoehen.reset_index(drop=True)
            hoehen["Punkt"] = hoehen.index

            flaeche = (
                alt.Chart(hoehen)
                .mark_area(color="#7FA8C9", opacity=0.55, line={"color": "#2C5F8A"})
                .encode(
                    x=alt.X("Punkt:Q", title="Verlauf der Tour"),
                    y=alt.Y(
                        "hoehe:Q",
                        title="Höhe (m)",
                        scale=alt.Scale(zero=False),
                    ),
                    tooltip=[alt.Tooltip("hoehe:Q", title="Höhe", format=".0f")],
                )
                .properties(height=220)
            )
            st.altair_chart(flaeche, use_container_width=True)

        st.download_button(
            "Als GPX herunterladen",
            data=routen_modul.als_gpx(
                punkte, f"{zeile['sportart']} {zeile['start_zeit']:%Y-%m-%d}"
            ),
            file_name=f"tour_{zeile['start_zeit']:%Y-%m-%d}_{int(auswahl_id)}.gpx",
            mime="application/gpx+xml",
        )
        if heimat_an:
            st.caption("Die heruntergeladene Datei ist um den Heimat-Umkreis gekürzt.")

# ------------------------------------------------------------------
# Tabelle
# ------------------------------------------------------------------

with tab_tabelle:
    tabelle = pd.DataFrame(
        {
            "Datum": gefiltert["start_zeit"].dt.strftime("%d.%m.%Y"),
            "Sportart": gefiltert["sportart"],
            "Strecke (km)": gefiltert["distanz_km"].round(1),
            "Dauer (min)": gefiltert["dauer_min"].round(0),
            "Aufstieg (m)": gefiltert["aufstieg_m"].round(0),
            "Punkte": gefiltert["punkte"],
        }
    )
    st.dataframe(tabelle, use_container_width=True, hide_index=True)

    st.subheader("Strecke pro Jahr")
    pro_jahr = (
        gefiltert.assign(Jahr=gefiltert["start_zeit"].dt.year)
        .groupby(["Jahr", "sportart"])["distanz_km"]
        .sum()
        .reset_index()
    )
    balken = (
        alt.Chart(pro_jahr)
        .mark_bar()
        .encode(
            x=alt.X("Jahr:O", title=None),
            y=alt.Y("distanz_km:Q", title="Kilometer"),
            color=alt.Color(
                "sportart:N",
                title="Sportart",
                scale=alt.Scale(
                    domain=list(karten.FARBEN.keys()),
                    range=list(karten.FARBEN.values()),
                ),
            ),
            tooltip=["Jahr", "sportart", alt.Tooltip("distanz_km:Q", format=".0f")],
        )
        .properties(height=300)
    )
    st.altair_chart(balken, use_container_width=True)

st.caption(
    "Kartendaten von OpenStreetMap-Mitwirkenden. Die Kacheln werden beim "
    "Anzeigen von den OSM-Servern geladen; die Routendaten selbst bleiben "
    "auf diesem Rechner."
)
