# FeatureGuard AI

AI-powered feature intelligence and safer incident recovery using Groq and Flagsmith.

## Current MVP

- Flask dashboard with mobile-friendly event collection and feature performance summaries.
- Groq-powered FeatureMind analysis using an OpenAI-compatible API endpoint.
- Server-side Flagsmith Management API integration to read feature states.
- RollbackAI preview for the allowlisted `new_checkout` flag.
- Explicit, one-time approval required before switching the flag OFF.
- After an approved update, the app reads Flagsmith again to verify the flag is OFF.
- Basic backend and rollback workflow tests.

## Required environment variables

Configure these in your hosting provider's secret environment settings. Never commit real values.

| Variable | Purpose |
|---|---|
| `XAI_API_KEY` | Groq API key (kept under this existing variable name for compatibility) |
| `XAI_BASE_URL` | `https://api.groq.com/openai/v1` |
| `XAI_MODEL` | `openai/gpt-oss-120b` |
| `FLAGSMITH_API_TOKEN` | Secret Flagsmith Organisation Management API token |
| `FLAGSMITH_ENVIRONMENT_KEY` | Development environment key used to address its feature states |
| `FLAGSMITH_API_URL` | `https://api.flagsmith.com` |
| `ROLLBACK_ALLOWED_FLAGS` | Defaults to `new_checkout`; comma-separated allowlist |

The Flagsmith Management API token must remain server-side. The environment key is used by the server in the Management API path; neither key is sent to browser JavaScript.

## Run locally

1. Install Python 3.10 or newer.
2. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in the values above.
4. Start the app:

   ```bash
   python app.py
   ```

5. Open `http://localhost:5000`.

On Windows, activate the environment with `.venv\\Scripts\\activate`.

## Demo flow

1. Send application events from the event collector.
2. Run FeatureMind to get an evidence-aware analysis from Groq.
3. RollbackAI reads feature states from the configured Flagsmith environment.
4. If `new_checkout` is ON, choose **Prepare rollback**.
5. Review the proposed change and explicitly approve it.
6. The backend switches the flag OFF through Flagsmith and reads it again to verify the new state.

Preparing a rollback does not change a flag. Approval tokens are short-lived (5 minutes), one-time, and stored in server memory. Restarting the service invalidates pending approvals.

## API

- `GET /api/health`
- `POST /api/events`
- `GET /api/events`
- `GET /api/summary`
- `POST /api/ai/analyse`
- `GET /api/flagsmith/flags`
- `POST /api/rollback/request`
- `POST /api/rollback/approve`

## Tests

Run `pytest -q`.

## Important MVP limitations

- Anomaly detection and automated incident correlation are not yet implemented; the current rollback preview is manually initiated.
- Only `new_checkout` is allowlisted by default.
- Pending approvals are held in memory and disappear on restart.
- The current SQLite database is on the host's local filesystem; on ephemeral hosting it is not durable.
- Add application authentication before using this with real users or production systems.
