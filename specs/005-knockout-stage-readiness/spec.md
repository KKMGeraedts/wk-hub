# Feature Specification: Knockout Stage Readiness

**Feature Branch**: `005-knockout-stage-readiness`

**Created**: 2026-06-24

**Status**: Draft

**Input**: User description: "The knockout phase is coming up. Include a new page where people can better see what is happening and the predictions they still need to make. Define new quiz questions and make sure the app is ready for this next phase."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Navigate the Knockout Stage bracket (Priority: P1)

As a participant, I want a dedicated Knockout Page that visually shows the Knockout Stage bracket, so that I can understand what is happening after the group stage without scanning a flat schedule.

**Why this priority**: The Knockout Stage changes the shape of the tournament. Participants need a clear first screen that shows bracket progression, known teams, Bracket Slots, dates, and which matches are actionable.

**Independent Test**: Can be tested by opening the Knockout Page with no knockout teams known, then with some knockout teams known, and verifying the visual bracket remains understandable in both states.

**Acceptance Scenarios**:

1. **Given** no Knockout Stage teams are known yet, **When** a participant opens the Knockout Page, **Then** they see a visually bracket-shaped overview using Bracket Slots such as group positions and prior-match winners.
2. **Given** some Knockout Stage teams are known, **When** a participant opens the Knockout Page, **Then** known teams appear in their Knockout Match Tiles while unresolved teams remain visible as Bracket Slots.
3. **Given** a participant selects a Knockout Match Tile, **When** that match has unresolved Bracket Slots, **Then** the detail panel shows match path, date, venue, and status without prediction controls.
4. **Given** a participant selects a Knockout Match Tile with known teams, **When** the match is still open, **Then** the detail panel shows the actionable prediction state for that match.

---

### User Story 2 - Complete my open knockout predictions (Priority: P1)

As a participant, I want the Knockout Page to show the predictions and quiz answers I still need to make, so that I can complete my own open knockout work before lock times.

**Why this priority**: The main operational risk is that participants miss newly available knockout predictions because the existing prediction surfaces are group-stage oriented.

**Independent Test**: Can be tested by leaving an open Knockout Stage score prediction or quiz answer empty, opening the Knockout Page, and completing the item from the selected match detail.

**Acceptance Scenarios**:

1. **Given** a Knockout Stage match has both teams known and has not locked, **When** a participant has no score prediction for it, **Then** the match is presented as a Missing Action on the Knockout Page.
2. **Given** a Knockout Stage match has a published Quiz Question and has not locked, **When** a participant has no valid quiz answer for it, **Then** the match is presented as a Missing Action on the Knockout Page.
3. **Given** a Knockout Stage match has both teams known but no Quiz Question set yet, **When** a participant opens the match detail, **Then** score prediction remains available and the quiz area says the quiz question is not set yet.
4. **Given** a participant saves a score prediction or quiz answer from the Knockout Page, **When** the save succeeds, **Then** the Missing Action state updates without requiring a page reload.
5. **Given** a match reaches its lock time, **When** a participant views the Knockout Page, **Then** prediction and quiz controls for that match are no longer editable.

---

### User Story 3 - Set knockout quiz questions (Priority: P1)

As an admin, I want to prepare one Quiz Question for every Knockout Stage match in the app, so that participants can answer knockout quizzes without requiring a code deployment for each question.

**Why this priority**: Knockout quiz coverage currently stops at the group stage. Admin-owned Quiz Setup is needed before participants can answer quiz questions for knockout matches.

**Independent Test**: Can be tested by logging in as an admin, setting a quiz question for a knockout match that previously had none, and confirming participants can answer it once available.

**Acceptance Scenarios**:

1. **Given** an admin opens Quiz Setup, **When** a Knockout Stage match has no Quiz Question, **Then** the admin can set the question, answer options, and scoring information required for participant answers.
2. **Given** a Quiz Question has been set for a Knockout Stage match, **When** a participant opens that match on the Knockout Page, **Then** the quiz question and answer controls are available before lock time.
3. **Given** a published Quiz Question contains a mistake, **When** an admin corrects it before lock time, **Then** existing participant answers remain valid if they still match corrected options and otherwise become Missing Actions again.
4. **Given** a correction is needed after lock time, **When** an admin updates quiz data, **Then** scoring facts and labels can be corrected without automatically reopening participant answers.

---

### User Story 4 - Route users to knockout work at the right time (Priority: P2)

As a participant, I want navigation and the existing My Predictions entry point to take me to the right prediction surface during the Knockout Stage, so that I do not end up in a group-stage workflow once the tournament has moved on.

