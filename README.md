# Talpa WK Pool

A Flask + React World Cup 2026 dashboard for a department watch list:

- group tables
- full match schedule in `Europe/Amsterdam`
- Netherlands-focused fixtures
- venues
- Talpa WK Pool login
- group-stage score predictions
- per-match quiz questions
- five Leeuwtjes score doublers per player
- World Cup winner predictions
- leaderboard scoring
- matchday overview, daily recap and badges

## Run Locally

Install dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-dev.txt
npm install
```

Build the React frontend:

```bash
npm run build
```

Run the Flask app:

```bash
.venv/bin/python backend/app.py
```

Then visit `http://localhost:8000`.

## Development

For frontend-only iteration, run Vite:

```bash
npm run dev
```

For local full-stack inspection, Flask serves `frontend/dist`, `/api/world-cup`, and the pool API.

## Quality Checks

Python quality tooling is configured in `pyproject.toml`:

```bash
npm run py:format
npm run py:lint
npm run py:typecheck
npm run py:check
```

Run the full app check before deployment:

```bash
npm run check
```

Backend logs go to stdout. Set `WK_HUB_LOG_LEVEL=DEBUG` for noisier local diagnostics.

## Vercel

Deploy from the repository root. `vercel.json` builds the Vite frontend into `frontend/dist`, serves it as the static output, and routes `/api/*` to the Flask app through `api/index.py`.

Set these Vercel environment variables before deploying:

- `POSTGRES_URL` or `DATABASE_URL`: a durable Postgres database URL for pool users and predictions.
- `WK_HUB_SECRET`: a stable random secret used to sign login session cookies.

Local development uses `backend/pool.db` by default. Vercel Functions do not provide durable local file storage, so production must use Postgres.

## Pool

Pool data is stored locally in `backend/pool.db`, or in Postgres when `POSTGRES_URL` or `DATABASE_URL` is set.

Current scoring:

- group stage exact score: 45 points
- group stage correct outcome: 30 points
- group position correct: 25 points
- Round of 32 exact/outcome: 90/60 points
- Round of 16 exact/outcome: 135/90 points
- quarter-final exact/outcome: 180/120 points
- semi-final exact/outcome: 225/150 points
- final exact/outcome: 270/180 points
- World Cup winner: 250 points
- quiz yes/no correct: 15 points
- quiz open answer correct: 50 points
- quiz kijkcijfers closest answer: 30 points

Every player has 5 Leeuwtjes. A Leeuwtje doubles the match-prediction points for
one fixture and is consumed once that fixture locks, regardless of whether the
prediction scores points.

Group-stage predictions are open immediately. Knockout predictions are designed to unlock only when the match has confirmed teams.

Quiz questions live in `backend/quiz-2026.json` and are merged into
`/api/world-cup`. Correct quiz answers should be filled after the final whistle
from an official match-event/stat feed. The data model supports exact answers
with `correct_answer` or `correct_answers`, plus `viewership_answer` for the
closest kijkcijfers scoring.

## Data

The app uses a bundled fallback snapshot served by Flask. The group-stage dates and times are parsed from `wkvoetbal.nl` in Dutch time; Group F venues are cross-checked against current schedule pages; knockout scaffolding and base venue records come from `wc26-mcp@0.3.1`.

For live results and standings, put a provider behind a small server endpoint instead of exposing tokens in browser code. Shortlist:

- `Sportmonks`: Dutch-language docs/site, paid, comprehensive World Cup API.
- `wc2026api.com`: lightweight developer API if accessible from your network.
- FIFA and Dutch public schedule pages: useful for validation, not a stable app API.

Live provider integration should be added in Flask, not in React, so API tokens stay server-side.
