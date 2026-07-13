#!/usr/bin/env python3
"""
Simulateur de pompe à perfusion IoMT (HL7/MLLP) - baseline étape 8bis.
= étape 7bis (pilotage par prescription) + CANAL DE COMMANDE OT.
La pompe émet sa télémétrie (thread principal) et écoute des commandes de
reprogrammation (thread canal de commande). État partagé protégé par un verrou.
Canal NON authentifié : surface d'attaque OT volontaire (durcissement plus tard).
"""
import json
import time
import random
import socket
import logging
import argparse
import threading
import urllib.request
import urllib.parse
from security.audit import audit
from dataclasses import dataclass, field

from config.settings import (
    RECEIVER_HOST, RECEIVER_PORT, SEND_INTERVAL_SEC, SIM_SPEED_FACTOR,
    RECEIVER_APP, RECEIVER_FACILITY, API_BASE_URL,
    PUMP_CMD_BIND, PUMP_CMD_PORT,
)
from hl7lib import mllp, message

PROB_OCCLUSION = 0.004
PROB_AIR_IN_LINE = 0.003
PROB_AC_DISCONNECT = 0.002
PROB_AC_RECONNECT = 0.15
PROB_NURSE_PAUSE = 0.002
FLOW_JITTER_PCT = 0.02

ALARM_PRIORITY = {
    "ALARM_OCCLUSION": "HAUTE",
    "ALARM_AIR_IN_LINE": "HAUTE",
    "ALARM_LOW_VOLUME": "MOYENNE",
    "ALARM_LOW_BATTERY": "MOYENNE",
    "ALARM_AC_DISCONNECTED": "BASSE",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [pump_sim] %(levelname)s %(message)s",
    handlers=[logging.FileHandler("pump_sim.log"), logging.StreamHandler()],
)
logger = logging.getLogger("pump_sim")


@dataclass
class DeviceInfo:
    device_id: str = "PUMP-IOMT-01"
    serial_number: str = "SN-2026-0417"
    firmware_version: str = "3.2.1"
    manufacturer: str = "SimuMed"
    model: str = "InfusionSim-500"
    location: str = "ICU-ROOM-04"


