import os
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from featureguard.database import init_db, save_event, recent_events, event_summary
from featureguard.ai import analyse_events

load_dotenv()
app = Flask(__name__)
init_db()

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "FeatureGuard AI"})

@app.post("/api/events")
def ingest_event():
    data = request.get_json(silent=True) or {}
    required = ("event_name",)
    if any(not data.get(k) for k in required):
        return jsonify({"error": "event_name is required"}), 400
    event_id = save_event(
        event_name=str(data["event_name"])[:100],
        feature_name=str(data.get("feature_name", "unknown"))[:100],
        success=bool(data.get("success", True)),
        value=float(data.get("value", 1) or 0),
        metadata=data.get("metadata", {})
    )
    return jsonify({"accepted": True, "event_id": event_id}), 201

@app.get("/api/events")
def get_events():
    return jsonify(recent_events())

@app.get("/api/summary")
def summary():
    return jsonify(event_summary())

@app.post("/api/ai/analyse")
def ai_analyse():
    result = analyse_events(event_summary())
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
