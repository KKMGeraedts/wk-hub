# Quickstart: API Data Sync

## Automated Checks

Run after implementation:

```bash
python3 -m unittest discover backend -p '*_test.py'
npm run build
npm run py:check
npm run check
```

## Local Setup

1. Install dependencies if needed:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/pip install -r requirements-dev.txt
   npm install
   ```

2. Configure local environment:

   ```bash
   cp .env.example .env
   ```

3. Set sync-related values in `.env` when testing provider calls:

   ```text
   API_FOOTBALL_KEY=...
   WK_HUB_SYNC_TOKEN=...
   ```

4. Start the app:

   ```bash
   .venv/bin/python backend/app.py
   ```

## Manual Scenario Review

## Current Sync And Read Paths

- Protected result sync enters through `/api/cron/api-football-sync` and `/api/admin/api-football/sync`.
- Protected squad sync enters through `/api/cron/api-football-squad-sync` and `/api/admin/api-football/squads/sync`.
- API-Football retrieval is currently performed by backend helper functions in `backend/app.py`.
- Raw fixture and squad payload history is stored in API-Football history tables.
- Current match facts are read from `match_results`, `match_events`, `match_clean_sheets`, and `player_match_stats`.
- Participant app reads enter through `/api/world-cup`, `/api/pool`, and `/api/profiles/<user_id>/predictions`.
- Scored leaderboard categories are stored in `computed_points` after provider-backed or manual fact changes. Leaderboard and profile payloads read those stored rows when present.
- Admin-only sync issues are stored in `admin_sync_notifications` and surfaced through the existing notification bell.
- Account creation enters through `/api/auth/login` and must validate `firstname.lastname@talpanetwork.com` or `firstname.lastname@talpastudios.com`.
- Prize-pot participation is surfaced through `/api/pool` notifications and saved through an authenticated participant action.
- Tournament pick UI surfaces include prediction entry, prediction adjustment, and profile pick panels.

### Scenario 1: First post-match attempt only targets the due match

1. Set one match to be due for the first post-match result attempt.
2. Keep other matches before their sync window or already terminal.
3. Run the protected result sync.
4. Confirm only the due match is requested from the provider.
5. Confirm a sync attempt record exists for that match.

Expected result: unrelated completed history is not fetched.

### Scenario 2: Second post-match attempt updates partial facts

1. Seed or mock a first attempt with partial provider data.
2. Run the second attempt window for the same match.
3. Confirm raw history contains both payloads.
4. Confirm current provider-backed facts use newer values where no manual override exists.

Expected result: partial early data can be improved without losing audit history.

### Scenario 3: Manual override wins over provider update

1. Save a manual result, event, or player-stat correction as an admin.
2. Run a provider sync for the same match.
3. Confirm provider payload history is stored.
4. Confirm the manual fact remains the active scoring fact.
5. Confirm audit history identifies the manual change, source, actor, and reason.
6. If the match is not final, confirm participant scoring remains unchanged.

Expected result: provider updates do not undo admin corrections.

### Scenario 4: Manual override reversal

1. Start with a provider-backed fact.
2. Save a manual override.
3. Reverse the manual override.
4. Confirm the active scoring fact returns to the provider-backed value if available.

Expected result: overrides are reversible without editing predictions.

### Scenario 5: Missing provider fixture link

1. Make a match due for result sync without a provider fixture link.
2. Run result sync.
3. Confirm no result is published for that match.
4. Confirm a skipped `provider_sync_attempts` row exists.
5. Confirm admins receive a `sync_issue` notification.
6. Confirm repeating the same failure updates the active notification instead of creating duplicates.
7. Confirm normal users do not see provider error details.

Expected result: missing links are operationally visible but not user-facing errors.

### Scenario 6: Provider request failure

1. Link a due match to a provider fixture.
2. Make the provider request fail or omit that fixture from the response.
3. Run result sync.
4. Confirm a failed `provider_sync_attempts` row exists.
5. Confirm admins receive a `sync_issue` notification.
6. Confirm `/api/world-cup` and `/api/pool` do not expose provider error details.

Expected result: retrieval failures are admin-visible and participant-safe.

### Scenario 7: Stored computed points

1. Complete a match and sync result facts.
2. Confirm affected computed point rows are updated.
3. Load leaderboard and profile pages.
4. Confirm both surfaces show totals derived from the same stored computed points.

Expected result: leaderboard and profile scoring agree after recalculation.

### Scenario 7A: Automatic quiz label from provider facts

1. Add an `auto_label` resolver rule to a quiz question, such as `goal_before_minute` with `minute: 10`.
2. Sync a linked finished match whose provider-backed goal events satisfy the rule.
3. Confirm an automatic quiz label is stored with source `api-football`.
4. Confirm the effective quiz label has the resolved `correct_answers`.
5. Confirm `computed_points` rows for `quiz_points` are recalculated.
6. Load leaderboard and profile pages and confirm quiz points agree.

Expected result: API-answerable quiz questions are labeled and scored without manual admin entry.

### Scenario 7B: Manual quiz override wins over automatic label

1. Save a manual quiz label for a match as an admin.
2. Sync provider facts for the same match where the quiz resolver would produce a different answer.
3. Confirm the automatic label may be stored for audit/review, but the effective scoring label remains manual.
4. Confirm computed quiz points reflect the manual answer.

Expected result: admin quiz labels remain authoritative.

### Scenario 7C: Unsupported or insufficient quiz facts remain manual

1. Add or select a quiz question with no supported resolver rule, or one that requires statistics the provider did not return.
2. Sync the match.
3. Confirm no scoring quiz label is guessed.
4. Confirm admin review can see unsupported or insufficient-facts status where implemented.
5. Save a manual label and confirm quiz points recalculate.

Expected result: automatic resolution is conservative and never guesses low-confidence answers.

### Scenario 8: Talpa account creation

1. Open the login page.
2. Try `first.last@talpanetwork.com` with a valid password flow.
3. Confirm the account is created or loaded.
4. Try `first.last@talpastudios.com` with a valid password flow.
5. Try `first@talpastudios.com`.
6. Try `first.middle.last@talpastudios.com`.
7. Try `first.last@example.com`.
8. Confirm invalid emails are rejected by frontend validation and backend validation.
9. Try uppercase and whitespace around a valid Talpa email.

Expected result: only normalized `firstname.lastname@talpanetwork.com` and `firstname.lastname@talpastudios.com` accounts are accepted, and casing/whitespace do not create duplicates.

### Scenario 9: Prize-pot notification and profile status

1. Log in as a participant with no prize-pot answer.
2. Confirm the notification bell includes a prize-pot prompt.
3. Confirm the prompt states the EUR 10 contribution, the prize amount is still to be determined, and Olivier Thijsen organizes payment outside the app.
4. Choose to join.
5. Reload `/api/pool` or return to the website.
6. Confirm the prize-pot prompt no longer appears.
7. Open the participant's profile from the leaderboard.
8. Confirm the profile shows that the participant joined.
9. Repeat with another participant choosing decline.

Expected result: each participant is asked until they answer, and saved participation is visible on profiles without payment handling.

### Scenario 10: Tournament picks are view-first

1. Save champion, top-scorer, and five striker picks before lock.
2. Return to the prediction screen.
3. Confirm the tournament pick component opens in view mode.
4. Confirm champion shows a flag.
5. Confirm top scorer and striker rows show full names plus country flag/country when metadata is available.
6. Click inside the component without pressing edit.
7. Confirm no saved pick changes.
8. Press the edit button while picks are unlocked.
9. Confirm editable controls appear and saving still uses existing lock validation.
10. Open another participant's profile and confirm their visible picks use the same richer display.

Expected result: picks are readable and visually clear in view mode, and only explicit edit mode can change them.

### Scenario 11: Tournament pick metadata fallback

1. Seed or save a striker/top-scorer name that is not present in squad metadata.
2. Open the pick summary.
3. Confirm the stored name is still shown.
4. Confirm the UI does not display an incorrect flag/country.

Expected result: existing plain-name predictions remain valid even when player metadata cannot be resolved.

## Production Notes

- Production still depends on `DATABASE_URL` or `POSTGRES_URL`.
- Vercel cron timing is approximate. The cron may run more often than match windows; app-level sync candidate selection enforces the 5-minute, 15-minute, and 2-hour post-match windows and records terminal attempts.
- Result sync fetches only the relevant due match fixtures. Squad sync remains a separate rare job.
- Provider errors should be logged and surfaced to admins, not normal participants.
- Automatic quiz resolution should run only after normalized facts are stored and should not run from participant-facing reads.
- Prize-pot payment collection remains outside the app; the app stores only join/decline state.
- Talpa email validation should be reviewed carefully before deploy because changing accepted domains can affect existing users.
