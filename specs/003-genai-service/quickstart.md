# Quickstart: GenAI Service

## Prerequisites

1. Install the existing app dependencies:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/pip install -r requirements-dev.txt
   npm install
   ```

2. Configure the existing app database and sync settings as documented in `README.md`.

3. Configure GenAI provider settings:

   ```bash
   export GENAI_PROVIDER=mistral
   export MISTRAL_API_KEY=...
   export GENAI_MODEL=...
   export GENAI_TIMEOUT_SECONDS=10
   ```

   `GENAI_PROVIDER=mistral` with `MISTRAL_API_KEY` enables provider calls. Without a supported provider and key, attempted jobs fail closed and create admin-only sync issues.

## Validation Commands

Run after implementation:

```bash
.venv/bin/python -m unittest discover backend -p '*_test.py'
npm run build
npm run py:check
npm run check
```

If the local shell does not provide Node/npm, run the backend validation directly:

```bash
.venv/bin/python -m unittest backend.api_data_sync_test
.venv/bin/python -m ruff check backend api
.venv/bin/python -m mypy
```

## Scenario 1: Quiz Answer Accepted From Match Facts

1. Seed or sync a completed match with normalized result/events/player stats.
2. Pick a match quiz whose answer can be proven from those facts.
3. Run the sync/admin path that triggers `quiz_answer_from_match_facts`.
4. Confirm the GenAI Job input contains only question, answer options, and compact normalized facts.
5. Confirm the accepted output selects an existing answer option and cites supplied facts.
6. Confirm an automatic quiz label is effective when no manual override exists.
7. Confirm computed quiz points are recalculated.
8. Review `GET /api/admin/labels` or the admin scoring labels panel for the GenAI source/status/evidence.

Expected result: evidence-backed GenAI quiz answers can score without participant prediction mutation.

## Scenario 2: Quiz Answer Rejected And Admin Notified

1. Use a quiz whose answer cannot be proven from available normalized facts.
2. Run the GenAI quiz job.
3. Confirm no automatic scoring label is accepted.
4. Confirm admins receive one active sync issue for the unresolved quiz.
5. Repeat the failure and confirm the active notification is updated rather than duplicated.

Expected result: unsupported or low-confidence GenAI answers do not score and create admin work.

## Scenario 3: Manual Quiz Override Wins

1. Save a manual quiz label for a match in the existing admin label editor.
2. Run a GenAI quiz job that would produce a different answer.
3. Confirm the manual label remains the effective scoring label.
4. Confirm computed quiz points reflect the manual answer.
5. Clear the manual override and confirm the accepted automatic label can become effective if still valid.

Expected result: the existing admin panel remains authoritative.

## Scenario 4: Player Match Accepted After Deterministic Matching Fails

1. Seed squad-player rows with an abbreviated or accented player name.
2. Seed a scorer/striker name that deterministic matching rejects but a human would recognize.
3. Run player database verification.
4. Confirm deterministic matching is attempted before the GenAI Job.
5. Confirm the GenAI Job receives only the unresolved raw name, target context, and a short candidate list.
6. Confirm the accepted output selects one existing candidate.
7. Confirm the raw scorer/striker name remains visible.
8. Review the admin scoring labels panel for the accepted player link; it should show the original raw name and matched squad player.

Expected result: GenAI can link an unresolved name to an existing player without rewriting source names.

## Scenario 5: Player Match Rejected And Admin Notified

1. Seed an unresolved scorer/striker name with no safe candidate match, or multiple ambiguous candidates.
2. Run player database verification.
3. Confirm no player candidate link is created.
4. Confirm admins receive one active sync issue for the unresolved player target.
5. Add or correct squad-player data so deterministic or GenAI matching can resolve the target.
6. Confirm the active notification is resolved.

Expected result: uncertain player matches remain manual/admin-visible.

## Scenario 6: Participant Reads Have No GenAI Side Effects

1. Seed unresolved quiz/player targets.
2. Load participant-facing pool, profile, and world-cup payloads.
3. Confirm no GenAI provider call is made.
4. Confirm no GenAI result rows or admin sync notifications are created from these reads.

Expected result: participant reads remain side-effect-free.