**Why this priority**: This improves discoverability after the core bracket and prediction flow exists.

**Independent Test**: Can be tested by simulating the period where Knockout Stage planning is relevant and verifying navigation exposes the Knockout Page and My Predictions leads to knockout work.

**Acceptance Scenarios**:

1. **Given** Knockout Stage planning is relevant, **When** a participant views top-level navigation, **Then** a `Knockout` navigation item is visible.
2. **Given** a participant clicks My Predictions during the Knockout Stage, **When** there are urgent missing knockout actions, **Then** the app opens the Knockout Page focused on the first urgent open match.
3. **Given** a participant clicks My Predictions during the Knockout Stage with no urgent missing knockout action, **When** the Knockout Page is relevant, **Then** the app opens the bracket overview.

---

### Edge Cases

- A Knockout Stage match has a date and Bracket Slots but no known teams yet.
- A Knockout Stage match has both teams known, but no Quiz Question has been set.
- A Quiz Correction changes answer options before lock time after some participants already answered.
- A Quiz Correction is needed after lock time.
- A participant opens a match detail shortly before lock time and the match locks before they save.
- A participant has saved a score prediction but not a quiz answer, or vice versa.
- A participant has no remaining Missing Actions but still wants to inspect the bracket.
- Mobile users need to inspect a 32-match bracket without text overlap or unusable tiny controls.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a dedicated Knockout Page for the Knockout Stage.
- **FR-002**: The Knockout Page MUST present the Knockout Stage as a visually bracket-shaped experience rather than only as a flat list.
- **FR-003**: The Knockout Page MUST show all Knockout Stage matches from Round of 32 through Final, including matches with unresolved Bracket Slots.
- **FR-004**: The system MUST display known teams where available and Bracket Slots where teams are not yet known.
- **FR-005**: The Knockout Page MUST make each Knockout Match Tile selectable.
- **FR-006**: Selecting a Knockout Match Tile MUST open match details without requiring navigation away from the Knockout Page.
- **FR-007**: Match details MUST show match timing, round, venue, known teams or Bracket Slots, lock status, and the participant's current prediction state.
- **FR-008**: The Knockout Page MUST show personal Missing Actions for all known, open Knockout Stage matches, not only today and tomorrow.
- **FR-009**: The existing urgent notification and wall-of-shame behavior MUST remain limited to the current and next matchday.
- **FR-010**: The Knockout Page MUST NOT include a group accountability or wall-of-shame section.
- **FR-011**: Score predictions MUST become available for a Knockout Stage match when both teams are known and the match has not locked.
- **FR-012**: A missing Quiz Question MUST NOT block score prediction for an otherwise open Knockout Stage match.
- **FR-013**: A Knockout Stage quiz answer MUST become available only when that match has a Quiz Question and has not locked.
- **FR-014**: The system MUST support Quiz Setup for one Quiz Question per Knockout Stage match.
- **FR-015**: Admins MUST be able to set a Quiz Question for a Knockout Stage match that currently has none.
- **FR-016**: Admins MUST be able to correct a published Quiz Question or answer options when a mistake is found.
- **FR-017**: If a pre-lock Quiz Correction invalidates a participant's existing answer, the quiz MUST become a Missing Action again for that participant until the normal lock time.
- **FR-018**: If a Quiz Correction happens after lock time, the system MUST NOT automatically reopen participant answers.
- **FR-019**: The `Knockout` top-level navigation item MUST become visible when Knockout Stage planning is relevant.
- **FR-020**: The existing My Predictions entry point MUST route participants to Knockout Stage work when Knockout Stage planning is relevant and group-stage prediction entry is no longer the main task.
- **FR-021**: Knockout Stage score predictions MUST be judged against the Knockout Stage Prediction Result, meaning the score after extra time when extra time is played, while penalty shootout goals MUST NOT be added to the predicted or scored goals.
- **FR-022**: Knockout Stage score predictions MUST use Advancing Team as the Prediction Outcome, including when the participant predicts a non-draw score and when the completed tie is decided after extra time or penalties.
- **FR-023**: Admins MUST be able to manually correct the Advancing Team for a completed Knockout Stage match without changing participant score prediction semantics.
- **FR-024**: The Knockout Page MUST work on mobile and desktop without controls or text overlapping.
- **FR-025**: A Knockout Stage match MUST become actionable when both Bracket Slots resolve to teams and the match has not locked; an API provider fixture link MUST NOT be required for participants to make predictions.
- **FR-026**: If a correction changes a resolved Bracket Slot after participants have already predicted that Knockout Stage match, the system MUST NOT automatically delete or reopen those predictions; admins handle any exceptional cleanup manually.
- **FR-027**: Prior-match Bracket Slots such as `W73` and `L73` MUST resolve only from an Advancing Team fact, not by inferring advancement from the Prediction Result.
- **FR-028**: Composite Third-Place Slots MUST remain unresolved until the official allocation rule is encoded or a trusted provider fixture identifies both teams.
- **FR-029**: Once the relevant groups are final, an unresolved Composite Third-Place Slot MUST surface as an admin-only Admin Sync Issue while remaining a normal Bracket Slot placeholder for participants.
- **FR-030**: Group-position Bracket Slots MUST use the same standings ordering logic as group-position quiz scoring, so bracket resolution and scoring facts do not disagree.
- **FR-031**: If final group standings cannot confidently resolve a group-position Bracket Slot, the affected Bracket Slot MUST remain unresolved and surface as an admin-only Admin Sync Issue.
- **FR-032**: The system MUST NOT introduce a separate manual Bracket Slot override; unresolved group-position slots must be resolved by correcting trusted match facts or improving the shared standings logic.
- **FR-033**: If a participant enters a draw as the Knockout Stage Prediction Result, the system MUST require an Advancing Team choice before the prediction is complete while the match is open.
- **FR-034**: If a participant enters a non-draw Knockout Stage Prediction Result, the system MUST infer the participant's Advancing Team from the predicted score and MUST NOT require a separate Advancing Team choice.
- **FR-035**: A locked draw prediction without a participant Advancing Team MUST remain saved but MUST NOT receive outcome or exact-score points; home-goal and away-goal points can still be awarded.
- **FR-036**: A completed penalty-decided Knockout Stage match MUST be scoreable from trusted provider facts when the provider supplies the after-extra-time score, penalty shootout score evidence, and Advancing Team.
- **FR-037**: The UI MUST label Knockout Stage score inputs as score after maximum 120 minutes.
- **FR-038**: The UI MUST display penalty shootout scores as result context for completed penalty-decided Knockout Stage matches, not as prediction input fields.
- **FR-039**: The leaderboard MUST expose total points as the sum of Match Points, Quiz Points, Scorer Points, and Leeuwtje Points.
- **FR-040**: The leaderboard MUST remove the Predictions fraction column and MUST keep Exact and Outcome visible as statistics.
- **FR-041**: Leaderboard numeric point/stat columns MUST be sortable while preserving the `#` column as overall rank and using overall leaderboard order as the tie-breaker.
- **FR-042**: The leaderboard MUST show Leeuwtje Points as a point column; hovering that column MUST show the public Remaining Leeuwtje Count fraction for the active tournament stage.
- **FR-043**: Group-position points MUST not contribute to leaderboard totals or Match Points.

