"""Referenzbereiche, Erklärtexte und Messhinweise für die Kennzahlen.

Diese Datei ist bewusst die einzige Stelle, an der medizinische
Referenzwerte stehen - anpassbar, ohne den Dashboard-Code anzufassen.

Zu jedem Wert gehören:
  * `population`  Referenzbereich aus der Literatur (oder None)
  * `quelle`      Woher der Bereich stammt
  * `messhinweis` Wie Apple misst und warum das vom klinischen
                  Messverfahren abweichen kann - der wichtigste Teil,
                  wenn ein Arzt auf die Diagramme schaut
  * `erklaerung` / `hoch` / `niedrig`  Einordnung für Laien

WICHTIG: Referenzbereiche gelten für gesunde Erwachsene und sind
Orientierung, keine Diagnostik. Einzelne Werte ausserhalb eines
Bereichs sind häufig und meist harmlos; relevant sind anhaltende
Verschiebungen gegenüber der persönlichen Baseline.

Alters- und geschlechtsabhängige Bereiche werden über
`referenzbereich(key, profil)` aufgelöst. Das Profil stammt aus dem
`<Me>`-Element des Health-Exports (siehe `profil.py`). Ohne Profil
werden nur die alters-unabhängigen Bereiche angezeigt.
"""


# ---------------------------------------------------------------------
# Kennzahlen-Registry
#
# agg:   'avg' = Tagesmittel ist die sinnvolle Kennzahl
#        'sum' = Tagessumme ist die sinnvolle Kennzahl
# scale: Faktor auf den Rohwert (z.B. SpO2 wird als Anteil gespeichert)
# ---------------------------------------------------------------------

