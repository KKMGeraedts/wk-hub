# Implementation Plan: API Data Sync + Participant Experience Updates

**Branch**: `main` | **Date**: 2026-06-11 | **Spec**: `specs/002-api-data-sync/spec.md`

**Input**: Feature specification from `specs/002-api-data-sync/spec.md`, plus scope expansion requested on 2026-06-11 for Talpa Studios account creation, prize-pot participation choice, and clearer prediction pick display/edit behavior.

**Note**: This plan stops before implementation. Generate and review `tasks.md` before running implementation.

## Summary

Keep the API data sync architecture from the original feature while adding three participant-facing updates in the same Flask/Vite application: account creation must accept only `firstname.lastname@talpastudios.com` addresses, every logged-in participant must be asked through notifications whether they join the optional EUR 10 prize pot, and the prediction pick component must separate view mode from edit mode while showing richer player/team context with flags.

## Technical Context

**Language/Version**: Python 3.12; JavaScript/React 19; Vite 7

**Primary Dependencies**: Flask 3.1.1, psycopg 3.2.13, React, React DOM, Vite

**Storage**: Existing SQLite local / Postgres production tables. Existing tables include `users`, prediction tables, notification tables, `api_football_*`, `match_results`, `match_events`, `match_clean_sheets`, `player_match_stats`, `quiz_label_overrides`, and `label_audit_log`. New or extended storage is planned for provider-agnostic sync attempts, admin sync notifications, stored computed points, prize-pot participation choices, and richer top-scorer/striker pick metadata where needed.

**Testing**: Existing checks via `npm run build`, `npm run py:check`, and `npm run check`; targeted Python unit/integration coverage should be added for sync candidate selection, manual-override precedence, computed point persistence, Talpa Studios email validation, prize-pot notification state, and prediction pick save/view behavior.

**Target Platform**: Web app running locally via Flask/Vite and production via Vercel serverless Python plus Vite static frontend

**Project Type**: Full-stack web application with monolithic Flask backend and single-file React frontend

**Performance Goals**: Result sync requests only due matches and never re-fetches unrelated history; leaderboard/profile reads should use stored computed points; prize-pot notifications and profile badges should add no noticeable overhead to `/api/pool` or profile payloads.

**Constraints**: Preserve participant prediction data; keep provider calls out of normal participant views; preserve permanent raw provider history; manual overrides must not be overwritten by provider updates; account creation must enforce the exact Talpa Studios email convention; prize-pot payment is outside the app; avoid new dependencies unless clearly justified.

**Scale/Scope**: Existing 2026 World Cup tournament data, post-match result sync, rare squad sync, admin label/editor flows, scoring labels, leaderboard/profile scoring output, admin and participant notification-bell infrastructure, login/account creation, public profiles, and prediction pick components.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The current constitution file is still a placeholder and defines no enforceable project-specific gates. General Spec Kit gates apply:

- Feature spec exists and has no unresolved `[NEEDS CLARIFICATION]` markers: PASS
- Requirements quality checklist exists and is complete for the original sync scope: PASS
- Plan avoids implementation before task generation: PASS
- No known privacy/security violation introduced by design: PASS
- Provider data and manual override updates are explicitly barred from mutating participant prediction rows: PASS
- Prize-pot participation is an explicit opt-in/opt-out user choice and does not handle payment in app: PASS
- Email account creation is constrained to the requested Talpa Studios convention: PASS

Post-design re-check:

- Research decisions resolve technical unknowns: PASS
- Data model identifies new and existing entities, including prize-pot participation and prediction pick display metadata: PASS
- Contracts define sync, admin notification, computed scoring, account creation, prize-pot notification, and prediction pick behavior: PASS
- Quickstart defines validation and manual review paths for sync and participant UX updates: PASS

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
├── app.py                  # Current monolith: auth, routes, DB setup, scoring, provider sync, notifications
├── worldcup-2026.json      # Static match schedule and lock timing source
├── quiz-2026.json          # Static quiz fallback data
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

**Structure Decision**: Keep the current monolithic backend and single-file React frontend for this implementation scope. Add clearer internal service/helper boundaries inside `backend/app.py` for auth validation, prize-pot notification state, sync, and scoring before considering module extraction. Frontend changes should reuse the existing notification bell, profile panels, winner/top-scorer/striker controls, and route structure.

## Complexity Tracking

This feature intentionally adds data-model complexity for sync attempts, stored computed points, prize-pot participation, and richer pick display state.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Provider-agnostic sync attempt records | Needed to model per-match attempts, failure notifications, and future provider support | Continuing only with `api_football_requests` records provider calls but not app-level scheduling, attempt windows, or skipped/missing-link outcomes |
| Stored computed points | Needed for consistent leaderboard/profile reads and auditability after manual/provider facts change | Recomputing all points on every read makes source/fact interactions harder to audit and can produce inconsistent views during changes |
| Prize-pot participation records | Needed to ask each participant once and show each participant's choice on profiles | A transient notification-only answer would be lost and could not be shown to others |
| Rich pick metadata for display | Needed to show full player names plus country flags in view mode | Storing/displaying only plain names makes the striker/top-scorer picks unclear and visually weak |

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
- Enforce `firstname.lastname@talpastudios.com` for account creation and login normalization.
- Use the existing notification bell to ask each participant whether they join the optional EUR 10 prize pot until they answer.
- Store prize-pot choice on the user/profile domain and expose it on profiles.
- Make tournament pick components view-first, with explicit edit actions before selections become adjustable.

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
- Account creation should update `TALPA_EMAIL_PATTERN`, backend validation copy, frontend validation copy, placeholders, and admin defaults away from the previous Talpa Network domain where applicable.
- Prize-pot participation should be modeled as a persistent per-user choice with `undecided`, `joined`, and `declined` states. Olivier Thijsen is the organizer/payee context, but payment remains outside the app.
- Profile payloads should expose whether a participant joined the prize pot.
- Prediction pick view mode should show champion flag, top scorer name with flag/country, and each striker's full name with flag/country. Clicks in view mode should not modify picks; an edit button switches to editable controls subject to lock rules.

## Validation Strategy

Automated validation after implementation:

```bash
python3 -m unittest discover backend -p '*_test.py'
npm run build
npm run py:check
npm run check
```

Manual review scenarios are documented in `specs/002-api-data-sync/quickstart.md`.
