# Tasks: API Data Sync

**Input**: Design documents from `specs/002-api-data-sync/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/api-and-ui-contract.md`, `quickstart.md`

**Tests**: Targeted backend tests are included because the implementation plan requires coverage for sync candidate selection, manual-override precedence, and computed point persistence. Use Python `unittest` to avoid new dependencies.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently after the foundational phase.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare validation and identify the current sync/scoring surfaces before changing behavior.

- [X] T001 Add a `py:test` script using `python3 -m unittest discover backend -p '*_test.py'` and include it in `check` in `package.json`
- [X] T002 [P] Create backend test package marker in `backend/__init__.py`
- [X] T003 [P] Add API data sync test skeleton and helpers in `backend/api_data_sync_test.py`
- [X] T004 [P] Document the current API-Football sync entry points and scoring read paths in `specs/002-api-data-sync/quickstart.md`
- [X] T005 Verify ignore coverage for Python/Node artifacts in `.gitignore`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add shared schema and backend boundaries that all user stories depend on.

**CRITICAL**: No user story work should begin until these tasks are complete.

- [X] T006 Add provider sync constants for provider key, attempt kinds, target types, and statuses in `backend/app.py`
- [X] T007 Add SQLite schema for `provider_sync_attempts`, `computed_points`, and `admin_sync_notifications` in `backend/app.py`
- [X] T008 Add Postgres schema for `provider_sync_attempts`, `computed_points`, and `admin_sync_notifications` in `backend/app.py`
- [X] T009 Add migration/backfill guards for new provider sync tables and computed point tables in `backend/app.py`
- [X] T010 Add new tables to `DB_BACKUP_TABLES` in `backend/app.py`
- [X] T011 Add provider boundary helper functions for sync attempt creation, status updates, and terminal lookup in `backend/app.py`
- [X] T012 Add provider boundary helper functions for admin sync notification creation, deduplication, and resolution in `backend/app.py`
- [X] T013 Add provider boundary helper functions for computed point upsert, deletion by scope, and lookup in `backend/app.py`
- [X] T014 Add unit tests for schema-independent sync attempt scheduling helpers in `backend/api_data_sync_test.py`

**Checkpoint**: Schema and helper boundaries exist; user-story work can proceed.

---

## Phase 3: User Story 1 - Retrieve only relevant post-match data (Priority: P1) MVP

**Goal**: Result sync requests only matches whose first or second post-match attempt is due.

**Independent Test**: Mark one match as due while other matches are future, already attempted, or outside their window; confirm only the due match is selected and requested.

### Tests for User Story 1

- [X] T015 [P] [US1] Add tests for first post-match due-match selection in `backend/api_data_sync_test.py`
- [X] T016 [P] [US1] Add tests for second post-match due-match selection after partial first attempt in `backend/api_data_sync_test.py`
- [X] T017 [P] [US1] Add tests proving already terminal attempts and unrelated completed matches are not selected in `backend/api_data_sync_test.py`
- [X] T018 [P] [US1] Add tests for `POST /api/admin/api-football/sync` with `match_id`, `dry_run`, and omitted `match_id` compatibility in `backend/api_data_sync_test.py`

### Implementation for User Story 1

- [X] T019 [US1] Replace broad completed-match candidate selection with two-window per-match sync candidate selection in `backend/app.py`
- [X] T020 [US1] Update `run_api_football_completed_sync()` to record one sync attempt per due match in `backend/app.py`
- [X] T021 [US1] Update `run_api_football_completed_sync()` to fetch provider fixtures only for linked due matches in `backend/app.py`
- [X] T022 [US1] Add `match_id` handling and dry-run candidate reporting to `/api/admin/api-football/sync` in `backend/app.py`
- [X] T023 [US1] Update `/api/cron/api-football-sync` response shape to report attempts and skipped due candidates in `backend/app.py`
- [X] T024 [US1] Remove reliance on the app-managed daily request limit for candidate selection while preserving provider error reporting in `backend/app.py`
- [X] T025 [US1] Update result sync examples in `README.md`

**Checkpoint**: User Story 1 is independently testable: due result sync targets only the relevant match.

---

## Phase 4: User Story 2 - Keep external data behind a clear boundary (Priority: P1)

**Goal**: Provider-specific retrieval, normalization, and scoring publication are isolated from participant-facing routes.