METRICS = {
    # ---------------- Herz & Kreislauf ----------------
    "resting_hr": {
        "label": "Ruhepuls",
        "kategorie": "Herz & Kreislauf",
        "hk_type": "HKQuantityTypeIdentifierRestingHeartRate",
        "agg": "avg",
        "einheit": "/min",
        "population": (60, 100),
        "population_label": "Normalbereich Erwachsene (60-100/min)",
        "richtung": "niedriger_besser",
        "quelle": (
            "60-100/min gilt als Normalbereich für Erwachsene in Ruhe "
            "(gängige Lehrbuch- und Leitlinienangabe, u.a. American Heart "
            "Association). Ausdauertrainierte liegen regelhaft bei 40-60/min."
        ),
        "messhinweis": (
            "Die Apple Watch schätzt den Ruhepuls aus Phasen längerer "
            "Ruhe über den Tag (optische Photoplethysmographie), nicht aus "
            "einer standardisierten Ruhemessung im Liegen. Absolutwerte sind "
            "daher nur eingeschränkt mit einer Praxismessung vergleichbar; "
            "der Verlauf über die Zeit ist belastbarer als der Einzelwert."
        ),
        "erklaerung": (
            "Wie oft dein Herz schlägt, wenn du dich ausruhst. Ein gut "
            "trainiertes Herz pumpt pro Schlag mehr Blut und braucht deshalb "
            "weniger Schläge."
        ),
        "hoch": (
            "Ein über Tage erhöhter Ruhepuls tritt häufig auf bei beginnendem "
            "Infekt, Schlafmangel, Alkohol, Stress, Fieber, Dehydrierung oder "
            "nach intensiver Belastung. Dauerhaft erhöhte Werte sind in "
            "Kohortenstudien mit erhöhtem kardiovaskulärem Risiko assoziiert."
        ),
        "niedrig": (
            "Niedrige Werte sind bei Ausdauertrainierten normal und in der "
            "Regel ein Zeichen guter Fitness. Sehr niedrige Werte zusammen mit "
            "Schwindel, Luftnot oder Ohnmacht gehören ärztlich abgeklärt."
        ),
    },
    "hrv": {
        "label": "Herzratenvariabilität (SDNN)",
        "kategorie": "Herz & Kreislauf",
        "hk_type": "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
        "agg": "avg",
        "einheit": "ms",
        # Bewusst kein Populationsbereich - siehe messhinweis
        "population": None,
        "population_label": None,
        "richtung": "hoeher_besser",
        "quelle": (
            "Bewusst KEIN Populations-Referenzbereich hinterlegt. Die bekannten "
            "SDNN-Schwellen (<50 ms auffällig, >100 ms normal) stammen aus der "
            "Task Force of the European Society of Cardiology and the North "
            "American Society of Pacing and Electrophysiology (Circulation 1996) "
            "und beziehen sich auf 24-Stunden-Holter-EKG-Aufzeichnungen."
        ),
        "messhinweis": (
            "Die Apple Watch berechnet SDNN aus kurzen Messfenstern (etwa 60 "
            "Sekunden), meist im Ruhezustand oder bei Achtsamkeitsübungen - "
            "NICHT über 24 Stunden. Kurzzeit-SDNN und 24h-SDNN sind numerisch "
            "nicht vergleichbar, die klinischen Grenzwerte dürfen hier nicht "
            "angewendet werden. Zusätzlich ist HRV interindividuell extrem "
            "streuend. Aussagekräftig ist deshalb ausschliesslich die "
            "Abweichung von der eigenen Baseline."
        ),
        "erklaerung": (
            "Schwankung der zeitlichen Abstände zwischen zwei Herzschlägen. "
            "Ein entspanntes, erholtes Nervensystem lässt mehr Schwankung zu - "
            "höhere Werte sprechen tendenziell für gute Erholung."
        ),
        "hoch": (
            "Höhere Werte als sonst sprechen meist für gute Erholung. "
            "Einzelne Ausreisser nach oben sind ohne Bedeutung."
        ),
        "niedrig": (
            "Mehrere Tage deutlich unter deiner Baseline finden sich typisch "
            "bei Stress, Schlafmangel, Alkohol, beginnendem Infekt oder "
            "Übertraining. Der Wert sagt nichts darüber aus, welche dieser "
            "Ursachen vorliegt."
        ),
    },
    "walking_hr": {
        "label": "Durchschnittspuls beim Gehen",
        "kategorie": "Herz & Kreislauf",
        "hk_type": "HKQuantityTypeIdentifierWalkingHeartRateAverage",
        "agg": "avg",
        "einheit": "/min",
        "population": None,
        "population_label": None,
        "richtung": "niedriger_besser",
        "quelle": (
            "Kein etablierter klinischer Referenzbereich - der Wert hängt stark "
            "von Gehtempo, Steigung und Umgebungstemperatur ab. Beurteilung "
            "daher nur gegen die eigene Baseline."
        ),
        "messhinweis": (
            "Apple mittelt hier die Herzfrequenz während Gehphasen des Tages. "
            "Tempo und Gelände werden dabei nicht herausgerechnet."
        ),
        "erklaerung": (
            "Wie hoch dein Puls bei normaler Alltagsbelastung geht. Sinkt "
            "typischerweise, wenn deine Ausdauer besser wird."
        ),
        "hoch": (
            "Anhaltend höhere Werte bei gleichem Gehverhalten können auf "
            "nachlassende Fitness, Infekt, Hitze oder Stress hindeuten."
        ),
        "niedrig": "Sinkende Werte über Wochen sprechen für verbesserte Ausdauer.",
    },
    "hr_recovery": {
        "label": "Herzfrequenz-Erholung (1 Min)",
        "kategorie": "Herz & Kreislauf",
        "hk_type": "HKQuantityTypeIdentifierHeartRateRecoveryOneMinute",
        "agg": "avg",
        "einheit": "/min",
        "population": (12, 60),
        "population_label": "Abfall > 12/min gilt als unauffällig",
        "richtung": "hoeher_besser",
        "quelle": (
            "Der Schwellenwert von 12/min stammt aus Cole et al., New England "
            "Journal of Medicine 1999, wo eine Erholung von 12/min oder weniger "
            "eine Minute nach standardisierter Belastungsuntersuchung mit "
            "erhöhter Mortalität assoziiert war."
        ),
        "messhinweis": (
            "ACHTUNG: Der NEJM-Grenzwert beruht auf einem standardisierten "
            "Belastungstest mit definiertem Abbruchkriterium und definierter "
            "Nachbelastungsphase. Die Apple Watch misst nach beliebigen "
            "Trainingseinheiten unterschiedlicher Intensität. Der Wert ist "
            "hier als Trend zu lesen, nicht als Testergebnis. In diesem "
            "Datensatz liegen ohnehin nur wenige Messungen vor."
        ),
        "erklaerung": (
            "Um wie viele Schläge dein Puls in der ersten Minute nach dem "
            "Training abfällt. Ein schneller Abfall spricht für ein gut "
            "reagierendes vegetatives Nervensystem und gute Fitness."
        ),
        "hoch": "Ein schneller Pulsabfall ist günstig.",
        "niedrig": (
            "Ein langsamer Abfall kann für geringere Fitness, unvollständige "
            "Erholung oder hohe Belastung sprechen. Bei reproduzierbar sehr "
            "niedrigen Werten ärztlich abklären lassen."
        ),
    },
    # ---------------- Fitness ----------------
    "vo2max": {
        "label": "VO2max (Cardio-Fitness)",
        "kategorie": "Fitness",
        "hk_type": "HKQuantityTypeIdentifierVO2Max",
        "agg": "avg",
        "einheit": "mL/kg/min",
        # Alters- und geschlechtsabhängig, siehe VO2MAX_NORMEN
        "population": None,
        "population_label": "durchschnittlich bis gut",
        "altersabhaengig": True,
        "richtung": "hoeher_besser",
        "quelle": (
            "Normwerte nach Alter und Geschlecht, angelehnt an die "
            "Referenztabellen des Cooper Institute, wie sie im ACSM's "
            "Guidelines for Exercise Testing and Prescription verwendet werden. "
            "Die hinterlegten Grenzen markieren näherungsweise den Bereich "
            "'durchschnittlich bis gut' der jeweiligen Alters- und "
            "Geschlechtsgruppe - vor einer Verwendung im ärztlichen Gespräch "
            "bitte gegen die aktuelle ACSM-Auflage prüfen und in "
            "reference_ranges.VO2MAX_NORMEN anpassen."
        ),
        "messhinweis": (
            "Es handelt sich um einen SCHÄTZWERT der Apple Watch aus "
            "Herzfrequenz und Bewegungsdaten beim Gehen/Laufen im Freien, "
            "nicht um eine Spiroergometrie. Systematische Abweichungen zum "
            "Labormesswert sind bekannt. Der Verlauf über Monate ist "
            "aussagekräftiger als der Absolutwert."
        ),
        "erklaerung": (
            "Geschätzte maximale Sauerstoffaufnahme - das gängigste Mass für "
            "Ausdauerleistungsfähigkeit. Höhere Werte bedeuten, dass dein "
            "Körper unter Belastung mehr Sauerstoff verwerten kann."
        ),
        "hoch": (
            "Hohe Werte sprechen für gute Ausdauerleistungsfähigkeit, die in "
            "Kohortenstudien konsistent mit niedrigerer Gesamtmortalität "
            "assoziiert ist."
        ),
        "niedrig": (
            "Niedrigere Werte oder ein Abfall über Monate können auf "
            "nachlassendes Ausdauertraining, längere Krankheit oder "
            "Trainingspausen zurückgehen."
        ),
    },
    "steps": {
        "label": "Schritte",
        "kategorie": "Fitness",
        "hk_type": "HKQuantityTypeIdentifierStepCount",
        "agg": "sum",
        "einheit": "Schritte/Tag",
        "population": (8000, 10000),
        "population_label": "Bereich, ab dem der Zusatznutzen abflacht",
        "altersabhaengig": True,
        "richtung": "hoeher_besser",
        "quelle": (
            "Paluch et al., Lancet Public Health 2022 (Metaanalyse, 15 Kohorten): "
            "Die Sterblichkeit sinkt mit steigender Schrittzahl und erreicht bei "
            "Erwachsenen unter 60 Jahren ein Plateau bei etwa 8.000-10.000 "
            "Schritten pro Tag, bei Erwachsenen ab 60 Jahren bereits bei etwa "
            "6.000-8.000. Es handelt sich um einen Beobachtungszusammenhang, "
            "nicht um eine Zielvorgabe."
        ),
        "messhinweis": (
            "Schritte werden von Watch und iPhone gezählt; bei parallel "
            "getragenen Geräten führt Apple die Werte zusammen. Radfahren und "
            "Krafttraining erzeugen kaum Schritte, obwohl sie belastend sind."
        ),
        "erklaerung": (
            "Gesamte Alltagsbewegung. Der wichtigste Unterschied besteht "
            "zwischen sehr wenig und mässig viel Bewegung - oberhalb von etwa "
            "8.000-10.000 Schritten nimmt der Zusatznutzen deutlich ab."
        ),
        "hoch": "Mehr Bewegung ist grundsätzlich günstig.",
        "niedrig": (
            "Anhaltend niedrige Werte können auf Krankheit, Verletzung, "
            "Wetterlage oder veränderte Arbeitssituation zurückgehen."
        ),
    },
    "exercise_min": {
        "label": "Trainingsminuten",
        "kategorie": "Fitness",
        "hk_type": "HKQuantityTypeIdentifierAppleExerciseTime",
        "agg": "sum",
        "einheit": "min/Tag",
        "population": (21, 43),
        "population_label": "WHO-Empfehlung, auf den Tag umgelegt",
        "richtung": "hoeher_besser",
        "quelle": (
            "WHO Guidelines on Physical Activity and Sedentary Behaviour (2020): "
            "150-300 Minuten moderate oder 75-150 Minuten intensive Aktivität "
            "pro Woche für Erwachsene. Auf den Tag umgelegt entspricht das etwa "
            "21-43 Minuten moderater Aktivität."
        ),
        "messhinweis": (
            "Apple zählt Minuten ab einer Intensität von etwa zügigem Gehen. "
            "Die Wochenempfehlung der WHO ist der eigentliche Bezugsrahmen - "
            "die Umrechnung auf den Einzeltag dient nur der Darstellung."
        ),
        "erklaerung": (
            "Minuten mit erhöhter körperlicher Intensität. Die WHO-Empfehlung "
            "gilt pro Woche, nicht pro Tag - einzelne ruhige Tage sind "
            "unproblematisch, solange die Wochensumme stimmt."
        ),
        "hoch": "Höhere Aktivität ist bis in hohe Umfänge mit Vorteilen assoziiert.",
        "niedrig": "Anhaltend niedrige Werte deuten auf eine inaktive Phase hin.",
    },
    "flights": {
        "label": "Etagen gestiegen",
        "kategorie": "Fitness",
        "hk_type": "HKQuantityTypeIdentifierFlightsClimbed",
        "agg": "sum",
        "einheit": "Etagen/Tag",
        "population": None,
        "population_label": None,
        "richtung": "hoeher_besser",
        "quelle": "Kein etablierter Referenzbereich - Beurteilung gegen die eigene Baseline.",
        "messhinweis": "Barometrische Messung; eine Etage entspricht etwa 3 Metern Höhengewinn.",
        "erklaerung": "Treppensteigen als Mass für kurze, intensive Alltagsbelastung.",
        "hoch": "Höhere Werte sprechen für aktiven Alltag.",
        "niedrig": "Niedrigere Werte sind meist schlicht wohnungs- und arbeitsplatzbedingt.",
    },
    # ---------------- Schlaf ----------------
    "time_in_bed": {
        "label": "Zeit im Bett",
        "kategorie": "Schlaf",
        "hk_type": None,
        "sleep_column": "in_bed_min",
        "agg": "avg",
        "scale": 1 / 60,
        "einheit": "h",
        "population": None,
        "population_label": None,
        "richtung": "neutral",
        "quelle": (
            "Kein eigener Referenzbereich: 'Zeit im Bett' ist NICHT dasselbe wie "
            "Schlafdauer und darf nicht gegen die 7-9-Stunden-Empfehlung gelesen "
            "werden. Sie enthält Einschlafzeit und nächtliche Wachphasen."
        ),
        "messhinweis": (
            "In diesem Datensatz die einzige verfügbare Schlafgrösse für die "
            "Jahre 2020-2024 (Erfassung überwiegend per iPhone, ohne "
            "Stadienerkennung). Ab 2025 liegen stattdessen echte Schlafphasen "
            "vor. Die beiden Grössen sind bewusst getrennt, weil ein "
            "gemeinsamer Verlauf einen Sprung zeigen würde, der nur auf der "
            "geänderten Messmethode beruht."
        ),
        "erklaerung": (
            "Zeit zwischen Zubettgehen und Aufstehen, einschliesslich "
            "Einschlafphase und Wachliegen."
        ),
        "hoch": "Viel Zeit im Bett bei wenig Erholung spricht für unruhigen Schlaf.",
        "niedrig": "Kurze Zeiten im Bett begrenzen zwangsläufig die mögliche Schlafdauer.",
    },
    "sleep_hours": {
        "label": "Schlafdauer (Schlafphasen)",
        "kategorie": "Schlaf",
        "hk_type": None,  # kommt aus daily_sleep
        "sleep_column": "asleep_min",
        "agg": "avg",
        "scale": 1 / 60,
        "einheit": "h",
        "population": (7, 9),
        "population_label": "empfohlene Schlafdauer",
        "altersabhaengig": True,
        "richtung": "hoeher_besser",
        "quelle": (
            "Konsensempfehlung der American Academy of Sleep Medicine und der "
            "Sleep Research Society (2015): Erwachsene von 18-60 Jahren sollten "
            "regelmässig 7 Stunden oder mehr schlafen. Die altersgestaffelten "
            "Bereiche stammen von der National Sleep Foundation (Hirshkowitz "
            "et al., Sleep Health 2015): 14-17 Jahre 8-10 h, 18-64 Jahre "
            "7-9 h, ab 65 Jahren 7-8 h."
        ),
        "messhinweis": (
            "Die Apple Watch schätzt Schlaf aus Bewegung und Herzfrequenz. "
            "Gegenüber der Polysomnographie (Goldstandard) ist die "
            "Übereinstimmung bei der Gesamtschlafzeit gut, bei den einzelnen "
            "Schlafstadien deutlich schwächer. In diesem Datensatz wurden "
            "überlappende Segmente mehrerer Quellen (Watch, iPhone, Pillow) "
            "zusammengeführt, damit Nächte nicht doppelt gezählt werden. "
            "WICHTIG: Schlafphasen liegen erst ab 2025 durchgängig vor - "
            "davor wurde überwiegend nur 'Zeit im Bett' erfasst (siehe dort). "
            "Ein Vergleich der Schlafdauer über 2024/2025 hinweg vergliche "
            "zwei verschiedene Messverfahren."
        ),
        "erklaerung": (
            "Tatsächliche Schlafzeit ohne Wachphasen. Regelmässigkeit ist dabei "
            "mindestens so wichtig wie die reine Dauer."
        ),
        "hoch": (
            "Dauerhaft sehr lange Schlafzeiten können bei Erschöpfung, Infekt "
            "oder unerholsamem Schlaf auftreten."
        ),
        "niedrig": (
            "Regelmässig unter 7 Stunden ist in Studien mit erhöhtem Risiko für "
            "Herz-Kreislauf-Erkrankungen, Stoffwechselstörungen und "
            "eingeschränkter kognitiver Leistung assoziiert."
        ),
    },
    "deep_share": {
        "label": "Tiefschlaf-Anteil",
        "kategorie": "Schlaf",
        "hk_type": None,
        "sleep_column": "deep_share",
        "agg": "avg",
        "einheit": "%",
        "population": (13, 23),
        "population_label": "typischer Anteil bei Erwachsenen",
        "richtung": "hoeher_besser",
        "quelle": (
            "Typische Verteilung der Schlafstadien bei gesunden Erwachsenen: "
            "Tiefschlaf (N3) etwa 13-23 Prozent der Gesamtschlafzeit "
            "(schlafmedizinische Standardliteratur, u.a. Carskadon & Dement). "
            "Der Anteil nimmt mit dem Lebensalter physiologisch ab."
        ),
        "messhinweis": (
            "Die Stadieneinteilung eines Wearables ist NICHT mit einer "
            "Polysomnographie gleichzusetzen - die Übereinstimmung bei "
            "Tiefschlaf und REM ist in Validierungsstudien nur mässig. Für ein "
            "ärztliches Gespräch ist der Verlauf der eigenen Werte "
            "interpretierbar, der Absolutwert nur eingeschränkt."
        ),
        "erklaerung": (
            "Anteil des körperlich erholsamsten Schlafstadiums. Tiefschlaf "
            "liegt überwiegend in der ersten Nachthälfte."
        ),
        "hoch": "Höhere Anteile sprechen für erholsamen Schlaf.",
        "niedrig": (
            "Niedrige Anteile finden sich häufig nach Alkohol, bei spätem "
            "Training, Stress oder unregelmässigen Schlafzeiten."
        ),
    },
    "rem_share": {
        "label": "REM-Anteil",
        "kategorie": "Schlaf",
        "hk_type": None,
        "sleep_column": "rem_share",
        "agg": "avg",
        "einheit": "%",
        "population": (20, 25),
        "population_label": "typischer Anteil bei Erwachsenen",
        "richtung": "hoeher_besser",
        "quelle": (
            "Typischer REM-Anteil gesunder Erwachsener etwa 20-25 Prozent der "
            "Gesamtschlafzeit (schlafmedizinische Standardliteratur)."
        ),
        "messhinweis": (
            "Wie beim Tiefschlaf gilt: Wearable-Stadien weichen von der "
            "Polysomnographie ab. REM liegt überwiegend in der zweiten "
            "Nachthälfte - verkürzter Schlaf trifft daher zuerst den REM-Anteil."
        ),
        "erklaerung": ("Traumschlaf, wichtig für Gedächtnisbildung und emotionale Verarbeitung."),
        "hoch": "Höhere Anteile sind meist unproblematisch.",
        "niedrig": (
            "Niedrige Anteile treten typisch bei verkürztem Schlaf und nach Alkoholkonsum auf."
        ),
    },
    "bedtime_var": {
        "label": "Regelmässigkeit der Schlafenszeit",
        "kategorie": "Schlaf",
        "hk_type": None,
        "sleep_column": "bedtime_minutes",
        "agg": "avg",
        "einheit": "Uhrzeit",
        "population": None,
        "population_label": None,
        "richtung": "neutral",
        "quelle": (
            "Kein Referenzbereich für die Uhrzeit selbst. Studien zur "
            "Schlafregelmässigkeit (u.a. Sleep Regularity Index, Lunsford-Avery "
            "et al., Scientific Reports 2018) zeigen, dass eine hohe Streuung "
            "der Schlafzeiten unabhängig von der Schlafdauer mit ungünstigeren "
            "kardiometabolischen Markern assoziiert ist."
        ),
        "messhinweis": (
            "Dargestellt ist der Beginn des ersten erfassten Schlafsegments. "
            "Nächte ohne getragene Uhr fehlen und dürfen nicht als "
            "'kein Schlaf' gelesen werden."
        ),
        "erklaerung": (
            "Wann du ins Bett gehst - und vor allem, wie stark das schwankt. "
            "Eine geringe Streuung ist günstig für den zirkadianen Rhythmus."
        ),
        "hoch": "Späte Zeiten verschieben den Rhythmus, besonders bei festem Aufstehzeitpunkt.",
        "niedrig": "Sehr frühe Zeiten sind unkritisch, solange sie regelmässig sind.",
    },
    # ---------------- Atmung & Umwelt ----------------
    "respiratory_rate": {
        "label": "Atemfrequenz (Schlaf)",
        "kategorie": "Atmung & Umwelt",
        "hk_type": "HKQuantityTypeIdentifierRespiratoryRate",
        "agg": "avg",
        "einheit": "/min",
        "population": (12, 20),
        "population_label": "Normalbereich Erwachsene in Ruhe",
        "richtung": "neutral",
        "quelle": (
            "12-20 Atemzüge pro Minute gelten als Normalbereich für Erwachsene "
            "in Ruhe (gängige Lehrbuchangabe, Grundlage u.a. der "
            "Frühwarn-Scores wie NEWS)."
        ),
        "messhinweis": (
            "Die Apple Watch schätzt die Atemfrequenz im Schlaf aus "
            "Bewegungs- und Pulssignalen. Sie ist nicht für die Erkennung von "
            "Schlafapnoe oder Atemstörungen validiert."
        ),
        "erklaerung": "Atemzüge pro Minute während des Schlafs.",
        "hoch": (
            "Ein Anstieg über mehrere Nächte kann bei Infekt, Fieber oder "
            "Belastung auftreten. Deutlich erhöhte Werte mit Beschwerden "
            "gehören ärztlich abgeklärt."
        ),
        "niedrig": "Leicht niedrigere Werte sind meist Ausdruck tiefer Entspannung.",
    },
    "spo2": {
        "label": "Sauerstoffsättigung",
        "kategorie": "Atmung & Umwelt",
        "hk_type": "HKQuantityTypeIdentifierOxygenSaturation",
        "agg": "avg",
        "scale": 100,
        "einheit": "%",
        "population": (95, 100),
        "population_label": "Normalbereich (>= 95 %)",
        "richtung": "hoeher_besser",
        "quelle": (
            "Eine periphere Sauerstoffsättigung von 95-100 Prozent gilt bei "
            "Gesunden auf Meereshöhe als normal; Werte unter 90 Prozent gelten "
            "als behandlungsbedürftig abklärungspflichtig (gängige "
            "Lehrbuch- und Leitlinienangabe)."
        ),
        "messhinweis": (
            "Die Blutsauerstoff-Messung der Apple Watch ist ein "
            "Wellness-Feature und ausdrücklich NICHT für medizinische Zwecke "
            "zugelassen. Messungen sind bewegungs-, durchblutungs- und "
            "hautkontaktabhängig; einzelne niedrige Werte sind meist "
            "Messartefakte. In den USA war die Funktion zeitweise durch einen "
            "Patentstreit eingeschränkt - Datenlücken können technische "
            "Ursachen haben."
        ),
        "erklaerung": (
            "Anteil des mit Sauerstoff beladenen Hämoglobins im Blut, optisch "
            "am Handgelenk gemessen."
        ),
        "hoch": "Werte im oberen Normbereich sind unauffällig.",
        "niedrig": (
            "Einzelne niedrige Werte sind meist Messfehler. Wiederholt und "
            "reproduzierbar niedrige Werte, besonders mit Luftnot oder "
            "Tagesmüdigkeit, gehören ärztlich abgeklärt (auch mit Blick auf "
            "eine Schlafapnoe)."
        ),
    },
    "audio_exposure": {
        "label": "Umgebungslautstärke",
        "kategorie": "Atmung & Umwelt",
        "hk_type": "HKQuantityTypeIdentifierEnvironmentalAudioExposure",
        "agg": "avg",
        "einheit": "dB(A)",
        "population": (0, 70),
        "population_label": "unter 70 dB(A) im Tagesmittel unbedenklich",
        "richtung": "niedriger_besser",
        "quelle": (
            "Die WHO nennt einen über 24 Stunden gemittelten Pegel unter "
            "70 dB(A) als Schwelle, unterhalb derer keine Gehörschädigung zu "
            "erwarten ist. Im Arbeitsschutz gilt (NIOSH) ein Grenzwert von "
            "85 dB(A) bei 8 Stunden Expositionsdauer."
        ),
        "messhinweis": (
            "Das Mikrofon der Watch misst nur, wenn sie getragen wird, und "
            "erfasst die Lautstärke am Handgelenk - nicht am Ohr. "
            "Kopfhörer-Lautstärke wird separat erfasst."
        ),
        "erklaerung": (
            "Wie laut deine Umgebung im Tagesmittel ist. Gehörschädigung hängt "
            "von Pegel UND Dauer ab."
        ),
        "hoch": (
            "Hohe Tagesmittel über längere Zeit erhöhen das Risiko für "
            "Hörschäden; kurzfristig können sie Stressreaktionen und "
            "schlechteren Schlaf begünstigen."
        ),
        "niedrig": "Niedrige Werte sind unbedenklich.",
    },
    "daylight": {
        "label": "Zeit im Tageslicht",
        "kategorie": "Atmung & Umwelt",
        "hk_type": "HKQuantityTypeIdentifierTimeInDaylight",
        "agg": "sum",
        "einheit": "min/Tag",
        "population": None,
        "population_label": None,
        "richtung": "hoeher_besser",
        "quelle": (
            "Kein etablierter medizinischer Referenzbereich. Helles Tageslicht "
            "am Morgen ist der stärkste Taktgeber des zirkadianen Rhythmus; in "
            "der Myopie-Prävention bei Kindern werden etwa 2 Stunden täglich "
            "diskutiert. Für Erwachsene existiert keine belastbare Zielgrösse."
        ),
        "messhinweis": (
            "Apple schätzt die Tageslichtzeit über den Umgebungslichtsensor der "
            "Watch. Getragen-werden ist Voraussetzung; lange Ärmel "
            "unterschätzen den Wert systematisch."
        ),
        "erklaerung": (
            "Zeit draussen bei Tageslicht. Wirkt über die innere Uhr auf "
            "Einschlafzeitpunkt und Schlafqualität."
        ),
        "hoch": "Mehr Tageslicht, besonders morgens, stabilisiert den Rhythmus.",
        "niedrig": (
            "Wenig Tageslicht über Wochen (typisch im Winter) geht bei manchen "
            "Menschen mit schlechterem Schlaf und gedrückter Stimmung einher."
        ),
    },
}


