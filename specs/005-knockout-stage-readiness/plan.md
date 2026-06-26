# Implementation Plan: Knockout Stage Readiness

**Branch**: `005-knockout-stage-readiness` | **Date**: 2026-06-24 | **Spec**: `specs/005-knockout-stage-readiness/spec.md`

**Input**: Feature specification from `specs/005-knockout-stage-readiness/spec.md`

## Summary

Add a participant-facing Knockout Page that renders the Knockout Stage as an interactive bracket, exposes personal knockout Missing Actions through selectable Knockout Match Tiles, lets admins complete Quiz Setup for knockout matches without code deployment, and supports Knockout Stage score predictions through maximum 120 minutes with Advancing Team selection for predicted draws. Reuse existing quiz, lock-time, admin label, Leeuwtje, and scoring concepts while making leaderboard point breakdowns derivable from visible columns.

## Technical Context

**Language/Version**: Python 3.12; JavaScript/React 19; Vite 7

**Primary Dependencies**: Flask 3.1.1, psycopg 3.2.13, React, React DOM, Vite; no new runtime dependency planned

**Storage**: Existing SQLite local / Postgres production schema, including match predictions, quiz predictions, quiz label overrides, static tournament data, and existing audit tables; likely requires extending quiz persistence or admin quiz override behavior for creating quizzes where none exist

**Testing**: Python `unittest`; existing `npm run build`, `npm run py:check`, `npm run py:test`, and `npm run check`

**Target Platform**: Flask running locally and as a Vercel serverless Python entry point; Vite static frontend

**Project Type**: Full-stack web application with a Flask backend and React frontend

**Performance Goals**: Load the 32-match bracket within the existing pool-state request budget; no additional provider calls from participant reads; bracket interaction must be client-local after initial data load except prediction/admin saves

**Constraints**: Preserve existing group-stage prediction flow; preserve today/tomorrow urgent notification and wall-of-shame scope; Knockout Stage outcome scoring uses Advancing Team while penalties never add score goals; avoid adding a new frontend framework or visualization dependency

**Scale/Scope**: One new participant page, admin quiz setup extension, 32 Knockout Stage matches, existing pool participant count, responsive desktop/mobile UI

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution is an unfilled template and defines no enforceable project-specific gates. The following feature gates apply:

- Existing prediction secrecy and lock rules remain in force: PASS
- Participant-facing reads must not call external GenAI/provider services: PASS
- Existing urgent notification and wall-of-shame behavior remains scoped to current/next matchday: PASS
- Knockout draw/advancing-team semantics are explicit and must be implemented consistently: PASS
- Admin quiz setup must not mutate participant predictions except where a pre-lock Quiz Correction invalidates an answer: PASS
- Mobile/desktop bracket must remain readable and usable: PASS

Post-design re-check:

- Research resolves page scope, bracket rendering, missing-action scope, Quiz Setup ownership, navigation, Knockout Stage score semantics, Leeuwtje reset semantics, and leaderboard breakdown semantics: PASS
- Data model keeps domain concepts aligned with `CONTEXT.md`: PASS
- Contracts define backend/UI payload expectations without changing public auth behavior: PASS
- Quickstart covers participant, admin, correction, and routing flows: PASS

## Project Structure

### Documentation (this feature)

```text
specs/005-knockout-stage-readiness/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── api-and-ui-contract.md
├── tasks.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
backend/
├── app.py                    # Flask routes, pool payloads, prediction saves, admin quiz setup
├── api_data_sync_test.py     # Existing backend integration tests
├── quiz-2026.json            # Existing static group-stage quiz seed data
└── worldcup-2026.json        # Existing tournament and Knockout Stage match data

frontend/
└── src/
    ├── main.jsx              # Existing single-file React app; add route, page, bracket, detail panel
    └── styles.css            # Add responsive bracket and detail-panel styles

api/
└── index.py                  # Vercel entry point; unchanged import of backend.app
```

**Structure Decision**: Keep the feature inside existing `backend/app.py` and `frontend/src/main.jsx` because this app currently centralizes routing, pool payload construction, admin labels, and prediction UI there. Add helper functions/components locally first; extract only if implementation becomes meaningfully complex.

## Complexity Tracking

No constitution violations require justification.
