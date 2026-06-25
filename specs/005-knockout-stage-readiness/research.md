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

## Decision: Keep knockout score semantics unresolved

**Rationale**: The user wants to discuss whether knockout draws require an advancing-team prediction with a colleague. The feature must not accidentally introduce or hard-code that behavior.

**Alternatives considered**: Implementing score-only now is simplest but may be wrong. Implementing score-plus-advancing-team now is likely better for penalty scenarios but premature without product agreement.

## Decision: Add `Knockout` top-level navigation when relevant

**Rationale**: Once Knockout Stage planning is relevant, participants need a visible entry point. The app already uses concise English nav labels such as Matchday and Leaderboard, so `Knockout` fits.

**Alternatives considered**: Always showing the page would expose irrelevant content early. Hiding it behind My Predictions only would make the bracket hard to discover.
