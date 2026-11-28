"""Small, server-side Flagsmith Management API client.

The organisation token is secret and must never be sent to the browser.
The environment key identifies the target environment and is used only in
the Management API URL.
"""
import os
import requests

API_BASE = os.getenv("FLAGSMITH_API_URL", "https://api.flagsmith.com").rstrip("/")
TIMEOUT = 15


class FlagsmithError(Exception):
    pass


def _config():
    token = os.getenv("FLAGSMITH_API_TOKEN", "").strip()
    environment_key = os.getenv("FLAGSMITH_ENVIRONMENT_KEY", "").strip()
    if not token:
        raise FlagsmithError("FLAGSMITH_API_TOKEN is not configured on the server.")
    if not environment_key:
        raise FlagsmithError("FLAGSMITH_ENVIRONMENT_KEY is not configured on the server.")
    return token, environment_key


def _request(method, path, **kwargs):
    token, _ = _config()
    headers = kwargs.pop("headers", {})
    headers.update({
        "Authorization": f"Api-Key {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    })
    try:
        response = requests.request(
            method, f"{API_BASE}/api/v1{path}",
            headers=headers, timeout=TIMEOUT, **kwargs
        )
    except requests.exceptions.RequestException as exc:
        raise FlagsmithError(f"Could not reach Flagsmith: {type(exc).__name__}") from exc
    if not response.ok:
        # Do not include request headers or tokens in error messages.
        detail = (response.text or "")[:400]
        raise FlagsmithError(f"Flagsmith returned HTTP {response.status_code}: {detail}")
    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise FlagsmithError("Flagsmith returned an invalid JSON response.") from exc


def list_feature_states():
    _, environment_key = _config()
    data = _request("GET", f"/environments/{environment_key}/featurestates/")
    if isinstance(data, dict):
        data = data.get("results", data.get("feature_states", []))
    if not isinstance(data, list):
        raise FlagsmithError("Unexpected feature-state response from Flagsmith.")
    flags = []
    for item in data:
        feature = item.get("feature") or {}
        name = feature.get("name") or item.get("feature_name") or item.get("name")
        if not name or "id" not in item:
            continue
        flags.append({
            "id": item["id"],
            "name": name,
            "enabled": bool(item.get("enabled", False)),
            "value": item.get("feature_state_value"),
        })
    return flags


def set_feature_enabled(feature_name, enabled):
    """Update only an existing environment feature state."""
    flags = list_feature_states()
    target = next((f for f in flags if f["name"] == feature_name), None)
    if target is None:
        raise FlagsmithError(f"Feature flag '{feature_name}' was not found in the configured environment.")
    _, environment_key = _config()
    _request(
        "PATCH",
        f"/environments/{environment_key}/featurestates/{target['id']}/",
        json={"enabled": bool(enabled)},
    )
    updated = next((f for f in list_feature_states() if f["name"] == feature_name), None)
    if updated is None or updated["enabled"] != bool(enabled):
        raise FlagsmithError("Flagsmith accepted the update, but verification did not confirm the requested state.")
    return updated
