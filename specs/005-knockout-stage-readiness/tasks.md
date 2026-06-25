# Tasks: Knockout Stage Readiness

**Input**: Design documents from `specs/005-knockout-stage-readiness/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/api-and-ui-contract.md`, `quickstart.md`

**Tests**: No dedicated test-first workflow was requested. Validation tasks are included in the final phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish feature scaffolding and shared terminology.

- [X] T001 Confirm `AGENTS.md` points to `specs/005-knockout-stage-readiness/plan.md`
- [X] T002 [P] Review existing knockout match data in `backend/worldcup-2026.json` and document any placeholder anomalies in `specs/005-knockout-stage-readiness/quickstart.md`
- [X] T003 [P] Review existing quiz/admin label behavior in `backend/app.py` for matches without quiz entries

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add shared backend/frontend concepts that every user story depends on.

**CRITICAL**: No user story work should begin until this phase is complete.

- [X] T004 Add backend helper functions for identifying Knockout Stage matches and Bracket Slot labels in `backend/app.py`
- [X] T005 Add backend helper for Knockout Stage match status values in `backend/app.py`
- [X] T006 Add backend helper for knockout-scoped personal Missing Actions without changing today/tomorrow notification helpers in `backend/app.py`
- [X] T007 Add frontend route constants and route parsing for `/knockout` in `frontend/src/main.jsx`
- [X] T008 Add shared frontend utilities for knockout rounds, tile labels, and selected-match lookup in `frontend/src/main.jsx`
- [X] T009 Add baseline responsive style primitives for the Knockout Page in `frontend/src/styles.css`

**Checkpoint**: Backend can project knockout data and frontend can route to a placeholder Knockout Page.

---

## Phase 3: User Story 1 - Navigate the Knockout Stage bracket (Priority: P1) MVP

**Goal**: Participants can open a dedicated visual Knockout Page and inspect all 32 Knockout Stage matches.

**Independent Test**: Open `/knockout` with unresolved and partially resolved knockout data; verify all rounds render as a bracket and selecting tiles opens useful details.

### Implementation for User Story 1

- [X] T010 [US1] Add `knockout` projection to the authenticated pool payload in `backend/app.py`
- [X] T011 [US1] Create the `KnockoutPage` component and route rendering branch in `frontend/src/main.jsx`
- [X] T012 [US1] Render all 32 Knockout Match Tiles by round/path in `frontend/src/main.jsx`
- [X] T013 [US1] Render known teams and Bracket Slots inside Knockout Match Tiles in `frontend/src/main.jsx`
- [X] T014 [US1] Add selectable tile state and a match detail panel or bottom sheet in `frontend/src/main.jsx`
- [X] T015 [US1] Style the desktop bracket as a visually converging Knockout Stage layout in `frontend/src/styles.css`
- [X] T016 [US1] Style mobile bracket navigation and the selected-match detail panel in `frontend/src/styles.css`

**Checkpoint**: User Story 1 is independently usable as a bracket viewer.

---

## Phase 4: User Story 2 - Complete my open knockout predictions (Priority: P1)

**Goal**: Participants can see and complete their own open knockout score and quiz Missing Actions.

**Independent Test**: Make a known-team knockout match open, leave score/quiz empty, complete them from `/knockout`, and verify the page updates.

### Implementation for User Story 2

- [X] T017 [US2] Extend the knockout projection with participant prediction, quiz prediction, Leeuwtje, lock, and Missing Action state in `backend/app.py`
- [X] T018 [US2] Reuse the existing prediction save endpoint for selected knockout match detail saves in `frontend/src/main.jsx`
- [X] T019 [US2] Add score prediction controls to the selected knockout match detail panel in `frontend/src/main.jsx`
- [X] T020 [US2] Add quiz answer controls and "Quiz question not set yet" state to the selected knockout match detail panel in `frontend/src/main.jsx`
- [X] T021 [US2] Add Leeuwtje display/toggle behavior for open knockout matches in `frontend/src/main.jsx`
- [X] T022 [US2] Update tile and detail states after successful save without a full page reload in `frontend/src/main.jsx`
- [X] T023 [US2] Preserve existing today/tomorrow notification and wall-of-shame scope in `backend/app.py`
- [X] T024 [US2] Replace the obsolete knockout draw guardrail with explicit Prediction Result and Advancing Team handling in `backend/app.py`
- [X] T042 Add additive `match_results` fields for Advancing Team, Match Decision Method, provider score evidence, extra-time score evidence, and penalty score evidence in `backend/app.py`
- [X] T043 Resolve group-position and prior-match Bracket Slots in loaded tournament data without persisting resolved teams in `backend/app.py`
- [X] T044 Surface unresolved bracket slot blockers as admin-only Admin Sync Issues in `backend/app.py`
- [X] T045 Add admin manual Advancing Team correction controls for Knockout Stage results in `frontend/src/main.jsx`

**Checkpoint**: User Story 2 is independently usable for personal knockout prediction work.

