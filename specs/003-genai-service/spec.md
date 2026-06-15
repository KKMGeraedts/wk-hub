# Feature Specification: GenAI Service

**Feature Branch**: `[003-genai-service]`

**Created**: 2026-06-15

**Status**: Draft

**Input**: User description: "Add an agentic layer to the app. Use Mistral as the LLM provider while keeping the framework provider agnostic. Use-case 1: answer quiz questions given match data from data-sync; the LLM interprets what happened and admins get notified when this does not work. Use-case 2: when striker/player database and match-data scorer cannot be matched with regex, use a quick LLM call as the last try; admins get notified if it does not work. Call the layer GenAI Service and the bounded use-cases GenAI Jobs. Admins must still be able to overwrite automatic quiz labels with the existing admin panel tool."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Answer Quiz From Match Facts (Priority: P1)

As an admin, I want match quiz questions to be answered automatically from synced match data when the answer can be proven, so that scoring can move forward without manual label entry for every quiz.

**Why this priority**: Quiz labels affect participant scoring and are currently a manual bottleneck when deterministic resolver metadata is not enough or would take too much setup per question.

**Independent Test**: Can be tested by syncing a completed match with normalized facts, running the quiz GenAI Job, and confirming a valid answer is accepted only when it matches an existing option and cites supplied match evidence.

**Acceptance Scenarios**:

1. **Given** a completed match has normalized match facts and a quiz with answer options, **When** the quiz GenAI Job can prove one option from those facts, **Then** the system stores an automatic quiz label that can be used for scoring.
2. **Given** the GenAI Job returns an answer that is not one of the quiz options, **When** the output is validated, **Then** no scoring label is created and admins are notified.
3. **Given** the GenAI Job cannot prove the answer from supplied match facts, **When** the job completes, **Then** the quiz remains unresolved and admins are notified to label it manually.
4. **Given** an admin manually overwrites a GenAI-produced quiz label in the existing admin panel, **When** scoring is recalculated, **Then** the manual label remains authoritative.

---

### User Story 2 - Match Players After Deterministic Matching Fails (Priority: P2)

As an admin, I want unmatched scorer or striker names to get one final GenAI-assisted match attempt against existing player database candidates, so that small naming differences do not create avoidable manual work.

**Why this priority**: Scorer and striker scoring depends on player identity. Deterministic matching should stay first, but a bounded GenAI fallback can resolve names that humans would recognize quickly.

**Independent Test**: Can be tested by creating a scorer or striker name that deterministic matching rejects, providing a shortlist of existing player candidates, and confirming the GenAI Job either links to one candidate or notifies admins.

**Acceptance Scenarios**:

1. **Given** a scorer name cannot be matched by player id, exact name, normalized name, or initial/surname rules, **When** the player matching GenAI Job receives a candidate shortlist, **Then** it may link the name to one existing player candidate.
2. **Given** the GenAI Job proposes a player outside the candidate list, **When** the output is validated, **Then** the proposed match is rejected and admins are notified.
3. **Given** multiple candidates remain plausible, **When** confidence is not high, **Then** no automatic player link is accepted and admins are notified.
4. **Given** a GenAI player link is accepted, **When** admins inspect the relevant match or player issue, **Then** the original source name remains visible for review.

---

### User Story 3 - Operate GenAI Safely (Priority: P3)

As an admin, I want GenAI successes to be visible and failures to appear as admin-only notifications, so that I can trust what was automated and intervene when needed.

**Why this priority**: GenAI should reduce manual work without hiding uncertainty or exposing provider errors to participants.

**Independent Test**: Can be tested by forcing one successful job and one failed or low-confidence job, then confirming admin review surfaces show the success while only the failure creates an active admin notification.

**Acceptance Scenarios**:

1. **Given** a GenAI Job succeeds, **When** an admin views the relevant label or player match area, **Then** the source, status, provider, and compact evidence are visible.
2. **Given** a GenAI Job fails, times out, returns invalid output, or has low confidence, **When** the job result is processed, **Then** admins receive a deduplicated notification and participants see no provider details.
3. **Given** a participant loads a public or pool page, **When** the page is rendered, **Then** no GenAI provider call is triggered.

### Edge Cases

