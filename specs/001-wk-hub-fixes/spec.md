# Feature Specification: WK Hub Fixes

**Feature Branch**: `001-wk-hub-fixes`

**Created**: 2026-06-04

**Status**: Draft

**Input**: User description: "WK Hub fixes from testing: champion, top scorer, and strikers must remain secret and editable until 1 hour before the first match on 11 June; after that users may see each other's champion, top scorer, and striker picks. Per-match predictions from other users become available once each match can no longer be adjusted, 1 hour before that match. Top scorer selection must not be constrained by selected champion. Top scorer and striker lists must be searchable. Personal profile text/layout needs improvement. Tutorial flow breaks when users leave it; completing tutorial should reach leaderboard; profile should not be clickable in tutorial; Back to leaderboard on profile can be removed. Leaderboard should remove awkward top scorer/striker display; player names should be clickable like profile pictures. People who just created an account do not show up in the leaderboard yet; remove the old tutorial/prediction completion gate so users can join the app, use full functionality, and be included in the leaderboard regardless of which predictions they have filled in. Admins need a manual scoring-label editor as a backup for incomplete API-Football data. Admins should inspect and adjust labels used for scoring predictions, quiz answers, scorer/striker goals, and related scoring facts, but must not be able to adjust participant predictions."

## Clarifications

### Session 2026-06-10

- Q: What time window should the wall of shame use for missing predictions/quizzes? → A: Today and tomorrow only.

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

### User Story 5 - Admins manage scoring labels without changing predictions (Priority: P1)

As an admin, I want to inspect and manually adjust the scoring labels used by the pool, so that scoring can still be corrected when API-Football data is missing, late, or wrong.

**Why this priority**: All participant scoring depends on comparing predictions to actual labels. If external label data is incomplete, the pool needs an authorized fallback without compromising participant predictions.

**Independent Test**: Can be tested by logging in as an admin, opening the label editor, changing a match result label, quiz label, or scorer/striker goal label, and verifying scoring updates while participant prediction rows remain unchanged.

**Acceptance Scenarios**:

1. **Given** an admin is logged in, **When** they open the admin labels page, **Then** they can inspect current labels for match score/result, quiz answer/viewership, goal events, scorer names, striker goal counts, and label source metadata.
2. **Given** an admin edits a match score/result label, **When** they save, **Then** leaderboard/profile scoring uses the updated label.
3. **Given** an admin edits a quiz correct-answer or viewership label, **When** they save, **Then** quiz scoring uses the updated label.
4. **Given** an admin edits scorer/goal labels, **When** they save, **Then** top scorer and striker scoring use the updated labels.
5. **Given** an admin uses the label editor, **When** they save changes, **Then** no participant prediction records are created, changed, or deleted.
6. **Given** a non-admin is logged in, **When** they try to access label inspection or update routes, **Then** access is denied.

---

### User Story 6 - Act on clear notification-bell actions (Priority: P1)

As a participant, I want notification-bell reminders to tell me exactly which prediction or quiz is missing and take me directly there, so that I can complete the right item without hunting through the predictions page.

**Why this priority**: The current bell correctly identifies that something is open, but the generic link creates confusion and can leave users unsure which quiz or match they still need to fill in.

**Independent Test**: Can be tested by leaving a specific quiz or match prediction empty, opening the notification bell, confirming the missing match/quiz is named, clicking it, and landing on the prediction interface focused on that item.

**Acceptance Scenarios**:

1. **Given** a participant has one missing quiz for an unlocked match, **When** they open the notification bell, **Then** the notification identifies that match and quiz rather than only saying a quiz is missing.
2. **Given** a participant clicks a missing quiz notification, **When** the predictions view opens, **Then** the relevant match/quiz is visible and ready to fill in.
3. **Given** a participant has multiple missing predictions or quizzes, **When** they open the notification bell, **Then** each actionable item is identifiable by match/team/date context.
4. **Given** a missing item later becomes locked or completed, **When** notifications refresh, **Then** it no longer appears as an open action.

---

### User Story 7 - Admins broadcast messages through the notification bell (Priority: P2)

As an admin, I want to send a notification message to everyone from the admin page, so that important pool updates appear in the same notification bell users already check.

**Why this priority**: Admin communication currently has no in-app broadcast path. Reusing the bell keeps messages visible without adding another communication surface.

**Independent Test**: Can be tested by logging in as an admin, sending a message from the new admin section, logging in as a different user, and confirming the bell shows the broadcast.

**Acceptance Scenarios**:

