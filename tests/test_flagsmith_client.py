import pytest

from featureguard import flagsmith_client as client


def _fake_flagsmith(monkeypatch, *, fail_publish=False, apply_change=True):
    state = {"enabled": True}
    calls = []

    monkeypatch.setattr(client, "_config", lambda: ("test-token", "env-key"))

    def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if method == "GET" and path == "/environments/env-key/":
            return {"id": 5, "project": 12}
        if method == "GET" and path == "/projects/12/features/":
            return [{"id": 21, "name": "new_checkout"}]
        if method == "GET" and path == "/environments/env-key/featurestates/":
            return [{
                "id": 31,
                "feature": 21,
                "enabled": state["enabled"],
                "feature_state_value": {"type": "boolean", "boolean_value": True},
                "feature_segment": None,
                "identity": None,
                "multivariate_feature_state_values": [],
            }]
        if method == "POST" and path == "/environments/5/features/21/versions/":
            if fail_publish:
                raise client.FlagsmithError("Flagsmith returned HTTP 400")
            if apply_change:
                state["enabled"] = kwargs["json"]["feature_states_to_update"][0]["enabled"]
            return {"uuid": "version-uuid", "published": True}
        raise AssertionError(f"Unexpected Flagsmith request: {method} {path}")

    monkeypatch.setattr(client, "_request", fake_request)
    return calls, state


def test_v2_rollback_creates_and_publishes_version(monkeypatch):
    calls, state = _fake_flagsmith(monkeypatch)

    result = client.set_feature_enabled("new_checkout", False)

    publish_call = next(
        call for call in calls
        if call[0] == "POST" and call[1].endswith("/versions/")
    )
    payload = publish_call[2]["json"]
    assert payload["publish_immediately"] is True
    assert payload["feature_states_to_update"][0]["enabled"] is False
    assert payload["feature_states_to_update"][0]["feature_state_value"] == {
        "type": "boolean", "boolean_value": True
    }
    assert result["enabled"] is False
    assert state["enabled"] is False


def test_v2_rollback_reports_flagsmith_api_error(monkeypatch):
    _fake_flagsmith(monkeypatch, fail_publish=True)

    with pytest.raises(client.FlagsmithError, match="HTTP 400"):
        client.set_feature_enabled("new_checkout", False)


def test_v2_rollback_fails_when_published_state_cannot_be_verified(monkeypatch):
    _fake_flagsmith(monkeypatch, apply_change=False)

    with pytest.raises(client.FlagsmithError, match="verification"):
        client.set_feature_enabled("new_checkout", False)
