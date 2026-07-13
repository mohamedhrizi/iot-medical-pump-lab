#!/usr/bin/env python3
"""
Serveur de commande OT de la pompe.

Version baseline.

AUCUNE authentification.
AUCUN chiffrement.

Le serveur écoute sur TCP et accepte des commandes
texte envoyées par un client.

Exemples :

SET_RATE 120
PAUSE
RESUME
STOP
STATUS
"""

import socket
import threading
import logging

logger = logging.getLogger("pump_command")


class CommandServer:

    def __init__(
        self,
        state,
        host="0.0.0.0",
        port=7000
    ):

        self.state = state
        self.host = host
        self.port = port

    def start(self):

        thread = threading.Thread(
            target=self.run,
            daemon=True
        )

        thread.start()

        logger.info(
            "Command Server écoute sur %s:%s",
            self.host,
            self.port
        )

    def run(self):

        server = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        server.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        server.bind(
            (
                self.host,
                self.port
            )
        )

        server.listen(5)

        while True:

            client, addr = server.accept()

            logger.info(
                "Connexion commande depuis %s",
                addr[0]
            )

            threading.Thread(
                target=self.handle_client,
                args=(client,),
                daemon=True
            ).start()

    def handle_client(self, client):

        with client:

            while True:

                data = client.recv(1024)

                if not data:
                    break

                command = data.decode().strip()

                response = self.execute(command)

                client.sendall(
                    (response + "\n").encode()
                )

    def execute(self, command):

        parts = command.split()

        if not parts:
            return "ERROR"

        cmd = parts[0].upper()

        if cmd == "STATUS":

            return (
                f"{self.state.status} "
                f"{self.state.current_target_rate():.1f}"
            )

        elif cmd == "PAUSE":

            self.state.status = "PAUSED"

            return "OK"

        elif cmd == "RESUME":

            self.state.status = "RUNNING"

            return "OK"

        elif cmd == "STOP":

            self.state.status = "COMPLETE"

            return "OK"

        elif cmd == "SET_RATE":

            if len(parts) != 2:
                return "ERROR"

            try:

                rate = float(parts[1])

                self.state.flow_rate_ml_h = rate

                logger.warning(
                    "Débit modifié à distance : %.1f ml/h",
                    rate
                )

                return "OK"

            except ValueError:

                return "ERROR"

        else:

            return "UNKNOWN_COMMAND"