1. **Given** an admin is on the admin page, **When** they open the admin section selector, **Then** a third "send message" section is available alongside user management and label editing.
2. **Given** an admin submits a broadcast title and body, **When** users open the app, **Then** the message appears in their notification bell.
3. **Given** a non-admin attempts to access broadcast APIs or UI, **When** they try to send a message, **Then** access is denied.
4. **Given** an admin deactivates or expires a broadcast, **When** users refresh notifications, **Then** that broadcast is no longer shown as active.

---

### User Story 8 - Show real names subtly on the leaderboard (Priority: P2)

As a participant, I want leaderboard nicknames to remain prominent while also seeing a person's first and last name as a subtle side note, so that nicknames can be playful without making identity unclear.

**Why this priority**: The current display uses the username as the only visible identity. The organization email format provides reliable first/last names without requiring another profile field.

**Independent Test**: Can be tested by viewing leaderboard rows for users with `firstname.lastname@talpanetwork.com` emails and confirming the nickname is primary while derived first/last name is smaller and lower contrast.

**Acceptance Scenarios**:

1. **Given** a participant has nickname `MVP` and email `jane.doe@talpanetwork.com`, **When** the leaderboard displays their row, **Then** `MVP` is primary and `Jane Doe` is shown smaller and lighter.
2. **Given** a participant's email is valid Talpa format, **When** leaderboard data is returned, **Then** derived first and last name fields are available for display.
3. **Given** a leaderboard row is displayed on mobile, **When** nickname and real name are both present, **Then** text remains readable without overlap.

---

### User Story 9 - Preview profile pictures from the leaderboard (Priority: P3)

As a participant, I want to hover or focus a leaderboard profile picture and see it larger, so that I can inspect profile pictures without opening every profile page.

**Why this priority**: The profile page already shows a larger image, but quickly browsing the leaderboard should not require navigation.

**Independent Test**: Can be tested by hovering or keyboard-focusing a leaderboard avatar and confirming a larger preview appears without changing layout or opening the profile.

**Acceptance Scenarios**:

1. **Given** a participant views the leaderboard on desktop, **When** they hover over another user's avatar, **Then** a larger profile image preview appears.
2. **Given** a participant navigates by keyboard, **When** the avatar/name link receives focus, **Then** the larger image preview is also available.
3. **Given** the preview appears near screen edges, **When** the leaderboard is displayed on common viewport widths, **Then** the preview does not cover critical controls or overflow incoherently.

---

### User Story 10 - Restrict account emails to Talpa identity format (Priority: P1)

As an admin, I want only `firstname.lastname@talpanetwork.com` email addresses to create accounts, so that the pool is limited to the intended organization and real names can be reliably derived.

**Why this priority**: Email format now drives both access eligibility and first/last-name display. Allowing other domains or structures would break both assumptions.

**Independent Test**: Can be tested by creating accounts with valid and invalid emails and confirming only valid Talpa-format emails are accepted.

**Acceptance Scenarios**:

1. **Given** a new user enters `jane.doe@talpanetwork.com`, **When** they create an account, **Then** the account can be created if all other validation passes.
2. **Given** a new user enters a non-Talpa domain, **When** they create an account, **Then** account creation is rejected with a clear message.
3. **Given** a new user enters `jane@talpanetwork.com` or another address without exactly derivable first and last names, **When** they create an account, **Then** account creation is rejected with a clear message.

---

### User Story 11 - Admins fully edit quiz questions and answer options (Priority: P1)

As an admin, I want the label editor to let me select labels/options and adjust quiz question text plus answer options, so that wrong or incomplete quiz data can be corrected without editing code or participant predictions.

**Why this priority**: Some quiz questions and answers are wrong or incomplete. Admins need an operational fix path for both labels and quiz content.

**Independent Test**: Can be tested by editing a quiz question, answer options, and correct answer from the admin page, then verifying prediction entry/scoring uses the corrected data while participant predictions remain unchanged.

**Acceptance Scenarios**:

1. **Given** an admin opens the label editor, **When** a match has many labels/options, **Then** the admin can scroll through and select the needed label or option.
2. **Given** an admin edits a quiz question, **When** they save, **Then** the corrected question appears in the prediction interface.
3. **Given** an admin edits quiz answer options, **When** they save, **Then** the corrected options are available for prediction entry and scoring.
4. **Given** an admin changes correct quiz labels, **When** scoring is recalculated, **Then** quiz points use the updated labels without changing participant prediction rows.

---

### User Story 12 - Show a wall of shame for missing open predictions (Priority: P2)

As a participant, I want to see who still has open predictions to fill in, so that the pool can hold each other accountable before matches lock.

**Why this priority**: The app now allows incomplete predictions, which is good for access, but the group still needs visibility into who has open actionable work.

**Independent Test**: Can be tested by leaving predictions incomplete for one user, completing them for another, and confirming only the user with currently open missing items appears in the wall of shame.

