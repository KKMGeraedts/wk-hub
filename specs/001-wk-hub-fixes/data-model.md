# Data Model: WK Hub Fixes

## Participant

Represents a pool user.

**Existing fields involved**:

- `id`
- `name`
- `email`
- `profile_image_url`

**Relationships**:

- Has many match predictions.
- Has zero or one champion prediction.
- Has zero or one top scorer / striker prediction record.
- Has many quiz predictions.
- Has many Leeuwtje predictions.
- Has one leaderboard row after account creation, even when all prediction relationships are empty.

**Validation rules**:

- A participant can always view their own predictions.
- Other participants' prediction visibility is governed by tournament or match lock moments.
- Prediction completion is not a prerequisite for app access or leaderboard inclusion.

## App Participant

Represents an account user participating in the pool.

**Existing storage involved**:

- `users`

**Fields**:

- `id`
- `name`
- `email`
- `profile_image_url`

**State transitions**:

1. Created account with zero predictions and zero points.
2. Partial prediction progress as match/tournament picks are saved.
3. Complete prediction progress if all tracked predictions are filled in.

**Validation rules**:

- Account creation is sufficient for leaderboard inclusion.
- Missing predictions produce zero prediction-derived points and incomplete progress indicators.
- Missing champion, top scorer, or striker picks are empty/not chosen states, not invalid participation states.
- App functionality remains available unless a separate authentication or lock rule blocks a specific action.

## Tournament Pick

Represents champion, top scorer, and five striker selections for a participant.

**Existing storage involved**:

- Champion pick: `winner_predictions`
- Top scorer and striker picks: `top_scorer_predictions`

**Fields**:

- `winner_team_id`
- `top_scorer_name`
- `striker_names[0..4]`
- `updated_at`

**State transitions**:

1. Editable and private before tournament-pick lock/reveal time.
2. Locked and public at or after tournament-pick lock/reveal time.

**Validation rules**:

- Champion must be a participating team.
- Top scorer may be any available/selectable player and is not constrained by champion.
- Strikers may be any available/selectable players and are not constrained by champion.
- Duplicate striker names are not allowed.
- Picks cannot be changed after tournament-pick lock time.

## Match Prediction

Represents a participant's match-specific prediction details.

**Existing storage involved**:

- `match_predictions`
- `quiz_predictions`
- `leeuwtje_predictions`

**Fields**:

- `match_id`
- `home_score`
- `away_score`
- `quiz_answer`
- `viewership_prediction`
- `leeuwtje_active`
- `updated_at`

**State transitions**:

1. Editable and private from other participants before the individual match lock time.
2. Locked and visible to other participants at or after the individual match lock time.

**Validation rules**:

- Score values must remain within existing score limits.
- Match prediction details cannot be changed after the individual match lock time.
- Own match prediction details remain visible to the owner regardless of lock/completion state.

## Player Option

Represents a selectable player for top scorer and striker picks.

**Fields**:

- `name`
- `team_id`
- `team_name`
- `role` or position metadata when available
- display label distinguishing duplicate names

**Validation rules**:

- Search should match player name and team name.
- Duplicate player display names must be distinguishable by team.
- Saved values not currently in the option list should remain manageable for their owner before lock time.

## Leaderboard Row

Represents a ranked participant summary.

**Fields involved**:

- `user_id`
- `name`
- `profile_picture`
- rank and rank movement
- point totals and scoring metrics
- prediction completion counts
- badge/progress summaries

**Visibility rules**:

- Must not expose top scorer or striker names in leaderboard display.
- Tournament-pick names for other participants must be masked in response data before reveal if included for any downstream surface.
- Profile navigation is enabled in normal leaderboard contexts and disabled in tutorial preview contexts.
- Must be created for every account user regardless of prediction completion.
- Completion booleans/counts describe progress only and must not determine whether the row exists.

## Profile View

Represents detailed participant information.

**Fields involved**:

- Participant identity and avatar
- Ranking/scoring summary
- Tournament picks when visibility allows
- Match prediction groups when visibility allows
- Badge/progress details

**Visibility rules**:

