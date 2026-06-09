# Feature Specification: WK Hub Fixes

**Feature Branch**: `001-wk-hub-fixes`

**Created**: 2026-06-04

**Status**: Draft

**Input**: User description: "WK Hub fixes from testing: champion, top scorer, and strikers must remain secret and editable until 1 hour before the first match on 11 June; after that users may see each other's champion, top scorer, and striker picks. Per-match predictions from other users become available once each match can no longer be adjusted, 1 hour before that match. Top scorer selection must not be constrained by selected champion. Top scorer and striker lists must be searchable. Personal profile text/layout needs improvement. Tutorial flow breaks when users leave it; completing tutorial should reach leaderboard; profile should not be clickable in tutorial; Back to leaderboard on profile can be removed. Leaderboard should remove awkward top scorer/striker display; player names should be clickable like profile pictures. People who just created an account do not show up in the leaderboard yet; remove the old tutorial/prediction completion gate so users can join the app, use full functionality, and be included in the leaderboard regardless of which predictions they have filled in."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Protect prediction secrecy until lock times (Priority: P1)

As a pool participant, I want tournament picks and match predictions from other participants to stay hidden until the agreed lock moment, so that nobody can copy or react to private predictions while they are still editable.

**Why this priority**: Prediction secrecy is core to pool fairness. Leaking champion, top scorer, striker, or match predictions early undermines trust in the competition.

**Independent Test**: Can be fully tested by comparing what a participant sees for their own predictions versus another participant's predictions before and after the relevant lock moments.

**Acceptance Scenarios**:

1. **Given** the current time is before the tournament-pick reveal time, **When** a participant views another participant's leaderboard row or profile, **Then** champion, top scorer, and striker pick names for that other participant are not visible.
2. **Given** the current time is before the tournament-pick reveal time, **When** a participant views their own profile or prediction flow, **Then** their own champion, top scorer, and striker picks remain visible and editable.
3. **Given** the current time is at or after the tournament-pick reveal time, **When** a participant views another participant's profile, **Then** that participant's champion, top scorer, and striker picks are visible.
4. **Given** a match has not reached its individual prediction lock time, **When** a participant views another participant's match predictions, **Then** that match's prediction details are hidden.
5. **Given** a match has reached its individual prediction lock time, **When** a participant views another participant's match predictions before or after kickoff, **Then** that match's prediction details are visible.

---

### User Story 2 - Choose tournament scorers easily and freely (Priority: P2)

As a participant entering tournament picks, I want to search across all available players for top scorer and striker picks, regardless of my selected champion, so that I can make accurate picks without scrolling through long lists or being constrained by another selection.

**Why this priority**: Tournament picks are required for a complete entry and the current long list is hard to use. Restricting scorer choices to the champion team prevents valid pool strategies.

**Independent Test**: Can be tested by selecting one team as champion, choosing a top scorer from a different team, using search to find players by name or team, and saving the picks before lock time.

**Acceptance Scenarios**:

1. **Given** a participant has selected a champion team, **When** they choose a top scorer, **Then** they can select a player from any available team, not only the champion team.
2. **Given** a participant is choosing a top scorer or striker, **When** they type part of a player name, **Then** matching player options are discoverable.
3. **Given** a participant is choosing a top scorer or striker, **When** they type part of a team name, **Then** matching player options from that team are discoverable.
4. **Given** a participant has already selected a striker, **When** they choose another striker slot, **Then** duplicate striker selections are prevented or clearly unavailable.
5. **Given** tournament picks are locked, **When** a participant views scorer and striker controls, **Then** the controls are no longer editable.

---

### User Story 3 - Use leaderboard and profile pages without confusing navigation or layout (Priority: P3)

As a participant, I want profile, leaderboard, and tutorial screens to have clear navigation and readable text, so that I can complete onboarding and browse standings without getting stuck or seeing awkwardly formatted information.

**Why this priority**: These fixes improve usability after the fairness-critical prediction rules are correct.

**Independent Test**: Can be tested by walking through onboarding, viewing the leaderboard preview, continuing without mandatory prediction prerequisites, opening profiles from the normal leaderboard, and checking profile readability on common screen sizes.

**Acceptance Scenarios**:

1. **Given** a participant is in the tutorial leaderboard preview, **When** they interact with leaderboard rows, **Then** profile links are not active in that tutorial context.
2. **Given** a participant continues from onboarding, with or without saving predictions, **When** they proceed, **Then** they arrive at a normal app view such as the leaderboard.
3. **Given** a participant views a profile page, **When** the page is displayed, **Then** there is no profile-specific "Back to leaderboard" control.
4. **Given** a participant views the normal leaderboard, **When** they select either a player's profile picture or name, **Then** the player's profile opens.
5. **Given** a participant views the leaderboard, **When** standings are displayed, **Then** top scorer and striker names are not shown in leaderboard columns.
6. **Given** a participant views a profile with long names or labels, **When** the profile is displayed on common desktop or mobile widths, **Then** text remains readable without awkward overflow or truncation.

