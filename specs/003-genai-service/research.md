# Research: GenAI Service

## Decision: Use a provider-agnostic GenAI Service with Mistral as the first provider

**Rationale**: The feature explicitly selects Mistral but also requires provider agnosticism. A small internal client boundary lets workflow code call `run_genai_job(...)` without knowing provider endpoint details, request headers, or model names. This also centralizes timeout, disabled-state, and error handling.

**Alternatives considered**:

- Call Mistral directly from quiz and player matching workflows: rejected because it duplicates provider handling and makes provider replacement harder.
- Add a broad multi-agent framework: rejected because both initial use-cases are single-step bounded jobs, not autonomous planning workflows.

## Decision: Require structured JSON output plus deterministic validation

**Rationale**: GenAI output can affect scoring, so free-form answers are not acceptable. Each job gets a strict expected output shape and workflow-specific validation. Quiz answers must match existing options and cite supplied facts. Player matches must choose an existing candidate.

**Alternatives considered**:

- Trust model confidence/explanation alone: rejected because scoring changes need deterministic acceptance gates.
- Require admin approval for every successful result: rejected because the feature goal is to reduce manual admin work while keeping failures visible.

## Decision: Send minimal normalized inputs only

**Rationale**: Match facts and player candidates are enough for the two supported jobs. Raw provider payloads, participant predictions, user identity data, passwords, and broad database context increase privacy exposure without improving the bounded decision.

**Alternatives considered**:

- Send raw API-Football payloads for richer context: rejected because normalized facts are the app-owned scoring boundary.
- Send participant predictions to tailor scoring context: rejected because participant data is unnecessary and sensitive.

## Decision: Do not store full prompts or raw model responses by default

**Rationale**: Admins need to know what happened, not retain every provider exchange. Compact job status, accepted output, compact evidence, failure code/message, provider/model, and timestamps are enough for normal operations.

**Alternatives considered**:

- Store every request and response: rejected because it increases retention and privacy risk.
- Store only accepted labels/links: rejected because admins also need visibility into failures and low-confidence outcomes.

## Decision: Run GenAI Jobs only from sync/admin/scoring-publication workflows

**Rationale**: Existing provider sync design already keeps external calls out of participant reads. GenAI should follow the same boundary so participant pages remain predictable, fast, and side-effect-free.

**Alternatives considered**:

- Trigger GenAI lazily when a participant opens a page: rejected because it adds external calls and writes to read paths.
- Run GenAI continuously in a separate queue: deferred because current app is a Vercel/Flask monolith and the initial scope can run from existing sync/admin triggers.

## Decision: Quiz GenAI Jobs can interpret question text, with evidence validation

**Rationale**: The user wants every quiz to be attempted by the GenAI Job using question, options, and match data. This reduces per-question setup, while evidence validation prevents unsupported guesses from affecting scoring.

**Alternatives considered**:

- Keep explicit deterministic `auto_label` metadata as the only path: rejected for this separate GenAI feature because it would not satisfy the broad quiz-answering use-case.
- Accept any high-confidence option: rejected because confidence must be grounded in supplied facts.

## Decision: Player GenAI Jobs create links, not source-name rewrites

**Rationale**: The original scorer/striker text remains important for audit and admin review. Accepted GenAI output should link that raw name to an existing player candidate instead of mutating the source event/stat/prediction text.

**Alternatives considered**:

- Rewrite `match_events.player_name` or striker prediction names: rejected because it hides source data and makes later disputes harder.
- Let GenAI create new player records: rejected because the job is a matcher, not a player database authority.

## Decision: Reuse admin sync notifications for GenAI failures

**Rationale**: The app already has deduplicated admin-only sync issues in `admin_sync_notifications` and exposes them through the notification bell. GenAI failures are operational scoring-data issues and fit that model.

**Alternatives considered**:

- Add a separate notification system: rejected because it would duplicate admin notification behavior.
- Show GenAI failures only in admin label pages: rejected because admins need active notification when automation cannot resolve scoring work.
