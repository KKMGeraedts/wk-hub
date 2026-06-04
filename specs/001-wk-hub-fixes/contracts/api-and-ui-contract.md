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
- Continuing after successful required prediction completion routes to the leaderboard.

## UI Contract: Normal Leaderboard

In normal leaderboard context:

- Profile picture opens the participant profile.
- Player name opens the participant profile.
- Top scorer and striker names are not displayed in leaderboard columns.

## UI Contract: Profile Page

Profile page must:

- Omit the profile-specific `Back to leaderboard` control.
- Keep long participant names, player names, and labels readable.
- Show tournament-pick privacy messaging before reveal when viewing another participant.
- Show tournament picks after reveal when viewing another participant.
- Always show own tournament picks to the owner subject to editability controls.
