#!/usr/bin/env python3
"""
API REST du lab IoMT.
Expose la base en lecture (JSON) et fournit l'endpoint que la pompe
interroge pour connaître sa prescription active.
IMPORTANT : à ce stade, AUCUNE authentification — c'est volontaire.
Cette surface non protégée est le point de départ de la Phase 3 (durcissement).
"""
from flask import Flask, jsonify, request

from config.settings import API_HOST, API_PORT
from db import queries

app = Flask(__name__)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/patients")
def patients():
    return jsonify(queries.list_patients())


@app.route("/api/prescriptions")
def prescriptions():
    return jsonify(queries.list_prescriptions())


@app.route("/api/prescriptions/active")
def active_prescription():
    """Endpoint consommé par la pompe : ?patient_id=PT-XXXXX."""
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"error": "parametre patient_id requis"}), 400
    presc = queries.get_active_prescription(patient_id)
    if not presc:
        return jsonify({}), 404
    return jsonify(presc)


@app.route("/api/infusions/active")
def active_infusions():
    """Perfusions en cours (dernière télémétrie de chaque pompe)."""
    return jsonify(queries.list_active_infusions())


@app.route("/api/alarms")
def alarms():
    return jsonify(queries.list_alarms())


def main():
    app.run(host=API_HOST, port=API_PORT, debug=False)


if __name__ == "__main__":
    main()
