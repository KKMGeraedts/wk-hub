# Tasks: WK Hub Fixes - Expanded Notification, Identity, Admin, and Accountability Scope

**Input**: Design documents from `specs/001-wk-hub-fixes/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: No test-first tasks were explicitly requested. Validation is via existing project checks and manual review scenarios in `quickstart.md`.

**Organization**: Prior US1-US5 work is already complete. This task list covers the expanded US6-US12 scope.

## Phase 1: Setup and Guardrails

**Purpose**: Confirm the executable scope and project hygiene before code changes.

- [x] T001 Review expanded plan, contracts, and clarified wall-of-shame window in `specs/001-wk-hub-fixes/plan.md`
- [x] T002 Verify Python and Node ignore patterns remain covered in `.gitignore`

---

## Phase 2: Foundational Backend Data and Helpers

**Purpose**: Add shared backend helpers and storage used by multiple stories.

**CRITICAL**: Complete before user-story UI integration.

- [x] T003 Add Talpa email parsing and derived real-name helpers in `backend/app.py`
- [x] T004 Add admin broadcast notification storage and migration setup in `backend/app.py`
- [x] T005 Extend quiz override storage/loading to support question and choices in `backend/app.py`
- [x] T006 Add reusable missing-action item builder for today/tomorrow unlocked predictions and quizzes in `backend/app.py`

---

## Phase 3: User Story 6 - Act on clear notification-bell actions (Priority: P1)

**Goal**: Notification-bell reminders identify the exact missing match/quiz and route users directly there.

**Independent Test**: Leave one unlocked match prediction or quiz empty, open the bell, click the item, and confirm the relevant prediction area is focused.

- [x] T007 [US6] Enrich notification payloads with actionable item metadata in `backend/app.py`
- [x] T008 [US6] Add frontend selected-match/selected-kind navigation state for prediction focus in `frontend/src/main.jsx`
- [x] T009 [US6] Render actionable notification rows and click handlers in `frontend/src/main.jsx`
- [x] T010 [US6] Add notification item and focus styles in `frontend/src/styles.css`

---

## Phase 4: User Story 10 - Restrict account emails to Talpa identity format (Priority: P1)

**Goal**: New accounts can only be created with `firstname.lastname@talpanetwork.com` emails.

**Independent Test**: Account creation accepts a valid Talpa email and rejects invalid formats/domains.

- [x] T011 [US10] Enforce Talpa email validation on account creation/login-upsert paths in `backend/app.py`
- [x] T012 [US10] Add auth-form validation hints and invalid-email messaging in `frontend/src/main.jsx`

---

## Phase 5: User Story 11 - Admins fully edit quiz questions and answer options (Priority: P1)

**Goal**: Admins can edit quiz question text, answer options, and correct labels without mutating participant predictions.

**Independent Test**: Edit quiz text/options/correct answer as admin and confirm prediction entry/scoring reflect overrides while `quiz_predictions` stays unchanged.

- [x] T013 [US11] Include quiz question and choices in admin label payloads in `backend/app.py`
- [x] T014 [US11] Accept and audit quiz question/choice overrides in admin quiz label API in `backend/app.py`
- [x] T015 [US11] Add admin quiz question and choice editing controls in `frontend/src/main.jsx`
- [x] T016 [US11] Add scrollable/selectable quiz option editor styles in `frontend/src/styles.css`

---

## Phase 6: User Story 7 - Admins broadcast messages through the notification bell (Priority: P2)

**Goal**: Admins send active broadcast messages from a third admin section and users see them in the bell.

**Independent Test**: Admin creates a broadcast, another user sees it in the bell, then admin deactivates it.

- [x] T017 [US7] Add admin broadcast list/create/deactivate APIs in `backend/app.py`
- [x] T018 [US7] Merge active broadcasts into pool-state notifications in `backend/app.py`
- [x] T019 [US7] Add admin send-message section and broadcast controls in `frontend/src/main.jsx`
- [x] T020 [US7] Add broadcast notification/admin message styles in `frontend/src/styles.css`

---

## Phase 7: User Story 8 - Show real names subtly on the leaderboard (Priority: P2)

**Goal**: Leaderboard rows show nickname prominently and derived first/last name as subtle supporting text.

**Independent Test**: A row for `jane.doe@talpanetwork.com` with nickname `MVP` shows `MVP` primary and `Jane Doe` secondary.

- [x] T021 [US8] Add derived real-name fields to leaderboard/user payloads in `backend/app.py`
- [x] T022 [US8] Render subtle derived full name in leaderboard rows in `frontend/src/main.jsx`
- [x] T023 [US8] Add responsive leaderboard real-name styles in `frontend/src/styles.css`

---

## Phase 8: User Story 9 - Preview profile pictures from the leaderboard (Priority: P3)

**Goal**: Users can hover or focus leaderboard avatars to inspect a larger profile picture without navigating.

**Independent Test**: Hover/focus a leaderboard avatar and confirm a larger preview appears without row layout shift.

- [x] T024 [US9] Add leaderboard avatar preview markup in `frontend/src/main.jsx`
- [x] T025 [US9] Add hover/focus avatar preview styles in `frontend/src/styles.css`

---

## Phase 9: User Story 12 - Show a wall of shame for missing open predictions (Priority: P2)

**Goal**: Show active users with currently open missing predictions/quizzes for today and tomorrow.

**Independent Test**: User A with missing today/tomorrow actions appears; User B with complete actions does not; archived users are excluded.

- [x] T026 [US12] Add wall-of-shame payload using today/tomorrow missing-action helpers in `backend/app.py`
- [x] T027 [US12] Render wall-of-shame section in leaderboard view in `frontend/src/main.jsx`
- [x] T028 [US12] Add wall-of-shame responsive styles in `frontend/src/styles.css`

---

## Phase 10: Polish and Validation

**Purpose**: Validate the expanded implementation and update traceability.

- [x] T029 Run frontend build with `npm run build`
- [ ] T030 Run Python quality checks with `npm run py:check`
- [ ] T031 Run combined validation with `npm run check` if prior checks pass
- [x] T032 Update completed task checkboxes in `specs/001-wk-hub-fixes/tasks.md`

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Blocks all user stories.
- **US6, US10, US11**: Highest priority after foundation.
- **US7 and US12**: Depend on notification/missing-action foundation.
- **US8 and US9**: Depend on leaderboard payload/rendering surfaces and can be implemented after backend identity helpers.
- **Polish**: Runs after all implementation phases.

## Parallel Opportunities

- T012 can be reviewed separately from backend email validation once T011 defines the server error contract.
- T015-T016 are frontend-only after T013-T014 define payload shape.
- T022-T025 are CSS/JS leaderboard enhancements and can be reviewed together.
- T027-T028 are frontend-only after T026 adds the payload.

## Implementation Strategy

1. Complete backend foundations T003-T006.
2. Complete P1 flows T007-T016.
3. Add admin broadcasts and accountability surfaces T017-T028.
4. Run validation T029-T031 and mark tasks complete.
