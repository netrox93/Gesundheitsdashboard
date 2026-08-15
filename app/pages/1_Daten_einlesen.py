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
import dateiauswahl
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
1. Auf dem iPhone die **Health-App** oeffnen (weisses Symbol mit rotem Herz)
2. Oben rechts auf das **Profilbild** tippen
3. Ganz unten **"Alle Gesundheitsdaten exportieren"** waehlen
4. Der Export dauert einige Minuten. Danach die Datei **`Export.zip`**
   auf diesen Rechner uebertragen - per AirDrop, Mail an sich selbst,
   Kabel oder Cloud-Ordner

Die Daten bleiben dabei vollstaendig auf diesem Rechner. Es wird nichts
hochgeladen oder verschickt.
"""
        )

    # Einmal gewaehlte Quelle ueber Klicks hinweg merken
    quelle = st.session_state.get("quelle")

    # --------------------------------------------------------------
    # Weg 1: automatisch suchen
    # --------------------------------------------------------------

    st.subheader("1. Export suchen lassen")

    if st.button("Auf diesem Rechner suchen", type="primary"):
        with st.spinner("Suche in Downloads, auf dem Schreibtisch und an Wechselmedien ..."):
            st.session_state["treffer"] = dateiauswahl.finde_exporte()

    treffer = st.session_state.get("treffer")

    if treffer is not None:
        if not treffer:
            st.warning(
                "Nichts gefunden. Der Export liegt vermutlich woanders - dann "
                "unten den Auswahldialog benutzen."
            )
        else:
            st.write(f"{len(treffer)} moegliche Exporte gefunden, neueste zuerst:")
            for nummer, eintrag in enumerate(treffer):
                spalte_info, spalte_knopf = st.columns([4, 1])
                with spalte_info:
                    st.markdown(
                        f"**{eintrag['pfad'].name}** ({eintrag['art']}, "
                        f"{eintrag['groesse_mb']:.0f} MB, "
                        f"vom {eintrag['geaendert']:%d.%m.%Y})  \n"
                        f"<span style='color:#647585;font-size:0.85em'>{eintrag['pfad']}</span>",
                        unsafe_allow_html=True,
                    )
                with spalte_knopf:
                    if st.button("Auswaehlen", key=f"treffer_{nummer}", use_container_width=True):
                        st.session_state["quelle"] = eintrag["pfad"]
                        st.rerun()

    # --------------------------------------------------------------
    # Weg 2: Datei-Dialog des Betriebssystems
    # --------------------------------------------------------------

    st.subheader("2. Oder selbst auswaehlen")

    if dateiauswahl.dialog_verfuegbar():
        spalte_datei, spalte_ordner = st.columns(2)

        with spalte_datei:
            if st.button("Export.zip auswaehlen ...", use_container_width=True):
                gewaehlt = dateiauswahl.waehle_datei("Export.zip auswaehlen")
                if gewaehlt:
                    st.session_state["quelle"] = Path(gewaehlt)
                    st.rerun()

        with spalte_ordner:
            if st.button("Entpackten Ordner auswaehlen ...", use_container_width=True):
                gewaehlt = dateiauswahl.waehle_datei(
                    "Ordner apple_health_export auswaehlen", ordner=True
                )
                if gewaehlt:
                    st.session_state["quelle"] = Path(gewaehlt)
                    st.rerun()

        st.caption(
            "Oeffnet den gewohnten Auswahldialog. Er erscheint als eigenes "
            "Fenster - unter Umstaenden hinter dem Browser."
        )
    else:
        st.caption(
            "Auf diesem System steht kein Auswahldialog zur Verfuegung "
            "(kein grafischer Arbeitsplatz). Bitte den Pfad unten eintragen."
        )

    with st.expander("Pfad von Hand eintragen"):
        eingabe = st.text_input(
            "Pfad zur Export.zip oder zum entpackten Ordner",
            placeholder="C:\\Users\\Name\\Downloads\\Export.zip",
            help="Anfuehrungszeichen aus 'Als Pfad kopieren' duerfen drin bleiben.",
        )
        if eingabe:
            bereinigt = Path(dateiauswahl.bereinige_pfad(eingabe))
            if bereinigt.exists():
                if st.button("Diesen Pfad verwenden"):
                    st.session_state["quelle"] = bereinigt
                    st.rerun()
            else:
                st.error(f"Nicht gefunden: {bereinigt}")

    with st.expander("Datei hochladen (nur fuer kleine Exporte)"):
        st.caption(
            "Der Weg ueber den Browser braucht viel Arbeitsspeicher und ist "
            "begrenzt. Ein mehrjaehriger Export ist dafuer meist zu gross - "
            "dann die Auswahl oben verwenden."
        )
        hochgeladen = st.file_uploader("Export.zip", type=["zip"])
        if hochgeladen is not None:
            ziel = BASIS / "imports" / "Export.zip"
            ziel.parent.mkdir(parents=True, exist_ok=True)
            with open(ziel, "wb") as datei:
                datei.write(hochgeladen.getbuffer())
            st.session_state["quelle"] = ziel
            st.rerun()

    # --------------------------------------------------------------
    # Weg 3: einlesen
    # --------------------------------------------------------------

    st.divider()
    st.subheader("3. Einlesen")

    if not quelle:
        st.info("Noch nichts ausgewaehlt. Oben suchen lassen oder Datei auswaehlen.")
    else:
        st.success(f"Ausgewaehlt: **{quelle.name}**")
        st.caption(str(quelle))

        mit_ekg = st.checkbox("EKG-Aufzeichnungen mit einlesen", value=True)

        spalte_los, spalte_weg = st.columns([1, 3])

        with spalte_weg:
            if st.button("Andere Datei waehlen"):
                st.session_state.pop("quelle", None)
                st.rerun()

        with spalte_los:
            starten = st.button("Jetzt einlesen", type="primary", use_container_width=True)

        if starten:
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
            bericht = (
                f"{zahlen['seen']:,} Messwerte gelesen, davon {zahlen['records']:,} neu. "
                f"{zahlen['workouts']} Trainings, {zahlen['summaries']} Aktivitaetstage, "
                f"{ergebnis['tageswerte']:,} Tageswerte, {ergebnis['naechte']} Naechte."
            ).replace(",", ".")

            if zahlen["seen"] == 0:
                # Kein Erfolg, auch wenn technisch nichts schiefging
                st.warning(
                    "In der ausgewaehlten Datei standen keine Messwerte. "
                    "Moeglicherweise wurde der Export abgebrochen oder es "
                    "wurde die falsche Datei gewaehlt - erwartet wird die "
                    "`Export.zip` aus der Health-App."
                )
            elif zahlen["records"] == 0:
                st.info(
                    f"{bericht} Alle Werte waren bereits vorhanden - die "
                    "Datenbank ist damit schon auf diesem Stand."
                )
            else:
                st.success(bericht)

            if ergebnis.get("ekg"):
                st.success(f"{ergebnis['ekg']['neu']} EKG-Aufzeichnungen eingelesen.")

            if ergebnis.get("profil"):
                st.success("Profil aus dem Export uebernommen.")
            else:
                st.warning(
                    "Im Export standen keine Angaben zu Geburtsdatum und Geschlecht. "
                    "Bitte im Reiter *Profil* von Hand eintragen, damit die alters- "
                    "und geschlechtsabhaengigen Referenzbereiche stimmen."
                )

            st.info("Die Auswertung ist jetzt in der linken Navigation verfuegbar.")

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
