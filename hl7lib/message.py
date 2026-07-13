"""
Construction et analyse minimales de messages HL7 v2.x.
On reste au niveau utile pour le lab : séparateurs standard, en-tête MSH
cohérent, découpage en segments/champs, et génération d'ACK.
Pas d'ambition d'implémenter tout le standard.
"""
from datetime import datetime

FIELD_SEP = "|"
COMP_SEP = "^"
SEGMENT_SEP = "\r"
ENCODING_CHARS = r"^~\&"


def timestamp() -> str:
    """Horodatage HL7 (format YYYYMMDDHHMMSS)."""
    return datetime.now().strftime("%Y%m%d%H%M%S")


def build_msh(sending_app: str, sending_facility: str,
              receiving_app: str, receiving_facility: str,
              message_type: str, control_id: str, version: str = "2.3") -> str:
    """
    Construit un segment MSH. Le champ MSH-1 est le séparateur de champ lui-même,
    MSH-2 les caractères d'encodage — convention HL7 respectée.
    message_type ex. : 'ORU^R01', 'ADT^A01', 'ORM^O01'.
    """
    return FIELD_SEP.join([
        "MSH",
        ENCODING_CHARS,
        sending_app, sending_facility,
        receiving_app, receiving_facility,
        timestamp(), "",
        message_type, control_id,
        "P", version,
    ])


def parse(hl7_message: str) -> dict:
    """
    Analyse un message HL7 en structure exploitable.
    Retourne un dict : { 'segments': [ {'type': 'MSH', 'fields': [...]}, ... ] }
    Le parsing par position de champ suffit à nos besoins (PID, OBX, etc.).
    """
    segments = []
    for line in hl7_message.replace("\n", "\r").split(SEGMENT_SEP):
        line = line.strip()
        if not line:
            continue
        fields = line.split(FIELD_SEP)
        segments.append({"type": fields[0], "fields": fields})
    return {"segments": segments}


def get_segment(parsed: dict, seg_type: str):
    """Retourne le premier segment d'un type donné, ou None."""
    for seg in parsed["segments"]:
        if seg["type"] == seg_type:
            return seg
    return None


def get_segments(parsed: dict, seg_type: str):
    """Retourne tous les segments d'un type donné (utile pour les OBX multiples)."""
    return [seg for seg in parsed["segments"] if seg["type"] == seg_type]


def get_control_id(parsed: dict) -> str:
    """Extrait l'identifiant de contrôle du message (MSH-10)."""
    msh = get_segment(parsed, "MSH")
    if msh and len(msh["fields"]) > 9:
        return msh["fields"][9]
    return "UNKNOWN"


def build_ack(parsed: dict, ack_code: str = "AA") -> str:
    """
    Construit un ACK HL7 en réponse à un message reçu.
    ack_code : 'AA' (accepté), 'AE' (erreur), 'AR' (rejeté).
    Le récepteur renverra ce message à l'émetteur — comportement HL7 réel
    qui manquait dans ta version initiale.
    """
    control_id = get_control_id(parsed)
    msh = build_msh(
        sending_app="HL7-RECEIVER", sending_facility="IT-ZONE",
        receiving_app="PUMP", receiving_facility="ICU",
        message_type="ACK", control_id=f"ACK-{control_id}",
    )
    msa = FIELD_SEP.join(["MSA", ack_code, control_id])
    return msh + SEGMENT_SEP + msa + SEGMENT_SEP
