# Implementation Plan: API Data Sync

**Branch**: `main` | **Date**: 2026-06-10 | **Spec**: `specs/002-api-data-sync/spec.md`

**Input**: Feature specification from `specs/002-api-data-sync/spec.md`

**Note**: This plan stops before implementation. Generate and review `tasks.md` before running implementation.

## Summary

Create a clearer internal boundary for external football data sync while keeping the current Flask/Vite application shape. Result sync will become a provider-backed, per-match workflow with two post-match attempts: approximately 15 minutes and 2 hours after each match. Squad sync stays separate and rare. Provider payloads remain permanently auditable, normalized current facts feed scoring, manual overrides win over provider data, and affected computed points are stored after scoring facts change.

## Technical Context

**Language/Version**: Python 3.12; JavaScript/React 19; Vite 7

**Primary Dependencies**: Flask 3.1.1, psycopg 3.2.13, React, React DOM, Vite

**Storage**: Existing SQLite local / Postgres production tables. Existing provider and scoring-label tables include `api_football_*`, `match_results`, `match_events`, `match_clean_sheets`, `player_match_stats`, `quiz_label_overrides`, and `label_audit_log`. New storage is planned for provider-agnostic sync attempts, admin sync notifications, and stored computed points.

**Testing**: Existing project checks via `npm run build`, `npm run py:check`, and `npm run check`; targeted Python unit/integration coverage should be added for sync candidate selection, manual-override precedence, and computed point persistence.

**Target Platform**: Web app running locally via Flask/Vite and production via Vercel serverless Python plus Vite static frontend

**Project Type**: Full-stack web application with monolithic Flask backend and single-file React frontend

**Performance Goals**: Result sync requests only due matches and never re-fetches unrelated history; leaderboard/profile reads should use stored computed points for scored categories without noticeable extra overhead.

**Constraints**: Preserve participant prediction data; keep provider calls out of normal participant views; preserve permanent raw provider history; manual overrides must not be overwritten by provider updates; avoid new dependencies unless clearly justified.

**Scale/Scope**: Existing 2026 World Cup tournament data, post-match result sync, rare squad sync, admin label/editor flows, scoring labels, leaderboard/profile scoring output, and admin notification-bell infrastructure.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The current constitution file is still a placeholder and defines no enforceable project-specific gates. General Spec Kit gates apply:

- Feature spec exists and has no unresolved `[NEEDS CLARIFICATION]` markers: PASS
- Requirements quality checklist exists and is complete: PASS
- Plan avoids implementation before task generation: PASS
- No known privacy/security violation introduced by design: PASS
- Provider data and manual override updates are explicitly barred from mutating participant prediction rows: PASS

Post-design re-check:

- Research decisions resolve technical unknowns: PASS
- Data model identifies new and existing entities: PASS
- Contracts define sync, admin notification, and computed scoring behavior: PASS
- Quickstart defines validation and manual review paths: PASS

## Project Structure

### Documentation (this feature)

```text
specs/002-api-data-sync/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── api-and-ui-contract.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
backend/
├── app.py                  # Current monolith: routes, DB setup, scoring, provider sync
├── worldcup-2026.json      # Static match schedule and lock timing source
├── quiz-2026.json          # Static quiz fallback data
└── team-profiles-2026.json # Static/synced team profile fallback data

api/
└── index.py                # Vercel Flask entry point

frontend/
├── index.html
└── src/
    ├── main.jsx            # Admin UI, notifications, leaderboard/profile reads
    └── styles.css

specs/002-api-data-sync/
└── ...                     # Feature planning artifacts
```

**Structure Decision**: Keep the current monolithic backend for implementation scope, but introduce clearer internal service/function boundaries inside `backend/app.py` first. Extraction into separate backend modules can be considered during implementation only if it reduces risk and keeps imports simple for Vercel packaging. Frontend changes should be limited to admin notifications/status surfaces needed by this feature.

## Complexity Tracking

This feature intentionally adds data-model complexity for sync attempts and stored computed points.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Provider-agnostic sync attempt records | Needed to model per-match attempts, failure notifications, and future provider support | Continuing only with `api_football_requests` records provider calls but not app-level scheduling, attempt windows, or skipped/missing-link outcomes |
| Stored computed points | Needed for consistent leaderboard/profile reads and auditability after manual/provider facts change | Recomputing all points on every read makes source/fact interactions harder to audit and can produce inconsistent views during changes |

## Phase 0: Research Summary

Research output: `specs/002-api-data-sync/research.md`

Key decisions:

- Keep provider calls out of normal participant requests.
- Introduce a provider boundary inside the backend before considering physical module extraction.
- Model result sync as scheduled per-match attempt windows rather than a broad completed-history scan.
- Keep squad sync separate and rare.
- Retain raw provider payloads permanently and use normalized current facts for scoring.
- Represent manual overrides as source-prioritized current facts with audit history and reversal.
- Store computed points for scored categories and recompute only affected users/categories when facts change.
- Notify admins through existing notification-bell infrastructure when sync cannot retrieve or link data.

## Phase 1: Design Summary

Design outputs:

- `specs/002-api-data-sync/data-model.md`
- `specs/002-api-data-sync/contracts/api-and-ui-contract.md`
- `specs/002-api-data-sync/quickstart.md`

Design notes:

- Existing `api_football_*` tables remain valid provider-specific inputs and raw history, but the new planning layer should not expose API-Football naming to participant-facing code.
- `match_results`, `match_events`, `match_clean_sheets`, `player_match_stats`, and `quiz_label_overrides` continue as current facts, with source metadata strengthened where needed.
- New sync attempt records track due windows, attempt status, provider, target type, match/team id, and failure reason.
- Computed point records store category-level scoring output with source fact revision metadata.
- Admin notifications should be generated for missing provider links and failed due-match retrievals; normal users should only see blank/pending results.

## Validation Strategy

Automated validation after implementation:

```bash
npm run build
npm run py:check
npm run check
```

Manual review scenarios are documented in `specs/002-api-data-sync/quickstart.md`.
