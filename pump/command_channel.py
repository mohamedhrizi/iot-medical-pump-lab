#!/usr/bin/env python3
"""
Canal de commande de la pompe (etape 8bis) - surface d'attaque OT.

Modelise le canal de programmation a distance d'une vraie pompe connectee
(cf. vulnerabilites documentees sur pompes Alaris/Baxter/B.Braun : commande
a distance, manipulation de debit). Volontairement NON authentifie a ce
stade -- c'est le baseline vulnerable, durci en Phase 3.

Commandes texte, une par ligne, format : COMMANDE [ARGUMENT]
  SET_RATE <valeur>     - modifie le debit courant (mL/h)
  PAUSE                 - met la pompe en pause
  RESUME                - relance la pompe
  DISABLE_ALARM         - desactive la remontee d'alarme (masque l'etat reel)
  STATUS                - retourne l'etat courant en texte

Le serveur tourne dans un thread separe, partage l'objet PumpState avec
la boucle principale de telemetrie via un verrou (Lock).
"""

import socket
import threading
import logging

logger = logging.getLogger("pump_sim.command_channel")


class CommandChannel:
    """
    Serveur TCP texte simple, une connexion a la fois, qui applique des
    commandes sur un objet PumpState partage (thread-safe via lock).
    """

    def __init__(self, pump_state, lock: threading.Lock, host="0.0.0.0", port=6001):
        self.pump_state = pump_state
        self.lock = lock
        self.host = host
        self.port = port
        self._server_socket = None

    def start(self):
        thread = threading.Thread(target=self._serve_forever, daemon=True)
        thread.start()
        logger.warning(
            "Canal de commande demarre sur %s:%s -- AUCUNE AUTHENTIFICATION (baseline vulnerable)",
            self.host, self.port,
        )

    def _serve_forever(self):
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(5)

        while True:
            conn, addr = self._server_socket.accept()
            logger.info("Connexion canal de commande depuis %s:%s", addr[0], addr[1])
            with conn:
                buffer = b""
                while True:
                    chunk = conn.recv(1024)
                    if not chunk:
                        break
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        response = self._handle_line(line.decode("utf-8", errors="replace").strip(), addr[0])
                        if response:
                            conn.sendall((response + "\n").encode("utf-8"))

    def _handle_line(self, line: str, source_ip: str) -> str:
        if not line:
            return ""
        parts = line.split()
        cmd = parts[0].upper()

        with self.lock:
            if cmd == "SET_RATE" and len(parts) == 2:
                try:
                    new_rate = float(parts[1])
                except ValueError:
                    return "ERR valeur invalide"
                old_rate = self.pump_state.flow_rate_ml_h
                self.pump_state.flow_rate_ml_h = new_rate
                logger.warning(
                    "COMMANDE SET_RATE recue de %s : %.1f -> %.1f mL/h (non authentifie)",
                    source_ip, old_rate, new_rate,
                )
                return f"OK debit regle a {new_rate} mL/h"

            elif cmd == "PAUSE":
                self.pump_state.status = "PAUSED"
                logger.warning("COMMANDE PAUSE recue de %s (non authentifie)", source_ip)
                return "OK pompe en pause"

            elif cmd == "RESUME":
                self.pump_state.status = "RUNNING"
                logger.warning("COMMANDE RESUME recue de %s (non authentifie)", source_ip)
                return "OK pompe relancee"

            elif cmd == "DISABLE_ALARM":
                self.pump_state.alarms_disabled = True
                logger.warning(
                    "COMMANDE DISABLE_ALARM recue de %s -- remontee d'alarme masquee (non authentifie)",
                    source_ip,
                )
                return "OK alarmes desactivees"

            elif cmd == "ENABLE_ALARM":
                self.pump_state.alarms_disabled = False
                return "OK alarmes reactivees"

            elif cmd == "STATUS":
                return (f"phase={self.pump_state.phase} status={self.pump_state.status} "
                        f"debit={self.pump_state.flow_rate_ml_h} "
                        f"alarmes_desactivees={self.pump_state.alarms_disabled}")

            else:
                return "ERR commande inconnue"
