# WK Hub

WK Hub is a World Cup prediction pool where participant predictions are scored against trusted match facts and quiz labels.

## Language

**Scoring Fact**:
A trusted football fact used to compute participant points, such as a match result, goal event, clean sheet, player statistic, or quiz label.
_Avoid_: Raw provider data, LLM answer

**Quiz Label**:
The accepted answer for a match quiz question used during scoring. A quiz label can come from static quiz data, a deterministic resolver, a GenAI Job, or a manual admin override.
_Avoid_: Quiz prediction, participant answer

**Quiz Question**:
A match-specific question that participants answer before a match locks. Knockout Stage matches each have one quiz question; published quiz questions should stay stable, with corrections reserved for mistakes.
_Avoid_: Prompt

**Quiz Correction**:
A change to a published quiz question or answer options that fixes a mistake. Existing participant answers remain valid when they still match the corrected options; otherwise the quiz becomes a missing action again until the normal lock time.
_Avoid_: Quiz rewrite, republish

**Manual Override**:
An admin-authored scoring fact that takes precedence over provider-backed or automatically derived facts.
_Avoid_: Manual prediction, admin correction

**GenAI Service**:
The app layer that calls a language model for bounded support work, such as interpreting match facts for a quiz label or matching a scorer name to an existing player. It may only publish a scoring fact when the result passes deterministic validation; otherwise it creates admin work.
_Avoid_: AI scorer, free-form quiz parser

**GenAI Job**:
A single bounded unit of GenAI Service work with known input data, expected output shape, validation rules, and failure handling.
_Avoid_: Agent task, workflow

**Admin Sync Issue**:
An admin-only notification that a scoring fact or supporting sync step could not be resolved automatically.
_Avoid_: User notification, provider error

**Matchday**:
A tournament session shown from the Dutch viewer perspective, where early-morning kickoffs can belong to the previous football day rather than the Amsterdam calendar date.
_Avoid_: Calendar day, fixture date

**Knockout Stage**:
The elimination part of the tournament after the group stage, from the Round of 32 through the Final.
_Avoid_: Knockout phase, bracket phase

**Bracket Slot**:
A placeholder for a Knockout Stage team that is not known yet, such as a group position or prior match winner.
_Avoid_: Unknown team, TBD team

**Missing Action**:
A prediction or quiz answer that a participant can still complete before its lock time. Urgent missing actions are limited to matches on the current or next matchday, while Knockout Stage planning may show all known open missing actions.
_Avoid_: Incomplete data, notification

**Day Score**:
The points earned by each active participant from scoring facts on a single matchday. A day score list includes every active participant, including participants who earned zero points.
_Avoid_: Top players, daily leaderboard

**Rank Movement**:
The change in a participant's standing caused by one matchday, comparing their rank before that matchday with their rank after that matchday.
_Avoid_: Current leaderboard delta, overall movement
