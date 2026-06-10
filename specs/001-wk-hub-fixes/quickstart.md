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

13. Actionable notification clarity:
   - Leave one unlocked match prediction empty and one unlocked quiz empty.
   - Open the notification bell.
   - Confirm each missing item identifies the match and action type.
   - Click the missing quiz item.
   - Confirm the predictions view opens with the relevant match/quiz visible and ready to fill in.
   - Complete the quiz, refresh pool state, and confirm the notification disappears.

14. Admin broadcast notifications:
   - Log in as an admin.
   - Open the admin page and confirm a third send-message section exists.
   - Send a broadcast title and body.
   - Log in as another active user and confirm the message appears in the notification bell.
   - Deactivate or expire the broadcast and confirm it no longer appears after refresh.
   - Confirm a non-admin cannot access broadcast management APIs.

15. Leaderboard nickname and derived real name:
   - Create or inspect a user with email `jane.doe@talpanetwork.com` and nickname `MVP`.
   - Confirm the leaderboard shows `MVP` prominently.
   - Confirm `Jane Doe` appears smaller and lighter as supporting text.
   - Check the row on mobile width for readable wrapping and no overlap.

16. Leaderboard avatar hover preview:
   - View the leaderboard with users who have profile images.
   - Hover over a profile avatar and confirm a larger preview appears without opening the profile.
   - Keyboard-focus the avatar/name link and confirm the preview is also available.
   - Confirm rows do not resize or shift when the preview appears.

17. Talpa email validation:
   - Attempt account creation with `jane.doe@talpanetwork.com` and confirm it passes normal validation.
   - Attempt account creation with `jane@talpanetwork.com`, `jane.doe@gmail.com`, `jane+pool.doe@talpanetwork.com`, and `jane.@talpanetwork.com`.
   - Confirm invalid emails are rejected server-side with a clear message.

18. Admin quiz question and option editing:
   - Open the admin labels page as an admin.
   - Select a match with a quiz and confirm answer options are scrollable/selectable when needed.
   - Edit the quiz question text and answer options.
   - Save, then open prediction entry and confirm the corrected question/options are shown.
   - Set the correct answer and confirm scoring uses the updated label.
   - Confirm `quiz_predictions` rows are unchanged.

19. Wall of shame:
   - Leave unlocked predictions/quizzes missing for User A.
   - Complete all currently open predictions/quizzes for User B.
   - Confirm User A appears in the wall of shame with missing-action context.
   - Confirm User B does not appear.
   - Lock or simulate locking a match and confirm that locked missing item no longer counts.
   - Archive a user and confirm they are excluded.
