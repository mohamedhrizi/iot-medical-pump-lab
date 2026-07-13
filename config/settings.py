"""
Configuration centrale du laboratoire IoMT.
Tous les composants importent leurs paramètres d'ici — aucune valeur
réseau ou chemin ne doit être codée en dur ailleurs.
"""
import os

# --- Racine du projet (calculée automatiquement) ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Réseau : récepteur HL7 (MLLP) ---
RECEIVER_HOST = "127.0.0.1"     # côté émetteur (pompe/générateurs)
RECEIVER_BIND = "0.0.0.0"       # côté écoute du récepteur
RECEIVER_PORT = 2575

# --- Réseau : API REST et Dashboard (Flask) ---
# API en boucle locale (surface réduite) ; seul le dashboard est exposé.
API_HOST = "127.0.0.1"
API_PORT = 5000
DASHBOARD_HOST = "0.0.0.0"      # exposé au réseau pour accès depuis l'hôte
DASHBOARD_PORT = 5001
API_BASE_URL = f"http://{API_HOST}:{API_PORT}"

# --- Réseau : canal de commande de la pompe (surface d'attaque OT) ---
# La pompe écoute ici les commandes de reprogrammation (SET_RATE, PAUSE...).
# Non authentifié en baseline : c'est volontaire, c'est la vulnérabilité OT.
PUMP_CMD_BIND = "0.0.0.0"
PUMP_CMD_HOST = "127.0.0.1"
PUMP_CMD_PORT = 9100

# --- Base de données SQLite ---
DB_PATH = os.path.join(BASE_DIR, "db", "iomt.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "db", "schema.sql")

# --- Constantes MLLP (partagées par tous les émetteurs/récepteurs) ---
MLLP_START = b"\x0b"
MLLP_END = b"\x1c\x0d"

# --- Paramètres de simulation ---
SIM_SPEED_FACTOR = 60.0     # accélération temporelle
SEND_INTERVAL_SEC = 10      # intervalle d'émission de la pompe

# --- Identité applicative (champ MSH) ---
RECEIVER_APP = "HL7-RECEIVER"
RECEIVER_FACILITY = "IT-ZONE"
