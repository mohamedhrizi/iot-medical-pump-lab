"""
Requêtes de lecture sur la base SQLite.
Séparé de store.py (écritures) pour garder une frontière nette :
l'API lit via queries, le récepteur écrit via store. Un seul module
de lecture = un seul endroit à contrôler quand on ajoutera l'auth.
"""
import sqlite3
from config.settings import DB_PATH


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row   # accès aux colonnes par nom
    return conn


def _rows(cur):
    return [dict(r) for r in cur.fetchall()]


def list_patients():
    with _connect() as conn:
        cur = conn.execute("""
            SELECT patient_id, first_name, last_name, sex, location, status, admitted_at
            FROM patients ORDER BY admitted_at DESC
        """)
        return _rows(cur)


def list_prescriptions():
    with _connect() as conn:
        cur = conn.execute("""
            SELECT order_id, patient_id, drug_name, concentration, dose_unit,
                   flow_rate_ml_h, volume_total_ml, status, created_at
            FROM prescriptions ORDER BY created_at DESC
        """)
        return _rows(cur)


def get_active_prescription(patient_id):
    """Prescription ACTIVE la plus récente d'un patient — utilisée par la pompe."""
    with _connect() as conn:
        cur = conn.execute("""
            SELECT order_id, patient_id, drug_name, concentration, dose_unit,
                   flow_rate_ml_h, volume_total_ml
            FROM prescriptions
            WHERE patient_id = ? AND status = 'ACTIVE'
            ORDER BY created_at DESC LIMIT 1
        """, (patient_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_active_infusions():
    """
    Perfusions « en cours » = dernière observation connue de chaque pompe.
    On joint chaque device à son observation la plus récente (MAX(id)).
    C'est ce que le dashboard affichera comme état temps quasi réel.
    """
    with _connect() as conn:
        cur = conn.execute("""
            SELECT o.device_id, o.patient_id, o.phase, o.status, o.flow_rate_ml_h,
                   o.volume_infused_ml, o.volume_remaining_ml, o.battery_pct,
                   o.ac_connected, o.received_at
            FROM observations o
            JOIN (
                SELECT device_id, MAX(id) AS max_id
                FROM observations GROUP BY device_id
            ) latest ON o.id = latest.max_id
            ORDER BY o.received_at DESC
        """)
        return _rows(cur)


def list_alarms(limit=20):
    """Évènements récents (alarmes, pauses, etc.), les plus récents d'abord."""
    with _connect() as conn:
        cur = conn.execute("""
            SELECT device_id, patient_id, event_type, priority, detail, created_at
            FROM events ORDER BY id DESC LIMIT ?
        """, (limit,))
        return _rows(cur)
