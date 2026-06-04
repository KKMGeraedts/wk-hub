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

**Validation rules**:

- A participant can always view their own predictions.
- Other participants' prediction visibility is governed by tournament or match lock moments.

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

Represents the onboarding leaderboard preview and required prediction flow.

**Rules**:

- Profile navigation is inactive inside tutorial leaderboard preview.
- Completing the required onboarding prediction step leads to the leaderboard.
- Normal profile navigation remains available outside tutorial.