**Acceptance Scenarios**:

1. **Given** a participant has missing predictions for matches that are still editable, **When** the wall of shame is displayed, **Then** that participant appears with missing-action context.
2. **Given** a participant has completed all currently open required predictions and quizzes, **When** the wall of shame is displayed, **Then** that participant does not appear.
3. **Given** a missing prediction's match has locked, **When** the wall of shame refreshes, **Then** that locked item no longer counts as an open missing action.
4. **Given** an account is archived, **When** the wall of shame is displayed, **Then** the archived user is excluded.

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
- API-Football provides no data for a completed match yet.
- API-Football provides a match score but missing or incomplete goal/scorer events.
- API-Football scorer names do not exactly match selectable player names.
- A quiz answer label is missing or corrected after participants already entered predictions.
- An admin saves a manual label and API-Football sync later returns different data.
- A non-admin attempts to call admin label APIs directly.
- A notification references a match that locks before the participant clicks it.
- Multiple missing quiz/prediction notifications exist for the same match.
- An admin broadcast is active while a user has no personal missing-action notifications.
- A participant uses a nickname that does not resemble their email-derived name.
- A user email contains uppercase letters but otherwise matches the required Talpa format.
- A user email contains plus-addressing, extra dots, missing first name, missing last name, or another domain.
- A profile image URL is missing or broken when the leaderboard hover preview is shown.
- An admin edits answer options after participants already selected old answer values.
- A wall-of-shame row has many missing items and must remain readable on mobile.

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
- **FR-032**: The system MUST provide an admin-only page for inspecting scoring labels used to score match predictions, quiz predictions, top scorer picks, and striker picks.
- **FR-033**: The system MUST store and expose scoring-label source metadata, distinguishing API-Football labels from manual admin labels where relevant.
- **FR-034**: The system MUST allow admins to manually update match score/result labels.
- **FR-035**: The system MUST allow admins to manually update quiz correct-answer and viewership labels.
- **FR-036**: The system MUST allow admins to manually update goal/scorer labels that determine top scorer and striker points.
- **FR-037**: The system MUST ensure admin label updates affect scoring through label/result data only and MUST NOT mutate participant prediction records.
- **FR-038**: The system MUST deny label inspection and label update access to non-admin users.
- **FR-039**: The system MUST preserve enough audit/source information to identify who manually changed labels and when.
- **FR-040**: The system MUST continue to use API-Football labels when no manual override exists.
- **FR-041**: Notification-bell missing-action items MUST identify the specific match and whether the missing item is a score prediction, quiz answer, or other supported prediction action.
- **FR-042**: Clicking a missing-action notification MUST route the participant to a prediction interface focused on the relevant missing item when that item is still editable.
- **FR-043**: Notification data MUST remove completed or locked missing-action items on refresh.
- **FR-044**: The system MUST provide admin-only broadcast-notification creation from the admin page.
- **FR-045**: Admin broadcast notifications MUST appear in the notification bell for active, non-archived users while the broadcast is active.
- **FR-046**: Non-admin users MUST NOT be able to create, update, deactivate, or inspect admin broadcast management endpoints.
- **FR-047**: The admin page MUST include a third section for sending messages in addition to existing user management and label editing sections.
- **FR-048**: The leaderboard MUST keep the nickname as the primary visible name.
- **FR-049**: The leaderboard MUST show first and last name derived from `firstname.lastname@talpanetwork.com` as smaller, lighter supporting text.
- **FR-050**: The system MUST derive first and last name from the user's email using the required Talpa email format rather than adding a separate editable real-name field.
- **FR-051**: Leaderboard profile avatars MUST show a larger image preview on hover and keyboard focus without requiring navigation to the profile page.
- **FR-052**: Account creation MUST only allow email addresses matching `firstname.lastname@talpanetwork.com`.
- **FR-053**: Account creation MUST reject non-Talpa domains and Talpa emails that do not provide both first and last name segments.
- **FR-054**: Email validation MUST be enforced server-side for all account-creation paths.
- **FR-055**: The admin label editor MUST allow admins to scroll through and select label/answer options when the option list is longer than the visible area.
- **FR-056**: The admin label editor MUST allow admins to update quiz question text.
- **FR-057**: The admin label editor MUST allow admins to update quiz answer options.
- **FR-058**: Quiz question and option overrides MUST affect prediction entry and scoring without mutating participant quiz prediction records.
- **FR-059**: Admin quiz question, option, and correct-label edits MUST preserve audit/source metadata.
- **FR-060**: The system MUST provide a wall of shame listing active users with currently open missing predictions or quizzes for matches scheduled today or tomorrow.
- **FR-061**: The wall of shame MUST exclude archived users, completed items, items outside the today/tomorrow notification window, and items that are no longer editable because their match is locked.
- **FR-062**: Wall-of-shame rows MUST show enough context to understand what is missing without exposing private prediction content.

