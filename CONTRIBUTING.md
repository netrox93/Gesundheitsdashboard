# Mitmachen

Beiträge sind willkommen - Fehlerberichte genauso wie Code.

## Vorweg: keine Gesundheitsdaten ins Repository

Die Ordner `data/`, `imports/` und `exports/` sind in `.gitignore`
ausgeschlossen und müssen es bleiben. Vor einem Pull Request bitte mit
`git status` prüfen, dass keine Datenbank, kein Export und kein
erzeugter Bericht mit eingecheckt wird.

Auch Screenshots und Beispielausgaben in Issues bitte auf persönliche
Daten prüfen - eine EKG-CSV enthält Name und Geburtsdatum, der PDF-Bericht
Alter und Geschlecht.

## Entwicklungsumgebung

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pip install ruff pytest
```

Unter macOS und Linux entsprechend `.venv/bin/python`.

## Vor jedem Pull Request

```bash
ruff check .
ruff format --check .
pytest
python tools/check_pages.py
```

Dieselben vier Schritte laufen in der CI. `check_pages.py` lädt jede
Streamlit-Seite einmal und meldet Ausnahmen - er braucht keine Datenbank.

## Referenzbereiche ändern

Alle medizinischen Referenzwerte stehen in `app/reference_ranges.py`.
Wer dort etwas ändert oder ergänzt, sollte mitliefern:

- die **Quelle** (Leitlinie, Studie, Lehrbuch) im Feld `quelle`
- einen **Messhinweis**, falls das Messverfahren der Uhr vom klinischen
  Verfahren abweicht
- die Angabe, ob der Bereich **alters- oder geschlechtsabhängig** ist

Wo ein Populationsbereich in die Irre führen würde, ist bewusst keiner
hinterlegt - zum Beispiel bei der Herzratenvariabilität, weil die
verbreiteten SDNN-Grenzwerte aus 24-Stunden-Holter-Messungen stammen und
nicht auf die 60-Sekunden-Fenster der Apple Watch übertragbar sind. Solche
Entscheidungen bitte nicht ohne Begründung umkehren.

## Grenze des Projekts

Das Projekt stellt Daten dar und misst, was objektiv messbar ist. Es
interpretiert bewusst nicht: keine Rhythmusdiagnosen aus dem EKG, keine
Bewertung von Kurvenformen, keine Therapieempfehlungen. Pull Requests, die
in diese Richtung gehen, werden nicht übernommen.

## Stil

- Code, Kommentare und Oberfläche auf Deutsch
- Kommentare erklären das *Warum*, nicht das *Was*
- Zeilenlänge 100 Zeichen, Formatierung per `ruff format`
- Neue Rechenlogik gehört in `app/metrics_core.py` (ohne Streamlit-Bezug),
  damit sie auch im PDF-Export nutzbar ist und sich testen lässt