**Independent Test**: Review participant routes and tests to confirm they read app-owned data and do not call provider retrieval helpers.

### Tests for User Story 2

- [X] T026 [P] [US2] Add tests proving `load_world_cup_data()`, `/api/pool`, and profile prediction routes do not call provider retrieval helpers in `backend/api_data_sync_test.py`
- [X] T027 [P] [US2] Add tests for provider normalization publishing app-owned current facts from a fixture payload in `backend/api_data_sync_test.py`

### Implementation for User Story 2

- [X] T028 [US2] Group provider adapter helpers under a clear API-Football provider boundary section in `backend/app.py`
- [X] T029 [US2] Group provider-agnostic sync orchestration helpers under a separate boundary section in `backend/app.py`
- [X] T030 [US2] Rename or wrap provider-specific status data so participant-facing payloads use app-owned result/profile fields in `backend/app.py`
- [X] T031 [US2] Ensure `/api/world-cup`, `/api/pool`, and `/api/profiles/<profile_user_id>/predictions` do not call provider retrieval helpers in `backend/app.py`
- [X] T032 [US2] Update internal comments and README sync overview to describe the provider boundary in `backend/app.py` and `README.md`

**Checkpoint**: User Story 2 is independently testable: participant views are decoupled from provider retrieval.

---

## Phase 5: User Story 3 - Preserve data history while using current facts for scoring (Priority: P2)

**Goal**: Raw provider snapshots remain permanent, current facts update from provider data, and manual overrides win until reversed.

**Independent Test**: Run two syncs for the same match, then add/reverse a manual override and verify raw history, current facts, and audit records.

### Tests for User Story 3

- [X] T033 [P] [US3] Add tests confirming every successful fixture sync inserts raw snapshot history in `backend/api_data_sync_test.py`
- [X] T034 [P] [US3] Add tests confirming newer provider-backed facts update current result/event/stat rows when no manual override exists in `backend/api_data_sync_test.py`
- [X] T035 [P] [US3] Add tests confirming provider updates do not overwrite manual result, event, or player-stat facts in `backend/api_data_sync_test.py`
- [X] T036 [P] [US3] Add tests for manual override reversal restoring provider-backed facts in `backend/api_data_sync_test.py`
- [X] T037 [P] [US3] Add tests confirming label audit rows include actor, previous value, new value, source, and reason metadata in `backend/api_data_sync_test.py`

### Implementation for User Story 3

- [X] T038 [US3] Extend current fact rows or companion metadata to distinguish provider-backed, manual, and reverted sources in `backend/app.py`
- [X] T039 [US3] Update fixture snapshot storage to record sync attempt references and preserve raw history permanently in `backend/app.py`
- [X] T040 [US3] Update result normalization so partial provider data is stored without requiring complete event/stat data in `backend/app.py`
- [X] T041 [US3] Update event and player-stat normalization so provider-backed rows are replaced only when no active manual rows exist in `backend/app.py`
- [X] T042 [US3] Add manual override reversal helpers for result, quiz, event, and player-stat labels in `backend/app.py`
- [X] T043 [US3] Extend admin label audit payloads with source and optional reason metadata in `backend/app.py`
- [X] T044 [US3] Add admin label API support for clearing/reversing manual overrides in `backend/app.py`
- [X] T045 [US3] Add frontend admin label controls for reversing manual overrides in `frontend/src/main.jsx`
- [X] T046 [US3] Add styles for manual override and reversal states in `frontend/src/styles.css`

**Checkpoint**: User Story 3 is independently testable: history is permanent and manual overrides win until reversed.

---

## Phase 6: User Story 4 - Score from stored computed points (Priority: P2)

**Goal**: Scoring fact changes update stored computed point rows, and leaderboard/profile reads agree.

**Independent Test**: Sync or manually correct a done match, then confirm computed rows update and leaderboard/profile totals read the same values.

### Tests for User Story 4

- [X] T047 [P] [US4] Add tests for computed match-score and Leeuwtje point persistence after result fact changes in `backend/api_data_sync_test.py`
- [X] T048 [P] [US4] Add tests for computed quiz point persistence after quiz label changes in `backend/api_data_sync_test.py`
- [X] T049 [P] [US4] Add tests for computed top-scorer and striker point persistence after event/stat changes in `backend/api_data_sync_test.py`
- [X] T050 [P] [US4] Add tests proving manual labels do not affect participant-visible scoring before a match is done in `backend/api_data_sync_test.py`
- [X] T051 [P] [US4] Add tests proving leaderboard and profile totals read the same computed point rows in `backend/api_data_sync_test.py`