### Key Entities

- **Participant**: A logged-in pool user who can enter predictions, view their own picks, view the leaderboard, and view participant profiles.
- **Tournament Pick**: A participant's champion, top scorer, and five striker selections, governed by one shared tournament lock/reveal moment.
- **Match Prediction**: A participant's match-specific prediction details, including score prediction, quiz prediction, and Leeuwtje usage, governed by that match's lock moment.
- **Player Option**: A selectable football player associated with a team and used for top scorer and striker picks.
- **Leaderboard Row**: A summary of participant ranking and scoring information, with profile navigation but without detailed scorer/striker names.
- **Profile View**: A detailed participant view that can display tournament picks and match prediction details when visibility rules allow.
- **Tutorial Context**: The onboarding flow where leaderboard preview content is informational and must not activate profile navigation.
- **App Participant**: An account user who has access to normal app functionality and leaderboard inclusion independent of prediction completion.
- **Admin User**: An account user with permission to manage accounts and scoring labels.
- **Scoring Label**: Actual-result data used to score predictions, including match score/result, quiz answer/viewership answer, goal/scorer event labels, and player-stat labels.
- **Manual Label Override**: An admin-authored correction or fallback label that takes precedence over missing or incorrect API-Football data.
- **Actionable Notification**: A notification-bell item that identifies a specific missing prediction or quiz and includes a route/focus target.
- **Admin Broadcast Notification**: An admin-authored message shown through the notification bell to all active users during its active window.
- **Derived Real Name**: A user's first and last name parsed from the required Talpa email address and displayed as secondary leaderboard identity.
- **Wall of Shame Entry**: An accountability row for an active user with currently editable missing prediction or quiz actions.

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
- **SC-014**: 100% of admin label update attempts by non-admin users are rejected.
- **SC-015**: After an admin updates a match score/result label, affected match prediction points reflect the new label without changing participant prediction rows.
- **SC-016**: After an admin updates quiz or scorer/goal labels, affected quiz/top-scorer/striker points reflect the new labels without changing participant prediction rows.
- **SC-017**: The admin labels page shows source/override status for all editable scoring labels.
- **SC-018**: 100% of missing quiz notifications identify the affected match and open the relevant prediction/quiz area when clicked.
- **SC-019**: Admin broadcast messages sent from the admin page appear in another active user's notification bell after refresh.
- **SC-020**: 100% of tested invalid account emails outside `firstname.lastname@talpanetwork.com` are rejected during account creation.
- **SC-021**: Leaderboard rows show nickname as primary text and derived first/last name as smaller, lower-emphasis text for users with valid Talpa emails.
- **SC-022**: Hovering or keyboard-focusing leaderboard avatars shows a larger profile picture preview on desktop without layout shift.
- **SC-023**: Admin quiz edits to question text and answer options are reflected in prediction entry/scoring without changing participant prediction rows.
- **SC-024**: Wall-of-shame output includes users with currently open missing items for today or tomorrow and excludes users with no currently open missing items in that window.

## Assumptions

- The first scheduled tournament match in the app's World Cup data is the source of truth for calculating the tournament-pick lock/reveal moment.
- Tournament-pick lock and reveal are the same moment: 1 hour before the first scheduled tournament match.
- "Other participants' match predictions" includes score, quiz, and Leeuwtje details because these are match-specific prediction details shown in profile prediction groups.
- Leaderboard should not show top scorer or striker names; detailed tournament-pick names should be revealed through profile or prediction-detail surfaces after reveal.
- Scorer and striker choices are selected from available player options; if an already-saved value is not currently in the option list, it should remain visible to its owner and manageable before lock time.
- Existing login/session behavior remains unchanged.
- Account creation is sufficient to make a user an app participant for leaderboard purposes; prediction completion affects scoring/progress only.
- Existing label tables `match_results`, `match_events`, and `player_match_stats` are the scoring-label database for API-Football match scores, events, and player stats.
- Quiz label overrides require DB-backed storage because quiz labels currently come from static quiz data.
- Manual labels take precedence over API-Football labels for scoring until edited or cleared by an admin.
- All valid participant emails follow `firstname.lastname@talpanetwork.com`; casing may be normalized for storage/display.
- `users.name` remains the nickname field.
- Admin broadcast dismissal/read-state is not required for the first implementation unless added during task generation; active broadcasts may remain visible until deactivated or expired.
- The wall of shame is for currently actionable missing predictions/quizzes for today and tomorrow, not for future fixtures outside that window or historical missed locked predictions.
