import os, requests

def analyse_events(summary):
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        return {
            "configured": False,
            "message": "Grok is not configured yet. Add XAI_API_KEY to your private .env file.",
            "summary": summary
        }

    base_url = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
    model = os.getenv("XAI_MODEL", "grok-3-mini")
    prompt = (
        "You are FeatureGuard AI, a cautious product analytics assistant. "
        "Analyse the following aggregated application event data. "
        "Identify patterns and give evidence-based recommendations. "
        "Do not claim causation from correlation. If data is insufficient, say so. "
        "Return concise plain text with: Observations, Risks, Recommendations.\n\n"
        f"Event summary: {summary}"
    )
    def fail(msg, **extra):
        out = {"configured": True, "error": msg, "summary": summary}
        out.update(extra)
        return out

    def clean(text, key):
        text = (text or "").replace(key, "[redacted]")
        return text[:1500]

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2
            },
            timeout=45
        )
    except requests.exceptions.Timeout:
        return fail("AI request failed: timed out after 45s waiting for the xAI API.", model=model)
    except requests.exceptions.ConnectionError as exc:
        return fail(f"AI request failed: could not connect to {base_url} ({clean(str(exc), api_key)[:200]}).", model=model)
    except requests.exceptions.RequestException as exc:
        return fail(f"AI request failed: {type(exc).__name__}: {clean(str(exc), api_key)[:200]}", model=model)

    if not response.ok:
        body = clean(response.text, api_key)
        print(f"[featureguard.ai] xAI HTTP {response.status_code} model={model}: {body}", flush=True)
        return fail(
            f"AI request failed: xAI API returned HTTP {response.status_code} for model '{model}'. Response: {body}",
            status_code=response.status_code, response_body=body, model=model)

    try:
        payload = response.json()
    except ValueError:
        return fail(f"AI request failed: xAI returned invalid JSON (HTTP {response.status_code}): {clean(response.text, api_key)[:300]}",
                    status_code=response.status_code, model=model)
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return fail(f"AI request failed: unexpected response format from xAI: {clean(str(payload), api_key)[:500]}",
                    status_code=response.status_code, model=model)
    if not isinstance(content, str) or not content.strip():
        return fail("AI request failed: xAI returned an empty analysis.", model=model)
    return {"configured": True, "analysis": content, "model": model}
