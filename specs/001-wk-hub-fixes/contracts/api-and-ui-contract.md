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

## API/Data Response Contract: Actionable Notifications

Pool state notifications must support specific missing-action items and broadcast messages.

```json
{
  "notifications": [
    {
      "type": "quiz",
      "title": "Quizvraag open",
      "body": "Mexico - South Africa mist nog een quizantwoord.",
      "count": 1,
      "items": [
        {
          "match_id": "2026-06-11-mex-rsa",
          "kind": "quiz",
          "label": "Mexico - South Africa",
          "subtitle": "2026-06-11 - Group Stage - Group A",
          "target_view": "predictions",
          "target_match_id": "2026-06-11-mex-rsa",
          "target_kind": "quiz"
        }
      ]
    }
  ]
}
```

Rules:

- Missing-action notifications must identify the affected match and action type.
- Each actionable item must provide a target view and focus metadata.
- Locked or completed items must be omitted after refresh.
- The frontend may still render an aggregate title/count, but the user must be able to tell which quiz or prediction is missing before clicking.

## UI Contract: Notification Bell

The notification bell must:

- Show personal missing actions and admin broadcasts in the same popover.
- Render missing actions as clickable rows or buttons with match/team/date context.
- Navigate to the prediction entry/adjust surface focused on the selected `target_match_id` and `target_kind`.
- Keep a generic predictions fallback only for aggregate or future notification types without a specific target.
- Use active broadcast styling that is visually distinct from missing-action reminders.

## API Contract: Admin Broadcast Notifications

All broadcast management endpoints require an authenticated admin user. Non-admin users receive `403`; anonymous users receive `401`.

### List broadcasts

`GET /api/admin/notifications/broadcasts`

Returns active and recent broadcast notifications for the admin page.

```json
{
  "broadcasts": [
    {
      "id": 1,
      "title": "Deadline reminder",
      "body": "Fill in today's predictions before lock.",
      "is_active": true,
      "starts_at": "2026-06-10T10:00:00Z",
      "expires_at": "2026-06-11T10:00:00Z",
      "created_by_user_id": 1,
      "created_at": "2026-06-10T09:55:00Z"
    }
  ]
}
```

### Create broadcast

`POST /api/admin/notifications/broadcasts`

Allowed fields:

- `title`
- `body`
- `starts_at` optional
- `expires_at` optional

Creates an active broadcast notification shown in users' notification bells while active.

### Deactivate broadcast

`POST /api/admin/notifications/broadcasts/<broadcast_id>/deactivate`

Marks a broadcast inactive so it no longer appears in notification bells.

### Broadcast notification in pool state

Active broadcasts should be included in normal pool state notifications:

```json
{
  "type": "broadcast",
  "id": 1,
  "title": "Deadline reminder",
  "body": "Fill in today's predictions before lock.",
  "created_at": "2026-06-10T09:55:00Z"
}
```

## UI Contract: Admin Send Message Section

The admin page must:

- Offer a third section for sending messages, next to user management and scoring-label editing.
- Provide fields for broadcast title and message body.
- Show save, success, and error states.
- Show active/recent broadcasts with deactivate controls.
- Hide the section entirely from non-admin users.

## API/Data Response Contract: Leaderboard Identity

Leaderboard rows should include nickname and derived real-name metadata.

```json
{
  "user_id": 9,
  "name": "MVP",
  "email": "jane.doe@talpanetwork.com",
  "first_name": "Jane",
  "last_name": "Doe",
  "full_name": "Jane Doe",
  "profile_image_url": "https://..."
}
```

Rules:

- `name` remains the nickname and primary display label.
- `first_name`, `last_name`, and `full_name` are derived from the validated email.
- The frontend should display `full_name` smaller and lower contrast than `name`.
- Derived names must remain readable on mobile leaderboard rows.

## UI Contract: Leaderboard Avatar Preview

Leaderboard avatar behavior must:

- Keep avatar/name click behavior opening profiles in normal leaderboard context.
- Show a larger profile picture preview on hover.
- Show the same preview on keyboard focus.
- Use initials/fallback avatar if the profile image is missing.
- Avoid row-height changes and incoherent viewport overflow.

## API/Auth Contract: Talpa Email Validation

Account creation and any login/upsert path that can create a user must enforce:

```text
firstname.lastname@talpanetwork.com
```

Rules:

- Domain must be `talpanetwork.com`.
- Local part must provide first and last name segments separated by dot notation.
- Invalid examples include `jane@talpanetwork.com`, `jane.doe@gmail.com`, `jane+pool.doe@talpanetwork.com`, `jane.@talpanetwork.com`, and `@talpanetwork.com`.
- Error responses should be clear enough for the auth UI to tell users to use `firstname.lastname@talpanetwork.com`.
- Existing users with invalid historical emails need a migration or compatibility decision during implementation, but new account creation must reject invalid emails.

## API Contract: Quiz Metadata Editing

Quiz label update contracts must support question and option overrides in addition to correct labels.

`PATCH /api/admin/labels/<match_id>/quiz`

Allowed fields:

- `question`
- `choices`
- `correct_answer`
- `correct_answers`
- `viewership_answer`
- `clear_override`

Rules:

- Question overrides affect the prediction UI.
- Choice overrides affect prediction UI option lists and scoring validation.
- Correct-answer overrides affect scoring.
- Participant `quiz_predictions` rows must not be changed by this endpoint.
- Source/audit metadata must record the admin and timestamp.

## UI Contract: Admin Quiz/Label Editor Completion

The admin label editor must:

- Let admins scroll through long match lists and long option/label lists.
- Let admins select existing labels/options rather than typing everything blindly.
- Let admins edit quiz question text.
- Let admins edit answer options.
- Let admins edit correct answers and viewership answers.
- Keep result labels, quiz labels, goal/scorer labels, and player-stat labels visually distinct.
- Avoid nested scrolling traps on common desktop and mobile widths.

## API/Data Response Contract: Wall of Shame

Pool state or a dedicated endpoint must expose active users with currently open missing actions.

```json
{
  "wall_of_shame": [
    {
      "user_id": 9,
      "name": "MVP",
      "full_name": "Jane Doe",
      "profile_image_url": "https://...",
      "missing_count": 2,
      "missing_items": [
        {
          "match_id": "2026-06-11-mex-rsa",
          "kind": "prediction",
          "label": "Mexico - South Africa",
          "deadline": "2026-06-11T18:00:00Z"
        },
        {
          "match_id": "2026-06-11-mex-rsa",
          "kind": "quiz",
          "label": "Mexico - South Africa",
          "deadline": "2026-06-11T18:00:00Z"
        }
      ]
    }
  ]
}
```

Rules:

- Archived users are excluded.
- Users with zero currently open missing actions are excluded.
- Locked matches are excluded.
- The payload identifies missing action categories but must not expose prediction contents.

## UI Contract: Wall of Shame

The wall of shame UI must:

- Be visible from a leaderboard-adjacent or otherwise easy-to-find app surface.
- Show nickname as primary and derived real name as secondary when available.
- Show missing counts and concise missing match/action context.
- Stay readable on mobile when a user has many missing items.
- Avoid implying users can still fix locked historical misses.
