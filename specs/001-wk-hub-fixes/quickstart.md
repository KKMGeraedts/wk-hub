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
   - Completing required onboarding predictions leads to leaderboard.
   - In normal leaderboard, avatar and name open profile.
   - Top scorer and striker names are not shown in leaderboard columns.

7. Profile layout:
   - Profile page has no profile-specific `Back to leaderboard` button.
   - Long names and labels remain readable on common desktop and mobile widths.
