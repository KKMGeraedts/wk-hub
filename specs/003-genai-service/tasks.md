# Tasks: GenAI Service

**Input**: Design documents from `/specs/003-genai-service/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Targeted backend coverage is required by `specs/003-genai-service/plan.md`.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare configuration and documentation surfaces for the GenAI Service.

- [X] T001 Add GenAI environment variable documentation for `GENAI_PROVIDER`, `MISTRAL_API_KEY`, `GENAI_MODEL`, and `GENAI_TIMEOUT_SECONDS` in `README.md`
- [X] T002 Verify `.gitignore` covers Python, Node, build output, and environment files for this Flask/Vite project in `.gitignore`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core GenAI storage and client boundaries that MUST be complete before any user story can be implemented.

**CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational Infrastructure

> Write these tests first and confirm they fail before implementation.

- [X] T003 [P] Add tests for GenAI configuration defaults, disabled state, and missing Mistral API key behavior in `backend/api_data_sync_test.py`
- [X] T004 [P] Add tests proving GenAI job result storage persists compact status/evidence but not full prompts or raw responses in `backend/api_data_sync_test.py`
- [X] T005 [P] Add tests for GenAI admin sync notification deduplication and resolution helpers in `backend/api_data_sync_test.py`

### Implementation

- [X] T006 Add GenAI constants, environment configuration helpers, provider enabled checks, and timeout parsing in `backend/app.py`
- [X] T007 Add SQLite schema for `genai_job_results`, `quiz_auto_labels`, and `player_candidate_links` in `backend/app.py`
- [X] T008 Add Postgres schema for `genai_job_results`, `quiz_auto_labels`, and `player_candidate_links` in `backend/app.py`
- [X] T009 Add SQLite/Postgres migration guards for new GenAI tables and columns in `backend/app.py`
- [X] T010 Implement compact GenAI job result persistence, input hashing, status updates, and lookup helpers in `backend/app.py`
- [X] T011 Implement provider-agnostic GenAI client boundary and Mistral HTTP helper with structured-output parsing and timeout handling in `backend/app.py`
- [X] T012 Implement shared GenAI failure notification helpers using `admin_sync_notifications` in `backend/app.py`
- [X] T013 Run foundational backend tests for GenAI configuration, compact result storage, and notification helpers with `.venv/bin/python -m unittest backend.api_data_sync_test`

**Checkpoint**: GenAI configuration, storage, client boundary, and notification primitives are ready for user-story implementation.

---

## Phase 3: User Story 1 - Answer Quiz From Match Facts (Priority: P1) MVP

**Goal**: Automatically answer match quiz questions from normalized match facts when the answer is evidence-backed, while preserving manual admin override precedence.

**Independent Test**: Sync/seed a completed match with normalized facts, run the quiz GenAI Job, and confirm a valid answer is accepted only when it matches an existing option and cites supplied match evidence.

### Tests for User Story 1

> Write these tests first and confirm they fail before implementation.

- [X] T014 [P] [US1] Add quiz GenAI accepted-output validation tests for option matching, high confidence, and supplied-fact evidence in `backend/api_data_sync_test.py`
- [X] T015 [P] [US1] Add quiz GenAI rejection tests for invalid JSON, outside-option answers, low confidence, unsupported status, and missing evidence in `backend/api_data_sync_test.py`
- [X] T016 [P] [US1] Add tests proving rejected quiz GenAI output creates one deduplicated admin sync issue and does not score participants in `backend/api_data_sync_test.py`
- [X] T017 [P] [US1] Add tests proving manual quiz override wins over a GenAI automatic label and participant `quiz_predictions` are not mutated in `backend/api_data_sync_test.py`
- [X] T018 [P] [US1] Add tests proving accepted GenAI quiz labels trigger computed quiz point recalculation in `backend/api_data_sync_test.py`

### Implementation for User Story 1

- [X] T019 [US1] Implement normalized match fact extraction for quiz GenAI inputs from `match_results`, `match_events`, `match_clean_sheets`, and `player_match_stats` in `backend/app.py`
- [X] T020 [US1] Implement quiz GenAI input construction using quiz question text, answer options, and compact normalized facts in `backend/app.py`
- [X] T021 [US1] Implement quiz GenAI output schema validation for selected answers, confidence, status, and evidence references in `backend/app.py`
- [X] T022 [US1] Implement `quiz_auto_labels` persistence for accepted `genai:mistral` labels below manual override precedence in `backend/app.py`
- [X] T023 [US1] Extend effective quiz label application so manual `quiz_label_overrides` win over GenAI automatic labels in `backend/app.py`
- [X] T024 [US1] Trigger computed point recalculation when an accepted GenAI quiz label changes the effective label in `backend/app.py`
- [X] T025 [US1] Create or update admin sync issues for rejected quiz GenAI outcomes and resolve them when the quiz becomes accepted or manually labeled in `backend/app.py`
- [X] T026 [US1] Add GenAI quiz source/status/evidence fields to admin label payloads in `backend/app.py`
- [X] T027 [US1] Render GenAI quiz status, source, confidence, evidence summary, and manual override precedence in the admin labels panel in `frontend/src/main.jsx`
- [X] T028 [US1] Add CSS for GenAI quiz status and evidence display in `frontend/src/styles.css`
- [X] T029 [US1] Run User Story 1 backend tests with `.venv/bin/python -m unittest backend.api_data_sync_test`

**Checkpoint**: User Story 1 is independently functional and can be reviewed through the admin label editor.

---

## Phase 4: User Story 2 - Match Players After Deterministic Matching Fails (Priority: P2)

**Goal**: Use a GenAI Job as the final fallback to link unresolved scorer/striker names to existing squad-player candidates without rewriting source names.

**Independent Test**: Create a scorer/striker name that deterministic matching rejects, provide a shortlist of existing player candidates, and confirm the GenAI Job either links to one candidate or notifies admins.

### Tests for User Story 2

> Write these tests first and confirm they fail before implementation.

- [X] T030 [P] [US2] Add tests proving player GenAI matching runs only after deterministic player-id/name/initial-surname matching fails in `backend/api_data_sync_test.py`
- [X] T031 [P] [US2] Add player GenAI accepted-output tests proving the matched candidate must exist in the supplied candidate list in `backend/api_data_sync_test.py`
- [X] T032 [P] [US2] Add player GenAI rejection tests for ambiguous, outside-candidate, no-match, low-confidence, and invalid output in `backend/api_data_sync_test.py`
- [X] T033 [P] [US2] Add tests proving accepted player candidate links preserve original scorer/striker names and do not mutate participant prediction rows in `backend/api_data_sync_test.py`
- [X] T034 [P] [US2] Add tests proving rejected player GenAI outcomes create deduplicated admin sync issues and accepted/manual fixes resolve them in `backend/api_data_sync_test.py`

### Implementation for User Story 2

- [X] T035 [US2] Implement squad-player candidate shortlist generation for unresolved scorer and striker targets in `backend/app.py`
- [X] T036 [US2] Implement player GenAI input construction with raw name, target context, and existing candidate list in `backend/app.py`
- [X] T037 [US2] Implement player GenAI output validation for matched candidate id, confidence, status, and evidence in `backend/app.py`
- [X] T038 [US2] Implement `player_candidate_links` persistence for accepted GenAI matches without rewriting `match_events`, `player_match_stats`, or `top_scorer_predictions` in `backend/app.py`
- [X] T039 [US2] Integrate accepted player candidate links into `player_matches_squad_database()` and `verify_player_database_matches()` in `backend/app.py`
- [X] T040 [US2] Update unresolved scorer and striker notification resolution to account for accepted GenAI player candidate links in `backend/app.py`
- [X] T041 [US2] Add GenAI player link status/evidence to admin label payloads for goal/scorer and player-stat inspection in `backend/app.py`
- [X] T042 [US2] Render GenAI player match status and original-name preservation in the admin labels panel in `frontend/src/main.jsx`
- [X] T043 [US2] Add CSS for GenAI player match status in `frontend/src/styles.css`
- [X] T044 [US2] Run User Story 2 backend tests with `.venv/bin/python -m unittest backend.api_data_sync_test`

**Checkpoint**: User Story 2 is independently functional and unresolved player matching remains admin-visible when GenAI cannot safely link a candidate.

---

## Phase 5: User Story 3 - Operate GenAI Safely (Priority: P3)

**Goal**: Make successful GenAI outcomes visible to admins, keep failures admin-only, and prove participant reads never trigger GenAI calls or writes.

**Independent Test**: Force one successful job and one failed or low-confidence job, then confirm admin review surfaces show the success while only the failure creates an active admin notification.

### Tests for User Story 3

> Write these tests first and confirm they fail before implementation.

- [X] T045 [P] [US3] Add tests proving participant `/api/world-cup`, `/api/pool`, and profile reads do not call the GenAI client or write GenAI result rows in `backend/api_data_sync_test.py`
- [X] T046 [P] [US3] Add tests proving successful GenAI outcomes are present in admin review payloads but do not create notification-bell items in `backend/api_data_sync_test.py`
- [X] T047 [P] [US3] Add tests proving GenAI provider disabled, timeout, and provider error states create admin-only notifications without participant details in `backend/api_data_sync_test.py`
- [ ] T048 [P] [US3] Add frontend coverage or build-safe rendering assertions for GenAI admin status payloads in `frontend/src/main.jsx`

### Implementation for User Story 3

- [X] T049 [US3] Add defensive guards so participant-facing routes cannot trigger GenAI jobs or GenAI writes in `backend/app.py`
- [X] T050 [US3] Ensure admin pool notifications include GenAI failure sync issues only for admin users in `backend/app.py`
- [X] T051 [US3] Add admin-facing GenAI provider/status summary to existing admin label or sync status payloads in `backend/app.py`
- [X] T052 [US3] Render GenAI failure notifications through existing notification bell styles without exposing provider internals to normal participants in `frontend/src/main.jsx`
- [X] T053 [US3] Add or adjust notification/status styles for GenAI failure severity in `frontend/src/styles.css`
- [X] T054 [US3] Run User Story 3 backend tests with `.venv/bin/python -m unittest backend.api_data_sync_test`

**Checkpoint**: User Story 3 is independently functional and GenAI operations are safe, visible, and participant-read-free.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and cleanup that affect multiple stories.

- [X] T055 Update GenAI operational documentation and quickstart notes in `README.md`
- [X] T056 Update `specs/003-genai-service/quickstart.md` with any finalized environment variable names or admin review paths discovered during implementation
- [X] T057 Review `specs/003-genai-service/contracts/api-and-ui-contract.md` against final payload shapes and update if needed
- [ ] T058 Run Python formatting and static checks with `npm run py:check`
- [ ] T059 Run frontend build with `npm run build`
- [ ] T060 Run full validation with `npm run check`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - blocks all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational completion - MVP scope
- **User Story 2 (Phase 4)**: Depends on Foundational completion; can be implemented independently after foundation, but benefits from shared GenAI helpers created for US1
- **User Story 3 (Phase 5)**: Depends on Foundational completion and should validate behavior across completed stories
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - no dependency on other stories
- **User Story 2 (P2)**: Can start after Foundational - no dependency on US1 domain behavior, only shared GenAI primitives
- **User Story 3 (P3)**: Can start after Foundational, but final validation should run after US1 and US2 are implemented

### Within Each User Story

- Tests MUST be written and fail before implementation
- Validation helpers before persistence
- Persistence before effective scoring or matching integration
- Backend payloads before frontend rendering
- Story checkpoint before moving to the next priority

### Parallel Opportunities

- Setup documentation tasks can be separated from backend foundation work
- Foundational test tasks T003-T005 can run in parallel
- US1 test tasks T014-T018 can run in parallel
- US2 test tasks T030-T034 can run in parallel
- US3 test tasks T045-T048 can run in parallel
- Frontend rendering tasks can run after backend payload shapes are defined

---

## Parallel Example: User Story 1

```bash
Task: "T014 [P] [US1] Add quiz GenAI accepted-output validation tests in backend/api_data_sync_test.py"
Task: "T015 [P] [US1] Add quiz GenAI rejection tests in backend/api_data_sync_test.py"
Task: "T016 [P] [US1] Add rejected-output notification tests in backend/api_data_sync_test.py"
Task: "T017 [P] [US1] Add manual override precedence tests in backend/api_data_sync_test.py"
Task: "T018 [P] [US1] Add computed point recalculation tests in backend/api_data_sync_test.py"
```

## Parallel Example: User Story 2

```bash
Task: "T030 [P] [US2] Add deterministic-fallback tests in backend/api_data_sync_test.py"
Task: "T031 [P] [US2] Add candidate-list validation tests in backend/api_data_sync_test.py"
Task: "T032 [P] [US2] Add rejected-output tests in backend/api_data_sync_test.py"
Task: "T033 [P] [US2] Add original-name preservation tests in backend/api_data_sync_test.py"
Task: "T034 [P] [US2] Add player notification lifecycle tests in backend/api_data_sync_test.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational GenAI configuration, storage, client, and notification primitives
3. Complete Phase 3: User Story 1 quiz answering
4. Stop and validate quiz GenAI behavior independently with backend tests and admin label payload review

### Incremental Delivery

1. Foundation ready
2. Add User Story 1 - quiz answer from match facts
3. Add User Story 2 - player match from candidates
4. Add User Story 3 - admin visibility and participant-read safety
5. Polish docs and run full validation

### Notes

- [P] tasks are marked only when they can be worked independently in different focus areas.
- Tasks touching `backend/app.py` should still be merged carefully because the backend is currently monolithic.
- Do not add a broad autonomous agent framework; keep GenAI Jobs bounded and validation-first.
- Do not store full prompts or raw model responses unless a later debug-mode feature changes the requirement.
- Existing dirty or unrelated workspace changes must not be reverted.
