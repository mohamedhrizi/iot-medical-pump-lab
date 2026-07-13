"""
Client API utilisé par la pompe IoMT.

La pompe demande sa prescription active
au serveur central avant de démarrer.
"""

import requests

from config.settings import API_HOST, API_PORT


def get_active_prescription(patient_id):
    """
    Récupère la prescription active d'un patient.

    Retourne un dictionnaire :
    {
        drug_name,
        flow_rate_ml_h,
        volume_total_ml
    }
    """

    url = (
        f"http://{API_HOST}:{API_PORT}"
        f"/api/prescriptions/active"
    )

    params = {
        "patient_id": patient_id
    }

    response = requests.get(
        url,
        params=params,
        timeout=5
    )

    response.raise_for_status()

    return response.json()
