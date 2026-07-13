"""
Framing MLLP (Minimal Lower Layer Protocol).
HL7 v2.x circule sur TCP encapsulé dans MLLP : chaque message est
entouré d'un octet de début (0x0B) et de deux octets de fin (0x1C 0x0D).
Ce module centralise l'emballage et l'extraction, côté émetteur ET récepteur.
"""
from config.settings import MLLP_START, MLLP_END


def wrap(hl7_message: str) -> bytes:
    """Encapsule un message HL7 dans une trame MLLP prête à envoyer."""
    return MLLP_START + hl7_message.encode("utf-8") + MLLP_END


def send_message(sock, hl7_message: str):
    """Envoie un message HL7 encadré MLLP sur une socket connectée."""
    sock.sendall(wrap(hl7_message))


def extract_messages(buffer: bytes):
    """
    Extrait tous les messages HL7 complets présents dans un buffer.
    Reprend la logique éprouvée du récepteur d'origine :
    - ignore le bruit avant un octet de début,
    - conserve un message partiel (début reçu, fin pas encore) pour le tour suivant.

    Retourne (messages, buffer_restant).
    """
    messages = []
    while True:
        start_idx = buffer.find(MLLP_START)
        if start_idx == -1:
            # aucun début de trame : tout ce qui reste est du bruit
            return messages, b""
        end_idx = buffer.find(MLLP_END, start_idx + len(MLLP_START))
        if end_idx == -1:
            # message partiel : on jette le bruit avant le début, on garde le reste
            return messages, buffer[start_idx:]
        payload = buffer[start_idx + len(MLLP_START):end_idx]
        messages.append(payload.decode("utf-8", errors="replace"))
        buffer = buffer[end_idx + len(MLLP_END):]
