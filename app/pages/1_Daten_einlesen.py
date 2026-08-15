"""Seite 1: Health-Export einlesen, Datenbank verwalten, Profil pflegen.

Erste Anlaufstelle für neue Nutzer - deshalb bewusst ohne
Kommandozeile: Datei auswählen, Knopf drücken, fertig.
"""

import contextlib
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import data_access as da
import einstellungen
import metrics_core as core
import pandas as pd
import pipeline
import profil as profil_modul
import streamlit as st

st.set_page_config(page_title="Daten einlesen", layout="wide")
st.title("Daten einlesen")

BASIS = Path(__file__).parent.parent.parent


def leere_zwischenspeicher() -> None:
    """Nach einem Wechsel der Datenbank müssen Daten und Verbindung neu.

    `cache_resource` hält die offene SQLite-Verbindung - ohne das Leeren
    würde das Dashboard weiter aus der alten Datei lesen.
    """
    st.cache_data.clear()
    st.cache_resource.clear()


def zeige_datenbestand(pfad: Path) -> None:
    """Kurzer Überblick über eine Datenbank."""
    pruefung = einstellungen.pruefe_datenbank(pfad)
    if not pruefung["gueltig"]:
        st.error(pruefung["meldung"])
        return

    spalten = st.columns(4)
    spalten[0].metric("Grösse", f"{pruefung['groesse_mb']:.0f} MB")
    spalten[1].metric("Messwerte", f"{pruefung['tabellen'].get('records', 0):,}".replace(",", "."))
    tageswerte = pruefung["tabellen"].get("daily_metrics", 0)
    spalten[2].metric("Tageswerte", f"{tageswerte:,}".replace(",", "."))
    spalten[3].metric("EKG", f"{pruefung['tabellen'].get('ecg', 0)}")

    if pruefung.get("zeitraum"):
        von, bis = pruefung["zeitraum"]
        st.caption(f"Zeitraum {von} bis {bis}")


tab_export, tab_datenbank, tab_profil = st.tabs(["Export einlesen", "Datenbank", "Profil"])

# ==================================================================
# Export einlesen
# ==================================================================

with tab_export:
    with st.expander("Wie komme ich an meinen Export?", expanded=not da.db_exists()):
        st.markdown(
            """
1. Auf dem iPhone die **Health-App** öffnen (weisses Symbol mit rotem Herz)
2. Oben rechts auf das **Profilbild** tippen
3. Ganz unten **"Alle Gesundheitsdaten exportieren"** wählen
4. Der Export dauert einige Minuten. Danach die Datei **`Export.zip`**
   auf diesen Rechner übertragen - per AirDrop, Mail an sich selbst,
   Kabel oder Cloud-Ordner
5. Unten die ZIP-Datei auswählen und einlesen

Die Daten bleiben dabei vollständig auf diesem Rechner. Es wird nichts
hochgeladen oder verschickt.
"""
        )

    quelle_art = st.radio(
        "Woher kommen die Daten?",
        ["ZIP-Datei hochladen", "Pfad auf diesem Rechner angeben"],
        horizontal=True,
    )

    quelle = None

    if quelle_art == "ZIP-Datei hochladen":
        hochgeladen = st.file_uploader(
            "Export.zip auswählen",
            type=["zip"],
            help="Die unveränderte Datei aus der Health-App.",
        )
        if hochgeladen is not None:
            ziel = BASIS / "imports" / "Export.zip"
            ziel.parent.mkdir(parents=True, exist_ok=True)
            with open(ziel, "wb") as datei:
                datei.write(hochgeladen.getbuffer())
            quelle = ziel
            st.success(f"Datei übernommen ({ziel.stat().st_size / 1024**2:.0f} MB).")
    else:
        eingabe = st.text_input(
            "Pfad zur Export.zip oder zum entpackten Ordner",
            value=str(BASIS / "imports"),
            help="Zum Beispiel C:\\Users\\Name\\Downloads\\Export.zip",
        )
        if eingabe:
            pfad = Path(eingabe)
            if pfad.exists():
                quelle = pfad
            else:
                st.error("Pfad nicht gefunden.")

    mit_ekg = st.checkbox("EKG-Aufzeichnungen mit einlesen", value=True)

    if quelle and st.button("Daten einlesen", type="primary"):
        balken = st.progress(0.0)
        status = st.empty()

        def melde(text: str, anteil: float) -> None:
            status.write(text)
            balken.progress(min(1.0, anteil))

        try:
            ergebnis = pipeline.einlesen(quelle, fortschritt=melde, mit_ekg=mit_ekg)
        except pipeline.EinleseFehler as fehler:
            balken.empty()
            status.empty()
            st.error(str(fehler))
            st.stop()
        except Exception as fehler:  # noqa: BLE001
            balken.empty()
            status.empty()
            st.error(f"Beim Einlesen ist ein Fehler aufgetreten: {fehler}")
            st.stop()

        leere_zwischenspeicher()
        balken.empty()
        status.empty()

        zahlen = ergebnis["messwerte"]
        st.success(
            (
                f"{zahlen['seen']:,} Messwerte gelesen, davon {zahlen['records']:,} neu. "
                f"{zahlen['workouts']} Trainings, {zahlen['summaries']} Aktivitätstage, "
                f"{ergebnis['tageswerte']:,} Tageswerte, {ergebnis['naechte']} Nächte."
            ).replace(",", ".")
        )

        if ergebnis.get("ekg"):
            st.success(f"{ergebnis['ekg']['neu']} EKG-Aufzeichnungen eingelesen.")

        if ergebnis.get("profil"):
            st.success("Profil aus dem Export übernommen.")
        else:
            st.warning(
                "Im Export standen keine Angaben zu Geburtsdatum und Geschlecht. "
                "Bitte im Reiter *Profil* von Hand eintragen, damit die alters- "
                "und geschlechtsabhängigen Referenzbereiche stimmen."
            )

        st.info("Die Auswertung ist jetzt in der linken Navigation verfügbar.")

