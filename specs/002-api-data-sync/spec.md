# Feature Specification: API Data Sync

**Feature Branch**: `main`

**Created**: 2026-06-10

**Status**: Draft

**Input**: User description: "Redesign external football data retrieval as a clearer provider-agnostic sync boundary with post-match per-match result sync, fixed squad sync, raw snapshot history, normalized current labels, manual overrides that win over provider data, stored computed points, auditability, and admin notification when fixture linking is impossible or API data cannot be retrieved."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retrieve only relevant post-match data (Priority: P1)

As the pool operator, I want match result data to be retrieved only for the match that just finished, so that scoring updates are timely without repeatedly fetching the full tournament history.

**Why this priority**: Result data drives scoring. The current broad sync model should become a clearer post-match workflow that uses external data intentionally and avoids unnecessary provider calls.

**Independent Test**: Can be tested by marking one match as eligible for post-match sync while other completed or future matches are not eligible, then confirming only the eligible match is requested from the provider.

**Acceptance Scenarios**:

1. **Given** a match has passed its first post-match sync moment, **When** the result sync runs, **Then** the system requests data only for that match.
2. **Given** a match has not reached a post-match sync moment, **When** the result sync runs, **Then** the system does not request provider data for that match.
3. **Given** earlier matches have already completed their scheduled result sync attempts, **When** a later match becomes due, **Then** the system does not re-fetch the earlier matches.
4. **Given** a match receives partial provider data at the first sync moment, **When** the second sync moment runs, **Then** the system requests that same match again and updates the stored provider data with any newer values.

---

### User Story 2 - Keep external data behind a clear boundary (Priority: P1)

As a maintainer, I want provider retrieval, normalization, and scoring inputs to sit behind a clear internal boundary, so that API-Football can be managed as a provider rather than mixed into general app behavior.

**Why this priority**: The app should be easier to reason about and should not spread provider-specific assumptions through leaderboard, profile, prediction, or admin code.

**Independent Test**: Can be tested by reviewing data retrieval flows and confirming normal user views read app-owned data while provider-specific request logic is isolated to the sync boundary.

**Acceptance Scenarios**:

1. **Given** a normal participant loads the app, **When** leaderboard, profile, or prediction screens render, **Then** those screens read app-owned tournament and scoring data rather than contacting the external provider.
2. **Given** a provider response is received, **When** the sync completes, **Then** provider-specific fields are transformed into app-owned result, event, player-stat, and scoring-label records.
3. **Given** a future provider is introduced, **When** it supplies equivalent match data, **Then** the app can store normalized scoring inputs without changing participant-facing behavior.

---

### User Story 3 - Preserve data history while using current facts for scoring (Priority: P2)

As an admin, I want every provider payload and manual correction to remain auditable while scoring uses the latest trusted current facts, so that disputes can be investigated without making scoring logic depend on historical payload parsing.

**Why this priority**: Scoring must be stable and explainable. Keeping raw history supports audits, while normalized current labels keep app reads straightforward.

**Independent Test**: Can be tested by running two sync attempts for the same match, checking that both raw payloads remain available, and confirming the current scoring labels reflect the latest non-manual provider data unless an admin override exists.

**Acceptance Scenarios**:

1. **Given** provider data is retrieved for a match, **When** it is stored, **Then** the raw provider payload is retained permanently.
2. **Given** newer provider data arrives for a match, **When** no manual override exists for the affected fact, **Then** the current normalized fact is updated.
3. **Given** a manual override exists for an affected fact, **When** newer provider data arrives, **Then** the manual value remains the scoring value.
4. **Given** an admin manually changes a scoring fact, **When** the change is saved, **Then** the system records who changed it, when it changed, the previous value, the new value, and the reason when provided.
5. **Given** an admin reverses a manual override, **When** the reversal is saved, **Then** scoring returns to the current provider-backed value if one exists.

---

### User Story 4 - Score from stored computed points (Priority: P2)

As a participant, I want standings and profiles to reflect updated results consistently after data arrives, so that every page shows the same points after a match has been scored.

**Why this priority**: Recomputing points only on read can make behavior harder to audit and may become inconsistent as manual overrides and provider updates interact.

**Independent Test**: Can be tested by syncing or manually correcting a finished match and confirming stored computed points are updated and then displayed consistently across leaderboard and profile views.

**Acceptance Scenarios**:

1. **Given** a match is not done, **When** manual labels exist for that match, **Then** those labels do not affect visible participant scoring yet.
2. **Given** a match is done and scoring facts are updated, **When** recalculation runs, **Then** stored computed points are updated for affected participants.
3. **Given** leaderboard and profile pages are loaded after recalculation, **When** they show points for the affected match, **Then** both pages use the same stored computed values.
4. **Given** provider data is partial, **When** scoring can be computed for some categories but not others, **Then** completed categories are stored and incomplete categories remain pending or unscored until data or manual labels are available.

