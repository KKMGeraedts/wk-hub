# Data Model: Knockout Stage Readiness

## Knockout Stage

**Represents**: The elimination part of the tournament after the group stage, from Round of 32 through Final.

**Key fields**:

- `round`: Round of 32, Round of 16, Quarter-final, Semi-final, Third-place play-off, or Final
- `matches`: Knockout Stage matches ordered by bracket path and kickoff

**Rules**:

- Includes every non-group-stage match.
- Does not include group-stage matches.

## Knockout Match Tile

**Represents**: One selectable visual match in the bracket.

**Key fields**:

- `match_id`
- `match_number`
- `round`
- `date`
- `venue`
- `home_team` or `home_bracket_slot`
- `away_team` or `away_bracket_slot`
- `status`: not-yet-actionable, open, locked, completed
- `missing_actions`: personal missing score and/or quiz actions

**Rules**:

- A tile can be displayed before both teams are known.
- Prediction controls are available only through selected match details.

## Bracket Slot

**Represents**: A placeholder for a team that is not known yet.

**Key fields**:

- `label`: e.g. `1A`, `3C/E/F/H/I`, `W73`, `L101`
- `slot_type`: group position, prior winner, prior loser, or compound third-place path

**Rules**:

- A Bracket Slot is displayable but not predictable as a team.
- A match with one or more Bracket Slots does not count as a Missing Action.

## Missing Action

**Represents**: A prediction or quiz answer a participant can still complete before lock time.

**Key fields**:

- `kind`: score prediction or quiz answer
- `match_id`
- `deadline`
- `scope`: urgent reminder or knockout planning

**Rules**:

- Knockout Page planning includes all known open Knockout Stage Missing Actions.
- Existing urgent reminders remain limited to current and next matchday.
- A match with a missing quiz setup cannot create a quiz Missing Action.

## Quiz Question

**Represents**: A match-specific question participants answer before lock time.

**Key fields**:

- `match_id`
- `question`
- `answer_type`
- `answer_options`
- `scoring_values`
- `published_state`

**Rules**:

- Each Knockout Stage match can have one Quiz Question.
- Published questions should remain stable, with corrections reserved for mistakes.
- Quiz Question setup is independent from score prediction availability.

## Quiz Correction

**Represents**: A mistake fix to a published Quiz Question or answer options.

**Key fields**:

- `match_id`
- `changed_fields`
- `correction_time`
- `reason`
- `affected_answer_count`

**Rules**:

- Before lock time, existing answers remain valid if they still match corrected options.
- Before lock time, existing answers that no longer match corrected options become Missing Actions.
- After lock time, corrections do not automatically reopen participant answers.

## Knockout Score Prediction

**Represents**: A participant's predicted Knockout Stage score after maximum 120 minutes, plus the Advancing Team when the predicted score is a draw.

**Key fields**:

- `match_id`
- `home_score`
- `away_score`
- `advancing_team_id`

**Rules**:

- Penalty shootout goals are never part of `home_score` or `away_score`.
- `advancing_team_id` is required for open draw predictions.
- Non-draw predictions derive the participant's Advancing Team from the predicted score.
- Locked draw predictions without `advancing_team_id` can still earn home-goal and away-goal points, but cannot earn outcome or exact-score points.

## Leaderboard Points

**Represents**: The point categories shown in the leaderboard.

**Key fields**:

- `points`
- `match_points`
- `quiz_points`
- `scorer_points`
- `leeuwtje_points`

**Rules**:

- `points` is the sum of the four visible point categories.
- `match_points` includes score-prediction points and tournament winner points.
- `scorer_points` includes top-scorer and striker-pick points.
- `leeuwtje_points` includes only Leeuwtje points from scored matches.
- Group-position points are no longer used.

## Leeuwtje Stage Accounting

**Represents**: The active-stage Leeuwtje budget and remaining count shown from the leaderboard Leeuwtje Points hover.

**Key fields**:

- `active_stage`
- `assigned_count`
- `consumed_count`
- `remaining_count`
- `stage_total`

**Rules**:

- The active stage is Group Stage until all Group Stage matches have trusted final results; after that it is Knockout Stage.
- Every participant receives a fresh Knockout Stage Leeuwtje Budget when Knockout Stage becomes active.
- Historical Group Stage Leeuwtjes remain available for scoring but do not count against the Knockout Stage budget.
- Assigned Leeuwtjes count against save validation for the active stage.
- Only Consumed Leeuwtjes reduce Remaining Leeuwtje Count.

## State Transitions

```text
Bracket Slot match
  -> known open match        when both teams are known and lock time has not passed
  -> locked match            when lock time passes
  -> completed match         when trusted scoring facts are available

Unset quiz
  -> published quiz          when admin completes Quiz Setup
  -> corrected quiz          when admin fixes a published mistake

Valid quiz answer
  -> missing quiz action     when a pre-lock Quiz Correction invalidates the answer
  -> locked answer           when lock time passes

Group Stage Leeuwtje Budget
  -> Knockout Stage Leeuwtje Budget  when all Group Stage matches have trusted final results
```
