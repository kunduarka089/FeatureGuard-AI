"""Server-side Flagsmith Management API client.

The organisation API token is secret and must never be sent to the browser.
The environment API key is used only to identify the configured environment.
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
        detail = (response.text or "")[:300]
        raise FlagsmithError(f"Flagsmith returned HTTP {response.status_code}: {detail}")
    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise FlagsmithError("Flagsmith returned an invalid JSON response.") from exc


def _as_list(data, label):
    if isinstance(data, dict):
        data = data.get("results", data.get(label, []))
    if not isinstance(data, list):
        raise FlagsmithError(f"Unexpected {label} response from Flagsmith.")
    return data


def _environment_and_features(environment_key):
    """Return the numeric environment ID and its project's feature records."""
    environment = _request("GET", f"/environments/{environment_key}/")
    if not isinstance(environment, dict) or not isinstance(environment.get("id"), int):
        raise FlagsmithError("Could not determine the Flagsmith environment ID.")
    project_id = environment.get("project")
    if isinstance(project_id, dict):
        project_id = project_id.get("id")
    if not isinstance(project_id, int):
        raise FlagsmithError("Could not determine the project ID for this Flagsmith environment.")
    features = _as_list(
        _request("GET", f"/projects/{project_id}/features/"),
        "features",
    )
    return environment["id"], features


def _feature_names_by_id(environment_key):
    _, features = _environment_and_features(environment_key)
    return {
        feature.get("id"): feature.get("name")
        for feature in features
        if isinstance(feature, dict)
        and isinstance(feature.get("id"), int)
        and feature.get("name")
    }


def list_feature_states():
    _, environment_key = _config()
    data = _as_list(
        _request("GET", f"/environments/{environment_key}/featurestates/"),
        "feature-state",
    )
    needs_lookup = any(
        isinstance(item, dict) and isinstance(item.get("feature"), int)
        for item in data
    )
    names_by_id = _feature_names_by_id(environment_key) if needs_lookup else {}

    flags = []
    for item in data:
        if not isinstance(item, dict):
            continue
        feature = item.get("feature")
        if isinstance(feature, dict):
            name = feature.get("name")
        elif isinstance(feature, str):
            name = feature
        elif isinstance(feature, int):
            name = names_by_id.get(feature)
        else:
            name = None
        name = name or item.get("feature_name") or item.get("name")
        state_id = item.get("id")
        if not name or not isinstance(state_id, int):
            continue
        flags.append({
            "id": state_id,
            "name": name,
            "enabled": bool(item.get("enabled", False)),
            "value": item.get("feature_state_value"),
            # Retain scope and multivariate data so a versioned update can
            # target the environment default without damaging overrides.
            "feature_segment": item.get("feature_segment"),
            "identity": item.get("identity"),
            "multivariate_feature_state_values": item.get(
                "multivariate_feature_state_values", []
            ),
        })
    return flags


def _typed_feature_state_value(value):
    """Convert the scalar returned by the environment API to the typed v2 format."""
    if isinstance(value, dict):
        return value
    if isinstance(value, bool):
        return {"type": "bool", "boolean_value": value}
    if isinstance(value, int):
        return {"type": "int", "integer_value": value}
    if isinstance(value, str):
        return {"type": "unicode", "string_value": value}
    raise FlagsmithError(
        f"Cannot safely preserve unsupported Flagsmith feature value type: {type(value).__name__}."
    )


def set_feature_enabled(feature_name, enabled):
    """Change one environment-default flag using Flagsmith v2 feature versioning.

    Legacy PATCH /environments/{key}/featurestates/{id}/ is rejected when v2
    feature versioning is enabled. Instead, create and immediately publish a
    new version containing only the requested default-state change.
    """
    _, environment_key = _config()
    flags = list_feature_states()
    target = next(
        (
            flag for flag in flags
            if flag["name"] == feature_name
            and flag["feature_segment"] is None
            and flag["identity"] is None
        ),
        None,
    )
    if target is None:
        raise FlagsmithError(
            f"Environment-default state for feature flag '{feature_name}' was not found."
        )
    if target["enabled"] is bool(enabled):
        requested = "ON" if enabled else "OFF"
        raise FlagsmithError(f"Feature flag '{feature_name}' is already {requested}; no new version was created.")
    if target["value"] is None:
        raise FlagsmithError(
            f"Cannot safely update '{feature_name}': Flagsmith did not return its current value."
        )

    environment_id, features = _environment_and_features(environment_key)
    feature = next(
        (
            item for item in features
            if isinstance(item, dict) and item.get("name") == feature_name
        ),
        None,
    )
    if not feature or not isinstance(feature.get("id"), int):
        raise FlagsmithError(f"Could not resolve the feature ID for '{feature_name}'.")

    # Version creation copies the current version. Updating only the default
    # state preserves the other settings and segment overrides. Publishing is
    # part of this same API operation, but still occurs only after UI approval.
    version = _request(
        "POST",
        f"/environments/{environment_id}/features/{feature['id']}/versions/",
        json={
            "description": f"FeatureGuard AI rollback: {feature_name} set to {'ON' if enabled else 'OFF'}",
            "feature_states_to_update": [{
                "enabled": bool(enabled),
                "feature_state_value": _typed_feature_state_value(target["value"]),
                "multivariate_feature_state_values": (
                    target["multivariate_feature_state_values"] or []
                ),
            }],
            "publish_immediately": True,
        },
    )
    if not isinstance(version, dict) or not version.get("uuid"):
        raise FlagsmithError(
            "Flagsmith did not return a published feature version; the new state cannot be verified."
        )

    updated = next(
        (
            flag for flag in list_feature_states()
            if flag["name"] == feature_name
            and flag["feature_segment"] is None
            and flag["identity"] is None
        ),
        None,
    )
    if updated is None or updated["enabled"] is not bool(enabled):
        raise FlagsmithError(
            "Flagsmith created a feature version, but verification did not confirm the requested state."
        )
    return updated