### Implementation for User Story 4

- [X] T052 [US4] Implement computed point recalculation for match score and Leeuwtje categories in `backend/app.py`
- [X] T053 [US4] Implement computed point recalculation for quiz categories in `backend/app.py`
- [X] T054 [US4] Implement computed point recalculation for top scorer and striker categories in `backend/app.py`
- [X] T055 [US4] Trigger affected computed point recalculation after provider-backed fact changes for done matches in `backend/app.py`
- [X] T056 [US4] Trigger affected computed point recalculation after manual override save or reversal for done matches in `backend/app.py`
- [X] T057 [US4] Update leaderboard construction to read stored computed point rows with fallback for not-yet-computed categories in `backend/app.py`
- [X] T058 [US4] Update profile prediction/detail scoring to read stored computed point rows with fallback for not-yet-computed categories in `backend/app.py`
- [X] T059 [US4] Add backfill helper to compute points for already completed matches in `backend/app.py`

**Checkpoint**: User Story 4 is independently testable: leaderboard and profile scoring agree from stored computed rows.

---

## Phase 7: User Story 5 - Notify admins when data cannot be retrieved or linked (Priority: P2)

**Goal**: Missing fixture links and provider retrieval failures create admin-only notifications while normal users see pending/blank results.

**Independent Test**: Make a due match lack a fixture link or fail retrieval; confirm admin notification exists and participant routes expose no provider error details.

### Tests for User Story 5

- [X] T060 [P] [US5] Add tests for missing fixture link sync attempts creating admin notifications in `backend/api_data_sync_test.py`
- [X] T061 [P] [US5] Add tests for provider request failures creating admin notifications in `backend/api_data_sync_test.py`
- [X] T062 [P] [US5] Add tests proving normal participant pool/world-cup payloads hide provider failure details in `backend/api_data_sync_test.py`
- [X] T063 [P] [US5] Add tests proving admin users receive active sync issue notifications in pool state in `backend/api_data_sync_test.py`

### Implementation for User Story 5

- [X] T064 [US5] Record failed or skipped sync attempts for missing fixture links in `backend/app.py`
- [X] T065 [US5] Record failed sync attempts for provider request and normalization errors in `backend/app.py`
- [X] T066 [US5] Create deduplicated admin sync notifications for missing links and failed due-match retrievals in `backend/app.py`
- [X] T067 [US5] Include active sync issue notifications for admins only in `user_pool_state()` in `backend/app.py`
- [X] T068 [US5] Ensure participant `/api/world-cup` and `/api/pool` payloads show blank/pending result state without provider failure details in `backend/app.py`
- [X] T069 [US5] Add admin-facing sync issue rendering in the existing notification bell in `frontend/src/main.jsx`
- [X] T070 [US5] Add notification styles for sync issue severity in `frontend/src/styles.css`

**Checkpoint**: User Story 5 is independently testable: admins see sync issues, participants do not see provider internals.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, documentation, and cleanup across all stories.

- [X] T071 [P] Update production cron and sync behavior documentation in `README.md`
- [X] T072 [P] Update manual review instructions in `specs/002-api-data-sync/quickstart.md`
- [X] T073 Run `python3 -m unittest discover backend -p '*_test.py'` and fix failures in `backend/app.py` or `backend/api_data_sync_test.py`
- [X] T074 Run `npm run py:check` and fix Python formatting, lint, and type issues in `backend/app.py`
- [X] T075 Run `npm run build` and fix frontend build issues in `frontend/src/main.jsx` or `frontend/src/styles.css`
- [X] T076 Run `npm run check` and fix remaining validation issues
- [X] T077 Review `specs/002-api-data-sync/quickstart.md` scenarios against implemented behavior and note any intentionally deferred scope

---

## Phase 9: Participant Experience Scope Expansion

**Purpose**: Implement the 2026-06-11 additions for Talpa account validation, prize-pot participation, and view-first tournament pick display.

