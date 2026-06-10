# Research: API Data Sync

## Decision: Keep sync as background infrastructure

**Rationale**: Normal participants should not trigger provider calls or see provider internals. Participant views should read app-owned schedule, labels, and stored computed scoring data.

**Alternatives considered**:

- Fetch provider data during participant page loads: rejected because it couples user traffic to external API reliability and risks inconsistent privacy/scoring behavior.
- Show detailed provider status to all users: rejected for this scope because the requested behavior is background infrastructure only.

## Decision: Introduce an internal provider boundary first

**Rationale**: The existing backend is a monolithic Flask file deployed through Vercel. A clear internal boundary can be created with provider adapter, scheduling, normalization, storage, and scoring-publication helpers before deciding whether separate modules are worth the packaging risk.

**Alternatives considered**:

- Build a separate sync service: rejected as unnecessary operational complexity for the current app.
- Keep all API-Football logic interleaved with app routes: rejected because the feature explicitly asks for a clearer boundary and future provider option.

## Decision: Use per-match post-match result attempts

**Rationale**: Result sync should run for only the relevant match after it has been played. The accepted timing is one attempt around 15 minutes after the match and a second around 2 hours after the match. This supports partial early data and later corrections without re-fetching full history.

**Alternatives considered**:

- Daily completed-history sweep: rejected because it asks the provider for too much unrelated history and updates late.
- Continuous live polling: rejected because live data is out of scope and user preference is post-match only.
- Ongoing final-result rechecks: rejected because user preference is exactly the two attempts unless future manual correction scope is added.

## Decision: Keep squad sync separate and rare

**Rationale**: Squads are expected to be largely fixed for tournament usage, and the user explicitly does not want squad sync on the regular result cadence.

**Alternatives considered**:

- Sync squads daily: rejected because it spends provider calls on mostly fixed data.
- Merge squad and result sync into one workflow: rejected because they have different timing, target type, and operational expectations.

## Decision: Store raw history forever and maintain normalized current facts

**Rationale**: Permanent raw payload history supports audit and parser replay. Normalized current facts keep app scoring and reads simple.

**Alternatives considered**:

- Store only normalized facts: rejected because disputes and parser bugs would be hard to investigate.
- Score directly from raw provider payloads: rejected because scoring would become provider-shape dependent and harder to test.

## Decision: Manual overrides win until reversed

**Rationale**: Admin corrections are explicit operational decisions. Provider updates may continue to arrive but must not overwrite facts an admin intentionally corrected.

**Alternatives considered**:

- Always let newest provider data win: rejected because it can undo admin corrections.
- Copy manual values into participant predictions: rejected because participant prediction rows must never be mutated by label/scoring administration.

## Decision: Store computed points after scoring facts change

**Rationale**: Stored computed points make leaderboard/profile reads consistent and auditable after provider data or manual labels change. Recalculation should be scoped to affected matches/categories.

**Alternatives considered**:

- Continue recomputing everything on read: rejected for this feature because manual overrides and provider revisions need a stable scoring output to inspect.
- Store only total leaderboard points: rejected because category-level records are needed to explain affected scoring and support profiles.

## Decision: Use admin notifications for sync failures

**Rationale**: Missing fixture links and provider retrieval failures should be visible to admins without exposing provider internals to normal participants. The app already has notification-bell infrastructure that can carry admin-targeted operational messages.

**Alternatives considered**:

- Logs only: rejected because admins need in-app signal.
- Public user-facing errors: rejected because users should see pending/blank results, not provider failure details.

## Decision: Do not add a separate app-managed request limit

**Rationale**: The requested per-match two-attempt schedule is already a strong boundary. Provider/account-level limits still exist, but the app should not create an additional daily budget feature for this scope.

**Alternatives considered**:

- Keep current app daily request cap as a primary scheduling control: rejected because schedule discipline should determine when requests happen.
- Admin-adjustable request limits: rejected as unnecessary for the requested behavior.