---

### User Story 4 - Join immediately without prediction prerequisites (Priority: P1)

As a newly registered participant, I want to access the app and appear in the leaderboard immediately, so that joining the pool is not blocked by an outdated tutorial requirement or by missing tournament predictions.

**Why this priority**: New users currently disappear from the leaderboard until they complete legacy prediction steps. That makes account creation feel broken and hides active participants from the pool.

**Independent Test**: Can be tested by creating a new account, entering the app without saving champion, top scorer, striker, Netherlands, or other predictions, and verifying the user has normal app access and a leaderboard row.

**Acceptance Scenarios**:

1. **Given** a person has just created an account and saved no predictions, **When** they enter the app, **Then** they can access normal app functionality without being forced through a prediction prerequisite.
2. **Given** a person has just created an account and saved no predictions, **When** the leaderboard is loaded, **Then** that participant appears in the leaderboard with zero points and appropriate incomplete-prediction progress state.
3. **Given** a participant has filled in only some predictions, **When** the leaderboard is loaded, **Then** that participant remains visible in the leaderboard.
4. **Given** a participant has not filled in champion, top scorer, or striker picks, **When** their leaderboard row or profile is displayed, **Then** missing picks are represented as empty/not chosen states rather than excluding the participant.

---

### Edge Cases

- Lock-time boundary: exactly at the tournament-pick reveal time, tournament picks become non-editable and visible according to the reveal rules.
- Per-match boundary: exactly at an individual match lock time, other participants' match prediction details become visible.
- A participant has not selected a champion, top scorer, or all five strikers before reveal.
- A saved scorer or striker name is no longer present in the current available player list.
- Multiple available players share the same display name across different teams.
- Search returns no matching players.
- A participant exits or reloads during tutorial before completing any predictions.
- A participant appears in leaderboard contexts with no predictions or with incomplete optional predictions.
- Profile names, player names, or team names are unusually long.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define one shared tournament-pick lock and reveal moment for champion, top scorer, and striker picks: 1 hour before the first scheduled tournament match on 11 June.
- **FR-002**: The system MUST allow a participant to view and edit their own champion, top scorer, and striker picks until the tournament-pick lock moment.
- **FR-003**: The system MUST prevent changes to champion, top scorer, and striker picks after the tournament-pick lock moment.
- **FR-004**: The system MUST hide champion, top scorer, and striker pick names for other participants before the tournament-pick reveal moment.
- **FR-005**: The system MUST show champion, top scorer, and striker pick names for other participants at or after the tournament-pick reveal moment.
- **FR-006**: The system MUST ensure hidden tournament-pick names are not exposed through views or response data used by leaderboard and profile surfaces before reveal.
- **FR-007**: The system MUST allow participants to see their own match prediction details regardless of whether each match is locked or completed.
- **FR-008**: The system MUST hide another participant's match-specific prediction details until that individual match reaches its prediction lock time.
- **FR-009**: The system MUST show another participant's match-specific prediction details once that individual match reaches its prediction lock time, even if the match has not started or finished.
- **FR-010**: Match-specific prediction details MUST include score prediction, quiz prediction, and Leeuwtje usage where those details exist for a match.
- **FR-011**: The system MUST allow top scorer selection from all available player options, independent of the selected champion team.
- **FR-012**: The system MUST allow striker selections from all available player options, independent of the selected champion team.
- **FR-013**: The system MUST provide searchable top scorer and striker selection controls that support search by player name and team name.
- **FR-014**: The system MUST clearly distinguish players with the same name when they belong to different teams.
- **FR-015**: The system MUST prevent duplicate striker selections across the five striker slots.
- **FR-016**: The system MUST preserve already-saved scorer and striker selections when a participant revisits or reloads prediction entry before lock time.
- **FR-017**: The system MUST allow a participant to clear or replace a scorer or striker selection before the tournament-pick lock moment.
- **FR-018**: The system MUST keep profile links inactive in tutorial leaderboard previews.
- **FR-019**: The system MUST route a participant to a normal app view such as the leaderboard when they continue from onboarding, regardless of whether they saved predictions.
- **FR-020**: The system MUST remove the profile-specific "Back to leaderboard" control from profile pages.
- **FR-021**: The system MUST make both player profile pictures and player names open profiles from the normal leaderboard.
- **FR-022**: The system MUST remove top scorer and striker names from leaderboard display.
- **FR-023**: The system MUST not rely on leaderboard tournament-pick name columns for revealing champion, top scorer, or striker picks; detailed reveal belongs on profile or other detailed prediction surfaces after reveal.
- **FR-024**: The system MUST improve profile text layout so names, stat labels, pick labels, and long player/team names remain readable on common desktop and mobile widths.
- **FR-025**: The system MUST present clear empty states when scorer search has no results or when a participant has not made tournament picks.
- **FR-026**: The system MUST use consistent, understandable Dutch-facing labels for affected tournament-pick and profile concepts.
- **FR-027**: The system MUST include every account user in the leaderboard, regardless of whether they have completed Netherlands group predictions, champion picks, top scorer picks, striker picks, or any other prediction set.
- **FR-028**: The system MUST treat prediction completion as progress metadata only and MUST NOT use completion state as a prerequisite for app access or leaderboard eligibility.
- **FR-029**: The system MUST show newly registered users with no predictions as leaderboard participants with zero earned points and appropriate incomplete/missing-prediction indicators.
- **FR-030**: The system MUST allow participants with no or partial predictions to access normal app functionality, including leaderboard, profiles, prediction entry, and adjustment flows where otherwise permitted.
- **FR-031**: Onboarding/tutorial copy and routing MUST NOT state or imply that specific predictions are required to join the app or appear on the leaderboard.

