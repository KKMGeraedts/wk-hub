# Feature Specification: Matchday Recap Updates

**Feature Branch**: `004-matchday-recap-updates`

**Created**: 2026-06-24

**Status**: Draft

**Input**: User description: "Update schedule ordering so today's games appear first, followed by historic games newest-to-oldest and then future games. Remove the orange missing-prediction highlight and legend from the leaderboard while keeping prediction completeness visible. Show a participant's own prediction, result, and clickable point breakdown on matchday overview cards and the locked match detail page. Improve slow loading of locked match prediction detail. Make daily recap day score and biggest winners/losers use the same matchday baseline, and add a clickable full day-score modal with every active player and per-match point breakdowns."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read the schedule in matchday order (Priority: P1)

As a participant, I want the schedule to start with the current matchday, then let me review past matchdays before future matchdays, so that the schedule matches how I follow the tournament during the day.

**Why this priority**: The schedule is a primary navigation surface. Showing older historic games before today's games makes it harder to find the matches participants care about now.

**Independent Test**: Can be tested by loading the schedule on a day with today, past, and future matches and confirming the visible order is current matchday, past matchdays newest-to-oldest, and future matchdays oldest-to-newest.

**Acceptance Scenarios**:

1. **Given** the tournament has matches on the current matchday, previous matchdays, and future matchdays, **When** a participant opens the schedule, **Then** the current matchday's matches appear before all other matches.
2. **Given** the participant scrolls below the current matchday, **When** past matches are shown, **Then** past matchdays appear from most recent to oldest.
3. **Given** all past matchdays have been shown, **When** future matches are shown, **Then** future matchdays appear from nearest to latest.
4. **Given** early-morning kickoffs belong to the previous football day by app rules, **When** the schedule decides what counts as today's games, **Then** it uses the app's matchday definition rather than the plain calendar date.

---

### User Story 2 - See leaderboard completeness without orange warning colors (Priority: P2)

As a participant, I want the leaderboard to keep prediction completeness visible without orange row highlighting, so that standings do not imply that missing predictions are a scoring warning or status color.

**Why this priority**: The orange highlight is visually confusing in a points-focused table. The same information can remain available through the prediction-completeness column.

**Independent Test**: Can be tested by viewing a leaderboard with participants who have complete and incomplete predictions and confirming rows are not tinted or explained by a missing-prediction legend while the completeness numbers remain present.

**Acceptance Scenarios**:

1. **Given** a participant has incomplete predictions, **When** the leaderboard displays their row, **Then** the row is not visually highlighted with the previous orange missing-prediction treatment.
2. **Given** the leaderboard is displayed, **When** the table header and body are visible, **Then** the prediction-completeness column remains available.
3. **Given** the leaderboard is displayed, **When** the surrounding legend area is shown, **Then** there is no missing-prediction color legend.

---

### User Story 3 - Review my matchday prediction and points at a glance (Priority: P1)

As a participant, I want each completed matchday card to show the result, my prediction, and my point breakdown, so that the matchday tab gives the same scoring clarity as the schedule.

**Why this priority**: Participants use the matchday tab frequently. A completed match card that shows only the result leaves users unable to quickly compare what happened with what they predicted.

**Independent Test**: Can be tested by opening the matchday tab for a completed match where the viewer has a prediction and points, then confirming the result, personal prediction, and expandable point breakdown are visible on the card.

**Acceptance Scenarios**:

1. **Given** a completed match where the viewer made a score prediction, **When** the matchday overview card is displayed, **Then** the card shows the match result and the viewer's prediction near each other.
2. **Given** a completed match where the viewer earned points, **When** the matchday overview card is displayed, **Then** the card shows a clickable points summary that opens the point breakdown.
3. **Given** a completed match where the viewer did not make a prediction, **When** the matchday overview card is displayed, **Then** the card shows `Mijn voorspelling: -` and no personal points chip.
4. **Given** a match is not completed, **When** the matchday overview card is displayed, **Then** it does not show a completed-result scoring summary.
5. **Given** the viewer opens a locked match detail page, **When** the match header is displayed, **Then** the viewer can see their own result, prediction, and points summary without searching the player prediction list.

