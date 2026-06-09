# Implementation Plan: WK Hub Fixes

**Branch**: `main` | **Date**: 2026-06-09 | **Spec**: `specs/001-wk-hub-fixes/spec.md`

**Input**: Feature specification from `specs/001-wk-hub-fixes/spec.md`

**Note**: This plan stops before implementation. Implementation should begin only after review/approval, followed by task generation and review gates.

## Summary

Implement the WK Hub testing fixes by enforcing prediction privacy at the correct lock moments, improving tournament-pick entry UX, cleaning leaderboard/profile navigation, refining profile readability, removing legacy onboarding eligibility gates, and adding an admin-only manual label editor. The label editor gives admins a fallback when API-Football does not provide all data needed for scoring: admins can inspect and adjust result labels, scorer/striker goal labels, player-stat labels, and quiz-answer labels without gaining any ability to edit participant predictions.

## Technical Context

**Language/Version**: Python 3.12; JavaScript/React 19; Vite 7

**Primary Dependencies**: Flask 3.1.1, psycopg 3.2.13, React, React DOM, Vite

**Storage**: Existing SQLite local / Postgres production tables. Existing label tables found locally: `match_results`, `match_events`, and `player_match_stats`. New or extended DB-backed quiz-label override storage is needed because quiz labels currently come from static quiz JSON.

**Testing**: Existing project checks via `npm run build`, `npm run py:check`, and `npm run check`; manual scenario review required for time-based visibility, onboarding, empty-prediction leaderboard flows, admin access controls, and scoring-label overrides

**Target Platform**: Web app running locally via Flask/Vite and production via Vercel serverless Python plus Vite static frontend

**Project Type**: Full-stack web application with monolithic Flask backend and single-file React frontend

**Performance Goals**: Searchable scorer picker remains responsive for the current tournament player list; pool/profile data responses avoid exposing hidden data before reveal; leaderboard construction includes all active account users without noticeable extra overhead; admin label editor loads current tournament labels without blocking normal participant views

**Constraints**: Preserve existing prediction scoring and persistence; avoid new dependencies unless clearly justified; privacy must be enforced server-side, not only hidden in the UI; leaderboard eligibility must not depend on prediction completion; admin label edits must never mutate participant prediction rows

**Scale/Scope**: Existing 2026 World Cup pool data, participant leaderboard/profile surfaces, prediction entry/adjust flows, tutorial/onboarding flow, account-created participant rows, admin account management, and admin-managed scoring labels

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The current constitution file is still a placeholder and defines no enforceable project-specific gates. General Spec Kit gates apply:

- Feature spec exists and has no unresolved `[NEEDS CLARIFICATION]` markers: PASS
- Requirements quality checklist exists and is complete for the existing feature scope: PASS
- Plan avoids implementation before approval: PASS
- No known privacy/security violation introduced by design: PASS
- Admin-only label editing has an explicit authorization boundary: PASS

Post-design re-check:

- Research decisions resolve technical unknowns: PASS
- Data model confirms existing label tables and identifies quiz-label override storage: PASS
- Contracts define admin-only label inspection/update behavior and forbid prediction mutation: PASS
- Quickstart defines validation and manual review paths: PASS

## Project Structure

### Documentation (this feature)

```text
specs/001-wk-hub-fixes/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── api-and-ui-contract.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
backend/
├── app.py                  # Pool state, admin auth, labels DB, prediction privacy, save validation, profile prediction visibility
├── worldcup-2026.json       # Source of match schedule/lock timing
├── quiz-2026.json           # Existing quiz data and static fallback labels
└── team-profiles-2026.json  # Static/synced team profile fallback data

api/
└── index.py                 # Vercel Flask entry point

frontend/
├── index.html
└── src/
    ├── main.jsx             # Prediction entry, admin labels, leaderboard, profile, tutorial, player picker UI
    └── styles.css           # Admin/label/profile/leaderboard/player picker responsive styling

specs/001-wk-hub-fixes/
└── ...                      # Feature planning artifacts
```

**Structure Decision**: Use the existing monolithic backend and frontend files for a focused bug-fix/refinement feature. Avoid broad refactors or new packages during this feature; split components only locally inside `frontend/src/main.jsx` unless implementation later justifies extraction.

## Complexity Tracking

The admin label feature adds one justified complexity item: manual override storage for scoring labels.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| DB-backed quiz label overrides | Quiz answer/viewership labels are currently static JSON, but admins need runtime backup edits when external data is incomplete | Editing `quiz-2026.json` at runtime would not work reliably in production serverless deployment and would not provide auditability |

## Phase 0: Research Summary

Research output: `specs/001-wk-hub-fixes/research.md`

Key decisions:

