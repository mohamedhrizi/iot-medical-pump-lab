#!/usr/bin/env python3
"""
Générateur de prescriptions : émet un ORM^O01 (ordre médical) vers le récepteur.
Représente le système de prescription (CPOE / pharmacie) qui prescrit un
médicament à perfuser pour un patient donné. Deuxième étape du cycle de vie.
"""
import socket
import random
import argparse
import logging

from config.settings import RECEIVER_HOST, RECEIVER_PORT, RECEIVER_APP, RECEIVER_FACILITY
from hl7lib import mllp, message

logging.basicConfig(level=logging.INFO, format="%(asctime)s [prescription_gen] %(levelname)s %(message)s")
logger = logging.getLogger("prescription_gen")

DRUG_LIBRARY = [
    {"name": "NaCl 0.9%", "concentration": "N/A", "dose_unit": "mL/h", "flow": 50, "volume": 500},
    {"name": "Noradrenaline", "concentration": "4 mg/50mL", "dose_unit": "mcg/kg/min", "flow": 8, "volume": 50},
    {"name": "Propofol", "concentration": "10 mg/mL", "dose_unit": "mg/kg/h", "flow": 20, "volume": 100},
    {"name": "Insuline Actrapid", "concentration": "1 UI/mL", "dose_unit": "UI/h", "flow": 4, "volume": 50},
    {"name": "Heparine", "concentration": "25000 UI/500mL", "dose_unit": "UI/h", "flow": 25, "volume": 500},
]


def build_orm(order_id, patient_id, drug):
    """Construit un message ORM^O01 (prescription)."""
    msh = message.build_msh(
        sending_app="CPOE-PHARMACY", sending_facility="HOSPITAL",
        receiving_app=RECEIVER_APP, receiving_facility=RECEIVER_FACILITY,
        message_type="ORM^O01", control_id=f"ORM-{order_id}",
    )
    pid = f"PID|1||{patient_id}"
    orc = f"ORC|NW|{order_id}"  # NW = New order
    segs = [
        msh, pid, orc,
        f"OBX|1|ST|DRUG^Medicament||{drug['name']}||||||F",
        f"OBX|2|ST|CONC^Concentration||{drug['concentration']}||||||F",
        f"OBX|3|ST|DOSE_UNIT^Unite||{drug['dose_unit']}||||||F",
        f"OBX|4|NM|FLOW^Flow Rate||{drug['flow']}|mL/h|||||F",
        f"OBX|5|NM|VOL_TOTAL^Volume Total||{drug['volume']}|mL|||||F",
    ]
    return "\r".join(segs) + "\r"


def send(host, port, patient_id, order_id):
    drug = random.choice(DRUG_LIBRARY)
    orm = build_orm(order_id, patient_id, drug)
    with socket.create_connection((host, port), timeout=5) as sock:
        mllp.send_message(sock, orm)
        resp = sock.recv(4096)
        acks, _ = mllp.extract_messages(resp)
        ack_code = "?"
        if acks:
            msa = message.get_segment(message.parse(acks[0]), "MSA")
            ack_code = msa["fields"][1] if msa else "?"
    logger.info("Prescription %s pour %s : %s %dmL/h %dmL — ACK %s",
                order_id, patient_id, drug["name"], drug["flow"], drug["volume"], ack_code)


def main():
    parser = argparse.ArgumentParser(description="Générateur de prescriptions (ORM^O01)")
    parser.add_argument("--host", default=RECEIVER_HOST)
    parser.add_argument("--port", type=int, default=RECEIVER_PORT)
    parser.add_argument("--patient-id", required=True, help="ID du patient à prescrire")
    parser.add_argument("--order-id", default=None, help="ID d'ordre (sinon généré)")
    args = parser.parse_args()

    order_id = args.order_id or f"ORD-{random.randint(10000, 99999)}"
    send(args.host, args.port, args.patient_id, order_id)


if __name__ == "__main__":
    main()
