# Tasks: Deep GenAI Service Module

**Input**: Design documents from `specs/003-genai-service/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/api-and-ui-contract.md`, `quickstart.md`

**Tests**: Characterization and integration tests are required because this is a behavior-preserving extraction and each user story defines an independent test.

**Organization**: Tasks are grouped by user story. Each story migrates one coherent behavior set behind the deep module interface and remains independently verifiable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it changes a different file and does not depend on incomplete work
- **[Story]**: Maps the task to a user story from `spec.md`
- Every task names the exact file it changes or validates

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the physical module and focused test location without changing runtime behavior.

- [ ] T001 Create the importable GenAI Service module scaffold and explicit public export list in `backend/genai_service.py`
- [ ] T002 [P] Create the focused unittest harness with temporary SQLite setup and deterministic structured-completion fake in `backend/genai_service_test.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Move cross-story configuration, provider invocation, result persistence, and failure lifecycle behind the deep module seam.

**⚠️ CRITICAL**: No user story migration begins until this phase passes focused tests.

- [ ] T003 Add characterization tests for disabled configuration, Mistral request shaping, timeout/error conversion, compact result retention, and absence of raw prompt/response persistence in `backend/genai_service_test.py`
- [ ] T004 Move GenAI constants, configuration parsing, canonical input hashing, structured response parsing, provider errors, and the private Mistral adapter from `backend/app.py` into `backend/genai_service.py`
- [ ] T005 Move compact GenAI Job Result persistence and GenAI-specific Admin Sync Issue create/deduplicate/resolve behavior from `backend/app.py` into `backend/genai_service.py`
- [ ] T006 Replace shared GenAI configuration and provider call sites with the module interface while preserving Flask initialization and generic notification behavior in `backend/app.py`
- [ ] T007 Run the focused foundational tests and fix only module-seam regressions in `backend/genai_service_test.py` and `backend/genai_service.py`

**Checkpoint**: Provider behavior and shared GenAI persistence execute through `backend.genai_service`; quiz and player workflows may now migrate independently.

---

## Phase 3: User Story 1 - Answer Quiz From Match Facts (Priority: P1) 🎯 MVP

**Goal**: Quiz Answer Jobs run through the deep module, publish only evidence-backed automatic Quiz Labels, and preserve manual-label precedence and scoring behavior.

**Independent Test**: Sync a completed match with normalized facts, inject accepted and rejected model outputs, and verify existing-option/evidence validation, automatic label publication, deduplicated admin work, recalculation metadata, and manual override precedence without mutating participant predictions.

### Tests for User Story 1

- [ ] T008 [P] [US1] Add module-level tests for minimal normalized quiz inputs, accepted-option validation, evidence validation, low-confidence rejection, and unsupported evidence in `backend/genai_service_test.py`
- [ ] T009 [P] [US1] Add Flask integration characterization tests for sync-triggered quiz execution, manual Quiz Label precedence, admin review, scoring recalculation, and unchanged participant predictions in `backend/api_data_sync_test.py`

### Implementation for User Story 1

- [ ] T010 [US1] Move Quiz Answer Job models, prompt construction, normalized fact input construction, and deterministic output validation from `backend/app.py` into `backend/genai_service.py`
- [ ] T011 [US1] Move GenAI Automatic Quiz Label persistence, effective-label application, review persistence, and unresolved-quiz Admin Sync Issue lifecycle from `backend/app.py` into `backend/genai_service.py`
- [ ] T012 [US1] Expose workflow-level quiz execution, automatic-label projection, and admin-review operations from `backend/genai_service.py` without exposing prompt, validator, or SQL helpers
- [ ] T013 [US1] Rewire data-sync orchestration, effective Quiz Label application, admin label projection, and `POST /api/admin/genai/quiz-reviews/<job_result_id>` to the deep module in `backend/app.py`
- [ ] T014 [US1] Remove migrated quiz GenAI definitions and update affected test imports from `backend.app` to `backend.genai_service` in `backend/app.py` and `backend/api_data_sync_test.py`
- [ ] T015 [US1] Run the US1 module and Flask integration scenarios and resolve parity failures in `backend/genai_service_test.py`, `backend/api_data_sync_test.py`, `backend/genai_service.py`, and `backend/app.py`

**Checkpoint**: User Story 1 works end-to-end through the deep module and is independently testable with the player workflow still unchanged.

---

## Phase 4: User Story 2 - Match Players After Deterministic Matching Fails (Priority: P2)

**Goal**: Player Matching Jobs run only after deterministic matching fails, select only supplied squad candidates, preserve original names, and publish accepted links through the deep module.

**Independent Test**: Seed an unmatched scorer or striker and a candidate shortlist, inject matched and ambiguous outputs, and verify deterministic-first ordering, candidate constraints, accepted links, source-name preservation, scoring use, and admin work for unresolved targets.

### Tests for User Story 2

- [ ] T016 [P] [US2] Add module-level tests for candidate shortlist construction, deterministic-failure eligibility, accepted candidate validation, ambiguity, outside-candidate rejection, and preserved raw names in `backend/genai_service_test.py`
- [ ] T017 [P] [US2] Add Flask integration characterization tests for scorer/striker job triggering, accepted-link scoring, and unresolved-player notification resolution in `backend/api_data_sync_test.py`

### Implementation for User Story 2

- [ ] T018 [US2] Move player-name normalization, deterministic match checks, candidate shortlist construction, Player Matching Job prompt construction, and output validation from `backend/app.py` into `backend/genai_service.py`
- [ ] T019 [US2] Move Player Candidate Link persistence, accepted-link projection, unresolved target discovery, player-job execution, and player-related Admin Sync Issue lifecycle from `backend/app.py` into `backend/genai_service.py`
- [ ] T020 [US2] Rewire post-sync player-job orchestration, player database verification, accepted scorer-link lookup, and scorer/striker scoring reads to the deep module in `backend/app.py`
- [ ] T021 [US2] Remove migrated player GenAI definitions and update affected test imports from `backend.app` to `backend.genai_service` in `backend/app.py` and `backend/api_data_sync_test.py`
- [ ] T022 [US2] Run the US2 module and Flask integration scenarios and resolve parity failures in `backend/genai_service_test.py`, `backend/api_data_sync_test.py`, `backend/genai_service.py`, and `backend/app.py`

**Checkpoint**: User Stories 1 and 2 execute independently through the deep module and retain their original persisted state and scoring effects.

---

## Phase 5: User Story 3 - Operate GenAI Safely (Priority: P3)

**Goal**: Admins retain compact success visibility and deduplicated failure notifications while participant-facing reads never invoke providers or create GenAI state.

**Independent Test**: Force accepted, rejected, disabled, and provider-failure outcomes, then verify compact admin projections, one active issue per target/type, issue resolution, hidden participant provider details, and zero provider calls or writes from participant reads.

### Tests for User Story 3

- [ ] T023 [P] [US3] Add module-level tests for compact status projections, provider detail handling, failure deduplication, successful issue resolution, and projection helpers that perform no provider calls in `backend/genai_service_test.py`
- [ ] T024 [P] [US3] Add Flask integration tests proving `/api/world-cup`, `/api/pool`, and profile reads perform zero provider calls and GenAI writes while admin label and notification payloads remain compatible in `backend/api_data_sync_test.py`

### Implementation for User Story 3

- [ ] T025 [US3] Move compact GenAI status summaries, Quiz Answer review payloads, player-link payloads, and admin projection helpers from `backend/app.py` into `backend/genai_service.py`
- [ ] T026 [US3] Rewire admin label and Admin Sync Issue payload construction to read through side-effect-free module projections while keeping authorization and Flask responses in `backend/app.py`
- [ ] T027 [US3] Remove remaining GenAI implementation details from `backend/app.py` so routes, sync, and scoring callers use only workflow-level operations exported by `backend/genai_service.py`
- [ ] T028 [US3] Run the US3 safety and compatibility scenarios and resolve parity failures in `backend/genai_service_test.py`, `backend/api_data_sync_test.py`, `backend/genai_service.py`, and `backend/app.py`

**Checkpoint**: All three user stories retain behavior while GenAI policy, provider handling, persistence, and projections have locality in one deep module.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Prove the extraction is complete, preserve quality gates, and synchronize documentation with the resulting interface.

- [ ] T029 [P] Update the implemented module ownership, public operations, and validation commands after extraction in `specs/003-genai-service/quickstart.md` and `specs/003-genai-service/contracts/api-and-ui-contract.md`
- [ ] T030 Apply the deletion test by removing forwarding aliases and confirming prompt, validator, provider, persistence, and job-orchestration definitions no longer exist in `backend/app.py`
- [ ] T031 Verify `backend/genai_service.py` does not import `backend.app`, exposes only workflow-level operations, and keeps Mistral details private in `backend/genai_service.py`
- [ ] T032 Run Black, Ruff, and mypy and fix findings in `backend/genai_service.py`, `backend/genai_service_test.py`, `backend/app.py`, and `backend/api_data_sync_test.py`
- [ ] T033 Run the full backend unittest suite and resolve regressions in `backend/genai_service_test.py`, `backend/api_data_sync_test.py`, `backend/genai_service.py`, and `backend/app.py`
- [ ] T034 Run the frontend production build and full repository check, confirming no HTTP/UI contract regressions in `frontend/src/main.jsx` and `specs/003-genai-service/contracts/api-and-ui-contract.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T001 and T002 can start together.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user story migrations.
- **User Story 1 (Phase 3)**: Depends on Foundational and establishes the MVP Quiz Answer Job path.
- **User Story 2 (Phase 4)**: Depends on Foundational; can be implemented in parallel with US1 after shared helpers stabilize, but sequential execution reduces conflicts in `backend/app.py` and `backend/genai_service.py`.
- **User Story 3 (Phase 5)**: Depends on Foundational and on the US1/US2 projections it consolidates.
- **Polish (Phase 6)**: Depends on all selected user stories.