---

### User Story 5 - Notify admins when data cannot be retrieved or linked (Priority: P2)

As an admin, I want to know when a scheduled post-match sync cannot retrieve or map the needed provider data, so that I can manually correct labels before participants are confused by missing scores.

**Why this priority**: Missing provider links should be exceptional. If they happen, normal users should not see broken internals, and admins need enough signal to act.

**Independent Test**: Can be tested by creating a match due for sync without a provider fixture mapping and confirming the result remains blank while admins receive a clear notification.

**Acceptance Scenarios**:

1. **Given** a due match has no provider fixture mapping, **When** the result sync runs, **Then** the match result remains blank and admins are notified.
2. **Given** the provider request fails for a due match, **When** the sync attempt finishes, **Then** admins are notified that data could not be retrieved.
3. **Given** participants view a match whose result could not be retrieved, **When** the match is displayed, **Then** they see no incorrect result or provider error details.

---

### User Story 6 - Create Talpa Studios accounts with strict email convention (Priority: P1)

As a Talpa Studios participant, I want to create or access my account with my company email, so that only eligible participants can join the pool.

**Why this priority**: Account access is the entry point for all pool behavior. The requested domain and naming convention should be enforced consistently in frontend and backend validation.

**Independent Test**: Can be tested by attempting login/account creation with valid and invalid email addresses and confirming only `firstname.lastname@talpastudios.com` accounts are accepted.

**Acceptance Scenarios**:

1. **Given** a new participant enters `firstname.lastname@talpastudios.com`, **When** they log in with a valid password flow, **Then** the system creates or accesses that account.
2. **Given** an email is outside the `talpastudios.com` domain, **When** the user attempts account creation or login for a missing account, **Then** the system rejects the email.
3. **Given** an email does not follow `firstname.lastname@talpastudios.com`, **When** account creation is attempted, **Then** the system rejects it with a clear validation message.
4. **Given** an existing eligible participant returns, **When** they log in, **Then** email normalization remains case-insensitive and does not create duplicate accounts.

---

### User Story 7 - Ask each participant whether they join the prize pot (Priority: P1)

As a participant, I want to choose whether I join the optional prize pot, so that my participation status is clear without requiring payment handling inside the app.

**Why this priority**: The pool organizer needs a clear opt-in/opt-out signal, and participants should be free to decide. The choice should be visible on profiles so others can see who joined.

**Independent Test**: Can be tested by logging in as an undecided participant, confirming the notification appears, choosing join or decline, and confirming the notification no longer prompts after the choice is stored.

**Acceptance Scenarios**:

1. **Given** a participant has not answered the prize-pot question, **When** they log in or return to the website, **Then** they receive a notification asking whether they want to join.
2. **Given** the participant chooses to join, **When** the answer is saved, **Then** their profile shows that they participate in the prize pot.
3. **Given** the participant chooses not to join, **When** the answer is saved, **Then** their profile shows that they do not participate.
4. **Given** a participant has already answered, **When** they return to the website, **Then** the prize-pot prompt is not shown again unless they reset or edit the choice in a future scope.
5. **Given** the prize-pot prompt is displayed, **When** the participant reads it, **Then** it communicates the EUR 10 contribution, that the final prize amount is still to be determined, and that Olivier Thijsen organizes payment outside the app.

---

### User Story 8 - Make tournament prediction picks clearer and view-first (Priority: P2)

As a participant, I want the champion, top-scorer, and striker picks to be easy to understand in view mode and only editable after I explicitly choose to edit, so that I can inspect picks without accidentally changing them.

**Why this priority**: The current striker copy is unclear and the pick surface mixes viewing and editing. Better visual context reduces mistakes and makes profiles more useful.

**Independent Test**: Can be tested by opening the prediction screen and a profile with completed tournament picks, confirming full names plus flags/countries are visible, then clicking the component in view mode and confirming no value changes until the edit button is used.

**Acceptance Scenarios**:

1. **Given** a participant has selected a champion, **When** the pick is shown in predictions or profile view, **Then** the champion name is shown with its flag.
2. **Given** a participant has selected a top scorer, **When** the pick is shown in view mode, **Then** the player's full name and country flag/country are visible.
3. **Given** a participant has selected strikers, **When** the striker section is shown in view mode, **Then** each striker shows the full player name and country flag/country.
4. **Given** the participant clicks a pick component in view mode, **When** no edit mode is active, **Then** the click does not change the pick.
5. **Given** the participant selects the edit button, **When** tournament picks are still unlocked, **Then** champion, top scorer, and striker controls become editable.
6. **Given** tournament picks are locked, **When** the participant opens the component, **Then** it remains view-only and does not offer changes.

---

### Edge Cases

