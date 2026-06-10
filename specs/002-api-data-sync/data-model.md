# Data Model: API Data Sync

## Existing Entities To Preserve

### API-Football Team Link

Maps an app team to an API-Football team.

Current storage: `api_football_team_links`

Key fields:

- `local_team_id`
- `api_team_id`
- `api_team_name`
- `confidence`
- `linked_at`

Validation:

- Team links should exist before squad sync.
- Missing links should prevent that team from syncing and produce operational visibility.

### API-Football Fixture Link

Maps an app match to an API-Football fixture.

Current storage: `api_football_fixture_links`

Key fields:

- `match_id`
- `api_fixture_id`
- `api_home_team_id`
- `api_away_team_id`
- `api_home_team_name`
- `api_away_team_name`
- `confidence`
- `linked_at`

Validation:

- A due result sync with no fixture link must leave the result blank and notify admins.
- Fixture links are expected to exist before match result sync is due.

### Raw Provider Snapshot

Permanent copy of provider payloads received during sync.

Current storage:

- `api_football_fixture_snapshot_history`
- `api_football_team_squad_snapshot_history`

Planned behavior:

- Keep all successful provider payloads permanently.
- Keep latest snapshot tables as convenience projections.
- Do not score directly from raw payloads.

### Normalized Current Facts

App-owned facts used by scoring and inspection.

Current storage:

- `match_results`
- `match_events`
- `match_clean_sheets`
- `player_match_stats`
- `quiz_label_overrides`

Validation:

- Provider-backed facts can be overwritten by newer provider data.
- Manual facts must not be overwritten by provider data unless the manual override is reversed.
- Partial facts can be stored when complete facts are unavailable.

### Label Audit Log

Records admin changes to scoring labels.

Current storage: `label_audit_log`

Planned behavior:

- Record actor, timestamp, label type, match id, previous value, new value, source, and optional reason where implementation supports it.
- Use for manual override and reversal audit trails.

## New Or Extended Entities

### Sync Attempt

Represents one app-level attempt to retrieve or process external data.

Recommended storage: new `provider_sync_attempts` table.

Fields:

- `id`
- `provider_key`
- `target_type`: `match_result` or `team_squad`
- `target_id`: app match id or app team id
- `attempt_kind`: `first_post_match`, `second_post_match`, `manual`, or `squad_refresh`
- `scheduled_for`
- `started_at`
- `finished_at`
- `status`: `pending`, `running`, `succeeded`, `skipped`, `failed`
- `provider_request_id`
- `raw_snapshot_id`
- `failure_code`
- `failure_message`
- `created_at`

Relationships:

- Match result attempts reference app matches through `target_id`.
- Team squad attempts reference app teams through `target_id`.
- Successful provider attempts can reference raw snapshot history rows.

Validation:

- A match should have at most one succeeded or terminal attempt per scheduled attempt kind.
- Attempt records should exist for missing-link and failed-request outcomes, even when no provider payload is stored.

State transitions:

1. `pending`
2. `running`
3. `succeeded`, `skipped`, or `failed`

### Provider Source

Represents an external data provider as an app concept.

Recommended implementation:

- Use stable provider keys such as `api-football`.
- Avoid exposing provider-specific names in participant-facing payloads unless explicitly needed for admin inspection.

Fields:

- `provider_key`
- `display_name`
- `enabled`
- `configured`

Validation:

- At least `api-football` must be supported initially.
- Future providers should publish equivalent normalized facts.

### Manual Override

Represents an admin-authored replacement for a scoring fact.

Recommended storage:

- Extend existing normalized fact tables where a fact is match-bound and source-specific.
- Use `label_audit_log` for immutable audit entries.

Fields:

- `fact_type`
- `match_id`
- `fact_key`
- `value_json`
- `source`: `manual`
- `updated_by_user_id`
- `updated_at`
- `reverted_at`
- `reverted_by_user_id`
- `reason`

Validation:

- Manual overrides must not update participant prediction tables.
- Manual overrides affect visible scoring only when the match is done.
- Reversal restores provider-backed value if one exists; otherwise the fact becomes missing/pending.

### Computed Points

Stores participant scoring output derived from predictions plus current scoring facts.

Recommended storage: new `computed_points` table.

Fields:

- `user_id`
- `scope_type`: `match`, `tournament`, or `quiz`
- `scope_id`: match id or tournament-level category id
- `category`: `match_score`, `leeuwtje`, `quiz`, `winner`, `top_scorer`, `striker`, or future category
- `points`
- `details_json`
- `facts_revision_key`
- `computed_at`

Relationships:

- References users by `user_id`.
- References match ids for match-bound categories.
- Reads predictions but never mutates prediction rows.

Validation:

- One current computed row per user/scope/category.
- Affected rows must be recalculated after scoring facts change for done matches.
- Incomplete categories should remain absent or pending rather than using incorrect points.

### Admin Sync Notification

Represents operational sync issues visible only to admins.

Recommended storage:

- Reuse or extend notification-bell storage if suitable.
- Otherwise add a focused `admin_sync_notifications` table.

Fields:

- `id`
- `type`: `missing_provider_link`, `provider_request_failed`, `normalization_failed`
- `target_type`
- `target_id`
- `title`
- `body`
- `is_active`
- `created_at`
- `resolved_at`
- `related_attempt_id`

Validation:

- Normal participants must not receive provider failure details.
- Duplicate active notifications should be avoided for the same target and failure type.

## Source Precedence

For any scoring fact:

1. Active manual override
2. Latest normalized provider-backed fact
3. Static fallback data when applicable
4. Missing/pending

Provider updates may update provider-backed facts and raw history, but they must not change active manual override facts.

## Scoring Recalculation Rules

- Recalculate affected computed points after a done match receives new provider-backed facts.
- Recalculate affected computed points after manual override save or reversal for a done match.
- Do not expose scoring changes from manual labels before a match is done.
- Do not mutate `match_predictions`, `quiz_predictions`, `leeuwtje_predictions`, `winner_predictions`, or `top_scorer_predictions`.
