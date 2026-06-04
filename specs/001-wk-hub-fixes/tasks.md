# Tasks: WK Hub Fixes

**Input**: Design documents from `specs/001-wk-hub-fixes/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: No test-first tasks were explicitly requested in the specification. Validation is via existing project checks and manual review scenarios in `quickstart.md`.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm feature context and preserve Spec Kit traceability.

- [x] T001 Review approved decisions in `specs/001-wk-hub-fixes/plan.md`
- [x] T002 Review API/UI contracts in `specs/001-wk-hub-fixes/contracts/api-and-ui-contract.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared lock/reveal metadata and privacy helpers required by all stories.

**⚠️ CRITICAL**: No user story work should begin until this phase is complete.

- [x] T003 Add tournament-pick lock/reveal helper aliases in `backend/app.py`
- [x] T004 Add tournament-pick visibility metadata to pool state in `backend/app.py`
- [x] T005 Update frontend lock/visibility helper functions in `frontend/src/main.jsx`

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Protect prediction secrecy until lock times (Priority: P1) 🎯 MVP

**Goal**: Tournament picks and match predictions from other participants remain hidden until their approved lock moments, with backend-side privacy enforcement.

**Independent Test**: Compare what User A sees for own predictions versus User B's predictions before/after tournament and match lock moments.

### Implementation for User Story 1

- [x] T006 [US1] Pass viewer context and current time into leaderboard construction in `backend/app.py`
- [x] T007 [US1] Mask other users' champion/topscorer/striker fields before tournament reveal in `backend/app.py`
- [x] T008 [US1] Update tournament-pick edit lock validation to use tournament helper names in `backend/app.py`
- [x] T009 [US1] Change profile prediction visibility from match-result-complete to match-lock-time in `backend/app.py`
- [x] T010 [US1] Add frontend profile tournament-pick privacy display using pool visibility metadata in `frontend/src/main.jsx`
- [x] T011 [US1] Ensure hidden tournament picks are not rendered for other profiles before reveal in `frontend/src/main.jsx`

**Checkpoint**: User Story 1 should be fully functional and testable independently.

---

## Phase 4: User Story 2 - Choose tournament scorers easily and freely (Priority: P2)

**Goal**: Participants can search all available players by player/team name for top scorer and striker picks, independent of champion selection.

**Independent Test**: Choose one champion team, search and save a top scorer from another team, search by team/player, and verify duplicate strikers are prevented.

### Implementation for User Story 2

- [x] T012 [US2] Add reusable searchable player picker components in `frontend/src/main.jsx`
- [x] T013 [US2] Replace top scorer native select in initial prediction flow in `frontend/src/main.jsx`
- [x] T014 [US2] Replace striker native selects in initial prediction flow in `frontend/src/main.jsx`
- [x] T015 [US2] Replace top scorer and striker native selects in adjust prediction flow in `frontend/src/main.jsx`
- [x] T016 [US2] Preserve/label saved scorer values not present in current option list in `frontend/src/main.jsx`
- [x] T017 [US2] Add searchable picker styles and locked/empty states in `frontend/src/styles.css`

**Checkpoint**: User Story 2 should be independently usable after User Story 1 foundation.

---

## Phase 5: User Story 3 - Use leaderboard and profile pages without confusing navigation or layout (Priority: P3)

**Goal**: Tutorial, leaderboard, and profile pages have clear navigation and readable layout.

**Independent Test**: Tutorial leaderboard preview has no profile links; completing onboarding reaches leaderboard; normal leaderboard avatar/name opens profile; profile text remains readable.

### Implementation for User Story 3

- [x] T018 [US3] Add `profileLinksEnabled` behavior to leaderboard rendering in `frontend/src/main.jsx`
- [x] T019 [US3] Disable leaderboard profile links in tutorial preview in `frontend/src/main.jsx`
- [x] T020 [US3] Make avatar and player name a combined profile link in normal leaderboard in `frontend/src/main.jsx`
- [x] T021 [US3] Remove top scorer and striker name columns from leaderboard in `frontend/src/main.jsx`
- [x] T022 [US3] Remove profile-specific Back to leaderboard control in `frontend/src/main.jsx`
- [x] T023 [US3] Ensure onboarding continue flow routes to leaderboard in `frontend/src/main.jsx`
- [x] T024 [US3] Improve profile and leaderboard link layout styles in `frontend/src/styles.css`
- [x] T025 [US3] Improve profile text wrapping and responsive layout styles in `frontend/src/styles.css`

**Checkpoint**: User Story 3 should be independently reviewable after implementation.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and traceability cleanup.

- [x] T026 Run frontend build with `npm run build`
- [x] T027 Run Python quality checks with `npm run py:check`
- [x] T028 Run combined validation with `npm run check` if prior checks pass
- [x] T029 Update completed task checkboxes in `specs/001-wk-hub-fixes/tasks.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; MVP privacy story.
- **User Story 2 (Phase 4)**: Depends on Foundational; can be worked after or alongside US1 frontend review.
- **User Story 3 (Phase 5)**: Depends on Foundational; can be worked after or alongside US2 because it is mostly UI cleanup.
- **Polish (Phase 6)**: Depends on all implemented stories.

### User Story Dependencies

- **US1**: Required for privacy correctness and MVP.
- **US2**: Independent of US3, but uses shared tournament lock metadata from foundation.
- **US3**: Independent of US2, but uses leaderboard/profile surfaces touched by US1.

### Parallel Opportunities

- T006-T009 are backend-only and can be reviewed separately from T010-T011 frontend privacy display.
- T012-T017 are scorer picker tasks concentrated in `frontend/src/main.jsx` and `frontend/src/styles.css`; avoid concurrent edits to the same file.
- T024-T025 are CSS-only after JSX structure settles.

## Implementation Strategy

### MVP First

1. Complete T001-T005.
2. Complete US1 privacy tasks T006-T011.
3. Validate backend data masking and match-lock visibility manually.

### Incremental Delivery

1. Add searchable scorer picker (US2).
2. Add leaderboard/tutorial/profile cleanup (US3).
3. Run automated checks and manual scenarios.
