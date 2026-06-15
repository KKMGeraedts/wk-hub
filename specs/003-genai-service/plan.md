# Implementation Plan: GenAI Service

**Branch**: `main` | **Date**: 2026-06-15 | **Spec**: `specs/003-genai-service/spec.md`

**Input**: Feature specification from `specs/003-genai-service/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Add a bounded GenAI Service to support two scoring-adjacent workflows: answer match quiz questions from normalized match facts, and match unresolved scorer/striker names to existing squad-player candidates after deterministic matching fails. Mistral is the initial LLM provider, but the backend should expose a provider-agnostic client boundary. GenAI outputs only affect scoring or player matching after strict validation; failures and low-confidence results create admin-only sync issues, while existing admin label tools remain authoritative.

## Technical Context

**Language/Version**: Python 3.12; JavaScript/React 19; Vite 7

**Primary Dependencies**: Flask 3.1.1, psycopg 3.2.13, React, React DOM, Vite. Add a minimal outbound HTTP helper for Mistral using the Python standard library unless implementation later justifies a small dedicated client dependency.

**Storage**: Existing SQLite local / Postgres production tables. Existing tables include `users`, prediction tables, `api_football_*`, `match_results`, `match_events`, `match_clean_sheets`, `player_match_stats`, `quiz_label_overrides`, `label_audit_log`, `computed_points`, and `admin_sync_notifications`. Add compact GenAI result/status storage without full prompt or raw response retention by default.

**Testing**: Existing checks via `.venv/bin/python -m unittest discover backend -p '*_test.py'`, `npm run build`, `npm run py:check`, and `npm run check`; targeted backend coverage should be added for the GenAI client boundary, quiz output validation, player-candidate validation, admin notification behavior, manual override precedence, and no GenAI calls from participant reads.

**Target Platform**: Web app running locally via Flask/Vite and production via Vercel serverless Python plus Vite static frontend.

**Project Type**: Full-stack web application with monolithic Flask backend and single-file React frontend.

**Performance Goals**: GenAI Jobs run only from sync/admin/scoring-publication workflows, never from participant reads. Job inputs are bounded to one match's normalized facts or one unresolved player name plus a short candidate list. Timeouts should fail closed and notify admins rather than blocking participant views.

**Constraints**: Use Mistral first while keeping provider replacement localized. Send only minimal normalized data to the LLM. Do not send raw provider payloads, participant predictions, user identity data, passwords, or broad database context. Do not store full prompts or raw model responses by default. Manual quiz labels remain highest priority. Participant prediction rows must not be changed by GenAI output.

**Scale/Scope**: Existing 2026 World Cup quiz set, match result sync, squad/player database, top-scorer/striker scoring, admin label/editor flows, stored computed points, and admin notifications.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The current constitution file is still a placeholder and defines no enforceable project-specific gates. General Spec Kit gates apply:

- Feature spec exists and has no unresolved `[NEEDS CLARIFICATION]` markers: PASS
- Plan avoids implementation before task generation: PASS
- No known privacy/security violation introduced by design: PASS
- GenAI inputs exclude raw provider payloads, participant predictions, user identity data, passwords, and broad database context: PASS
- Participant-facing reads do not trigger provider or GenAI calls: PASS
- Manual admin quiz labels remain higher priority than GenAI-produced automatic labels: PASS
- GenAI outputs must fail closed unless deterministic validation passes: PASS

Post-design re-check:

- Research decisions resolve technical unknowns: PASS
- Data model identifies GenAI Service, GenAI Job, automatic quiz label, player candidate link, and admin sync issue state: PASS
- Contracts define job inputs/outputs, admin review behavior, scoring behavior, and failure handling: PASS
- Quickstart defines validation and manual review paths for both GenAI Jobs: PASS

## Project Structure

### Documentation (this feature)

```text
specs/003-genai-service/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── api-and-ui-contract.md
├── tasks.md
└── checklists/
    ├── requirements.md
    └── genai.md
```

### Source Code (repository root)

```text
backend/
├── app.py                  # Current monolith: auth, routes, DB setup, scoring, provider sync, GenAI helpers, notifications
├── worldcup-2026.json      # Static match schedule and lock timing source
├── quiz-2026.json          # Static quiz questions and answer options
└── team-profiles-2026.json # Static/synced team profile fallback data

api/
└── index.py                # Vercel Flask entry point

frontend/
├── index.html
└── src/
    ├── main.jsx            # Login, notifications, predictions, profiles, admin UI
    └── styles.css

