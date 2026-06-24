# Tasks: Matchday Recap Updates

**Input**: Design documents from `specs/004-matchday-recap-updates/`

**Prerequisites**: `spec.md`, `checklists/requirements.md`, current app plan in `specs/003-genai-service/plan.md`

**Tests**: Focused backend tests are required for scoring projections, matchday payloads, and recap consistency. Frontend validation is covered by production build and manual UI checks.

**Organization**: Tasks are grouped by user story so each change can be validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it changes a different file and does not depend on incomplete work
- **[Story]**: Maps the task to a user story from `spec.md`
- Every task names the exact file it changes or validates

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm feature context, preserve existing work, and establish focused test coverage points.

- [X] T001 Review existing schedule, matchday, leaderboard, and recap code paths in `frontend/src/main.jsx`, `frontend/src/styles.css`, and `backend/app.py`
- [X] T002 [P] Review existing backend regression tests for matchday and recap behavior in `backend/api_data_sync_test.py`
- [X] T003 Confirm unrelated working-tree changes are preserved in `frontend/src/main.jsx` and `backend/genai_service.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add shared backend helpers and payload fields needed by multiple stories.

**⚠️ CRITICAL**: Complete this phase before frontend story work, because UI changes depend on backend payloads.

- [ ] T004 Add a single-match point breakdown helper that avoids full tournament recomputation in `backend/app.py`
- [ ] T005 Add viewer personal prediction and personal points payloads to matchday summary/detail data in `backend/app.py`
- [ ] T006 Add backend regression tests for matchday personal prediction and detail personal summary payloads in `backend/api_data_sync_test.py`

**Checkpoint**: Matchday APIs expose enough data for the UI and can compute selected-match points without per-user full-tournament loops.

---

## Phase 3: User Story 1 - Read the schedule in matchday order (Priority: P1) 🎯 MVP

**Goal**: Schedule starts with the current matchday, then historic matchdays newest-to-oldest, then future matchdays oldest-to-newest.

**Independent Test**: Load a schedule with current, past, and future matches and verify grouped ordering.

### Implementation for User Story 1

- [ ] T007 [US1] Reorder schedule groups by app matchday key in `frontend/src/main.jsx`
- [ ] T008 [US1] Ensure schedule headings preserve readable date labels for current, historic, and future groups in `frontend/src/main.jsx`

**Checkpoint**: User Story 1 is independently testable from the schedule page.

---

## Phase 4: User Story 3 - Review my matchday prediction and points at a glance (Priority: P1)

**Goal**: Completed matchday overview and locked match detail show result, viewer prediction, and clickable point breakdowns.

**Independent Test**: Open matchday overview and a locked match detail for a completed match with a viewer prediction and points.

### Implementation for User Story 3

- [ ] T009 [US3] Render result, viewer prediction, and clickable personal points on completed matchday overview cards in `frontend/src/main.jsx`
- [ ] T010 [US3] Render viewer result, prediction, and clickable personal points near the locked match detail header in `frontend/src/main.jsx`
- [ ] T011 [US3] Add responsive styles for matchday personal scoring summaries in `frontend/src/styles.css`
- [ ] T012 [US3] Update post-save matchday pool patching to preserve new personal prediction fields in `frontend/src/main.jsx`

**Checkpoint**: User Story 3 is independently testable from the matchday tab and a locked match route.

---

## Phase 5: User Story 4 - Open locked match prediction detail quickly (Priority: P1)

**Goal**: Locked match detail computes prediction point rows efficiently while preserving payload accuracy.

**Independent Test**: Backend test verifies the detail payload for multiple users and point categories without calling full match-point recomputation once per prediction.

### Implementation for User Story 4

- [ ] T013 [US4] Refactor `matchday_match_detail` to batch-load selected match predictions and use the single-match point helper in `backend/app.py`
- [ ] T014 [US4] Add match-scoped database indexes for prediction, quiz, Leeuwtje, and top-scorer lookups in `backend/app.py`
- [ ] T015 [US4] Add regression coverage for selected-match point accuracy after the refactor in `backend/api_data_sync_test.py`

**Checkpoint**: User Story 4 keeps the same visible data while removing per-prediction tournament-wide point recomputation.

---

## Phase 6: User Story 5 - Trust the daily recap winners and losers (Priority: P1)

**Goal**: Daily recap day score and winners/losers share the same matchday baseline.

**Independent Test**: Build a recap where supplied overall leaderboard movement conflicts with matchday movement and confirm matchday movement wins.

### Implementation for User Story 5

- [ ] T016 [US5] Make daily recap rank movement always compare standings before and after the recap matchday in `backend/app.py`
- [ ] T017 [US5] Replace conflicting supplied-leaderboard movement test with matchday-baseline tests in `backend/api_data_sync_test.py`
- [ ] T018 [US5] Include full day-score rows and target date metadata in daily recap payload in `backend/app.py`

**Checkpoint**: User Story 5 is independently testable through backend recap tests and the existing recap board.

---

## Phase 7: User Story 6 - Inspect the full day score (Priority: P2)

**Goal**: Daily recap has a clear action that opens a modal with every active participant and one expandable per-player per-match breakdown.

**Independent Test**: Click the day-score action and verify all active participants appear, including zero-point participants, with one expanded breakdown at a time.

### Implementation for User Story 6

- [ ] T019 [US6] Add all active participants and per-match day-score breakdowns to recap payload in `backend/app.py`
- [ ] T020 [US6] Add the day-score modal, header action, one-open-row behavior, and point breakdown rendering in `frontend/src/main.jsx`
- [ ] T021 [US6] Add responsive modal and day-score detail styles in `frontend/src/styles.css`
- [ ] T022 [US6] Add backend regression tests for all-active-player day-score rows, zero-point participants, and per-match breakdowns in `backend/api_data_sync_test.py`

**Checkpoint**: User Story 6 is independently testable from the home page daily recap.

---

## Phase 8: User Story 2 - See leaderboard completeness without orange warning colors (Priority: P2)

**Goal**: Remove orange missing-prediction highlight and legend while keeping prediction completeness visible.

**Independent Test**: View leaderboard rows with incomplete predictions and confirm no orange highlight or legend remains.

### Implementation for User Story 2

- [ ] T023 [US2] Remove missing-prediction legend and row highlight class usage from leaderboard markup in `frontend/src/main.jsx`
- [ ] T024 [US2] Remove unused missing-prediction highlight styles from `frontend/src/styles.css`

**Checkpoint**: User Story 2 is independently testable from the leaderboard page.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Validate the integrated feature and keep documentation aligned.

- [ ] T025 Run focused backend tests for matchday and recap scenarios with `npm run py:test`
- [ ] T026 Run frontend production build with `npm run build`
- [ ] T027 Run full repository check with `npm run check`
- [ ] T028 Update completed task checkboxes in `specs/004-matchday-recap-updates/tasks.md`
- [ ] T029 Review final diffs for unrelated changes and preserve existing user edits in `frontend/src/main.jsx` and `backend/genai_service.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks matchday UI work.
- **US1 Schedule (Phase 3)**: Can start after Setup.
- **US3 Matchday personal summary (Phase 4)**: Depends on Foundational.
- **US4 Matchday performance (Phase 5)**: Depends on Foundational.
- **US5 Recap consistency (Phase 6)**: Can start after Setup.
- **US6 Full day score (Phase 7)**: Depends on US5 recap payload decisions.
- **US2 Leaderboard color removal (Phase 8)**: Can start after Setup.
- **Polish (Phase 9)**: Depends on all implemented user stories.

### User Story Dependency Graph

```text
Setup ─┬→ US1 Schedule
       ├→ US2 Leaderboard color removal
       ├→ Foundational → US3 Matchday personal summary
       │               └→ US4 Matchday performance
       └→ US5 Recap consistency → US6 Full day score

All selected stories → Polish
```

### Parallel Opportunities

- T001 and T002 can run in parallel.
- US1, US2, and US5 can proceed independently after Setup.
- US3 and US4 both depend on T004/T005 but can be implemented in either order.
- CSS-only tasks T011, T021, and T024 can run after corresponding markup decisions.

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational phases.
2. Complete US1, US3, US4, and US5 because they cover the P1 user-facing and correctness issues.
3. Validate backend tests and frontend build.

### Incremental Delivery

1. Schedule ordering and leaderboard color removal are low-risk frontend-only increments.
2. Matchday personal summaries require backend payload additions before frontend rendering.
3. Matchday detail performance should be verified with backend regression tests before UI polish.
4. Recap consistency should land before full day-score modal because the modal uses the same recap data.