- Use existing tournament and match lock semantics as the source of truth.
- Enforce tournament-pick privacy in backend-returned data.
- Keep leaderboard focused on ranking and move detailed pick reveal to profile/detail surfaces.
- Treat account creation, not prediction completion, as leaderboard eligibility.
- Use a custom searchable player picker rather than native grouped selects.
- Keep participant prediction storage unchanged.
- Treat tutorial/profile fixes as navigation and layout refinements.
- Use existing label tables (`match_results`, `match_events`, `player_match_stats`) as the primary labels database for scores, goals, and player stats.
- Add DB-backed quiz-label overrides and admin label audit metadata for manual fallback coverage.
- Restrict all label inspection/update APIs to admins and keep prediction update APIs scoped to the current participant only.

## Phase 1: Design Summary

Design outputs:

- `specs/001-wk-hub-fixes/data-model.md`
- `specs/001-wk-hub-fixes/contracts/api-and-ui-contract.md`
- `specs/001-wk-hub-fixes/quickstart.md`

Design notes:

- The existing feature changes visibility, eligibility, and UI behavior, not participant prediction entities.
- Hidden tournament-pick names should be masked before response data reaches the frontend for other users.
- Other users' match predictions should be filtered by match lock time rather than match result completion.
- Every active account user should receive a leaderboard row, with missing predictions represented as empty/incomplete progress rather than exclusion.
- Searchable player selection must support player/team filtering, duplicate prevention, clear states, and locked state.
- Tutorial leaderboard preview requires non-clickable rows; normal leaderboard requires avatar and name profile navigation.
- Admin label editing must write scoring labels, not participant predictions.
- Manual label edits should flow through the same scoring helpers already used by leaderboard/profile scoring.

## Planned Implementation Areas *(for future `/speckit-tasks`, not implementation in this phase)*

1. Backend privacy, lock semantics, and leaderboard eligibility
   - Add clearer tournament-pick lock/reveal helpers.
   - Pass viewer context into leaderboard/pool state construction.
   - Mask tournament-pick names for other users before reveal.
   - Change profile prediction group visibility from result-complete to match-locked.
   - Remove any leaderboard row filter that requires Netherlands group, champion, top scorer, striker, or all-prediction completion.
   - Keep completion flags/counts as progress metadata only.

2. Frontend visibility and navigation
   - Consume tournament-pick visibility metadata.
   - Hide other users' tournament picks on profile before reveal.
   - Remove scorer/striker names from leaderboard.
   - Make leaderboard name and avatar a combined profile link outside tutorial.
   - Disable profile links in tutorial leaderboard preview.
   - Remove profile-specific `Back to leaderboard`.
   - Update onboarding and leaderboard empty/progress copy so predictions are optional for participation.

3. Searchable scorer picker
   - Replace native scorer/striker selects with searchable controls.
   - Support filtering, duplicate prevention, clearing, no-result state, and disabled locked state.
   - Apply consistently in initial prediction and adjust prediction flows.

4. Profile layout and copy
   - Improve wrapping/responsiveness for profile and pick panels.
   - Normalize affected labels/copy.

5. Admin label editor
   - Verify/migrate label tables for results, match events, player stats, and quiz overrides.
   - Add admin-only label inspection endpoint returning current API-Football labels, manual overrides, source metadata, and scoring-relevant fields.
   - Add admin-only label update endpoints for score/result labels, quiz answer/viewership labels, goal/scorer labels, and player-stat labels.
   - Add admin UI page for inspecting and editing labels by match.
   - Ensure admin label routes cannot edit `match_predictions`, `quiz_predictions`, `leeuwtje_predictions`, `winner_predictions`, or `top_scorer_predictions`.
   - Recompute affected leaderboard/profile scoring from updated labels.

## Validation Strategy

Automated validation after implementation:

```bash
npm run build
npm run py:check
npm run check
```

Manual review scenarios are documented in `specs/001-wk-hub-fixes/quickstart.md`.

## Approved Review Decisions Before Implementation

The following plan decisions were reviewed and approved by the user on 2026-06-04. They are now binding inputs for task generation and implementation:

- **Approved**: Leaderboard will remove top scorer and striker names entirely.
- **Approved**: Tournament-pick detail reveal will occur on profile/detail surfaces, not leaderboard columns.
- **Approved**: Match-specific prediction visibility includes score, quiz, and Leeuwtje details.
- **Approved**: No database schema change is planned for the original privacy/navigation/scorer-picker scope.
- **Approved**: Privacy must be enforced backend-side, not only hidden in the frontend.

The following additional decisions were provided by the user on 2026-06-09 and are binding for task generation and implementation:

- **Approved**: Users who create an account have full app functionality and appear in the leaderboard even when they have not filled in champion, top scorer, striker, Netherlands, or any other predictions.
- **Approved**: Admins can archive accounts and manage admin access.
- **Approved**: Admins need a manual scoring-label editor as a fallback for incomplete API-Football data.
- **Approved**: Admins must not be able to adjust other participants' predictions.
