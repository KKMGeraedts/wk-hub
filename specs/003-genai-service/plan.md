# Implementation Plan: Deep GenAI Service Module

**Branch**: `main` | **Date**: 2026-06-22 | **Spec**: `specs/003-genai-service/spec.md`

**Input**: Feature specification from `specs/003-genai-service/spec.md` plus the selected architecture candidate “Concentrate the GenAI Service”.

## Summary

Preserve the implemented GenAI feature behavior while moving its policy out of the 11,246-line Flask monolith into one deep backend module. `backend/genai_service.py` will own GenAI Job input construction, provider invocation, deterministic validation, compact persistence, automatic Quiz Label and player-link publication, and Admin Sync Issue lifecycle. `backend/app.py` will retain Flask routes, database initialization, scoring, and provider-data sync, and will call the module only at explicit sync, admin-review, scoring-publication, and read-projection seams.

## Technical Context

**Language/Version**: Python 3.12; JavaScript/React 19; Vite 7

**Primary Dependencies**: Flask 3.1.1, psycopg 3.2.13, Pydantic 2.x, Python standard-library HTTP client, React, React DOM, Vite

**Storage**: Existing SQLite local / Postgres production schema, including `genai_job_results`, `quiz_auto_labels`, `quiz_genai_reviews`, `player_candidate_links`, `admin_sync_notifications`, normalized match-fact tables, and manual `quiz_label_overrides`; no migration is required for this refactor

**Testing**: Python `unittest` with provider-call fakes and temporary SQLite integration tests; existing `npm run build`, `npm run py:check`, `npm run py:test`, and `npm run check`

**Target Platform**: Flask running locally and as a Vercel serverless Python entry point; Vite static frontend

**Project Type**: Full-stack web application with a Flask backend and React frontend

**Performance Goals**: Preserve current request and sync behavior; add no participant-read provider calls; perform no additional database round trips beyond those required by current GenAI workflows; retain configured provider timeout behavior

**Constraints**: Preserve all existing endpoints and payload shapes; preserve manual Quiz Label precedence; fail closed on provider or validation errors; keep raw provider payloads, participant data, identity data, full prompts, and raw model responses out of GenAI persistence and provider inputs; avoid circular imports from `backend/genai_service.py` back to `backend/app.py`

**Scale/Scope**: Extract approximately 2,000 lines of cohesive GenAI behavior from `backend/app.py`; preserve two GenAI Jobs, one Mistral adapter, admin review, sync triggers, scoring integration, and current SQLite/Postgres behavior

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution is an unfilled template and defines no enforceable project-specific gates. The following feature and architecture gates apply:

- Feature spec exists and contains no `NEEDS CLARIFICATION` markers: PASS
- ADR-0001 minimal normalized input rule remains enforced inside the deep module: PASS
- ADR-0002 evidence validation remains enforced before Quiz Label publication: PASS
- Participant-facing reads remain free of GenAI provider calls and writes: PASS
- Manual Quiz Labels remain authoritative over automatic labels: PASS
- Existing endpoint and admin payload contracts remain compatible: PASS
- Provider-specific implementation is localized without introducing a framework: PASS
- Module interface is smaller than the implementation it hides: PASS
- No new persistence entity or schema migration is introduced by the refactor: PASS

Post-design re-check:

- Research resolves module ownership, dependency direction, extraction sequence, and test strategy: PASS
- Data model assigns existing entity invariants to the deep module without changing storage: PASS
- Contract defines the module seam and preserves external HTTP/UI behavior: PASS
- Quickstart verifies parity, failure handling, participant-read isolation, and import direction: PASS

## Project Structure

### Documentation (this feature)

```text
specs/003-genai-service/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── api-and-ui-contract.md
├── tasks.md
└── checklists/
    ├── requirements.md
    └── genai.md
```

### Source Code (repository root)

```text
backend/
├── app.py                    # Flask routes, DB initialization, scoring, provider-data sync
├── genai_service.py          # Deep GenAI Service module and Mistral adapter
├── genai_service_test.py     # Interface-focused unit and SQLite integration tests
├── api_data_sync_test.py     # Existing end-to-end regression tests
├── quiz-2026.json
├── team-profiles-2026.json
└── worldcup-2026.json

api/
└── index.py                  # Vercel entry point; unchanged import of backend.app

frontend/
└── src/
    └── main.jsx              # Existing admin and participant UI; no structural change
```

**Structure Decision**: Add one physical module, `backend/genai_service.py`, rather than a package of shallow modules. Its implementation owns GenAI Job policy and persistence. `backend/app.py` supplies a database connection, app-owned match data, configuration, and explicit callbacks only where app-owned scoring behavior must run. The Mistral adapter remains private to the module; tests inject a deterministic completion callable. This maximizes locality without creating multiple pass-through modules.

## Module Ownership

`backend/genai_service.py` owns:

- GenAI configuration interpretation and provider dispatch
- Pydantic job input/output models and prompt construction
- minimal normalized Quiz Answer Job and Player Matching Job inputs
- deterministic output, confidence, option, candidate, and evidence validation
- compact GenAI Job Result, automatic Quiz Label, review, and player-link persistence
- GenAI-related Admin Sync Issue creation, deduplication, and resolution
- orchestration of jobs after data sync
- admin-review mutation and admin/scoring projection helpers

`backend/app.py` retains:

- database connection and cross-database schema initialization
- normalized provider-data ingestion
- Flask authentication, authorization, routing, and response construction
- scoring algorithms and computed-point orchestration
- participant-facing payload construction

Dependency direction is one-way: `backend.app` imports `backend.genai_service`; `backend.genai_service` must not import `backend.app`.

## Extraction Strategy

1. Add characterization tests around the current external seam: sync-triggered jobs, admin review, manual override precedence, accepted player links, failure notification deduplication, and participant reads.
2. Introduce `backend/genai_service.py` with the existing GenAI implementation moved without behavior changes; keep public entry points narrow and internal helpers private.
3. Inject provider completion into the module so tests use a deterministic adapter and production uses the private Mistral adapter.
4. Replace direct GenAI helper calls in sync, scoring, and admin routes with module entry points.
5. Remove moved definitions from `backend/app.py`; run the deletion test to ensure GenAI policy does not reappear across callers.
6. Run focused tests, full backend checks, frontend build, and complete repository checks.

## Complexity Tracking

No constitution violations require justification.