### User Story Dependency Graph

```text
Setup → Foundational → US1 (P1) ─┐
                      US2 (P2) ─┼→ US3 (P3) → Polish
                                ┘
```

### Within Each User Story

- Write characterization and integration tests first and verify they pass against current behavior or fail only because the new module seam is absent.
- Move pure models, input construction, and validation before persistence and publication.
- Move persistence and workflow orchestration before rewiring Flask, sync, and scoring callers.
- Delete old definitions only after callers use the deep module.
- Complete the story checkpoint before proceeding to the next priority in a single-developer workflow.

### Parallel Opportunities

- T001 and T002 modify different new files.
- T008 and T009 cover US1 in different test files.
- T016 and T017 cover US2 in different test files.
- T023 and T024 cover US3 in different test files.
- US1 and US2 can proceed in parallel after Phase 2 when developers coordinate edits to `backend/app.py` and `backend/genai_service.py`.
- T029 can run alongside deletion-test preparation because it changes only feature documentation.

---

## Parallel Example: User Story 1

```text
Task T008: Add quiz module characterization tests in backend/genai_service_test.py
Task T009: Add quiz Flask integration characterization tests in backend/api_data_sync_test.py
```

## Parallel Example: User Story 2

```text
Task T016: Add player module characterization tests in backend/genai_service_test.py
Task T017: Add player Flask integration characterization tests in backend/api_data_sync_test.py
```

## Parallel Example: User Story 3

```text
Task T023: Add operational module tests in backend/genai_service_test.py
Task T024: Add participant-read and admin-payload integration tests in backend/api_data_sync_test.py
```

---

## Implementation Strategy

### MVP First: User Story 1

1. Complete Setup and Foundational phases.
2. Complete US1 characterization tests and extraction.
3. Validate quiz acceptance, rejection, manual precedence, and recalculation independently.
4. Stop with the Quiz Answer Job fully behind the deep module if incremental delivery is required.

### Incremental Delivery

1. Setup + Foundational → provider and compact persistence foundation.
2. US1 → evidence-backed Quiz Answer Jobs and manual precedence.
3. US2 → deterministic-first Player Matching Jobs and preserved source names.
4. US3 → consolidated admin visibility and participant-read isolation.
5. Polish → deletion test, static checks, full tests, and documentation parity.

### Safe Refactor Discipline

- Preserve persisted schemas and HTTP/UI payloads throughout.
- Avoid mixing feature changes with moved code.
- Keep commits small: characterization, move, rewire, delete, validate.
- Do not retain forwarding aliases after callers migrate; they would recreate shallow modules.
