import os, tempfile
import pytest
from app import app
from featureguard import database

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        yield client

def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"

def test_event_validation(client):
    response = client.post("/api/events", json={})
    assert response.status_code == 400

def test_event_ingestion_and_summary(client):
    response = client.post("/api/events", json={
        "event_name": "checkout_completed",
        "feature_name": "new_checkout",
        "success": True,
        "value": 1
    })
    assert response.status_code == 201
    summary = client.get("/api/summary").json
    assert summary[0]["feature_name"] == "new_checkout"
    assert summary[0]["events"] == 1
