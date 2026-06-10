# Contracts: API Data Sync

## Participant-Facing Contract

Normal participant routes must not trigger external provider retrieval.

Affected payloads:

- `GET /api/world-cup`
- `GET /api/pool`
- `GET /api/profiles/<user_id>/predictions`

Rules:

- These endpoints read app-owned static data, normalized facts, and stored computed points.
- These endpoints do not expose provider request errors.
- If a due match cannot be retrieved or linked, participant views show blank or pending result state rather than incorrect provider details.
- Participant prediction rows are never changed by provider sync, manual overrides, or computed scoring updates.

## Result Sync Contract

Protected sync routes continue to require the existing sync token protection.

### Scheduled result sync

`GET /api/cron/api-football-sync`

Behavior:

- Select only matches with due result sync attempt windows.
- Supported due windows are approximately:
  - first attempt: 15 minutes after the match
  - second attempt: 2 hours after the match
- Fetch provider data only for due linked matches.
- Do not re-fetch unrelated completed history.
- Store raw payload history for successful provider responses.
- Publish normalized provider-backed facts for result, events, clean sheets, and player stats.
- Preserve active manual overrides.
- Recalculate affected computed points when a done match has changed scoring facts.
- Create admin sync notifications for missing links and failed retrievals.

Example response:

```json
{
  "ok": true,
  "attempts": [
    {
      "target_type": "match_result",
      "target_id": "m001",
      "attempt_kind": "first_post_match",
      "status": "succeeded",
      "provider_key": "api-football",
      "changed_facts": ["result", "events", "player_stats"],
      "computed_points_updated": true
    }
  ],
  "skipped": [
    {
      "target_type": "match_result",
      "target_id": "m002",
      "reason": "not_due"
    }
  ]
}
```

### Manual result sync

`POST /api/admin/api-football/sync`

Existing route may remain, but behavior should align with the provider boundary.

Accepted body:

```json
{
  "match_id": "m001",
  "dry_run": false,
  "force": false
}
```

Rules:

- `match_id` should allow syncing one specific match.
- `dry_run` reports candidate attempts without provider writes.
- `force` is admin/sync-token-only and should not override active manual facts.
- If `match_id` is omitted for backward compatibility, the route must still not fetch unrelated history beyond due candidates.

## Squad Sync Contract

`POST /api/admin/api-football/squads/sync`

Rules:

- Squad sync remains separate from result sync.
- Squad sync targets missing or stale team profiles only.
- Squad sync is rare/manual or separately scheduled, not part of regular post-match result processing.
- Successful payloads are retained in raw history and normalized into app-owned team profile data.

## Admin Notification Contract

Admin notifications may be implemented through the existing notification-bell payload or a dedicated admin status endpoint.

Required notification cases:

- Due match has no provider fixture link.
- Provider request for a due match fails.
- Provider payload cannot be normalized enough to publish expected facts.

Notification item shape:

```json
{
  "type": "sync_issue",
  "target_type": "match_result",
  "target_id": "m001",
  "title": "Result sync needs attention",
  "body": "The match result could not be retrieved or linked.",
  "severity": "warning",
  "created_at": "2026-06-10T18:00:00Z"
}
```

Rules:

- Only admins receive these notifications.
- Normal participants do not receive provider error bodies or provider request metadata.
- Duplicate active notifications for the same target and issue type should be avoided.

## Manual Override Contract

Manual label/editor routes from the existing admin label feature remain admin-only.

Rules:

- Manual saves create audit entries.
- Manual values take precedence over provider-backed facts.
- Provider updates do not overwrite active manual values.
- Manual reversal restores current provider-backed values when available.
- Manual labels affect participant-visible scoring only after the match is done.
- Manual label routes must not write to participant prediction tables.

## Computed Points Contract

Leaderboard and profile payloads should use stored computed points for scored categories.

Rules:

- Computed rows are updated when scoring facts change for a done match.
- Computed rows are scoped enough to explain match score, quiz, Leeuwtje, tournament winner, top scorer, and striker points.
- Incomplete categories remain pending or absent until enough facts exist.
- Leaderboard and profile totals must agree because they read the same stored computed rows.

## Validation Contract

Implementation must support the following checks:

- A due-match sync requests only the due match.
- Missing fixture links produce admin notifications and no participant-facing wrong result.
- Partial provider data is stored and can be improved by the second sync attempt.
- Manual override wins over provider update.
- Manual override reversal restores provider-backed fact.
- Stored computed points update after fact changes and are read by both leaderboard and profile flows.
