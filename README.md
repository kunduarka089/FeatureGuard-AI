# FeatureGuard AI

AI-powered feature intelligence and incident recovery using Flagsmith.

## Current MVP status

This initial milestone includes:
- Flask backend and mobile-friendly dashboard
- SQLite event storage
- Event ingestion API
- Feature performance aggregation
- Optional Grok analysis through the xAI API
- Basic automated tests

Flagsmith flag evaluation, management actions, human approval workflow, continuous monitoring and the shopping demo are planned for subsequent milestones. They are not implemented yet.

## Run locally

1. Install Python 3.10 or newer.
2. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and add your xAI API key if you want AI analysis.
4. Start the app:

   ```bash
   python app.py
   ```

5. Open `http://localhost:5000`.

On Windows, activate the environment with `.venv\\Scripts\\activate`.

## API examples

Record an event:

```bash
curl -X POST http://localhost:5000/api/events \\
  -H "Content-Type: application/json" \\
  -d '{"event_name":"checkout_completed","feature_name":"new_checkout","success":true,"value":1}'
```

View event aggregates: `GET /api/summary`

Run AI analysis: `POST /api/ai/analyse`

## Secrets

Never commit `.env`, API keys, passwords or private tokens. Use `.env.example` as a template.
