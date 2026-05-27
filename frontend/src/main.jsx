import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const AMSTERDAM_TZ = "Europe/Amsterdam";
const NETHERLANDS_ID = "ned";
const TROPHY_SRC = "/world-cup-trophy.svg";
const TEAM_FLAGS = {
  alg: "🇩🇿",
  arg: "🇦🇷",
  aus: "🇦🇺",
  aut: "🇦🇹",
  bel: "🇧🇪",
  bih: "🇧🇦",
  bra: "🇧🇷",
  can: "🇨🇦",
  civ: "🇨🇮",
  cod: "🇨🇩",
  col: "🇨🇴",
  cpv: "🇨🇻",
  cro: "🇭🇷",
  cuw: "🇨🇼",
  cze: "🇨🇿",
  ecu: "🇪🇨",
  egy: "🇪🇬",
  eng: "🏴",
  esp: "🇪🇸",
  fra: "🇫🇷",
  ger: "🇩🇪",
  gha: "🇬🇭",
  hai: "🇭🇹",
  irn: "🇮🇷",
  irq: "🇮🇶",
  jor: "🇯🇴",
  jpn: "🇯🇵",
  kor: "🇰🇷",
  ksa: "🇸🇦",
  mar: "🇲🇦",
  mex: "🇲🇽",
  ned: "🇳🇱",
  nor: "🇳🇴",
  nzl: "🇳🇿",
  pan: "🇵🇦",
  par: "🇵🇾",
  por: "🇵🇹",
  qat: "🇶🇦",
  rsa: "🇿🇦",
  sco: "🏴",
  sen: "🇸🇳",
  sui: "🇨🇭",
  swe: "🇸🇪",
  tun: "🇹🇳",
  tur: "🇹🇷",
  uru: "🇺🇾",
  usa: "🇺🇸",
  uzb: "🇺🇿",
};

function escapeDate(match) {
  return new Date(`${match.date}T${match.time_utc}:00Z`);
}

function formatDate(match, short = false) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: AMSTERDAM_TZ,
    weekday: short ? "short" : "long",
    day: "numeric",
    month: short ? "short" : "long",
    year: "numeric",
  }).format(escapeDate(match));
}

function formatTime(match) {
  return new Intl.DateTimeFormat("nl-NL", {
    timeZone: AMSTERDAM_TZ,
    hour: "2-digit",
    minute: "2-digit",
  }).format(escapeDate(match));
}

function broadcastInfo() {
  return {
    name: "NOS/NPO live",
    url: "https://nos.nl/live",
  };
}

function isMatchLive(match, now = new Date()) {
  if (match.status === "live") return true;
  if (match.status !== "scheduled") return false;
  const kickoff = escapeDate(match);
  const finalWhistle = new Date(kickoff.getTime() + 2 * 60 * 60 * 1000);
  return now >= kickoff && now <= finalWhistle;
}

function localDateKey(match) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: AMSTERDAM_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(escapeDate(match));
}

function groupPredictionsComplete(poolState) {
  const progress = poolState?.progress;
  const requiredPredictions = progress?.required_group_predictions ?? progress?.group_stage_predictions;
  const requiredTotal = progress?.required_group_total ?? progress?.group_stage_total;
  return Boolean(
    requiredTotal &&
      requiredPredictions >= requiredTotal,
  );
}

function defaultAuthenticatedView(poolState) {
  if (groupPredictionsComplete(poolState)) return "home";
  return "welcome";
}

const VIEW_ROUTES = {
  home: "/home",
  welcome: "/welcome",
  leaderboardPreview: "/leaderboard-preview",
  join: "/join",
  leaderboard: "/leaderboard",
  groups: "/tables",
  teams: "/teams",
  schedule: "/schedule",
  venues: "/venues",
  matchday: "/matchday",
  pool: "/predictions",
  adjust: "/predictions/adjust",
};

const ROUTE_VIEWS = Object.fromEntries(Object.entries(VIEW_ROUTES).map(([view, route]) => [route, view]));
const ONBOARDING_VIEWS = new Set(["welcome", "leaderboardPreview", "join", "pool"]);

const NEWS_ARTICLES = [
  {
    title: "WK 2026 levert landen recordbedrag op",
    publisher: "NU.nl",
    country: "Netherlands",
    summary: "FIFA raises the prize pool for the 2026 World Cup, with a larger base payout for every qualified country.",
    url: "https://www.nu.nl/voetbal/6379805/wk-2026-levert-landen-recordbedrag-op-wereldkampioen-krijgt-42-miljoen-euro.html",
  },
  {
    title: "FIFA WK voetbal 2026 en 2030 live bij de NOS",
    publisher: "NOS",
    country: "Netherlands",
    summary: "NOS outlines its broadcast role for the 2026 and 2030 men’s World Cups.",
    url: "https://over.nos.nl/nieuws/fifa-wk-voetbal-2026-en-2030-live-bij-de-nos/",
  },
  {
    title: "Het volledige speelschema van de Rode Duivels",
    publisher: "VoetbalPrimeur.be",
    country: "Belgium",
    summary: "Belgian coverage of the Red Devils’ group-stage schedule, opponents and kick-off windows.",
    url: "https://www.voetbalprimeur.be/nieuws/1718992/wk-voetbal-2026-ontdek-hier-het-volledige-speelschema-van-de-rode-duivels.html",
  },
  {
    title: "WK 2026 wordt luxeproduct",
    publisher: "VoetbalPrimeur.be",
    country: "Belgium",
    summary: "A Belgian fan-facing look at World Cup ticket prices and allocation pressure.",
    url: "https://www.voetbalprimeur.be/nieuws/1721351/wk-2026-wordt-luxeproduct-dit-kosten-tickets-voor-wedstrijden-van-de-rode-duivels.html",
  },
];

function normalizeRoute(pathname) {
  const path = pathname.replace(/\/+$/, "");
  return path || "/";
}

function viewFromRoute(pathname) {
  const path = normalizeRoute(pathname);
  if (/^\/profile\/\d+$/.test(path)) return "profile";
  if (/^\/teams\/[a-z0-9-]+$/i.test(path)) return "team";
  return ROUTE_VIEWS[path] ?? null;
}

function profileIdFromRoute(pathname) {
  return normalizeRoute(pathname).match(/^\/profile\/(\d+)$/)?.[1] ?? "";
}

function profileRoute(userId) {
  return `/profile/${userId}`;
}

function teamIdFromRoute(pathname) {
  return normalizeRoute(pathname).match(/^\/teams\/([a-z0-9-]+)$/i)?.[1] ?? "";
}

function teamRoute(teamId) {
  return `/teams/${teamId}`;
}

function routeForView(view, profileId = "", teamId = "") {
  if (view === "profile" && profileId) return profileRoute(profileId);
  if (view === "team" && teamId) return teamRoute(teamId);
  return VIEW_ROUTES[view] ?? VIEW_ROUTES.leaderboard;
}

function onboardingViewAllowed(poolState, routedView) {
  if (!routedView) return false;
  if (groupPredictionsComplete(poolState)) return routedView && !ONBOARDING_VIEWS.has(routedView);
  return routedView && ONBOARDING_VIEWS.has(routedView);
}

function authenticatedViewFromRoute(poolState, pathname) {
  const routedView = viewFromRoute(pathname);
  if (onboardingViewAllowed(poolState, routedView)) return routedView;
  return defaultAuthenticatedView(poolState);
}

function formatCountdown(targetDate, now) {
  const totalMinutes = Math.max(0, Math.floor((targetDate - now) / 60000));
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  return {
    days: String(days),
    hours: String(hours).padStart(2, "0"),
    minutes: String(minutes).padStart(2, "0"),
  };
}

function teamFlag(id) {
  return TEAM_FLAGS[id] ?? "";
}

function matchLock(pool, matchId) {
  return pool?.locks?.matches?.[matchId] ?? { locked: false, lock_at: null };
}

function winnerLocked(pool) {
  return Boolean(pool?.locks?.winner_locked);
}

function viewLabel(view) {
  const labels = {
    home: "Home",
    leaderboard: "Leaderboard",
    groups: "Tables",
    teams: "Teams",
    schedule: "Schedule",
    matchday: "Matchday",
    venues: "Venues",
  };
  return labels[view] ?? view;
}

const BADGE_FAMILY_LABELS = {
  zayu: "Zayu Jaguar",
  oranje: "Oranje Leeuw",
  maple: "Maple Moose",
  clutch: "Clutch Eagle",
  trophy: "WK bokaal",
};

function badgeFamilyLabel(family, mascot) {
  return BADGE_FAMILY_LABELS[family] ?? mascot ?? "Badges";
}

async function apiJson(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options,
  });
  const body = await response.text();
  let data = null;
  if (body) {
    try {
      data = JSON.parse(body);
    } catch {
      const snippet = body.trim().replace(/\s+/g, " ").slice(0, 180);
      const message = snippet
        ? `API ${path} returned ${response.status}: ${snippet}`
        : `API ${path} returned ${response.status} without JSON`;
      throw new Error(message);
    }
  }
  if (!response.ok) throw new Error(data?.error || `API returned ${response.status}`);
  return data ?? {};
}

function FieldMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 240 240" fill="none" aria-hidden="true">
      <rect x="10" y="10" width="220" height="220" rx="26" fill="#F36C21" />
      <path d="M10 74H230V105H10V74Z" fill="#FFFFFF" fillOpacity="0.9" />
      <path d="M10 135H230V166H10V135Z" fill="#21468B" fillOpacity="0.92" />
      <rect x="29" y="29" width="182" height="182" rx="12" stroke="#FFFFFF" strokeWidth="8" />
      <path d="M120 30V210" stroke="#FFFFFF" strokeWidth="7" />
      <circle cx="120" cy="120" r="32" stroke="#FFFFFF" strokeWidth="7" />
      <circle cx="120" cy="120" r="7" fill="#FFFFFF" />
      <path d="M29 82H58V158H29" stroke="#FFFFFF" strokeWidth="7" />
      <path d="M211 82H182V158H211" stroke="#FFFFFF" strokeWidth="7" />
      <path d="M29 101H43V139H29" stroke="#FFFFFF" strokeWidth="6" />
      <path d="M211 101H197V139H211" stroke="#FFFFFF" strokeWidth="6" />
      <path d="M52 204C82 184 119 184 150 204C170 216 192 216 211 206" stroke="#00A7B5" strokeWidth="10" strokeLinecap="round" />
    </svg>
  );
}

function TeamLabel({ id, teams }) {
  const team = teams.get(id);
  return (
    <span className="team-inline">
      {teamFlag(id) && <span className="team-flag" aria-hidden="true">{teamFlag(id)}</span>}
      <span className={id === NETHERLANDS_ID ? "team-name highlight-text" : "team-name"}>
        {team?.name ?? id ?? "TBD"}
      </span>{" "}
      <span className="muted">{team?.code ?? "TBD"}</span>
    </span>
  );
}

function TeamBadge({ id, teams, align = "left" }) {
  const team = teams.get(id);
  const className = [
    "team-badge",
    id === NETHERLANDS_ID ? "is-highlight" : "",
    align === "right" ? "align-right" : "",
  ].filter(Boolean).join(" ");
  return (
    <span className={className}>
      {teamFlag(id) && <span className="team-badge-flag" aria-hidden="true">{teamFlag(id)}</span>}
      <span>
        <strong>{team?.name ?? id ?? "TBD"}</strong>
        <em>{team?.code ?? "TBD"}</em>
      </span>
    </span>
  );
}

function teamProfile(team) {
  return team?.profile ?? team?.team_profile ?? {};
}

function normalizePeople(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  return [value];
}

function personName(person) {
  if (typeof person === "string") return person;
  return person?.name ?? person?.full_name ?? "To be confirmed";
}

function personRole(person, fallback = "") {
  if (typeof person === "string") return fallback;
  return person?.role ?? person?.position ?? person?.job_title ?? fallback;
}

function personMeta(person) {
  if (typeof person === "string") return "";
  return [person?.club, person?.country, person?.age ? `${person.age} yrs` : ""].filter(Boolean).join(" · ");
}

function teamCoach(team) {
  const profile = teamProfile(team);
  return profile.head_coach ?? profile.coach ?? team?.head_coach ?? team?.coach ?? null;
}

function teamStaff(team) {
  const profile = teamProfile(team);
  return normalizePeople(profile.staff ?? profile.coaching_staff ?? team?.staff ?? team?.coaching_staff);
}

