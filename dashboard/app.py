#!/usr/bin/env python3
"""
Dashboard poste infirmier (baseline).
Sert une page HTML qui interroge SES PROPRES endpoints /data/*, lesquels
relaient l'API REST côté serveur. Ce proxy évite les soucis CORS.
"""
import json
import urllib.request
import urllib.parse
from flask import Flask, render_template, jsonify

from config.settings import API_BASE_URL, DASHBOARD_HOST, DASHBOARD_PORT

app = Flask(__name__)


def _api_get(path, params=None):
    url = f"{API_BASE_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/data/infusions")
def data_infusions():
    return jsonify(_api_get("/api/infusions/active"))


@app.route("/data/alarms")
def data_alarms():
    return jsonify(_api_get("/api/alarms"))


@app.route("/data/patients")
def data_patients():
    return jsonify(_api_get("/api/patients"))


def main():
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False)


if __name__ == "__main__":
    main()
