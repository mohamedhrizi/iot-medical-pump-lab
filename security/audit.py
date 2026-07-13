"""
Journalisation d'audit structurée (un objet JSON par ligne).

But : produire une trace exploitable directement par un SIEM (Wazuh) sans
re-parsing. Tous les composants écrivent via ce module, dans un fichier
unique, avec un schéma de champs stable.

Schéma d'un évènement :
    timestamp   : horodatage ISO 8601
    event       : type normalisé (ex. 'pump.command', 'hl7.oru', 'net.connect')
    component   : composant émetteur ('pump', 'receiver', 'api'...)
    src_ip      : IP source quand pertinent
    device_id   : équipement concerné
    patient_id  : patient concerné
    detail      : champ libre + tout champ supplémentaire passé en kwargs
"""
import os
import json
from datetime import datetime
from config.settings import BASE_DIR

AUDIT_LOG = os.path.join(BASE_DIR, "audit.log")


def audit(event: str, component: str = None, src_ip: str = None,
          device_id: str = None, patient_id: str = None, **extra):
    """
    Écrit une ligne JSON d'audit.
    `event`  : type normalisé de l'évènement (obligatoire).
    `extra`  : tout champ supplémentaire (command, flow, status, reason...).
    Retourne l'entrée écrite (utile pour les tests).
    """
    entry = {"timestamp": datetime.now().astimezone().isoformat(), "event": event}
    if component is not None:
        entry["component"] = component
    if src_ip is not None:
        entry["src_ip"] = src_ip
    if device_id is not None:
        entry["device_id"] = device_id
    if patient_id is not None:
        entry["patient_id"] = patient_id
    entry.update(extra)

    line = json.dumps(entry, ensure_ascii=False)
    try:
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass  # le logging ne doit jamais faire planter un composant
    return entry