### Key Entities *(include if feature involves data)*

- **Knockout Stage**: The elimination part of the tournament after the group stage, from Round of 32 through Final.
- **Bracket Slot**: A position in the Knockout Stage bracket, such as a group position or prior-match winner, which can be unresolved or resolved from trusted tournament facts.
- **Knockout Match Tile**: A selectable visual representation of one Knockout Stage match in the bracket.
- **Missing Action**: A prediction or quiz answer that a participant can still complete before its lock time.
- **Quiz Question**: A match-specific question that participants answer before a match locks.
- **Quiz Setup**: Admin-owned preparation of Quiz Questions before they are available to participants.
- **Quiz Correction**: A change to a published Quiz Question or answer options that fixes a mistake.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A participant can identify every Knockout Stage match, including unresolved Bracket Slots, from the Knockout Page without using the schedule page.
- **SC-002**: A participant can complete an open Knockout Stage score prediction and quiz answer from the Knockout Page in under 60 seconds once the relevant match is selected.
- **SC-003**: The Knockout Page distinguishes open, locked, completed, and not-yet-actionable matches for all 32 Knockout Stage matches.
- **SC-004**: Admins can set quiz questions for all 32 Knockout Stage matches without changing source code.
- **SC-005**: Existing today/tomorrow urgent reminders continue to behave unchanged while the Knockout Page shows broader knockout planning work.
- **SC-006**: The bracket remains readable and usable at common mobile and desktop viewport sizes.

## Assumptions

- The app's existing lock-time rule of one hour before kickoff applies to Knockout Stage score predictions and quiz answers.
- Knockout Stage score predictions use the same point structure as existing match predictions, but the Knockout Stage Prediction Outcome is the Advancing Team.
- The Knockout Page is participant-facing and authenticated like the existing main app surfaces.
- Existing admin authorization rules apply to Quiz Setup and Quiz Correction.
- Existing scoring labels and manual override concepts remain valid for knockout quiz scoring.