---

### User Story 4 - Open locked match prediction detail quickly (Priority: P1)

As a participant, I want the locked match detail page to load all player predictions quickly, so that opening a match from the matchday tab feels responsive.

**Why this priority**: The matchday overview loads quickly, but clicking into a match currently feels slow. The detail view is important for comparing predictions after lock.

**Independent Test**: Can be tested by opening a locked match with many submitted predictions and confirming the detail page loads within the target response time while preserving all displayed prediction and point data.

**Acceptance Scenarios**:

1. **Given** a locked match has many participant predictions, **When** a participant opens the match detail page, **Then** the prediction list, quiz answers, Leeuwtjes, and point summaries load within the expected response time.
2. **Given** the match detail page loads, **When** prediction rows are shown, **Then** each participant's score prediction, quiz answer, Leeuwtje marker, and point breakdown remain accurate.
3. **Given** a match is not locked, **When** a participant attempts to open the match detail page, **Then** the detail remains unavailable.

---

### User Story 5 - Trust the daily recap winners and losers (Priority: P1)

As a participant, I want the daily recap day score and biggest winners/losers to use the same matchday baseline, so that a high day scorer is not listed as a loser due to unrelated leaderboard movement.

**Why this priority**: The recap is used to understand what changed today. If the boards use different calculations, participants cannot trust the story it tells.

**Independent Test**: Can be tested by creating a matchday where a participant earns a high day score and verifying winners/losers are calculated from rank movement before versus after that same matchday.

**Acceptance Scenarios**:

1. **Given** the daily recap is available for a matchday, **When** day scores are calculated, **Then** they include points earned from scoring facts on that same matchday.
2. **Given** biggest winners and losers are calculated, **When** rank movement is determined, **Then** it compares each participant's standing before that matchday with their standing after that matchday.
3. **Given** a participant earns one of the highest day scores, **When** biggest losers are displayed, **Then** that participant only appears as a loser if their standing still dropped because of that same matchday's points.
4. **Given** multiple participants have equal rank movement, **When** winners or losers are displayed, **Then** ties are handled consistently and predictably.

---

### User Story 6 - Inspect the full day score (Priority: P2)

As a participant, I want to click the daily recap day score and see every active participant's score with a breakdown, so that I can understand how the matchday points were earned.

**Why this priority**: The recap top list is useful but incomplete. Participants want to inspect the full group and understand the point components behind the rankings.

**Independent Test**: Can be tested by clicking the day-score action in the recap and confirming a modal lists every active participant, including zero-point participants, with one expandable per-player breakdown.

**Acceptance Scenarios**:

1. **Given** a daily recap is available, **When** the participant clicks the day-score action, **Then** a full day-score modal opens.
2. **Given** the full day-score modal is open, **When** the list is displayed, **Then** every active participant appears, including participants who earned zero points.
3. **Given** the list contains participants with positive and zero points, **When** it is sorted, **Then** positive scores appear highest by points and zero-point participants are ordered predictably.
4. **Given** a participant row is expanded, **When** the breakdown is displayed, **Then** it shows per-match point components for that matchday.
5. **Given** one participant row is already expanded, **When** another row is expanded, **Then** the previously expanded row closes.

### Edge Cases