# ==================================================================
# Datenbank
# ==================================================================

with tab_datenbank:
    aktueller_pfad = einstellungen.db_pfad()

    st.subheader("Aktuell verwendete Datenbank")
    st.code(str(aktueller_pfad), language=None)

    if aktueller_pfad.exists():
        zeige_datenbestand(aktueller_pfad)
        if not einstellungen.ist_standardpfad():
            st.info(
                "Diese Datenbank liegt ausserhalb des Projektordners. Sie bleibt "
                "dort, wo sie ist - das Dashboard greift nur darauf zu."
            )
    else:
        st.warning("Unter diesem Pfad liegt noch keine Datenbank.")

    st.divider()

    st.subheader("Bestehende Datenbank verwenden")
    st.markdown(
        "Nützlich beim Wechsel auf einen anderen Rechner oder wenn die "
        "Datenbank auf einer externen Platte oder im Netzwerk liegen soll - "
        "so muss der Export nicht erneut eingelesen werden. Die Datei heisst "
        "üblicherweise `health.db`."
    )

    eingabe_db = st.text_input(
        "Pfad zur Datenbankdatei",
        key="db_pfad_eingabe",
        placeholder="D:\\Backup\\health.db",
    )

    if eingabe_db:
        pruefung = einstellungen.pruefe_datenbank(eingabe_db)

        if not pruefung["gueltig"]:
            st.error(pruefung["meldung"])
        else:
            st.success(pruefung["meldung"])
            zeige_datenbestand(Path(eingabe_db))

            spalte_a, spalte_b = st.columns(2)

            with spalte_a:
                if st.button("Verknüpfen", type="primary", use_container_width=True):
                    einstellungen.setze_db_pfad(eingabe_db)
                    leere_zwischenspeicher()
                    st.success("Datenbank verknüpft.")
                    st.rerun()
                st.caption(
                    "Die Datei bleibt an ihrem Ort. Ist sie auf einem externen "
                    "Laufwerk, muss dieses beim Start verbunden sein."
                )

            with spalte_b:
                if st.button("In den Projektordner kopieren", use_container_width=True):
                    ziel = einstellungen.STANDARD_DB
                    ziel.parent.mkdir(parents=True, exist_ok=True)

                    if ziel.exists() and Path(eingabe_db).resolve() != ziel.resolve():
                        sicherung = ziel.with_suffix(".db.alt")
                        shutil.move(str(ziel), str(sicherung))
                        st.info(f"Vorhandene Datenbank gesichert als {sicherung.name}.")

                    with st.spinner("Kopiere - bei grossen Datenbanken dauert das etwas ..."):
                        shutil.copy2(eingabe_db, ziel)

                    einstellungen.zuruecksetzen()
                    leere_zwischenspeicher()
                    st.success("Datenbank kopiert und in Benutzung.")
                    st.rerun()
                st.caption(
                    "Legt eine Kopie unter `data/health.db` an. Eine dort "
                    "vorhandene Datenbank wird vorher gesichert."
                )

    st.divider()

    st.subheader("Sicherungskopie anlegen")

    if aktueller_pfad.exists():
        vorgabe = str(BASIS / f"health-sicherung-{date.today():%Y-%m-%d}.db")
        ziel_eingabe = st.text_input("Zielpfad für die Kopie", value=vorgabe)

        if st.button("Kopie anlegen"):
            ziel = Path(ziel_eingabe)
            try:
                ziel.parent.mkdir(parents=True, exist_ok=True)
                with st.spinner("Kopiere ..."):
                    shutil.copy2(aktueller_pfad, ziel)
            except OSError as fehler:
                st.error(f"Kopie fehlgeschlagen: {fehler}")
            else:
                st.success(f"Kopie liegt unter {ziel} ({ziel.stat().st_size / 1024**2:.0f} MB).")
        st.caption(
            "Eine Kopie über den Browser herunterzuladen wäre bei mehreren "
            "hundert Megabyte unpraktisch - deshalb wird direkt im "
            "Dateisystem kopiert."
        )
    else:
        st.caption("Noch keine Datenbank vorhanden.")

    if not einstellungen.ist_standardpfad():
        st.divider()
        if st.button("Zurück zur Datenbank im Projektordner"):
            einstellungen.zuruecksetzen()
            leere_zwischenspeicher()
            st.rerun()

