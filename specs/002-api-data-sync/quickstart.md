# Quickstart: API Data Sync

## Automated Checks

Run after implementation:

```bash
python3 -m unittest discover backend -p '*_test.py'
npm run build
npm run py:check
npm run check
```

## Local Setup

1. Install dependencies if needed:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/pip install -r requirements-dev.txt
   npm install
   ```

2. Configure local environment:

   ```bash
   cp .env.example .env
   ```

3. Set sync-related values in `.env` when testing provider calls:

   ```text
   API_FOOTBALL_KEY=...
   WK_HUB_SYNC_TOKEN=...
   ```

4. Start the app:

   ```bash
   .venv/bin/python backend/app.py
   ```

## Manual Scenario Review

## Current Sync And Read Paths

- Protected result sync enters through `/api/cron/api-football-sync` and `/api/admin/api-football/sync`.
- Protected squad sync enters through `/api/cron/api-football-squad-sync` and `/api/admin/api-football/squads/sync`.
- API-Football retrieval is currently performed by backend helper functions in `backend/app.py`.
- Raw fixture and squad payload history is stored in API-Football history tables.
- Current match facts are read from `match_results`, `match_events`, `match_clean_sheets`, and `player_match_stats`.
- Participant app reads enter through `/api/world-cup`, `/api/pool`, and `/api/profiles/<user_id>/predictions`.
- Scored leaderboard categories are stored in `computed_points` after provider-backed or manual fact changes. Leaderboard and profile payloads read those stored rows when present.
- Admin-only sync issues are stored in `admin_sync_notifications` and surfaced through the existing notification bell.

### Scenario 1: First post-match attempt only targets the due match

1. Set one match to be due for the first post-match result attempt.
2. Keep other matches before their sync window or already terminal.
3. Run the protected result sync.
4. Confirm only the due match is requested from the provider.
5. Confirm a sync attempt record exists for that match.

Expected result: unrelated completed history is not fetched.

### Scenario 2: Second post-match attempt updates partial facts

1. Seed or mock a first attempt with partial provider data.
2. Run the second attempt window for the same match.
3. Confirm raw history contains both payloads.
4. Confirm current provider-backed facts use newer values where no manual override exists.

Expected result: partial early data can be improved without losing audit history.

### Scenario 3: Manual override wins over provider update

1. Save a manual result, event, or player-stat correction as an admin.
2. Run a provider sync for the same match.
3. Confirm provider payload history is stored.
4. Confirm the manual fact remains the active scoring fact.
5. Confirm audit history identifies the manual change, source, actor, and reason.
6. If the match is not final, confirm participant scoring remains unchanged.

Expected result: provider updates do not undo admin corrections.

### Scenario 4: Manual override reversal

1. Start with a provider-backed fact.
2. Save a manual override.
3. Reverse the manual override.
4. Confirm the active scoring fact returns to the provider-backed value if available.

Expected result: overrides are reversible without editing predictions.

### Scenario 5: Missing provider fixture link

1. Make a match due for result sync without a provider fixture link.
2. Run result sync.
3. Confirm no result is published for that match.
4. Confirm a skipped `provider_sync_attempts` row exists.
5. Confirm admins receive a `sync_issue` notification.
6. Confirm repeating the same failure updates the active notification instead of creating duplicates.
7. Confirm normal users do not see provider error details.

Expected result: missing links are operationally visible but not user-facing errors.

### Scenario 6: Provider request failure

1. Link a due match to a provider fixture.
2. Make the provider request fail or omit that fixture from the response.
3. Run result sync.
4. Confirm a failed `provider_sync_attempts` row exists.
5. Confirm admins receive a `sync_issue` notification.
6. Confirm `/api/world-cup` and `/api/pool` do not expose provider error details.

Expected result: retrieval failures are admin-visible and participant-safe.

### Scenario 7: Stored computed points

1. Complete a match and sync result facts.
2. Confirm affected computed point rows are updated.
3. Load leaderboard and profile pages.
4. Confirm both surfaces show totals derived from the same stored computed points.

Expected result: leaderboard and profile scoring agree after recalculation.

## Production Notes

- Production still depends on `DATABASE_URL` or `POSTGRES_URL`.
- Vercel cron timing is approximate. The cron may run more often than match windows; app-level sync candidate selection enforces the 15-minute and 2-hour match windows and records terminal attempts.
- Result sync fetches only the relevant due match fixtures. Squad sync remains a separate rare job.
- Provider errors should be logged and surfaced to admins, not normal participants.