- The current matchday has no scheduled matches but past and future matchdays exist.
- The current matchday contains early-morning games that belong to the previous football day by app rules.
- A completed match has a result but the viewer did not submit a prediction.
- A completed match has a personal prediction but zero earned points.
- A locked match detail has predictions from archived or removed users.
- A match has quiz data for some participants but not others.
- A participant has a Leeuwtje on a match but earned no score points from the score prediction.
- Multiple participants tie on day score or rank movement.
- Every active participant earns zero points on the recap matchday.
- The recap matchday includes multiple matches and a participant has points in more than one match.
- The tournament has future matches but no historic matches yet.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The schedule MUST show current matchday games before past and future games.
- **FR-002**: The schedule MUST order past matchdays from newest to oldest after the current matchday.
- **FR-003**: The schedule MUST order future matchdays from nearest to latest after all past matchdays.
- **FR-004**: The schedule MUST use the app's Matchday definition when identifying current, past, and future matchdays.
- **FR-005**: The leaderboard MUST NOT use the previous missing-prediction orange row highlight.
- **FR-006**: The leaderboard MUST NOT show the missing-prediction color legend.
- **FR-007**: The leaderboard MUST keep prediction-completeness information visible.
- **FR-008**: Completed matchday overview cards MUST show the match result.
- **FR-009**: Completed matchday overview cards MUST show the viewer's score prediction when one exists.
- **FR-010**: Completed matchday overview cards MUST show `Mijn voorspelling: -` when the viewer has no score prediction.
- **FR-011**: Completed matchday overview cards MUST show a clickable personal points summary when personal match points exist.
- **FR-012**: Personal points summaries on matchday surfaces MUST expose the same point categories used elsewhere for match score, Leeuwtje, quiz, and match-attributable striker points.
- **FR-013**: Locked match detail pages MUST show the viewer's own result, prediction, and personal points summary near the match header.
- **FR-014**: Locked match detail pages MUST continue to show all eligible participant predictions with score, quiz, Leeuwtje, and point information.
- **FR-015**: Match detail MUST remain unavailable before predictions for that match are locked.
- **FR-016**: Opening a locked match detail MUST meet the feature's response-time success criterion for typical pool size.
- **FR-017**: Daily recap day score MUST be calculated from points earned on the recap matchday.
- **FR-018**: Daily recap biggest winners and losers MUST be calculated from rank movement caused by the same recap matchday.
- **FR-019**: Rank movement MUST compare standings before the recap matchday with standings after the recap matchday.
- **FR-020**: Daily recap MUST provide a clear day-score action that opens the full day-score detail.
- **FR-021**: Full day-score detail MUST include every active participant, including participants with zero points.
- **FR-022**: Full day-score detail MUST show per-match point breakdowns for the recap matchday.
- **FR-023**: Full day-score detail MUST allow only one participant's breakdown to be expanded at a time.
- **FR-024**: Full day-score detail MUST exclude tournament-long categories unless the points are directly attributable to matches on the recap matchday.

### Key Entities *(include if feature involves data)*

- **Matchday**: A tournament session shown from the Dutch viewer perspective, including early-morning kickoff handling defined by the app.
- **Schedule Group**: A set of matches displayed together for one matchday in current, historic, or future order.
- **Personal Match Summary**: The viewer's result, score prediction, and points for one match.
- **Day Score**: The points earned by each active participant from scoring facts on one matchday.
- **Rank Movement**: The participant's standing change between before and after one matchday.
- **Point Breakdown**: The visible explanation of point components for one participant and match.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a schedule containing current, past, and future matches, 100% of current matchday games appear before historic and future games.
- **SC-002**: In a leaderboard with incomplete predictions, 0 rows use the previous orange missing-prediction highlight and no missing-prediction color legend is displayed.
- **SC-003**: For completed matchday cards with a viewer prediction, the viewer can see result, prediction, and a clickable points breakdown without leaving the matchday overview.
- **SC-004**: A locked match detail with the expected pool size loads prediction detail within 1 second on a normal local development dataset and within 2 seconds in production-like conditions.
- **SC-005**: Daily recap winners and losers are reproducible from the same matchday point inputs used for the day-score board.
- **SC-006**: The full day-score detail lists 100% of active participants for the recap matchday, including zero-point participants.
- **SC-007**: A participant can open the full day-score detail and expand one participant's breakdown without losing the recap context.

## Assumptions

- The app's existing Matchday definition remains authoritative for grouping early-morning kickoffs.
- Prediction completeness remains useful information, but should not be represented by orange row color on the leaderboard.
- The matchday detail page remains available only after match predictions are locked.
- The full day-score detail is a modal opened from the daily recap rather than a separate route.
- The full day-score list includes every active participant and uses one expanded participant row at a time.
- Per-match day-score breakdowns include score, Leeuwtje, quiz, and match-attributable striker points, while tournament-long categories remain out of scope for this feature.
