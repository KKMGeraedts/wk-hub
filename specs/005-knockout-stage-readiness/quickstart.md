# Quickstart: Knockout Stage Readiness

## Preconditions

- Install existing project dependencies.
- Use an authenticated participant account for participant checks.
- Use an authenticated admin account for Quiz Setup checks.
- Seed or simulate Knockout Stage matches with both unresolved Bracket Slots and known teams.

## Validate Participant Bracket

1. Start the app.
2. Log in as a participant.
3. Open `/knockout`.
4. Confirm the page shows Round of 32 through Final in a bracket-shaped layout.
5. Confirm unresolved matches show Bracket Slots such as `1A`, `W73`, or `L101`.
6. Select an unresolved tile and confirm the detail panel shows path/date/venue but no prediction controls.

## Validate Open Knockout Prediction

1. Set one Knockout Stage match to have both teams known and a future lock time.
2. Open `/knockout` as a participant.
3. Select that Knockout Match Tile.
4. Enter and save a score prediction.
5. Confirm the tile and detail panel no longer show a missing score prediction.
6. Confirm existing group-stage prediction screens still behave as before.

## Validate Quiz Not Set State

1. Use a known-team Knockout Stage match with no Quiz Question.
2. Open its detail panel.
3. Confirm score prediction is available.
4. Confirm the quiz area says the quiz question is not set yet.

## Validate Admin Quiz Setup

1. Log in as an admin.
2. Open the admin quiz/labels area.
3. Select a Knockout Stage match with no Quiz Question.
4. Set question text, answer options, scoring values, and reason.
5. Log in as a participant.
6. Open the same match on `/knockout`.
7. Confirm the quiz question is answerable before lock time.

## Validate Quiz Correction

1. Submit a participant quiz answer.
2. As admin, correct answer options before lock time so the existing answer no longer matches.
3. As participant, reopen `/knockout`.
4. Confirm that quiz answer is again a Missing Action.
5. Repeat after lock time and confirm participant answers are not automatically reopened.

## Validate Navigation

1. Simulate Knockout Stage planning relevance.
2. Confirm top-level navigation shows `Knockout`.
3. Click My Predictions and confirm it opens the Knockout Page or focuses the first urgent knockout action according to current app state.

## Validation Commands

```bash
npm run build
npm run py:check
npm run py:test
npm run check
```

## Validation Results

- 2026-06-24: `npm run build` passed.
- 2026-06-24: `npm run py:check` passed after formatting `backend/app.py`.
- 2026-06-24: `npm run py:test` passed, 121 tests.
- 2026-06-24: `npm run check` passed after final CSS fix.
- 2026-06-24: `npm run check` passed after review fixes for knockout relevance, new quiz setup validation, and quiz-only saves.
- 2026-06-24: Vite dev server served `/knockout` with HTTP 200 at `http://127.0.0.1:5175/knockout`.
- 2026-06-24: Browser/screenshot QA was not completed because no browser-control tool or local Playwright install was available in this session.
- 2026-06-25: `npm run check` passed after adding Prediction Result / Advancing Team storage, in-memory Bracket Slot resolution, admin sync issues, and admin Advancing Team correction.