# ---------------------------------------------------------------------
# Alters- und geschlechtsabhängige Normwerte
# ---------------------------------------------------------------------

# VO2max in mL/kg/min, Bereich "durchschnittlich bis gut".
# Schlüssel: (Geschlecht, Altersuntergrenze) -> (unten, oben)
#
# Näherung an die Referenztabellen des Cooper Institute / ACSM. Bei
# "divers" oder unbekanntem Geschlecht wird der weibliche Bereich als
# unterer und der männliche als oberer Rand zusammengefasst, damit der
# Bereich niemanden fälschlich als auffällig ausweist.
VO2MAX_NORMEN = {
    ("m", 0): (44, 52),
    ("m", 30): (40, 48),
    ("m", 40): (37, 45),
    ("m", 50): (34, 41),
    ("m", 60): (30, 37),
    ("m", 70): (26, 33),
    ("w", 0): (36, 44),
    ("w", 30): (34, 41),
    ("w", 40): (31, 38),
    ("w", 50): (28, 34),
    ("w", 60): (25, 31),
    ("w", 70): (22, 28),
}

# Empfohlene Schlafdauer in Stunden nach Altersgruppe
# (National Sleep Foundation, Hirshkowitz et al. 2015)
SCHLAF_NORMEN = {
    14: (8, 10),
    18: (7, 9),
    65: (7, 8),
}