@dataclass
class PumpState:
    phase: str = "AMORCAGE"
    drug: dict = field(default_factory=lambda: {"name": "NaCl 0.9%", "concentration": "N/A", "dose_unit": "mL/h"})
    flow_rate_ml_h: float = 50.0
    loading_dose_rate_ml_h: float = 120.0
    kvo_rate_ml_h: float = 5.0
    volume_total_ml: float = 500.0
    volume_infused_ml: float = 0.0
    status: str = "RUNNING"
    patient_id: str = "PT-50001"
    msg_seq: int = 0
    battery_pct: float = 100.0
    ac_connected: bool = True
    phase_elapsed_sec: float = 0.0
    amorcage_duration_sec: float = 120.0
    dose_charge_duration_sec: float = 600.0
    alarms_enabled: bool = True
    stopped: bool = False

    def remaining_volume(self):
        return max(0.0, self.volume_total_ml - self.volume_infused_ml)

    def current_target_rate(self):
        if self.phase == "AMORCAGE":
            return 0.0
        if self.phase == "DOSE_CHARGE":
            return self.loading_dose_rate_ml_h
        if self.phase == "MAINTIEN_VOIE":
            return self.kvo_rate_ml_h
        return self.flow_rate_ml_h

    def _update_battery(self, elapsed):
        if self.ac_connected:
            self.battery_pct = min(100.0, self.battery_pct + (elapsed / 60.0) * 0.5)
        else:
            self.battery_pct = max(0.0, self.battery_pct - (elapsed / 60.0) * 0.3)
        if self.ac_connected and random.random() < PROB_AC_DISCONNECT:
            self.ac_connected = False
        elif not self.ac_connected and random.random() < PROB_AC_RECONNECT:
            self.ac_connected = True

    def tick(self, elapsed):
        simulated = elapsed * SIM_SPEED_FACTOR
        self._update_battery(simulated)
        if self.stopped:
            self.status = "STOPPED"
            return
        if self.status == "PAUSED":
            return
        if self.status.startswith("ALARM"):
            return
        self.phase_elapsed_sec += simulated
        if self.phase == "AMORCAGE" and self.phase_elapsed_sec >= self.amorcage_duration_sec:
            self.phase = "DOSE_CHARGE"
            self.phase_elapsed_sec = 0.0
            logger.info("Transition : AMORCAGE -> DOSE_CHARGE")
        elif self.phase == "DOSE_CHARGE" and self.phase_elapsed_sec >= self.dose_charge_duration_sec:
            self.phase = "ENTRETIEN"
            self.phase_elapsed_sec = 0.0
            logger.info("Transition : DOSE_CHARGE -> ENTRETIEN")
        rate = self.current_target_rate()
        jitter = 1.0 + random.uniform(-FLOW_JITTER_PCT, FLOW_JITTER_PCT)
        self.volume_infused_ml += rate * jitter * simulated / 3600.0
        if self.alarms_enabled and self.phase in ("DOSE_CHARGE", "ENTRETIEN"):
            if random.random() < PROB_OCCLUSION:
                self.status = "ALARM_OCCLUSION"
                return
            if random.random() < PROB_AIR_IN_LINE:
                self.status = "ALARM_AIR_IN_LINE"
                return
            if random.random() < PROB_NURSE_PAUSE:
                self.status = "PAUSED"
                return
        if self.alarms_enabled and self.battery_pct <= 15 and not self.ac_connected:
            self.status = "ALARM_LOW_BATTERY"
            return
        if self.alarms_enabled and not self.ac_connected:
            self.status = "ALARM_AC_DISCONNECTED"
        else:
            self.status = "RUNNING"
        remaining = self.remaining_volume()
        if self.phase == "ENTRETIEN" and remaining < 20:
            self.phase = "MAINTIEN_VOIE"
            logger.info("Transition : ENTRETIEN -> MAINTIEN_VOIE (KVO)")
        elif self.phase == "MAINTIEN_VOIE" and remaining <= 0:
            self.volume_infused_ml = self.volume_total_ml
            self.phase = "TERMINE"
            self.status = "COMPLETE"


def apply_prescription(state, patient_id):
    state.patient_id = patient_id
    url = f"{API_BASE_URL}/api/prescriptions/active?" + urllib.parse.urlencode({"patient_id": patient_id})
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not data:
            logger.warning("Aucune prescription active pour %s — valeurs par défaut", patient_id)
            return
        state.drug = {
            "name": data.get("drug_name", "NaCl 0.9%"),
            "concentration": data.get("concentration", "N/A"),
            "dose_unit": data.get("dose_unit", "mL/h"),
        }
        if data.get("flow_rate_ml_h"):
            state.flow_rate_ml_h = float(data["flow_rate_ml_h"])
        if data.get("volume_total_ml"):
            state.volume_total_ml = float(data["volume_total_ml"])
        logger.info("Prescription appliquée : %s %.1f mL/h, %.0f mL (patient %s)",
                    state.drug["name"], state.flow_rate_ml_h, state.volume_total_ml, patient_id)
    except Exception as e:
        logger.warning("Échec récupération prescription (%s) — valeurs par défaut", e)


