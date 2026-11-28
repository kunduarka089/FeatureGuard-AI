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
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return {"configured": True, "analysis": content, "model": model}
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        return {"configured": True, "error": f"AI request failed: {type(exc).__name__}", "summary": summary}
