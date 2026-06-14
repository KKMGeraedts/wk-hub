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
- `API_FOOTBALL_KEY` for post-match result and squad syncing
- `WK_HUB_SYNC_TOKEN` or `CRON_SECRET` to protect sync endpoints
- `API_FOOTBALL_SQUAD_SYNC_BATCH_SIZE`, optional, default `6`

`DATABASE_URL` must be present in the Vercel project for the API to start. `POSTGRES_URL` is also supported as a fallback. Without one of those values, `/api/health` returns a JSON `503` explaining the missing database configuration, and the app cannot load pool data.

After changing Vercel environment variables, redeploy and verify:

```bash
curl https://your-vercel-domain.vercel.app/api/health
```

The response should include `"ok": true` and `"database": "postgres:DATABASE_URL"`.

## Database Safety

Prediction writes are recorded in an append-only `prediction_audit_log` table before the live prediction tables are updated. This gives every save operation a replayable JSON trail in addition to the current table state.

Use the protected database endpoints with the same `WK_HUB_SYNC_TOKEN` or `CRON_SECRET` used for sync jobs:

```bash
curl -H "Authorization: Bearer $WK_HUB_SYNC_TOKEN" http://localhost:8000/api/admin/database/status
curl -H "Authorization: Bearer $WK_HUB_SYNC_TOKEN" \
  -o wk-hub-backup.json http://localhost:8000/api/admin/database/backup
```

The backup response includes deterministic table dumps, row counts, the schema version, and SHA-256 hashes for the static World Cup and quiz data files so a run can be reproduced from the same database and fixture data.

API-Football fixture and squad syncs also keep append-only raw snapshot history tables. The normalized result, event, player-stat, squad, and coach tables are current-state projections; the raw history tables preserve every provider payload received so a later parser change can be replayed without losing source data.

## API-Football Sync

The app can sync completed match data and team squads from API-Football using World Cup `league=1` and `season=2026`. Result sync is intentionally narrow: the app selects only matches whose post-match sync windows are due, currently around 5 minutes, 15 minutes, and 2 hours after the expected end of the match, and requests only those linked fixtures. The cron endpoint can run more frequently than those windows because the backend records terminal per-match attempts and skips unrelated history. Squad sync remains separate because squads are mostly fixed tournament data. Successful provider payloads are retained in raw history tables, while normalized result/event/player-stat rows feed the app. Normal participant views read app-owned schedule, result, profile, and scoring data; they do not call API-Football directly.

If a due result sync cannot run because the app match has no provider fixture link, the sync attempt is recorded as skipped and admins get a notification-bell item. If the provider request fails or does not return the linked fixture, the attempt is recorded as failed and admins get a deduplicated sync issue notification. Normal participants keep seeing a blank or pending result rather than provider failure details.

Useful endpoints:

```bash
curl -H "Authorization: Bearer $WK_HUB_SYNC_TOKEN" http://localhost:8000/api/admin/api-football/status
curl -X POST -H "Authorization: Bearer $WK_HUB_SYNC_TOKEN" -H "Content-Type: application/json" \
  -d '{"dry_run": true}' http://localhost:8000/api/admin/api-football/sync
curl -X POST -H "Authorization: Bearer $WK_HUB_SYNC_TOKEN" -H "Content-Type: application/json" \
  -d '{"match_id": "m001", "dry_run": true}' http://localhost:8000/api/admin/api-football/sync
curl -X POST -H "Authorization: Bearer $WK_HUB_SYNC_TOKEN" -H "Content-Type: application/json" \
  -d '{"dry_run": true}' http://localhost:8000/api/admin/api-football/squads/sync
```

Config:

- `API_FOOTBALL_DAILY_LIMIT`, default `90`
- `API_FOOTBALL_SQUAD_SYNC_BATCH_SIZE`, default `6`, because squads use one `players/squads` call and one `coachs` call per team
- `API_FOOTBALL_SQUAD_REFRESH_HOURS`, default `24`
- Result sync windows are app-defined at approximately 5 minutes, 15 minutes, and 2 hours after the expected match end. The expected end is controlled by `API_FOOTBALL_POSTMATCH_BUFFER_MINUTES`, default `135` minutes after kickoff. The Vercel result cron is configured to run every 5 minutes in UTC so those windows are picked up promptly; this requires a Vercel plan that supports more-than-daily cron frequency.
- Scoring fact changes recompute stored leaderboard point categories. Leaderboard and profile responses read those stored rows when present and fall back to live calculation for not-yet-computed categories.

## Newsletter Refresh

Home-page news is stored in the database and refreshed from RSS feeds by a daily Vercel cron. The app falls back to static articles when no refreshed articles are available yet.

Useful endpoints:

```bash
curl http://localhost:8000/api/newsletters
curl -X POST -H "Authorization: Bearer $WK_HUB_SYNC_TOKEN" \
  http://localhost:8000/api/admin/newsletters/refresh
curl -H "Authorization: Bearer $WK_HUB_SYNC_TOKEN" \
  http://localhost:8000/api/cron/newsletters-refresh
```

Config:

- `NEWSLETTER_MAX_ARTICLES`, default `6`

Vercel production does not have a durable local filesystem, so production must use Neon/Postgres through `DATABASE_URL`. Schema setup runs at API cold start through `CREATE TABLE IF NOT EXISTS`, but data population should be done through the protected sync endpoints or the included Vercel cron jobs. Do not rely on SQLite in production.