def build_hl7_oru(state, device):
    state.msg_seq += 1
    msg_id = f"{device.device_id}-{state.msg_seq:08d}"
    priority = ALARM_PRIORITY.get(state.status, "")
    msh = message.build_msh(
        sending_app=device.device_id, sending_facility=device.location,
        receiving_app=RECEIVER_APP, receiving_facility=RECEIVER_FACILITY,
        message_type="ORU^R01", control_id=msg_id,
    )
    segments = [
        msh,
        f"PID|1||{state.patient_id}||DOE^JOHN||19800101|M",
        f"OBR|1|{msg_id}||INFUSION^Infusion Monitoring",
        f"OBX|1|ST|DRUG^Medicament||{state.drug['name']}||||||F",
        f"OBX|2|ST|CONC^Concentration||{state.drug['concentration']}||||||F",
        f"OBX|3|ST|PHASE^Phase clinique||{state.phase}||||||F",
        f"OBX|4|NM|FLOW^Flow Rate||{state.current_target_rate():.1f}|mL/h|||||F",
        f"OBX|5|NM|VOL_INF^Volume Infused||{state.volume_infused_ml:.1f}|mL|||||F",
        f"OBX|6|NM|VOL_REM^Volume Remaining||{state.remaining_volume():.1f}|mL|||||F",
        f"OBX|7|ST|STATUS^Device Status||{state.status}||||||F",
        f"OBX|8|ST|ALARM_PRIO^Alarm Priority||{priority}||||||F",
        f"OBX|9|NM|BATTERY^Battery Level||{state.battery_pct:.0f}|%|||||F",
        f"OBX|10|ST|AC_POWER^AC Power Connected||{'YES' if state.ac_connected else 'NO'}||||||F",
    ]
    return "\r".join(segments) + "\r"


def apply_command(state, lock, command, src_ip):
    parts = command.strip().split("|")
    verb = parts[0].upper()

    with lock:

        if verb == "SET_RATE" and len(parts) >= 2:
            try:
                new_rate = float(parts[1])
            except ValueError:
                audit(
                    "pump.command_rejected",
                    component="pump",
                    src_ip=src_ip,
                    command="SET_RATE",
                    reason="valeur_invalide",
                    raw=parts[1],
                )
                return "ERR|valeur invalide"

            old = state.flow_rate_ml_h
            state.flow_rate_ml_h = new_rate

            audit(
                "pump.command",
                component="pump",
                src_ip=src_ip,
                device_id="PUMP-IOMT-01",
                patient_id=state.patient_id,
                command="SET_RATE",
                old_rate=old,
                new_rate=new_rate,
            )

            logger.warning(
                "COMMANDE SET_RATE de %s : %.1f -> %.1f mL/h",
                src_ip,
                old,
                new_rate,
            )

            return f"OK|rate={new_rate}"

        if verb == "PAUSE":
            state.status = "PAUSED"

            audit(
                "pump.command",
                component="pump",
                src_ip=src_ip,
                patient_id=state.patient_id,
                command="PAUSE",
            )

            logger.warning("COMMANDE PAUSE de %s", src_ip)
            return "OK|paused"

        if verb == "RESUME":
            state.status = "RUNNING"
            state.stopped = False

            audit(
                "pump.command",
                component="pump",
                src_ip=src_ip,
                patient_id=state.patient_id,
                command="RESUME",
            )

            logger.warning("COMMANDE RESUME de %s", src_ip)
            return "OK|resumed"

        if verb == "DISABLE_ALARM":
            state.alarms_enabled = False

            audit(
                "pump.command",
                component="pump",
                src_ip=src_ip,
                patient_id=state.patient_id,
                command="DISABLE_ALARM",
                severity="critical",
            )

            logger.warning(
                "COMMANDE DISABLE_ALARM de %s — securite desactivee",
                src_ip,
            )

            return "OK|alarms_disabled"

        if verb == "ENABLE_ALARM":
            state.alarms_enabled = True

            audit(
                "pump.command",
                component="pump",
                src_ip=src_ip,
                patient_id=state.patient_id,
                command="ENABLE_ALARM",
            )

            logger.warning("COMMANDE ENABLE_ALARM de %s", src_ip)
            return "OK|alarms_enabled"

        if verb == "STOP":
            state.stopped = True

            audit(
                "pump.command",
                component="pump",
                src_ip=src_ip,
                patient_id=state.patient_id,
                command="STOP",
                severity="critical",
            )

            logger.warning("COMMANDE STOP de %s", src_ip)
            return "OK|stopped"

        audit(
            "pump.command_rejected",
            component="pump",
            src_ip=src_ip,
            command=verb,
            reason="commande_inconnue",
        )

        return "ERR|commande inconnue"


