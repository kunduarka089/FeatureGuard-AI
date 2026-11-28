import os
import secrets
import time
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from featureguard.database import init_db, save_event, recent_events, event_summary
from featureguard.ai import analyse_events
from featureguard.flagsmith_client import (
    FlagsmithError, list_feature_states, set_feature_enabled
)

load_dotenv()
app = Flask(__name__)
init_db()

# Short-lived, one-time approvals. A restart safely invalidates pending approvals.
_pending_rollbacks = {}
APPROVAL_TTL_SECONDS = 300


def _allowed_rollback_flags():
    raw = os.getenv("ROLLBACK_ALLOWED_FLAGS", "new_checkout")
    return {name.strip() for name in raw.split(",") if name.strip()}


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "FeatureGuard AI"})


@app.post("/api/events")
def ingest_event():
    data = request.get_json(silent=True) or {}
    if not data.get("event_name"):
        return jsonify({"error": "event_name is required"}), 400
    try:
        value = float(data.get("value", 1) or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "value must be numeric"}), 400
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        return jsonify({"error": "metadata must be an object"}), 400
    event_id = save_event(
        event_name=str(data["event_name"])[:100],
        feature_name=str(data.get("feature_name", "unknown"))[:100],
        success=bool(data.get("success", True)),
        value=value,
        metadata=metadata
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
    return jsonify(analyse_events(event_summary()))


@app.get("/api/monitor/anomalies")
def monitor_anomalies():
    """Conservative rule-based detector; never changes feature flags."""
    min_events = max(3, int(os.getenv("ANOMALY_MIN_EVENTS", "3")))
    failure_threshold = min(1.0, max(0.0, float(os.getenv("ANOMALY_FAILURE_RATE", "0.5"))))
    features = event_summary()
    alerts = []
    insufficient = []
    for item in features:
        count = int(item["events"])
        rate = float(item["failure_rate"] or 0)
        record = {
            "feature_name": item["feature_name"],
            "events": count,
            "failures": int(item["failures"] or 0),
            "failure_rate": rate,
        }
        if count < min_events:
            insufficient.append(record)
        elif rate >= failure_threshold:
            alerts.append({
                **record,
                "severity": "high" if rate >= 0.8 else "warning",
                "message": (
                    f"{record['failures']} of {count} events failed "
                    f"({round(rate * 100)}%). Investigate this feature."
                ),
            })
    return jsonify({
        "status": "alert" if alerts else ("insufficient_data" if insufficient else "healthy"),
        "thresholds": {"minimum_events": min_events, "failure_rate": failure_threshold},
        "alerts": alerts,
        "insufficient_data": insufficient,
        "message": (
            "Potential feature issue detected. This is a signal to investigate, not proof of cause."
            if alerts else
            "Not enough events yet to assess every feature reliably."
            if insufficient else
            "No feature crossed the configured failure threshold."
        ),
    })


@app.get("/api/flagsmith/flags")
def flagsmith_flags():
    try:
        return jsonify({"configured": True, "flags": list_feature_states()})
    except FlagsmithError as exc:
        return jsonify({"configured": False, "error": str(exc)}), 503


@app.post("/api/rollback/request")
def request_rollback():
    data = request.get_json(silent=True) or {}
    feature_name = str(data.get("feature_name", "")).strip()
    reason = str(data.get("reason", "FeatureGuard detected a possible incident."))[:300]
    if feature_name not in _allowed_rollback_flags():
        return jsonify({"error": "This flag is not on the rollback allowlist."}), 403
    try:
        flags = list_feature_states()
    except FlagsmithError as exc:
        return jsonify({"error": str(exc)}), 503
    target = next((f for f in flags if f["name"] == feature_name), None)
    if target is None:
        return jsonify({"error": "Flag not found in the configured Flagsmith environment."}), 404
    if not target["enabled"]:
        return jsonify({"error": "This flag is already OFF; no rollback is needed."}), 409

    approval_id = secrets.token_urlsafe(24)
    _pending_rollbacks[approval_id] = {
        "feature_name": feature_name,
        "reason": reason,
        "expires_at": time.time() + APPROVAL_TTL_SECONDS,
    }
    return jsonify({
        "approval_id": approval_id,
        "feature_name": feature_name,
        "current_state": "ON",
        "proposed_state": "OFF",
        "reason": reason,
        "expires_in_seconds": APPROVAL_TTL_SECONDS,
        "message": "Rollback prepared. Nothing has changed yet; explicit approval is required."
    })


@app.post("/api/rollback/approve")
def approve_rollback():
    data = request.get_json(silent=True) or {}
    approval_id = str(data.get("approval_id", ""))
    pending = _pending_rollbacks.pop(approval_id, None)
    if not pending or pending["expires_at"] < time.time():
        return jsonify({"error": "Approval is missing, expired, or already used. Request a new rollback."}), 400

    feature_name = pending["feature_name"]
    if feature_name not in _allowed_rollback_flags():
        return jsonify({"error": "This flag is no longer on the rollback allowlist."}), 403
    try:
        updated = set_feature_enabled(feature_name, False)
    except FlagsmithError as exc:
        return jsonify({"error": str(exc), "changed": False}), 502

    return jsonify({
        "success": True,
        "changed": True,
        "feature": updated,
        "reason": pending["reason"],
        "message": f"Rollback complete. {feature_name} is OFF and Flagsmith confirmed the new state."
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
