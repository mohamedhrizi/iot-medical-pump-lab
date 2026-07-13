"""
Accès à la base SQLite. Centralise toutes les écritures pour que le reste
du code n'ait jamais à écrire de SQL en dur. Un seul point d'entrée = un
seul endroit à sécuriser/auditer plus tard.
"""
import sqlite3
from config.settings import DB_PATH


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def upsert_patient(patient_id, last_name=None, first_name=None,
                   birth_date=None, sex=None, location=None):
    """Insère un patient admis, ou met à jour ses infos s'il existe déjà."""
    with _connect() as conn:
        conn.execute("""
            INSERT INTO patients (patient_id, last_name, first_name, birth_date, sex, location)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(patient_id) DO UPDATE SET
                last_name=excluded.last_name,
                first_name=excluded.first_name,
                location=excluded.location
        """, (patient_id, last_name, first_name, birth_date, sex, location))


def insert_prescription(order_id, patient_id, drug_name, concentration,
                        dose_unit, flow_rate_ml_h, volume_total_ml):
    """Enregistre une prescription (ORM^O01)."""
    with _connect() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO prescriptions
                (order_id, patient_id, drug_name, concentration, dose_unit,
                 flow_rate_ml_h, volume_total_ml)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (order_id, patient_id, drug_name, concentration, dose_unit,
              flow_rate_ml_h, volume_total_ml))


def insert_observation(device_id, patient_id, phase, status, flow_rate_ml_h,
                       volume_infused_ml, volume_remaining_ml, battery_pct, ac_connected):
    """Enregistre une observation de télémétrie pompe (issue d'un ORU^R01)."""
    with _connect() as conn:
        conn.execute("""
            INSERT INTO observations
                (device_id, patient_id, phase, status, flow_rate_ml_h,
                 volume_infused_ml, volume_remaining_ml, battery_pct, ac_connected)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (device_id, patient_id, phase, status, flow_rate_ml_h,
              volume_infused_ml, volume_remaining_ml, battery_pct, ac_connected))


def insert_event(device_id, patient_id, event_type, priority=None, detail=None):
    """Enregistre un évènement clinique (alarme, pause, changement de phase)."""
    with _connect() as conn:
        conn.execute("""
            INSERT INTO events (device_id, patient_id, event_type, priority, detail)
            VALUES (?, ?, ?, ?, ?)
        """, (device_id, patient_id, event_type, priority, detail))
