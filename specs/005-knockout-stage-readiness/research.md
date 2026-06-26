# Research: Knockout Stage Readiness

## Decision: Build a dedicated Knockout Page

**Rationale**: Matchday answers "what is happening today"; the Knockout Page answers "where are we in the bracket and what can I still predict?" These are different user jobs, and the existing prediction UI is group-stage oriented.

**Alternatives considered**: Expanding Matchday would reduce navigation but would blur daily session tracking with bracket planning. Extending Adjust Predictions alone would not give participants a clear bracket overview.

## Decision: Render a visual bracket with selectable tiles

**Rationale**: The user explicitly wants the page to look like the Knockout Stage rather than a grouped list. Selectable Knockout Match Tiles keep the bracket visually clean while moving score, quiz, Leeuwtje, and lock controls into a detail panel.

**Alternatives considered**: A flat round-grouped list is simpler and more compact, but it does not meet the desired visual experience. Putting controls inside every tile would make the bracket crowded and fragile on mobile.

## Decision: Show Bracket Slots for unresolved teams

**Rationale**: Existing tournament data already contains placeholders such as `1A`, `3C/E/F/H/I`, `W73`, and `L101`. Showing these lets the bracket communicate future paths before teams are known.

**Alternatives considered**: Hiding unknown matches would make the bracket feel incomplete. Showing generic "TBD" labels would discard useful path information already present in the data.

## Decision: Knockout Page shows personal Missing Actions only

**Rationale**: The user reversed the earlier group-accountability idea. The Knockout Page should help each participant understand and complete their own open work, not show a wall of shame.

**Alternatives considered**: A knockout-scoped accountability list could support group pressure, but it would add social noise and duplicate an existing wall-of-shame concept the user no longer wants here.

## Decision: Keep urgent reminders scoped to today/tomorrow

**Rationale**: Existing notifications and wall of shame intentionally focus on current and next matchday. The Knockout Page can show all known open knockout work as planning context without increasing notification noise.

**Alternatives considered**: Expanding reminders to all open knockout matches would improve completeness but risks noisy alerts for matches several days away.

## Decision: Admins own Knockout Stage Quiz Setup in-app

**Rationale**: `backend/quiz-2026.json` currently covers `m1` through `m72`; Knockout Stage matches `m73` through `m104` have no quiz entries. Admin setup avoids code deployments for deciding or correcting quiz questions.

**Alternatives considered**: Static file updates are simple but operationally slow during the tournament. Auto-generating quiz questions is out of scope and conflicts with the user's desire to determine them with a colleague.

## Decision: Missing quiz setup does not block score prediction

**Rationale**: Score predictions can be made as soon as both teams are known and the match is open. Quiz questions may be set later, and the page should show a clear "not set yet" state rather than blocking the whole match.

**Alternatives considered**: Requiring quiz setup before score prediction would simplify tile completeness rules but would unnecessarily prevent valid score predictions.

## Decision: Knockout Prediction Result includes extra time but not penalties

**Rationale**: Knockout Stage participants predict the score after maximum 120 minutes. Penalty shootout goals never become score goals, but the participant still predicts the Advancing Team whenever their predicted score is a draw. Knockout outcome points are awarded for the correct Advancing Team, while home-goal, away-goal, and exact-score points keep the existing match-prediction structure.

**Alternatives considered**: Keeping score predictions at 90 minutes would preserve the earlier implementation assumption but does not match how participants reason about knockout ties. Including penalty shootout goals in the score would make football score totals misleading. Adding a separate fixed-point Advancing Team bonus was rejected because the existing point structure should remain intact.

## Decision: Trust API-Football Advancing Team and penalty evidence

**Rationale**: API-Football exposes penalty-decided matches with `status.short = PEN`, `goals` as the after-extra-time score, `score.penalty` as shootout evidence, and `teams.*.winner` as the Advancing Team. This is sufficient to score knockout outcome and exact predictions without admin handwork when the provider payload is complete.

**Alternatives considered**: Requiring manual Advancing Team confirmation for every penalty-decided tie would be safer but unnecessarily operationally heavy when trusted provider fields are present. Inferring the Advancing Team from scores is invalid for drawn after-extra-time results.

## Decision: Resolve bracket slots in loaded tournament data

**Rationale**: Once trusted tournament facts identify a Bracket Slot's team, the app should treat that Knockout Stage side like a known team for prediction availability, Missing Actions, lock behavior, and display. Resolving slots in loaded in-memory tournament data keeps static tournament JSON and persisted match rows as source data while allowing existing match logic to work with `home_team_id` and `away_team_id`.

**Alternatives considered**: Persisting resolved teams to static JSON or match rows would make the resolution durable but create extra correction work if provider facts change. Keeping resolved teams only in a separate Knockout Page projection would avoid mutating loaded data, but duplicate prediction and Missing Action logic would then need to understand both raw and projected teams.

## Decision: Add `Knockout` top-level navigation when relevant

**Rationale**: Once Knockout Stage planning is relevant, participants need a visible entry point. The app already uses concise English nav labels such as Matchday and Leaderboard, so `Knockout` fits.

**Alternatives considered**: Always showing the page would expose irrelevant content early. Hiding it behind My Predictions only would make the bracket hard to discover.