---

## Phase 5: User Story 3 - Set knockout quiz questions (Priority: P1)

**Goal**: Admins can set and correct Quiz Questions for Knockout Stage matches without source-code changes.

**Independent Test**: Admin creates a quiz for a knockout match with no quiz entry; participant sees and answers it from `/knockout`.

### Implementation for User Story 3

- [X] T025 [US3] Extend admin quiz payloads to include Knockout Stage matches without existing quiz entries in `backend/app.py`
- [X] T026 [US3] Extend admin quiz update behavior to create Quiz Questions for matches that currently have none in `backend/app.py`
- [X] T027 [US3] Preserve audit/reason handling for Quiz Setup and Quiz Correction in `backend/app.py`
- [X] T028 [US3] Apply pre-lock Quiz Correction invalidation rules for participant answers in `backend/app.py`
- [X] T029 [US3] Ensure post-lock Quiz Correction does not automatically reopen participant answers in `backend/app.py`
- [X] T030 [US3] Update the admin quiz/labels UI to show unset knockout quiz state and setup controls in `frontend/src/main.jsx`
- [X] T031 [US3] Add admin styles for unset quiz setup and correction states in `frontend/src/styles.css`

**Checkpoint**: User Story 3 is independently usable for admin-owned knockout Quiz Setup.

---

## Phase 6: User Story 4 - Route users to knockout work at the right time (Priority: P2)

**Goal**: Participants can discover the Knockout Page and My Predictions routes to knockout work when relevant.

**Independent Test**: Simulate Knockout Stage relevance, verify nav shows `Knockout`, and click My Predictions with and without urgent knockout work.

### Implementation for User Story 4

- [X] T032 [US4] Add backend `knockout.is_relevant` semantics to the pool payload in `backend/app.py`
- [X] T033 [US4] Add the top-level `Knockout` navigation item when relevant in `frontend/src/main.jsx`
- [X] T034 [US4] Update My Predictions routing to open `/knockout` when Knockout Stage planning is relevant in `frontend/src/main.jsx`
- [X] T035 [US4] Add selected-match focus behavior when routing to the first urgent knockout Missing Action in `frontend/src/main.jsx`

**Checkpoint**: User Story 4 is independently usable for navigation and routing.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validate behavior and finish quality checks.

- [X] T036 [P] Verify `CONTEXT.md` terminology matches implementation labels and update only glossary terms if needed
- [X] T037 [P] Run `npm run build` and fix frontend build issues
- [X] T038 [P] Run `npm run py:check` and fix backend formatting/lint/type issues
- [X] T039 [P] Run `npm run py:test` and fix backend regressions
- [X] T040 Run `npm run check` and record results in `specs/005-knockout-stage-readiness/quickstart.md`
- [ ] T041 Validate quickstart participant, admin, correction, and navigation scenarios from `specs/005-knockout-stage-readiness/quickstart.md`
- [ ] T042 Review the Knockout Page at mobile and desktop viewport sizes and adjust `frontend/src/styles.css` for text overlap or unusable controls

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories
- **US1 (Phase 3)**: Depends on Foundational; MVP bracket viewer
- **US2 (Phase 4)**: Depends on US1 selected-tile/detail structure
- **US3 (Phase 5)**: Depends on Foundational; can proceed in parallel with US1/US2 after shared payload expectations are stable
- **US4 (Phase 6)**: Depends on US1 and backend relevance semantics
- **Polish (Phase 7)**: Depends on desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: First MVP slice after Foundational
- **User Story 2 (P1)**: Requires US1 detail panel structure
- **User Story 3 (P1)**: Can proceed after Foundational, but participant visibility is demonstrated best with US1/US2
- **User Story 4 (P2)**: Requires Knockout Page route and relevance semantics

### Parallel Opportunities

- T002 and T003 can run in parallel.
- T004, T005, T006 can be split after backend data shape is agreed.
- T007, T008, T009 can run in parallel with backend helpers.
- US3 backend admin tasks can proceed while US1 frontend bracket work is underway.
- Final validation tasks T037, T038, and T039 can run independently before T040.

---

## Parallel Example: User Story 1

```text
Task: "Render all 32 Knockout Match Tiles by round/path in frontend/src/main.jsx"
Task: "Style the desktop bracket as a visually converging Knockout Stage layout in frontend/src/styles.css"
Task: "Style mobile bracket navigation and the selected-match detail panel in frontend/src/styles.css"
```

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational phases.
2. Complete User Story 1 to ship a useful bracket viewer.
3. Add User Story 2 to make the bracket actionable for participants.
4. Add User Story 3 so admins can prepare knockout quizzes.
5. Add User Story 4 for navigation polish.

### Guardrails

- Do not add public group accountability or wall-of-shame content to the Knockout Page.
- Do not broaden urgent notifications beyond current/next matchday.
- Do not implement advancing-team prediction behavior until the open product decision is resolved.
- Keep score prediction available even when quiz setup is missing.
