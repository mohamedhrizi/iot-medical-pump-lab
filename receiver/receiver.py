"""
Récepteur HL7/MLLP enrichi.
Évolution du récepteur d'origine :
  - multi-thread (un thread par connexion : pompe + générateurs en parallèle)
  - parsing HL7 via hl7lib
  - routage par type de message (ADT / ORM / ORU) vers la base
  - ACK renvoyé à l'émetteur (comportement HL7 réel)
Il joue le rôle de mini-moteur d'intégration du lab.
"""
import socket
import threading
import logging

from config.settings import (
    RECEIVER_BIND, RECEIVER_PORT, RECEIVER_APP, RECEIVER_FACILITY,
)
from hl7lib import mllp, message
from db import store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [receiver] %(levelname)s %(message)s",
    handlers=[logging.FileHandler("receiver.log"), logging.StreamHandler()],
)
logger = logging.getLogger("receiver")

# Priorités d'alarme (miroir de celles de la pompe, pour enrichir les events)
ALARM_PRIORITY = {
    "ALARM_OCCLUSION": "HAUTE",
    "ALARM_AIR_IN_LINE": "HAUTE",
    "ALARM_LOW_VOLUME": "MOYENNE",
    "ALARM_LOW_BATTERY": "MOYENNE",
    "ALARM_AC_DISCONNECTED": "BASSE",
}


def _obx_value(parsed, code):
    """Récupère la valeur (OBX-5) d'un OBX dont l'identifiant (OBX-3) commence par `code`."""
    for obx in message.get_segments(parsed, "OBX"):
        if len(obx["fields"]) > 5 and obx["fields"][3].startswith(code):
            return obx["fields"][5]
    return None


def _patient_id(parsed):
    pid = message.get_segment(parsed, "PID")
    if pid and len(pid["fields"]) > 3:
        return pid["fields"][3]
    return None


def handle_oru(parsed):
    """Traite un ORU^R01 (télémétrie pompe) : observation + event si alarme."""
    msh = message.get_segment(parsed, "MSH")
    device_id = msh["fields"][2] if msh and len(msh["fields"]) > 2 else "UNKNOWN"
    patient_id = _patient_id(parsed)

    phase = _obx_value(parsed, "PHASE")
    status = _obx_value(parsed, "STATUS")

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    store.insert_observation(
        device_id=device_id,
        patient_id=patient_id,
        phase=phase,
        status=status,
        flow_rate_ml_h=num(_obx_value(parsed, "FLOW")),
        volume_infused_ml=num(_obx_value(parsed, "VOL_INF")),
        volume_remaining_ml=num(_obx_value(parsed, "VOL_REM")),
        battery_pct=num(_obx_value(parsed, "BATTERY")),
        ac_connected=_obx_value(parsed, "AC_POWER"),
    )

    # un statut d'alarme génère aussi un event tracé
    if status and status.startswith("ALARM"):
        store.insert_event(device_id, patient_id, status,
                           priority=ALARM_PRIORITY.get(status, "?"),
                           detail=f"phase={phase}")
    logger.info("ORU traité - device=%s patient=%s phase=%s status=%s",
                device_id, patient_id, phase, status)


def handle_adt(parsed):
    """Traite un ADT^A01 (admission patient)."""
    pid = message.get_segment(parsed, "PID")
    if not pid or len(pid["fields"]) < 6:
        logger.warning("ADT sans PID exploitable")
        return
    patient_id = pid["fields"][3]
    name = pid["fields"][5].split("^") if len(pid["fields"]) > 5 else []
    last_name = name[0] if len(name) > 0 else None
    first_name = name[1] if len(name) > 1 else None
    birth = pid["fields"][7] if len(pid["fields"]) > 7 else None
    sex = pid["fields"][8] if len(pid["fields"]) > 8 else None
    store.upsert_patient(patient_id, last_name, first_name, birth, sex)
    logger.info("ADT traité - admission patient=%s (%s %s)", patient_id, first_name, last_name)


def handle_orm(parsed):
    """Traite un ORM^O01 (prescription)."""
    patient_id = _patient_id(parsed)
    orc = message.get_segment(parsed, "ORC")
    order_id = orc["fields"][2] if orc and len(orc["fields"]) > 2 else None

    drug = _obx_value(parsed, "DRUG")
    conc = _obx_value(parsed, "CONC")
    unit = _obx_value(parsed, "DOSE_UNIT")
    flow = _obx_value(parsed, "FLOW")
    vol = _obx_value(parsed, "VOL_TOTAL")

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    if order_id and patient_id:
        store.insert_prescription(order_id, patient_id, drug, conc, unit,
                                  num(flow), num(vol))
        logger.info("ORM traité - prescription %s patient=%s drug=%s", order_id, patient_id, drug)
    else:
        logger.warning("ORM incomplet (order_id ou patient manquant)")


def route(parsed):
    """Aiguille le message vers le bon traitement selon MSH-9 (type de message)."""
    msh = message.get_segment(parsed, "MSH")
    msg_type = msh["fields"][8] if msh and len(msh["fields"]) > 8 else ""
    if msg_type.startswith("ORU"):
        handle_oru(parsed)
    elif msg_type.startswith("ADT"):
        handle_adt(parsed)
    elif msg_type.startswith("ORM"):
        handle_orm(parsed)
    else:
        logger.warning("Type de message non géré : %s", msg_type)


def handle_client(conn, addr):
    """Boucle de réception pour une connexion (exécutée dans son propre thread)."""
    logger.info("Connexion de %s:%s", addr[0], addr[1])
    buffer = b""
    with conn:
        while True:
            try:
                chunk = conn.recv(4096)
            except OSError:
                break
            if not chunk:
                logger.info("Connexion fermée par %s:%s", addr[0], addr[1])
                break
            buffer += chunk
            messages, buffer = mllp.extract_messages(buffer)
            for raw in messages:
                try:
                    parsed = message.parse(raw)
                    route(parsed)
                    # ACK renvoyé à l'émetteur
                    ack = message.build_ack(parsed, "AA")
                    mllp.send_message(conn, ack)
                except Exception as e:
                    logger.error("Erreur de traitement : %s", e)
                    try:
                        parsed = message.parse(raw)
                        mllp.send_message(conn, message.build_ack(parsed, "AE"))
                    except Exception:
                        pass


def run():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((RECEIVER_BIND, RECEIVER_PORT))
        s.listen(5)
        logger.info("Récepteur %s@%s en écoute sur %s:%s (MLLP)",
                    RECEIVER_APP, RECEIVER_FACILITY, RECEIVER_BIND, RECEIVER_PORT)
        while True:
            conn, addr = s.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()


if __name__ == "__main__":
    run()
