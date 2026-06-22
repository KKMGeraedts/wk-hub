# API and UI Contract: GenAI Service

## Deep Module Interface Contract

`backend.genai_service` is the sole module callers use for GenAI behavior. Its public interface is limited to workflow-level operations and read projections:

- run eligible GenAI Jobs after a completed data-sync workflow;
- apply accepted automatic Quiz Labels while preserving manual precedence;
- expose accepted player links to scoring;
- build GenAI status for admin label projections;
- process an admin Quiz Answer review.

Callers provide an open DB-API connection and app-owned match data. Production provider configuration is read inside the module. Tests may inject a structured-completion callable. The module returns plain dictionaries and change metadata; it does not return Flask responses or import Flask route code.

Rules:

- `backend.genai_service` must not import `backend.app`.
- Flask routes and sync workflows must not call prompt, validator, provider, or GenAI persistence helpers directly.
- Internal helper names are not compatibility contracts.
- Existing HTTP paths, status codes, request bodies, and response payloads below remain unchanged.
- Provider calls occur only from explicit execution operations, never from projection helpers.

## GenAI Execution Contract

GenAI execution is internal to sync, admin, and scoring-publication workflows. It must not run from participant-facing reads.

### Provider configuration

Configuration should support:

- provider key, initially `mistral`
- API key secret
- model name
- timeout seconds
- enabled/disabled state

Rules:

- Missing or disabled provider configuration causes attempted jobs to fail closed.
- Provider errors are not exposed to participants.
- Provider-specific code stays behind the GenAI Service boundary.

### Shared job output shape

All GenAI Jobs should return structured JSON that can be validated before domain state changes:

```json
{
  "status": "answered",
  "confidence": "high",
  "reason": "The first goal event is recorded at minute 6.",
  "evidence": [
    {"type": "match_event", "id": "event-key-1"}
  ]
}
```

Rules:

- Free-form text alone is never accepted.
- Invalid JSON or missing required fields produces a rejected/failed job status.
- Evidence must refer to facts or candidates supplied in the job input.

## Quiz Answer Job Contract

### Input

```json
{
  "job_type": "quiz_answer_from_match_facts",
  "match_id": "m009",
  "question": "Komt er een doelpunt in de eerste 10 minuten?",
  "answer_options": ["ja", "nee"],
  "facts": {
    "result": {"home_score": 2, "away_score": 1, "status_short": "FT"},
    "events": [
      {
        "id": "event-key-1",
        "elapsed": 6,
        "event_type": "Goal",
        "detail": "Normal Goal",
        "player_name": "Cody Gakpo",
        "local_team_id": "ned"
      }
    ],
    "clean_sheets": [],
    "player_stats": []
  }
}
```

### Accepted output

```json
{
  "status": "answered",
  "selected_answers": ["ja"],
  "confidence": "high",
  "reason": "A goal event is recorded in minute 6.",
  "evidence": [
    {"type": "match_event", "id": "event-key-1"}
  ]
}
```

Rules:

- `selected_answers` must match existing answer options after normal answer normalization.
- `confidence` must be `high`.
- `evidence` must reference supplied facts.
- Accepted output creates or updates an automatic quiz label below manual override precedence.
- Accepted label changes trigger computed point recalculation.
- Manual quiz labels in `quiz_label_overrides` remain authoritative.
- Participant `quiz_predictions` rows are never changed.

### Rejected output

```json
{
  "status": "insufficient_evidence",
  "selected_answers": [],
  "confidence": "low",
  "reason": "The supplied facts do not include VAR decisions.",
  "evidence": []
}
```

Rules:

- Invalid, low-confidence, unsupported, or insufficient-evidence output must not score participants.
- Rejected output creates or updates an admin sync issue for the match quiz.
- If a manual quiz override already exists, the GenAI result may be stored for review but must not affect the effective label.

## Player Matching Job Contract

### Input

```json
{
  "job_type": "player_match_from_candidates",
  "target_type": "match_scorer",
  "target_id": "m012:omar-rekik",
  "raw_player_name": "Omar Rekik",
  "match_id": "m012",
  "local_team_id": "swe",
  "candidates": [
    {
      "candidate_id": "api:1",
      "api_player_id": 1,
      "player_name": "O. Rekik",
      "local_team_id": "swe"
    }
  ]
}
```

### Accepted output

```json
{
  "status": "matched",
  "matched_candidate_id": "api:1",
  "confidence": "high",
  "reason": "The full first name and surname align with the abbreviated squad name.",
  "evidence": [
    {"type": "candidate", "id": "api:1"}
  ]
}
```

Rules:

- Job runs only after deterministic player matching fails.
- `matched_candidate_id` must be in the supplied candidate list.
- The matched player must already exist in the squad-player database.
- Accepted output creates a player candidate link and preserves the original scorer/striker name.
- Accepted output must not change participant prediction rows.

### Rejected output

```json
{
  "status": "ambiguous",
  "matched_candidate_id": null,
  "confidence": "low",
  "reason": "Two candidates share the same surname and initial.",
  "evidence": [
    {"type": "candidate", "id": "api:1"},
    {"type": "candidate", "id": "api:2"}
  ]
}
```

Rules:

- Ambiguous, no-match, outside-candidate, low-confidence, or invalid output must not create a player candidate link.
- Rejected output creates or updates an admin sync issue.

## Admin Label Payload

`GET /api/admin/labels` may include GenAI status alongside existing result, quiz, event, and player-stat labels:

```json
{
  "match_id": "m009",
  "quiz": {
    "question": "Komt er een doelpunt in de eerste 10 minuten?",
    "correct_answers": ["ja"],
    "source": "genai:mistral",
    "genai": {
      "job_type": "quiz_answer_from_match_facts",
      "status": "accepted",
      "provider_key": "mistral",
      "model": "configured-model",
      "confidence": "high",
      "evidence": [{"type": "match_event", "id": "event-key-1"}],
      "resolved_at": "2026-06-15T00:00:00Z"
    },
    "manual_override_active": false
  }
}
```

The same response also includes a compact provider/job summary:

```json
{
  "genai": {
    "provider_key": "mistral",
    "model": "configured-model",
    "enabled": true,
    "disabled_reason": null,
    "job_counts": {"accepted": 2, "rejected": 1}
  }
}
```

Goal-event and player-stat rows may include an accepted player link:

```json
{
  "player_name": "Gakppo",
  "genai_link": {
    "job_type": "player_match_from_candidates",
    "status": "accepted",
    "source": "genai:mistral",
    "confidence": "high",
    "raw_player_name": "Gakppo",
    "matched_player_name": "Cody Gakpo",
    "evidence": [{"type": "candidate", "id": "ned:1"}]
  }
}
```

Rules:

- Existing `PATCH /api/admin/labels/<match_id>/quiz` remains the manual override endpoint.
- When a manual override exists, payloads should make that precedence visible.
- Successful GenAI status should be visible to admins but should not create notification-bell noise.
- Normal participant payloads do not need GenAI evidence or provider details.

## Admin Notification Contract

GenAI failures use the existing admin sync notification surface.

Required notification cases:

- GenAI provider disabled or unconfigured when a job is attempted.
- Provider call failure or timeout.
- Invalid structured output.
- Quiz answer has low confidence, unsupported status, or insufficient evidence.
- Quiz answer selects an answer outside the allowed options.
- Player matching output is ambiguous, low confidence, outside the candidate list, or no match.

Rules:

- Only admins receive these notifications.
- Duplicate active notifications for the same target and issue type should be avoided.
- Notifications should resolve when the target becomes accepted or manually fixed.