### Key Entities

- **Participant**: A logged-in pool user who can enter predictions, view their own picks, view the leaderboard, and view participant profiles.
- **Tournament Pick**: A participant's champion, top scorer, and five striker selections, governed by one shared tournament lock/reveal moment.
- **Match Prediction**: A participant's match-specific prediction details, including score prediction, quiz prediction, and Leeuwtje usage, governed by that match's lock moment.
- **Player Option**: A selectable football player associated with a team and used for top scorer and striker picks.
- **Leaderboard Row**: A summary of participant ranking and scoring information, with profile navigation but without detailed scorer/striker names.
- **Profile View**: A detailed participant view that can display tournament picks and match prediction details when visibility rules allow.
- **Tutorial Context**: The onboarding flow where leaderboard preview content is informational and must not activate profile navigation.
- **App Participant**: An account user who has access to normal app functionality and leaderboard inclusion independent of prediction completion.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Before tournament-pick reveal time, 100% of other participants' champion, top scorer, and striker names are hidden from leaderboard and profile surfaces.
- **SC-002**: At or after tournament-pick reveal time, participants can view other participants' champion, top scorer, and striker names on detailed prediction/profile surfaces.
- **SC-003**: For each match, other participants' match prediction details become visible no later than the match's lock moment and remain hidden before that moment.
- **SC-004**: Participants can successfully save a top scorer from a different team than their selected champion before tournament-pick lock time.
- **SC-005**: Participants can find relevant scorer or striker options by typing part of a player name or team name.
- **SC-006**: Duplicate striker selections are prevented for 100% of striker slots.
- **SC-007**: Participants who continue from onboarding arrive at a normal app view without needing additional manual navigation or prediction completion.
- **SC-008**: In tutorial leaderboard preview, profile navigation is unavailable for 100% of leaderboard rows.
- **SC-009**: In normal leaderboard view, both the profile picture and player name provide access to the participant profile.
- **SC-010**: Profile pages remain readable without horizontal text overflow at common desktop and mobile viewport widths.
- **SC-011**: 100% of newly created accounts appear in the leaderboard before saving any predictions.
- **SC-012**: 100% of participants with partial or missing tournament picks remain visible in the leaderboard.
- **SC-013**: Newly created accounts can reach normal app views without completing Netherlands, champion, top scorer, or striker predictions first.

## Assumptions

- The first scheduled tournament match in the app's World Cup data is the source of truth for calculating the tournament-pick lock/reveal moment.
- Tournament-pick lock and reveal are the same moment: 1 hour before the first scheduled tournament match.
- "Other participants' match predictions" includes score, quiz, and Leeuwtje details because these are match-specific prediction details shown in profile prediction groups.
- Leaderboard should not show top scorer or striker names; detailed tournament-pick names should be revealed through profile or prediction-detail surfaces after reveal.
- Scorer and striker choices are selected from available player options; if an already-saved value is not currently in the option list, it should remain visible to its owner and manageable before lock time.
- Existing login/session behavior remains unchanged.
- Account creation is sufficient to make a user an app participant for leaderboard purposes; prediction completion affects scoring/progress only.