- [X] T078 [US6] Update backend and frontend email validation/copy for `firstname.lastname@talpanetwork.com` and `firstname.lastname@talpastudios.com` account creation in `backend/app.py` and `frontend/src/main.jsx`
- [X] T079 [US7] Add persistent prize-pot participation state, authenticated save endpoint, pool notification, and profile payload support in `backend/app.py`
- [X] T080 [US7] Add prize-pot notification actions and profile status rendering in `frontend/src/main.jsx` and `frontend/src/styles.css`
- [X] T081 [US8] Add view-first tournament pick summary with explicit edit mode for prediction entry and adjustment in `frontend/src/main.jsx`
- [X] T082 [US8] Add richer champion/top-scorer/striker display styling and profile flag/country rendering in `frontend/src/main.jsx` and `frontend/src/styles.css`
- [X] T083 Run backend/frontend validation for the participant experience scope and fix issues

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: No dependencies.
- **Phase 2 Foundational**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 US1**: Depends on Phase 2. This is the MVP.
- **Phase 4 US2**: Depends on Phase 2 and can run alongside US1 after shared helpers exist, but should be validated before broader stories.
- **Phase 5 US3**: Depends on Phase 2 and benefits from US2 provider boundary names.
- **Phase 6 US4**: Depends on Phase 2 and uses current facts from US3 where manual overrides are involved.
- **Phase 7 US5**: Depends on Phase 2 and uses sync attempts from US1.
- **Phase 8 Polish**: Depends on all desired user stories.

### User Story Dependencies

- **US1 Retrieve only relevant post-match data**: MVP; no dependency on other stories after foundation.
- **US2 Keep external data behind a clear boundary**: Independent after foundation; should be completed before large follow-on refactors.
- **US3 Preserve data history while using current facts for scoring**: Independent for provider/manual fact behavior, but uses provider boundary helpers.
- **US4 Score from stored computed points**: Depends on computed point foundations and scoring fact change hooks.
- **US5 Notify admins when data cannot be retrieved or linked**: Depends on sync attempt records and notification helpers.

### Parallel Opportunities

- T002, T003, T004, and T005 can run in parallel.
- US1 tests T015 through T018 can run in parallel.
- US2 tests T026 and T027 can run in parallel.
- US3 tests T033 through T037 can run in parallel.
- US4 tests T047 through T051 can run in parallel.
- US5 tests T060 through T063 can run in parallel.
- Documentation tasks T071 and T072 can run in parallel.

## Parallel Example: User Story 1

```text
Task: "T015 [P] [US1] Add tests for first post-match due-match selection in backend/api_data_sync_test.py"
Task: "T016 [P] [US1] Add tests for second post-match due-match selection after partial first attempt in backend/api_data_sync_test.py"
Task: "T017 [P] [US1] Add tests proving already terminal attempts and unrelated completed matches are not selected in backend/api_data_sync_test.py"
Task: "T018 [P] [US1] Add tests for POST /api/admin/api-football/sync with match_id, dry_run, and omitted match_id compatibility in backend/api_data_sync_test.py"
```

## Parallel Example: User Story 3

```text
Task: "T033 [P] [US3] Add tests confirming every successful fixture sync inserts raw snapshot history in backend/api_data_sync_test.py"
Task: "T034 [P] [US3] Add tests confirming newer provider-backed facts update current result/event/stat rows when no manual override exists in backend/api_data_sync_test.py"
Task: "T035 [P] [US3] Add tests confirming provider updates do not overwrite manual result, event, or player-stat facts in backend/api_data_sync_test.py"
Task: "T036 [P] [US3] Add tests for manual override reversal restoring provider-backed facts in backend/api_data_sync_test.py"
Task: "T037 [P] [US3] Add tests confirming label audit rows include actor, previous value, new value, source, and reason metadata in backend/api_data_sync_test.py"
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3, User Story 1.
3. Validate that the sync selects and fetches only due matches.
4. Stop for review before adding stored points and admin notification behavior if needed.

### Incremental Delivery

1. Foundation: schema, sync attempt helpers, admin notification helpers, computed point helpers.
2. US1: per-match post-match result sync.
3. US2: provider boundary and participant-route decoupling.
4. US3: raw history and manual override precedence/reversal.
5. US4: stored computed scoring.
6. US5: admin-only sync issue notifications.
7. Polish: full validation and docs.

### Validation Commands

```bash
python3 -m unittest discover backend -p '*_test.py'
npm run py:check
npm run build
npm run check
```
