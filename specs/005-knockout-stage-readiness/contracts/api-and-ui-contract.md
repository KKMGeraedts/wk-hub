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

The existing prediction save behavior remains the source of truth for saving score predictions, quiz answers, and Leeuwtjes. The Knockout Page should use the same participant-facing save semantics and lock validation as existing prediction surfaces.

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
- Clear state for unresolved Bracket Slots.
- Clear state for "Quiz question not set yet".
- No knockout wall-of-shame or group accountability section.
