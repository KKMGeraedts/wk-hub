# Implementation Plan: API Data Sync + Automatic Quiz Resolver

**Branch**: `main` | **Date**: 2026-06-15 | **Spec**: `specs/002-api-data-sync/spec.md`

**Input**: Feature specification from `specs/002-api-data-sync/spec.md`, expanded on 2026-06-15 to add automatic quiz-answer resolution from synced football facts.

## Summary

Extend the existing provider-backed result sync so quiz questions can opt into deterministic automatic labeling. Each API-answerable quiz question gets explicit resolver metadata that maps the question to normalized match facts such as goals, cards, penalties, substitutions, clean sheets, or team/player statistics. Provider-backed quiz labels are stored separately from participant predictions, manual quiz labels remain highest priority, unsupported questions remain manual, and computed quiz points are recalculated whenever automatic labels are created or changed.

## Technical Context

**Language/Version**: Python 3.12; JavaScript/React 19; Vite 7

**Primary Dependencies**: Flask 3.1.1, psycopg 3.2.13, React, React DOM, Vite

**Storage**: Existing SQLite local / Postgres production tables. Existing tables include `users`, prediction tables, notification tables, `api_football_*`, `match_results`, `match_events`, `match_clean_sheets`, `player_match_stats`, `quiz_label_overrides`, `label_audit_log`, `provider_sync_attempts`, `computed_points`, and `admin_sync_notifications`. Automatic quiz labels should extend the existing quiz-label domain without mutating participant `quiz_predictions`.

**Testing**: Existing checks via `.venv/bin/python -m unittest discover backend -p '*_test.py'`, `npm run build`, `npm run py:check`, and `npm run check`; targeted backend coverage should be added for each resolver family, manual override precedence, insufficient-facts behavior, and computed quiz point recalculation after automatic labels.

**Target Platform**: Web app running locally via Flask/Vite and production via Vercel serverless Python plus Vite static frontend.

**Project Type**: Full-stack web application with monolithic Flask backend and single-file React frontend.

**Performance Goals**: Quiz resolver runs only after provider/manual fact changes and should add no provider calls during participant reads. Resolver work is per-match and bounded by a single fixture's normalized facts.

**Constraints**: Do not parse quiz question prose to infer answers. Use explicit resolver metadata. Keep provider calls out of participant views. Manual quiz labels must win over automatic labels. Unsupported or low-confidence questions must remain unresolved rather than guessed. Participant prediction rows must not be changed by resolver output.

**Scale/Scope**: Existing 2026 World Cup quiz set, match result sync, admin label/editor flows, scoring labels, leaderboard/profile stored computed points, and admin notifications.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The current constitution file is still a placeholder and defines no enforceable project-specific gates. General Spec Kit gates apply:

- Feature spec exists and has no unresolved `[NEEDS CLARIFICATION]` markers: PASS
- Plan avoids implementation before task generation: PASS
- No known privacy/security violation introduced by design: PASS
- Participant prediction rows are explicitly not mutated by provider sync, manual overrides, automatic quiz labels, or computed scoring updates: PASS
- Manual admin quiz labels remain higher priority than provider-backed automatic quiz labels: PASS
- Participant reads do not trigger provider retrieval or quiz resolution side effects: PASS

Post-design re-check:

- Research decisions resolve technical unknowns: PASS
- Data model identifies quiz resolver rule, automatic quiz label, and quiz resolution attempt/status: PASS
- Contracts define resolver metadata, sync behavior, admin review, and scoring behavior: PASS
- Quickstart defines validation and manual review paths for automatic quiz labels: PASS

## Project Structure

### Documentation (this feature)

