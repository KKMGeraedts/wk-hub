# Data Model: GenAI Service

## Existing Entities To Preserve

### Normalized Match Fact

App-owned football facts used by scoring and inspection.

Current storage:

- `match_results`
- `match_events`
- `match_clean_sheets`
- `player_match_stats`

Validation:

- GenAI Jobs may read compact normalized facts but must not read or send raw provider payloads.
- If facts are missing or contradictory, GenAI output must not become a scoring fact unless evidence validation passes.

### Static Quiz Definition

Represents a quiz question attached to a match.

Current storage: `backend/quiz-2026.json`

Existing fields:

- `question`
- `type`
- `choices`
- `correct_answer` or `correct_answers`
- optional point fields

Validation:

- Quiz GenAI Jobs receive question text and answer options.
- Accepted GenAI answers must match existing options after normal answer normalization.

### Manual Quiz Override

Admin-authored quiz label that takes precedence over automatic labels.

Current storage: `quiz_label_overrides`

Validation:

- Manual labels must remain authoritative over GenAI-produced labels.
- Existing admin quiz label editor remains the manual overwrite tool.

### Admin Sync Issue

Admin-only operational issue surfaced through the notification bell.

Current storage: `admin_sync_notifications`

Validation:

- GenAI failures, invalid output, low confidence, insufficient evidence, and ambiguous player matches should create deduplicated active notifications.
- Successful GenAI Jobs should be visible in admin review surfaces but should not create notification-bell noise.

## New Or Extended Entities

### GenAI Service

Application layer that calls an LLM provider for bounded support work.

Fields/configuration:

- `provider_key`: initially `mistral`
- `model`: configured model name
- `api_key`: secret, configured through environment
- `timeout_seconds`
- `enabled`: derived from provider configuration

Validation:

- Provider details must stay behind a small client boundary.
- Disabled or unconfigured service must fail closed and create admin-visible status when a job is attempted.
- Participant-facing reads must never call the service.

### GenAI Job Result

Compact status record for a single GenAI Job outcome.

Recommended storage: new `genai_job_results` table, or equivalent compact fields if implementation finds an existing table more appropriate.

Fields:

- `id`
- `job_type`: `quiz_answer_from_match_facts` or `player_match_from_candidates`
- `target_type`: `match_quiz`, `match_scorer`, or `striker_pick`
- `target_id`: stable target identifier such as match id or notification target id
- `provider_key`
- `model`
- `status`: `accepted`, `rejected`, `failed`, `skipped_manual_override`, `disabled`
- `failure_code`
- `failure_message`
- `accepted_output_json`: compact accepted answer/link when present
- `evidence_json`: compact supplied-fact or candidate evidence used to justify acceptance
- `input_hash`: hash of canonical minimal input, not full prompt text
- `created_at`
- `updated_at`

Validation:

- Full prompts and raw provider responses are not stored by default.
- Accepted output must pass the job-specific validation before it is stored as accepted.
- Rejected and failed results should preserve enough status to explain admin notifications.

State transitions:

1. `accepted`: job output passed schema and domain validation.
2. `rejected`: provider output was valid enough to parse but failed confidence/evidence/domain validation.
3. `failed`: provider call failed, timed out, or output could not be parsed.
4. `skipped_manual_override`: job was not applied because a manual quiz label is active.
5. `disabled`: GenAI provider is not configured or disabled.

### GenAI Automatic Quiz Label

Automatic quiz label produced by the `quiz_answer_from_match_facts` GenAI Job.

Recommended storage:

- Add a focused `quiz_auto_labels` table, or extend the automatic quiz-label table introduced by the data-sync feature.

Fields:

- `match_id`
- `source`: for example `genai:mistral`
- `job_result_id`
- `correct_answers_json`
- `confidence`: `high`
- `facts_revision_key`
- `evidence_json`
- `resolved_at`
- `updated_at`

Relationships:

- References a match id from the static schedule.
- References the accepted GenAI Job Result.
- Feeds effective quiz labels below `quiz_label_overrides`.

Validation:

- Must not update participant `quiz_predictions`.
- Must not overwrite or replace manual quiz overrides.
- Must select existing answer options.
- Must trigger computed quiz point recalculation when the effective label changes.

### Player Candidate Link

Mapping from an unresolved raw scorer/striker name to one existing squad-player candidate.

Recommended storage: new `player_candidate_links` table or equivalent compact mapping.

Fields:

- `id`
- `target_type`: `match_scorer` or `striker_pick`
- `target_id`: match/player target identifier
- `raw_player_name`
- `matched_local_team_id`
- `matched_api_player_id`
- `matched_player_name`
- `source`: `genai:mistral`
- `job_result_id`
- `confidence`: `high`
- `evidence_json`
- `created_at`
- `updated_at`

Relationships:

- References an accepted GenAI Job Result.
- Points to an existing player in `team_squad_players`.
- Does not rewrite `match_events`, `player_match_stats`, or participant prediction names.

Validation:

- Candidate links can be created only after deterministic matching fails.
- Matched player must be one of the supplied candidates.
- Ambiguous, outside-candidate, low-confidence, or invalid output must not create a link.

### Quiz Answer Job

GenAI Job that answers a match quiz from question text, answer options, and normalized match facts.

Input fields:

- `match_id`
- `question`
- `answer_options`
- `facts`: compact normalized facts from result, events, clean sheets, and player stats

Output fields:

- `selected_answers`
- `confidence`
- `evidence`
- `reason`

Validation:

- Output must be parseable structured JSON.
- Selected answers must match existing answer options.
- Confidence must be high.
- Evidence must reference supplied facts.
- Unsupported or insufficient-fact output creates an admin sync issue.

### Player Matching Job

GenAI Job that links an unmatched scorer/striker name to an existing squad-player candidate.

Input fields:

- `raw_player_name`
- `target_type`
- `target_id`
- `match_id`, if known
- `local_team_id`, if known
- `candidates`: short list of existing squad players

Output fields:

- `matched_candidate_id`
- `confidence`
- `evidence`
- `reason`

Validation:

- Output must be parseable structured JSON.
- Matched candidate id must exist in the supplied candidate list.
- Confidence must be high.
- Ambiguous or no-match output creates an admin sync issue.