def _handle_command_conn(conn, addr, state, lock):
    src_ip = addr[0]
    with conn:
        try:
            data = conn.recv(1024).decode("utf-8", errors="replace").strip()
        except OSError:
            return
        if not data:
            return
        response = apply_command(state, lock, data, src_ip)
        conn.sendall((response + "\n").encode("utf-8"))


def command_server(state, lock):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((PUMP_CMD_BIND, PUMP_CMD_PORT))
        s.listen(5)
        logger.info("Canal de commande en écoute sur %s:%s [BASELINE non authentifié]",
                    PUMP_CMD_BIND, PUMP_CMD_PORT)
        while True:
            conn, addr = s.accept()
            threading.Thread(target=_handle_command_conn,
                             args=(conn, addr, state, lock), daemon=True).start()


def telemetry_loop(state, device, lock, receiver_host, receiver_port):
    while True:
        try:
            with socket.create_connection((receiver_host, receiver_port), timeout=5) as sock:
                logger.info("Connecté au récepteur %s:%s", receiver_host, receiver_port)
                while True:
                    with lock:
                        state.tick(SEND_INTERVAL_SEC)
                        hl7_msg = build_hl7_oru(state, device)
                        snap = (state.phase, state.status, state.current_target_rate(),
                                state.remaining_volume(), state.battery_pct, state.ac_connected)
                    mllp.send_message(sock, hl7_msg)
                    try:
                        sock.settimeout(3)
                        resp = sock.recv(4096)
                        acks, _ = mllp.extract_messages(resp)
                        if acks:
                            msa = message.get_segment(message.parse(acks[0]), "MSA")
                            logger.info("ACK reçu : %s", msa["fields"][1] if msa else "?")
                    except socket.timeout:
                        logger.warning("Pas d'ACK reçu (timeout)")

                    phase, status, rate, remaining, batt, ac = snap
                    if status == "RUNNING":
                        logger.info("Envoyé - phase=%s débit=%.1f restant=%.1fmL batterie=%.0f%% AC=%s",
                                    phase, rate, remaining, batt, "ON" if ac else "OFF")
                    elif status == "PAUSED":
                        logger.info("En pause")
                    elif status == "STOPPED":
                        logger.warning("Pompe ARRÊTÉE (commande STOP)")
                    else:
                        logger.warning("ALARME [%s] - status=%s", ALARM_PRIORITY.get(status, "?"), status)

                    if status == "COMPLETE":
                        logger.info("Perfusion terminée, reset dans 3s")
                        time.sleep(3)
                        with lock:
                            pid = state.patient_id
                            state.__init__()
                            state.patient_id = pid
                    elif status == "PAUSED":
                        time.sleep(8)
                        with lock:
                            if state.status == "PAUSED":
                                state.status = "RUNNING"
                    elif status.startswith("ALARM"):
                        time.sleep(5)
                        with lock:
                            if state.status != "ALARM_LOW_BATTERY" or state.ac_connected:
                                state.status = "RUNNING"

                    time.sleep(SEND_INTERVAL_SEC)
        except (ConnectionRefusedError, socket.timeout, OSError) as e:
            logger.error("Connexion échouée (%s), retry dans 5s...", e)
            time.sleep(5)


def run(receiver_host, receiver_port, patient_id=None):
    device = DeviceInfo()
    state = PumpState()
    lock = threading.Lock()
    if patient_id:
        apply_prescription(state, patient_id)
    logger.info("Démarrage pompe - device=%s patient=%s médicament=%s",
                device.device_id, state.patient_id, state.drug["name"])
    threading.Thread(target=command_server, args=(state, lock), daemon=True).start()
    telemetry_loop(state, device, lock, receiver_host, receiver_port)


def main():
    parser = argparse.ArgumentParser(description="Simulateur de pompe IoMT (HL7/MLLP) - etape 8bis")
    parser.add_argument("--host", default=RECEIVER_HOST)
    parser.add_argument("--port", type=int, default=RECEIVER_PORT)
    parser.add_argument("--patient-id", default=None, help="Patient dont on applique la prescription")
    args = parser.parse_args()
    run(args.host, args.port, args.patient_id)


if __name__ == "__main__":
    main()
