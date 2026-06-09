# Quickstart: WK Hub Fixes

## Prerequisites

Install dependencies from the repository root if not already installed:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-dev.txt
npm install
```

## Local validation commands

Run the frontend build:

```bash
npm run build
```

Run Python quality checks:

```bash
npm run py:check
```

Run the combined check:

```bash
npm run check
```

## Manual review scenarios after implementation

1. Tournament-pick privacy before reveal:
   - User A has champion, top scorer, and striker picks.
   - User B views User A before reveal.
   - User B does not see User A's tournament-pick names.

2. Tournament-pick reveal after lock:
   - At or after reveal time, User B can view User A's tournament-pick names on profile/detail surfaces.

3. Tournament-pick editability:
   - User A can edit own tournament picks before reveal.
   - User A cannot edit tournament picks after reveal.

4. Match prediction visibility:
   - User B cannot see User A's prediction for an unlocked match.
   - User B can see User A's prediction once the match locks, even before the match finishes.

5. Searchable scorer picker:
   - Champion can be one team while top scorer is selected from another team.
   - Search by player name returns matching players.
   - Search by team name returns players from that team.
   - Duplicate striker selections are prevented.

6. Tutorial and leaderboard:
   - Profile links are inactive in tutorial leaderboard preview.
   - Completing or skipping onboarding prediction prompts leads to normal app views.
   - In normal leaderboard, avatar and name open profile.
   - Top scorer and striker names are not shown in leaderboard columns.
   - Onboarding and empty-state copy does not say predictions are required to join or appear on the leaderboard.

7. Profile layout:
   - Profile page has no profile-specific `Back to leaderboard` button.
   - Long names and labels remain readable on common desktop and mobile widths.

8. New account leaderboard inclusion:
   - Create a new account and do not save any predictions.
   - Confirm the user can access the leaderboard, profiles, prediction entry, and prediction adjustment views where normal lock rules allow.
   - Confirm the new user appears in the leaderboard with zero points and incomplete/missing-prediction indicators.
   - Confirm another logged-in user also sees the new account in the leaderboard.
   - Save only one subset of predictions, then confirm the user remains visible in the leaderboard.

9. Admin label database:
   - Confirm the database has scoring label storage for `match_results`, `match_events`, and `player_match_stats`.
   - Confirm quiz label override storage exists after implementation.
   - Confirm admin label inspection returns current result, event/scorer, player-stat, and quiz label state.

10. Admin label editor access:
   - Log in as an admin and confirm the admin labels page is visible.
   - Log in as a non-admin and confirm the admin labels page and admin label APIs are unavailable.
   - Confirm archived/non-admin account management does not grant label editing access.

11. Manual result label update:
   - Save a manual match score/result label.
   - Confirm leaderboard/profile match prediction points use the updated score/result.
   - Confirm rows in `match_predictions` are unchanged.

12. Manual quiz and scorer label update:
   - Save a manual quiz correct-answer or viewership label.
   - Confirm quiz points use the updated label.
   - Save manual goal/scorer labels for a match.
   - Confirm top scorer and striker points use the updated labels.
   - Confirm `quiz_predictions` and `top_scorer_predictions` are unchanged.