function teamPlayers(team) {
  const profile = teamProfile(team);
  return normalizePeople(profile.players ?? profile.squad ?? profile.roster ?? team?.players ?? team?.squad ?? team?.roster);
}

function teamSources(team) {
  const profile = teamProfile(team);
  return normalizePeople(profile.sources ?? team?.sources);
}

function LockPill({ lock }) {
  if (!lock?.locked) return null;
  return <span className="lock-pill is-locked">Locked</span>;
}

function PredictionStatusPill({ complete, active, locked }) {
  if (locked) return <span className="pill">Locked</span>;
  if (active) return <span className="pill orange">Editing</span>;
  if (complete) return <span className="pill green">Entered</span>;
  return <span className="pill">Open</span>;
}

function scoreComplete(scores) {
  const homeScore = scores?.home_score;
  const awayScore = scores?.away_score;
  return homeScore !== undefined && homeScore !== null && homeScore !== "" && awayScore !== undefined && awayScore !== null && awayScore !== "";
}

function draftPredictions(draft) {
  return Object.entries(draft)
    .filter(([, scores]) => scoreComplete(scores))
    .map(([match_id, scores]) => ({
      match_id,
      home_score: Number(scores.home_score),
      away_score: Number(scores.away_score),
    }));
}

function quizAnswerComplete(quiz, prediction) {
  if (!quiz) return true;
  const answer = String(prediction?.answer ?? "").trim();
  if (!answer) return false;
  if (quiz.viewership) {
    const viewership = prediction?.viewership_prediction;
    return viewership !== undefined && viewership !== null && viewership !== "";
  }
  return true;
}

function draftQuizPredictions(draft) {
  return Object.entries(draft).map(([match_id, prediction]) => ({
    match_id,
    answer: String(prediction?.answer ?? "").trim(),
    viewership_prediction:
      prediction?.viewership_prediction === "" ||
      prediction?.viewership_prediction === undefined ||
      prediction?.viewership_prediction === null
        ? null
        : Number(prediction.viewership_prediction),
  }));
}

function leeuwtjesUsed(pool) {
  return pool?.progress?.leeuwtjes_used ?? pool?.leeuwtjes_match_ids?.length ?? 0;
}

function leeuwtjesTotal(pool) {
  return pool?.progress?.leeuwtjes_total ?? pool?.rules?.leeuwtjes_total ?? 5;
}

function formatNumber(value) {
  if (value === undefined || value === null || value === "") return "";
  return new Intl.NumberFormat("nl-NL").format(Number(value));
}

function MatchPredictionEditor({
  match,
  teams,
  scores,
  locked,
  onScore,
  onSubmit,
  saving,
  compact = false,
}) {
  const canSubmit = scoreComplete(scores) && !locked && !saving;

  function submitOnEnter(event) {
    if (event.key !== "Enter" || !canSubmit) return;
    event.preventDefault();
    onSubmit?.();
  }

  return (
    <div className={compact ? "fixture-score-grid is-compact" : "fixture-score-grid"}>
      <label className="fixture-team-input is-home">
        <TeamBadge id={match.home_team_id} teams={teams} />
        <input
          aria-label={`${teams.get(match.home_team_id)?.name ?? "Home"} score`}
          type="number"
          min="0"
          max="30"
          value={scores?.home_score ?? ""}
          disabled={locked}
          onChange={(event) => onScore(match.id, "home_score", event.target.value)}
          onKeyDown={submitOnEnter}
        />
      </label>
      <span className="fixture-score-separator">-</span>
      <label className="fixture-team-input is-away">
        <TeamBadge id={match.away_team_id} teams={teams} align="right" />
        <input
          aria-label={`${teams.get(match.away_team_id)?.name ?? "Away"} score`}
          type="number"
          min="0"
          max="30"
          value={scores?.away_score ?? ""}
          disabled={locked}
          onChange={(event) => onScore(match.id, "away_score", event.target.value)}
          onKeyDown={submitOnEnter}
        />
      </label>
      <button className="fixture-ok-button" type="button" onClick={onSubmit} disabled={!canSubmit}>
        {saving ? "Saving..." : "OK"}
      </button>
    </div>
  );
}

function MatchQuizEditor({
  match,
  prediction,
  locked,
  onAnswer,
  onViewership,
}) {
  const quiz = match.quiz;
  if (!quiz) return null;
  const answer = prediction?.answer ?? "";
  const viewership = prediction?.viewership_prediction ?? "";
  const complete = quizAnswerComplete(quiz, prediction);

  return (
    <section className={complete ? "fixture-quiz is-complete" : "fixture-quiz"} aria-label="Quizvraag">
      <div className="fixture-quiz-heading">
        <div>
          <span className="game-kicker">Quizvraag</span>
          <strong>{quiz.question}</strong>
        </div>
        <PredictionStatusPill complete={complete} locked={locked} />
      </div>
      <div className={quiz.viewership ? "fixture-quiz-inputs has-viewership" : "fixture-quiz-inputs"}>
        <label>
          Antwoord
          {quiz.choices?.length ? (
            <select value={answer} disabled={locked} onChange={(event) => onAnswer(match.id, event.target.value)}>
              <option value="">Kies antwoord</option>
              {quiz.choices.map((choice) => (
                <option key={choice} value={choice}>{choice}</option>
              ))}
            </select>
          ) : (
            <input
              value={answer}
              disabled={locked}
              maxLength={160}
              placeholder="Typ je antwoord"
              onChange={(event) => onAnswer(match.id, event.target.value)}
            />
          )}
        </label>
        {quiz.viewership && (
          <label>
            Kijkcijfers
            <input
              value={viewership}
              disabled={locked}
              inputMode="numeric"
              min="0"
              placeholder="Aantal kijkers"
              type="number"
              onChange={(event) => onViewership(match.id, event.target.value)}
            />
          </label>
        )}
      </div>
    </section>
  );
}

function LeeuwtjeButton({ active, disabled, onToggle, remaining }) {
  return (
    <button
      className={active ? "leeuwtje-button is-active" : "leeuwtje-button"}
      type="button"
      onClick={onToggle}
      disabled={disabled}
      aria-pressed={active}
      title={active ? "Leeuwtje ingezet voor deze wedstrijd" : "Verdubbel punten voor deze wedstrijd"}
    >
      <span aria-hidden="true">L</span>
      <strong>{active ? "Leeuwtje aan" : "Leeuwtje"}</strong>
      {!active && <em>{remaining} over</em>}
    </button>
  );
}

function MatchPredictionRow({
  match,
  index,
  teams,
  venues,
  scores,
  quizPrediction,
  locked,
  editing,
  saving,
  leeuwtjeActive,
  canToggleLeeuwtje,
  leeuwtjesRemaining,
  onEdit,
  onScore,
  onQuizAnswer,
  onQuizViewership,
  onToggleLeeuwtje,
  onSubmit,
  compact = false,
}) {
  const complete = scoreComplete(scores);
  const venue = venues.get(match.venue_id);
  const scoreLabel = complete ? `${scores.home_score} - ${scores.away_score}` : "— - —";

  return (
    <article
      className={[
        "prediction-fixture-row",
        editing ? "is-active" : "",
        complete ? "is-complete" : "",
        locked ? "is-locked" : "",
      ].filter(Boolean).join(" ")}
    >
      <div className="fixture-row-header">
        <div className="fixture-open-button as-static">
          <span className="fixture-number">{index + 1}</span>
          <span>
            <strong><TeamLabel id={match.home_team_id} teams={teams} /> vs <TeamLabel id={match.away_team_id} teams={teams} /></strong>
            <em>{formatDate(match, true)} · {formatTime(match)} · {venue?.city ?? "Venue to confirm"}</em>
          </span>
        </div>
        <div className="fixture-row-status">
          <LeeuwtjeButton
            active={leeuwtjeActive}
            disabled={locked || !canToggleLeeuwtje}
            remaining={leeuwtjesRemaining}
            onToggle={onToggleLeeuwtje}
          />
          <PredictionStatusPill complete={complete} active={editing} locked={locked} />
          <LockPill lock={{ locked }} />
        </div>
      </div>

      {editing ? (
        <MatchPredictionEditor
          match={match}
          teams={teams}
          scores={scores}
          locked={locked}
          onScore={onScore}
          onSubmit={onSubmit}
          saving={saving}
          compact={compact}
        />
      ) : (
        <button className="fixture-preview" type="button" onClick={onEdit} disabled={locked}>
          <TeamBadge id={match.home_team_id} teams={teams} />
          <strong>{scoreLabel}</strong>
          <TeamBadge id={match.away_team_id} teams={teams} align="right" />
        </button>
      )}
      <MatchQuizEditor
        match={match}
        prediction={quizPrediction}
        locked={locked}
        onAnswer={onQuizAnswer}
        onViewership={onQuizViewership}
      />
    </article>
  );
}

function MatchCard({ match, teams, venues }) {
  const venue = venues.get(match.venue_id);
  const venueLabel = match.venue_id === "to_confirm"
    ? "Venue to confirm"
    : `${venue?.name ?? match.venue_id}, ${venue?.city ?? ""}`;
  const group = match.group ? `Group ${match.group}` : match.round;
  const broadcaster = broadcastInfo(match);
  const live = isMatchLive(match);
  return (
    <article className="match-card">
      <div className="match-time">{formatTime(match)}</div>
      <div>
        <div className="match-teams">
          <TeamLabel id={match.home_team_id} teams={teams} /> <span className="muted">vs</span>{" "}
          <TeamLabel id={match.away_team_id} teams={teams} />
        </div>
        <div className="match-meta">
          {formatDate(match, true)} · {venueLabel}
        </div>
        {match.quiz && <div className="match-quiz-line">Quiz: {match.quiz.question}</div>}
      </div>
      <div className="match-actions">
        {live && <span className="live-indicator"><span aria-hidden="true" />Live</span>}
        <span className="pill">{group}</span>
        <span className="broadcast-pill">{broadcaster.name}</span>
        <a
          className="match-link"
          href={broadcaster.url}
          target="_blank"
          rel="noreferrer"
        >
          Watch on NOS.nl
        </a>
      </div>
    </article>
  );
}

function Schedule({ matches, teams, venues }) {
  if (!matches.length) return <div className="empty">No matches available.</div>;
  const grouped = matches.reduce((days, match) => {
    const key = localDateKey(match);
    if (!days.has(key)) days.set(key, []);
    days.get(key).push(match);
    return days;
  }, new Map());

  return [...grouped.entries()].map(([key, dayMatches]) => (
    <React.Fragment key={key}>
      <h3 className="date-heading">{formatDate(dayMatches[0])}</h3>
      <div className="match-list">
        {dayMatches.map((match) => (
          <MatchCard key={match.id} match={match} teams={teams} venues={venues} />
        ))}
      </div>
    </React.Fragment>
  ));
}