- The LLM provider is not configured or unavailable.
- The normalized match facts are incomplete, contradictory, or missing the evidence needed to answer a quiz.
- The quiz has open-text or unusual answer options that cannot be safely selected from model output.
- The model returns valid JSON but chooses an answer without citing evidence from supplied facts.
- The player candidate shortlist is empty, too broad, or contains multiple near-duplicates.
- An admin manual quiz label conflicts with a GenAI-produced automatic label.
- A repeated failure for the same quiz or player target would otherwise create duplicate notifications.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a GenAI Service layer for bounded model-assisted work while keeping individual use-cases represented as GenAI Jobs.
- **FR-002**: The system MUST use Mistral as the initial LLM provider while keeping the GenAI Service provider-agnostic for future replacement.
- **FR-003**: The system MUST run GenAI Jobs only from sync, admin, or scoring-publication workflows, not from participant-facing reads.
- **FR-004**: The system MUST send only the smallest normalized data needed for each GenAI Job.
- **FR-005**: The system MUST NOT send raw provider payloads, participant prediction data, user identity data, passwords, or broad database context to the LLM provider.
- **FR-006**: The system MUST NOT store full prompts or raw model responses by default.
- **FR-007**: The system MUST keep compact GenAI status for accepted and rejected outcomes, including job type, target, provider/model, status, accepted output when present, compact evidence, failure code/message, and timestamps.
- **FR-008**: The quiz answer GenAI Job MUST receive the quiz question, answer options, and normalized match facts.
- **FR-009**: A quiz GenAI result MUST be accepted only when it selects existing answer options, has high confidence, and cites evidence from supplied match facts.
- **FR-010**: Invalid, low-confidence, unsupported, or insufficient-evidence quiz results MUST leave the quiz unresolved and create an admin-only notification.
- **FR-011**: GenAI-produced quiz labels MUST NOT update participant quiz prediction rows.
- **FR-012**: Manual quiz labels saved through the existing admin panel MUST take precedence over GenAI-produced automatic labels.
- **FR-013**: Admins MUST be able to overwrite a GenAI-produced quiz label using the existing admin quiz label editor.
- **FR-014**: Accepted GenAI quiz labels MUST trigger the same affected scoring recalculation behavior as other automatic quiz label changes.
- **FR-015**: The player matching GenAI Job MUST run only after deterministic player matching fails.
- **FR-016**: The player matching GenAI Job MUST choose only from existing player database candidates and MUST NOT invent a player.
- **FR-017**: A player matching GenAI result MUST be rejected when it is ambiguous, low-confidence, outside the candidate list, or invalid.
- **FR-018**: Failed or rejected player matching GenAI results MUST create admin-only notifications.
- **FR-019**: Accepted player matching results MUST preserve the original scorer or striker name for review.
- **FR-020**: Successful GenAI Jobs SHOULD be visible in admin review surfaces but MUST NOT create notification-bell noise.
- **FR-021**: GenAI failure notifications MUST be deduplicated by target and issue type while the issue remains active.

### Key Entities

- **GenAI Service**: The app layer that calls an LLM provider for bounded support work.
- **GenAI Job**: A single bounded use-case handled by the GenAI Service with known input, output, validation, and failure handling.
- **Quiz Answer Job**: A GenAI Job that answers a match quiz from question text, answer options, and normalized match facts.
- **Player Matching Job**: A GenAI Job that links an unmatched scorer or striker name to one existing player candidate after deterministic matching fails.
- **Automatic Quiz Label**: A scoring label produced automatically below manual admin override priority.
- **Admin Sync Issue**: An admin-only notification that a GenAI Job or supporting sync step needs manual attention.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 90% of GenAI-produced quiz labels accepted by validation can be reviewed by admins with visible source, status, and compact evidence.
- **SC-002**: 100% of invalid, low-confidence, or insufficient-evidence GenAI quiz outputs leave scoring unchanged and create an admin-only notification.
- **SC-003**: 100% of GenAI player matching outputs are constrained to existing player candidates; no accepted result creates a new player identity.
- **SC-004**: Participant-facing page loads trigger zero GenAI provider calls.
- **SC-005**: Manual admin quiz overrides win over GenAI automatic labels in 100% of tested scoring cases.
- **SC-006**: Repeated unresolved GenAI failures for the same target create one active admin notification rather than duplicate active notifications.

## Assumptions

- Data-sync continues to own provider retrieval and normalized match facts.
- The GenAI Service consumes normalized match facts and player candidates produced elsewhere; it does not fetch football data itself.
- Admins continue using the current admin panel for manual quiz label edits.
- The first two GenAI Jobs are quiz answering from match facts and player matching from candidates.
- Full prompt/response retention is out of scope unless a later debug mode is requested.
