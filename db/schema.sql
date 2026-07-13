-- Schéma de la base IoMT.
-- Reflète le cycle de vie : admission (patients) -> prescription
-- -> perfusion (infusions) -> suivi (observations, events).
-- SQLite suffit pour le lab ; migration PostgreSQL possible plus tard.

PRAGMA foreign_keys = ON;

-- Patients admis (alimentée par les messages HL7 ADT^A01)
CREATE TABLE IF NOT EXISTS patients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id      TEXT UNIQUE NOT NULL,       -- identifiant métier (ex. PT-00123)
    last_name       TEXT,
    first_name      TEXT,
    birth_date      TEXT,
    sex             TEXT,
    location        TEXT,                       -- chambre/service (ex. ICU-ROOM-04)
    admitted_at     TEXT DEFAULT (datetime('now')),
    status          TEXT DEFAULT 'ADMITTED'     -- ADMITTED / DISCHARGED
);

-- Prescriptions médicales (alimentée par les messages HL7 ORM^O01)
CREATE TABLE IF NOT EXISTS prescriptions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        TEXT UNIQUE NOT NULL,       -- identifiant d'ordre
    patient_id      TEXT NOT NULL,
    drug_name       TEXT NOT NULL,
    concentration   TEXT,
    dose_unit       TEXT,
    flow_rate_ml_h  REAL,                        -- débit prescrit
    volume_total_ml REAL,                        -- volume à perfuser
    status          TEXT DEFAULT 'ACTIVE',       -- ACTIVE / COMPLETED / CANCELLED
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- Perfusions : instance d'exécution d'une prescription par une pompe
CREATE TABLE IF NOT EXISTS infusions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       TEXT NOT NULL,               -- pompe (ex. PUMP-IOMT-01)
    patient_id      TEXT NOT NULL,
    order_id        TEXT,                        -- prescription appliquée
    started_at      TEXT DEFAULT (datetime('now')),
    ended_at        TEXT,
    status          TEXT DEFAULT 'RUNNING',      -- RUNNING / COMPLETE / STOPPED
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- Observations : télémétrie de la pompe (alimentée par les OBX des ORU^R01)
CREATE TABLE IF NOT EXISTS observations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id           TEXT NOT NULL,
    patient_id          TEXT,
    phase               TEXT,                    -- AMORCAGE / DOSE_CHARGE / ENTRETIEN / ...
    status              TEXT,                    -- RUNNING / PAUSED / ALARM_* / COMPLETE
    flow_rate_ml_h      REAL,
    volume_infused_ml   REAL,
    volume_remaining_ml REAL,
    battery_pct         REAL,
    ac_connected        TEXT,
    received_at         TEXT DEFAULT (datetime('now'))
);

-- Events : alarmes et évènements cliniques (dérivés du statut des observations)
CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       TEXT NOT NULL,
    patient_id      TEXT,
    event_type      TEXT NOT NULL,               -- ex. ALARM_OCCLUSION, PAUSED, PHASE_CHANGE
    priority        TEXT,                        -- HAUTE / MOYENNE / BASSE
    detail          TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Index utiles pour le dashboard (requêtes fréquentes par patient et par récence)
CREATE INDEX IF NOT EXISTS idx_obs_device_time ON observations(device_id, received_at);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_presc_patient ON prescriptions(patient_id, status);
