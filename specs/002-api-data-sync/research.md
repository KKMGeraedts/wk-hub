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

**Rationale**: Result sync should run for only the relevant match after it has been played. The accepted timing is one attempt around 5 minutes after the match, another around 15 minutes after the match, and a final regular attempt around 2 hours after the match. This supports partial early data and later corrections without re-fetching full history.

**Alternatives considered**:

- Daily completed-history sweep: rejected because it asks the provider for too much unrelated history and updates late.
- Continuous live polling: rejected because live data is out of scope and user preference is post-match only.
- Ongoing final-result rechecks: rejected because user preference is a bounded set of planned post-match attempts unless facts are still missing or a manual correction scope is used.

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

**Rationale**: The requested per-match post-match attempt schedule is already a strong boundary. Provider/account-level limits still exist, but the app should not create an additional daily budget feature for this scope.

**Alternatives considered**:

- Keep current app daily request cap as a primary scheduling control: rejected because schedule discipline should determine when requests happen.
- Admin-adjustable request limits: rejected as unnecessary for the requested behavior.

## Decision: Enforce Talpa Network and Talpa Studios account emails as the account boundary

**Rationale**: The user explicitly requested account creation for Talpa participants using either `firstname.lastname@talpanetwork.com` or `firstname.lastname@talpastudios.com`. The existing login flow already creates missing accounts and validates a first.last Talpa email format, so the least risky change is to update that validation in both backend and frontend and keep normalized email lookup case-insensitive.

**Alternatives considered**:

- Accept any Talpa-like domain: rejected because the request specifies only Talpa Network and Talpa Studios.
- Let users enter names separately and construct email addresses: rejected because email remains the account identifier and should be validated directly.
- Only validate on the frontend: rejected because backend validation is required for security and API consistency.

## Decision: Model prize-pot participation as persistent user state

**Rationale**: The prize-pot prompt must be asked until each participant chooses, and other users should see participation on profiles. A persistent per-user state supports `undecided`, `joined`, and `declined` without handling payment in the app.

**Alternatives considered**:

- Use a one-time notification dismissal: rejected because dismissing is not the same as choosing join or decline.
- Track actual payment status: rejected because payment to Olivier Thijsen is explicitly outside the app.
- Store participation only in notification payloads: rejected because profiles need durable status.

## Decision: Use the existing notification bell for prize-pot prompts

**Rationale**: The app already has participant notification infrastructure for missing predictions and broadcasts. Extending that payload with a `prize_pot` action keeps the prompt visible on login/return without adding a new modal-only system.

**Alternatives considered**:

- Force a blocking modal on every login: rejected because the user asked for a notification and participants should remain free to decide.
- Put the question only on the profile page: rejected because users may not visit profile before making predictions.

## Decision: Make tournament picks view-first with explicit edit mode

**Rationale**: The user wants to inspect the entire pick component without accidental changes. View mode should render champion, top scorer, and strikers as readable summaries with flags/country context; edit mode should be entered only through an edit button and should obey existing lock rules.

**Alternatives considered**:

- Keep always-editable selects: rejected because clicks in the component can accidentally change values and the current striker purpose is unclear.
- Split champion/top-scorer/strikers into unrelated panels: rejected because they are a single tournament-pick workflow and should remain understandable as a component.

## Decision: Preserve plain-name player picks while enriching display with metadata

**Rationale**: Existing `top_scorer_predictions` rows store plain names. Backwards compatibility is required, while better display can be achieved by resolving names against static/synced squad/team data where available and falling back to the stored plain name.

**Alternatives considered**:

- Require player IDs for all existing picks immediately: rejected because it would require migrating or invalidating existing predictions.
- Show flags only for champion teams: rejected because the requested improvement specifically includes strikers and top scorer names with flags/country.

## Decision: Use explicit quiz resolver metadata rather than natural-language parsing

**Rationale**: Quiz questions are written for humans in Dutch and are not a stable machine interface. A resolver rule such as `goal_before_minute` with parameters such as `minute: 10` is deterministic, testable, and reviewable. This lets the app clearly associate each question with the exact provider-backed facts needed to answer it.

**Alternatives considered**:

- Parse the question text and infer rule intent automatically: rejected because small wording changes could alter scoring behavior and make disputes hard to explain.
- Manually label all quiz questions after every match: rejected because several questions are directly answerable from synced facts and should not require repetitive admin work.
- Ask API-Football a quiz-specific question: rejected because the provider exposes raw football facts, not app-specific quiz semantics.

## Decision: Resolve quizzes from normalized app facts after sync

**Rationale**: The result sync already normalizes provider payloads into `match_results`, `match_events`, `match_clean_sheets`, and `player_match_stats`. Quiz resolution should consume those app-owned facts after they are stored, which keeps provider-specific shape behind the sync boundary and prevents participant reads from triggering external calls or writes.

**Alternatives considered**:

- Resolve directly from raw provider payload during request handling: rejected because it would couple scoring to provider payload shape and duplicate normalization logic.
- Resolve during participant page loads: rejected because participant reads must remain side-effect free and provider independent.
- Store only raw resolver output without normalized facts: rejected because admins need inspectable facts and existing scoring already reads normalized tables.

## Decision: Manual quiz labels win over provider-backed automatic labels

**Rationale**: Admin overrides are explicit scoring decisions. Automatic labels reduce work but should not overwrite a manual correction or a question that an admin intentionally interpreted differently.

**Alternatives considered**:

- Let latest provider-backed resolver output win: rejected because it could undo admin decisions silently.
- Prevent admins from overriding automatic quiz labels: rejected because some questions are ambiguous or provider data can be incomplete.
- Store automatic labels directly as manual overrides: rejected because source provenance would be lost.

## Decision: Start with a conservative resolver registry

**Rationale**: The first implementation should support only high-confidence rule families: goal timing, first/last scoring team, team scoring thresholds, player scoring, cards, penalties, clean sheets, substitutions where sufficient facts exist, and statistics-backed questions where the provider supplies the relevant stat. Unsupported or insufficient-fact questions should stay unresolved for manual labeling.

**Alternatives considered**:

- Implement every quiz question immediately: rejected because several questions require subjective, unavailable, or low-confidence facts such as FIFA man of the match, inside-post goals, or VAR-disallowed goals.
- Treat missing provider facts as a negative answer: rejected because absence of data is not the same as a verified `nee`.
- Use fuzzy matching for player/team names without metadata: rejected for initial scope because explicit team/player identifiers or normalized known names are safer for scoring.

## Decision: Recompute stored quiz points when automatic labels change

**Rationale**: Leaderboard and profile views read stored computed points when present. When a resolver creates or changes an effective quiz label, stored `quiz_points` must be refreshed so every surface agrees.

**Alternatives considered**:

- Wait for the next full result sync to recompute points: rejected because automatic quiz labels may be the only changed fact.
- Recompute quiz points only on read: rejected because this feature already chose stored computed points for consistency and auditability.
- Recompute only users who answered that match in the first pass: deferred because full recompute is simpler and current scale is small enough.
