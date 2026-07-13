#!/usr/bin/env python3
"""
Générateur de patients : émet un ADT^A01 (admission) vers le récepteur HL7.
Représente le système d'admission hospitalier (SIH) qui déclare un nouveau
patient. Point de départ du cycle de vie : admission -> prescription -> perfusion.
"""
import socket
import random
import argparse
import logging

from config.settings import RECEIVER_HOST, RECEIVER_PORT, RECEIVER_APP, RECEIVER_FACILITY
from hl7lib import mllp, message

logging.basicConfig(level=logging.INFO, format="%(asctime)s [patient_gen] %(levelname)s %(message)s")
logger = logging.getLogger("patient_gen")

LAST_NAMES = ["MARTIN", "BERNARD", "DUBOIS", "PETIT", "DURAND", "MOREAU"]
FIRST_NAMES = ["JEAN", "MARIE", "PIERRE", "SOPHIE", "PAUL", "CLAIRE"]
SEXES = ["M", "F"]
ROOMS = ["ICU-ROOM-01", "ICU-ROOM-02", "ICU-ROOM-03", "ICU-ROOM-04"]


def build_adt(patient_id, last_name, first_name, birth_date, sex, location):
    """Construit un message ADT^A01 (admission patient)."""
    msh = message.build_msh(
        sending_app="SIH-ADMISSION", sending_facility="HOSPITAL",
        receiving_app=RECEIVER_APP, receiving_facility=RECEIVER_FACILITY,
        message_type="ADT^A01", control_id=f"ADT-{patient_id}",
    )
    pid = f"PID|1||{patient_id}||{last_name}^{first_name}||{birth_date}|{sex}"
    pv1 = f"PV1|1|I|{location}"  # PV1 = visite ; I = Inpatient (hospitalisé)
    return "\r".join([msh, pid, pv1]) + "\r"


def send(host, port, patient_id):
    last_name = random.choice(LAST_NAMES)
    first_name = random.choice(FIRST_NAMES)
    birth_date = f"19{random.randint(40,99)}{random.randint(1,12):02d}{random.randint(1,28):02d}"
    sex = random.choice(SEXES)
    location = random.choice(ROOMS)

    adt = build_adt(patient_id, last_name, first_name, birth_date, sex, location)
    with socket.create_connection((host, port), timeout=5) as sock:
        mllp.send_message(sock, adt)
        resp = sock.recv(4096)
        acks, _ = mllp.extract_messages(resp)
        ack_code = "?"
        if acks:
            msa = message.get_segment(message.parse(acks[0]), "MSA")
            ack_code = msa["fields"][1] if msa else "?"
    logger.info("Patient admis %s : %s %s (%s, %s) — ACK %s",
                patient_id, first_name, last_name, sex, location, ack_code)
    return patient_id


def main():
    parser = argparse.ArgumentParser(description="Générateur de patients (ADT^A01)")
    parser.add_argument("--host", default=RECEIVER_HOST)
    parser.add_argument("--port", type=int, default=RECEIVER_PORT)
    parser.add_argument("--patient-id", default=None, help="ID patient (sinon généré)")
    args = parser.parse_args()

    patient_id = args.patient_id or f"PT-{random.randint(10000, 99999)}"
    send(args.host, args.port, patient_id)


if __name__ == "__main__":
    main()
