from unittest.mock import patch, MagicMock
import requests
from featureguard.ai import analyse_events

def _env(m):
    m.setenv("XAI_API_KEY", "sk-secret-123")

def test_http_error_returns_status_and_body(monkeypatch):
    _env(monkeypatch)
    r = MagicMock(ok=False, status_code=404, text='{"error":"model not found sk-secret-123"}')
    with patch("featureguard.ai.requests.post", return_value=r):
        out = analyse_events({})
    assert "404" in out["error"] and "model not found" in out["error"]
    assert "sk-secret-123" not in str(out)

def test_timeout(monkeypatch):
    _env(monkeypatch)
    with patch("featureguard.ai.requests.post", side_effect=requests.exceptions.Timeout()):
        assert "timed out" in analyse_events({})["error"]

def test_bad_json_and_format(monkeypatch):
    _env(monkeypatch)
    r = MagicMock(ok=True, status_code=200, text="x"); r.json.side_effect = ValueError()
    with patch("featureguard.ai.requests.post", return_value=r):
        assert "invalid JSON" in analyse_events({})["error"]
    r2 = MagicMock(ok=True, status_code=200); r2.json.return_value = {"foo": 1}
    with patch("featureguard.ai.requests.post", return_value=r2):
        assert "unexpected response" in analyse_events({})["error"]

def test_success(monkeypatch):
    _env(monkeypatch)
    r = MagicMock(ok=True, status_code=200); r.json.return_value = {"choices":[{"message":{"content":"hi"}}]}
    with patch("featureguard.ai.requests.post", return_value=r):
        assert analyse_events({})["analysis"] == "hi"

def test_missing_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert analyse_events({})["configured"] is False
