# Research: WK Hub Fixes

## Decision 1: Use existing lock semantics as the source of truth

**Decision**: Tournament-pick lock and reveal should use the app's existing tournament start lock calculation: 1 hour before the first scheduled tournament match. Per-match prediction visibility should use each match's existing prediction lock calculation.

**Rationale**: The requested business rule matches the existing lock language used by participants. Reusing the same lock moments avoids divergent privacy/editability behavior.

**Alternatives considered**:

- Hardcode 11 June as a separate reveal timestamp: rejected because the schedule data already defines the first match and hardcoding creates drift risk.
- Reveal only after match kickoff: rejected because the user explicitly requested visibility when predictions are no longer adjustable, 1 hour before kickoff.

## Decision 2: Treat tournament pick privacy as backend-enforced masking

**Decision**: Hidden champion, top scorer, and striker names must not be included in response data for other participants before reveal. Frontend display rules are secondary UX safeguards.

**Rationale**: UI-only hiding would still expose private picks to anyone inspecting network responses. Privacy must be enforced at the data returned for leaderboard/profile surfaces.

**Alternatives considered**:

- Hide only in the frontend: rejected due to privacy leakage.
- Hide all leaderboard rows before reveal: rejected because the requested secrecy is limited to tournament-pick and not general ranking visibility.

## Decision 3: Keep leaderboard focused on ranking, move detailed tournament pick reveal to profile/detail surfaces

**Decision**: Remove top scorer and striker names from leaderboard display. Do not rely on leaderboard tournament-pick columns for revealing detailed picks; profile/detail surfaces handle that after reveal.

**Rationale**: The user explicitly said top scorer/striker display is awkward and may be removed. Keeping detailed picks out of the leaderboard also reduces privacy risk.

**Alternatives considered**:

- Keep names hidden until reveal, then show in leaderboard: rejected because it preserves the clutter the user wants removed.
- Remove all scorer-related information, including points: left for implementation judgment based on current leaderboard readability, but pick names must be removed.

## Decision 4: Treat account creation as leaderboard eligibility

**Decision**: Every account user should be included in leaderboard construction immediately. Prediction completion, including any old Netherlands group/tutorial requirement and tournament picks, should remain progress metadata only and must not filter leaderboard rows or normal app access.

**Rationale**: The user explicitly identified the missing-new-account behavior as a remnant of the previous tutorial phase. Account creation is the current participation boundary, and hiding users with incomplete predictions makes the app appear broken.

**Alternatives considered**:

- Keep requiring Netherlands group predictions before leaderboard inclusion: rejected because this is the legacy behavior being removed.
- Require champion/top scorer/striker picks before leaderboard inclusion: rejected because tournament picks are optional for access and may remain incomplete until lock.
- Frontend-only insertion of the current user into the leaderboard: rejected because other participants also need to see newly joined users, and ranking/points should stay backend-authored.

## Decision 5: Use a searchable custom player picker rather than native grouped select

**Decision**: Replace long native player selects with searchable controls supporting player-name and team-name filtering, duplicate-striker prevention, clearing, and locked disabled state.

**Rationale**: Native selects with many grouped options are hard to search and do not give enough control over duplicate handling or empty-result messaging.

**Alternatives considered**:

- Browser datalist: rejected because duplicate disabling, grouped metadata, and consistent UX are harder to control.
- External component dependency: rejected unless implementation reveals a strong need; the project currently has no UI component dependency.

## Decision 6: Keep data model unchanged

**Decision**: No database schema changes are required. Privacy and display behavior can be derived from existing prediction rows, user identity, and lock times.

**Rationale**: The feature changes visibility, editability enforcement, and UI controls, not the persisted prediction concepts.

**Alternatives considered**:

- Add reveal-state columns: rejected because reveal state is deterministic from match schedule and current time.
- Add audit tables: rejected because prediction audit logging already exists for saves.

## Decision 7: Profile and tutorial fixes are navigation/layout refinements

**Decision**: Profile readability and tutorial navigation changes should be handled as UI state and copy/layout refinements without changing authentication rules. Tutorial copy and routing should be updated so it no longer presents prediction completion as required for leaderboard inclusion.

**Rationale**: The requested issues are about where users land, which links are active in tutorial, and how text flows.

**Alternatives considered**:

- Add new onboarding persistence state: rejected unless implementation discovers current routing cannot reliably infer the required flow.

## Decision 8: Reuse existing football label tables for manual result labels

**Decision**: Treat `match_results`, `match_events`, and `player_match_stats` as the existing labels database for score/result labels, goal/scorer labels, and player-stat labels. Admin manual edits should write to these scoring-label tables, using source/manual metadata where available.

**Rationale**: Current scoring already reads match scores from loaded match data populated by `match_results`, striker goal counts from `match_events`, and API-Football player stats from `player_match_stats`. Reusing the same tables keeps manual corrections on the same scoring path as synced API-Football labels.

**Alternatives considered**:

- Add a separate parallel manual-label table for all football labels: rejected because scoring helpers would need precedence merging across duplicate sources for data already represented in existing tables.
- Edit static World Cup JSON at runtime: rejected because production serverless deployments should not depend on mutable packaged files.

## Decision 9: Add DB-backed quiz label overrides

**Decision**: Add DB-backed storage for quiz correct-answer and viewership-answer overrides, then apply those overrides when loading quiz data for scoring.

**Rationale**: Quiz labels currently come from `quiz-2026.json`, not the football label tables. Admins need runtime fallback edits without mutating static files, and scoring must use the same loaded match/quiz shape after overrides are applied.

