#!/usr/bin/env python3
"""Client de commande légitime pour la pompe (baseline)."""
import socket
import argparse
from config.settings import PUMP_CMD_HOST, PUMP_CMD_PORT


def send_command(host, port, command):
    with socket.create_connection((host, port), timeout=5) as sock:
        sock.sendall(command.encode("utf-8"))
        return sock.recv(1024).decode("utf-8", errors="replace").strip()


def main():
    parser = argparse.ArgumentParser(description="Client de commande pompe (legitime)")
    parser.add_argument("verb", help="SET_RATE | PAUSE | RESUME | DISABLE_ALARM | ENABLE_ALARM | STOP")
    parser.add_argument("value", nargs="?", help="valeur (ex. debit pour SET_RATE)")
    parser.add_argument("--host", default=PUMP_CMD_HOST)
    parser.add_argument("--port", type=int, default=PUMP_CMD_PORT)
    args = parser.parse_args()
    command = args.verb.upper()
    if args.value is not None:
        command += f"|{args.value}"
    print("Réponse pompe :", send_command(args.host, args.port, command))


if __name__ == "__main__":
    main()