- A match goes to extra time or penalties, and the first post-match sync occurs before complete provider labels are available.
- Provider data contains a final score but missing events or player statistics.
- The provider changes score, event, or player-stat facts between the first and second scheduled sync.
- A manual override exists before the second provider sync arrives.
- A manual override is reversed after provider data has already been stored.
- A match has no provider fixture mapping even though the schedule expects one.
- A provider request fails, times out, or returns malformed data for a due match.
- Squad data changes unexpectedly after the tournament starts.
- Computed scoring updates partially because some scoring categories have complete labels and others do not.
- A participant uses uppercase letters or leading/trailing spaces in an otherwise valid Talpa Studios email.
- A participant has an old account from the previous email convention.
- A participant dismisses or ignores the prize-pot notification without choosing join or decline.
- Prize-pot payment is made outside the app but the participant has not updated their app choice.
- A player shares a name with another player from a different country.
- A selected striker/top-scorer name no longer appears in synced squad metadata.
- A participant opens the tournament pick component on mobile and long names must still fit without overlapping.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST keep normal participant app usage separate from external provider retrieval; participant views MUST read app-owned data only.
- **FR-002**: The system MUST provide a clear internal boundary for provider retrieval, provider response storage, normalization, and scoring-label publication.
- **FR-003**: The provider boundary MUST be able to support API-Football initially while preserving a path for future providers with equivalent match data.
- **FR-004**: Result sync MUST run per relevant match rather than fetching the full completed tournament history.
- **FR-005**: Each match result sync MUST be scheduled for two post-match attempts: one approximately 15 minutes after the match and one approximately 2 hours after the match.
- **FR-006**: The system MUST fetch result data only after a match has started and reached a configured post-match sync moment.
- **FR-007**: The system MUST NOT keep rechecking final matches after the two planned post-match attempts unless an admin explicitly triggers a correction workflow in a future scope.
- **FR-008**: Squad sync MUST remain separate from result sync and MUST NOT run on the same regular cadence as match results.
- **FR-009**: The system MUST support one-time or rare squad sync because tournament squads are expected to be mostly fixed.
- **FR-010**: The system MUST retain raw provider payload history permanently for audit and replay.
- **FR-011**: The system MUST maintain normalized current records for match results, match events, player match statistics, and scoring labels.
- **FR-012**: The system MUST store partial provider data when some facts are available and MUST allow later provider data to overwrite incomplete or outdated provider-backed facts.
- **FR-013**: Manual admin overrides MUST take precedence over provider-backed facts.
- **FR-014**: Provider updates MUST NOT overwrite manually overridden facts unless the manual override has been reversed or removed.
- **FR-015**: Manual override changes MUST be auditable with actor, timestamp, previous value, new value, source, and optional reason.
- **FR-016**: Admins MUST be able to reverse manual overrides so the scoring fact can return to the current provider-backed value.
- **FR-017**: Manual labels for a match MUST affect participant-visible scoring only after that match is done.
- **FR-018**: The system MUST store computed participant points after scoring facts change.
- **FR-019**: Leaderboard and profile views MUST read stored computed points for scored categories.
- **FR-020**: The system MUST recalculate affected stored points when provider-backed facts or manual override facts change for a done match.
- **FR-021**: If a due match cannot be linked to a provider fixture, the system MUST leave the result blank and notify admins.
- **FR-022**: If a provider request cannot retrieve data for a due match, the system MUST notify admins without exposing provider error details to normal participants.
- **FR-023**: The system MUST avoid a separate app-managed API request limit for result sync beyond provider/account constraints and the configured per-match sync schedule.
- **FR-024**: The system MUST keep existing participant prediction data unchanged when provider data, manual labels, or computed scoring records are updated.
- **FR-025**: The system MUST treat manual override and provider data source labels consistently so scoring can identify whether a fact came from a provider, admin override, or future source.
- **FR-026**: The system MUST allow eligible participants to create accounts during login only when their email follows `firstname.lastname@talpastudios.com`.
- **FR-027**: Account email validation MUST be enforced on both the backend and frontend and MUST be case-insensitive after trimming whitespace.
- **FR-028**: The system MUST reject account creation or missing-account login attempts for emails outside `talpastudios.com` or without exactly one first-name and one last-name segment before the domain.
- **FR-029**: Existing account lookup MUST avoid duplicate users when the same eligible email is entered with different casing.
- **FR-030**: The system MUST ask every participant with no prize-pot answer whether they want to join the optional prize pot when they log in or return to the website.
- **FR-031**: The prize-pot notification MUST allow a participant to choose join or decline and MUST clearly state the EUR 10 contribution, that the prize amount is not yet final, and that Olivier Thijsen organizes payment outside the app.
- **FR-032**: The system MUST persist each participant's prize-pot choice as joined, declined, or undecided.
- **FR-033**: The system MUST stop showing the prize-pot prompt once the participant has saved joined or declined.
- **FR-034**: Participant profile views MUST show whether that participant joined the prize pot.
- **FR-035**: The app MUST NOT process, track, or reconcile actual prize-pot payments in this scope.
- **FR-036**: The prediction tournament-pick component MUST have a view mode and an explicit edit mode.
- **FR-037**: Clicking the tournament-pick component in view mode MUST NOT change champion, top-scorer, or striker selections.
- **FR-038**: The component MUST expose an edit button when tournament picks are still editable and MUST respect existing lock rules.
- **FR-039**: Champion picks MUST be shown with the team flag wherever the tournament-pick summary is displayed.
- **FR-040**: Top-scorer and striker picks MUST show full player names and country flag/country in view mode where metadata is available.
- **FR-041**: Top-scorer and striker pick storage/display MUST remain backwards compatible with existing plain-name predictions.