specs/003-genai-service/
└── ...                     # Feature planning artifacts
```

**Structure Decision**: Keep the current monolithic backend and single-file React frontend for this planning scope. Add internal helper boundaries inside `backend/app.py` for provider-agnostic GenAI client calls, GenAI Job input construction, output validation, compact result persistence, player candidate matching, automatic quiz label publication, admin notification creation, and computed point recalculation before considering physical module extraction.

## Complexity Tracking

This expansion adds an external LLM provider boundary and compact GenAI result state, but keeps the implementation inside existing backend/admin/scoring boundaries.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| GenAI quiz interpretation from question text | Lets every match quiz attempt automatic answering without per-question deterministic resolver metadata | Pure deterministic metadata is safer but requires manual resolver setup for every quiz shape and was split into the data-sync feature |
| Provider-agnostic GenAI client with Mistral first | Allows the first provider to be swapped without rewriting job validation and scoring logic | Calling Mistral inline from each workflow would duplicate privacy, timeout, and validation behavior |
| Compact GenAI result storage | Needed to show admins accepted/rejected job status without retaining full prompts or raw model responses | Full request/response history would aid debugging but stores more data than needed for normal operations |
| Player candidate link metadata | Needed to preserve original scorer/striker names while letting scoring use a matched existing player | Rewriting source names would be harder to audit and could hide provider/admin input issues |

## Phase 0: Research Summary

Research output: `specs/003-genai-service/research.md`

Key decisions:

- Implement a provider-agnostic GenAI Service boundary with Mistral as the first provider.
- Use structured JSON outputs plus deterministic validation; never trust free-form model text directly.
- Run GenAI Jobs only from sync/admin/scoring-publication paths, never participant-facing reads.
- Send minimal normalized inputs only, and do not store full prompts or raw model responses by default.
- Store compact accepted/rejected job status and compact evidence on purpose-built tables or fields.
- Treat quiz answering as a GenAI Job that can interpret question text, but only accepts answers that match existing options and cite supplied match facts.
- Treat player matching as a last fallback after deterministic matching fails; it can choose only from existing squad-player candidates and must preserve the original name.
- Reuse existing admin sync notifications for failed, invalid, ambiguous, or low-confidence GenAI outcomes.
- Reuse existing admin quiz label editor for manual overrides and keep manual labels authoritative.

## Phase 1: Design Summary

Design outputs:

- `specs/003-genai-service/data-model.md`
- `specs/003-genai-service/contracts/api-and-ui-contract.md`
- `specs/003-genai-service/quickstart.md`

Design notes:

- Add GenAI configuration such as provider key, API key, model, timeout, and disabled/enabled state.
- Add a provider-neutral call shape that accepts a job type, input JSON, and expected output schema.
- Add compact `genai_job_results` status storage or equivalent fields for accepted/rejected job outcomes, without full prompt/response retention.
- Add `quiz_auto_labels` or extend the automatic quiz-label state from the data-sync feature so `genai:mistral` labels sit below manual `quiz_label_overrides`.
- Add `player_candidate_links` or equivalent mapping so raw scorer/striker names can link to an existing squad-player candidate without rewriting source names.
- Admin label payloads should show GenAI status, source, provider/model, compact evidence, and manual override precedence.
- Existing notification bell can show GenAI failures through `admin_sync_notifications` with deduplication by target and issue type.
- Accepted quiz labels should trigger the same computed point recalculation path as manual or provider-backed label changes.

## Validation Strategy

Automated validation after implementation:

```bash
.venv/bin/python -m unittest discover backend -p '*_test.py'
npm run build
npm run py:check
npm run check
```

Targeted backend tests should cover:

- GenAI disabled/unconfigured state creates admin-visible failure without participant exposure.
- Mistral client boundary is mocked in tests and receives minimal normalized inputs.
- Quiz GenAI output must be valid JSON, select existing answer options, have high confidence, and cite supplied facts.
- Invalid, low-confidence, unsupported, or insufficient-evidence quiz outputs do not score and create admin notifications.
- Manual quiz override wins over a GenAI-produced automatic label.
- Accepted GenAI quiz label triggers computed quiz point recalculation.
- Player matching GenAI Job runs only after deterministic matching fails.
- Player matching output can select only one existing candidate and preserves the original name.
- Ambiguous/outside-candidate/invalid player matching outputs create admin notifications.
- Participant `/api/world-cup`, `/api/pool`, and profile reads do not trigger GenAI calls or writes.

Manual review scenarios are documented in `specs/003-genai-service/quickstart.md`.
