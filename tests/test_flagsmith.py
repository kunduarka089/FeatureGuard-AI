from app import app
import app as app_module


def test_flags_list_returns_flags(monkeypatch):
    monkeypatch.setattr(app_module, "list_feature_states", lambda: [
        {"id": 1, "name": "new_checkout", "enabled": True, "value": None}
    ])
    client = app.test_client()
    response = client.get("/api/flagsmith/flags")
    assert response.status_code == 200
    assert response.json["flags"][0]["name"] == "new_checkout"


def test_rollback_requires_allowlisted_flag(monkeypatch):
    monkeypatch.setattr(app_module, "list_feature_states", lambda: [
        {"id": 1, "name": "discount_banner", "enabled": True, "value": None}
    ])
    client = app.test_client()
    response = client.post("/api/rollback/request", json={
        "feature_name": "discount_banner"
    })
    assert response.status_code == 403


def test_rollback_requires_approval_and_verifies(monkeypatch):
    monkeypatch.setattr(app_module, "list_feature_states", lambda: [
        {"id": 1, "name": "new_checkout", "enabled": True, "value": None}
    ])
    monkeypatch.setattr(app_module, "set_feature_enabled", lambda name, enabled: {
        "id": 1, "name": name, "enabled": enabled, "value": None
    })
    client = app.test_client()

    prepared = client.post("/api/rollback/request", json={
        "feature_name": "new_checkout",
        "reason": "Test incident"
    })
    assert prepared.status_code == 200
    approval_id = prepared.json["approval_id"]

    # Preparing a rollback must not change the flag.
    assert prepared.json["proposed_state"] == "OFF"
    assert "explicit approval" in prepared.json["message"]

    approved = client.post("/api/rollback/approve", json={
        "approval_id": approval_id
    })
    assert approved.status_code == 200
    assert approved.json["success"] is True
    assert approved.json["feature"]["enabled"] is False

    # Approval tokens are one-time.
    repeated = client.post("/api/rollback/approve", json={
        "approval_id": approval_id
    })
    assert repeated.status_code == 400
