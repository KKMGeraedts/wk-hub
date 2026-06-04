# Implementation Plan: WK Hub Fixes

**Branch**: `001-wk-hub-fixes` | **Date**: 2026-06-04 | **Spec**: `specs/001-wk-hub-fixes/spec.md`

**Input**: Feature specification from `specs/001-wk-hub-fixes/spec.md`

**Note**: This plan stops before implementation. Implementation should begin only after review/approval, followed by task generation and review gates.

## Summary

Implement the WK Hub testing fixes by enforcing prediction privacy at the correct lock moments, improving tournament-pick entry UX, cleaning leaderboard/profile navigation, and refining profile readability. The approach is to reuse existing lock semantics, enforce privacy in returned pool/profile data, replace long scorer selects with searchable controls, remove scorer/striker names from leaderboard display, disable profile links in tutorial context, and adjust profile layout/copy without introducing schema changes.

## Technical Context

**Language/Version**: Python 3.12; JavaScript/React 19; Vite 7

**Primary Dependencies**: Flask 3.1.1, psycopg 3.2.13, React, React DOM, Vite

**Storage**: Existing SQLite local / Postgres production tables; no new tables planned

**Testing**: Existing project checks via `npm run build`, `npm run py:check`, and `npm run check`; manual scenario review required for time-based visibility and onboarding flows

**Target Platform**: Web app running locally via Flask/Vite and production via Vercel serverless Python plus Vite static frontend

**Project Type**: Full-stack web application with monolithic Flask backend and single-file React frontend

**Performance Goals**: Searchable scorer picker remains responsive for the current tournament player list; pool/profile data responses avoid exposing hidden data before reveal

**Constraints**: Preserve existing prediction scoring and persistence; avoid new dependencies unless clearly justified; no database schema migration expected; privacy must be enforced server-side, not only hidden in the UI

**Scale/Scope**: Existing 2026 World Cup pool data, participant leaderboard/profile surfaces, prediction entry/adjust flows, tutorial onboarding flow

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The current constitution file is still a placeholder and defines no enforceable project-specific gates. General Spec Kit gates apply:

- Feature spec exists and has no unresolved `[NEEDS CLARIFICATION]` markers: PASS
- Requirements quality checklist exists and is complete: PASS
- Plan avoids implementation before approval: PASS
- No known privacy/security violation introduced by design: PASS

Post-design re-check:

- Research decisions resolve technical unknowns: PASS
- Data model confirms no schema change is required: PASS
- Contracts define privacy-sensitive response/display behavior: PASS
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
├── app.py                  # Pool state, prediction privacy, save validation, profile prediction visibility
├── worldcup-2026.json       # Source of match schedule/lock timing
├── quiz-2026.json           # Existing quiz data
└── team-profiles-2026.json  # Static/synced team profile fallback data

api/
└── index.py                 # Vercel Flask entry point

frontend/
├── index.html
└── src/
    ├── main.jsx             # Prediction entry, leaderboard, profile, tutorial, player picker UI
    └── styles.css           # Profile/leaderboard/player picker responsive styling

specs/001-wk-hub-fixes/
└── ...                      # Feature planning artifacts
```

**Structure Decision**: Use the existing monolithic backend and frontend files for a focused bug-fix/refinement feature. Avoid broad refactors or new packages during this feature; split components only locally inside `frontend/src/main.jsx` unless implementation later justifies extraction.

## Complexity Tracking

No constitution violations or unusual complexity are currently justified.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Phase 0: Research Summary

Research output: `specs/001-wk-hub-fixes/research.md`

Key decisions:

- Use existing tournament and match lock semantics as the source of truth.
- Enforce tournament-pick privacy in backend-returned data.
- Keep leaderboard focused on ranking and move detailed pick reveal to profile/detail surfaces.
- Use a custom searchable player picker rather than native grouped selects.
- Keep the data model unchanged.
- Treat tutorial/profile fixes as navigation and layout refinements.

## Phase 1: Design Summary

Design outputs:

- `specs/001-wk-hub-fixes/data-model.md`
- `specs/001-wk-hub-fixes/contracts/api-and-ui-contract.md`
- `specs/001-wk-hub-fixes/quickstart.md`

Design notes:

- The feature changes visibility and UI behavior, not stored entities.
- Hidden tournament-pick names should be masked before response data reaches the frontend for other users.
- Other users' match predictions should be filtered by match lock time rather than match result completion.
- Searchable player selection must support player/team filtering, duplicate prevention, clear states, and locked state.
- Tutorial leaderboard preview requires non-clickable rows; normal leaderboard requires avatar and name profile navigation.

## Planned Implementation Areas *(for future `/speckit-tasks`, not implementation in this phase)*

1. Backend privacy and lock semantics
   - Add clearer tournament-pick lock/reveal helpers.
   - Pass viewer context into leaderboard/pool state construction.
   - Mask tournament-pick names for other users before reveal.
   - Change profile prediction group visibility from result-complete to match-locked.

2. Frontend visibility and navigation
   - Consume tournament-pick visibility metadata.
   - Hide other users' tournament picks on profile before reveal.
   - Remove scorer/striker names from leaderboard.
   - Make leaderboard name and avatar a combined profile link outside tutorial.
   - Disable profile links in tutorial leaderboard preview.
   - Remove profile-specific `Back to leaderboard`.

3. Searchable scorer picker
   - Replace native scorer/striker selects with searchable controls.
   - Support filtering, duplicate prevention, clearing, no-result state, and disabled locked state.
   - Apply consistently in initial prediction and adjust prediction flows.

4. Profile layout and copy
   - Improve wrapping/responsiveness for profile and pick panels.
   - Normalize affected labels/copy.

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
- **Approved**: No database schema change is planned.
- **Approved**: Privacy must be enforced backend-side, not only hidden in the frontend.
