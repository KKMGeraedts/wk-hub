# Research: WK Hub Fixes

## Decision 1: Use existing lock semantics as the source of truth

**Decision**: Tournament-pick lock and reveal should use the app's existing tournament start lock calculation: 1 hour before the first scheduled tournament match. Per-match prediction visibility should use each match's existing prediction lock calculation.

**Rationale**: The requested business rule matches the existing lock language used by participants. Reusing the same lock moments avoids divergent privacy/editability behavior.

**Alternatives considered**:

- Hardcode 11 June as a separate reveal timestamp: rejected because the schedule data already defines the first match and hardcoding creates drift risk.
- Reveal only after match kickoff: rejected because the user explicitly requested visibility when predictions are no longer adjustable, 1 hour before kickoff.

## Decision 2: Treat tournament pick privacy as backend-enforced masking

**Decision**: Hidden champion, top scorer, and striker names must not be included in response data for other participants before reveal. Frontend display rules are secondary UX safeguards.

**Rationale**: UI-only hiding would still expose private picks to anyone inspecting network responses. Privacy must be enforced at the data returned for leaderboard/profile surfaces.

**Alternatives considered**:

- Hide only in the frontend: rejected due to privacy leakage.
- Hide all leaderboard rows before reveal: rejected because the requested secrecy is limited to tournament-pick and not general ranking visibility.

## Decision 3: Keep leaderboard focused on ranking, move detailed tournament pick reveal to profile/detail surfaces

**Decision**: Remove top scorer and striker names from leaderboard display. Do not rely on leaderboard tournament-pick columns for revealing detailed picks; profile/detail surfaces handle that after reveal.

**Rationale**: The user explicitly said top scorer/striker display is awkward and may be removed. Keeping detailed picks out of the leaderboard also reduces privacy risk.

**Alternatives considered**:

- Keep names hidden until reveal, then show in leaderboard: rejected because it preserves the clutter the user wants removed.
- Remove all scorer-related information, including points: left for implementation judgment based on current leaderboard readability, but pick names must be removed.

## Decision 4: Treat account creation as leaderboard eligibility

**Decision**: Every account user should be included in leaderboard construction immediately. Prediction completion, including any old Netherlands group/tutorial requirement and tournament picks, should remain progress metadata only and must not filter leaderboard rows or normal app access.

**Rationale**: The user explicitly identified the missing-new-account behavior as a remnant of the previous tutorial phase. Account creation is the current participation boundary, and hiding users with incomplete predictions makes the app appear broken.

**Alternatives considered**:

- Keep requiring Netherlands group predictions before leaderboard inclusion: rejected because this is the legacy behavior being removed.
- Require champion/top scorer/striker picks before leaderboard inclusion: rejected because tournament picks are optional for access and may remain incomplete until lock.
- Frontend-only insertion of the current user into the leaderboard: rejected because other participants also need to see newly joined users, and ranking/points should stay backend-authored.

## Decision 5: Use a searchable custom player picker rather than native grouped select

**Decision**: Replace long native player selects with searchable controls supporting player-name and team-name filtering, duplicate-striker prevention, clearing, and locked disabled state.

**Rationale**: Native selects with many grouped options are hard to search and do not give enough control over duplicate handling or empty-result messaging.

**Alternatives considered**:

- Browser datalist: rejected because duplicate disabling, grouped metadata, and consistent UX are harder to control.
- External component dependency: rejected unless implementation reveals a strong need; the project currently has no UI component dependency.

## Decision 6: Keep data model unchanged

**Decision**: No database schema changes are required. Privacy and display behavior can be derived from existing prediction rows, user identity, and lock times.

**Rationale**: The feature changes visibility, editability enforcement, and UI controls, not the persisted prediction concepts.

**Alternatives considered**:

- Add reveal-state columns: rejected because reveal state is deterministic from match schedule and current time.
- Add audit tables: rejected because prediction audit logging already exists for saves.

## Decision 7: Profile and tutorial fixes are navigation/layout refinements

**Decision**: Profile readability and tutorial navigation changes should be handled as UI state and copy/layout refinements without changing authentication rules. Tutorial copy and routing should be updated so it no longer presents prediction completion as required for leaderboard inclusion.

**Rationale**: The requested issues are about where users land, which links are active in tutorial, and how text flows.

**Alternatives considered**:

- Add new onboarding persistence state: rejected unless implementation discovers current routing cannot reliably infer the required flow.