function TeamDirectoryPage({ data, teams, onTeam }) {
  const groupedTeams = data.groups.map((group) => ({
    ...group,
    teams: group.teams.map((teamId) => teams.get(teamId)).filter(Boolean),
  }));

  return (
    <div className="teams-page">
      <article className="panel">
        <div className="panel-header">
          <div>
            <h3>Teams</h3>
            <p>All participating countries by group.</p>
          </div>
          <span className="pill green">{data.teams.length} teams</span>
        </div>
        <div className="panel-body team-directory">
          {groupedTeams.map((group) => (
            <section className="team-group-block" key={group.id} aria-label={`Group ${group.id}`}>
              <div className="team-group-heading">
                <h4>Group {group.id}</h4>
                <span className="pill">{group.teams.length} teams</span>
              </div>
              <div className="team-directory-grid">
                {group.teams.map((team) => (
                  <button className="team-directory-card" key={team.id} type="button" onClick={() => onTeam(team.id)}>
                    <span className="team-card-flag" aria-hidden="true">{teamFlag(team.id)}</span>
                    <span className="team-card-copy">
                      <strong>{team.name}</strong>
                      <span>{team.code} · {team.confederation}</span>
                    </span>
                    <span className="team-card-meta">
                      {team.is_host && <em>Host</em>}
                      <b>#{team.fifa_ranking ?? "-"}</b>
                    </span>
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
      </article>
    </div>
  );
}

function TeamPeopleSection({
  title,
  subtitle,
  people,
  empty,
  countLabel,
  fallbackRole = "",
}) {
  return (
    <article className="panel team-section">
      <div className="panel-header">
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
        <span className={people.length ? "pill green" : "pill"}>{people.length ? countLabel ?? people.length : "TBC"}</span>
      </div>
      <div className="panel-body">
        {!people.length && <div className="empty compact">{empty}</div>}
        {!!people.length && (
          <ul className="team-person-list">
            {people.map((person, index) => {
              const role = personRole(person, fallbackRole);
              const meta = personMeta(person);
              const number = typeof person === "string" ? "" : person?.number ?? person?.shirt_number ?? "";
              return (
                <li className="team-person-row" key={`${personName(person)}-${index}`}>
                  <span className="team-person-number">{number || index + 1}</span>
                  <span>
                    <strong>{personName(person)}</strong>
                    {(role || meta) && <em>{[role, meta].filter(Boolean).join(" · ")}</em>}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </article>
  );
}

function TeamFixtureSection({ team, matches, teams, venues }) {
  const teamMatches = matches
    .filter((match) => match.home_team_id === team.id || match.away_team_id === team.id)
    .sort((a, b) => escapeDate(a) - escapeDate(b));

  return (
    <article className="panel team-section">
      <div className="panel-header">
        <div>
          <h3>Matches</h3>
          <p>{team.name} fixtures in the current schedule.</p>
        </div>
        <span className="pill">{teamMatches.length} matches</span>
      </div>
      <div className="panel-body team-fixture-list">
        {!teamMatches.length && <div className="empty compact">No matches available for this team.</div>}
        {teamMatches.map((match) => {
          const opponentId = match.home_team_id === team.id ? match.away_team_id : match.home_team_id;
          const venue = venues.get(match.venue_id);
          return (
            <article className="team-fixture-row" key={match.id}>
              <span className="match-time">{formatTime(match)}</span>
              <span>
                <strong><TeamLabel id={opponentId} teams={teams} /></strong>
                <em>{formatDate(match, true)} · {venue?.city ?? "Venue to confirm"}</em>
              </span>
              <span className="pill">{match.group ? `Group ${match.group}` : match.round}</span>
            </article>
          );
        })}
      </div>
    </article>
  );
}

function TeamDetailPage({ team, data, teams, venues, onBack }) {
  if (!team) {
    return (
      <div className="teams-page">
        <article className="panel">
          <div className="panel-header">
            <div>
              <h3>Team not found</h3>
              <p>This country is not available in the current World Cup data.</p>
            </div>
            <button className="text-button" type="button" onClick={onBack}>Teams</button>
          </div>
        </article>
      </div>
    );
  }

  const group = data.groups.find((candidate) => candidate.teams.includes(team.id));
  const coach = teamCoach(team);
  const staff = teamStaff(team);
  const players = teamPlayers(team);
  const sources = teamSources(team);

  return (
    <div className="team-page">
      <button className="text-button team-back-button" type="button" onClick={onBack}>
        Back to Teams
      </button>

      <section className="team-hero" aria-label={`${team.name} team profile`}>
        <span className="team-hero-flag" aria-hidden="true">{teamFlag(team.id)}</span>
        <div className="team-hero-copy">
          <p className="eyebrow">Group {team.group ?? group?.id ?? "-"}</p>
          <h3>{team.name}</h3>
          <div className="team-hero-meta">
            <span>{team.code}</span>
            <span>{team.confederation}</span>
            <span>FIFA #{team.fifa_ranking ?? "-"}</span>
            {team.is_host && <span>Host nation</span>}
          </div>
        </div>
      </section>

      <div className="team-profile-grid">
        <TeamPeopleSection
          title="Coach"
          subtitle="Head coach for this World Cup cycle."
          people={coach ? [coach] : []}
          empty="Head coach data is not available in this local dataset yet."
          countLabel="1 coach"
          fallbackRole="Head coach"
        />
        <TeamPeopleSection
          title="Staff"
          subtitle="Technical and support staff."
          people={staff}
          empty="Staff data is not available in this local dataset yet."
        />
      </div>

      <TeamPeopleSection
        title="WK squad"
        subtitle="Players selected for the tournament."
        people={players}
        empty="Final WK squad data is not available in this local dataset yet."
        countLabel={`${players.length} players`}
      />

      {!!sources.length && (
        <article className="panel team-section">
          <div className="panel-header">
            <div>
              <h3>Sources</h3>
              <p>Roster references for this team.</p>
            </div>
            <span className="pill">{sources.length}</span>
          </div>
          <div className="panel-body team-source-list">
            {sources.map((source, index) => {
              const href = typeof source === "string" ? source : source.url;
              const label = typeof source === "string" ? source : source.label ?? source.title ?? source.url ?? "Source";
              if (!href) return <span key={`${label}-${index}`}>{label}</span>;
              return (
                <a key={`${href}-${index}`} href={href} target="_blank" rel="noreferrer">
                  {label}
                </a>
              );
            })}
          </div>
        </article>
      )}

      <TeamFixtureSection team={team} matches={data.matches} teams={teams} venues={venues} />
    </div>
  );
}

function StandingsTable({ group, matches, teams }) {
  const rows = group.teams.map((teamId) => ({
    teamId,
    played: 0,
    won: 0,
    drawn: 0,
    lost: 0,
    goalsFor: 0,
    goalsAgainst: 0,
    points: 0,
  }));
  const byTeam = new Map(rows.map((row) => [row.teamId, row]));

  matches
    .filter((match) => match.group === group.id && match.status === "completed")
    .forEach((match) => {
      if (typeof match.home_score !== "number" || typeof match.away_score !== "number") return;
      const home = byTeam.get(match.home_team_id);
      const away = byTeam.get(match.away_team_id);
      if (!home || !away) return;

      home.played += 1;
      away.played += 1;
      home.goalsFor += match.home_score;
      home.goalsAgainst += match.away_score;
      away.goalsFor += match.away_score;
      away.goalsAgainst += match.home_score;

      if (match.home_score > match.away_score) {
        home.won += 1;
        home.points += 3;
        away.lost += 1;
      } else if (match.home_score < match.away_score) {
        away.won += 1;
        away.points += 3;
        home.lost += 1;
      } else {
        home.drawn += 1;
        away.drawn += 1;
        home.points += 1;
        away.points += 1;
      }
    });

  rows.sort((a, b) => {
    const gdA = a.goalsFor - a.goalsAgainst;
    const gdB = b.goalsFor - b.goalsAgainst;
    return b.points - a.points || gdB - gdA || b.goalsFor - a.goalsFor;
  });

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Team</th>
            <th className="numeric">P</th>
            <th className="numeric">W</th>
            <th className="numeric">D</th>
            <th className="numeric">L</th>
            <th className="numeric">GD</th>
            <th className="numeric">Pts</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const gd = row.goalsFor - row.goalsAgainst;
            return (
              <tr key={row.teamId} className={row.teamId === NETHERLANDS_ID ? "highlight" : undefined}>
                <td><TeamLabel id={row.teamId} teams={teams} /></td>
                <td className="numeric">{row.played}</td>
                <td className="numeric">{row.won}</td>
                <td className="numeric">{row.drawn}</td>
                <td className="numeric">{row.lost}</td>
                <td className="numeric">{gd}</td>
                <td className="numeric"><strong>{row.points}</strong></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function PredictedStandingsTable({ group, matches, teams, predictions }) {
  const rows = group.teams.map((teamId) => ({
    teamId,
    played: 0,
    won: 0,
    drawn: 0,
    lost: 0,
    goalsFor: 0,
    goalsAgainst: 0,
    points: 0,
  }));
  const byTeam = new Map(rows.map((row) => [row.teamId, row]));
  const groupMatches = matches.filter((match) => match.group === group.id);
  const completedPredictions = groupMatches.filter((match) => scoreComplete(predictions[match.id]));

  for (const match of completedPredictions) {
    const scores = predictions[match.id];
    const homeScore = Number(scores.home_score);
    const awayScore = Number(scores.away_score);
    const home = byTeam.get(match.home_team_id);
    const away = byTeam.get(match.away_team_id);
    if (!home || !away) continue;

    home.played += 1;
    away.played += 1;
    home.goalsFor += homeScore;
    home.goalsAgainst += awayScore;
    away.goalsFor += awayScore;
    away.goalsAgainst += homeScore;

    if (homeScore > awayScore) {
      home.won += 1;
      home.points += 3;
      away.lost += 1;
    } else if (homeScore < awayScore) {
      away.won += 1;
      away.points += 3;
      home.lost += 1;
    } else {
      home.drawn += 1;
      away.drawn += 1;
      home.points += 1;
      away.points += 1;
    }
  }

  rows.sort((a, b) => {
    const gdA = a.goalsFor - a.goalsAgainst;
    const gdB = b.goalsFor - b.goalsAgainst;
    return b.points - a.points || gdB - gdA || b.goalsFor - a.goalsFor;
  });

  return (
    <section className="predicted-table-panel">
      <div className="prediction-step-header">
        <div>
          <h4>Your predicted Group {group.id} table</h4>
          <p>This table is built from your score predictions for this group.</p>
        </div>
        <span className="pill orange">Prediction preview</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Team</th>
              <th className="numeric">P</th>
              <th className="numeric">W</th>
              <th className="numeric">D</th>
              <th className="numeric">L</th>
              <th className="numeric">GF</th>
              <th className="numeric">GA</th>
              <th className="numeric">GD</th>
              <th className="numeric">Pts</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const goalDifference = row.goalsFor - row.goalsAgainst;
              return (
                <tr key={row.teamId} className={row.teamId === NETHERLANDS_ID ? "highlight" : undefined}>
                  <td><TeamLabel id={row.teamId} teams={teams} /></td>
                  <td className="numeric">{row.played}</td>
                  <td className="numeric">{row.won}</td>
                  <td className="numeric">{row.drawn}</td>
                  <td className="numeric">{row.lost}</td>
                  <td className="numeric">{row.goalsFor}</td>
                  <td className="numeric">{row.goalsAgainst}</td>
                  <td className="numeric">{goalDifference}</td>
                  <td className="numeric"><strong>{row.points}</strong></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function GroupPanel({ group, data, teams }) {
  const teamNames = group.teams.map((id) => teams.get(id)?.name ?? id).join(", ");
  const groupMatches = data.matches.filter((match) => match.group === group.id);
  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <h3>Group {group.id}</h3>
          <p>{teamNames}</p>
        </div>
        <span className={group.id === "F" ? "pill orange" : "pill"}>{groupMatches.length} matches</span>
      </div>
      <div className="panel-body">
        <StandingsTable group={group} matches={data.matches} teams={teams} />
      </div>
    </article>
  );
}

function LoginPanel({ onLogin }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const result = await apiJson("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ name, email }),
      });
      await onLogin(result.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="panel pool-login">
      <div className="panel-header">
        <div>
          <h3>Join the Talpa WK Pool</h3>
          <p>Log in once, then fill in group-stage scores and your tournament winner.</p>
        </div>
        <span className="pill orange">Login</span>
      </div>
      <form className="panel-body login-form" onSubmit={submit}>
        <label>
          Username
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="your username" />
        </label>
        <label>
          Email
          <input value={email} onChange={(event) => setEmail(event.target.value)} inputMode="email" autoComplete="email" placeholder="name@talpa.nl" />
        </label>
        {error && <div className="form-error">{error}</div>}
        <button className="primary-button" type="submit" disabled={saving}>
          {saving ? "Logging in..." : "Log in"}
        </button>
      </form>
    </article>
  );
}

function LoginPage({ onLogin }) {
  return (
    <main className="login-page">
      <section className="login-copy" aria-label="Talpa WK Pool login">
        <FieldMark />
        <p className="eyebrow">FIFA World Cup 2026</p>
        <h1>Talpa WK Pool</h1>
        <p>Sign in to open your predictions, standings and Oranje planning.</p>
      </section>
      <LoginPanel onLogin={onLogin} />
    </main>
  );
}

function ProfileAvatar({ player, size = "medium" }) {
  const avatar = player?.profile_picture ?? {};
  return (
    <span
      className={`profile-avatar ${size}`}
      style={{ "--avatar-hue": avatar.hue ?? 24 }}
      role="img"
      aria-label={`${player?.name ?? "Player"} profile picture`}
    >
      {avatar.initials ?? "?"}
    </span>
  );
}

function FriendButton({ relation, onFollow, onUnfollow }) {
  if (relation === null) return <span className="muted">Your profile</span>;
  if (relation?.is_friend) {
    return (
      <button className="text-button friend-button" type="button" onClick={onUnfollow}>
        Unfollow
      </button>
    );
  }
  if (relation?.is_following) {
    return (
      <button className="text-button friend-button" type="button" onClick={onUnfollow}>
        Following
      </button>
    );
  }
  return (
    <button className="primary-button friend-button" type="button" onClick={onFollow}>
      Follow
    </button>
  );
}

function HomePage({ onSchedule, recap }) {
  return (
    <div className="home-layout">
      <section className="home-kicker" aria-label="World Cup quick links">
        <div>
          <p className="eyebrow">World Cup hub</p>
          <h3>News from Dutch and Belgian press</h3>
          <p>Follow the tournament context, then jump straight into the match schedule.</p>
        </div>
        <button className="primary-button" type="button" onClick={onSchedule}>
          View games
        </button>
      </section>

      <DailyRecap recap={recap} />

      <section className="news-grid" aria-label="World Cup news">
        {NEWS_ARTICLES.map((article) => (
          <article className="news-card" key={article.url}>
            <div className="news-source">
              <span>{article.publisher}</span>
              <span>{article.country}</span>
            </div>
            <h3>{article.title}</h3>
            <p>{article.summary}</p>
            <a href={article.url} target="_blank" rel="noreferrer">
              Read article
            </a>
          </article>
        ))}
      </section>
    </div>
  );
}

function OutcomeBar({ home, draw, away }) {
  const total = home + draw + away;
  const homeWidth = total ? `${Math.round((home / total) * 100)}%` : "0%";
  const drawWidth = total ? `${Math.round((draw / total) * 100)}%` : "0%";
  const awayWidth = total ? `${Math.round((away / total) * 100)}%` : "0%";
  return (
    <div className="outcome-bar" aria-label={`${home} home, ${draw} draw, ${away} away predictions`}>
      <span className="home" style={{ width: homeWidth }} />
      <span className="draw" style={{ width: drawWidth }} />
      <span className="away" style={{ width: awayWidth }} />
    </div>
  );
}

function percentage(value, total) {
  return total ? Math.round((value / total) * 100) : 0;
}

function OutcomeBreakdown({ match, teams }) {
  const home = match.home_win_count ?? 0;
  const draw = match.draw_count ?? 0;
  const away = match.away_win_count ?? 0;
  const total = home + draw + away;
  const homeTeam = teams.get(match.home_team_id);
  const awayTeam = teams.get(match.away_team_id);
  const items = [
    { key: "home", label: homeTeam?.code ?? homeTeam?.name ?? "Home", value: home },
    { key: "draw", label: "Tie", value: draw },
    { key: "away", label: awayTeam?.code ?? awayTeam?.name ?? "Away", value: away },
  ];
  return (
    <div className="outcome-breakdown">
      <OutcomeBar home={home} draw={draw} away={away} />
      <div className="outcome-percentages">
        {items.map((item) => (
          <span className={`outcome-percentage is-${item.key}`} key={item.key}>
            <strong>{percentage(item.value, total)}%</strong>
            <em>{item.label}</em>
          </span>
        ))}
      </div>
    </div>
  );
}

function DailyRecap({ recap }) {
  const topPlayers = recap?.top_players ?? [];
  const topMovers = recap?.top_movers ?? [];
  return (
    <article className="panel recap-panel">
      <div className="panel-header">
        <div>
          <h3>Daily recap</h3>
          <p>Top 5 + ties voor dagscore en beweging.</p>
        </div>
        <span className={recap?.available ? "pill green" : "pill"}>{recap?.available ? "Live" : "Nog leeg"}</span>
      </div>
      <div className="panel-body recap-body">
        <div className="daily-recap-grid">
          <section className="daily-recap-board">
            <h4>Dagscore</h4>
            {!topPlayers.length && <div className="empty compact">Nog geen dagpunten.</div>}
            {!!topPlayers.length && (
              <ol className="daily-top-list">
                {topPlayers.map((player, index) => (
                  <li className="is-score" key={player.user_id}>
                    <span className="daily-rank">{player.rank ?? index + 1}</span>
                    <ProfileAvatar player={player} size="small" />
                    <strong>{player.name}</strong>
                    <b>{player.points} pts</b>
                  </li>
                ))}
              </ol>
            )}
          </section>
          <section className="daily-recap-board">
            <h4>Biggest movers</h4>
            {!topMovers.length && <div className="empty compact">Nog geen beweging.</div>}
            {!!topMovers.length && (
              <ol className="daily-top-list">
                {topMovers.map((player, index) => (
                  <li className="is-mover" key={player.user_id}>
                    <span className="daily-rank">{index + 1}</span>
                    <ProfileAvatar player={player} size="small" />
                    <strong>{player.name}</strong>
                    <span className="daily-mover-meta">
                      #{player.rank_previous ?? "-"} to #{player.rank ?? "-"}
                    </span>
                    <RankMovement movement={player.rank_movement ?? 0} />
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>
      </div>
    </article>
  );
}

function BadgePill({ badge }) {
  return (
    <span
      className={`badge-pill ${badge.family ? `is-${badge.family}` : ""}`}
      title={badge.detail}
    >
      <em aria-hidden="true">{badge.mark ?? badge.label?.[0] ?? "B"}</em>
      {badge.label}
      {badge.count > 1 && <b>x{badge.count}</b>}
    </span>
  );
}

function BadgeCloud({ badges = [] }) {
  if (!badges.length) return <span className="muted">Nog geen badges</span>;
  return (
    <div className="badge-cloud">
      {badges.map((badge) => (
        <BadgePill badge={badge} key={badge.key ?? badge.label} />
      ))}
    </div>
  );
}

function badgeProgressFromCatalog(catalog = [], unlockedBadges = []) {
  const unlockedByKey = new Map(unlockedBadges.map((badge) => [badge.key, badge]));
  return catalog.map((badge) => {
    const unlocked = unlockedByKey.get(badge.key);
    return {
      ...badge,
      count: unlocked?.count ?? 0,
      unlocked: Boolean(unlocked),
      current: unlocked ? 1 : 0,
      target: 1,
      progress: unlocked ? 100 : 0,
      unit: "unlock",
    };
  });
}

function BadgeProgressSection({ player, badgeCatalog = [], canView }) {
  const badges = player?.badge_progress?.length
    ? player.badge_progress
    : badgeProgressFromCatalog(badgeCatalog, player?.badges ?? []);
  const unlockedCount = canView ? badges.filter((badge) => badge.unlocked).length : 0;

  return (
    <article className="panel profile-badges">
      <div className="panel-header">
        <div>
          <h3>Badges</h3>
          <p>Unlocked badges and progress toward the next ones.</p>
        </div>
        <span className={canView ? "pill green" : "pill"}>{unlockedCount}/{badges.length}</span>
      </div>
      <div className="panel-body">
        {!canView && (
          <div className="empty compact">Badges are visible when you follow each other.</div>
        )}
        {canView && !badges.length && <div className="empty compact">Geen badges beschikbaar.</div>}
        {canView && !!badges.length && (
          <div className="badge-progress-grid">
            {badges.map((badge) => (
              <article
                className={`badge-progress-card is-${badge.family} ${badge.unlocked ? "is-unlocked" : "is-locked"}`}
                key={badge.key}
              >
                <div className="badge-progress-heading">
                  <span className="badge-progress-mark" aria-hidden="true">{badge.mark ?? "B"}</span>
                  <div>
                    <h4>{badge.label}</h4>
                    <p>{badge.detail}</p>
                  </div>
                </div>
                <div className="badge-progress-track" aria-hidden="true">
                  <span style={{ width: `${badge.progress ?? 0}%` }} />
                </div>
                <div className="badge-progress-meta">
                  <span>{badge.current ?? 0}/{badge.target ?? 1} {badge.unit}</span>
                  <strong>{badge.unlocked ? `Unlocked${badge.count > 1 ? ` x${badge.count}` : ""}` : "Locked"}</strong>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

function BadgeCatalogPage({ badges = [] }) {
  const groupedBadges = badges.reduce((groups, badge) => {
    const family = badge.family ?? "other";
    return { ...groups, [family]: [...(groups[family] ?? []), badge] };
  }, {});

  return (
    <div className="badges-page">
      <article className="panel">
        <div className="panel-header">
          <div>
            <h3>Badge catalogus</h3>
            <p>Alle badges kunnen per speeldag opnieuw worden verdiend.</p>
          </div>
          <span className="pill green">{badges.length} badges</span>
        </div>
        <div className="panel-body badge-catalog">
          {!badges.length && <div className="empty compact">Geen badges beschikbaar.</div>}
          {Object.entries(groupedBadges).map(([family, familyBadges]) => (
            <section className="badge-family" key={family}>
              <div className="badge-family-heading">
                <span className={`badge-family-mark is-${family}`} aria-hidden="true">
                  {familyBadges[0]?.mark ?? "B"}
                </span>
                <div>
                  <h4>{badgeFamilyLabel(family, familyBadges[0]?.mascot)}</h4>
                  <p>{familyBadges[0]?.mascot ?? "Badge familie"}</p>
                </div>
              </div>
              <div className="badge-catalog-grid">
                {familyBadges.map((badge) => (
                  <article className={`badge-catalog-card is-${badge.family}`} key={badge.key}>
                    <BadgePill badge={badge} />
                    <p>{badge.detail}</p>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
      </article>
    </div>
  );
}

function MatchdayPredictionModal({
  match,
  teams,
  pool,
  onClose,
  onPoolUpdate,
}) {
  const [scores, setScores] = useState({ home_score: "", away_score: "" });
  const [quizDraft, setQuizDraft] = useState({ answer: "", viewership_prediction: "" });
  const [leeuwtjeActive, setLeeuwtjeActive] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!match) return;
    const existingQuiz = pool.quiz_predictions?.[match.id] ?? {};
    setScores({ home_score: "", away_score: "" });
    setQuizDraft({
      answer: existingQuiz.answer ?? "",
      viewership_prediction: existingQuiz.viewership_prediction ?? "",
    });
    setLeeuwtjeActive(false);
    setError("");
  }, [match?.id, pool.quiz_predictions]);

  if (!match) return null;

  const leeuwtjeTotal = leeuwtjesTotal(pool);
  const currentLeeuwtjes = new Set(pool.leeuwtjes_match_ids ?? []);
  const leeuwtjesRemaining = Math.max(0, leeuwtjeTotal - currentLeeuwtjes.size);
  const canToggleLeeuwtje = leeuwtjeActive || currentLeeuwtjes.has(match.id) || currentLeeuwtjes.size < leeuwtjeTotal;
  const locked = Boolean(match.locked);

  function setScore(_matchId, key, value) {
    setScores((current) => ({ ...current, [key]: value }));
  }

  function setQuizAnswer(_matchId, value) {
    setQuizDraft((current) => ({ ...current, answer: value }));
  }

  function setQuizViewership(_matchId, value) {
    setQuizDraft((current) => ({ ...current, viewership_prediction: value }));
  }

  async function savePrediction() {
    if (!scoreComplete(scores) || saving || locked) return;
    setSaving(true);
    setError("");
    const body = {
      predictions: [
        {
          match_id: match.id,
          home_score: Number(scores.home_score),
          away_score: Number(scores.away_score),
        },
      ],
    };
    if (match.quiz) {
      body.quiz_predictions = [
        {
          match_id: match.id,
          answer: String(quizDraft.answer ?? "").trim(),
          viewership_prediction:
            quizDraft.viewership_prediction === "" ||
            quizDraft.viewership_prediction === undefined ||
            quizDraft.viewership_prediction === null
              ? null
              : Number(quizDraft.viewership_prediction),
        },
      ];
    }
    if (leeuwtjeActive && !currentLeeuwtjes.has(match.id)) {
      body.leeuwtjes_match_ids = [...new Set([...currentLeeuwtjes, match.id])];
    }

    try {
      const updated = await apiJson("/api/predictions", {
        method: "POST",
        body: JSON.stringify(body),
      });
      onPoolUpdate(updated);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <article className="prediction-modal" role="dialog" aria-modal="true" aria-label="Match prediction" onMouseDown={(event) => event.stopPropagation()}>
        <div className="prediction-modal-header">
          <div>
            <h3><TeamLabel id={match.home_team_id} teams={teams} /> vs <TeamLabel id={match.away_team_id} teams={teams} /></h3>
            <p>{formatDate(match, true)} · {formatTime(match)}</p>
          </div>
          <button className="text-button" type="button" onClick={onClose}>Close</button>
        </div>
        <div className="prediction-modal-body">
          <MatchPredictionEditor
            match={match}
            teams={teams}
            scores={scores}
            locked={locked}
            onScore={setScore}
            onSubmit={savePrediction}
            saving={saving}
            compact
          />
          <MatchQuizEditor
            match={match}
            prediction={quizDraft}
            locked={locked}
            onAnswer={setQuizAnswer}
            onViewership={setQuizViewership}
          />
          <div className="matchday-modal-actions">
            <LeeuwtjeButton
              active={leeuwtjeActive}
              disabled={locked || !canToggleLeeuwtje}
              remaining={leeuwtjesRemaining}
              onToggle={() => setLeeuwtjeActive((current) => !current)}
            />
            <button className="primary-button" type="button" onClick={savePrediction} disabled={!scoreComplete(scores) || saving || locked}>
              {saving ? "Saving..." : "Save prediction"}
            </button>
          </div>
          {error && <span className="form-error">{error}</span>}
        </div>
      </article>
    </div>
  );
}

function MatchdayPage({ pool, teams, venues, onPoolUpdate }) {
  const summary = pool.matchday;
  const [activeMatch, setActiveMatch] = useState(null);

  function statusMessage(match) {
    if (match.has_my_prediction) return "Je voorspelling is ingevuld.";
    if (match.locked) return "Je voorspelling mist, maar deze wedstrijd is gesloten.";
    return "Je voorspelling mist nog. Klik op deze wedstrijd om hem in te vullen.";
  }

  function openMatch(match) {
    if (match.has_my_prediction || match.locked) return;
    setActiveMatch({ ...match, id: match.id ?? match.match_id });
  }

  return (
    <div className="matchday-layout">
      <article className="panel">
        <div className="panel-header">
          <div>
            <h3>{summary?.is_today ? "Wedstrijddag" : "Volgende wedstrijddag"}</h3>
            <p>Wedstrijden, voorspellingen, quizreacties en ingezette Leeuwtjes.</p>
          </div>
          <span className="pill">{summary?.matches?.length ?? 0} matches</span>
        </div>
        <div className="panel-body matchday-body">
          {!summary?.matches?.length && <div className="empty compact">Geen wedstrijden gevonden.</div>}
          {summary?.matches?.map((rawMatch) => {
            const match = { ...rawMatch, id: rawMatch.id ?? rawMatch.match_id };
            const venue = venues.get(match.venue_id);
            const canOpen = !match.has_my_prediction && !match.locked;
            const matchStatusMessage = statusMessage(match);
            return (
              <button
                className={`matchday-card ${match.has_my_prediction ? "is-predicted" : "is-missing"} ${canOpen ? "is-clickable" : ""}`}
                key={match.match_id}
                type="button"
                onClick={() => openMatch(match)}
                aria-disabled={!canOpen}
              >
                <span
                  className={match.has_my_prediction ? "matchday-status is-done" : "matchday-status is-missing"}
                  aria-label={matchStatusMessage}
                  data-tooltip={matchStatusMessage}
                  title={matchStatusMessage}
                >
                  {match.has_my_prediction ? "✓" : "i"}
                </span>
                <span className="match-time">{formatTime(match)}</span>
                <span className="matchday-main">
                  <strong className="match-teams">
                    <TeamLabel id={match.home_team_id} teams={teams} /> <span className="muted">vs</span>{" "}
                    <TeamLabel id={match.away_team_id} teams={teams} />
                  </strong>
                  <span className="match-meta">{formatDate(match, true)} · {venue?.city ?? "Venue to confirm"}</span>
                </span>
                <span className="matchday-side">
                  <OutcomeBreakdown match={match} teams={teams} />
                  <span className="matchday-stats">
                    <span>{match.prediction_count} voorspellingen</span>
                    <span>{match.quiz_answer_count} quiz</span>
                    <span>{match.leeuwtjes_count} Leeuwtjes</span>
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </article>

      <MatchdayPredictionModal
        match={activeMatch}
        teams={teams}
        pool={pool}
        onClose={() => setActiveMatch(null)}
        onPoolUpdate={onPoolUpdate}
      />
    </div>
  );
}

function RankMovement({ movement = 0 }) {
  if (movement > 0) {
    return <span className="rank-movement is-up" aria-label={`Moved up ${movement} ranks`}>▲ {movement}</span>;
  }
  if (movement < 0) {
    return <span className="rank-movement is-down" aria-label={`Moved down ${Math.abs(movement)} ranks`}>▼ {Math.abs(movement)}</span>;
  }
  return <span className="rank-movement is-flat" aria-label="No rank movement">-</span>;
}

function Leaderboard({ pool, onProfile = () => {} }) {
  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <h3>Leaderboard</h3>
          <p>Shows players who completed the Netherlands group.</p>
        </div>
        <span className="pill green">{pool.leaderboard.length} players</span>
      </div>
      <div className="panel-body">
        <div className="leaderboard-legend" aria-label="Leaderboard legend">
          <span className="legend-swatch missing-predictions" aria-hidden="true" />
          <span>missing predictions</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Player</th>
                <th className="numeric">Pts</th>
                <th className="numeric">Exact</th>
                <th className="numeric">Outcome</th>
                <th className="numeric">Quiz pts</th>
                <th className="numeric">Leeuwtjes</th>
                <th className="numeric">Predictions</th>
                <th>Winner</th>
              </tr>
            </thead>
            <tbody>
              {pool.leaderboard.map((row, index) => {
                const missingPredictions = !row.all_predictions_complete;
                const rowClass = [
                  "leaderboard-row",
                  pool.me?.id === row.user_id ? "highlight" : "",
                  missingPredictions ? "has-missing-predictions" : "",
                ].filter(Boolean).join(" ");
                return (
                  <tr key={row.user_id} className={rowClass}>
                    <td>{index + 1}</td>
                    <td>
                      <button className="profile-icon-link" type="button" onClick={() => onProfile(row.user_id)} aria-label={`Open ${row.name} profile`}>
                        <ProfileAvatar player={row} size="small" />
                      </button>
                      <span className="leaderboard-name">
                        <strong>{row.name}</strong>
                        <RankMovement movement={row.rank_movement ?? 0} />
                      </span>
                    </td>
                    <td className="numeric"><strong>{row.points}</strong></td>
                    <td className="numeric">{row.exact_scores}</td>
                    <td className="numeric">{row.outcomes}</td>
                    <td className="numeric">{row.quiz_points ?? 0}</td>
                    <td className="numeric">{row.leeuwtjes_used ?? 0}/{pool.progress?.leeuwtjes_total ?? 5}</td>
                    <td className="numeric">{row.group_stage_predictions}/{row.group_stage_total}</td>
                    <td>{row.winner_pick_name ?? <span className="muted">Not picked</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {!pool.leaderboard.length && <div className="empty">No leaderboard entries yet. Complete the Netherlands group to appear here.</div>}
      </div>
    </article>
  );
}

function PlayerPredictions({ player, canView }) {
  const [predictionGroups, setPredictionGroups] = useState([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [limited, setLimited] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setPredictionGroups([]);
    setError("");
    setLoaded(false);
    setLimited(false);

    if (!player || !canView) {
      setLoaded(true);
      return () => {
        cancelled = true;
      };
    }

    async function loadPredictions() {
      try {
        const result = await apiJson(`/api/profiles/${player.user_id}/predictions`);
        if (!cancelled) {
          setPredictionGroups(result.groups ?? []);
          setLimited(Boolean(result.limited_to_completed_matches));
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoaded(true);
      }
    }

    loadPredictions();
    return () => {
      cancelled = true;
    };
  }, [player?.user_id, canView]);

  return (
    <article className="panel profile-predictions">
      <div className="panel-header">
        <div>
          <h3>Predictions</h3>
          <p>{limited ? "Other players show only matches that have finished." : "Grouped by World Cup group."}</p>
        </div>
      </div>
      <div className="panel-body profile-prediction-body">
        {!canView && (
          <div className="empty compact">Predictions are not available.</div>
        )}
        {canView && !loaded && <div className="empty compact">Loading predictions...</div>}
        {canView && error && <div className="form-error">{error}</div>}
        {canView && loaded && !error && !predictionGroups.length && (
          <div className="empty compact">{limited ? "No finished-match predictions visible yet." : "No predictions filled in yet."}</div>
        )}
        {canView && predictionGroups.map((group) => (
          <section className="profile-prediction-group" key={group.group}>
            <h4>Group {group.group}</h4>
            <div className="profile-prediction-list">
              {group.predictions.map((prediction) => (
                <article className="profile-prediction-row" key={prediction.match_id}>
                  <div>
                    <strong>{prediction.home_team_name} vs {prediction.away_team_name}</strong>
                    <span>{formatDate(prediction, true)} · {formatTime(prediction)}</span>
                    {prediction.quiz_answer && (
                      <span>Quiz: {prediction.quiz_answer}{prediction.viewership_prediction ? ` · ${formatNumber(prediction.viewership_prediction)} kijkers` : ""}</span>
                    )}
                    {prediction.leeuwtje && <span>Leeuwtje ingezet</span>}
                  </div>
                  <b>{prediction.home_score} - {prediction.away_score}</b>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </article>
  );
}

function PlayerProfile({
  player,
  rank,
  relation,
  badgeCatalog,
  onBack,
  onFollow,
  onUnfollow,
}) {
  if (!player) {
    return (
      <article className="panel">
        <div className="panel-body">
          <div className="empty">Player profile not found.</div>
        </div>
      </article>
    );
  }

  const stats = [
    { label: "PTS", value: player.points, detail: "Total points" },
    { label: "Precision", value: player.precision, detail: "Exact scores" },
    { label: "Shooting", value: player.shooting, detail: "Winner goals" },
    { label: "Defence", value: player.defence, detail: "Loser goals" },
    { label: "Games", value: player.scoring_games, detail: "Scored on" },
  ];
  const canViewPredictions = true;
  const canViewBadges = relation === null || relation?.is_friend;
  const rankLabel = rank ? `Rank #${rank}` : "Nog niet gerankt";

  return (
    <div className="profile-page">
      <button className="text-button" type="button" onClick={onBack}>
        Back to leaderboard
      </button>
      <article className="fifa-card">
        <div className="fifa-card-top">
          <div>
            <span className="fifa-rating">{player.points}</span>
            <span className="fifa-position">PTS</span>
            <span className="fifa-rank">{rankLabel}</span>
          </div>
          <ProfileAvatar player={player} size="large" />
        </div>
        <div className="fifa-card-name">
          <h3>{player.name}</h3>
          <p>{player.winner_pick_name ? `Winner pick: ${player.winner_pick_name}` : "No winner picked yet"}</p>
          <div className="profile-actions">
            <FriendButton
              relation={relation}
              onFollow={() => onFollow(player.user_id)}
              onUnfollow={() => onUnfollow(player.user_id)}
            />
            {relation?.is_friend && <span className="pill green">Badges visible</span>}
            {relation?.is_following && !relation?.is_friend && <span className="pill warning">Waiting for follow back</span>}
            {relation?.follows_me && !relation?.is_friend && <span className="pill orange">Follows you</span>}
          </div>
        </div>
        <div className="fifa-stats">
          {stats.map((stat) => (
            <div className="fifa-stat" key={stat.label}>
              <strong>{stat.value}</strong>
              <span>{stat.label}</span>
              <em>{stat.detail}</em>
            </div>
          ))}
        </div>
      </article>
      <BadgeProgressSection player={player} badgeCatalog={badgeCatalog} canView={canViewBadges} />
      <PlayerPredictions player={player} canView={canViewPredictions} />
    </div>
  );
}

function OnboardingActions({ backLabel = "Back", nextLabel, onBack, onNext }) {
  return (
    <div className="onboarding-actions">
      {onBack && (
        <button className="text-button" type="button" onClick={onBack}>
          {backLabel}
        </button>
      )}
      <button className="primary-button" type="button" onClick={onNext}>
        {nextLabel}
      </button>
    </div>
  );
}

function WelcomeStep({ pool, onNext }) {
  return (
    <div className="onboarding-layout">
      <article className="panel onboarding-card">
        <div className="panel-header">
          <div>
            <h3>Welcome, {pool.me.name}</h3>
            <p>Start here before making your first predictions.</p>
          </div>
          <span className="pill orange">Step 1</span>
        </div>
        <div className="panel-body">
          <p className="onboarding-message">
            This is the Talpa WK Pool for the 2026 World Cup. Check the leaderboard to see who is in, then add your Netherlands group predictions. After that first round is done, the app opens straight to the leaderboard.
          </p>
          <OnboardingActions nextLabel="View leaderboard" onNext={onNext} />
        </div>
      </article>
    </div>
  );
}

function LeaderboardPreviewStep({ pool, onBack, onNext, onProfile }) {
  return (
    <div className="onboarding-layout">
      <Leaderboard pool={pool} onProfile={onProfile} />
      <OnboardingActions nextLabel="Continue" onBack={onBack} onNext={onNext} />
    </div>
  );
}

function JoinStep({ onBack, onNext }) {
  return (
    <div className="onboarding-layout">
      <article className="panel onboarding-card">
        <div className="panel-header">
          <div>
            <h3>Wanna join?</h3>
            <p>Fill in the Netherlands group to claim your spot on the leaderboard.</p>
          </div>
          <span className="pill orange">Step 2</span>
        </div>
        <div className="panel-body">
          <p className="onboarding-message">
            Your predictions can be adjusted later until each match locks one hour before kickoff. Start with the Netherlands group, then keep going if you want the full card.
          </p>
          <OnboardingActions nextLabel="Start predictions" onBack={onBack} onNext={onNext} />
        </div>
      </article>
    </div>
  );
}

function PredictionPanel({ data, teams, venues, pool, onPoolUpdate, onContinue, onBack }) {
  const groupMatches = useMemo(
    () => data.matches.filter((match) => match.round === "Group Stage").sort((a, b) => escapeDate(a) - escapeDate(b)),
    [data],
  );
  const matchesByGroup = useMemo(() => {
    const groups = new Map(data.groups.map((group) => [group.id, []]));
    for (const match of groupMatches) {
      groups.get(match.group)?.push(match);
    }
    return groups;
  }, [data.groups, groupMatches]);
  const requiredGroup = data.groups.find((group) => group.teams.includes(NETHERLANDS_ID)) ?? data.groups[0];
  const requiredGroupId = requiredGroup?.id ?? "";
  const initialGroupId = requiredGroupId || data.groups[0]?.id || "";
  const [draft, setDraft] = useState({});
  const [quizDraft, setQuizDraft] = useState({});
  const [leeuwtjeMatchIds, setLeeuwtjeMatchIds] = useState(() => new Set(pool.leeuwtjes_match_ids ?? []));
  const [selectedGroupId, setSelectedGroupId] = useState(initialGroupId);
  const [editingMatchId, setEditingMatchId] = useState("");
  const [winner, setWinner] = useState(pool.winner_pick ?? "");
  const [winnerDirty, setWinnerDirty] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const selectedGroup = data.groups.find((group) => group.id === selectedGroupId);
  const selectedMatches = selectedGroupId ? matchesByGroup.get(selectedGroupId) ?? [] : [];
  const winnerTeam = winner ? teams.get(winner) : null;
  const lockedWinner = winnerLocked(pool);
  const leeuwtjeTotal = leeuwtjesTotal(pool);
  const leeuwtjeUsedCount = leeuwtjeMatchIds.size;
  const leeuwtjesRemaining = Math.max(0, leeuwtjeTotal - leeuwtjeUsedCount);

  useEffect(() => {
    const nextDraft = {};
    const nextQuizDraft = {};
    for (const match of groupMatches) {
      const prediction = pool.predictions[match.id];
      nextDraft[match.id] = {
        home_score: prediction?.home_score ?? "",
        away_score: prediction?.away_score ?? "",
      };
      const quizPrediction = pool.quiz_predictions?.[match.id];
      nextQuizDraft[match.id] = {
        answer: quizPrediction?.answer ?? "",
        viewership_prediction: quizPrediction?.viewership_prediction ?? "",
      };
    }
    setDraft(nextDraft);
    setQuizDraft(nextQuizDraft);
    setLeeuwtjeMatchIds(new Set(pool.leeuwtjes_match_ids ?? []));
    setSelectedGroupId((current) => current || initialGroupId);
  }, [pool, groupMatches, initialGroupId]);

  useEffect(() => {
    if (!winnerDirty) setWinner(pool.winner_pick ?? "");
  }, [pool.winner_pick, winnerDirty]);

  function hasPrediction(match) {
    return scoreComplete(draft[match.id]);
  }

  function groupPredictionCount(groupId) {
    return (matchesByGroup.get(groupId) ?? []).filter(hasPrediction).length;
  }

  const predictedMatchCount = groupMatches.filter(hasPrediction).length;
  const quizPredictedCount = groupMatches.filter((match) => quizAnswerComplete(match.quiz, quizDraft[match.id])).length;
  const requiredMatches = requiredGroupId ? matchesByGroup.get(requiredGroupId) ?? [] : groupMatches;
  const requiredPredictedCount = requiredMatches.filter(hasPrediction).length;
  const requiredPredictionsComplete = Boolean(requiredMatches.length && requiredPredictedCount >= requiredMatches.length);
  const missingRequiredCount = Math.max(0, requiredMatches.length - requiredPredictedCount);
  const selectedGroupPredictionCount = selectedGroup ? groupPredictionCount(selectedGroup.id) : 0;
  const progressPercent = groupMatches.length ? Math.round((predictedMatchCount / groupMatches.length) * 100) : 0;
  const allPredictionsComplete = predictedMatchCount === groupMatches.length;

  function chooseGroup(groupId) {
    setSelectedGroupId(groupId);
    setEditingMatchId("");
    setError("");
  }

  function setScore(matchId, key, value) {
    setDraft((current) => ({
      ...current,
      [matchId]: { ...current[matchId], [key]: value },
    }));
  }

  function setQuizAnswer(matchId, value) {
    setQuizDraft((current) => ({
      ...current,
      [matchId]: { ...current[matchId], answer: value },
    }));
  }

  function setQuizViewership(matchId, value) {
    setQuizDraft((current) => ({
      ...current,
      [matchId]: { ...current[matchId], viewership_prediction: value },
    }));
  }

  function toggleLeeuwtje(matchId) {
    setLeeuwtjeMatchIds((current) => {
      const next = new Set(current);
      if (next.has(matchId)) {
        next.delete(matchId);
        return next;
      }
      if (next.size >= leeuwtjeTotal) return next;
      next.add(matchId);
      return next;
    });
  }

  function chooseWinner(value) {
    setWinner(value);
    setWinnerDirty(true);
    setError("");
  }

  async function save(closeEditor = false, options = {}) {
    setSaving(true);
    setError("");
    const predictions = draftPredictions(draft);
    const body = {
      predictions,
      quiz_predictions: draftQuizPredictions(quizDraft),
      leeuwtjes_match_ids: [...leeuwtjeMatchIds],
    };
    if (Object.hasOwn(options, "winnerTeamId")) {
      body.winner_team_id = options.winnerTeamId || null;
    }

    try {
      const updated = await apiJson("/api/predictions", {
        method: "POST",
        body: JSON.stringify(body),
      });
      onPoolUpdate(updated);
      if (Object.hasOwn(options, "winnerTeamId")) setWinnerDirty(false);
      if (closeEditor) setEditingMatchId("");
      return updated;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function continueToLeaderboard() {
    const updated = await save(true, { winnerTeamId: winner });
    if (updated) onContinue(updated);
  }

  return (
    <div className="pool-layout">
      <article className="panel prediction-guide">
        <div className="panel-header">
          <div>
            <h3>{selectedGroup ? `Group ${selectedGroup.id}: make predictions` : "Make predictions"}</h3>
            <p>Work through the schedule and watch your predicted table update.</p>
          </div>
          <div className="panel-header-actions">
            {onBack && (
              <button className="text-button" type="button" onClick={onBack}>
                Back home
              </button>
            )}
          </div>
        </div>
        <div className="panel-body">
          <section className={winnerTeam ? "winner-spotlight-card has-winner" : "winner-spotlight-card"} aria-label="World Cup winner pick">
            <div className="winner-trophy" aria-hidden="true"><img src={TROPHY_SRC} alt="" /></div>
            <div className="winner-spotlight-copy">
              <span className="game-kicker">World Cup winner</span>
              <h4>{winnerTeam ? `${teamFlag(winnerTeam.id)} ${winnerTeam.name}` : "Pick your champion"}</h4>
              <p>
                {winnerTeam
                  ? "Your trophy pick sits at the top of this prediction card."
                  : "Choose the country you think will lift the trophy."}
              </p>
            </div>
            <label className="winner-select winner-select-inline">
              Winner
              <select value={winner} onChange={(event) => chooseWinner(event.target.value)} disabled={lockedWinner}>
                <option value="">Choose a winner</option>
                {data.teams.slice().sort((a, b) => a.name.localeCompare(b.name)).map((team) => (
                  <option key={team.id} value={team.id}>{teamFlag(team.id)} {team.name}</option>
                ))}
              </select>
            </label>
          </section>

          <section className="prediction-game-card" aria-label="Prediction progress">
            <div>
              <span className="game-kicker">Total prediction progress</span>
              <h4>{predictedMatchCount} of {groupMatches.length} group fixtures predicted</h4>
              <p>{quizPredictedCount} quizvragen ingevuld · {leeuwtjeUsedCount}/{leeuwtjeTotal} Leeuwtjes ingezet.</p>
            </div>
            <div className="game-score">
              <strong>{progressPercent}%</strong>
              <span>complete</span>
            </div>
            <div className="prediction-progress-track" aria-hidden="true">
              <span style={{ width: `${progressPercent}%` }} />
            </div>
          </section>

          <div className="prediction-group-switcher" aria-label="Prediction groups">
            {data.groups.map((group) => {
              const total = matchesByGroup.get(group.id)?.length ?? 0;
              const predicted = groupPredictionCount(group.id);
              return (
                <button
                  className={group.id === selectedGroupId ? "group-switch is-active" : "group-switch"}
                  key={group.id}
                  type="button"
                  onClick={() => chooseGroup(group.id)}
                >
                  <span className="group-mini-flags">{group.teams.map((teamId) => <span key={teamId}>{teamFlag(teamId)}</span>)}</span>
                  <strong>Group {group.id}</strong>
                  <em>{predicted}/{total}</em>
                </button>
              );
            })}
          </div>

          {selectedGroup && (
            <div className="prediction-workspace">
              <PredictedStandingsTable
                group={selectedGroup}
                matches={selectedMatches}
                teams={teams}
                predictions={draft}
              />

              <section className="prediction-schedule-panel">
                <div className="prediction-step-header">
                  <div>
                    <h4>Group {selectedGroup.id} schedule</h4>
                    <p>Click a score to edit it. Press OK or Enter to save and return to view mode.</p>
                  </div>
                </div>

                <div className="prediction-fixture-list" aria-label={`Group ${selectedGroup.id} schedule`}>
                  {selectedMatches.map((match, index) => {
                    const scores = draft[match.id] ?? {};
                    const lock = matchLock(pool, match.id);
                    const locked = Boolean(lock.locked);
                    return (
                      <MatchPredictionRow
                        key={match.id}
                        match={match}
                        index={index}
                        teams={teams}
                        venues={venues}
                        scores={scores}
                        quizPrediction={quizDraft[match.id]}
                        locked={locked}
                        editing={editingMatchId === match.id}
                        saving={saving}
                        leeuwtjeActive={leeuwtjeMatchIds.has(match.id)}
                        canToggleLeeuwtje={leeuwtjeMatchIds.has(match.id) || leeuwtjeMatchIds.size < leeuwtjeTotal}
                        leeuwtjesRemaining={leeuwtjesRemaining}
                        onEdit={() => setEditingMatchId(match.id)}
                        onScore={setScore}
                        onQuizAnswer={setQuizAnswer}
                        onQuizViewership={setQuizViewership}
                        onToggleLeeuwtje={() => toggleLeeuwtje(match.id)}
                        onSubmit={() => save(true)}
                      />
                    );
                  })}
                </div>

                <div className="prediction-actions">
                  <button className="primary-button" type="button" onClick={() => save(true)} disabled={saving}>
                    {saving ? "Saving..." : "Save progress"}
                  </button>
                  {error && <span className="form-error">{error}</span>}
                </div>
              </section>
            </div>
          )}

          <article className={requiredPredictionsComplete ? "prediction-continue-card is-ready" : "prediction-continue-card"}>
            <div>
              <h4>{requiredPredictionsComplete ? "Ready for the leaderboard" : "Finish the essentials"}</h4>
              <p>
                {requiredPredictionsComplete && winner && allPredictionsComplete
                  ? "Full card, trophy pick set. Time to check the leaderboard."
                  : requiredPredictionsComplete && winner
                    ? "Your prediction card still has some empty spots. No prediction, no points — the scoreboard is strict like that."
                    : requiredPredictionsComplete
                      ? "You can pick your World Cup winner above now or continue to the leaderboard."
                    : requiredPredictedCount === 0
                      ? "Fill in the Netherlands group first, then pick your World Cup winner."
                      : `You still need ${missingRequiredCount} score prediction${missingRequiredCount === 1 ? "" : "s"} in the Netherlands group before you can continue.`}
              </p>
            </div>
            <button className="primary-button" type="button" onClick={continueToLeaderboard} disabled={!requiredPredictionsComplete || saving}>
              {saving ? "Saving..." : "Continue"}
            </button>
          </article>
        </div>
      </article>
    </div>
  );
}

function AdjustPredictionsPanel({ data, teams, venues, pool, onPoolUpdate, onBack }) {
  const groupMatches = useMemo(
    () => data.matches.filter((match) => match.round === "Group Stage").sort((a, b) => escapeDate(a) - escapeDate(b)),
    [data],
  );
  const matchesByGroup = useMemo(() => {
    const groups = new Map(data.groups.map((group) => [group.id, []]));
    for (const match of groupMatches) {
      groups.get(match.group)?.push(match);
    }
    return groups;
  }, [data.groups, groupMatches]);
  const [draft, setDraft] = useState({});
  const [quizDraft, setQuizDraft] = useState({});
  const [leeuwtjeMatchIds, setLeeuwtjeMatchIds] = useState(() => new Set(pool.leeuwtjes_match_ids ?? []));
  const [selectedGroupId, setSelectedGroupId] = useState(data.groups[0]?.id ?? "");
  const [editingMatchId, setEditingMatchId] = useState("");
  const [winner, setWinner] = useState(pool.winner_pick ?? "");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const [dirty, setDirty] = useState(false);

  const selectedGroup = data.groups.find((group) => group.id === selectedGroupId);
  const selectedMatches = selectedGroupId ? matchesByGroup.get(selectedGroupId) ?? [] : [];
  const lockedWinner = winnerLocked(pool);
  const winnerTeam = winner ? teams.get(winner) : null;
  const leeuwtjeTotal = leeuwtjesTotal(pool);
  const leeuwtjesRemaining = Math.max(0, leeuwtjeTotal - leeuwtjeMatchIds.size);

  useEffect(() => {
    const nextDraft = {};
    const nextQuizDraft = {};
    for (const match of groupMatches) {
      const prediction = pool.predictions[match.id];
      nextDraft[match.id] = {
        home_score: prediction?.home_score ?? "",
        away_score: prediction?.away_score ?? "",
      };
      const quizPrediction = pool.quiz_predictions?.[match.id];
      nextQuizDraft[match.id] = {
        answer: quizPrediction?.answer ?? "",
        viewership_prediction: quizPrediction?.viewership_prediction ?? "",
      };
    }
    setDraft(nextDraft);
    setQuizDraft(nextQuizDraft);
    setLeeuwtjeMatchIds(new Set(pool.leeuwtjes_match_ids ?? []));
    setWinner(pool.winner_pick ?? "");
    setInitialized(true);
    setDirty(false);
  }, [pool, groupMatches]);

  function setScore(matchId, key, value) {
    setDraft((current) => ({
      ...current,
      [matchId]: { ...current[matchId], [key]: value },
    }));
    setDirty(true);
  }

  function chooseWinner(value) {
    setWinner(value);
    setDirty(true);
  }

  function setQuizAnswer(matchId, value) {
    setQuizDraft((current) => ({
      ...current,
      [matchId]: { ...current[matchId], answer: value },
    }));
    setDirty(true);
  }

  function setQuizViewership(matchId, value) {
    setQuizDraft((current) => ({
      ...current,
      [matchId]: { ...current[matchId], viewership_prediction: value },
    }));
    setDirty(true);
  }

  function toggleLeeuwtje(matchId) {
    setLeeuwtjeMatchIds((current) => {
      const next = new Set(current);
      if (next.has(matchId)) {
        next.delete(matchId);
      } else if (next.size < leeuwtjeTotal) {
        next.add(matchId);
      }
      return next;
    });
    setDirty(true);
  }

  function hasPrediction(match) {
    return scoreComplete(draft[match.id]);
  }

  function groupPredictionCount(groupId) {
    return (matchesByGroup.get(groupId) ?? []).filter(hasPrediction).length;
  }

  async function save(closeEditor = false) {
    setSaving(true);
    setError("");
    try {
      const updated = await apiJson("/api/predictions", {
        method: "POST",
        body: JSON.stringify({
          predictions: draftPredictions(draft),
          quiz_predictions: draftQuizPredictions(quizDraft),
          leeuwtjes_match_ids: [...leeuwtjeMatchIds],
          winner_team_id: winner || null,
        }),
      });
      onPoolUpdate(updated);
      if (closeEditor) setEditingMatchId("");
      setDirty(false);
      return updated;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    if (!initialized || !dirty) return undefined;
    const timer = window.setTimeout(() => {
      save();
    }, 700);
    return () => window.clearTimeout(timer);
  }, [draft, quizDraft, leeuwtjeMatchIds, winner, initialized, dirty]);

  async function saveAndGoHome() {
    const updated = await save(true);
    if (updated && onBack) onBack();
  }

  return (
    <div className="pool-layout">
      <article className="panel prediction-guide">
        <div className="panel-header">
          <div>
            <h3>Adjust predictions</h3>
            <p>Change scores and your World Cup winner until each lock moment.</p>
          </div>
          <div className="panel-header-actions">
            {onBack && (
              <button className="text-button" type="button" onClick={onBack}>
                Back home
              </button>
            )}
            <button className="primary-button" type="button" onClick={saveAndGoHome} disabled={saving}>
              {saving ? "Saving..." : "Save changes"}
            </button>
          </div>
        </div>
        <div className="panel-body">
          <section className={winnerTeam ? "winner-spotlight-card has-winner" : "winner-spotlight-card"} aria-label="World Cup winner pick">
            <div className="winner-trophy" aria-hidden="true"><img src={TROPHY_SRC} alt="" /></div>
            <div className="winner-spotlight-copy">
              <span className="game-kicker">World Cup winner</span>
              <h4>{winnerTeam ? `${teamFlag(winnerTeam.id)} ${winnerTeam.name}` : "Pick your champion"}</h4>
              <p>Editable until one hour before the tournament opener.</p>
            </div>
            <label className="winner-select winner-select-inline">
              Winner
              <select value={winner} onChange={(event) => chooseWinner(event.target.value)} disabled={lockedWinner}>
                <option value="">Choose a winner</option>
                {data.teams.slice().sort((a, b) => a.name.localeCompare(b.name)).map((team) => (
                  <option key={team.id} value={team.id}>{teamFlag(team.id)} {team.name}</option>
                ))}
              </select>
            </label>
            <LockPill lock={{ locked: lockedWinner }} />
          </section>

          <div className="prediction-group-switcher" aria-label="Prediction groups">
            {data.groups.map((group) => {
              const total = matchesByGroup.get(group.id)?.length ?? 0;
              const predicted = groupPredictionCount(group.id);
              return (
                <button
                  className={group.id === selectedGroupId ? "group-switch is-active" : "group-switch"}
                  key={group.id}
                  type="button"
                  onClick={() => {
                    setSelectedGroupId(group.id);
                    setEditingMatchId("");
                  }}
                >
                  <span className="group-mini-flags">{group.teams.map((teamId) => <span key={teamId}>{teamFlag(teamId)}</span>)}</span>
                  <strong>Group {group.id}</strong>
                  <em>{predicted}/{total}</em>
                </button>
              );
            })}
          </div>

          {selectedGroup && (
            <div className="prediction-workspace">
              <section className="comparison-grid" aria-label={`Group ${selectedGroup.id} table comparison`}>
                <article className="prediction-table-panel">
                  <div className="prediction-step-header">
                    <div>
                      <h4>Live Group {selectedGroup.id} table</h4>
                      <p>Current table from completed match results.</p>
                    </div>
                    <span className="pill">Live</span>
                  </div>
                  <StandingsTable group={selectedGroup} matches={data.matches} teams={teams} />
                </article>
                <PredictedStandingsTable
                  group={selectedGroup}
                  matches={selectedMatches}
                  teams={teams}
                  predictions={draft}
                />
              </section>

              <section className="prediction-schedule-panel">
                <div className="prediction-step-header">
                  <div>
                    <h4>Group {selectedGroup.id} schedule</h4>
                    <p>Locked rows are read-only; open rows can still be changed.</p>
                  </div>
                </div>
                <div className="prediction-fixture-list">
                  {selectedMatches.map((match, index) => {
                    const scores = draft[match.id] ?? {};
                    const lock = matchLock(pool, match.id);
                    const locked = Boolean(lock.locked);
                    return (
                      <MatchPredictionRow
                        key={match.id}
                        match={match}
                        index={index}
                        teams={teams}
                        venues={venues}
                        scores={scores}
                        quizPrediction={quizDraft[match.id]}
                        locked={locked}
                        editing={editingMatchId === match.id}
                        saving={saving}
                        leeuwtjeActive={leeuwtjeMatchIds.has(match.id)}
                        canToggleLeeuwtje={leeuwtjeMatchIds.has(match.id) || leeuwtjeMatchIds.size < leeuwtjeTotal}
                        leeuwtjesRemaining={leeuwtjesRemaining}
                        onEdit={() => setEditingMatchId(match.id)}
                        onScore={setScore}
                        onQuizAnswer={setQuizAnswer}
                        onQuizViewership={setQuizViewership}
                        onToggleLeeuwtje={() => toggleLeeuwtje(match.id)}
                        onSubmit={() => save(true)}
                        compact
                      />
                    );
                  })}
                </div>
              </section>
            </div>
          )}
          {error && <div className="prediction-actions"><span className="form-error">{error}</span></div>}
        </div>
      </article>
    </div>
  );
}

function NotificationBell({ notifications, open, onToggle, onPredictions }) {
  const count = notifications.reduce((total, notification) => total + notification.count, 0);
  return (
    <div className="notification-wrap">
      <button
        className={count ? "notification-button has-items" : "notification-button"}
        type="button"
        onClick={onToggle}
        aria-label={`${count} open acties`}
        aria-expanded={open}
      >
        <span aria-hidden="true">🔔</span>
        {count > 0 && <b>{Math.min(count, 99)}</b>}
      </button>
      {open && (
        <div className="notification-popover" role="dialog" aria-label="Open acties">
          <div className="notification-title">
            <strong>Nog te doen</strong>
            <span>{notifications.length}/2 meldingen</span>
          </div>
          {notifications.length ? (
            notifications.map((notification) => (
              <article key={notification.type} className="notification-item">
                <strong>{notification.title}</strong>
                <p>{notification.body}</p>
              </article>
            ))
          ) : (
            <div className="empty compact">Geen open acties voor vandaag of morgen.</div>
          )}
          <button className="primary-button" type="button" onClick={onPredictions}>
            Open predictions
          </button>
        </div>
      )}
    </div>
  );
}

function fallbackProfile(pool) {
  const user = pool.me;
  if (!user) return null;
  const progress = pool.progress ?? {};
  return {
    user_id: user.id,
    name: user.name,
    points: 0,
    precision: 0,
    shooting: 0,
    defence: 0,
    scoring_games: 0,
    winner_pick_name: null,
    profile_picture: {
      initials: user.name
        .replace("-", " ")
        .split(" ")
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0])
        .join("")
        .toUpperCase() || "?",
      hue: 24,
    },
    group_stage_predictions: progress.group_stage_predictions ?? 0,
    group_stage_total: progress.group_stage_total ?? 0,
    badges: [],
  };
}

function App() {
  const [data, setData] = useState(null);
  const [pool, setPool] = useState(null);
  const [social, setSocial] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [view, setView] = useState(() => viewFromRoute(window.location.pathname) ?? "leaderboard");
  const [selectedProfileId, setSelectedProfileId] = useState(() => profileIdFromRoute(window.location.pathname));
  const [selectedTeamId, setSelectedTeamId] = useState(() => teamIdFromRoute(window.location.pathname));
  const [now, setNow] = useState(() => new Date());
  const [notificationsOpen, setNotificationsOpen] = useState(false);

  function replacePath(path) {
    if (normalizeRoute(window.location.pathname) !== path) {
      window.history.replaceState({}, "", path);
    }
  }

  function navigateToView(nextView, options = {}) {
    setNotificationsOpen(false);
    setView(nextView);
    const route = routeForView(nextView, selectedProfileId, selectedTeamId);
    const historyMethod = options.replace ? "replaceState" : "pushState";
    if (normalizeRoute(window.location.pathname) !== route) {
      window.history[historyMethod]({}, "", route);
    }
  }

  function navigateToProfile(userId) {
    const profileId = String(userId);
    setSelectedProfileId(profileId);
    setView("profile");
    const route = profileRoute(profileId);
    if (normalizeRoute(window.location.pathname) !== route) {
      window.history.pushState({}, "", route);
    }
  }

  function navigateToTeam(teamId) {
    const nextTeamId = String(teamId);
    setSelectedTeamId(nextTeamId);
    setView("team");
    const route = teamRoute(nextTeamId);
    if (normalizeRoute(window.location.pathname) !== route) {
      window.history.pushState({}, "", route);
    }
  }

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 30000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    function handlePopState() {
      const profileId = profileIdFromRoute(window.location.pathname);
      const teamId = teamIdFromRoute(window.location.pathname);
      setSelectedProfileId(profileId);
      setSelectedTeamId(teamId);
      if (pool?.me) {
        const nextView = authenticatedViewFromRoute(pool, window.location.pathname);
        setView(nextView);
        if (normalizeRoute(window.location.pathname) !== routeForView(nextView, profileId, teamId)) {
          replacePath(routeForView(nextView, profileId, teamId));
        }
        return;
      }
      setView(viewFromRoute(window.location.pathname) ?? "leaderboard");
    }

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [pool]);

  useEffect(() => {
    let cancelled = false;

    async function loadInitialState() {
      try {
        const poolState = await apiJson("/api/pool");
        if (cancelled) return;
        setPool(poolState);

        if (!poolState.me) {
          replacePath("/login");
          return;
        }

        if (poolState.me) {
          const [worldCup, socialState] = await Promise.all([
            apiJson("/api/world-cup"),
            apiJson("/api/social"),
          ]);
          if (!cancelled) {
            setData(worldCup);
            setSocial(socialState);
            const nextView = authenticatedViewFromRoute(poolState, window.location.pathname);
            const profileId = profileIdFromRoute(window.location.pathname);
            const teamId = teamIdFromRoute(window.location.pathname);
            setSelectedProfileId(profileId);
            setSelectedTeamId(teamId);
            setView(nextView);
            if (normalizeRoute(window.location.pathname) !== routeForView(nextView, profileId, teamId)) {
              replacePath(routeForView(nextView, profileId, teamId));
            }
          }
        }
      } catch (error) {
        console.error(error);
        if (!cancelled) setLoadError(error.message);
      } finally {
        if (!cancelled) setAuthChecked(true);
      }
    }

    loadInitialState();
    return () => {
      cancelled = true;
    };
  }, []);

  const socialById = useMemo(() => {
    return new Map((social?.people ?? []).map((person) => [person.user_id, person]));
  }, [social]);

  const maps = useMemo(() => {
    if (!data) return { teams: new Map(), venues: new Map() };
    return {
      teams: new Map(data.teams.map((team) => [team.id, team])),
      venues: new Map(data.venues.map((venue) => [venue.id, venue])),
    };
  }, [data]);

  const sortedMatches = useMemo(() => {
    if (!data) return [];
    return data.matches.slice().sort((a, b) => escapeDate(a) - escapeDate(b));
  }, [data]);

  async function handleLogin() {
    setLoadError("");
    const [worldCup, poolState, socialState] = await Promise.all([
      apiJson("/api/world-cup"),
      apiJson("/api/pool"),
      apiJson("/api/social"),
    ]);
    setData(worldCup);
    setPool(poolState);
    setSocial(socialState);
    navigateToView(defaultAuthenticatedView(poolState), { replace: true });
  }

  async function logout() {
    await apiJson("/api/auth/logout", { method: "POST", body: "{}" });
    setData(null);
    setSocial(null);
    setPool(await apiJson("/api/pool"));
    setView("leaderboard");
    replacePath("/login");
  }

  function updatePoolOnly(updatedPool) {
    setPool(updatedPool);
  }

  function continueToLeaderboard(updatedPool) {
    if (updatedPool) setPool(updatedPool);
    navigateToView("leaderboard");
  }

  async function followPerson(userId) {
    const socialState = await apiJson("/api/social/follow", {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    });
    setSocial(socialState);
  }

  async function unfollowPerson(userId) {
    const socialState = await apiJson(`/api/social/follow/${userId}`, {
      method: "DELETE",
    });
    setSocial(socialState);
  }

  if (!authChecked) {
    return <div className="loading">Loading Talpa WK Pool...</div>;
  }

  if (loadError) {
    return (
      <div className="loading">
        <div className="load-error">Could not load Talpa WK Pool: {loadError}</div>
      </div>
    );
  }

  if (!pool?.me) {
    return <LoginPage onLogin={handleLogin} />;
  }

  if (!data) {
    return <div className="loading">Loading Talpa WK Pool...</div>;
  }

  const kickoff = new Date("2026-06-11T19:00:00Z");
  const countdown = formatCountdown(kickoff, now);
  const entryComplete = groupPredictionsComplete(pool);
  const selectedProfile = (
    pool.leaderboard.find((row) => String(row.user_id) === selectedProfileId) ??
    (String(pool.me?.id) === selectedProfileId ? fallbackProfile(pool) : null)
  );
  const selectedProfileRank = selectedProfile
    ? pool.leaderboard.findIndex((row) => row.user_id === selectedProfile.user_id) + 1
    : 0;
  const selectedTeam = maps.teams.get(selectedTeamId) ?? null;
  const venueRows = data.venues;

  return (
    <>
      <header className="app-header">
        <div className="brand-lockup">
          <FieldMark />
          <div>
            <p className="eyebrow">FIFA World Cup 2026</p>
            <h1>Talpa WK Pool</h1>
          </div>
        </div>
        <div className="header-actions">
          <NotificationBell
            notifications={pool.notifications ?? []}
            open={notificationsOpen}
            onToggle={() => setNotificationsOpen((current) => !current)}
            onPredictions={() => navigateToView(entryComplete ? "adjust" : "pool")}
          />
          <button
            className="data-badge is-clickable"
            type="button"
            onClick={() => navigateToProfile(pool.me.id)}
          >
            {pool.me.name}
          </button>
          {entryComplete && (
            <button className="text-button" type="button" onClick={() => navigateToView("adjust")}>
              Adjust predictions
            </button>
          )}
          <button className="text-button" type="button" onClick={logout}>
            Logout
          </button>
        </div>
      </header>

      <main>
        <section className="hero-panel">
          <div className="hero-copy">
            <p className="eyebrow">FIFA World Cup 2026</p>
            <h2>Talpa WK Pool</h2>
            <p>
              Predict group-stage scores, pick the World Cup winner and follow the leaderboard.
            </p>
          </div>
          <div className="hero-countdown" aria-label="Countdown to kickoff">
            <span>Countdown to kickoff</span>
            <div
              className="clock-display"
              aria-label={`${countdown.days} days ${countdown.hours} hours ${countdown.minutes} minutes`}
            >
              <strong>{countdown.days}</strong>
              <b>:</b>
              <strong>{countdown.hours}</strong>
              <b>:</b>
              <strong>{countdown.minutes}</strong>
            </div>
            <div className="clock-labels" aria-hidden="true">
              <span>Days</span>
              <span>Hours</span>
              <span>Minutes</span>
            </div>
          </div>
        </section>

        {entryComplete && (
          <nav className="tabs" aria-label="Dashboard views">
            {["home", "matchday", "leaderboard", "groups", "teams", "schedule", "venues"].map((item) => {
              const active = view === item || (view === "team" && item === "teams");
              return (
                <button key={item} className={active ? "tab is-active" : "tab"} type="button" onClick={() => navigateToView(item)}>
                  {viewLabel(item)}
                </button>
              );
            })}
          </nav>
        )}

        {view === "welcome" && (
          <section className="view is-active">
            <WelcomeStep pool={pool} onNext={() => navigateToView("leaderboardPreview")} />
          </section>
        )}

        {view === "leaderboardPreview" && (
          <section className="view is-active">
            <LeaderboardPreviewStep
              pool={pool}
              onBack={() => navigateToView("welcome")}
              onNext={() => navigateToView("join")}
              onProfile={navigateToProfile}
            />
          </section>
        )}

        {view === "home" && (
          <section className="view is-active">
            <HomePage onSchedule={() => navigateToView("schedule")} recap={pool.daily_recap} />
          </section>
        )}

        {view === "matchday" && (
          <section className="view is-active">
            <MatchdayPage
              pool={pool}
              teams={maps.teams}
              venues={maps.venues}
              onPoolUpdate={updatePoolOnly}
            />
          </section>
        )}

        {view === "join" && (
          <section className="view is-active">
            <JoinStep
              onBack={() => navigateToView("leaderboardPreview")}
              onNext={() => navigateToView("pool")}
            />
          </section>
        )}

        {view === "pool" && (
          <section className="view is-active">
            <PredictionPanel
              data={data}
              teams={maps.teams}
              venues={maps.venues}
              pool={pool}
              onPoolUpdate={updatePoolOnly}
              onContinue={continueToLeaderboard}
              onBack={entryComplete ? () => navigateToView("leaderboard") : null}
            />
          </section>
        )}

        {view === "adjust" && (
          <section className="view is-active">
            <AdjustPredictionsPanel
              data={data}
              teams={maps.teams}
              venues={maps.venues}
              pool={pool}
              onPoolUpdate={updatePoolOnly}
              onBack={() => navigateToView("home")}
            />
          </section>
        )}

        {view === "leaderboard" && (
          <section className="view is-active">
            <Leaderboard pool={pool} onProfile={navigateToProfile} />
          </section>
        )}

        {view === "profile" && (
          <section className="view is-active">
            <PlayerProfile
              player={selectedProfile}
              rank={selectedProfileRank}
              relation={selectedProfile?.user_id === pool.me?.id ? null : socialById.get(selectedProfile?.user_id)}
              badgeCatalog={pool.badge_catalog ?? []}
              onBack={() => navigateToView("leaderboard")}
              onFollow={followPerson}
              onUnfollow={unfollowPerson}
            />
          </section>
        )}

        {view === "groups" && (
          <section className="view is-active">
            <div className="groups-grid">
              {data.groups.map((group) => <GroupPanel key={group.id} group={group} data={data} teams={maps.teams} />)}
            </div>
          </section>
        )}

        {view === "teams" && (
          <section className="view is-active">
            <TeamDirectoryPage data={data} teams={maps.teams} onTeam={navigateToTeam} />
          </section>
        )}

        {view === "team" && (
          <section className="view is-active">
            <TeamDetailPage
              team={selectedTeam}
              data={data}
              teams={maps.teams}
              venues={maps.venues}
              onBack={() => navigateToView("teams")}
            />
          </section>
        )}

        {view === "schedule" && (
          <section className="view is-active">
            <Schedule matches={sortedMatches} teams={maps.teams} venues={maps.venues} />
          </section>
        )}

        {view === "venues" && (
          <section className="view is-active">
            <div className="grid">
              {venueRows.map((venue) => {
                const matchCount = data.matches.filter((match) => match.venue_id === venue.id).length;
                return (
                  <article key={venue.id} className="venue-row">
                    <div>
                      <h3>{venue.name}</h3>
                      <div className="meta">{venue.city}, {venue.country} · {venue.timezone}</div>
                    </div>
                    <span className="pill">{matchCount} matches</span>
                  </article>
                );
              })}
            </div>
          </section>
        )}
      </main>
    </>
  );
}

const rootElement = document.getElementById("root");
rootElement.__wkHubRoot ??= createRoot(rootElement);
rootElement.__wkHubRoot.render(<App />);