# ==================================================================
# Profil
# ==================================================================

with tab_profil:
    st.caption(
        "Alter und Geschlecht werden für einen Teil der Referenzbereiche "
        "gebraucht: VO2max-Normwerte sind nach Alter und Geschlecht gestaffelt, "
        "die empfohlene Schlafdauer und der Schritt-Richtwert nach Alter. Alle "
        "übrigen Bereiche gelten für Erwachsene unabhängig davon."
    )

    if not da.db_exists():
        st.info("Noch keine Datenbank - erst einen Export einlesen.")
        st.stop()

    conn = core.connect()
    aktuell = profil_modul.lade(conn)

    if aktuell:
        st.write(
            f"Hinterlegt: **{profil_modul.beschreibung(aktuell)}** "
            f"(Geburtsdatum {aktuell['geburtsdatum']}, Quelle: {aktuell['quelle']})"
        )
    else:
        st.warning("Kein Profil hinterlegt.")

    with st.form("profil"):
        spalte1, spalte2 = st.columns(2)

        with spalte1:
            vorgabe_datum = date(1990, 1, 1)
            if aktuell and aktuell.get("geburtsdatum"):
                with contextlib.suppress(ValueError, TypeError):
                    vorgabe_datum = pd.to_datetime(aktuell["geburtsdatum"]).date()

            geburtsdatum = st.date_input(
                "Geburtsdatum",
                value=vorgabe_datum,
                min_value=date(1900, 1, 1),
                max_value=date.today(),
            )

        with spalte2:
            optionen = ["m", "w", "divers"]
            index = (
                optionen.index(aktuell["geschlecht"])
                if (aktuell and aktuell.get("geschlecht") in optionen)
                else 0
            )
            geschlecht = st.selectbox(
                "Geschlecht",
                optionen,
                index=index,
                format_func=lambda g: profil_modul.GESCHLECHT_LABEL[g],
                help="Wird nur für die VO2max-Normwerte verwendet.",
            )

        if st.form_submit_button("Profil speichern"):
            profil_modul.speichere(
                conn, geburtsdatum.isoformat(), geschlecht, quelle="manuell eingetragen"
            )
            st.cache_data.clear()
            st.success("Profil gespeichert.")
            st.rerun()

    st.divider()
    st.subheader("Bisherige Importe")

    start, ende = core.data_range(conn)
    if start is None:
        st.info("Noch keine Tageswerte berechnet.")
    else:
        verlauf = pd.read_sql(
            "SELECT file_name, imported_at, records_seen, records_inserted "
            "FROM imports ORDER BY id DESC LIMIT 5",
            conn,
        )
        if verlauf.empty:
            st.caption("Keine Importe protokolliert.")
        else:
            verlauf["imported_at"] = pd.to_datetime(verlauf["imported_at"]).dt.strftime(
                "%d.%m.%Y %H:%M"
            )
            verlauf.columns = ["Datei", "Eingelesen am", "Gelesen", "Neu"]
            st.dataframe(verlauf, use_container_width=True, hide_index=True)

    st.caption(
        "Ein erneuter Import mit einem neueren Export ergänzt nur die neuen "
        "Werte - bereits vorhandene werden übersprungen."
    )
