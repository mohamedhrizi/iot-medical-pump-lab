#!/usr/bin/env python3
"""
Dashboard poste infirmier (baseline).
Sert une page HTML qui interroge SES PROPRES endpoints /data/*, lesquels
relaient l'API REST côté serveur. Ce proxy évite les soucis CORS.
"""
import json
import urllib.request
import urllib.parse
from flask import Flask, render_template, jsonify, request

from config.settings import API_BASE_URL, DASHBOARD_HOST, DASHBOARD_PORT, PUMP_CMD_HOST, PUMP_CMD_PORT

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


def _send_pump_command(command, timeout=3):
    import socket
    try:
        with socket.create_connection((PUMP_CMD_HOST, PUMP_CMD_PORT), timeout=timeout) as s:
            s.sendall((command + "\n").encode("utf-8"))
            resp = s.recv(1024).decode("utf-8", errors="replace").strip()
            return {"ok": True, "response": resp}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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


@app.route("/data/set_rate", methods=["POST"])
def set_rate():
    rate = request.json.get("rate")
    result = _send_pump_command(f"SET_RATE|{rate}")
    return jsonify(result)


def main():
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False)


if __name__ == "__main__":
    main()
