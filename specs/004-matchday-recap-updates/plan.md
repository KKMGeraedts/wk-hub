# Implementation Plan: Matchday Recap Updates

**Branch**: `004-matchday-recap-updates` | **Date**: 2026-06-24 | **Spec**: `specs/004-matchday-recap-updates/spec.md`

**Input**: Feature specification from `specs/004-matchday-recap-updates/spec.md`

## Summary

Update participant-facing tournament navigation and recap surfaces while preserving existing app structure. The schedule should be ordered around the current Matchday, the leaderboard should stop using the orange missing-prediction warning treatment, matchday cards and locked match detail should show the viewer's own prediction and point breakdown, locked match detail point calculation should avoid repeated full-tournament recomputation, and the daily recap should use one consistent Matchday baseline for day score and rank movement. The full Day Score appears as a contextual modal listing every active participant.

## Technical Context

**Language/Version**: Python 3.12; JavaScript/React 19; Vite 7

**Primary Dependencies**: Flask 3.1.1, psycopg 3.2.13, React, React DOM, Vite

**Storage**: Existing SQLite local / Postgres production schema; add only non-unique lookup indexes for match-scoped prediction queries

**Testing**: Python `unittest` integration tests in `backend/api_data_sync_test.py`; existing `npm run build`, `npm run py:check`, `npm run py:test`, and `npm run check`

**Target Platform**: Flask backend running locally and as a Vercel serverless Python entry point; Vite static frontend

**Project Type**: Full-stack web application with a Flask backend and React frontend

**Performance Goals**: Locked match detail for a typical pool should avoid per-user full-tournament point recomputation and satisfy the response-time target in the spec

**Constraints**: Preserve existing prediction data and scoring rules; keep locked match detail unavailable before match prediction lock; avoid schema migrations beyond safe index creation; preserve unrelated working-tree edits

**Scale/Scope**: One schedule page, leaderboard table treatment, matchday overview/detail surfaces, daily recap payload/UI, and focused backend regression tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution is an unfilled template and defines no enforceable project-specific gates. The following feature gates apply:

- Feature spec exists and contains no `NEEDS CLARIFICATION` markers: PASS
- Requirements checklist is complete: PASS
- Matchday and Day Score terminology has been captured in `CONTEXT.md`: PASS
- Participant prediction records are not mutated by recap or detail projection changes: PASS
- Locked match detail remains lock-gated: PASS
- Existing validation commands remain the quality gate: PASS

Post-design re-check:

- Existing app structure is preserved: PASS
- Backend payload additions are additive for participant reads: PASS
- New indexes are non-destructive and lookup-only: PASS
- Full repo validation succeeds after implementation: PASS

## Project Structure

### Documentation (this feature)

```text
specs/004-matchday-recap-updates/
├── spec.md
├── plan.md
├── tasks.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
backend/
├── app.py                    # Matchday, recap, scoring projection, schema indexes
├── api_data_sync_test.py     # Focused backend regression tests
└── genai_service.py          # Unrelated existing edits preserved

frontend/
└── src/
    ├── main.jsx              # Schedule, leaderboard, matchday, recap modal UI
    └── styles.css            # Supporting responsive styles
```

**Structure Decision**: Keep the feature within existing `backend/app.py`, `backend/api_data_sync_test.py`, and `frontend/src/*` files. The requested behavior changes existing projections and views rather than introducing a new module or route family.

## Implementation Approach

1. Add backend helpers for selected-match point breakdowns and match-attributable striker points so locked match detail can avoid repeated full-tournament recomputation.
2. Add viewer-specific `my_prediction` and `my_points` fields to matchday summary and locked match detail payloads.
3. Derive daily recap day scores and rank movements from the same Matchday point data, and include full `day_scores` rows for every active participant.
4. Add match-scoped lookup indexes for prediction, quiz, Leeuwtje, and top-scorer tables.
5. Update the frontend schedule grouping to use the app Matchday key: current first, past newest-to-oldest, future oldest-to-newest.
6. Update matchday overview/detail UI to show result, viewer prediction, and clickable point breakdowns.
7. Add a Day Score modal with every active participant and one expanded breakdown at a time.
8. Remove leaderboard missing-prediction legend and row highlight while preserving the predictions column.
9. Validate with backend tests, frontend build, Python checks, and full repository check.

## Complexity Tracking

No constitution violations require justification.