# Schrittzahl, ab der der Zusatznutzen abflacht (Paluch et al. 2022)
SCHRITT_NORMEN = {
    0: (8000, 10000),
    60: (6000, 8000),
}


def _aus_altersstaffel(tabelle: dict, alter: int):
    """Passenden Eintrag einer nach Altersuntergrenze gestaffelten Tabelle."""
    passende = [grenze for grenze in tabelle if grenze <= alter]
    if not passende:
        return tabelle[min(tabelle)]
    return tabelle[max(passende)]


def _vo2max_bereich(alter: int, geschlecht: str):
    dekade = min(70, max(0, (alter // 10) * 10))
    if dekade < 30:
        dekade = 0

    if geschlecht in ("m", "w"):
        return VO2MAX_NORMEN[(geschlecht, dekade)], GESCHLECHT_TEXT[geschlecht]

    # Ohne eindeutige Zuordnung: beide Bereiche umspannen
    maennlich = VO2MAX_NORMEN[("m", dekade)]
    weiblich = VO2MAX_NORMEN[("w", dekade)]
    return (
        min(weiblich[0], maennlich[0]),
        max(weiblich[1], maennlich[1]),
    ), "alle Geschlechter zusammengefasst"


GESCHLECHT_TEXT = {"m": "Männer", "w": "Frauen"}


def referenzbereich(key: str, profil: dict = None) -> dict:
    """Referenzbereich einer Kennzahl, auf das Profil angepasst.

    Rückgabe:
        bereich       (unten, oben) oder None
        label         Beschriftung für Legende und Infobox
        angepasst     True, wenn Alter/Geschlecht eingeflossen sind
        hinweis       Text, falls kein Profil vorliegt oder gemittelt wurde
    """
    spec = METRICS[key]
    ergebnis = {
        "bereich": spec.get("population"),
        "label": spec.get("population_label"),
        "angepasst": False,
        "hinweis": None,
    }

    if not spec.get("altersabhaengig"):
        return ergebnis

    alter = (profil or {}).get("alter")
    geschlecht = (profil or {}).get("geschlecht")

    if alter is None:
        ergebnis["hinweis"] = (
            "Für diese Kennzahl hängt der Referenzbereich vom Alter ab. "
            "Ohne hinterlegtes Profil wird der Bereich für Erwachsene "
            "mittleren Alters angezeigt."
        )
        return ergebnis

    if key == "vo2max":
        bereich, gruppe = _vo2max_bereich(alter, geschlecht)
        ergebnis.update(
            {
                "bereich": bereich,
                "label": f"durchschnittlich bis gut ({gruppe}, {_dekade_text(alter)})",
                "angepasst": True,
            }
        )
        if geschlecht not in ("m", "w"):
            ergebnis["hinweis"] = (
                "Ohne eindeutige Geschlechtsangabe umfasst der Bereich die "
                "Normwerte für Frauen und Männer gemeinsam und ist dadurch "
                "breiter als eine geschlechtsspezifische Angabe."
            )
        return ergebnis

    if key == "sleep_hours":
        bereich = _aus_altersstaffel(SCHLAF_NORMEN, alter)
        ergebnis.update(
            {
                "bereich": bereich,
                "label": f"Empfehlung für {alter}-Jährige ({bereich[0]}-{bereich[1]} h)",
                "angepasst": True,
            }
        )
        return ergebnis

    if key == "steps":
        bereich = _aus_altersstaffel(SCHRITT_NORMEN, alter)
        ergebnis.update(
            {
                "bereich": bereich,
                "label": (
                    "Bereich, ab dem der Zusatznutzen abflacht "
                    f"({'ab 60 Jahren' if alter >= 60 else 'unter 60 Jahren'})"
                ),
                "angepasst": True,
            }
        )
        return ergebnis

    return ergebnis


def _dekade_text(alter: int) -> str:
    if alter < 30:
        return "bis 29 Jahre"
    if alter >= 70:
        return "ab 70 Jahre"
    dekade = (alter // 10) * 10
    return f"{dekade}-{dekade + 9} Jahre"


def referenz_text(key: str, profil: dict = None) -> str:
    """Referenzbereich als kurzer Text, z.B. für Tabellen."""
    referenz = referenzbereich(key, profil)
    if not referenz["bereich"]:
        return "nicht anwendbar"
    unten, oben = referenz["bereich"]
    return f"{unten}-{oben} {METRICS[key]['einheit']}"


KATEGORIEN = ["Herz & Kreislauf", "Fitness", "Schlaf", "Atmung & Umwelt"]

# Auf der Statusseite gezeigte Kennzahlen
STATUS_METRICS = [
    "resting_hr",
    "hrv",
    "sleep_hours",
    "steps",
    "exercise_min",
    "respiratory_rate",
]

# Als Kontext bei auffälligen Tagen herangezogen
KONTEXT_METRICS = [
    "sleep_hours",
    "time_in_bed",
    "deep_share",
    "resting_hr",
    "hrv",
    "exercise_min",
    "steps",
    "audio_exposure",
    "daylight",
    "respiratory_rate",
]

# Standardschwelle für Abweichungen, in robusten Standardabweichungen.
#
# Bei normalverteilten Daten wären mit 2 SD rund 5 % der Tage auffällig.
# In diesem Datensatz sind es bei 2 SD etwa 10 %, weil die Verteilungen
# breitere Ränder haben als eine Normalverteilung (und die MAD-basierte
# Streuungsschätzung entsprechend konservativ ist). 3 SD markiert rund
# 3 % der Tage und liefert damit ein brauchbares Signal-Rausch-Verhältnis.
SCHWELLE_STANDARD = 3.0

DISCLAIMER = (
    "Dieses Dashboard wertet Daten von Consumer-Wearables aus. Es ist kein "
    "Medizinprodukt und ersetzt keine ärztliche Diagnostik. Referenzbereiche "
    "gelten für gesunde Erwachsene und sind Orientierung. Aussagekräftig sind "
    "vor allem anhaltende Abweichungen von der eigenen Baseline, nicht "
    "einzelne Tage."
)


def metrics_by_category(kategorie: str) -> dict:
    return {k: v for k, v in METRICS.items() if v["kategorie"] == kategorie}


def label(key: str) -> str:
    return METRICS[key]["label"]
