-- Schema für Apple-Health-Export-Daten

-- ---------------------------------------------------------------
-- Rohdaten
-- ---------------------------------------------------------------

CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    source_name TEXT,
    unit TEXT,
    value REAL,
    value_text TEXT,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    creation_date TEXT,
    UNIQUE (type, source_name, start_date, end_date, value_text)
);

CREATE INDEX IF NOT EXISTS idx_records_type_start ON records (type, start_date);

-- Trainingseinheiten (<Workout>-Elemente)
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_type TEXT NOT NULL,
    source_name TEXT,
    duration_min REAL,
    distance_km REAL,
    energy_kcal REAL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    UNIQUE (activity_type, source_name, start_date, end_date)
);

CREATE INDEX IF NOT EXISTS idx_workouts_start ON workouts (start_date);

-- Aktivitätsringe pro Tag (<ActivitySummary>-Elemente), inkl. Tagesziele
CREATE TABLE IF NOT EXISTS activity_summaries (
    date TEXT PRIMARY KEY,
    active_energy_kcal REAL,
    active_energy_goal REAL,
    exercise_min REAL,
    exercise_goal REAL,
    stand_hours REAL,
    stand_goal REAL,
    move_min REAL,
    move_goal REAL
);

CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    records_seen INTEGER,
    records_inserted INTEGER,
    workouts_inserted INTEGER,
    summaries_inserted INTEGER
);

-- ---------------------------------------------------------------
-- Aggregate (von build_daily.py befüllt)
--
-- Das Dashboard liest fast ausschliesslich hieraus. Rohdaten nur,
-- wenn in einen einzelnen Tag gezoomt wird.
-- ---------------------------------------------------------------

CREATE TABLE IF NOT EXISTS daily_metrics (
    date TEXT NOT NULL,
    type TEXT NOT NULL,
    unit TEXT,
    n INTEGER,
    total REAL,
    avg REAL,
    min REAL,
    max REAL,
    PRIMARY KEY (date, type)
);

CREATE INDEX IF NOT EXISTS idx_daily_metrics_type_date ON daily_metrics (type, date);

-- Schlaf pro Nacht. date = Morgen des Aufwachens, damit eine Nacht
-- eine Zeile ist und sich sauber mit dem Folgetag verknüpfen lässt.
CREATE TABLE IF NOT EXISTS daily_sleep (
    date TEXT PRIMARY KEY,
    in_bed_min REAL,
    asleep_min REAL,
    core_min REAL,
    deep_min REAL,
    rem_min REAL,
    awake_min REAL,
    bedtime TEXT,
    wake_time TEXT
);
