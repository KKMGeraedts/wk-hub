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
- Participant payloads may include prize-pot participation state and tournament-pick display metadata; these reads must not trigger provider calls.

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

## Account Creation Contract

### Login / implicit account creation

`POST /api/auth/login`

Accepted body:

```json
{
  "email": "firstname.lastname@talpanetwork.com",
  "password": "..."
}
```

Rules:

- Backend validation accepts new accounts only when the normalized email matches `firstname.lastname@talpanetwork.com` or `firstname.lastname@talpastudios.com`.
- Frontend validation, placeholders, and helper copy use the same Talpa Network or Talpa Studios convention.
- Email normalization trims whitespace and compares case-insensitively.
- Invalid domains and invalid local-part shapes return a clear validation error.
- Existing archived-account behavior remains unchanged.
- Admin defaults should be reviewed when domain constants change.

## Prize Pot Contract

### Pool payload

`GET /api/pool`

Additional current-user shape:

```json
{
  "prize_pot": {
    "status": "undecided",
    "contribution_amount": 10,
    "currency": "EUR",
    "organizer_name": "Olivier Thijsen",
    "payment_in_app": false
  },
  "notifications": [
    {
      "type": "prize_pot",
      "title": "Prize pot",
      "body": "Join the optional EUR 10 prize pot. The final prize amount is still to be determined. Olivier Thijsen organizes payment outside the app.",
      "actions": [
        {"id": "join", "label": "Join"},
        {"id": "decline", "label": "Decline"}
      ]
    }
  ]
}
```

Rules:

- The `prize_pot` notification is included only when the current participant status is `undecided`.
- Participants remain free to join or decline.
- The app does not process payment, payment confirmation, or payout allocation.

### Save prize-pot choice

`POST /api/prize-pot/participation`

Accepted body:

```json
{
  "status": "joined"
}
```

Rules:

- `status` must be `joined` or `declined`.
- The authenticated user can save only their own choice.
- Saving a choice updates persistent participation state and suppresses the future prompt.
- Response includes the updated status.

Example response:

```json
{
  "ok": true,
  "prize_pot": {
    "status": "joined",
    "contribution_amount": 10,
    "currency": "EUR",
    "organizer_name": "Olivier Thijsen",
    "payment_in_app": false
  }
}
```

### Profile payload

`GET /api/profiles/<user_id>/predictions`

Additional profile shape:

```json
{
  "user_id": 12,
  "name": "First Last",
  "prize_pot_status": "joined"
}
```

Rules:

- Profile views show whether the participant joined, declined, or has not answered.
- Payment status is not shown because it is outside app scope.

## Tournament Pick UI Contract

Affected surfaces:

- Prediction entry view
- Prediction adjust view
- Profile pick panel
- Leaderboard/profile summaries where tournament picks are shown

View-mode rules:

- The champion pick displays team name plus flag.
- The top-scorer pick displays full player name plus country flag/country when metadata exists.
- Each striker pick displays full player name plus country flag/country when metadata exists.
- If player metadata is missing, show the stored plain name without an incorrect flag.
- Clicking the component in view mode does not change predictions.

Edit-mode rules:

- An explicit edit button switches the component into editable controls.
- Edit mode is available only while tournament picks are unlocked.
- Existing lock validation in `POST /api/predictions` remains authoritative.
- Saving uses the existing prediction save contract with `winner_team_id`, `top_scorer_name`, and `striker_names`.

Example tournament pick summary:

```json
{
  "winner_pick": "NED",
  "winner_pick_name": "Netherlands",
  "winner_pick_flag": "🇳🇱",
  "top_scorer_pick": {
    "name": "Cody Gakpo",
    "country": "Netherlands",
    "flag": "🇳🇱"
  },
  "striker_picks": [
    {"name": "Kylian Mbappe", "country": "France", "flag": "🇫🇷"},
    {"name": "Harry Kane", "country": "England", "flag": "🏴"}
  ],
  "tournament_picks_locked": false,
  "tournament_picks_editable": true
}
```

## Validation Contract

Implementation must support the following checks:

- A due-match sync requests only the due match.
- Missing fixture links produce admin notifications and no participant-facing wrong result.
- Partial provider data is stored and can be improved by the second sync attempt.
- Manual override wins over provider update.
- Manual override reversal restores provider-backed fact.
- Stored computed points update after fact changes and are read by both leaderboard and profile flows.
- Talpa account validation accepts only the requested Talpa Network or Talpa Studios email convention for new accounts.
- Undecided participants receive and can answer the prize-pot notification.
- Saved prize-pot participation appears on profiles.
- Tournament pick view mode is read-only and shows flags/country context where available.
