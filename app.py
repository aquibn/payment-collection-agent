"""
Flask backend for the Payment Collection Agent UI.

Usage:
    python app.py               # live mode (calls real API)
    python app.py --mock        # mock mode (no network needed)
    MOCK_API=1 python app.py    # mock mode via env var
    python app.py --port 5001   # custom port
"""

import sys, os, argparse, requests as req_lib

# ── Parse CLI flags BEFORE importing api_client (reads env on import) ────────
parser = argparse.ArgumentParser(description="PayAgent Flask server")
parser.add_argument("--mock",  action="store_true", help="Use mock API (no network)")
parser.add_argument("--port",  type=int, default=5003, help="Port (default: 5003)")
args, _ = parser.parse_known_args()
if args.mock:
    os.environ["MOCK_API"] = "1"

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify, render_template
from agent import Agent
import api_client

app = Flask(__name__, template_folder="templates", static_folder="static")

# ── CORS (fixes 403 / blocked request errors in browser) ─────────────────────
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.route("/api/chat",  methods=["OPTIONS"])
@app.route("/api/reset", methods=["OPTIONS"])
@app.route("/api/debug", methods=["OPTIONS"])
def handle_options(): return "", 204

# ── Session store ─────────────────────────────────────────────────────────────
_agents: dict[str, Agent] = {}

def get_agent(sid: str) -> Agent:
    if sid not in _agents:
        _agents[sid] = Agent()
        print(f"  [session] new: {sid} (total active: {len(_agents)})")
    return _agents[sid]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", mock_mode=api_client.MOCK_MODE)


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "mock_mode": api_client.MOCK_MODE,
        "sessions": len(_agents),
        "api_base": api_client.BASE_URL,
    })


@app.route("/api/debug", methods=["GET", "POST"])
def debug():
    """
    Tries the external API with ACC1001 and returns detailed diagnostics.
    Used by the UI health panel.
    """
    if api_client.MOCK_MODE:
        return jsonify({
            "mode": "mock",
            "verdict": "Running in MOCK mode — no external API calls made",
            "mock_accounts": list(api_client._MOCK_DB.keys()),
        })

    results = []
    # Try both the corrected URL and the old (buggy) one so user can see the diff
    candidates = [
        api_client.BASE_URL + "/lookup-account",
        api_client.BASE_URL.replace("/api", "/openapi/api") + "/lookup-account",
    ]
    for url in candidates:
        try:
            r = req_lib.post(url, json={"account_id": "ACC1001"}, timeout=6)
            results.append({"url": url, "status": r.status_code, "body": r.json() if r.status_code == 200 else str(r.text[:80])})
        except Exception as e:
            results.append({"url": url, "status": "error", "body": str(e)})

    working = next((r for r in results if r["status"] == 200), None)
    return jsonify({
        "mode": "live",
        "base_url": api_client.BASE_URL,
        "results": results,
        "verdict": "✅ API reachable" if working else "❌ API not reachable — run with --mock flag",
        "fix": None if working else "MOCK_API=1 python app.py",
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    sid  = data.get("session_id", "default")
    msg  = data.get("message", "").strip()

    if not msg:
        return jsonify({"error": "message is required"}), 400

    print(f"\n  [chat] [{sid[:8]}] USER  → {msg!r}")
    result = get_agent(sid).next(msg)
    reply  = result["message"]
    print(f"  [chat] [{sid[:8]}] AGENT → {reply[:100]!r}{'…' if len(reply)>100 else ''}")

    return jsonify({"reply": reply})


@app.route("/api/reset", methods=["POST"])
def reset():
    data = request.get_json(force=True, silent=True) or {}
    sid  = data.get("session_id", "default")
    _agents.pop(sid, None)
    print(f"  [session] reset: {sid}")
    return jsonify({"status": "reset", "session_id": sid})


# ── Startup ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = args.port
    mode_label = "🟡 MOCK (offline — no real API calls)" if api_client.MOCK_MODE else "🟢 LIVE (calling real external API)"

    print()
    print("  ╔═══════════════════════════════════════════════════╗")
    print("  ║            PayAgent — Flask Server                ║")
    print(f"  ║  Open   → http://localhost:{port}                   ║")
    print(f"  ║  Mode   → {mode_label:<40}║")
    print(f"  ║  API    → {api_client.BASE_URL[:40]:<40}║")
    print("  ╠═══════════════════════════════════════════════════╣")
    print("  ║  Debug  → http://localhost:" + str(port) + "/api/debug          ║")
    print("  ║  Health → http://localhost:" + str(port) + "/health             ║")
    print("  ╚═══════════════════════════════════════════════════╝")
    if not api_client.MOCK_MODE:
        print("\n  ⚠️  If you see 404/network errors in the UI, restart with:")
        print(f"     python app.py --mock --port {port}\n")

    app.run(debug=True, port=port, host="0.0.0.0")
