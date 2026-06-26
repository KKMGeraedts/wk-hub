# API and UI Contract: Knockout Stage Readiness

## Participant Pool Payload Additions

The authenticated pool payload should expose a `knockout` projection for the Knockout Page.

```json
{
  "knockout": {
    "is_relevant": true,
    "rounds": [
      {
        "round": "Round of 32",
        "matches": [
          {
            "id": "m73",
            "match_number": 73,
            "round": "Round of 32",
            "date": "2026-06-29",
            "kickoff_at": "2026-06-29T19:00:00Z",
            "lock_at": "2026-06-29T18:00:00Z",
            "venue": {"id": "sofi", "name": "SoFi Stadium"},
            "home": {"kind": "slot", "label": "2A"},
            "away": {"kind": "slot", "label": "2B"},
            "status": "not_yet_actionable",
            "locked": false,
            "prediction": null,
            "quiz": null,
            "quiz_prediction": null,
            "missing_actions": []
          }
        ]
      }
    ],
    "missing_actions": [
      {
        "match_id": "m73",
        "kind": "prediction",
        "deadline": "2026-06-29T18:00:00Z"
      }
    ]
  }
}
```

## Status Semantics

- `not_yet_actionable`: one or both teams are still Bracket Slots.
- `open`: both teams are known and lock time has not passed.
- `locked`: lock time has passed and final scoring facts are not complete.
- `completed`: match has completed scoring facts.

## Team or Slot Shape

```json
{"kind": "team", "id": "ned", "name": "Netherlands"}
```

```json
{"kind": "slot", "label": "W73"}
```

## Existing Save Prediction Contract

The existing prediction save behavior remains the source of truth for saving score predictions, quiz answers, and Leeuwtjes. The Knockout Page should use the same participant-facing save semantics and lock validation as existing prediction surfaces, extended so draw predictions for Knockout Stage matches include a participant Advancing Team.

Knockout Stage score prediction request shape extends score predictions when needed:

```json
{
  "home_score": 1,
  "away_score": 1,
  "advancing_team_id": "ned"
}
```

Expected behavior:

- `advancing_team_id` is required for open Knockout Stage draw predictions.
- `advancing_team_id` is ignored or derived from the predicted score for non-draw Knockout Stage predictions.
- Locked draw predictions without `advancing_team_id` remain saved but do not earn outcome or exact-score points.

## Admin Quiz Setup Contract

Admins need a way to create or update quiz data for a match that has no existing quiz entry.

Request shape:

```json
{
  "question": "Wordt er in de verlenging gescoord?",
  "type": "yes_no",
  "choices": ["ja", "nee"],
  "choice_points": {"ja": 4, "nee": 2},
  "reason": "Initial knockout quiz setup"
}
```

Expected behavior:

- Admin-only.
- Supports Knockout Stage matches without existing quiz questions.
- Preserves auditability of setup and corrections.
- Does not mutate participant predictions except by causing pre-lock invalid answers to become Missing Actions.

## UI Contract

The Knockout Page must provide:

- Top-level route `/knockout`.
- Top-level nav item `Knockout` when `knockout.is_relevant` is true.
- Bracket-shaped visual layout with all 32 Knockout Match Tiles.
- Selectable tile state.
- Detail panel or bottom sheet for the selected tile.
- Score, quiz, and Leeuwtje controls in the detail panel only when allowed.
- Knockout score controls labelled as score after max 120 minutes.
- Advancing Team choice shown only when the entered Knockout Stage score is a draw.
- Penalty shootout score shown only as completed-result context.
- Clear state for unresolved Bracket Slots.
- Clear state for "Quiz question not set yet".
- No knockout wall-of-shame or group accountability section.

## Leaderboard Contract

Leaderboard rows should expose enough point categories for the total to be derived:

```json
{
  "points": 503,
  "match_points": 251,
  "quiz_points": 75,
  "scorer_points": 96,
  "leeuwtje_points": 81,
  "exact_scores": 4,
  "outcomes": 38,
  "leeuwtjes_available": 2,
  "leeuwtjes_total": 3
}
```

UI columns:

- `#`
- `Player`
- `PTS`
- `Match PTS`
- `Quiz PTS`
- `Scorer PTS`
- `Leeuwtje PTS`
- `Exact`
- `Outcome`

Rules:

- `PTS = Match PTS + Quiz PTS + Scorer PTS + Leeuwtje PTS`.
- `Match PTS = match_score_points + winner_points`.
- `Scorer PTS = top_scorer_points + striker_points`.
- `group_position_points` are not used in leaderboard totals.
- The old `Predictions` fraction column is removed.
- Numeric point/stat columns are sortable; `#` always shows overall rank.
- Sort ties fall back to overall leaderboard order.
- Hovering `Leeuwtje PTS` shows the active-stage Remaining Leeuwtje Count fraction, for example `3/3`, `2/3`, `1/3`, or `0/3`.