### Key Entities *(include if feature involves data)*

- **Provider**: An external football data source that can supply fixture, result, event, player-stat, and squad data.
- **Provider Match Link**: Mapping between an app match and the provider's fixture identifier. Missing links are exceptional and require admin notification.
- **Sync Attempt**: A scheduled or manually triggered attempt to retrieve provider data for one match or one squad target, including status and failure reason.
- **Raw Provider Snapshot**: Permanent copy of the provider payload received during a sync attempt.
- **Normalized Match Fact**: App-owned current result, event, player-stat, or label value derived from provider data or manual override.
- **Manual Override**: Admin-authored replacement for a scoring fact, with audit metadata and reversible status.
- **Computed Points**: Stored participant scoring output for a scored category, derived from predictions plus current eligible scoring facts.
- **Admin Notification**: Internal notice that a sync could not retrieve, link, or normalize required data.
- **Talpa Studios Account**: User account identified by a normalized `firstname.lastname@talpastudios.com` email address.
- **Prize Pot Participation**: Per-user opt-in state for the optional EUR 10 prize pot, with states `undecided`, `joined`, and `declined`.
- **Prize Pot Notification**: Participant-facing notification that asks undecided users whether to join or decline the prize pot.
- **Tournament Pick Summary**: View-mode presentation of champion, top-scorer, and striker picks with flags/country metadata and an explicit edit affordance.
- **Player Pick Metadata**: Optional player identity context used to render full name and country flag/country for top-scorer and striker picks while preserving plain-name fallback behavior.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a completed match with valid provider linkage, no unrelated match is requested during either scheduled post-match result sync attempt.
- **SC-002**: For a completed match with provider data available, current result facts are available for scoring after the first or second scheduled post-match sync attempt.
- **SC-003**: For a match with provider data corrected between sync attempts, provider-backed current facts reflect the newer data after the second attempt unless manually overridden.
- **SC-004**: 100% of manual override saves create an audit record containing actor, timestamp, previous value, and new value.
- **SC-005**: 100% of raw provider payloads received through sync attempts remain retrievable for audit.
- **SC-006**: Leaderboard and profile point totals match the same stored computed point records after a scoring recalculation.
- **SC-007**: When a provider fixture link is missing for a due match, normal participant views show no incorrect result and admins receive a notification.
- **SC-008**: 100% of newly created accounts use emails matching `firstname.lastname@talpastudios.com`.
- **SC-009**: An undecided participant receives the prize-pot notification on login/return and no longer receives it after choosing join or decline.
- **SC-010**: Profile views show each participant's saved prize-pot participation state.
- **SC-011**: In tournament pick view mode, champion, top-scorer, and striker summaries can be inspected without changing stored predictions.
- **SC-012**: Tournament pick summaries show flags for champion picks and full player name plus country flag/country for top-scorer and striker picks when metadata is available.

## Assumptions

- API-Football remains the initial provider, but the design should not embed provider-specific details into participant-facing code.
- Provider fixture links should normally exist before matches need result sync; missing links are treated as exceptional.
- Result sync timing is approximate because scheduler precision may vary, but the intent is one attempt near 15 minutes post-match and one near 2 hours post-match.
- "Match is done" means the app has enough trusted status information to consider result/label scoring eligible for participant-visible scoring.
- This spec does not add a user-facing freshness display, public scoring-source labels, user reports for incorrect labels, or a full admin sync dashboard unless later planning includes them as implementation details for admin notification.
- This spec does not remove the existing manual label editor goal from the current fixes work; it refines how provider-backed and manual scoring facts should interact.
- Talpa Studios is the required account domain for newly created participant accounts.
- Existing accounts from a previous Talpa email convention may require migration or compatibility handling during implementation.
- Prize-pot payment collection and reconciliation happen outside the app with Olivier Thijsen and are intentionally not modeled as payment state.
- Player country metadata should come from existing static/synced team profile or squad data where possible, with plain-name fallback when unavailable.