- Own profile shows own tournament picks and match predictions.
- Other profiles hide tournament-pick names before tournament reveal.
- Other profiles show match-specific prediction details only for matches that have reached lock time.

## Tutorial Context

Represents the onboarding leaderboard preview and optional prediction flow.

**Rules**:

- Profile navigation is inactive inside tutorial leaderboard preview.
- Completing or skipping any onboarding prediction prompt leads to normal app views without affecting leaderboard eligibility.
- Tutorial/onboarding text must not claim that predictions are required to join or appear in the leaderboard.
- Normal profile navigation remains available outside tutorial.

## Admin User

Represents an account user with elevated permissions.

**Existing storage involved**:

- `users`

**Fields**:

- `id`
- `name`
- `email`
- `is_admin`
- `archived_at`

**Validation rules**:

- Only admin users may inspect or update scoring labels.
- Admin users may manage scoring labels and accounts.
- Admin users must not update another participant's prediction records.
- Non-admin users must receive an authorization error for admin label routes.

## Match Result Label

Represents the actual score/result label used to score match predictions and group standings.

**Existing storage involved**:

- `match_results`

**Fields**:

- `match_id`
- `source`
- `source_fixture_id`
- `status_long`
- `status_short`
- `elapsed`
- `home_score`
- `away_score`
- `synced_at`

**State transitions**:

1. Missing before API-Football sync or manual entry.
2. API-sourced after successful API-Football result sync.
3. Manual/admin-sourced after admin correction or fallback entry.

**Validation rules**:

- Scores must be whole numbers in the same accepted score range as match predictions.
- Manual result labels are scoring labels only and must not mutate `match_predictions`.
- Scoring should use manual/admin labels where present and otherwise use API-Football labels.

## Match Event Label

Represents goal/scorer event labels used for top scorer and striker scoring.

**Existing storage involved**:

- `match_events`

**Fields**:

- `match_id`
- `provider_event_key`
- `elapsed`
- `local_team_id`
- `team_name`
- `api_player_id`
- `player_name`
- `event_type`
- `detail`
- `comments`
- `raw_json`
- `updated_at`

**Validation rules**:

- Goal event labels should identify scorer name and team when known.
- Own goals and non-goal events must not incorrectly count as striker goals.
- Manual event edits must feed `goal_counts_by_player()` or equivalent scoring helper.
- Manual event edits must not mutate `top_scorer_predictions`.

## Player Stat Label

Represents synced or manually corrected player statistics relevant for inspection and future scoring labels.

**Existing storage involved**:

- `player_match_stats`

**Fields**:

- `match_id`
- `provider_player_key`
- `local_team_id`
- `team_name`
- `api_player_id`
- `player_name`
- `minutes`
- `position`
- `goals`
- `assists`
- `clean_sheet`
- `raw_json`
- `updated_at`

**Validation rules**:

- Stats must remain tied to a match and player identity.
- Goal totals should remain consistent with goal event labels or clearly show source/override state.
- Manual stat edits are label edits only and must not mutate participant predictions.

## Quiz Label Override

Represents DB-backed admin overrides for quiz labels that are otherwise loaded from static quiz data.

**Storage involved**:

- New or extended DB-backed quiz label override storage

**Fields**:

- `match_id`
- `correct_answer`
- `correct_answers`
- `viewership_answer`
- `source`
- `updated_by_user_id`
- `updated_at`

**State transitions**:

1. Missing, so scoring uses static quiz data.
2. Present, so scoring uses admin override values.
3. Cleared, so scoring returns to static quiz data.

**Validation rules**:

- Correct-answer overrides must match the quiz type and allowed choices when choices exist.
- Viewership answers must be whole numbers when present.
- Overrides affect quiz scoring only and must not mutate `quiz_predictions`.

## Label Audit Entry

Represents traceability for manual scoring-label changes.

**Storage involved**:

- Existing `prediction_audit_log` if scoped clearly, or a new label-specific audit table if implementation needs distinct retention

**Fields**:

- `id`
- `admin_user_id`
- `label_type`
- `match_id`
- `before`
- `after`
- `created_at`

