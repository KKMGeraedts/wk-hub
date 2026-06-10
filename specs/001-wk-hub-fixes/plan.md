# Implementation Plan: WK Hub Fixes

**Branch**: `main` | **Date**: 2026-06-10 | **Spec**: `specs/001-wk-hub-fixes/spec.md`

**Input**: Feature specification from `specs/001-wk-hub-fixes/spec.md`, extended by 2026-06-10 user feedback for notification clarity, admin broadcasts, leaderboard identity display, avatar hover previews, Talpa email validation, richer admin quiz/label editing, and a wall of shame for missing predictions.

**Note**: This plan stops before implementation. Implementation should begin only after review/approval, followed by task generation and review gates.

## Summary

Extend the existing WK Hub fixes with participant-facing accountability and admin communication features. The notification bell should point users to the exact missing prediction or quiz items instead of a generic predictions page. Admins should be able to send broadcast messages through the same bell from a third admin section. Leaderboard rows should keep the nickname as the primary name while adding a subtle first/last name derived from the required `firstname.lastname@talpanetwork.com` email structure, with larger avatar previews on hover. Account creation must reject non-Talpa and non-firstname.lastname emails. Admin label editing must become a complete quiz editor for question text, answer options, and correct labels. A wall of shame should surface participants who have not filled in currently open predictions yet.

## Technical Context

**Language/Version**: Python 3.12; JavaScript/React 19; Vite 7

**Primary Dependencies**: Flask 3.1.1, psycopg 3.2.13, React, React DOM, Vite

**Storage**: Existing SQLite local / Postgres production tables. Existing tables include `users`, prediction tables, label tables, `quiz_label_overrides`, `label_audit_log`, and newsletter tables. New DB-backed storage is needed for admin notification broadcasts. Existing `users.email` becomes the source for derived first/last names and must satisfy `firstname.lastname@talpanetwork.com`.

**Testing**: Existing project checks via `npm run build`, `npm run py:check`, and `npm run check`; manual scenario review required for actionable notification routing, admin broadcast visibility, email validation, leaderboard identity display, avatar hover preview, wall-of-shame inclusion/exclusion, and admin quiz/label editing.

**Target Platform**: Web app running locally via Flask/Vite and production via Vercel serverless Python plus Vite static frontend

**Project Type**: Full-stack web application with monolithic Flask backend and single-file React frontend

**Performance Goals**: Notification payloads remain small for today's/tomorrow's missing actions plus active broadcasts; leaderboard construction still loads all active users without noticeable overhead; wall-of-shame computation reuses existing missing-prediction metadata; admin label editor remains usable with scrollable match/option controls.

**Constraints**: Preserve existing prediction scoring and persistence; avoid new dependencies unless clearly justified; privacy must be enforced server-side; admin broadcasts and label edits must be admin-only; admin label/quiz edits must not mutate participant prediction rows; account creation must reject emails outside the required Talpa format.

**Scale/Scope**: Existing 2026 World Cup pool data, notification bell, prediction entry/adjust routing, leaderboard, profile avatars, account login/registration, admin account/label pages, admin-managed broadcasts, scoring labels, quiz metadata, and incomplete-prediction accountability surfaces.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The current constitution file is still a placeholder and defines no enforceable project-specific gates. General Spec Kit gates apply:

- Feature spec exists and has no unresolved `[NEEDS CLARIFICATION]` markers: PASS
- Requirements are testable from user-facing scenarios and admin access scenarios: PASS
- Plan avoids implementation before approval: PASS
- Privacy-sensitive prediction visibility remains backend-enforced: PASS
- Admin-only actions have an explicit authorization boundary: PASS
- Account email validation is defined server-side, with frontend validation as UX support only: PASS

Post-design re-check:

- Research decisions resolve technical unknowns for notifications, broadcasts, identity derivation, email validation, admin quiz editing, and wall-of-shame computation: PASS
- Data model identifies new or changed entities, including admin broadcasts and derived display identity: PASS
- Contracts define API/UI behavior for notification actions, broadcasts, email validation, leaderboard identity, avatar previews, quiz label editing, and wall of shame: PASS
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
├── checklists/
│   └── requirements.md
└── tasks.md              # Existing completed tasks; regenerate after plan approval
```

### Source Code (repository root)

```text
backend/
├── app.py                  # Pool state, admin auth, notifications, broadcasts, email validation, labels DB, scoring, profile visibility
├── worldcup-2026.json       # Match schedule and quiz routing context
├── quiz-2026.json           # Existing static quiz fallback data
└── team-profiles-2026.json

api/
└── index.py                 # Vercel Flask entry point

frontend/
├── index.html
└── src/
    ├── main.jsx             # Notification bell, admin broadcasts, leaderboard, wall of shame, admin quiz/labels, auth UI
    └── styles.css           # Notification, leaderboard identity, avatar hover, admin editor, wall-of-shame styles