**Alternatives considered**:

- Store quiz labels in `match_results`: rejected because match result labels and quiz labels have different shape and validation rules.
- Require code/file edits for quiz corrections: rejected because admins need in-app fallback operations.

## Decision 10: Keep admin label editing separate from participant prediction editing

**Decision**: Admin label APIs may update only label/result/override tables and audit metadata. They must not write to `match_predictions`, `quiz_predictions`, `leeuwtje_predictions`, `winner_predictions`, or `top_scorer_predictions`.

**Rationale**: The user explicitly wants admins to correct labels but not adjust other people's predictions. Keeping the write paths separate preserves participant trust and avoids accidental prediction tampering.

**Alternatives considered**:

- Add admin prediction editing for support use cases: rejected by explicit requirement.
- Reuse participant prediction save endpoint for admin correction: rejected because it targets prediction tables and current-user ownership semantics.

## Decision 11: Make notification reminders item-specific and route-focused

**Decision**: Keep notification construction server-side, but enrich missing-action notifications with match display context, missing action type, and a target route/focus identifier. The frontend should render each missing match/quiz as an actionable item instead of only showing a generic aggregate count.

**Rationale**: The backend already knows which `match_ids` are missing. Adding display context and focus metadata solves the confusion without making the frontend recompute lock and completion logic.

**Alternatives considered**:

- Keep a single "Open predictions" button: rejected because it is the source of the current confusion.
- Compute missing items only in the frontend: rejected because it risks drifting from backend lock/completion rules and requires exposing more raw data.

## Decision 12: Store admin broadcasts separately from personal missing-action notifications

**Decision**: Add DB-backed broadcast notification storage with admin author, title/body, active state/window, and audit timestamps. Merge active broadcasts into the notification-bell payload at pool-state load time.

**Rationale**: Broadcasts are authored messages for all users, while missing-action reminders are computed per user. Keeping storage separate avoids mixing admin content with derived prediction state.

**Alternatives considered**:

- Store broadcasts in static JSON: rejected because admins need to send messages in-app without deploys.
- Reuse newsletter storage: rejected because newsletters and notification-bell broadcasts have different lifecycle, urgency, and UI contracts.

## Decision 13: Add a third admin section for broadcasts

**Decision**: Extend the existing admin section selector with a "Send message" section that lists active/recent broadcasts and provides a title/body form.

**Rationale**: The admin page already centralizes operational controls. A third section matches the user's request and avoids hiding broadcast creation inside unrelated user or label panels.

**Alternatives considered**:

- Place broadcast controls inside user management: rejected because broadcasts are not account management.
- Place broadcast controls inside label editing: rejected because broadcasts are communication, not scoring data.

## Decision 14: Derive real names from validated Talpa emails and keep nickname primary

**Decision**: Continue using `users.name` as the nickname. Add derived first/last-name fields from `users.email` for leaderboard/profile payloads and display them as smaller, lower-contrast supporting text.

**Rationale**: The user wants usernames to become nicknames while first/last name comes from the organization email structure. This avoids introducing another editable identity field.

**Alternatives considered**:

- Add editable first_name/last_name columns: rejected because the email structure is the requested source of truth and avoids inconsistent self-entered names.
- Replace nickname with derived full name: rejected because nickname should remain the prominent display name.

## Decision 15: Enforce Talpa email format in backend account creation

**Decision**: Add a single backend validator for account-creation paths requiring `firstname.lastname@talpanetwork.com`, with lowercase-normalized storage and clear errors. Frontend validation mirrors this only as a UX aid.

**Rationale**: Email format now controls access and derived identity. Backend enforcement is required because frontend checks can be bypassed.

**Alternatives considered**:

- Accept any `@talpanetwork.com` email: rejected because first/last name derivation would be unreliable.
- Validate only on the frontend: rejected because it does not protect backend account creation.

## Decision 16: Use CSS-supported avatar hover/focus preview on leaderboard rows

**Decision**: Add a larger avatar preview anchored to the existing leaderboard avatar/name link, activated on hover and focus. The preview should use existing profile image URLs and fallback initials.

**Rationale**: Users want to inspect images without opening profiles. CSS hover/focus keeps the behavior lightweight and avoids extra API calls.

**Alternatives considered**:

- Open a modal on click: rejected because click already opens the profile.
- Increase all leaderboard avatars permanently: rejected because it would reduce leaderboard density.

## Decision 17: Expand quiz override storage to cover question text and options

**Decision**: Extend quiz override handling beyond correct answers/viewership to include admin-edited question text and answer options. Apply overrides when loading quiz data for both prediction entry and scoring.

**Rationale**: The current request says some questions are wrong and answer options are incomplete. Correct-answer-only overrides cannot fix what participants see or can choose.

**Alternatives considered**:

- Edit `quiz-2026.json` manually: rejected because runtime admin edits need persistence and auditability.
- Allow admins to edit participant quiz predictions after changing options: rejected because participant predictions must remain immutable.

## Decision 18: Compute wall of shame from currently actionable missing items

**Decision**: Build wall-of-shame entries from active users plus currently unlocked missing predictions/quizzes, using the same completion and lock rules as notification generation.

**Rationale**: The wall of shame is accountability for actions users can still take. Including locked historical misses would be punitive without being actionable.

**Alternatives considered**:

- Show all historical missed predictions: rejected because users cannot fix locked matches.
- Include only current viewer's missing items: rejected because the feature is explicitly about group accountability.
