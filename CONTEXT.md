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

**Quiz Setup**:
The admin-owned preparation of quiz questions before they are available to participants. Knockout Stage quiz setup covers one quiz question for each Knockout Stage match; an unset quiz question does not block score predictions for that match.
_Avoid_: Code update, deployment

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
A position in the Knockout Stage bracket, such as a group position or prior-match winner. A Bracket Slot can be unresolved or resolved from trusted tournament facts.
_Avoid_: Unknown team, TBD team

**Resolved Bracket Slot**:
A Bracket Slot whose team can be determined from trusted tournament facts, such as a final group standing or a completed Knockout Stage match.
_Avoid_: Populated placeholder, known placeholder

**Composite Third-Place Slot**:
A Bracket Slot that names multiple possible third-place group sources, where the final team depends on the tournament's third-place allocation rules.
_Avoid_: Third-place placeholder, wildcard slot

**Final Group**:
A World Cup group whose Group Stage matches all have trusted final results. Final group standings can resolve group-position Bracket Slots such as `1A`, `2A`, and `3A`.
_Avoid_: Completed table, locked group

**Knockout Match Tile**:
A selectable visual representation of one Knockout Stage match in the bracket. A tile can represent either known teams or Bracket Slots and opens match details when selected.
_Avoid_: Fixture card, game box

**Knockout Page**:
The top-level page for viewing and completing Knockout Stage predictions. It becomes prominent navigation when Knockout Stage planning is relevant.
_Avoid_: Matchday page, schedule page

**Missing Action**:
A prediction or quiz answer that a participant can still complete before its lock time. Urgent missing actions are limited to matches on the current or next matchday, while Knockout Stage planning may show all known open missing actions.
_Avoid_: Incomplete data, notification

**Prediction Result**:
The match score and outcome that participant score predictions are judged against. Group Stage Prediction Result means the regular-time result; Knockout Stage Prediction Result means the score after extra time when played, while penalties never add goals to the Prediction Result.
_Avoid_: Final score, penalty score

**Prediction Outcome**:
The outcome component of a score prediction. In the Group Stage this is home win, draw, or away win; in the Knockout Stage this is the Advancing Team.
_Avoid_: Winner, match result

**Leeuwtje Budget**:
The number of Leeuwtjes a participant may assign within a tournament stage. The Group Stage budget is separate from the Knockout Stage budget; unused Group Stage Leeuwtjes expire when all Group Stage matches have trusted final results, and every participant then receives a fresh Knockout Stage budget.
_Avoid_: Carried-over Leeuwtjes, bonus pool

**Leeuwtje Points**:
The extra points earned because a participant assigned a Leeuwtje to a scored match prediction. Leeuwtje Points are cumulative across tournament stages, even though Leeuwtje Budget is stage-specific.
_Avoid_: Remaining Leeuwtjes, selected Leeuwtjes

**Match Points**:
The leaderboard points from match-score predictions and the tournament winner pick, excluding quiz points, scorer points, and Leeuwtje Points. Group-position points are not part of Match Points.
_Avoid_: Group-position points, Leeuwtje Points

**Consumed Leeuwtje**:
A Leeuwtje assigned to a match that already has the trusted result needed for scoring. Assigned Leeuwtjes on future or unscored matches are not consumed yet.
_Avoid_: Available Leeuwtje, selected Leeuwtje

**Remaining Leeuwtje Count**:
The active-stage Leeuwtje Budget minus Consumed Leeuwtjes in that stage. Assigned Leeuwtjes on future or unscored matches do not reduce the Remaining Leeuwtje Count until those matches have trusted results.
_Avoid_: Total Leeuwtjes, Leeuwtje Points

**Advancing Team**:
The team that progresses from a Knockout Stage match after the tie is fully decided, including extra time or penalties when needed.
_Avoid_: Winner, score winner

**Match Decision Method**:
How a completed Knockout Stage match was decided: in regular time, after extra time, or by penalties.
_Avoid_: Status, result type

**Day Score**:
The points earned by each active participant from scoring facts on a single matchday. A day score list includes every active participant, including participants who earned zero points.
_Avoid_: Top players, daily leaderboard

**Rank Movement**:
The change in a participant's standing caused by one matchday, comparing their rank before that matchday with their rank after that matchday.
_Avoid_: Current leaderboard delta, overall movement