```text
specs/002-api-data-sync/
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
├── app.py                  # Current monolith: auth, routes, DB setup, scoring, provider sync, quiz labels, notifications
├── worldcup-2026.json      # Static match schedule and lock timing source
├── quiz-2026.json          # Static quiz metadata plus planned auto_label resolver metadata
└── team-profiles-2026.json # Static/synced team profile fallback data

api/
└── index.py                # Vercel Flask entry point

frontend/
├── index.html
└── src/
    ├── main.jsx            # Login, notifications, predictions, profiles, admin UI
    └── styles.css

specs/002-api-data-sync/
└── ...                     # Feature planning artifacts
```

**Structure Decision**: Keep the current monolithic backend and single-file React frontend for this planning scope. Add clearer internal helper boundaries inside `backend/app.py` for quiz resolver rule parsing, normalized fact access, automatic label persistence, and computed point recalculation before considering physical module extraction.

## Complexity Tracking

This expansion adds structured resolver metadata and provider-backed quiz labels, but keeps the implementation inside existing backend and admin label boundaries.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Explicit resolver metadata on quiz questions | Needed to map each Dutch quiz question to deterministic normalized facts without guessing from prose | Natural-language parsing is brittle and would produce unreviewable scoring surprises |
| Provider-backed automatic quiz label state | Needed to distinguish automatic labels from manual admin overrides and static fallback labels | Writing automatic answers directly into static quiz JSON is not possible in production and would lose source/audit context |
| Resolver status/attempt visibility | Needed to show admins why a quiz remains manual, unsupported, or waiting for facts | Silent skips would recreate the same operational confusion as missed scorer labels |

## Phase 0: Research Summary

Research output: `specs/002-api-data-sync/research.md`

Key decisions:

- Use explicit quiz resolver metadata, not natural-language question parsing.
- Run quiz resolution after normalized provider facts are stored, not from participant page loads.
- Store provider-backed automatic quiz labels separately from manual quiz overrides and keep manual precedence.
- Start with a conservative resolver registry for high-confidence rule families: goal timing, team scoring, player scoring, cards, penalties, clean sheets, substitutions, and statistics-backed rules when provider facts exist.
- Leave ambiguous, subjective, or low-confidence quiz questions unresolved for manual admin labeling.
- Recompute stored quiz points after automatic quiz labels are inserted or changed.
- Surface unsupported or insufficient-fact states to admins without exposing provider internals to normal participants.

## Phase 1: Design Summary

Design outputs:

- `specs/002-api-data-sync/data-model.md`
- `specs/002-api-data-sync/contracts/api-and-ui-contract.md`
- `specs/002-api-data-sync/quickstart.md`

Design notes:

- `backend/quiz-2026.json` should gain optional `auto_label` metadata per quiz. The metadata should include a `kind`, parameters, and expected answer mapping where needed.
- Resolver helpers should read normalized facts already written by provider sync: `match_results`, `match_events`, `match_clean_sheets`, `player_match_stats`, and future team-stat rows if added.
- Automatic labels should use a source such as `api-football` and should not overwrite manual labels in `quiz_label_overrides`.
- Existing `apply_quiz_label_overrides()` should continue to produce the effective scoring labels, extended as needed to apply automatic labels below manual labels.
- Admin label UI can show automatic source/status in the existing label editor payload, but manual override and reversal remain the authoritative editing flow.
- Computed points should be recalculated only when automatic quiz labels change or when a manual override changes the effective label.

## Validation Strategy

Automated validation after implementation:

```bash
.venv/bin/python -m unittest discover backend -p '*_test.py'
npm run build
npm run py:check
npm run check
```

Targeted backend tests should cover:

- Resolver metadata parsing and unsupported-rule rejection.
- Goal-before-minute, first-goal bucket, last-goal-after-minute, both-teams-score, team-scores, player-scores, penalty, card, clean-sheet, and statistics-backed resolver rules.
- Resolver skipped when required facts are missing.
- Manual quiz override wins over automatic provider label.
- Automatic label update triggers computed quiz point recalculation.
- Participant `/api/world-cup`, `/api/pool`, and profile reads do not trigger provider calls or resolver writes.

Manual review scenarios are documented in `specs/002-api-data-sync/quickstart.md`.
