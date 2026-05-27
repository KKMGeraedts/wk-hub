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

Host on Vercel from the repository root. The included `vercel.json` builds `frontend/dist` and routes `/api/*` to the Flask app.

For the database, create a Neon Serverless Postgres database from the Vercel Marketplace and connect it to this Vercel project. The Neon integration should add `DATABASE_URL` automatically. If it also adds `DATABASE_URL_UNPOOLED`, leave it in place; the app uses `DATABASE_URL` for normal requests and `DATABASE_URL_UNPOOLED` for schema setup.

Set these environment variables in Vercel:

- `DATABASE_URL`, created by Neon
- `WK_HUB_SECRET`
- `API_FOOTBALL_KEY` for post-match result syncing
- `WK_HUB_SYNC_TOKEN` or `CRON_SECRET` to protect sync endpoints

`DATABASE_URL` must be present in the Vercel project for the API to start. `POSTGRES_URL` is also supported as a fallback. Without one of those values, `/api/health` returns a JSON `503` explaining the missing database configuration, and the app cannot load pool data.

After changing Vercel environment variables, redeploy and verify:

```bash
curl https://your-vercel-domain.vercel.app/api/health
```

The response should include `"ok": true` and `"database": "postgres:DATABASE_URL"`.

## API-Football Sync

The app can sync completed match data from API-Football using World Cup `league=1` and `season=2026`. The sync is intentionally conservative: it only considers matches after the configured post-match buffer, stores the raw API payload, overlays final scores from the database into the app data, and records request usage so the free tier is not burned accidentally. The included Vercel cron runs once per day; use the same protected endpoint from an external scheduler if you want faster post-match refreshes.

Useful endpoints:

```bash
curl -H "Authorization: Bearer $WK_HUB_SYNC_TOKEN" http://localhost:8000/api/admin/api-football/status
curl -X POST -H "Authorization: Bearer $WK_HUB_SYNC_TOKEN" -H "Content-Type: application/json" \
  -d '{"dry_run": true}' http://localhost:8000/api/admin/api-football/sync
```

Config:

- `API_FOOTBALL_DAILY_LIMIT`, default `90`
- `API_FOOTBALL_POSTMATCH_BUFFER_MINUTES`, default `135`
- `API_FOOTBALL_FINAL_RESYNC_HOURS`, default `12`
