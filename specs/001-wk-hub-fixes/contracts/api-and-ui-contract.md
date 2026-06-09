# Contracts: WK Hub Fixes

## API/Data Response Contract: Pool State

### Visibility metadata

Pool state should expose tournament-pick visibility metadata for frontend decisions.

```json
{
  "visibility": {
    "tournament_picks_revealed": false,
    "tournament_picks_reveal_at": "2026-06-11T...Z"
  }
}
```

Alternatively, equivalent fields may live under the existing `locks` object if names remain clear.

### Leaderboard rows before tournament reveal

For rows representing users other than the current viewer, hidden tournament-pick names must not be exposed.

```json
{
  "user_id": 2,
  "name": "Participant",
  "winner_pick": null,
  "winner_pick_name": null,
  "top_scorer_pick": null,
  "striker_picks": [],
  "top_scorer_picks": []
}
```

Rows for the current viewer may include the viewer's own picks before reveal.

### Leaderboard eligibility

Pool state must include a leaderboard row for every account user. The backend must not filter leaderboard rows by Netherlands group completion, all-prediction completion, champion selection, top scorer selection, striker selection, or tutorial completion.

```json
{
  "user_id": 9,
  "name": "New Participant",
  "points": 0,
  "all_predictions_complete": false,
  "entry_complete": false,
  "winner_pick": null,
  "winner_pick_name": null,
  "top_scorer_pick": null,
  "top_scorer_picks": []
}
```

Completion fields may remain in the response as progress indicators, but they are not eligibility fields.

### Leaderboard display contract

Leaderboard UI must display ranking/scoring information and profile navigation, but not top scorer or striker names. Champion/winner display should not be used as a primary reveal surface.

## API/Data Response Contract: Profile Predictions

### Other participant before match lock

Match-specific prediction details for an unlocked match must be omitted from another participant's profile prediction groups.

### Other participant at or after match lock

Match-specific prediction details for a locked match may be included, even before kickoff or final result.

```json
{
  "match_id": "m1",
  "home_score": 2,
  "away_score": 1,
  "quiz_answer": "ja",
  "viewership_prediction": 1234567,
  "leeuwtje": true
}
```

### Own profile

Current viewer's own prediction groups may include all own match prediction details regardless of lock or completion state.

## UI Contract: Searchable Player Picker

The scorer/striker picker must provide:

- A visible label for the field.
- A text entry/search affordance.
- Filtering by player name.
- Filtering by team name.
- Clear display of player and team.
- Empty-result messaging.
- Clear action for removing a selected value.
- Disabled/locked state after tournament-pick lock time.
- Duplicate striker prevention across striker slots.

## UI Contract: Tutorial Leaderboard Preview

In tutorial context:

- Leaderboard rows may display ranking information.
- Profile picture and player name are not interactive profile links.
- Continuing, completing, or skipping any onboarding prediction prompt routes to normal app views without changing leaderboard eligibility.
- Copy must not state that completing predictions is required to join the app or appear in the leaderboard.

## UI Contract: Normal Leaderboard

In normal leaderboard context:

- Profile picture opens the participant profile.
- Player name opens the participant profile.
- Top scorer and striker names are not displayed in leaderboard columns.
- Users with no predictions are displayed with zero points and incomplete/missing-prediction progress states.
- Empty leaderboard messaging must only appear when there are no account users available to display, not when account users lack predictions.

## UI Contract: Profile Page

Profile page must:

- Omit the profile-specific `Back to leaderboard` control.
- Keep long participant names, player names, and labels readable.
- Show tournament-pick privacy messaging before reveal when viewing another participant.
- Show tournament picks after reveal when viewing another participant.
- Always show own tournament picks to the owner subject to editability controls.

## API Contract: Admin Labels

All admin label endpoints require an authenticated admin user. Non-admin users receive `403`; anonymous users receive `401`.

### Inspect labels

`GET /api/admin/labels`

Returns scoring labels grouped by match.

```json
{
  "matches": [
    {
      "match_id": "m1",
      "home_team_id": "ned",
      "away_team_id": "usa",
      "result": {
        "home_score": 2,
        "away_score": 1,
        "status_short": "FT",
        "source": "api-football",
        "updated_at": "2026-06-12T..."
      },
      "quiz": {
        "question": "Will there be a penalty?",
        "correct_answer": "ja",
        "viewership_answer": null,
        "source": "static"
      },
      "events": [
        {
          "event_id": "manual:m1:1",
          "event_type": "Goal",
          "detail": "Normal Goal",
          "player_name": "Player Name",
          "team_name": "Netherlands",
          "source": "manual"
        }
      ],
      "player_stats": []
    }
  ]
}
```

### Update result label

`PATCH /api/admin/labels/<match_id>/result`

Allowed fields:

- `home_score`
- `away_score`
- `status_short`
- `status_long`
- `elapsed`

Writes the match result label used by `match_prediction_points()` and group-position scoring.

### Update quiz label

`PATCH /api/admin/labels/<match_id>/quiz`

Allowed fields:

- `correct_answer`
- `correct_answers`
- `viewership_answer`
- `clear_override`

Writes or clears DB-backed quiz label overrides used by quiz scoring.

### Update goal/event labels

`PUT /api/admin/labels/<match_id>/events`

Replaces the editable goal/scorer labels for a match. Events must include enough identity to count goals consistently:

- `player_name`
- `team_name` or `local_team_id`
- `event_type`
- `detail`
- `elapsed`

### Update player stat labels

`PUT /api/admin/labels/<match_id>/player-stats`

Updates inspection/scoring-relevant player stat labels for a match.

### Prediction immutability guarantee

Admin label endpoints must not write to:

- `match_predictions`
- `quiz_predictions`
- `leeuwtje_predictions`
- `winner_predictions`
- `top_scorer_predictions`

## UI Contract: Admin Label Editor

The admin label page must:

- Be visible only to admin users.
- Provide match-level inspection of result labels, quiz labels, scorer/goal events, and player stats.
- Show source state for each label: API-Football, static, manual override, or missing.
- Allow manual edits and clearing overrides where supported.
- Show save/error states per match or label group.
- Include copy or layout that makes clear admins are editing labels/results, not participant predictions.
- Avoid exposing controls that edit another participant's predictions.