**Validation rules**:

- Every manual label update should record who changed it and when.
- Audit entries must not contain participant prediction edits.

## Actionable Notification

Represents a notification-bell item that points to a specific missing user action.

**Storage involved**:

- Computed from existing match, prediction, quiz, and lock state.

**Fields**:

- `type`
- `count`
- `items`
- `match_id`
- `title`
- `body`
- `action_label`
- `target_view`
- `target_match_id`
- `target_kind`
- `locked_at`

**Relationships**:

- Belongs to the current viewer's pool state.
- References one or more matches.
- May reference quiz metadata for quiz-specific actions.

**Validation rules**:

- Only unlocked, currently editable missing items may appear as actionable reminders.
- Completed items must be removed on refresh.
- Each item should include enough match/team/date context to identify what is missing.
- Action targets must not expose other users' private predictions.

## Admin Broadcast Notification

Represents an admin-authored message shown through the notification bell.

**Storage involved**:

- New DB-backed broadcast notification storage.

**Fields**:

- `id`
- `title`
- `body`
- `created_by_user_id`
- `created_at`
- `starts_at`
- `expires_at`
- `is_active`
- `deactivated_at`

**Relationships**:

- Created by one admin user.
- Visible to active, non-archived users while active.

**Validation rules**:

- Only admins may create, update, or deactivate broadcasts.
- Title and body must be non-empty after trimming.
- Broadcasts should be included in notification-bell payloads without changing prediction state.
- Expired or inactive broadcasts must not appear as active notifications.

## Derived Real Name

Represents a display-only identity derived from a user's email.

**Storage involved**:

- Existing `users.email`; no separate editable first/last-name storage is planned.

**Fields**:

- `first_name`
- `last_name`
- `full_name`
- `email`

**Validation rules**:

- Email must match `firstname.lastname@talpanetwork.com` for newly created accounts.
- Casing may be normalized for parsing and storage.
- The nickname in `users.name` remains independently editable and primary.
- Derived name fields are display metadata and must not be used as authentication credentials.

## Talpa Email Identity

Represents the account creation eligibility rule for user emails.

**Storage involved**:

- Existing `users.email`.

**Accepted format**:

- `firstname.lastname@talpanetwork.com`

**Validation rules**:

- Domain must be exactly `talpanetwork.com` after normalization.
- Local part must contain a first-name segment and a last-name segment separated by a single derivable dot structure.
- Empty segments, missing dot, missing domain, alternate domains, and plus-addressed variants are rejected for account creation.
- Server-side validation is authoritative; frontend validation is advisory.

## Quiz Metadata Override

Represents admin-authored runtime overrides for quiz content, not participant answers.

**Storage involved**:

- Existing `quiz_label_overrides` may be extended, or a new quiz metadata override table may be added if cleaner during implementation.

**Fields**:

- `match_id`
- `question`
- `choices`
- `correct_answers`
- `viewership_answer`
- `source`
- `updated_by_user_id`
- `updated_at`

**Relationships**:

- References a match quiz definition.
- Affects prediction-entry display and scoring.
- Does not reference participant quiz prediction rows.

**Validation rules**:

- Question text must be non-empty when overridden.
- Choice-based quizzes must have non-empty answer options.
- Correct answers should match available choices when choices exist.
- Existing participant predictions remain unchanged even if option text is corrected.
- Every save should record admin and timestamp metadata.

## Wall of Shame Entry

Represents an active user's currently open missing prediction actions.

**Storage involved**:

- Computed from `users`, prediction tables, quiz predictions, world cup match data, and lock state.

**Fields**:

- `user_id`
- `nickname`
- `first_name`
- `last_name`
- `profile_image_url`
- `missing_count`
- `missing_items`
- `match_id`
- `kind`
- `match_label`
- `deadline`

**Relationships**:

- One entry per active user with one or more currently open missing items.
- Each missing item references a match or quiz action.

**Validation rules**:

- Archived users are excluded.
- Users with no currently open missing items are excluded.
- Locked matches and completed predictions/quizzes are excluded.
- Missing item context may identify the match/action but must not reveal prediction contents.
