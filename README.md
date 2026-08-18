# Gesundheitsdashboard

[![Tests](https://github.com/netrox93/Gesundheitsdashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/netrox93/Gesundheitsdashboard/actions/workflows/ci.yml)
[![Lizenz: MIT](https://img.shields.io/badge/Lizenz-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

Wertet den Export der Apple-Health-App aus - lokal auf dem eigenen Rechner.
Zeigt Langzeitverläufe über Jahre, vergleicht sie mit Referenzbereichen aus
der Literatur, findet Abweichungen vom eigenen Normalzustand, stellt
EKG-Aufzeichnungen im klinischen Massstab dar und erzeugt einen PDF-Bericht
zur Mitnahme zum Arzt.

Entstanden aus der Frage, was in sechs Jahren Apple-Watch-Daten eigentlich
drinsteckt, wenn man sie nicht nur tageweise in der Health-App anschaut.

## Worum es geht

Die Health-App zeigt Momentaufnahmen. Interessant wird es, wenn man den
eigenen Verlauf über Jahre sieht und ihn einordnen kann:

- **Langzeitverläufe** statt Tagesansichten - Ruhepuls, HRV, VO2max,
  Schlaf, Aktivität über den gesamten Datenbestand
- **Zwei Referenzsysteme**: der Bereich aus der Literatur (bin ich
  grundsätzlich im gesunden Bereich?) und die eigene Baseline (weiche ich
  von mir selbst ab?)
- **Abweichungen mit Kontext** - auffällige Phasen und was zeitlich damit
  zusammenfiel
- **Zusammenhänge mit Zeitversatz** - wirkt schlechter Schlaf auf den
  Ruhepuls am Folgetag?
- **EKG** im gewohnten Millimeterraster, mit Apples Einstufung und eigener
  Frequenzmessung
- **Arztbericht als PDF**, bei dem das Messverfahren vor den Zahlen steht

## Wichtiger Hinweis

Dieses Projekt ist **kein Medizinprodukt** und ersetzt keine ärztliche
Untersuchung, Diagnose oder Behandlung. Es wertet Daten von
Consumer-Wearables aus, die nicht unter klinischen Bedingungen erhoben
werden.

Referenzbereiche stammen aus der Literatur und gelten für gesunde
Erwachsene - ein Wert ausserhalb eines Bereichs ist kein Befund. Das
Projekt interpretiert bewusst keine EKG-Kurven und stellt keine Diagnosen.
Bei gesundheitlichen Fragen oder auffälligen Werten bitte ärztlichen Rat
einholen.

## Datenschutz

Alle Daten bleiben auf dem eigenen Rechner. Es gibt keine Server-Komponente,
keine Telemetrie und keine Netzwerkverbindung nach aussen - Streamlit läuft
lokal im Browser.

Die Ordner `data/`, `imports/` und `exports/` sind von der Versionskontrolle
ausgeschlossen. Aus den EKG-Dateien werden Name und Geburtsdatum bewusst
nicht in die Datenbank übernommen; für die Referenzbereiche werden nur Alter
und Geschlecht gespeichert.

Der erzeugte PDF-Bericht enthält Alter, Geschlecht und Gesundheitsdaten -
vor dem Weitergeben entsprechend prüfen.


## Schnellstart

**Windows:** Doppelklick auf **`Gesundheitsdashboard starten.bat`**.

Beim ersten Start richtet sich die Umgebung selbst ein (dauert ein paar
Minuten), danach öffnet sich das Dashboard im Browser. Voraussetzung ist
eine Python-Installation ab Version 3.9 von
[python.org](https://www.python.org/downloads/) - dort bei der Installation
den Haken bei *"Add python.exe to PATH"* setzen.

Sind mehrere Python-Versionen installiert, wählt die Startdatei die
neueste. Eine unvollständige Umgebung aus einem früheren Versuch wird
erkannt und neu aufgebaut.

**macOS/Linux:**

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app/dashboard.py
```

## Daten einlesen

1. Auf dem iPhone die **Health-App** öffnen
2. Oben rechts auf das **Profilbild** tippen
3. Ganz unten **"Alle Gesundheitsdaten exportieren"** wählen
4. Die entstehende `Export.zip` auf den Rechner übertragen
5. Im Dashboard auf die Seite **Daten einlesen** gehen

Dort führen drei Wege zum Ziel, ohne dass ein Pfad getippt werden muss:

- **Suchen lassen** - durchsucht Downloads, Schreibtisch, Dokumente und
  angeschlossene Wechseldatenträger und bietet die Fundstellen zum
  Anklicken an, neueste zuerst
- **Auswahldialog** - der gewohnte Dateidialog des Betriebssystems, für
  ZIP-Datei oder entpackten Ordner
- **Pfad eintragen** - als Rückfalloption; Anführungszeichen aus Windows'
  "Als Pfad kopieren" und `file:///`-URLs werden dabei toleriert

Der Rest passiert automatisch: entpacken, Profil lesen, Messwerte
importieren, Tagesaggregate berechnen, EKGs einlesen. Ein Export mit rund
4,5 Millionen Messwerten braucht dafür etwa eine Minute.

Der Weg über den Browser-Upload existiert ebenfalls, ist aber nur für
kleine Exporte sinnvoll: Streamlit puffert die Datei dabei im
Arbeitsspeicher. Ein mehrjähriger Export ist dafür meist zu gross -
deshalb ist die Auswahl per Dialog der empfohlene Weg.

Ein späterer Export kann jederzeit erneut eingelesen werden - bereits
vorhandene Werte werden übersprungen, nur Neues kommt dazu.

Auf der Kommandozeile geht dasselbe mit:

```bash
python app/einlesen.py /pfad/zu/Export.zip
```

## Datenbank an einem anderen Ort

Standardmässig liegt die Datenbank unter `data/health.db` im Projektordner.
Über den Reiter **Datenbank** auf der Seite *Daten einlesen* lässt sich
stattdessen eine bestehende Datei verwenden:

- **Verknüpfen** - die Datei bleibt, wo sie ist (externe Platte,
  Cloud-Ordner, Netzlaufwerk), das Dashboard greift nur darauf zu
- **In den Projektordner kopieren** - legt eine Kopie unter
  `data/health.db` an; eine dort vorhandene Datenbank wird vorher als
  `health.db.alt` gesichert
- **Sicherungskopie anlegen** - kopiert die aktuelle Datenbank an einen
  frei wählbaren Ort

So lässt sich eine fertige Auswertung auf einen anderen Rechner mitnehmen,
ohne den Export erneut einzulesen. Vor dem Verknüpfen wird geprüft, ob die
Datei wirklich eine SQLite-Datenbank dieses Projekts ist - eine falsch
gewählte Datei fällt sofort auf statt später als unverständlicher Fehler.

Der gewählte Pfad steht in `config/einstellungen.json` und ist von der
Versionskontrolle ausgeschlossen, weil er rechnerabhängig ist.

## Mehrere Personen

Jede Person braucht eine eigene Kopie des Ordners, weil die Datenbank unter
`data/health.db` liegt und jeweils genau ein Profil enthält.

Geburtsdatum und Geschlecht liest das Tool aus dem `<Me>`-Element des
Exports. Fehlen sie dort, lassen sie sich auf der Seite *Daten einlesen*
von Hand eintragen. Beides wird gebraucht, weil ein Teil der
Referenzbereiche davon abhängt:

| Kennzahl | Anpassung |
| --- | --- |
| VO2max | nach Altersdekade und Geschlecht (Cooper/ACSM-Normen) |
| Schlafdauer | 14-17 Jahre 8-10 h, 18-64 Jahre 7-9 h, ab 65 Jahren 7-8 h |
| Schritte | unter 60 Jahren 8.000-10.000, ab 60 Jahren 6.000-8.000 |

Alle übrigen Bereiche (Ruhepuls, Atemfrequenz, Sauerstoffsättigung,
Trainingsminuten) gelten für Erwachsene unabhängig von Alter und
Geschlecht und bleiben deshalb konstant.

Ist kein Geschlecht hinterlegt oder "divers" gewählt, umfasst der
VO2max-Bereich die Normwerte für Frauen und Männer gemeinsam - er ist
dadurch breiter, weist aber niemanden fälschlich als auffällig aus.
Ohne Profil wird für VO2max gar kein Bereich angezeigt.

## Voraussetzungen

- Python 3.9 oder neuer (getestet bis 3.14)
- Ein Apple-Health-Export (iPhone, optional mit Apple Watch)
- Rund 2 GB freier Speicher bei einem mehrjährigen Datenbestand

Ohne Apple Watch funktioniert das Tool ebenfalls, dann fehlen allerdings
die meisten Kennzahlen - iPhone-Daten umfassen im Wesentlichen Schritte,
Distanz und Treppen.

## Datenmodell

Rohdaten:

| Tabelle | Inhalt |
| --- | --- |
| `records` | Einzelmesswerte (Puls, Schritte, Schlafsegmente, ...) |
| `workouts` | Trainingseinheiten mit Dauer, Distanz, Kalorien |
| `activity_summaries` | Aktivitätsringe pro Tag inkl. Tagesziele |
| `ecg` | EKG-Aufzeichnungen: Metadaten, Messwerte und Rohsignal |

Aggregate (von `build_daily.py` befüllt, Basis fürs Dashboard):

| Tabelle | Inhalt |
| --- | --- |
| `daily_metrics` | pro Tag und Typ: Anzahl, Summe, Schnitt, Min, Max |
| `daily_sleep` | pro Nacht: Schlafphasen in Minuten, Zubettgeh- und Aufwachzeit |
| `profil` | Geburtsdatum und Geschlecht für die Referenzbereiche |

Die Aggregate existieren aus Performancegründen: `records` hat bei sechs
Jahren Watch-Daten mehrere Millionen Zeilen, direkte Abfragen darauf sind
im Dashboard zu langsam. Eine Nacht in `daily_sleep` ist dem Morgen des
Aufwachens zugeordnet, damit sie sich mit dem Folgetag verknüpfen lässt.

## Aufbau des Dashboards

| Seite | Zweck |
| --- | --- |
| Start | Status der letzten 7 Tage gegen die persönliche Baseline, Auffälligkeiten der letzten 30 Tage |
| Kennzahl im Detail | Verlauf mit Referenzband und Baseline-Korridor, Langzeitentwicklung pro Jahr |
| Abweichungen | Auffällige Tage und Serien, mit Kontext-Panel zur Einordnung |
| Zusammenhänge | Zwei Kennzahlen mit einstellbarem Zeitversatz, inkl. Versatz-Profil |
| Sport und Schlaf | Trainingsbelastung nach Sportart, Schlafphasen, Regelmässigkeit |
| EKG | Aufzeichnungen ansehen, Kurve im klinischen Massstab, Frequenzmessung |
| Arztbericht | PDF-Bericht erzeugen und herunterladen |

### Zwei Arten von Referenzbereichen

Die Diagramme zeigen beides, weil es zwei verschiedene Fragen beantwortet:

- **Populations-Referenz** (Literatur, alters-/geschlechtsnormiert) - "Bin ich
  grundsätzlich im gesunden Bereich?" Liegt als blasses Band im Hintergrund.
- **Persönliche Baseline** (rollierender 90-Tage-Median ± robuste Streuung) -
  "Weiche ich von mir selbst ab?" Für die Abweichungserkennung ist das das
  empfindlichere Mass.

Beispiel: Ein Ruhepuls von 55/min liegt unterhalb des Lehrbuchbereichs
(60-100/min), ist bei Ausdauertrainierten aber der Regelfall. Ein Anstieg von
55 auf 62 läge *innerhalb* des Lehrbuchbereichs und wäre trotzdem das
relevantere Signal. Für Kennzahlen, bei denen ein Populationsbereich
irreführend wäre (HRV, Gehpuls), ist bewusst keiner hinterlegt - die
Begründung steht jeweils in der Infobox.

### Wissenschaftliche Einordnung

Alle Referenzwerte, Quellenangaben und Messhinweise stehen in
`app/reference_ranges.py` - eine Datei, bewusst getrennt vom Dashboard-Code,
damit sie ohne Programmierkenntnisse angepasst werden kann. Zu jeder Kennzahl
gehört ein Messhinweis, der erklärt, wie Apple misst und warum das vom
klinischen Messverfahren abweicht (Beispiel: die SDNN der Apple Watch stammt
aus 60-Sekunden-Fenstern, die bekannten klinischen Grenzwerte gelten für
24-Stunden-Holter-EKG und dürfen hier nicht angewendet werden).

Das Dashboard ist kein Medizinprodukt und ersetzt keine ärztliche Diagnostik.

### Bekannter Bruch in den Schlafdaten

Bis 2024 wurde überwiegend nur "Zeit im Bett" erfasst (iPhone, ohne
Stadienerkennung), ab 2025 liegen echte Schlafphasen vor. Beide sind als
getrennte Kennzahlen geführt, weil ein gemeinsamer Verlauf einen Sprung
zeigen würde, der allein auf der geänderten Messmethode beruht.

## Struktur

```
app/
  schema.sql             SQLite-Schema
  dateiauswahl.py        Export finden, Dateidialog, Pfadaufbereitung
  einstellungen.py       Ort der Datenbank, Prüfung beim Verknüpfen
  einlesen.py            Kompletter Einlese-Vorgang (Kommandozeile)
  pipeline.py            Ablauf: entpacken, importieren, aggregieren
  profil.py              Geburtsdatum und Geschlecht
  import_export.py       Import-Skript für Export.xml
  import_ecg.py          Import der EKG-CSVs
  ecg.py                 EKG einlesen, filtern, vermessen
  ecg_plot.py            EKG-Kurve im klinischen Massstab
  build_daily.py         Berechnet die Tagesaggregate neu
  reference_ranges.py    Referenzbereiche, Quellen, Erklärtexte
  metrics_core.py        Rechenkern (Laden, Baseline, Serien)
  data_access.py         Streamlit-Caching um den Rechenkern
  export_pdf.py          PDF-Bericht
  pdf_data.py            Inhalte für den Bericht
  charts.py              Diagramme und Infoboxen
  dashboard.py           Startseite (Status)
  pages/                 Seiten 1-7
data/
  health.db              SQLite-Datenbank (lokal, nicht in Git)
imports/
  (Ablage für den Export, nicht in Git)
exports/
  (erzeugte PDF-Berichte, nicht in Git)
config/
  einstellungen.json     (rechnerabhängige Pfade, nicht in Git)
Gesundheitsdashboard starten.bat   One-Klick-Start unter Windows
```

## EKG

Der Export enthält die EKG-Aufzeichnungen als CSV unter
`apple_health_export/electrocardiograms`. Sie werden beim normalen
Einlesen automatisch mit übernommen; nachträglich einzeln geht auch:

```bash
python app/import_ecg.py
```

Was ausgewertet wird:

- **Darstellung** der Kurve im klinischen Massstab (25 mm/s, 10 mm/mV),
  30 Sekunden in drei Zeilen, mit Millimeterraster wie auf EKG-Papier
- **Apples eigene Einstufung** (Sinusrhythmus, Vorhofflimmern, hohe/niedrige
  Frequenz, schlechte Aufzeichnung) mit Erklärung, was sie bedeutet
- **Eigene Messung**: Herzfrequenz und Abstände zwischen den Herzschlägen
  über eine R-Zacken-Erkennung (Bandpass 0,5-40 Hz, Energieschwelle mit
  Refraktärzeit, angelehnt an Pan-Tompkins)

Was bewusst **nicht** passiert: eine Beurteilung der Kurvenform. ST-Strecke,
QT-Zeit, Blockbilder und Rhythmusdiagnosen gehören in ärztliche Hand. Die
Apple Watch zeichnet zudem nur eine Ableitung auf; die Zulassung betrifft
die Unterscheidung Sinusrhythmus/Vorhofflimmern und nicht die Erkennung
anderer Herzerkrankungen.

Zwei Fallstricke, die in der Umsetzung berücksichtigt sind:

- **Polarität einheitlich halten.** Ist die S-Zacke tiefer als die R-Zacke
  hoch, springt eine Erkennung über den grössten Betrag zwischen beiden hin
  und her und erzeugt scheinbar unregelmässige Abstände. Die Richtung wird
  deshalb einmal für die gesamte Aufzeichnung festgelegt.
- **Unsichere Messungen kennzeichnen.** Ein verpasster Schlag verdoppelt den
  gemessenen Abstand. Abstände werden gegen den Median geprüft, alle
  Kennwerte robust berechnet und der Anteil verworfener Abstände als
  Signalqualität ausgewiesen. Bei "unzuverlässig" sind die Messwerte nicht
  belastbar - die Kurve bleibt ansehbar.

Name und Geburtsdatum stehen in den CSV-Dateien, werden aber bewusst nicht
in die Datenbank übernommen.

## PDF-Bericht für den Arztbesuch

Über die Seite "Arztbericht" im Dashboard oder auf der Kommandozeile:

```bash
python app/export_pdf.py --monate 12
```

Landet in `exports/` (nicht in Git). Aufbau:

1. Deckblatt mit Datenherkunft und Hinweis zur Einordnung
2. Zusammenfassung aller Kennzahlen gegen ihre Referenzbereiche
3. Auffällige Phasen (zusammenhängende Abweichungen, mindestens zwei Tage)
   als Tabelle mit leerer Spalte zum handschriftlichen Eintragen
4. Je Kennzahl eine Seite: Verlauf, Messverfahren, Quelle, Beobachtungen
   ebenfalls als Tabelle mit Notizspalte
5. Schlafstruktur
6. EKG: Tabelle aller Aufzeichnungen, dazu die jüngste und die
   abweichend eingestuften Kurven als Bild
7. Methodik, Grenzen der Auswertung, alle Quellenangaben

Zwei bewusste Entscheidungen im Berichtsaufbau:

- **Messverfahren steht vor den Zahlen.** Zu jeder Kennzahl kommt zuerst der
  Hinweis, wie Apple misst und wie das vom klinischen Verfahren abweicht.
- **Auffälligkeiten nur für physiologische Kennzahlen.** Erhöhte Schritte
  oder Trainingsminuten sind eine Wanderung, kein Befund - sie würden die
  Tabelle fluten und die relevanten Signale überdecken. Die Auswahl steht
  in `pdf_data.PHYSIO_METRIKEN`. Auf den Einzelseiten der Aktivitätsgrössen
  tauchen ihre Phasen weiterhin auf.
- **Notizspalte bleibt leer.** Welches Ereignis hinter einer Abweichung
  steckt, kann die Auswertung nicht wissen - diese Zuordnung trägt der
  Nutzer von Hand ein. Die Zeilen sind dafür entsprechend hoch.

Der Bericht enthält Geburtsjahr, Alter und Geschlecht.

## Design

Durchgehend das helle Schema "Klinik": kühles Weiss, blaugraues Raster,
nüchtern. Das Streamlit-Grundthema steht in `.streamlit/config.toml`
(fest auf `base = "light"`, folgt also nicht dem System-Dark-Mode), die
passenden Diagrammfarben in `app/charts.py` (Bildschirm) und
`app/export_pdf.py` (PDF).

## Qualitätssicherung

```bash
ruff check .              # Linter
ruff format --check .     # Formatierung
pytest                    # 109 Tests
python tools/check_pages.py   # laedt jede Dashboard-Seite einmal
```

Dieselben vier Schritte laufen bei jedem Push in der CI, gegen Python 3.9,
3.11 und 3.13. Die älteste unterstützte Version läuft bewusst mit -
Konstrukte aus neueren Versionen (etwa `datetime.UTC` ab Python 3.11)
würden sonst erst beim Nutzer auffallen.

Die Tests decken die Stellen ab, an denen stille Fehler entstehen: die
Vereinigung überlappender Schlafsegmente, die robuste Baseline-Berechnung,
die Serien-Erkennung, die Entfaltung von Uhrzeiten um Mitternacht, die
Alters- und Geschlechtsstaffelung der Referenzbereiche sowie die
R-Zacken-Erkennung gegen synthetische EKGs bekannter Frequenz.

## Mitmachen

Siehe [CONTRIBUTING.md](CONTRIBUTING.md). Kurz: keine Gesundheitsdaten ins
Repository, Referenzwerte nur mit Quellenangabe, und das Projekt
interpretiert bewusst keine EKG-Kurven.

## Geplant

- Kalenderdaten anbinden (CalDAV oder ICS-Export)
- Wetterdaten (z.B. Open-Meteo)
- Raumklima aus eigenen Sensoren
- Gemeinsame Auswertung dieser Quellen mit den Gesundheitsdaten

Die Tagesstruktur der Aggregattabellen ist bereits darauf ausgelegt;
Andockpunkt ist das Kontext-Panel auf der Seite *Abweichungen*.

## Lizenz

[MIT](LICENSE)

## Ähnliche Projekte

Es gibt mehrere Werkzeuge, die Apple-Health-Exporte in CSV oder eine
Datenbank überführen. Dieses Projekt setzt den Schwerpunkt bewusst anders:
auf die Einordnung der Werte gegen Referenzbereiche mit Quellenangabe, auf
die Trennung von Populations- und Eigenreferenz und auf einen Bericht, mit
dem eine Ärztin etwas anfangen kann.
