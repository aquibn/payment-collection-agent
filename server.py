"""
Flask web server — exposes the Payment Agent over HTTP.
Run: python server.py
Then open http://localhost:5000 in your browser.
"""

import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify, send_from_directory
from agent import Agent

app = Flask(__name__, static_folder=".")

# In-memory session store: session_id → Agent instance
sessions: dict = {}


def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
    return response


@app.after_request
def after_request(response):
    return add_cors(response)


@app.route("/", methods=["GET"])
def index():
    return send_from_directory(".", "ui.html")


@app.route("/api/session/new", methods=["POST", "OPTIONS"])
def new_session():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    session_id = str(uuid.uuid4())
    agent = Agent()
    sessions[session_id] = agent
    opening = agent.next("hi")
    return jsonify({"session_id": session_id, "message": opening["message"]})


@app.route("/api/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    data = request.get_json(force=True)
    session_id = data.get("session_id", "")
    user_input = data.get("message", "").strip()

    if not session_id or session_id not in sessions:
        return jsonify({"error": "Invalid or expired session."}), 400
    if not user_input:
        return jsonify({"error": "Message cannot be empty."}), 400

    agent = sessions[session_id]
    result = agent.next(user_input)
    msg = result["message"]

    terminal_phrases = [
        "session has been closed",
        "have a great day",
        "payment successful",
        "verification failed after",
    ]
    is_terminal = any(p in msg.lower() for p in terminal_phrases)
    if is_terminal:
        sessions.pop(session_id, None)

    return jsonify({"message": msg, "session_closed": is_terminal})


@app.route("/api/session/<session_id>", methods=["DELETE", "OPTIONS"])
def delete_session(session_id):
    sessions.pop(session_id, None)
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  PayFlow — Payment Collection Agent")
    print("  Open http://localhost:5000 in your browser")
    print("=" * 55 + "\n")
    app.run(debug=True, port=5000)

