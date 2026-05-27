# Talpa WK Pool

## App

Talpa WK Pool is a Flask + React app for a World Cup 2026 prediction pool.

It includes the match schedule, group standings, score predictions, quiz questions, Leeuwtjes score doublers, winner predictions, badges, and a leaderboard.

## Build, Run, and Host

Install dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-dev.txt
npm install
```

Build the frontend:

```bash
npm run build
```

Run the full app locally:

```bash
.venv/bin/python backend/app.py
```

Open `http://localhost:8000`.

For frontend development:

```bash
npm run dev
```

Vite runs on `http://localhost:5173` and proxies `/api` to the Flask app.

Host on Vercel from the repository root. The included `vercel.json` builds `frontend/dist` and routes `/api/*` to the Flask app. Set these environment variables in Vercel:

- `POSTGRES_URL` or `DATABASE_URL`
- `WK_HUB_SECRET`