specs/001-wk-hub-fixes/
└── ...                      # Feature planning artifacts
```

**Structure Decision**: Use the existing monolithic backend and frontend files for this focused feature set. Add database tables only where persistence is required for admin broadcasts and, if needed, quiz question/option overrides. Avoid a frontend component library; the current app already implements custom controls and admin panels in `frontend/src/main.jsx`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| DB-backed admin broadcasts | Broadcast notifications must persist and be shown to all users through the notification bell | Hardcoded messages or static JSON would require deploys, would not support admin sending, and would not provide audit/source metadata |
| DB-backed quiz metadata overrides if static quiz fields must change at runtime | Admins need to adjust question text and answer options, not only correct labels | Editing `quiz-2026.json` at runtime is unreliable in production serverless deployment and lacks admin auditability |

## Phase 0: Research Summary

Research output: `specs/001-wk-hub-fixes/research.md`

Key decisions:

- Keep missing-prediction notifications server-authored, but enrich each item with match labels, quiz labels, and target route/action metadata.
- Route notification clicks to a prediction view focused on the relevant missing match or quiz rather than to a generic predictions landing state.
- Store admin broadcast notifications in DB with admin author, title/body, active window, and audit metadata; merge active broadcasts into each user's notification bell.
- Add a third admin section for sending broadcast messages alongside existing user management and scoring-label editing.
- Derive first and last names from validated Talpa email addresses and keep `users.name` as nickname.
- Enforce `firstname.lastname@talpanetwork.com` email format on account creation and login/upsert paths that can create users.
- Use CSS hover/focus avatar preview on leaderboard rows, backed by existing profile image URLs.
- Expand admin label editing to include quiz question text and answer options through override storage, while keeping participant quiz predictions immutable.
- Compute wall-of-shame rows from existing active users plus currently open missing prediction/quiz state; do not shame locked or no-longer-actionable items.

## Phase 1: Design Summary

Design outputs:

- `specs/001-wk-hub-fixes/data-model.md`
- `specs/001-wk-hub-fixes/contracts/api-and-ui-contract.md`
- `specs/001-wk-hub-fixes/quickstart.md`

Design notes:

- Existing notification payloads already include missing `match_ids`; implementation should add human-readable match summaries and per-notification actions.
- Notification bell display should support mixed notification types: missing predictions, missing quizzes, admin broadcasts, and future notification types.
- Admin broadcasts are distinct from missing-action notifications because they are authored by admins and visible to many users at once.
- Leaderboard identity should display nickname first and derived real name as smaller, low-contrast supporting text.
- Email validation belongs in backend auth/account creation, with frontend validation only to produce faster feedback.
- Avatar hover previews should not require navigation and must not disturb table layout.
- Admin quiz editing should expose selectable/scrollable answer options and editable question text, correct answer(s), and viewership answer in the label editor.
- Wall of shame should use the same missing-action calculation as notifications so users are not called out for locked matches they can no longer change.

## Planned Implementation Areas *(for future `/speckit-tasks`, not implementation in this phase)*

1. Notification clarity and routing
   - Enrich notification payloads with match display names, dates, missing item kind, and focus target.
   - Render each notification as actionable rows rather than only one broad button.
   - Navigate to prediction entry/adjust view with selected match/quiz focus when clicked.
   - Preserve the generic "Open predictions" fallback only when no specific target exists.

2. Admin broadcast notifications
   - Add broadcast notification storage with active/dismissal-ready metadata.
   - Add admin-only create/list/deactivate APIs.
   - Add a third admin page section for "Send message".
   - Merge active broadcasts into the notification bell for every non-archived user.
   - Keep broadcasts visually distinct from personal missing-action notifications.

3. Leaderboard identity and avatar preview
   - Derive `first_name` and `last_name` from `users.email` in backend leaderboard/profile payloads.
   - Keep nickname (`users.name`) as the primary row label.
   - Add subtle derived full-name side note below or beside the nickname.
   - Add hover/focus avatar enlargement for leaderboard profile pictures without changing row height or requiring profile navigation.

4. Talpa email validation
   - Add a single backend email validator for `firstname.lastname@talpanetwork.com`.
   - Apply it anywhere a user account can be created or email can be normalized for account creation.
   - Return clear errors for non-Talpa, missing-dot, plus-addressed, malformed, or non-lowercase-equivalent invalid inputs.
   - Mirror validation in auth UI for immediate feedback.

5. Admin quiz/label editor completion
   - Make match selection and option lists scrollable and selectable in the admin label editor.
   - Allow editing quiz question text, answer options, correct answers, and viewership answer.
   - Persist quiz metadata overrides separately from participant predictions.
   - Apply quiz overrides consistently when loading data for prediction entry and scoring.
   - Preserve audit metadata for all admin label/quiz changes.

6. Wall of shame
   - Add a backend payload or endpoint listing active users with currently open missing predictions/quizzes.
   - Add a visible leaderboard/admin-adjacent section using Dutch-facing copy and accountability tone.
   - Include enough detail to show what is missing without exposing private prediction content.
   - Exclude archived users and exclude items that are already locked.

## Validation Strategy

Automated validation after implementation:

```bash
npm run build
npm run py:check
npm run check
```

Manual review scenarios are documented in `specs/001-wk-hub-fixes/quickstart.md`.

## Approved Review Decisions Before Implementation

Existing binding decisions from the prior plan remain in force:

- Leaderboard removes top scorer and striker names entirely.
- Tournament-pick detail reveal occurs on profile/detail surfaces, not leaderboard columns.
- Match-specific prediction visibility includes score, quiz, and Leeuwtje details.
- Privacy must be enforced backend-side, not only hidden in the frontend.
- Users who create an account have full app functionality and appear in the leaderboard even with missing predictions.
- Admins can archive accounts and manage admin access.
- Admins can edit scoring labels but must not edit participant predictions.

New decisions captured from 2026-06-10 user feedback:

- Notification bell entries must identify which quiz or prediction is missing and lead users directly to that item.
- Admin broadcast messages should be sent from a third admin section and delivered through the notification bell.
- Leaderboard nickname remains primary; first/last name derived from email is secondary and subtle.
- Leaderboard avatar hover should preview the profile picture larger without requiring profile navigation.
- New accounts must use `firstname.lastname@talpanetwork.com`.
- Admin quiz/label editing must include selecting labels/options and editing question text plus answer options.
- Wall of shame should show users who have not filled in currently open predictions yet.
