import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const AMSTERDAM_TZ = "Europe/Amsterdam";
const MATCHDAY_SESSION_END_HOUR = 4;
const NETHERLANDS_ID = "ned";
const TROPHY_SRC = "/world-cup-trophy.svg";
const POINTS_POPOVER_EVENT = "wk-points-popover-open";
const DISMISSED_BADGE_NOTIFICATIONS_KEY = "wk-dismissed-badge-notifications";
const TEAM_FLAG_CODES = {
  alg: "dz",
  arg: "ar",
  aus: "au",
  aut: "at",
  bel: "be",
  bih: "ba",
  bra: "br",
  can: "ca",
  civ: "ci",
  cod: "cd",
  col: "co",
  cpv: "cv",
  cro: "hr",
  cuw: "cw",
  cze: "cz",
  ecu: "ec",
  egy: "eg",
  eng: "gb-eng",
  esp: "es",
  fra: "fr",
  ger: "de",
  gha: "gh",
  hai: "ht",
  irn: "ir",
  irq: "iq",
  jor: "jo",
  jpn: "jp",
  kor: "kr",
  ksa: "sa",
  mar: "ma",
  mex: "mx",
  ned: "nl",
  nor: "no",
  nzl: "nz",
  pan: "pa",
  par: "py",
  por: "pt",
  qat: "qa",
  rsa: "za",
  sco: "gb-sct",
  sen: "sn",
  sui: "ch",
  swe: "se",
  tun: "tn",
  tur: "tr",
  uru: "uy",
  usa: "us",
  uzb: "uz",
};

function badgeNotificationKey(notification) {
  const badgeKeys = (notification?.badges ?? [])
    .map((badge) => badge.key ?? badge.label)
    .filter(Boolean)
    .sort();
  if (badgeKeys.length) return badgeKeys.join("|");
  return `${notification?.title ?? ""}|${notification?.body ?? ""}`;
}

function readDismissedBadgeNotificationKeys() {
  try {
    return JSON.parse(
      window.localStorage.getItem(DISMISSED_BADGE_NOTIFICATIONS_KEY) ?? "[]",
    );
  } catch {
    return [];
  }
}

function writeDismissedBadgeNotificationKeys(keys) {
  window.localStorage.setItem(
    DISMISSED_BADGE_NOTIFICATIONS_KEY,
    JSON.stringify(Array.from(keys)),
  );
}

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

function formatSessionDate(date) {
  const [year, month, day] = String(date ?? "")
    .split("-")
    .map((part) => Number(part));
  if (!year || !month || !day) return "";
  return new Intl.DateTimeFormat("nl-NL", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date(Date.UTC(year, month - 1, day, 12)));
}

function formatTime(match) {
  return new Intl.DateTimeFormat("nl-NL", {
    timeZone: AMSTERDAM_TZ,
    hour: "2-digit",
    minute: "2-digit",
  }).format(escapeDate(match));
}

function formatDateTimeIso(value) {
  if (!value) return "Unknown";
  return new Intl.DateTimeFormat("nl-NL", {
    timeZone: AMSTERDAM_TZ,
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
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

function dateKey(date) {
  return date.toISOString().slice(0, 10);
}

function amsterdamDateParts(date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: AMSTERDAM_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return {
    year: Number(values.year),
    month: Number(values.month),
    day: Number(values.day),
    hour: Number(values.hour),
  };
}

function tournamentSessionDateKeyFromDate(date) {
  const { year, month, day, hour } = amsterdamDateParts(date);
  if (!year || !month || !day) return "";
  const sessionDate = new Date(Date.UTC(year, month - 1, day, 12));
  if (hour <= MATCHDAY_SESSION_END_HOUR) {
    sessionDate.setUTCDate(sessionDate.getUTCDate() - 1);
  }
  return dateKey(sessionDate);
}

function tournamentSessionDateKey(match) {
  return tournamentSessionDateKeyFromDate(escapeDate(match));
}

function scheduleGroupedPredictions(groups) {
  const predictions = (groups ?? [])
    .flatMap((group) => group.predictions ?? [])
    .filter((prediction) => prediction?.date && prediction?.time_utc)
    .sort((left, right) => escapeDate(left) - escapeDate(right));
  const grouped = new Map();
  for (const prediction of predictions) {
    const key = localDateKey(prediction);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(prediction);
  }
  return [...grouped.entries()].map(([date, datePredictions]) => ({
    group: date,
    date,
    predictions: datePredictions,
  }));
}

function defaultAuthenticatedView() {
  return "home";
}

const VIEW_ROUTES = {
  home: "/home",
  welcome: "/welcome",
  leaderboardPreview: "/leaderboard-preview",
  join: "/join",
  leaderboard: "/leaderboard",
  admin: "/admin",
  groups: "/tables",
  teams: "/teams",
  schedule: "/schedule",
  venues: "/venues",
  faq: "/faq",
  matchday: "/matchday",
  knockout: "/knockout",
  pool: "/predictions",
  adjust: "/predictions/adjust",
};

const ROUTE_VIEWS = Object.fromEntries(
  Object.entries(VIEW_ROUTES).map(([view, route]) => [route, view]),
);
const ONBOARDING_VIEWS = new Set(["welcome", "leaderboardPreview", "join"]);

const NEWS_ARTICLES = [
  {
    title: "WK 2026 levert landen recordbedrag op",
    publisher: "NU.nl",
    country: "Netherlands",
    summary:
      "FIFA raises the prize pool for the 2026 World Cup, with a larger base payout for every qualified country.",
    url: "https://www.nu.nl/voetbal/6379805/wk-2026-levert-landen-recordbedrag-op-wereldkampioen-krijgt-42-miljoen-euro.html",
  },
  {
    title: "FIFA WK voetbal 2026 en 2030 live bij de NOS",
    publisher: "NOS",
    country: "Netherlands",
    summary:
      "NOS outlines its broadcast role for the 2026 and 2030 men’s World Cups.",
    url: "https://over.nos.nl/nieuws/fifa-wk-voetbal-2026-en-2030-live-bij-de-nos/",
  },
  {
    title: "Het volledige speelschema van de Rode Duivels",
    publisher: "VoetbalPrimeur.be",
    country: "Belgium",
    summary:
      "Belgian coverage of the Red Devils’ group-stage schedule, opponents and kick-off windows.",
    url: "https://www.voetbalprimeur.be/nieuws/1718992/wk-voetbal-2026-ontdek-hier-het-volledige-speelschema-van-de-rode-duivels.html",
  },
  {
    title: "WK 2026 wordt luxeproduct",
    publisher: "VoetbalPrimeur.be",
    country: "Belgium",
    summary:
      "A Belgian fan-facing look at World Cup ticket prices and allocation pressure.",
    url: "https://www.voetbalprimeur.be/nieuws/1721351/wk-2026-wordt-luxeproduct-dit-kosten-tickets-voor-wedstrijden-van-de-rode-duivels.html",
  },
];

const PROFILE_IMAGE_MAX_DIMENSION = 512;
const PROFILE_IMAGE_MAX_UPLOAD_BYTES = 750 * 1024;
const TALPA_EMAIL_PATTERN =
  /^[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*@talpa(?:network|studios)\.com$/i;

function normalizeRoute(pathname) {
  const path = pathname.replace(/\/+$/, "");
  return path || "/";
}

function viewFromRoute(pathname) {
  const path = normalizeRoute(pathname);
  if (/^\/profile\/\d+$/.test(path)) return "profile";
  if (/^\/teams\/[a-z0-9-]+$/i.test(path)) return "team";
  if (/^\/matchday\/[a-z0-9-]+$/i.test(path)) return "matchdayMatch";
  if (path === VIEW_ROUTES.pool) return "adjust";
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

function matchdayMatchIdFromRoute(pathname) {
  return normalizeRoute(pathname).match(/^\/matchday\/([a-z0-9-]+)$/i)?.[1] ?? "";
}

function matchdayMatchRoute(matchId) {
  return `/matchday/${matchId}`;
}

function routeForView(view, profileId = "", teamId = "", matchdayMatchId = "") {
  if (view === "profile" && profileId) return profileRoute(profileId);
  if (view === "team" && teamId) return teamRoute(teamId);
  if (view === "matchdayMatch" && matchdayMatchId) {
    return matchdayMatchRoute(matchdayMatchId);
  }
  return VIEW_ROUTES[view] ?? VIEW_ROUTES.leaderboard;
}

const KNOCKOUT_ROUND_ORDER = [
  "Round of 32",
  "Round of 16",
  "Quarter-final",
  "Semi-final",
  "Third-place play-off",
  "Final",
];

function onboardingViewAllowed(_poolState, routedView) {
  if (!routedView) return false;
  return !ONBOARDING_VIEWS.has(routedView);
}

function authenticatedViewFromRoute(poolState, pathname) {
  const routedView = viewFromRoute(pathname);
  if (routedView === "admin" && !poolState?.me?.is_admin) {
    return defaultAuthenticatedView(poolState);
  }
  if (onboardingViewAllowed(poolState, routedView)) return routedView;
  return defaultAuthenticatedView(poolState);
}

function TeamFlag({ id, className = "team-flag" }) {
  const [imageFailed, setImageFailed] = useState(false);
  const code = TEAM_FLAG_CODES[id];
  if (!code || imageFailed) {
    const fallback = String(id ?? "").toUpperCase();
    return fallback ? (
      <span className={`${className} flag-fallback`} aria-hidden="true">
        {fallback}
      </span>
    ) : null;
  }
  return (
    <img
      className={`${className} flag-icon`}
      src={`https://flagcdn.com/${code}.svg`}
      alt=""
      aria-hidden="true"
      loading="lazy"
      onError={() => setImageFailed(true)}
    />
  );
}

function teamOptionLabel(team) {
  return `${team.code ?? team.id.toUpperCase()} - ${team.name}`;
}

function matchLock(pool, matchId) {
  return pool?.locks?.matches?.[matchId] ?? { locked: false, lock_at: null };
}

function winnerLocked(pool) {
  return Boolean(
    pool?.locks?.tournament_picks_locked ?? pool?.locks?.winner_locked,
  );
}

function tournamentPicksRevealed(pool) {
  return Boolean(pool?.visibility?.tournament_picks_revealed);
}

function poolPredictions(pool) {
  return pool?.predictions && typeof pool.predictions === "object" ? pool.predictions : {};
}

function poolQuizPredictions(pool) {
  return pool?.quiz_predictions && typeof pool.quiz_predictions === "object" ? pool.quiz_predictions : {};
}

function poolLeeuwtjeMatchIds(pool) {
  return Array.isArray(pool?.leeuwtjes_match_ids) ? pool.leeuwtjes_match_ids : [];
}

function poolMatchPoints(pool) {
  return pool?.match_points && typeof pool.match_points === "object"
    ? pool.match_points
    : {};
}

function poolKnockout(pool) {
  return pool?.knockout && typeof pool.knockout === "object"
    ? pool.knockout
    : { is_relevant: false, rounds: [], missing_actions: [] };
}

function knockoutMatches(knockout) {
  return (knockout?.rounds ?? []).flatMap((round) => round.matches ?? []);
}

function knockoutMatchById(knockout, matchId) {
  return knockoutMatches(knockout).find((match) => match.id === matchId) ?? null;
}

function knockoutSideLabel(side) {
  if (!side) return "Nog onbekend";
  return side.kind === "team" ? side.name : side.label;
}

function knockoutSideTeamId(side) {
  return side?.kind === "team" ? side.id : "";
}

function knockoutStatusLabel(status) {
  if (status === "open") return "Open";
  if (status === "locked") return "Locked";
  if (status === "completed") return "Played";
  return "Path";
}

function poolStrikerPicks(pool) {
  return Array.isArray(pool?.striker_picks)
    ? pool.striker_picks
    : Array.isArray(pool?.top_scorer_picks)
      ? pool.top_scorer_picks
      : [];
}

function viewLabel(view) {
  const labels = {
    home: "Home",
    leaderboard: "Leaderboard",
    groups: "Tables",
    teams: "Teams",
    schedule: "Schedule",
    matchday: "Matchday",
    knockout: "Knockout",
    venues: "Venues",
    admin: "Admin",
    faq: "FAQ",
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
  if (!response.ok)
    throw new Error(data?.error || `API returned ${response.status}`);
  return data ?? {};
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(reader.result));
    reader.addEventListener("error", () =>
      reject(new Error("De afbeelding kon niet worden gelezen.")),
    );
    reader.readAsDataURL(file);
  });
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.addEventListener("load", () => resolve(image));
    image.addEventListener("error", () =>
      reject(new Error("De afbeelding kon niet worden geladen.")),
    );
    image.src = src;
  });
}

async function resizeProfileImage(file) {
  if (!file?.type?.startsWith("image/")) {
    throw new Error("Kies een afbeelding.");
  }

  const sourceUrl = await fileToDataUrl(file);
  const image = await loadImage(sourceUrl);
  const scale = Math.min(
    1,
    PROFILE_IMAGE_MAX_DIMENSION /
    Math.max(image.naturalWidth, image.naturalHeight),
  );
  const width = Math.max(1, Math.round(image.naturalWidth * scale));
  const height = Math.max(1, Math.round(image.naturalHeight * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  context.drawImage(image, 0, 0, width, height);

  const dataUrl = canvas.toDataURL("image/jpeg", 0.86);
  const estimatedBytes = Math.ceil(
    (dataUrl.length - dataUrl.indexOf(",") - 1) * 0.75,
  );
  if (estimatedBytes > PROFILE_IMAGE_MAX_UPLOAD_BYTES) {
    throw new Error("Kies een kleinere afbeelding.");
  }
  return dataUrl;
}

function FieldMark() {
  return (
    <svg
      className="brand-mark"
      viewBox="0 0 240 240"
      fill="none"
      aria-hidden="true"
    >
      <rect x="10" y="10" width="220" height="220" rx="26" fill="#F36C21" />
      <path d="M10 74H230V105H10V74Z" fill="#FFFFFF" fillOpacity="0.9" />
      <path d="M10 135H230V166H10V135Z" fill="#21468B" fillOpacity="0.92" />
      <rect
        x="29"
        y="29"
        width="182"
        height="182"
        rx="12"
        stroke="#FFFFFF"
        strokeWidth="8"
      />
      <path d="M120 30V210" stroke="#FFFFFF" strokeWidth="7" />
      <circle cx="120" cy="120" r="32" stroke="#FFFFFF" strokeWidth="7" />
      <circle cx="120" cy="120" r="7" fill="#FFFFFF" />
      <path d="M29 82H58V158H29" stroke="#FFFFFF" strokeWidth="7" />
      <path d="M211 82H182V158H211" stroke="#FFFFFF" strokeWidth="7" />
      <path d="M29 101H43V139H29" stroke="#FFFFFF" strokeWidth="6" />
      <path d="M211 101H197V139H211" stroke="#FFFFFF" strokeWidth="6" />
      <path
        d="M52 204C82 184 119 184 150 204C170 216 192 216 211 206"
        stroke="#00A7B5"
        strokeWidth="10"
        strokeLinecap="round"
      />
    </svg>
  );
}

function TeamLabel({ id, teams }) {
  const team = teams.get(id);
  return (
    <span className="team-inline">
      <TeamFlag id={id} />
      <span
        className={
          id === NETHERLANDS_ID ? "team-name highlight-text" : "team-name"
        }
      >
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
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <span className={className}>
      <TeamFlag id={id} className="team-badge-flag" />
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
  return [person?.club, person?.country, person?.age ? `${person.age} yrs` : ""]
    .filter(Boolean)
    .join(" · ");
}

function teamCoach(team) {
  const profile = teamProfile(team);
  return (
    profile.head_coach ??
    profile.coach ??
    team?.head_coach ??
    team?.coach ??
    null
  );
}

function teamStaff(team) {
  const profile = teamProfile(team);
  return normalizePeople(
    profile.staff ??
    profile.coaching_staff ??
    team?.staff ??
    team?.coaching_staff,
  );
}

function teamPlayers(team) {
  const profile = teamProfile(team);
  return normalizePeople(
    profile.players ??
    profile.squad ??
    profile.roster ??
    team?.players ??
    team?.squad ??
    team?.roster,
  );
}

function teamSources(team) {
  const profile = teamProfile(team);
  return normalizePeople(profile.sources ?? team?.sources);
}

function topScorerOptions(data) {
  const options = [];
  const teams = [...(data?.teams ?? [])].sort((a, b) =>
    a.name.localeCompare(b.name),
  );
  for (const team of teams) {
    const players = teamPlayers(team)
      .map((player) => {
        const name = personName(player);
        if (!name || name === "To be confirmed") return null;
        const role = personRole(player);
        const isAttacker = /forward|striker|wing|attack|aanval/i.test(role);
        return {
          name,
          label: name,
          teamId: team.id,
          teamName: team.name,
          country: team.name,
          preferred: isAttacker ? 0 : 1,
        };
      })
      .filter(Boolean)
      .sort(
        (a, b) => a.preferred - b.preferred || a.name.localeCompare(b.name),
      );
    for (const player of players) {
      const name = personName(player);
      options.push({
        name,
        label: player.label,
        teamId: player.teamId,
        teamName: player.teamName,
        country: player.country ?? player.teamName,
        preferred: player.preferred,
      });
    }
  }
  return options;
}

function normalizedPlayerPickName(value) {
  return String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/gi, "")
    .trim()
    .toLocaleLowerCase();
}

function playerPickDetails(name, options) {
  const normalized = normalizedPlayerPickName(name);
  if (!normalized) return null;
  const option = options.find(
    (candidate) => normalizedPlayerPickName(candidate.name) === normalized,
  );
  return {
    name: option?.name ?? String(name).trim(),
    teamId: option?.teamId ?? "",
    country: option?.country ?? option?.teamName ?? "",
  };
}

function PlayerPickDisplay({ pick, options, fallback = "Niet gekozen" }) {
  const details = playerPickDetails(pick, options);
  if (!details) return <span>{fallback}</span>;
  return (
    <span className="player-pick-display">
      {details.teamId && <TeamFlag id={details.teamId} />}
      <span>
        <strong>{details.name}</strong>
        {details.country && <em>{details.country}</em>}
      </span>
    </span>
  );
}

const QUIZ_TEAM_ALIASES = {
  arg: ["argentinie", "argentinië", "argentina"],
  bra: ["brazilie", "brazilië", "brazil"],
  eng: ["engeland", "england"],
  ned: ["nederland", "nederlandse", "netherlands"],
  por: ["portugal"],
};

function quizTeamIds(match, teams) {
  const question = (match?.quiz?.question ?? "").toLocaleLowerCase();
  const matchTeamIds = [match?.home_team_id, match?.away_team_id].filter(
    Boolean,
  );
  const explicitTeamIds = matchTeamIds.filter((teamId) => {
    const team = teams.get(teamId);
    const aliases = [
      team?.name,
      team?.code,
      ...(QUIZ_TEAM_ALIASES[teamId] ?? []),
    ].filter(Boolean);
    return aliases.some((alias) =>
      question.includes(alias.toLocaleLowerCase()),
    );
  });
  return explicitTeamIds.length ? explicitTeamIds : matchTeamIds;
}

function matchPlayerOptions(match, teams, teamIds = null) {
  const optionTeamIds =
    teamIds ?? [match?.home_team_id, match?.away_team_id].filter(Boolean);
  const options = [];
  const seen = new Set();
  for (const teamId of optionTeamIds) {
    const team = teams.get(teamId);
    for (const player of teamPlayers(team)) {
      const name = personName(player);
      if (!name || name === "To be confirmed") continue;
      const key = `${name.toLocaleLowerCase()}-${teamId}`;
      if (seen.has(key)) continue;
      seen.add(key);
      options.push({
        name,
        label: `${name} (${team?.name ?? teamId})`,
      });
    }
  }
  return options.sort((a, b) => a.name.localeCompare(b.name));
}

function quizChoicePoint(quiz, choice) {
  const choicePoints = quiz?.choice_points ?? {};
  const directPoints = choicePoints[choice];
  if (directPoints !== undefined) return directPoints;
  const normalizedChoice = String(choice ?? "")
    .trim()
    .toLocaleLowerCase();
  const matchedEntry = Object.entries(choicePoints).find(
    ([key]) => String(key).trim().toLocaleLowerCase() === normalizedChoice,
  );
  return matchedEntry?.[1];
}

function quizChoiceLabel(label, points) {
  if (points === undefined || points === null || points === "") return label;
  return `${label} (${points} pts)`;
}

function quizChoices(match, teams) {
  const quiz = match?.quiz;
  if (!quiz) return [];
  if (quiz.choices?.length) {
    return quiz.choices.map((choice) => ({
      value: choice,
      label: quizChoiceLabel(choice, quizChoicePoint(quiz, choice)),
    }));
  }
  if (quiz.type === "number") return [];
  if (
    /speler|scoort|man van de wedstrijd|schot op doel/i.test(
      quiz.question ?? "",
    )
  ) {
    const points = quiz.dynamic_choice_points ?? quiz.choice_points?.default;
    return matchPlayerOptions(match, teams, quizTeamIds(match, teams)).map(
      (option) => ({
        value: option.name,
        label: quizChoiceLabel(option.label, points),
      }),
    );
  }
  return [];
}

function topScorerPickFromPool(pool) {
  return pool?.top_scorer_pick ?? "";
}

function strikerPicksFromPool(pool) {
  const picks = poolStrikerPicks(pool);
  return [
    picks[0] ?? "",
    picks[1] ?? "",
    picks[2] ?? "",
    picks[3] ?? "",
    picks[4] ?? "",
  ];
}

function playerOptionDisplay(option, fallback = "") {
  if (!option) return fallback;
  return option.teamName
    ? `${option.label} — ${option.teamName}`
    : option.label;
}

function PlayerSearchSelect({
  label,
  value,
  options,
  locked,
  onChange,
  selectedValues = [],
  currentIndex = -1,
  idPrefix = "player-search",
}) {
  const selectedOption = options.find((option) => option.name === value);
  const selectedDisplay = playerOptionDisplay(selectedOption, value ?? "");
  const [query, setQuery] = useState(selectedDisplay);
  const [open, setOpen] = useState(false);
  const valueRef = useRef(value);

  useEffect(() => {
    setQuery(selectedDisplay);
  }, [selectedDisplay]);

  useEffect(() => {
    valueRef.current = value;
  }, [value]);

  const filteredOptions = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    const matches = needle
      ? options.filter(
        (option) =>
          option.name.toLocaleLowerCase().includes(needle) ||
          (option.teamName ?? "").toLocaleLowerCase().includes(needle),
      )
      : options;
    return matches.slice(0, 40);
  }, [options, query]);

  function selectedElsewhere(option) {
    return selectedValues.some(
      (pick, pickIndex) =>
        pickIndex !== currentIndex && pick && pick === option.name,
    );
  }

  function chooseOption(option) {
    if (selectedElsewhere(option)) return;
    onChange(option.name);
    setQuery(playerOptionDisplay(option));
    setOpen(false);
  }

  function clearSelection() {
    onChange("");
    setQuery("");
    setOpen(false);
  }

  return (
    <label className="player-search-select winner-select winner-select-inline">
      <span>{label}</span>
      <div
        className={locked ? "player-search-box is-locked" : "player-search-box"}
      >
        <input
          id={`${idPrefix}-${currentIndex}`}
          type="text"
          value={query}
          disabled={locked}
          placeholder="Typ speler of team"
          autoComplete="off"
          onFocus={() => {
            setOpen(true);
            if (query === selectedDisplay) setQuery("");
          }}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onBlur={() => {
            window.setTimeout(() => {
              const current = valueRef.current;
              setOpen(false);
              setQuery(
                playerOptionDisplay(
                  options.find((option) => option.name === current),
                  current ?? "",
                ),
              );
            }, 120);
          }}
        />
        {value && !locked && (
          <button
            className="player-search-clear"
            type="button"
            onMouseDown={(event) => event.preventDefault()}
            onTouchStart={(event) => event.preventDefault()}
            onClick={clearSelection}
            aria-label={`Wis ${label}`}
          >
            ×
          </button>
        )}
        {open && !locked && (
          <div
            className="player-search-menu"
            role="listbox"
            aria-label={`${label} opties`}
          >
            {filteredOptions.length ? (
              filteredOptions.map((option) => {
                const disabled = selectedElsewhere(option);
                return (
                  <button
                    key={`${idPrefix}-${currentIndex}-${option.teamId}-${option.name}`}
                    className={
                      disabled
                        ? "player-search-option is-disabled"
                        : "player-search-option"
                    }
                    type="button"
                    disabled={disabled}
                    onMouseDown={(event) => event.preventDefault()}
                    onTouchStart={(event) => event.preventDefault()}
                    onClick={() => chooseOption(option)}
                    role="option"
                    aria-selected={option.name === value}
                  >
                    <strong>{option.label}</strong>
                    <span>
                      {option.teamName}
                      {disabled ? " · al gekozen" : ""}
                    </span>
                  </button>
                );
              })
            ) : (
              <div className="player-search-empty">Geen spelers gevonden</div>
            )}
          </div>
        )}
      </div>
    </label>
  );
}

function PlayerPickSelects({
  label,
  picks,
  options,
  locked,
  onChange,
  idPrefix = "player-pick",
}) {
  return (
    <div className="top-scorer-selects">
      {picks.map((pick, index) => (
        <PlayerSearchSelect
          key={index}
          label={`${label} ${index + 1}`}
          value={pick ?? ""}
          options={options}
          locked={locked}
          selectedValues={picks}
          currentIndex={index}
          onChange={(nextValue) => onChange(index, nextValue)}
          idPrefix={idPrefix}
        />
      ))}
    </div>
  );
}

function TournamentPickSummary({
  winnerTeam,
  topScorer,
  strikers,
  options,
  locked,
  editing,
  onEdit,
}) {
  const filledStrikers = strikers.filter(Boolean);
  return (
    <div className="tournament-pick-summary">
      <div className="tournament-pick-summary-header">
        <span className="game-kicker">View mode</span>
        {!locked && !editing && (
          <button className="text-button" type="button" onClick={onEdit}>
            Edit
          </button>
        )}
      </div>
      <div className="tournament-pick-summary-grid">
        <div className="tournament-pick-summary-item">
          <strong>Kampioen</strong>
          <span className="winner-team-title">
            {winnerTeam ? (
              <>
                <TeamFlag id={winnerTeam.id} /> {winnerTeam.name}
              </>
            ) : (
              "Niet gekozen"
            )}
          </span>
        </div>
        <div className="tournament-pick-summary-item">
          <strong>Topscorer</strong>
          <PlayerPickDisplay pick={topScorer} options={options} />
        </div>
        <div className="tournament-pick-summary-item is-wide">
          <strong>Spitsen</strong>
          {filledStrikers.length ? (
            <div className="tournament-striker-summary-list">
              {strikers.map((pick, index) => (
                <span key={`${pick || "empty"}-${index}`}>
                  <em>{index + 1}</em>
                  <PlayerPickDisplay
                    pick={pick}
                    options={options}
                    fallback="Niet gekozen"
                  />
                </span>
              ))}
            </div>
          ) : (
            <span>Niet gekozen</span>
          )}
        </div>
      </div>
    </div>
  );
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
  return (
    homeScore !== undefined &&
    homeScore !== null &&
    homeScore !== "" &&
    awayScore !== undefined &&
    awayScore !== null &&
    awayScore !== ""
  );
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
  return Boolean(answer);
}

function quizDraftHasValue(prediction) {
  return Boolean(String(prediction?.answer ?? "").trim());
}

function draftQuizPredictions(draft, existing = {}) {
  return Object.entries(draft)
    .filter(
      ([match_id, prediction]) =>
        quizDraftHasValue(prediction) || existing[match_id],
    )
    .map(([match_id, prediction]) => ({
      match_id,
      answer: String(prediction?.answer ?? "").trim(),
    }));
}

function leeuwtjesUsed(pool) {
  return (
    pool?.progress?.leeuwtjes_used ?? pool?.leeuwtjes_match_ids?.length ?? 0
  );
}

function leeuwtjesTotal(pool) {
  return pool?.progress?.leeuwtjes_total ?? pool?.rules?.leeuwtjes_total ?? 5;
}

function formatNumber(value) {
  if (value === undefined || value === null || value === "") return "";
  return new Intl.NumberFormat("nl-NL").format(Number(value));
}

function scoreInputValue(value) {
  return String(value ?? "")
    .replace(/\D/g, "")
    .slice(0, 2);
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
  showSubmit = true,
}) {
  const canSubmit = scoreComplete(scores) && !locked && !saving;

  function submitOnEnter(event) {
    if (event.key !== "Enter" || !showSubmit || !canSubmit) return;
    event.preventDefault();
    onSubmit?.();
  }

  const className = [
    "fixture-score-grid",
    compact ? "is-compact" : "",
    compact ? "is-score-only" : "",
    showSubmit ? "" : "has-no-submit",
  ]
    .filter(Boolean)
    .join(" ");

  if (compact) {
    return (
      <div className={className}>
        <input
          aria-label={`${teams.get(match.home_team_id)?.name ?? "Home"} score`}
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          autoComplete="off"
          value={scores?.home_score ?? ""}
          disabled={locked}
          onFocus={(event) => event.target.select()}
          onChange={(event) =>
            onScore(match.id, "home_score", scoreInputValue(event.target.value))
          }
          onKeyDown={submitOnEnter}
        />
        <span className="fixture-score-separator">-</span>
        <input
          aria-label={`${teams.get(match.away_team_id)?.name ?? "Away"} score`}
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          autoComplete="off"
          value={scores?.away_score ?? ""}
          disabled={locked}
          onFocus={(event) => event.target.select()}
          onChange={(event) =>
            onScore(match.id, "away_score", scoreInputValue(event.target.value))
          }
          onKeyDown={submitOnEnter}
        />
        {showSubmit && (
          <button
            className="fixture-ok-button"
            type="button"
            onClick={onSubmit}
            disabled={!canSubmit}
          >
            {saving ? "Saving..." : "OK"}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className={className}>
      <label className="fixture-team-input is-home">
        <TeamBadge id={match.home_team_id} teams={teams} />
        <input
          aria-label={`${teams.get(match.home_team_id)?.name ?? "Home"} score`}
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          autoComplete="off"
          value={scores?.home_score ?? ""}
          disabled={locked}
          onFocus={(event) => event.target.select()}
          onChange={(event) =>
            onScore(match.id, "home_score", scoreInputValue(event.target.value))
          }
          onKeyDown={submitOnEnter}
        />
      </label>
      <span className="fixture-score-separator">-</span>
      <label className="fixture-team-input is-away">
        <TeamBadge id={match.away_team_id} teams={teams} align="right" />
        <input
          aria-label={`${teams.get(match.away_team_id)?.name ?? "Away"} score`}
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          autoComplete="off"
          value={scores?.away_score ?? ""}
          disabled={locked}
          onFocus={(event) => event.target.select()}
          onChange={(event) =>
            onScore(match.id, "away_score", scoreInputValue(event.target.value))
          }
          onKeyDown={submitOnEnter}
        />
      </label>
      {showSubmit && (
        <button
          className="fixture-ok-button"
          type="button"
          onClick={onSubmit}
          disabled={!canSubmit}
        >
          {saving ? "Saving..." : "OK"}
        </button>
      )}
    </div>
  );
}

function MatchQuizEditor({
  match,
  teams,
  prediction,
  locked,
  onAnswer,
}) {
  const quiz = match.quiz;
  if (!quiz) return null;
  const answer = prediction?.answer ?? "";
  const complete = quizAnswerComplete(quiz, prediction);
  const choices = quizChoices(match, teams);

  return (
    <section
      className={complete ? "fixture-quiz is-complete" : "fixture-quiz"}
      aria-label="Quizvraag"
    >
      <div className="fixture-quiz-heading">
        <div>
          <strong>{quiz.question}</strong>
        </div>
      </div>
      <div className="fixture-quiz-inputs">
        <label>
          Antwoord
          {choices.length ? (
            <select
              aria-label="Antwoord"
              value={answer}
              disabled={locked}
              onChange={(event) => onAnswer(match.id, event.target.value)}
            >
              <option value="">Kies antwoord</option>
              {choices.map((choice) => (
                <option key={choice.value} value={choice.value}>
                  {choice.label}
                </option>
              ))}
            </select>
          ) : quiz.type === "number" ? (
            <input
              aria-label="Antwoord"
              value={answer}
              disabled={locked}
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={12}
              placeholder="Vul een getal in"
              onChange={(event) => onAnswer(match.id, event.target.value)}
            />
          ) : (
            <input
              aria-label="Antwoord"
              value={answer}
              disabled={locked}
              maxLength={160}
              placeholder="Typ je antwoord"
              onChange={(event) => onAnswer(match.id, event.target.value)}
            />
          )}
        </label>
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
      title={
        active
          ? "Leeuwtje ingezet voor deze wedstrijd"
          : "Verdubbel punten voor deze wedstrijd"
      }
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
  onToggleLeeuwtje,
  onSubmit,
  compact = false,
  quickEntry = false,
  focused = false,
}) {
  const complete = scoreComplete(scores);
  const venue = venues.get(match.venue_id);

  return (
    <article
      className={[
        "prediction-fixture-row",
        editing && !quickEntry ? "is-active" : "",
        focused ? "is-focused" : "",
        complete ? "is-complete" : "",
        locked ? "is-locked" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="fixture-row-header">
        <div className="fixture-open-button as-static">
          <span className="fixture-number">{index + 1}</span>
          <span>
            <strong>
              <TeamLabel id={match.home_team_id} teams={teams} />{" "}
              <TeamLabel id={match.away_team_id} teams={teams} />
            </strong>
            <em>
              {formatDate(match, true)} · {formatTime(match)} ·{" "}
              {venue?.city ?? "Venue to confirm"}
            </em>
          </span>
        </div>
        <div className="fixture-row-status">
          <LeeuwtjeButton
            active={leeuwtjeActive}
            disabled={locked || !canToggleLeeuwtje}
            remaining={leeuwtjesRemaining}
            onToggle={onToggleLeeuwtje}
          />
          <PredictionStatusPill
            complete={complete}
            active={false}
            locked={locked}
          />
          <LockPill lock={{ locked }} />
        </div>
      </div>

      <MatchPredictionEditor
        match={match}
        teams={teams}
        scores={scores}
        locked={locked}
        onScore={onScore}
        onSubmit={onSubmit}
        saving={saving}
        compact={compact}
        showSubmit={!quickEntry}
      />
      <MatchQuizEditor
        match={match}
        teams={teams}
        prediction={quizPrediction}
        locked={locked}
        onAnswer={onQuizAnswer}
      />
    </article>
  );
}

function predictionScoreLabel(prediction) {
  if (!scoreComplete(prediction)) return "... - ...";
  return `${prediction.home_score} - ${prediction.away_score}`;
}

function KnockoutSide({ side }) {
  const label = knockoutSideLabel(side);
  if (side?.kind === "team") {
    return (
      <span className="knockout-side is-team">
        <TeamFlag id={side.id} />
        <strong>{label}</strong>
      </span>
    );
  }
  return (
    <span className="knockout-side is-slot">
      <em>{label}</em>
    </span>
  );
}

function KnockoutMatchTile({ match, selected, onSelect }) {
  const missingCount = match.missing_actions?.length ?? 0;
  return (
    <button
      className={[
        "knockout-tile",
        selected ? "is-selected" : "",
        `is-${match.status ?? "not_yet_actionable"}`,
        missingCount ? "has-missing" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      type="button"
      onClick={onSelect}
    >
      <span className="knockout-tile-meta">
        <b>#{match.match_number}</b>
        <em>{knockoutStatusLabel(match.status)}</em>
      </span>
      <KnockoutSide side={match.home} />
      <KnockoutSide side={match.away} />
      {missingCount > 0 && (
        <span className="knockout-missing-badge">{missingCount}</span>
      )}
    </button>
  );
}

function knockoutDetailMatch(match) {
  return {
    id: match.id,
    date: match.date,
    time_utc: match.kickoff_at?.slice(11, 16),
    round: match.round,
    home_team_id: knockoutSideTeamId(match.home),
    away_team_id: knockoutSideTeamId(match.away),
    quiz: match.quiz,
  };
}

function KnockoutPage({ pool, teams, onPoolUpdate, focusMatchId = "" }) {
  const knockout = poolKnockout(pool);
  const allMatches = knockoutMatches(knockout);
  const firstMissingMatchId = knockout.missing_actions?.[0]?.match_id ?? "";
  const [selectedMatchId, setSelectedMatchId] = useState(
    () => focusMatchId || firstMissingMatchId || allMatches[0]?.id || "",
  );
  const selectedMatch =
    knockoutMatchById(knockout, selectedMatchId) ?? allMatches[0] ?? null;
  const [scores, setScores] = useState({ home_score: "", away_score: "" });
  const [quizDraft, setQuizDraft] = useState({ answer: "" });
  const [leeuwtjeActive, setLeeuwtjeActive] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!focusMatchId) return;
    if (knockoutMatchById(knockout, focusMatchId)) {
      setSelectedMatchId(focusMatchId);
    }
  }, [focusMatchId, knockout]);

  useEffect(() => {
    if (!selectedMatch) return;
    setScores({
      home_score: selectedMatch.prediction?.home_score ?? "",
      away_score: selectedMatch.prediction?.away_score ?? "",
    });
    setQuizDraft({ answer: selectedMatch.quiz_prediction?.answer ?? "" });
    setLeeuwtjeActive(Boolean(selectedMatch.leeuwtje));
    setError("");
  }, [selectedMatch?.id, selectedMatch?.prediction, selectedMatch?.quiz_prediction, selectedMatch?.leeuwtje]);

  function setScore(_matchId, key, value) {
    setScores((current) => ({ ...current, [key]: value }));
  }

  function setQuizAnswer(_matchId, value) {
    setQuizDraft({ answer: value });
  }

  async function saveSelected() {
    if (!selectedMatch) return;
    setSaving(true);
    setError("");
    const nextLeeuwtjes = new Set(poolLeeuwtjeMatchIds(pool));
    if (leeuwtjeActive) {
      nextLeeuwtjes.add(selectedMatch.id);
    } else {
      nextLeeuwtjes.delete(selectedMatch.id);
    }
    try {
      const updated = await apiJson("/api/predictions", {
        method: "POST",
        body: JSON.stringify({
          predictions: scoreComplete(scores)
            ? [
              {
                match_id: selectedMatch.id,
                home_score: Number(scores.home_score),
                away_score: Number(scores.away_score),
              },
            ]
            : [],
          quiz_predictions: selectedMatch.quiz
            ? [
              {
                match_id: selectedMatch.id,
                answer: String(quizDraft.answer ?? "").trim(),
              },
            ]
            : [],
          leeuwtjes_match_ids: [...nextLeeuwtjes],
        }),
      });
      onPoolUpdate(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (!allMatches.length) {
    return (
      <article className="panel knockout-page">
        <div className="panel-header">
          <div>
            <h3>Knockout</h3>
            <p>The Knockout Stage schedule is not available yet.</p>
          </div>
        </div>
      </article>
    );
  }

  const detailMatch = selectedMatch ? knockoutDetailMatch(selectedMatch) : null;
  const openForPredictions = selectedMatch?.status === "open";
  const locked = !openForPredictions;
  const canToggleLeeuwtje =
    leeuwtjeActive || poolLeeuwtjeMatchIds(pool).length < leeuwtjesTotal(pool);
  const quizAnswer = String(quizDraft.answer ?? "").trim();
  const existingQuizAnswer = String(
    selectedMatch?.quiz_prediction?.answer ?? "",
  ).trim();
  const canSaveSelected =
    openForPredictions &&
    (scoreComplete(scores) ||
      (selectedMatch?.quiz && quizAnswer !== existingQuizAnswer) ||
      Boolean(selectedMatch?.leeuwtje) !== leeuwtjeActive);

  return (
    <div className="knockout-page">
      <section className="panel knockout-board-panel">
        <div className="panel-header">
          <div>
            <h3>Knockout</h3>
            <p>Select a match to inspect the path and complete open predictions.</p>
          </div>
          <span className="pill orange">
            {knockout.missing_actions?.length ?? 0} open
          </span>
        </div>
        <div className="panel-body">
          <div className="knockout-board" aria-label="Knockout Stage bracket">
            {KNOCKOUT_ROUND_ORDER.map((roundName) => {
              const round = knockout.rounds?.find((item) => item.round === roundName);
              if (!round?.matches?.length) return null;
              return (
                <section className="knockout-round" key={roundName}>
                  <h4>{roundName}</h4>
                  <div className="knockout-round-stack">
                    {round.matches.map((match) => (
                      <KnockoutMatchTile
                        key={match.id}
                        match={match}
                        selected={selectedMatch?.id === match.id}
                        onSelect={() => setSelectedMatchId(match.id)}
                      />
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        </div>
      </section>

      <aside className="panel knockout-detail-panel">
        <div className="panel-header">
          <div>
            <h3>
              {selectedMatch
                ? `Match ${selectedMatch.match_number}`
                : "Select match"}
            </h3>
            <p>
              {selectedMatch
                ? `${selectedMatch.round} · ${selectedMatch.date ?? "Date unknown"}`
                : "Choose a tile in the bracket."}
            </p>
          </div>
          {selectedMatch && (
            <span className={`pill ${openForPredictions ? "green" : ""}`}>
              {knockoutStatusLabel(selectedMatch.status)}
            </span>
          )}
        </div>
        {selectedMatch && detailMatch && (
          <div className="panel-body knockout-detail-body">
            <div className="knockout-detail-teams">
              <KnockoutSide side={selectedMatch.home} />
              <span>vs</span>
              <KnockoutSide side={selectedMatch.away} />
            </div>
            <div className="knockout-detail-meta">
              <span>{selectedMatch.venue?.name ?? "Venue to confirm"}</span>
              <span>Lock: {formatDateTimeIso(selectedMatch.lock_at)}</span>
            </div>

            {selectedMatch.status === "not_yet_actionable" ? (
              <div className="empty compact">
                This match opens once both Bracket Slots are resolved.
              </div>
            ) : (
              <>
                <MatchPredictionEditor
                  match={detailMatch}
                  teams={teams}
                  scores={scores}
                  locked={locked}
                  onScore={setScore}
                  onSubmit={saveSelected}
                  saving={saving}
                  compact
                  showSubmit={false}
                />
                {selectedMatch.quiz ? (
                  <MatchQuizEditor
                    match={detailMatch}
                    teams={teams}
                    prediction={quizDraft}
                    locked={locked}
                    onAnswer={setQuizAnswer}
                  />
                ) : (
                  <div className="fixture-quiz">
                    <div className="fixture-quiz-heading">
                      <div>
                        <strong>Quiz question not set yet</strong>
                      </div>
                    </div>
                  </div>
                )}
                <div className="knockout-detail-actions">
                  <LeeuwtjeButton
                    active={leeuwtjeActive}
                    disabled={locked || !canToggleLeeuwtje}
                    remaining={Math.max(
                      0,
                      leeuwtjesTotal(pool) - poolLeeuwtjeMatchIds(pool).length,
                    )}
                    onToggle={() => setLeeuwtjeActive((current) => !current)}
                  />
                  <button
                    className="primary-button"
                    type="button"
                    onClick={saveSelected}
                    disabled={saving || !canSaveSelected}
                  >
                    {saving ? "Saving..." : "Save prediction"}
                  </button>
                </div>
                <div className="knockout-missing-list">
                  {(selectedMatch.missing_actions ?? []).map((item) => (
                    <span key={`${item.kind}-${item.match_id}`} className="pill orange">
                      {item.kind === "quiz" ? "Quiz open" : "Score open"}
                    </span>
                  ))}
                </div>
              </>
            )}
            {error && <span className="form-error">{error}</span>}
          </div>
        )}
      </aside>
    </div>
  );
}

function splitExactScorePoints(total) {
  const components = [
    ["Correct outcome", 6],
    ["Correct home goals", 2],
    ["Correct away goals", 2],
    ["Exact score bonus", 2],
  ];
  const baseTotal = components.reduce((sum, [, value]) => sum + value, 0);
  const raw = components.map(([label, value]) => ({
    label,
    value: (Number(total) * value) / baseTotal,
  }));
  const rows = raw.map((row) => ({
    label: row.label,
    value: Math.floor(row.value),
    remainder: row.value - Math.floor(row.value),
  }));
  let remaining = Number(total) - rows.reduce((sum, row) => sum + row.value, 0);
  [...rows]
    .sort((left, right) => right.remainder - left.remainder)
    .slice(0, remaining)
    .forEach((row) => {
      row.value += 1;
      remaining -= 1;
    });
  return rows.map((row) => [row.label, row.value]).filter(([, value]) => value > 0);
}

function pointRows(points) {
  const breakdown = points?.score_breakdown ?? {};
  const rows = [
    ["Correct outcome", breakdown.outcome_points ?? 0],
    ["Correct home goals", breakdown.home_goals_points ?? 0],
    ["Correct away goals", breakdown.away_goals_points ?? 0],
    ["Exact score bonus", breakdown.exact_bonus_points ?? 0],
    ["Leeuwtje", points?.leeuwtje_points ?? 0],
    ["Quiz", points?.quiz_points ?? 0],
  ].filter(([, value]) => Number(value) > 0);
  for (const scorer of points?.striker_scorers ?? []) {
    const goals = Number(scorer.goals ?? 0);
    const suffix = goals > 1 ? ` x${goals}` : "";
    rows.push([`Striker: ${scorer.name}${suffix}`, scorer.points ?? 0]);
  }
  if (
    !points?.striker_scorers?.length &&
    Number(points?.striker_points ?? 0) > 0
  ) {
    rows.push(["Strikers", points.striker_points]);
  }
  if (!rows.length && Number(points?.score_points) > 0) {
    if (points.score_kind === "exact") {
      rows.push(...splitExactScorePoints(points.score_points));
    } else {
      const label =
        points.score_kind === "outcome" ? "Correct outcome" : "Score prediction";
      rows.push([label, Number(points.score_points)]);
    }
  }
  return rows;
}

function MatchPointBreakdown({ points, compact = false }) {
  if (!points) return null;
  const rows = pointRows(points);
  return (
    <div className={compact ? "point-breakdown is-popover" : "point-breakdown"}>
      <div className="point-breakdown-total">
        <strong>Total</strong>
        <b>{points.total_points ?? 0} pts</b>
      </div>
      {rows.length ? (
        rows.map(([label, value]) => (
          <div className="point-breakdown-row" key={label}>
            <span>{label}</span>
            <strong>{value} pts</strong>
          </div>
        ))
      ) : Number(points.total_points) > 0 ? (
        <div className="point-breakdown-row">
          <span>Awarded points</span>
          <strong>{points.total_points} pts</strong>
        </div>
      ) : (
        <span className="point-breakdown-empty">No points for this match.</span>
      )}
      {points.quiz?.answered && !compact && (
        <div className="point-breakdown-note">
          Quiz: {points.quiz.answer || "-"} · {points.quiz.points ?? 0} pts
        </div>
      )}
    </div>
  );
}

function PointsPopoverAnchor({ label, points, open, onToggle, onClose }) {
  const anchorRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    function closeOnOutsideClick(event) {
      if (anchorRef.current?.contains(event.target)) return;
      onClose();
    }
    document.addEventListener("pointerdown", closeOnOutsideClick, true);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick, true);
    };
  }, [open, onClose]);

  if (!points) return null;
  return (
    <span className="points-popover-anchor" ref={anchorRef}>
      <button
        className="points-chip"
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          onToggle();
        }}
        aria-expanded={open}
      >
        {label}
      </button>
      {open && <MatchPointBreakdown points={points} compact />}
    </span>
  );
}

function MatchCard({
  match,
  teams,
  venues,
  prediction,
  points,
  pointsOpen,
  onTogglePoints,
  onClosePoints,
  locked,
  onPrediction,
  onMatch,
}) {
  const venue = venues.get(match.venue_id);
  const venueLabel =
    match.venue_id === "to_confirm"
      ? "Venue to confirm"
      : `${venue?.name ?? match.venue_id}, ${venue?.city ?? ""}`;
  const group = match.group ? `Group ${match.group}` : match.round;
  const broadcaster = broadcastInfo(match);
  const live = isMatchLive(match);
  const completed = match.home_score != null && match.away_score != null;
  const kickoff = escapeDate(match);
  const alreadyStarted = kickoff <= new Date();
  const scheduleState = completed
    ? "completed"
    : live
      ? "live"
      : alreadyStarted
        ? "awaiting"
        : "upcoming";
  const statusLabel =
    scheduleState === "completed"
      ? "Played"
      : scheduleState === "live"
        ? "Live"
        : scheduleState === "awaiting"
          ? "Awaiting result"
          : "Upcoming";
  return (
    <article className={`match-card is-${scheduleState}`}>
      <div className="match-time">{formatTime(match)}</div>
      <div>
        <div className="match-teams">
          <TeamLabel id={match.home_team_id} teams={teams} />{" "}
          <span className="muted">vs</span>{" "}
          <TeamLabel id={match.away_team_id} teams={teams} />
          <button
            className={
              scoreComplete(prediction)
                ? "schedule-prediction-chip has-score"
                : "schedule-prediction-chip"
            }
            type="button"
            disabled={locked}
            onClick={onPrediction}
            aria-label={`Open prediction for ${teams.get(match.home_team_id)?.name ?? "home"
              } versus ${teams.get(match.away_team_id)?.name ?? "away"}`}
          >
            {predictionScoreLabel(prediction)}
          </button>
        </div>
        <div className="match-meta">
          {formatDate(match, true)} · {venueLabel}
        </div>
        {match.quiz && (
          <div className="match-quiz-line">Quiz: {match.quiz.question}</div>
        )}
        {completed && (
          <div className="match-result-line">
            <span>
              Final score: {match.home_score} - {match.away_score}
            </span>
            {points && (
              <PointsPopoverAnchor
                label={`Your points: ${points.total_points ?? 0}${points.leeuwtje_points ? " incl. Leeuwtje" : ""
                  }`}
                points={points}
                open={pointsOpen}
                onToggle={onTogglePoints}
                onClose={onClosePoints}
              />
            )}
          </div>
        )}
      </div>
      <div className="match-actions">
        {live ? (
          <span className="live-indicator">
            <span aria-hidden="true" />
            Live
          </span>
        ) : (
          <span className={`match-status-pill is-${scheduleState}`}>
            {statusLabel}
          </span>
        )}
        <span className="pill">{group}</span>
        <span className="broadcast-pill">{broadcaster.name}</span>
        {locked && (
          <button className="match-link" type="button" onClick={onMatch}>
            Analyse
          </button>
        )}
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

function Schedule({ matches, teams, venues, pool, onPoolUpdate, onMatch }) {
  const [activeMatch, setActiveMatch] = useState(null);
  const [openPointsId, setOpenPointsId] = useState(null);
  const popoverScope = useMemo(() => `schedule-${Math.random().toString(36).slice(2)}`, []);
  useEffect(() => {
    function closeOtherPopover(event) {
      if (event.detail?.scope !== popoverScope) setOpenPointsId(null);
    }
    window.addEventListener(POINTS_POPOVER_EVENT, closeOtherPopover);
    return () => {
      window.removeEventListener(POINTS_POPOVER_EVENT, closeOtherPopover);
    };
  }, [popoverScope]);
  if (!matches.length)
    return <div className="empty">No matches available.</div>;
  const predictions = poolPredictions(pool);
  const matchPoints = poolMatchPoints(pool);
  const now = new Date();
  const currentSessionKey = tournamentSessionDateKeyFromDate(now);
  const grouped = matches
    .slice()
    .sort((left, right) => escapeDate(left) - escapeDate(right))
    .reduce((days, match) => {
      const key = tournamentSessionDateKey(match);
      if (!days.has(key)) days.set(key, []);
      days.get(key).push(match);
      return days;
    }, new Map());
  const sessionGroups = [...grouped.entries()].map(([key, dayMatches]) => ({
    key,
    matches: dayMatches,
  }));
  const todayGroups = sessionGroups.filter((group) => group.key === currentSessionKey);
  const historicGroups = sessionGroups
    .filter((group) => group.key < currentSessionKey)
    .sort((left, right) => right.key.localeCompare(left.key));
  const futureGroups = sessionGroups
    .filter((group) => group.key > currentSessionKey)
    .sort((left, right) => left.key.localeCompare(right.key));
  const orderedGroups = [...todayGroups, ...historicGroups, ...futureGroups];
  const renderGroup = (group) => {
    const dayMatches = group.matches;
    const label = group.key === currentSessionKey ? "Vandaag" : formatDate(dayMatches[0]);
    return (
      <React.Fragment key={group.key}>
        <h3 className="date-heading">{label}</h3>
        <div className="match-list">
          {dayMatches.map(renderMatch)}
        </div>
      </React.Fragment>
    );
  };
  const renderMatch = (match) => {
    const lock = matchLock(pool, match.id);
    const locked = Boolean(lock.locked);
    return (
      <MatchCard
        key={match.id}
        match={match}
        teams={teams}
        venues={venues}
        prediction={predictions[match.id]}
        points={matchPoints[match.id]}
        pointsOpen={openPointsId === match.id}
        onTogglePoints={() => {
          setOpenPointsId((current) => {
            const next = current === match.id ? null : match.id;
            if (next) {
              window.dispatchEvent(
                new CustomEvent(POINTS_POPOVER_EVENT, {
                  detail: { scope: popoverScope },
                }),
              );
            }
            return next;
          });
        }}
        onClosePoints={() => setOpenPointsId(null)}
        locked={locked}
        onPrediction={() => setActiveMatch({ ...match, locked })}
        onMatch={() => onMatch?.(match.id)}
      />
    );
  };

  return (
    <>
      {orderedGroups.map(renderGroup)}
      <MatchdayPredictionModal
        match={activeMatch}
        teams={teams}
        pool={pool}
        onClose={() => setActiveMatch(null)}
        onPoolUpdate={onPoolUpdate}
      />
    </>
  );
}

function patchPoolAfterMatchPrediction(pool, matchId, result) {
  const patchMatchdayMatch = (match) =>
    (match.id ?? match.match_id) === matchId
      ? {
          ...match,
          has_my_prediction: true,
          my_prediction: result.prediction
            ? {
                home_score: result.prediction.home_score,
                away_score: result.prediction.away_score,
              }
            : match.my_prediction,
        }
      : match;
  const nextNotifications = (pool.notifications ?? [])
    .map((notification) => {
      if (!notification.items?.length) return notification;
      const items = notification.items.filter((item) => item.match_id !== matchId);
      return {
        ...notification,
        items,
        count: items.length,
        match_ids: (notification.match_ids ?? []).filter((id) => id !== matchId),
      };
    })
    .filter((notification) => !notification.items || notification.items.length);
  return {
    ...pool,
    predictions: {
      ...(pool.predictions ?? {}),
      [matchId]: result.prediction,
    },
    quiz_predictions: result.quiz_prediction
      ? {
        ...(pool.quiz_predictions ?? {}),
        [matchId]: result.quiz_prediction,
      }
      : pool.quiz_predictions,
    leeuwtjes_match_ids: result.leeuwtjes_match_ids ?? pool.leeuwtjes_match_ids,
    notifications: nextNotifications,
    progress: {
      ...(pool.progress ?? {}),
      ...(result.progress ?? {}),
    },
    matchday: pool.matchday
      ? {
          ...pool.matchday,
          matches: (pool.matchday.matches ?? []).map(patchMatchdayMatch),
          sessions: (pool.matchday.sessions ?? []).map((session) => ({
            ...session,
            matches: (session.matches ?? []).map(patchMatchdayMatch),
          })),
        }
      : pool.matchday,
  };
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
            <section
              className="team-group-block"
              key={group.id}
              aria-label={`Group ${group.id}`}
            >
              <div className="team-group-heading">
                <h4>Group {group.id}</h4>
                <span className="pill">{group.teams.length} teams</span>
              </div>
              <div className="team-directory-grid">
                {group.teams.map((team) => (
                  <button
                    className="team-directory-card"
                    key={team.id}
                    type="button"
                    onClick={() => onTeam(team.id)}
                  >
                    <TeamFlag id={team.id} className="team-card-flag" />
                    <span className="team-card-copy">
                      <strong>{team.name}</strong>
                      <span>
                        {team.code} · {team.confederation}
                      </span>
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
        <span className={people.length ? "pill green" : "pill"}>
          {people.length ? (countLabel ?? people.length) : "TBC"}
        </span>
      </div>
      <div className="panel-body">
        {!people.length && <div className="empty compact">{empty}</div>}
        {!!people.length && (
          <ul className="team-person-list">
            {people.map((person, index) => {
              const role = personRole(person, fallbackRole);
              const meta = personMeta(person);
              const number =
                typeof person === "string"
                  ? ""
                  : (person?.number ?? person?.shirt_number ?? "");
              return (
                <li
                  className="team-person-row"
                  key={`${personName(person)}-${index}`}
                >
                  <span className="team-person-number">
                    {number || index + 1}
                  </span>
                  <span>
                    <strong>{personName(person)}</strong>
                    {(role || meta) && (
                      <em>{[role, meta].filter(Boolean).join(" · ")}</em>
                    )}
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
    .filter(
      (match) =>
        match.home_team_id === team.id || match.away_team_id === team.id,
    )
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
        {!teamMatches.length && (
          <div className="empty compact">
            No matches available for this team.
          </div>
        )}
        {teamMatches.map((match) => {
          const opponentId =
            match.home_team_id === team.id
              ? match.away_team_id
              : match.home_team_id;
          const venue = venues.get(match.venue_id);
          return (
            <article className="team-fixture-row" key={match.id}>
              <span className="match-time">{formatTime(match)}</span>
              <span>
                <strong>
                  <TeamLabel id={opponentId} teams={teams} />
                </strong>
                <em>
                  {formatDate(match, true)} ·{" "}
                  {venue?.city ?? "Venue to confirm"}
                </em>
              </span>
              <span className="pill">
                {match.group ? `Group ${match.group}` : match.round}
              </span>
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
              <p>
                This country is not available in the current World Cup data.
              </p>
            </div>
            <button className="text-button" type="button" onClick={onBack}>
              Teams
            </button>
          </div>
        </article>
      </div>
    );
  }

  const group = data.groups.find((candidate) =>
    candidate.teams.includes(team.id),
  );
  const coach = teamCoach(team);
  const staff = teamStaff(team);
  const players = teamPlayers(team);
  const sources = teamSources(team);

  return (
    <div className="team-page">
      <button
        className="text-button team-back-button"
        type="button"
        onClick={onBack}
      >
        Back to Teams
      </button>

      <section className="team-hero" aria-label={`${team.name} team profile`}>
        <TeamFlag id={team.id} className="team-hero-flag" />
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
        subtitle="Definitive squads are due to FIFA on 1 June 2026 and become official on 2 June."
        people={players}
        empty="Squad data is not loaded yet. Some countries may announce earlier, but this local dataset will be completed after FIFA confirmation."
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
              const label =
                typeof source === "string"
                  ? source
                  : (source.label ?? source.title ?? source.url ?? "Source");
              if (!href) return <span key={`${label}-${index}`}>{label}</span>;
              return (
                <a
                  key={`${href}-${index}`}
                  href={href}
                  target="_blank"
                  rel="noreferrer"
                >
                  {label}
                </a>
              );
            })}
          </div>
        </article>
      )}

      <TeamFixtureSection
        team={team}
        matches={data.matches}
        teams={teams}
        venues={venues}
      />
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
      if (
        typeof match.home_score !== "number" ||
        typeof match.away_score !== "number"
      )
        return;
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
              <tr
                key={row.teamId}
                className={
                  row.teamId === NETHERLANDS_ID ? "highlight" : undefined
                }
              >
                <td>
                  <TeamLabel id={row.teamId} teams={teams} />
                </td>
                <td className="numeric">{row.played}</td>
                <td className="numeric">{row.won}</td>
                <td className="numeric">{row.drawn}</td>
                <td className="numeric">{row.lost}</td>
                <td className="numeric">{gd}</td>
                <td className="numeric">
                  <strong>{row.points}</strong>
                </td>
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
  const completedPredictions = groupMatches.filter((match) =>
    scoreComplete(predictions[match.id]),
  );

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
                <tr
                  key={row.teamId}
                  className={
                    row.teamId === NETHERLANDS_ID ? "highlight" : undefined
                  }
                >
                  <td>
                    <TeamLabel id={row.teamId} teams={teams} />
                  </td>
                  <td className="numeric">{row.played}</td>
                  <td className="numeric">{row.won}</td>
                  <td className="numeric">{row.drawn}</td>
                  <td className="numeric">{row.lost}</td>
                  <td className="numeric">{row.goalsFor}</td>
                  <td className="numeric">{row.goalsAgainst}</td>
                  <td className="numeric">{goalDifference}</td>
                  <td className="numeric">
                    <strong>{row.points}</strong>
                  </td>
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
  const teamNames = group.teams
    .map((id) => teams.get(id)?.name ?? id)
    .join(", ");
  const groupMatches = data.matches.filter((match) => match.group === group.id);
  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <h3>Group {group.id}</h3>
          <p>{teamNames}</p>
        </div>
        <span className={group.id === "F" ? "pill orange" : "pill"}>
          {groupMatches.length} matches
        </span>
      </div>
      <div className="panel-body">
        <StandingsTable group={group} matches={data.matches} teams={teams} />
      </div>
    </article>
  );
}

function LoginPanel({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showResetHelp, setShowResetHelp] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      if (email && !TALPA_EMAIL_PATTERN.test(email.trim())) {
        throw new Error(
          "Use firstname.lastname@talpanetwork.com or firstname.lastname@talpastudios.com.",
        );
      }

      const result = await apiJson("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
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
          <p>Log in with your email address and password.</p>
        </div>
        <span className="pill orange">Login</span>
      </div>
      <form className="panel-body login-form" onSubmit={submit}>
        <label>
          Email
          <input
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            inputMode="email"
            autoComplete="email"
            placeholder="firstname.lastname@talpanetwork.com"
          />
          <span className="field-help">
            Use firstname.lastname@talpanetwork.com or firstname.lastname@talpastudios.com.
          </span>
        </label>
        <label>
          Password
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            autoComplete="current-password"
            minLength="8"
            placeholder="at least 8 characters"
          />
        </label>
        {error && <div className="form-error">{error}</div>}
        {showResetHelp && (
          <div className="form-help-note">
            Password resets are handled by a pool admin — ask Sem, Karel or Olivier
            to reset yours. They will give you a temporary password, and you can set
            your own again on your next login.
          </div>
        )}
        <button className="primary-button" type="submit" disabled={saving}>
          {saving ? "Saving..." : "Log in"}
        </button>
        <button
          className="text-button"
          type="button"
          onClick={() => setShowResetHelp((current) => !current)}
        >
          Forgot password?
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
  const label = `${player?.name ?? "Player"} profile picture`;
  return (
    <span
      className={`profile-avatar ${size}`}
      style={{ "--avatar-hue": avatar.hue ?? 24 }}
      role="img"
      aria-label={label}
    >
      {avatar.image_url ? (
        <img src={avatar.image_url} alt="" aria-hidden="true" />
      ) : (
        (avatar.initials ?? "?")
      )}
    </span>
  );
}

function ProfileImageEditor({ player, canEdit, onUpdateImage }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function changeImage(event) {
    const [file] = event.target.files ?? [];
    event.target.value = "";
    if (!file) return;
    setSaving(true);
    setError("");
    try {
      const imageUrl = await resizeProfileImage(file);
      await onUpdateImage(imageUrl);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function removeImage() {
    setSaving(true);
    setError("");
    try {
      await onUpdateImage(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (!canEdit) return <ProfileAvatar player={player} size="large" />;

  return (
    <div className="profile-image-editor">
      <ProfileAvatar player={player} size="large" />
      <div className="profile-image-actions">
        <label className="text-button profile-image-upload">
          {saving ? "Uploaden..." : "Icoon uploaden"}
          <input
            type="file"
            accept="image/*"
            onChange={changeImage}
            disabled={saving}
          />
        </label>
        {player?.profile_picture?.image_url && (
          <button
            className="text-button"
            type="button"
            onClick={removeImage}
            disabled={saving}
          >
            Verwijderen
          </button>
        )}
      </div>
      {error && <span className="form-error">{error}</span>}
    </div>
  );
}

function ProfileNameEditor({ player, canEdit, onUpdateName }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(player?.name ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!editing) setDraft(player?.name ?? "");
  }, [player?.name, editing]);

  if (!canEdit) return <h3>{player.name}</h3>;

  async function submit(event) {
    event.preventDefault();
    const nextName = draft.trim().replace(/\s+/g, " ");
    if (nextName.length < 2) {
      setError("Gebruik minimaal 2 tekens.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await onUpdateName(nextName);
      setEditing(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return (
      <form className="profile-name-form" onSubmit={submit}>
        <label>
          Gebruikersnaam
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            maxLength="60"
            autoFocus
          />
        </label>
        <div className="profile-name-actions">
          <button className="primary-button" type="submit" disabled={saving}>
            {saving ? "Opslaan..." : "Opslaan"}
          </button>
          <button
            className="text-button"
            type="button"
            disabled={saving}
            onClick={() => {
              setDraft(player.name);
              setError("");
              setEditing(false);
            }}
          >
            Annuleren
          </button>
        </div>
        {error && <span className="form-error">{error}</span>}
      </form>
    );
  }

  return (
    <div className="profile-name-row">
      <h3>{player.name}</h3>
      <button
        className="text-button"
        type="button"
        onClick={() => setEditing(true)}
      >
        Naam aanpassen
      </button>
    </div>
  );
}

function ChangePasswordPanel({ onChangePassword, onSuccess, currentPasswordLabel }) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await onChangePassword({
        current_password: currentPassword,
        password,
        confirm_password: confirmPassword,
      });
      setCurrentPassword("");
      setPassword("");
      setConfirmPassword("");
      setSuccess("Password changed.");
      if (onSuccess) await onSuccess();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="change-password-form" onSubmit={submit}>
      <label>
        {currentPasswordLabel ?? "Current password"}
        <input
          value={currentPassword}
          onChange={(event) => setCurrentPassword(event.target.value)}
          type="password"
          autoComplete="current-password"
        />
      </label>
      <label>
        New password
        <input
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          type="password"
          autoComplete="new-password"
          minLength="8"
        />
      </label>
      <label>
        Confirm new password
        <input
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          type="password"
          autoComplete="new-password"
          minLength="8"
        />
      </label>
      {error && <div className="form-error">{error}</div>}
      {success && <div className="form-success">{success}</div>}
      <button className="primary-button" type="submit" disabled={saving}>
        {saving ? "Saving..." : "Change password"}
      </button>
    </form>
  );
}

function ChangePasswordModal({ onClose, onChangePassword }) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <article
        className="prediction-modal change-password-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Change password"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="prediction-modal-header">
          <div>
            <h3>Change password</h3>
            <p>Enter your current password, then choose a new one.</p>
          </div>
          <button className="text-button" type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="prediction-modal-body">
          <ChangePasswordPanel onChangePassword={onChangePassword} />
        </div>
      </article>
    </div>
  );
}

function ForcePasswordChangePage({ onChangePassword, onComplete, onLogout }) {
  return (
    <main className="login-page">
      <section className="login-copy" aria-label="Set a new password">
        <FieldMark />
        <p className="eyebrow">FIFA World Cup 2026</p>
        <h1>Set a new password</h1>
        <p>
          An admin gave your account a temporary password. Choose your own
          password now to finish logging in.
        </p>
      </section>
      <article className="panel pool-login">
        <div className="panel-header">
          <div>
            <h3>Choose a new password</h3>
            <p>Enter the temporary password, then pick a new one of your own.</p>
          </div>
          <span className="pill orange">Required</span>
        </div>
        <div className="panel-body">
          <ChangePasswordPanel
            onChangePassword={onChangePassword}
            onSuccess={onComplete}
            currentPasswordLabel="Temporary password"
          />
          <button className="text-button" type="button" onClick={onLogout}>
            Log out instead
          </button>
        </div>
      </article>
    </main>
  );
}

function prizePotAdminLabel(status) {
  if (status === "joined") return "Joined prize pot";
  if (status === "declined") return "Declined prize pot";
  return "Not answered";
}

function AdminUsersPage({ currentUser }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyUserId, setBusyUserId] = useState(null);
  const [resetResult, setResetResult] = useState(null);
  const prizePotCounts = useMemo(
    () =>
      users.reduce(
        (counts, user) => {
          const status = user.prize_pot_status ?? "undecided";
          counts[status] = (counts[status] ?? 0) + 1;
          return counts;
        },
        { joined: 0, declined: 0, undecided: 0 },
      ),
    [users],
  );
  const joinedPrizePotUsers = users.filter((user) => user.prize_pot_status === "joined");

  async function loadUsers() {
    setLoading(true);
    setError("");
    try {
      const result = await apiJson("/api/admin/users");
      setUsers(result.users ?? []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);

  async function updateUser(userId, action, options = {}) {
    setBusyUserId(userId);
    setError("");
    try {
      const endpoint =
        action === "archive" || action === "restore"
          ? `/api/admin/users/${userId}/${action}`
          : `/api/admin/users/${userId}`;
      const result = await apiJson(endpoint, {
        method: action === "admin" ? "PATCH" : "POST",
        body: action === "admin" ? JSON.stringify(options) : "{}",
      });
      setUsers(result.users ?? []);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyUserId(null);
    }
  }

  async function resetPassword(user) {
    setBusyUserId(user.id);
    setError("");
    setResetResult(null);
    try {
      const result = await apiJson(
        `/api/admin/users/${user.id}/reset-password`,
        { method: "POST", body: "{}" },
      );
      setUsers(result.users ?? []);
      setResetResult({
        userId: user.id,
        name: user.name,
        email: user.email,
        password: result.temporary_password,
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyUserId(null);
    }
  }

  return (
    <>
      {resetResult && (
        <TemporaryPasswordModal
          result={resetResult}
          onClose={() => setResetResult(null)}
        />
      )}
      <article className="panel admin-users-panel">
        <div className="panel-header">
          <div>
            <h3>Admin users</h3>
            <p>Archive accounts, restore accounts, manage admin access, and track the prize pot.</p>
          </div>
          <span className="pill orange">{users.length} accounts</span>
        </div>
        <div className="panel-body">
          {error && <div className="form-error">{error}</div>}
          {loading ? (
            <div className="empty">Loading accounts...</div>
          ) : (
            <>
              <section className="admin-prize-pot-summary" aria-label="Prize pot participation">
                <div>
                  <span>Prize pot</span>
                  <strong>{prizePotCounts.joined} joining</strong>
                </div>
                <div>
                  <span>Not joining</span>
                  <strong>{prizePotCounts.declined}</strong>
                </div>
                <div>
                  <span>Not answered</span>
                  <strong>{prizePotCounts.undecided}</strong>
                </div>
                <p>
                  {joinedPrizePotUsers.length
                    ? joinedPrizePotUsers.map((user) => user.name).join(", ")
                    : "Nobody has joined the prize pot yet."}
                </p>
              </section>
              <div className="admin-user-list">
                {users.map((user) => {
                  const archived = Boolean(user.archived_at);
                  const isSelf = user.id === currentUser?.id;
                  const busy = busyUserId === user.id;
                  const prizePotStatus = user.prize_pot_status ?? "undecided";
                  return (
                    <div
                      className={archived ? "admin-user-row is-archived" : "admin-user-row"}
                      key={user.id}
                    >
                      <div>
                        <strong>{user.name}</strong>
                        <span>{user.email}</span>
                        <div className="admin-user-meta">
                          <em>
                            {archived
                              ? `Archived ${user.archived_at}`
                              : user.is_admin
                                ? "Admin"
                                : "Participant"}
                          </em>
                          <b className={`admin-prize-pot-status ${prizePotStatus}`}>
                            {prizePotAdminLabel(prizePotStatus)}
                          </b>
                        </div>
                      </div>
                      <div className="admin-user-actions">
                        {!archived && (
                          <button
                            className="text-button"
                            type="button"
                            disabled={busy || (isSelf && user.is_admin)}
                            onClick={() =>
                              updateUser(user.id, "admin", {
                                is_admin: !user.is_admin,
                              })
                            }
                          >
                            {user.is_admin ? "Remove admin" : "Make admin"}
                          </button>
                        )}
                        {!archived && (
                          <button
                            className="text-button"
                            type="button"
                            disabled={busy}
                            onClick={() => resetPassword(user)}
                          >
                            Reset password
                          </button>
                        )}
                        {archived ? (
                          <button
                            className="text-button"
                            type="button"
                            disabled={busy}
                            onClick={() => updateUser(user.id, "restore")}
                          >
                            Restore
                          </button>
                        ) : (
                          <button
                            className="text-button"
                            type="button"
                            disabled={busy || isSelf}
                            onClick={() => updateUser(user.id, "archive")}
                          >
                            Archive
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </article>
    </>
  );
}

function TemporaryPasswordModal({ result, onClose }) {
  const [copied, setCopied] = useState(false);

  async function copyPassword() {
    try {
      await navigator.clipboard.writeText(result.password);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <article
        className="prediction-modal change-password-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Temporary password"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="prediction-modal-header">
          <div>
            <h3>Temporary password set</h3>
            <p>
              Share this with {result.name} ({result.email}). They will be asked
              to choose their own password the next time they log in.
            </p>
          </div>
          <button className="text-button" type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="prediction-modal-body">
          <div className="temp-password-display">
            <code>{result.password}</code>
            <button className="primary-button" type="button" onClick={copyPassword}>
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <p className="field-help">
            This password is shown only once. If you lose it, reset it again.
          </p>
        </div>
      </article>
    </div>
  );
}

function labelEventDraft(events = []) {
  return JSON.stringify(
    events.map((event) => ({
      elapsed: event.elapsed ?? "",
      local_team_id: event.local_team_id ?? "",
      team_name: event.team_name ?? "",
      player_name: event.player_name ?? "",
      event_type: event.event_type ?? "Goal",
      detail: event.detail ?? "",
      comments: event.comments ?? "",
    })),
    null,
    2,
  );
}

function labelStatDraft(stats = []) {
  return JSON.stringify(
    stats.map((stat) => ({
      local_team_id: stat.local_team_id ?? "",
      team_name: stat.team_name ?? "",
      player_name: stat.player_name ?? "",
      minutes: stat.minutes ?? 0,
      position: stat.position ?? "",
      rating: stat.rating ?? "",
      goals: stat.goals ?? 0,
      assists: stat.assists ?? 0,
      yellow_cards: stat.yellow_cards ?? 0,
      red_cards: stat.red_cards ?? 0,
      clean_sheet: Boolean(stat.clean_sheet),
    })),
    null,
    2,
  );
}

function labelSource(match, type) {
  if (type === "result") return match.result?.source ?? "missing";
  if (type === "quiz") return match.quiz?.source ?? "missing";
  if (type === "events") {
    if (match.events?.some((event) => event.source === "manual")) return "manual";
    return match.events?.length ? "api-football" : "missing";
  }
  if (type === "stats") {
    if (match.player_stats?.some((stat) => stat.source === "manual")) return "manual";
    return match.player_stats?.length ? "api-football" : "missing";
  }
  return "missing";
}

function LabelSourcePill({ source }) {
  const className = source === "manual" ? "pill orange" : source?.startsWith("genai") ? "pill blue" : "pill";
  return <span className={className}>{source}</span>;
}

function quizAnswerValues(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item ?? "").trim()).filter(Boolean);
  }
  return String(value ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function genaiEvidenceSummary(genai) {
  const evidence = genai?.evidence ?? [];
  if (!evidence.length) return "No evidence";
  return evidence
    .slice(0, 3)
    .map((item) => `${item.type}:${item.id}`)
    .join(", ");
}

function genaiPlayerLinkSummary(link) {
  if (!link) return "";
  return `${link.raw_player_name} -> ${link.matched_player_name}`;
}

function adminQuizFromDraft(match, draft) {
  if (!match?.quiz && !String(draft?.question ?? "").trim()) return null;
  const choices = String(draft.choices ?? "")
    .split("\n")
    .map((choice) => choice.trim())
    .filter(Boolean);
  const baseQuiz = match?.quiz ?? {
    question: "",
    type:
      choices.length === 2 &&
        choices.map((choice) => choice.toLowerCase()).sort().join("|") === "ja|nee"
        ? "yes_no"
        : choices.length
          ? "choice"
          : "open",
    choices: [],
  };
  return {
    ...baseQuiz,
    question: draft.question || baseQuiz.question,
    choices,
  };
}

function adminQuizDraftChoices(draft) {
  return String(draft.choices ?? "")
    .split("\n")
    .map((choice) => choice.trim())
    .filter(Boolean);
}

function adminQuizChoiceOptions(match, teams, draft) {
  const quiz = adminQuizFromDraft(match, draft);
  if (!quiz) return [];
  return quizChoices({ ...match, quiz }, teams);
}

function adminQuizChoicePoints(quiz, choice) {
  const points = quizChoicePoint(quiz, choice);
  if (points !== undefined && points !== null && points !== "") return points;
  if (quiz?.dynamic_choice_points !== undefined) return quiz.dynamic_choice_points;
  if (quiz?.type === "yes_no") return 3;
  return 5;
}

function AdminTeamOrSlot({ id, placeholder, teams }) {
  if (id) return <TeamLabel id={id} teams={teams} />;
  return <span className="admin-bracket-slot">{placeholder || "Bracket slot"}</span>;
}

function AdminLabelsPage({ teams }) {
  const [labels, setLabels] = useState({ matches: [], audit: [], tables: {} });
  const [selectedMatchId, setSelectedMatchId] = useState("");
  const [editingMatchId, setEditingMatchId] = useState("");
  const [drafts, setDrafts] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function loadLabels(nextMatchId = selectedMatchId) {
    setLoading(true);
    setError("");
    try {
      const result = await apiJson("/api/admin/labels");
      setLabels(result);
      const firstMatchId = result.matches?.[0]?.match_id ?? "";
      const activeMatchId = nextMatchId || firstMatchId;
      setSelectedMatchId(activeMatchId);
      const nextDrafts = {};
      for (const match of result.matches ?? []) {
        nextDrafts[match.match_id] = {
          home_score: match.result?.home_score ?? "",
          away_score: match.result?.away_score ?? "",
          status_short: match.result?.status_short ?? "FT",
          status_long: match.result?.status_long ?? "Manual result",
          elapsed: match.result?.elapsed ?? 90,
          advancing_team_id: match.result?.advancing_team_id ?? "",
          decision_method: match.result?.decision_method ?? "",
          question: match.quiz?.question ?? "",
          choices: (match.quiz?.choices ?? []).join("\n"),
          correct_answers: match.quiz?.correct_answers ?? [],
          viewership_answer: match.quiz?.viewership_answer ?? "",
          events_json: labelEventDraft(match.events),
          player_stats_json: labelStatDraft(match.player_stats),
        };
      }
      setDrafts(nextDrafts);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadLabels("");
  }, []);

  const match = labels.matches?.find((item) => item.match_id === selectedMatchId);
  const draft = drafts[selectedMatchId] ?? {};

  function updateDraft(key, value) {
    setDrafts((current) => ({
      ...current,
      [selectedMatchId]: {
        ...(current[selectedMatchId] ?? {}),
        [key]: value,
      },
    }));
  }

  async function saveResult() {
    setSaving("result");
    setError("");
    setSuccess("");
    try {
      const result = await apiJson(`/api/admin/labels/${selectedMatchId}/result`, {
        method: "PATCH",
        body: JSON.stringify({
          home_score: draft.home_score,
          away_score: draft.away_score,
          status_short: draft.status_short,
          status_long: draft.status_long,
          elapsed: draft.elapsed,
          advancing_team_id: draft.advancing_team_id,
          decision_method: draft.decision_method,
        }),
      });
      setLabels(result);
      setSuccess("Result label saved.");
      await loadLabels(selectedMatchId);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving("");
    }
  }

  async function clearResultOverride() {
    setSaving("result");
    setError("");
    setSuccess("");
    try {
      const result = await apiJson(`/api/admin/labels/${selectedMatchId}/result`, {
        method: "PATCH",
        body: JSON.stringify({ clear_override: true }),
      });
      setLabels(result);
      setSuccess("Result override reverted.");
      await loadLabels(selectedMatchId);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving("");
    }
  }

  async function saveQuiz(clear = false) {
    setSaving("quiz");
    setError("");
    setSuccess("");
    try {
      const answers = quizAnswerValues(draft.correct_answers);
      const choices = adminQuizDraftChoices(draft);
      const result = await apiJson(`/api/admin/labels/${selectedMatchId}/quiz`, {
        method: "PATCH",
        body: JSON.stringify(
          clear
            ? { clear_override: true }
            : {
              question: draft.question,
              choices,
              correct_answers: answers,
              viewership_answer: draft.viewership_answer,
            },
        ),
      });
      setLabels(result);
      setSuccess(clear ? "Quiz override cleared." : "Quiz label saved.");
      await loadLabels(selectedMatchId);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving("");
    }
  }

  async function saveJsonLabel(type, clear = false) {
    setSaving(type);
    setError("");
    setSuccess("");
    try {
      const key = type === "events" ? "events_json" : "player_stats_json";
      const parsed = clear ? [] : JSON.parse(draft[key] || "[]");
      const endpoint =
        type === "events"
          ? `/api/admin/labels/${selectedMatchId}/events`
          : `/api/admin/labels/${selectedMatchId}/player-stats`;
      const result = await apiJson(endpoint, {
        method: "PUT",
        body: JSON.stringify(
          clear
            ? { clear_override: true }
            : type === "events"
              ? { events: parsed }
              : { player_stats: parsed },
        ),
      });
      setLabels(result);
      setSuccess(
        clear
          ? type === "events"
            ? "Goal labels reverted."
            : "Player stats reverted."
          : type === "events"
            ? "Goal labels saved."
            : "Player stat labels saved.",
      );
      await loadLabels(selectedMatchId);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving("");
    }
  }

  return (
    <article className="panel admin-labels-panel">
      <div className="panel-header">
        <div>
          <h3>Scoring labels</h3>
          <p>Inspect and adjust labels/results used for scoring.</p>
        </div>
        <div className="admin-label-header-status">
          <span className="pill green">
            {Object.values(labels.tables ?? {}).filter(Boolean).length} label tables
          </span>
          {labels.genai && (
            <span className={labels.genai.enabled ? "pill blue" : "pill warning"}>
              GenAI {labels.genai.enabled ? "enabled" : "disabled"}
            </span>
          )}
        </div>
      </div>
      <div className="panel-body">
        {error && <div className="form-error">{error}</div>}
        {success && <div className="form-success">{success}</div>}
        {loading ? (
          <div className="empty">Loading scoring labels...</div>
        ) : (
          <>
            <div className="prediction-fixture-list admin-label-match-list">
              {labels.matches.map((labelMatch, index) => {
                const editing = editingMatchId === labelMatch.match_id;
                const goalEvents = (labelMatch.events ?? []).filter(
                  (event) =>
                    String(event.event_type ?? "").toLowerCase() === "goal",
                );
                const goalSummary = goalEvents.length
                  ? goalEvents
                    .map((event) => event.player_name)
                    .filter(Boolean)
                    .join(", ")
                  : "No goal labels";
                const statSummary = labelMatch.player_stats?.length
                  ? `${labelMatch.player_stats.length} player stat labels`
                  : "No player stat labels";
                const playerGenaiLinks = [
                  ...(labelMatch.events ?? []),
                  ...(labelMatch.player_stats ?? []),
                ]
                  .map((item) => item.genai_link)
                  .filter(Boolean);
                const needsQuizReview = Boolean(labelMatch.quiz_review_needed);
                const quizReviewReasons = labelMatch.quiz_review_reasons ?? [];
                const labelDraft = drafts[labelMatch.match_id] ?? {};
                const activeQuiz = adminQuizFromDraft(labelMatch, labelDraft);
                const quizOptions = adminQuizChoiceOptions(
                  labelMatch,
                  teams,
                  labelDraft,
                );
                const selectedQuizAnswers = new Set(
                  quizAnswerValues(labelDraft.correct_answers),
                );
                return (
                  <article
                    className={[
                      "prediction-fixture-row",
                      "admin-label-match",
                      editing ? "is-active" : "",
                      needsQuizReview ? "needs-quiz-review" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    key={labelMatch.match_id}
                  >
                    <div className="fixture-row-header">
                      <div className="fixture-open-button as-static">
                        <span className="fixture-number">{index + 1}</span>
                        <span>
                          <strong>
                            <AdminTeamOrSlot
                              id={labelMatch.home_team_id}
                              placeholder={labelMatch.home_placeholder}
                              teams={teams}
                            />{" "}
                            <AdminTeamOrSlot
                              id={labelMatch.away_team_id}
                              placeholder={labelMatch.away_placeholder}
                              teams={teams}
                            />
                          </strong>
                          <em>
                            {labelMatch.date ?? "Date unknown"} ·{" "}
                            {labelMatch.round ?? "Match"}
                            {labelMatch.group ? ` · Group ${labelMatch.group}` : ""}
                          </em>
                        </span>
                      </div>
                      <div className="fixture-row-status admin-label-status">
                        {needsQuizReview && (
                          <span className="pill warning">Quiz needs review</span>
                        )}
                        <LabelSourcePill source={labelSource(labelMatch, "result")} />
                        <LabelSourcePill source={labelSource(labelMatch, "quiz")} />
                        <LabelSourcePill source={labelSource(labelMatch, "events")} />
                        <button
                          className={editing ? "text-button is-active" : "text-button"}
                          type="button"
                          onClick={() => {
                            if (editing) {
                              setEditingMatchId("");
                              return;
                            }
                            setSelectedMatchId(labelMatch.match_id);
                            setEditingMatchId(labelMatch.match_id);
                          }}
                        >
                          {editing ? "Close" : "Edit"}
                        </button>
                      </div>
                    </div>

                    <div className="fixture-score-grid has-no-submit admin-label-score">
                      <label className="fixture-team-input is-home">
                        <TeamBadge id={labelMatch.home_team_id} teams={teams} />
                        <input
                          value={labelMatch.result?.home_score ?? ""}
                          readOnly
                          aria-label="Home result label"
                        />
                      </label>
                      <span className="fixture-score-separator">-</span>
                      <label className="fixture-team-input is-away">
                        <TeamBadge
                          id={labelMatch.away_team_id}
                          teams={teams}
                          align="right"
                        />
                        <input
                          value={labelMatch.result?.away_score ?? ""}
                          readOnly
                          aria-label="Away result label"
                        />
                      </label>
                    </div>

                    <section
                      className="fixture-quiz admin-label-readout"
                      aria-label="Scoring labels"
                    >
                      <div className="fixture-quiz-heading">
                        <div>
                          <strong>
                            {labelMatch.quiz?.question ?? "No quiz question"}
                          </strong>
                          {needsQuizReview && (
                            <span className="admin-review-warning">
                              Review needed: {quizReviewReasons.join(", ")}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="admin-label-readout-grid">
                        <span>
                          <strong>Quiz label</strong>
                          {labelMatch.quiz?.correct_answers?.length
                            ? labelMatch.quiz.correct_answers.join(", ")
                            : "Missing"}
                        </span>
                        <span>
                          <strong>Viewership</strong>
                          {formatNumber(labelMatch.quiz?.viewership_answer) ||
                            "Missing"}
                        </span>
                        <span
                          className={
                            labelMatch.quiz?.genai
                              ? "admin-genai-readout"
                              : "admin-genai-readout is-empty"
                          }
                        >
                          <strong>GenAI job</strong>
                          {labelMatch.quiz?.genai
                            ? `${labelMatch.quiz.genai.status} · ${labelMatch.quiz.genai.confidence}`
                            : "No GenAI label"}
                          {labelMatch.quiz?.manual_override_active &&
                            labelMatch.quiz?.genai && (
                              <em>Manual override active</em>
                            )}
                        </span>
                        <span>
                          <strong>Scorers</strong>
                          {goalSummary}
                        </span>
                        <span>
                          <strong>Stats</strong>
                          {statSummary}
                        </span>
                        {labelMatch.is_knockout && (
                          <span>
                            <strong>Advancing team</strong>
                            {labelMatch.result?.advancing_team_id ? (
                              <TeamLabel
                                id={labelMatch.result.advancing_team_id}
                                teams={teams}
                              />
                            ) : (
                              "Missing"
                            )}
                          </span>
                        )}
                        {labelMatch.is_knockout && (
                          <span>
                            <strong>Decision</strong>
                            {labelMatch.result?.decision_method || "Missing"}
                          </span>
                        )}
                        <span
                          className={
                            playerGenaiLinks.length
                              ? "admin-genai-readout"
                              : "admin-genai-readout is-empty"
                          }
                        >
                          <strong>Player GenAI</strong>
                          {playerGenaiLinks.length
                            ? `${playerGenaiLinks.length} accepted link${playerGenaiLinks.length === 1 ? "" : "s"
                            }`
                            : "No player links"}
                        </span>
                      </div>
                    </section>

                    {editing && match && (
                      <div className="admin-label-grid">
                        <section className="admin-label-section">
                          <h4>Result label</h4>
                          <div className="admin-label-fields">
                            <label>
                              Home
                              <input
                                type="number"
                                min="0"
                                max="30"
                                value={draft.home_score ?? ""}
                                onChange={(event) =>
                                  updateDraft("home_score", event.target.value)
                                }
                              />
                            </label>
                            <label>
                              Away
                              <input
                                type="number"
                                min="0"
                                max="30"
                                value={draft.away_score ?? ""}
                                onChange={(event) =>
                                  updateDraft("away_score", event.target.value)
                                }
                              />
                            </label>
                            <label>
                              Status
                              <input
                                value={draft.status_short ?? ""}
                                onChange={(event) =>
                                  updateDraft("status_short", event.target.value)
                                }
                              />
                            </label>
                            <label>
                              Elapsed
                              <input
                                type="number"
                                value={draft.elapsed ?? ""}
                                onChange={(event) =>
                                  updateDraft("elapsed", event.target.value)
                                }
                              />
                            </label>
                            {match.is_knockout && (
                              <label>
                                Decision
                                <select
                                  value={draft.decision_method ?? ""}
                                  onChange={(event) =>
                                    updateDraft("decision_method", event.target.value)
                                  }
                                >
                                  <option value="">From status</option>
                                  <option value="regular_time">Regular time</option>
                                  <option value="extra_time">Extra time</option>
                                  <option value="penalties">Penalties</option>
                                </select>
                              </label>
                            )}
                            {match.is_knockout && (
                              <label>
                                Advancing team
                                <select
                                  value={draft.advancing_team_id ?? ""}
                                  onChange={(event) =>
                                    updateDraft("advancing_team_id", event.target.value)
                                  }
                                >
                                  <option value="">Not set</option>
                                  {match.home_team_id && (
                                    <option value={match.home_team_id}>
                                      {teams[match.home_team_id]?.name ??
                                        match.home_team_name ??
                                        match.home_team_id}
                                    </option>
                                  )}
                                  {match.away_team_id && (
                                    <option value={match.away_team_id}>
                                      {teams[match.away_team_id]?.name ??
                                        match.away_team_name ??
                                        match.away_team_id}
                                    </option>
                                  )}
                                </select>
                              </label>
                            )}
                          </div>
                          <div className="admin-label-actions">
                            <button
                              className="primary-button"
                              type="button"
                              disabled={saving === "result"}
                              onClick={saveResult}
                            >
                              {saving === "result" ? "Saving..." : "Save result"}
                            </button>
                            <button
                              className="text-button"
                              type="button"
                              disabled={saving === "result"}
                              onClick={clearResultOverride}
                            >
                              Revert override
                            </button>
                          </div>
                        </section>

                        <section className="admin-label-section">
                          <h4>Quiz label</h4>
                          <>
                              {!match.quiz && (
                                <div className="admin-quiz-unset">
                                  No quiz question set yet. Add one here before participants answer it.
                                </div>
                              )}
                              {match.quiz?.genai && (
                                <div className="admin-genai-detail">
                                  <div>
                                    <strong>{match.quiz.genai.source}</strong>
                                    <span>
                                      {match.quiz.genai.status} ·{" "}
                                      {match.quiz.genai.confidence} confidence
                                    </span>
                                  </div>
                                  <p>{genaiEvidenceSummary(match.quiz.genai)}</p>
                                  {match.quiz.manual_override_active && (
                                    <em>Manual label is used for scoring.</em>
                                  )}
                                </div>
                              )}
                              <label>
                                Question
                                <textarea
                                  rows="3"
                                  value={draft.question ?? ""}
                                  onChange={(event) =>
                                    updateDraft("question", event.target.value)
                                  }
                                />
                              </label>
                              <label>
                                Answer options
                                <textarea
                                  className="admin-quiz-options"
                                  rows="5"
                                  value={draft.choices ?? ""}
                                  onChange={(event) =>
                                    updateDraft("choices", event.target.value)
                                  }
                                  placeholder="One option per line"
                                />
                              </label>
                              <label>
                                Correct answers
                                {quizOptions.length ? (
                                  <div className="admin-quiz-answer-options">
                                    {quizOptions.map((choice) => {
                                      const selected = selectedQuizAnswers.has(
                                        choice.value,
                                      );
                                      const points = adminQuizChoicePoints(
                                        activeQuiz,
                                        choice.value,
                                      );
                                      return (
                                        <button
                                          className={
                                            selected
                                              ? "admin-quiz-answer-option is-selected"
                                              : "admin-quiz-answer-option"
                                          }
                                          type="button"
                                          key={choice.value}
                                          aria-pressed={selected}
                                          onClick={() =>
                                            updateDraft(
                                              "correct_answers",
                                              selected ? [] : [choice.value],
                                            )
                                          }
                                        >
                                          <span>
                                            {String(choice.label).replace(
                                              /\s\([^)]*pts\)$/,
                                              "",
                                            )}
                                          </span>
                                          <b>{points} pts</b>
                                        </button>
                                      );
                                    })}
                                  </div>
                                ) : (
                                  <input
                                    value={quizAnswerValues(
                                      draft.correct_answers,
                                    ).join(", ")}
                                    onChange={(event) =>
                                      updateDraft(
                                        "correct_answers",
                                        quizAnswerValues(event.target.value),
                                      )
                                    }
                                  />
                                )}
                              </label>
                              <label>
                                Viewership answer
                                <input
                                  type="number"
                                  value={draft.viewership_answer ?? ""}
                                  onChange={(event) =>
                                    updateDraft("viewership_answer", event.target.value)
                                  }
                                />
                              </label>
                              <div className="admin-label-actions">
                                <button
                                  className="primary-button"
                                  type="button"
                                  disabled={saving === "quiz"}
                                  onClick={() => saveQuiz(false)}
                                >
                                  {saving === "quiz" ? "Saving..." : "Save quiz"}
                                </button>
                                <button
                                  className="text-button"
                                  type="button"
                                  disabled={saving === "quiz"}
                                  onClick={() => saveQuiz(true)}
                                >
                                  Clear override
                                </button>
                              </div>
                            </>
                        </section>

                        <section className="admin-label-section is-wide">
                          <h4>Goal and scorer labels</h4>
                          {playerGenaiLinks.length > 0 && (
                            <div className="admin-genai-link-list">
                              {playerGenaiLinks.map((link) => (
                                <span
                                  key={`${link.raw_player_name}-${link.matched_player_name}`}
                                >
                                  {genaiPlayerLinkSummary(link)}
                                </span>
                              ))}
                            </div>
                          )}
                          <textarea
                            rows="8"
                            value={draft.events_json ?? "[]"}
                            onChange={(event) =>
                              updateDraft("events_json", event.target.value)
                            }
                          />
                          <div className="admin-label-actions">
                            <button
                              className="primary-button"
                              type="button"
                              disabled={saving === "events"}
                              onClick={() => saveJsonLabel("events")}
                            >
                              {saving === "events" ? "Saving..." : "Save goal labels"}
                            </button>
                            <button
                              className="text-button"
                              type="button"
                              disabled={saving === "events"}
                              onClick={() => saveJsonLabel("events", true)}
                            >
                              Revert override
                            </button>
                          </div>
                        </section>

                        <section className="admin-label-section is-wide">
                          <h4>Player stat labels</h4>
                          <textarea
                            rows="8"
                            value={draft.player_stats_json ?? "[]"}
                            onChange={(event) =>
                              updateDraft("player_stats_json", event.target.value)
                            }
                          />
                          <div className="admin-label-actions">
                            <button
                              className="primary-button"
                              type="button"
                              disabled={saving === "player_stats"}
                              onClick={() => saveJsonLabel("player_stats")}
                            >
                              {saving === "player_stats"
                                ? "Saving..."
                                : "Save player stats"}
                            </button>
                            <button
                              className="text-button"
                              type="button"
                              disabled={saving === "player_stats"}
                              onClick={() => saveJsonLabel("player_stats", true)}
                            >
                              Revert override
                            </button>
                          </div>
                        </section>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>

            <div className="admin-label-audit">
              <h4>Recent label edits</h4>
              {labels.audit?.length ? (
                labels.audit.slice(0, 8).map((entry, index) => (
                  <span key={`${entry.match_id}-${entry.created_at}-${index}`}>
                    {entry.created_at}: {entry.label_type} · {entry.match_id}
                  </span>
                ))
              ) : (
                <span>No manual label edits yet.</span>
              )}
            </div>
          </>
        )}
      </div>
    </article>
  );
}

function AdminBroadcastPage() {
  const [broadcasts, setBroadcasts] = useState([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function loadBroadcasts() {
    setLoading(true);
    setError("");
    try {
      const result = await apiJson("/api/admin/notifications/broadcasts");
      setBroadcasts(result.broadcasts ?? []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBroadcasts();
  }, []);

  async function sendBroadcast(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const result = await apiJson("/api/admin/notifications/broadcasts", {
        method: "POST",
        body: JSON.stringify({
          title,
          body,
          expires_at: expiresAt || null,
        }),
      });
      setBroadcasts(result.broadcasts ?? []);
      setTitle("");
      setBody("");
      setExpiresAt("");
      setSuccess("Message sent.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function deactivateBroadcast(id) {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const result = await apiJson(
        `/api/admin/notifications/broadcasts/${id}/deactivate`,
        { method: "POST", body: "{}" },
      );
      setBroadcasts(result.broadcasts ?? []);
      setSuccess("Message deactivated.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <article className="panel admin-message-panel">
      <div className="panel-header">
        <div>
          <h3>Send message</h3>
          <p>Send a notification-bell message to everyone.</p>
        </div>
        <span className="pill orange">{broadcasts.length} messages</span>
      </div>
      <form className="panel-body admin-message-form" onSubmit={sendBroadcast}>
        {error && <div className="form-error">{error}</div>}
        {success && <div className="form-success">{success}</div>}
        <label>
          Title
          <input
            value={title}
            maxLength="120"
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Deadline reminder"
          />
        </label>
        <label>
          Message
          <textarea
            rows="4"
            value={body}
            maxLength="600"
            onChange={(event) => setBody(event.target.value)}
            placeholder="Fill in today's predictions before lock."
          />
        </label>
        <label>
          Expires at (optional)
          <input
            value={expiresAt}
            onChange={(event) => setExpiresAt(event.target.value)}
            placeholder="2026-06-11T18:00:00Z"
          />
        </label>
        <button className="primary-button" type="submit" disabled={saving}>
          {saving ? "Sending..." : "Send message"}
        </button>
        <div className="admin-broadcast-list">
          {loading ? (
            <div className="empty compact">Loading messages...</div>
          ) : broadcasts.length ? (
            broadcasts.map((broadcast) => (
              <article
                key={broadcast.id}
                className={
                  broadcast.is_active
                    ? "admin-broadcast-row"
                    : "admin-broadcast-row is-inactive"
                }
              >
                <div>
                  <strong>{broadcast.title}</strong>
                  <p>{broadcast.body}</p>
                  <span>
                    {broadcast.created_at}
                    {broadcast.expires_at ? ` · expires ${broadcast.expires_at}` : ""}
                  </span>
                </div>
                {broadcast.is_active ? (
                  <button
                    className="text-button"
                    type="button"
                    disabled={saving}
                    onClick={() => deactivateBroadcast(broadcast.id)}
                  >
                    Deactivate
                  </button>
                ) : (
                  <span className="pill">Inactive</span>
                )}
              </article>
            ))
          ) : (
            <div className="empty compact">No messages sent yet.</div>
          )}
        </div>
      </form>
    </article>
  );
}

function AdminDataSyncPage({ teams, onSyncComplete }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [syncStartedAt, setSyncStartedAt] = useState(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [reviewingJobId, setReviewingJobId] = useState(null);
  const [reviewChoices, setReviewChoices] = useState({});
  const [savingReviewId, setSavingReviewId] = useState(null);
  const [manualFillDrafts, setManualFillDrafts] = useState({});
  const [savingManualFillId, setSavingManualFillId] = useState("");

  const syncSteps = [
    "Checking missing match results",
    "Running scoring jobs",
    "Recomputing points",
  ];

  useEffect(() => {
    if (!busy || !syncStartedAt) return undefined;
    const interval = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - syncStartedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(interval);
  }, [busy, syncStartedAt]);

  function skippedMatchLabel(item) {
    const match = item.match || {};
    const teams =
      match.home_team_name && match.away_team_name
        ? `${match.home_team_name} vs ${match.away_team_name}`
        : item.match_id;
    return `Match ${match.match_number || item.match_id}: ${teams}`;
  }

  function requestCountLabel() {
    if (!result) return "";
    if (result.daily_limit === null || result.daily_limit === undefined) {
      return `API requests today: ${result.requests_today ?? "?"}`;
    }
    return `API requests today: ${result.requests_today ?? "?"}/${result.daily_limit}`;
  }

  async function syncAllData() {
    setBusy(true);
    setError("");
    setResult(null);
    setElapsedSeconds(0);
    setSyncStartedAt(Date.now());
    try {
      const response = await apiJson("/api/admin/api-football/data-sync", {
        method: "POST",
        body: "{}",
      });
      setResult(response);
      const fillDrafts = {};
      for (const fill of response.genai_jobs?.manual_quiz_fills ?? []) {
        fillDrafts[fill.match_id] = {
          correct_answer: "",
          viewership_answer: "",
        };
      }
      setManualFillDrafts(fillDrafts);
      if (response.ok && typeof onSyncComplete === "function") {
        await onSyncComplete();
      }
    } catch (syncError) {
      setError(syncError.message);
    } finally {
      setBusy(false);
      setSyncStartedAt(null);
    }
  }

  const quizReviews = (result?.genai_jobs?.quiz_jobs ?? [])
    .map((job) => job.review)
    .filter(Boolean);
  const manualQuizFills = result?.genai_jobs?.manual_quiz_fills ?? [];

  function manualFillChoiceOptions(fill) {
    return quizChoices(
      {
        home_team_id: fill.home_team_id,
        away_team_id: fill.away_team_id,
        quiz: {
          question: fill.question,
          type: fill.type,
          choices: fill.choices ?? [],
          dynamic_choice_points: 5,
        },
      },
      teams,
    );
  }

  function quizMatchAbbreviation(item) {
    const homeId = item.home_team_id;
    const awayId = item.away_team_id;
    const home = teams.get(homeId);
    const away = teams.get(awayId);
    const homeCode = home?.code ?? String(homeId ?? "").toUpperCase();
    const awayCode = away?.code ?? String(awayId ?? "").toUpperCase();
    if (!homeCode || !awayCode) return item.match_id ? `Match ${item.match_id}` : "";
    return `${homeCode} vs ${awayCode}`;
  }

  function updateManualFillDraft(matchId, key, value) {
    setManualFillDrafts((current) => ({
      ...current,
      [matchId]: {
        ...(current[matchId] ?? {}),
        [key]: value,
      },
    }));
  }

  async function saveManualQuizFill(fill) {
    const draft = manualFillDrafts[fill.match_id] ?? {};
    const answer = String(draft.correct_answer ?? "").trim();
    const choices = manualFillChoiceOptions(fill).map((choice) => choice.value);
    if (!answer) {
      setError("Fill in the correct quiz answer before saving.");
      return;
    }
    if (!choices.includes(answer)) {
      setError("Select one of the available quiz answers before saving.");
      return;
    }
    setSavingManualFillId(fill.match_id);
    setError("");
    try {
      await apiJson(`/api/admin/labels/${fill.match_id}/quiz`, {
        method: "PATCH",
        body: JSON.stringify({
          question: fill.question,
          choices,
          correct_answers: [answer],
          viewership_answer: draft.viewership_answer,
        }),
      });
      setResult((current) => ({
        ...current,
        genai_jobs: {
          ...current.genai_jobs,
          manual_quiz_fills: (current.genai_jobs?.manual_quiz_fills ?? []).filter(
            (item) => item.match_id !== fill.match_id,
          ),
        },
      }));
      if (typeof onSyncComplete === "function") await onSyncComplete();
    } catch (fillError) {
      setError(fillError.message);
    } finally {
      setSavingManualFillId("");
    }
  }

  async function submitQuizReview(review, decision) {
    const correctAnswer = reviewChoices[review.job_result_id] ?? "";
    if (decision === "disapproved" && !correctAnswer) {
      setError("Select the correct answer before saving.");
      return;
    }
    setSavingReviewId(review.job_result_id);
    setError("");
    try {
      const response = await apiJson(
        `/api/admin/genai/quiz-reviews/${review.job_result_id}`,
        {
          method: "POST",
          body: JSON.stringify({ decision, correct_answer: correctAnswer }),
        },
      );
      setResult((current) => ({
        ...current,
        genai_jobs: {
          ...current.genai_jobs,
          quiz_jobs: current.genai_jobs.quiz_jobs.map((job) =>
            job.review?.job_result_id === review.job_result_id
              ? { ...job, review: response.review }
              : job,
          ),
        },
      }));
      setReviewingJobId(null);
      if (typeof onSyncComplete === "function") await onSyncComplete();
    } catch (reviewError) {
      setError(reviewError.message);
    } finally {
      setSavingReviewId(null);
    }
  }

  const activeStepIndex = result
    ? syncSteps.length - 1
    : Math.min(syncSteps.length - 1, Math.floor(elapsedSeconds / 8));

  const syncLog = result
    ? [
      `${result.match_ids?.length ?? 0} missing matches checked`,
      `${result.synced?.length ?? 0} matches synced`,
      result.computed_points_updated ? "Points recomputed" : null,
    ].filter(Boolean)
    : [];

  return (
    <article className="panel admin-message-panel">
      <div className="panel-header">
        <div>
          <h3>Data sync</h3>
          <p>Fetch match results that are still missing and update scoring.</p>
        </div>
      </div>
      <div className="panel-body admin-sync-panel">
        <button
          className="primary-button"
          type="button"
          disabled={busy}
          onClick={syncAllData}
        >
          {busy ? "Syncing API-Football..." : "Sync missing match results"}
        </button>
        {(busy || result) && (
          <div className="admin-sync-progress">
            <div className="admin-sync-progress-header">
              <strong>{busy ? "Sync running" : "Sync log"}</strong>
              {busy && <span>{elapsedSeconds}s</span>}
            </div>
            <ol className="admin-sync-steps">
              {syncSteps.map((step, index) => {
                const status = result
                  ? "done"
                  : index < activeStepIndex
                    ? "done"
                    : index === activeStepIndex
                      ? "active"
                      : "pending";
                return (
                  <li className={`is-${status}`} key={step}>
                    <span>{index + 1}</span>
                    <strong>{step}</strong>
                  </li>
                );
              })}
            </ol>
            {!!syncLog.length && (
              <div className="admin-sync-log">
                {syncLog.map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
            )}
          </div>
        )}
        {error && <div className="form-error">{error}</div>}
        {result && (
          <div className="admin-sync-result">
            <strong>{result.ok ? "Sync complete" : "Sync finished with errors"}</strong>
            <span>{result.match_ids?.length ?? 0} missing matches checked</span>
            <span>{result.synced?.length ?? 0} matches synced</span>
            <span>{result.attempts?.length ?? 0} provider attempts</span>
            <span>{result.skipped?.length ?? 0} skipped</span>
            <span>{requestCountLabel()}</span>
            {result.computed_points_updated && <span>Points recomputed</span>}
            {result.skipped?.length > 0 && (
              <div className="admin-sync-details">
                {result.skipped.map((item) => (
                  <div key={`${item.match_id}-${item.reason}`} className="admin-sync-detail">
                    <strong>{skippedMatchLabel(item)}</strong>
                    <span>{item.message || item.reason || "Skipped"}</span>
                  </div>
                ))}
              </div>
            )}
            {quizReviews.length > 0 && (
              <section className="admin-genai-review-list" aria-label="GenAI quiz reviews">
                <div className="admin-genai-review-heading">
                  <strong>Check GenAI quiz answers</strong>
                  <span>{quizReviews.length} answered</span>
                </div>
                {quizReviews.map((review) => {
                  const pending = review.review_status === "pending";
                  const choosing = reviewingJobId === review.job_result_id;
                  return (
                    <div className="admin-genai-review" key={review.job_result_id}>
                      <div>
                        <div className="admin-genai-question-row">
                          <strong>{review.question}</strong>
                          <span>{quizMatchAbbreviation(review)}</span>
                        </div>
                        <span>
                          GenAI answer: {review.genai_answers.join(", ") || "Missing"}
                          {review.confidence ? ` · ${review.confidence} confidence` : ""}
                        </span>
                      </div>
                      {!pending ? (
                        <span className="pill">
                          {review.review_status === "approved"
                            ? "Approved"
                            : `Corrected to ${review.reviewed_answers.join(", ")}`}
                        </span>
                      ) : (
                        <div className="admin-genai-review-actions">
                          <button
                            className="primary-button"
                            type="button"
                            disabled={savingReviewId === review.job_result_id}
                            onClick={() => submitQuizReview(review, "approved")}
                          >
                            Approve
                          </button>
                          <button
                            className="text-button"
                            type="button"
                            disabled={savingReviewId === review.job_result_id}
                            onClick={() => setReviewingJobId(choosing ? null : review.job_result_id)}
                          >
                            Disapprove
                          </button>
                        </div>
                      )}
                      {pending && choosing && (
                        <div className="admin-genai-correction">
                          <strong>Select the correct answer</strong>
                          <div className="admin-genai-correction-options">
                            {review.choices.map((choice) => (
                              <label key={choice}>
                                <input
                                  type="radio"
                                  name={`genai-correction-${review.job_result_id}`}
                                  value={choice}
                                  checked={reviewChoices[review.job_result_id] === choice}
                                  onChange={() =>
                                    setReviewChoices((current) => ({
                                      ...current,
                                      [review.job_result_id]: choice,
                                    }))
                                  }
                                />
                                <span>{choice}</span>
                              </label>
                            ))}
                          </div>
                          <button
                            className="primary-button"
                            type="button"
                            disabled={
                              savingReviewId === review.job_result_id ||
                              !reviewChoices[review.job_result_id]
                            }
                            onClick={() => submitQuizReview(review, "disapproved")}
                          >
                            Save correct answer
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </section>
            )}
            {manualQuizFills.length > 0 && (
              <section className="admin-genai-review-list" aria-label="Manual quiz labels">
                <div className="admin-genai-review-heading">
                  <strong>Fill missing quiz labels</strong>
                  <span>{manualQuizFills.length} manual</span>
                </div>
                {manualQuizFills.map((fill) => {
                  const draft = manualFillDrafts[fill.match_id] ?? {};
                  const options = manualFillChoiceOptions(fill);
                  const matchTitle =
                    fill.home_team_name && fill.away_team_name
                      ? `${fill.home_team_name} vs ${fill.away_team_name}`
                      : fill.match_id;
                  return (
                    <div className="admin-genai-review" key={fill.match_id}>
                      <div>
                        <div className="admin-genai-question-row">
                          <strong>{fill.question}</strong>
                          <span>{quizMatchAbbreviation(fill)}</span>
                        </div>
                        <span>{matchTitle}</span>
                      </div>
                      <div className="admin-genai-correction">
                        <strong>Manual answer</strong>
                        {options.length ? (
                          <div className="admin-genai-correction-options">
                            {options.map((choice) => (
                              <label key={choice.value}>
                                <input
                                  type="radio"
                                  name={`manual-quiz-fill-${fill.match_id}`}
                                  value={choice.value}
                                  checked={draft.correct_answer === choice.value}
                                  onChange={() =>
                                    updateManualFillDraft(
                                      fill.match_id,
                                      "correct_answer",
                                      choice.value,
                                    )
                                  }
                                />
                                <span>{String(choice.label).replace(/\s\([^)]*pts\)$/, "")}</span>
                              </label>
                            ))}
                          </div>
                        ) : (
                          <div className="form-error">
                            No selectable quiz answers are available for this match.
                          </div>
                        )}
                        {fill.viewership_required && (
                          <label>
                            Viewership answer
                            <input
                              type="number"
                              value={draft.viewership_answer ?? ""}
                              onChange={(event) =>
                                updateManualFillDraft(
                                  fill.match_id,
                                  "viewership_answer",
                                  event.target.value,
                                )
                              }
                            />
                          </label>
                        )}
                        <button
                          className="primary-button"
                          type="button"
                          disabled={
                            savingManualFillId === fill.match_id ||
                            !String(draft.correct_answer ?? "").trim() ||
                            !options.length
                          }
                          onClick={() => saveManualQuizFill(fill)}
                        >
                          {savingManualFillId === fill.match_id
                            ? "Saving..."
                            : "Save manual quiz label"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </section>
            )}
          </div>
        )}
      </div>
    </article>
  );
}

function AdminPage({ currentUser, teams, onSyncComplete }) {
  const [section, setSection] = useState("labels");

  return (
    <div className="admin-page">
      <article className="panel admin-switcher-panel">
        <div className="panel-header">
          <div>
            <h3>Admin</h3>
            <p>Manage pool access and scoring labels.</p>
          </div>
          <label className="admin-section-select">
            Section
            <select value={section} onChange={(event) => setSection(event.target.value)}>
              <option value="users">User management</option>
              <option value="labels">Adjust labels</option>
              <option value="sync">Data sync</option>
              <option value="messages">Send message</option>
            </select>
          </label>
        </div>
      </article>
      {section === "users" ? (
        <AdminUsersPage currentUser={currentUser} />
      ) : section === "messages" ? (
        <AdminBroadcastPage />
      ) : section === "sync" ? (
        <AdminDataSyncPage teams={teams} onSyncComplete={onSyncComplete} />
      ) : (
        <AdminLabelsPage teams={teams} />
      )}
    </div>
  );
}

function ScoringRulesPanel({ rules }) {
  const groupRule = rules?.match_scores?.["Group Stage"] ?? {};
  const finalRule = rules?.match_scores?.["Final"] ?? {};
  const strikerRule = rules?.world_cup_strikers ?? {
    count: 5,
    points_per_goal: 6,
  };
  const groupExact = groupRule.exact ?? 12;
  const groupOutcome = groupRule.outcome ?? 6;
  const finalExact = finalRule.exact ?? 48;
  return (
    <article className="panel scoring-rules-panel">
      <div className="panel-header">
        <div>
          <h3>Puntentelling</h3>
          <p>Hoe voorspellingen, quizvragen en toernooipicks meetellen.</p>
        </div>
      </div>
      <div className="panel-body scoring-rules-grid">
        <div>
          <strong>Wedstrijden</strong>
          <span>
            Poulefase: {groupExact} punten exact, {groupOutcome} voor juiste
            toto.
          </span>
          <span>Juiste thuisgoals en uitgoals leveren extra punten op.</span>
          <span>
            Knock-out loopt op per ronde, tot {finalExact} punten exact in de
            finale.
          </span>
        </div>
        <div>
          <strong>Quiz</strong>
          <span>Keuze-opties tonen hun eigen punten op basis van kans.</span>
          <span>Open quizvragen: {rules?.quiz_open ?? 5} punten.</span>
        </div>
        <div>
          <strong>Toernooi</strong>
          <span>Wereldkampioen: {rules?.world_cup_winner ?? 60} punten.</span>
          <span>
            Topscorer: {rules?.world_cup_top_scorer ?? 40} punten aan het
            einde.
          </span>
          <span>
            {strikerRule.count ?? 5} spitsen:{" "}
            {strikerRule.points_per_goal ?? 6} basispunten per goal, met
            ronde-multiplier.
          </span>
        </div>
        <div>
          <strong>Leeuwtjes</strong>
          <span>{rules?.leeuwtjes_total ?? 5} keer inzetbaar.</span>
          <span>Verdubbelt de wedstrijdpunten van die voorspelling.</span>
        </div>
      </div>
    </article>
  );
}

function FaqPage({ rules }) {
  const groupRule = rules?.match_scores?.["Group Stage"] ?? {};
  const finalRule = rules?.match_scores?.["Final"] ?? {};
  const strikerRule = rules?.world_cup_strikers ?? {};
  const groupExact = groupRule.exact ?? 12;
  const groupOutcome = groupRule.outcome ?? 6;
  const groupHomeGoals = groupRule.home_goals ?? 2;
  const groupAwayGoals = groupRule.away_goals ?? 2;
  const groupExactBonus = groupRule.exact_bonus ?? 2;
  const finalExact = finalRule.exact ?? 48;
  const leeuwtjes = rules?.leeuwtjes_total ?? 5;
  const strikerCount = strikerRule.count ?? 5;
  const strikerGoal = strikerRule.points_per_goal ?? 6;
  const topScorer = rules?.world_cup_top_scorer ?? 40;
  const winner = rules?.world_cup_winner ?? 60;
  const quizOpen = rules?.quiz_open ?? 5;

  const faqItems = [
    {
      q: "Hoe verdien ik punten met wedstrijden?",
      a: `Voorspel de uitslag van elke wedstrijd. In de poulefase krijg je ${groupOutcome} punten voor de juiste toto, ${groupHomeGoals} voor het juiste aantal thuisgoals, ${groupAwayGoals} voor het juiste aantal uitgoals en ${groupExactBonus} bonuspunten voor een exacte score. Een exacte poulefase-uitslag is dus ${groupExact} punten. In de knock-out lopen de punten per ronde op, tot ${finalExact} punten voor een exact voorspelde finale. Je voorspelling aanpassen kan tot 1 uur voor de aftrap.`,
    },
    {
      q: "Wat doen de Leeuwtjes?",
      a: `Een Leeuwtje verdubbelt de wedstrijdpunten van die ene voorspelling. Je hebt er ${leeuwtjes} voor de groep fase van het toernooi. Zet er een in bij een wedstrijd vóórdat die op slot gaat (1 uur voor de aftrap). Tot dat moment kun je het Leeuwtje ook weer weghalen en op een andere wedstrijd zetten. Tip: bewaar ze voor duels waar je zeker van bent!`,
    },
    {
      q: "Hoe werken de spitsen?",
      a: `Je kiest ${strikerCount} spitsen. Elke goal die een van jouw spitsen maakt, levert ${strikerGoal} basispunten op en volgt dezelfde ronde-multiplier als wedstrijdpunten. Een goal in de finale is dus veel meer waard dan een goal in de poulefase. Je kiest ze eenmalig vóór de eerste groepswedstrijd; daarna staan ze vast.`,
    },
    {
      q: "Wat levert de topscorer op?",
      a: `Voorspel wie er aan het einde van het toernooi topscorer wordt. Heb je het goed, dan krijg je ${topScorer} punten. Ook deze keuze leg je vóór de eerste groepswedstrijd vast.`,
    },
    {
      q: "En de wereldkampioen?",
      a: `Voorspel welk land het WK wint. Goed voorspeld is dat ${winner} punten — de grootste klapper van de pool. Vastleggen kan tot 1 uur voor de eerste groepswedstrijd.`,
    },
    {
      q: "Krijg ik punten voor de eindstand van een poule?",
      a: "Nee. De poulestand wordt nog wel gebruikt voor voortgang en badges, maar levert geen losse punten meer op. Je verdient punten direct met je wedstrijdvoorspellingen.",
    },
    {
      q: "Wat zijn de quizvragen?",
      a: `Bij sommige wedstrijden hoort een quizvraag. Bij keuzevragen zie je per antwoord hoeveel punten het oplevert; makkelijke antwoorden zijn weinig punten en onwaarschijnlijke antwoorden maximaal ${quizOpen} punten. Open spelervragen zijn ${quizOpen} punten. Beantwoorden kan tot 1 uur voor de aftrap.`,
    },
    {
      q: "Wanneer gaat alles op slot?",
      a: `Wedstrijdvoorspellingen, quizantwoorden en Leeuwtjes kun je aanpassen tot 1 uur voor de aftrap van die wedstrijd. Je toernooipicks (wereldkampioen, topscorer en spitsen) liggen vast vanaf 1 uur voor de allereerste groepswedstrijd.`,
    },
  ];

  return (
    <div className="faq-layout">
      <article className="panel">
        <div className="panel-header">
          <div>
            <h3>Veelgestelde vragen</h3>
            <p>Hoe werkt de pool? Alles over voorspellen, Leeuwtjes, spitsen en punten.</p>
          </div>
          <span className="pill green">{faqItems.length} vragen</span>
        </div>
        <div className="panel-body faq-list">
          {faqItems.map((item, index) => (
            <details className="faq-item" key={item.q} open={index === 0}>
              <summary>{item.q}</summary>
              <p>{item.a}</p>
            </details>
          ))}
        </div>
      </article>
      <ScoringRulesPanel rules={rules} />
    </div>
  );
}

function HomePage({ onSchedule, recap, rules, newsletters = [] }) {
  const articles = newsletters.length ? newsletters : NEWS_ARTICLES;
  return (
    <div className="home-layout">
      <section className="home-kicker" aria-label="World Cup quick links">
        <div>
          <p className="eyebrow">World Cup hub</p>
          <h3>News from Dutch and Belgian press</h3>
          <p>
            Follow the tournament context, then jump straight into the match
            schedule.
          </p>
        </div>
        <button className="primary-button" type="button" onClick={onSchedule}>
          View games
        </button>
      </section>

      <DailyRecap recap={recap} />

      <section className="news-grid" aria-label="World Cup news">
        {articles.map((article) => (
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

      <ScoringRulesPanel rules={rules} />
    </div>
  );
}

function OutcomeBar({ home, draw, away }) {
  const total = home + draw + away;
  const homeWidth = total ? `${Math.round((home / total) * 100)}%` : "0%";
  const drawWidth = total ? `${Math.round((draw / total) * 100)}%` : "0%";
  const awayWidth = total ? `${Math.round((away / total) * 100)}%` : "0%";
  return (
    <div
      className="outcome-bar"
      aria-label={`${home} home, ${draw} draw, ${away} away predictions`}
    >
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
    {
      key: "home",
      label: homeTeam?.code ?? homeTeam?.name ?? "Home",
      value: home,
    },
    { key: "draw", label: "Tie", value: draw },
    {
      key: "away",
      label: awayTeam?.code ?? awayTeam?.name ?? "Away",
      value: away,
    },
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
  const [dayScoreOpen, setDayScoreOpen] = useState(false);
  const topPlayers = recap?.top_players ?? [];
  const topWinners = recap?.top_winners ?? [];
  const topLosers = recap?.top_losers ?? [];
  const dayScores = recap?.day_scores ?? [];
  const renderRankChanges = (players, emptyText) => (
    <>
      {!players.length && <div className="empty compact">{emptyText}</div>}
      {!!players.length && (
        <ol className="daily-top-list">
          {players.map((player, index) => (
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
    </>
  );
  return (
    <article className="panel recap-panel">
      <div className="panel-header">
        <div>
          <h3>Daily recap</h3>
          <p>Dagscore, stijgers en dalers.</p>
        </div>
        <span className={recap?.available ? "pill green" : "pill"}>
          {recap?.available ? "Live" : "Nog leeg"}
        </span>
      </div>
      <div className="panel-body recap-body">
        <div className="daily-recap-grid">
          <section className="daily-recap-board">
            <div className="daily-recap-board-heading">
              <h4>Dagscore</h4>
              {!!dayScores.length && (
                <button
                  className="text-button compact"
                  type="button"
                  onClick={() => setDayScoreOpen(true)}
                >
                  Bekijk alles
                </button>
              )}
            </div>
            {!topPlayers.length && (
              <div className="empty compact">Nog geen dagpunten.</div>
            )}
            {!!topPlayers.length && (
              <ol className="daily-top-list">
                {topPlayers.map((player, index) => (
                  <li className="is-score" key={player.user_id}>
                    <span className="daily-rank">
                      {player.rank ?? index + 1}
                    </span>
                    <ProfileAvatar player={player} size="small" />
                    <strong>{player.name}</strong>
                    <b>{player.points} pts</b>
                  </li>
                ))}
              </ol>
            )}
          </section>
          <section className="daily-recap-board">
            <h4>Biggest winners</h4>
            {renderRankChanges(topWinners, "Nog geen stijgers.")}
          </section>
          <section className="daily-recap-board">
            <h4>Biggest losers</h4>
            {renderRankChanges(topLosers, "Nog geen dalers.")}
          </section>
        </div>
      </div>
      {dayScoreOpen && (
        <DayScoreModal recap={recap} onClose={() => setDayScoreOpen(false)} />
      )}
    </article>
  );
}

function DayScoreModal({ recap, onClose }) {
  const [expandedUserId, setExpandedUserId] = useState(null);
  const rows = recap?.day_scores ?? [];
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <article
        className="day-score-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Dagscore"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="prediction-modal-header">
          <div>
            <h3>Dagscore</h3>
            <p>{recap?.date ? formatSessionDate(recap.date) : "Laatste wedstrijddag"}</p>
          </div>
          <button className="text-button" type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="day-score-list">
          {!rows.length && <div className="empty compact">Nog geen dagpunten.</div>}
          {rows.map((player) => {
            const expanded = expandedUserId === player.user_id;
            return (
              <section className="day-score-row" key={player.user_id}>
                <button
                  className="day-score-row-button"
                  type="button"
                  onClick={() =>
                    setExpandedUserId((current) =>
                      current === player.user_id ? null : player.user_id,
                    )
                  }
                  aria-expanded={expanded}
                >
                  <span className="daily-rank">{player.rank ?? "-"}</span>
                  <ProfileAvatar player={player} size="small" />
                  <strong>{player.name}</strong>
                  <b>{player.points ?? 0} pts</b>
                </button>
                {expanded && (
                  <div className="day-score-breakdowns">
                    {(player.matches ?? []).map((match) => (
                      <div className="day-score-match" key={match.match_id}>
                        <strong>{match.label}</strong>
                        <MatchPointBreakdown points={match.points} />
                      </div>
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      </article>
    </div>
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
  const unlockedByKey = new Map(
    unlockedBadges.map((badge) => [badge.key, badge]),
  );
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
  const unlockedCount = canView
    ? badges.filter((badge) => badge.unlocked).length
    : 0;

  return (
    <article className="panel profile-badges">
      <div className="panel-header">
        <div>
          <h3>Badges</h3>
          <p>Unlocked badges and progress toward the next ones.</p>
        </div>
        <span className={canView ? "pill green" : "pill"}>
          {unlockedCount}/{badges.length}
        </span>
      </div>
      <div className="panel-body">
        {!canView && (
          <div className="empty compact">
            Badges are visible when you follow each other.
          </div>
        )}
        {canView && !badges.length && (
          <div className="empty compact">Geen badges beschikbaar.</div>
        )}
        {canView && !!badges.length && (
          <div className="badge-progress-grid">
            {badges.map((badge) => (
              <article
                className={`badge-progress-card is-${badge.family} ${badge.unlocked ? "is-unlocked" : "is-locked"}`}
                key={badge.key}
              >
                <div className="badge-progress-heading">
                  <span className="badge-progress-mark" aria-hidden="true">
                    {badge.mark ?? "B"}
                  </span>
                  <div>
                    <h4>{badge.label}</h4>
                    <p>{badge.detail}</p>
                  </div>
                </div>
                <div className="badge-progress-track" aria-hidden="true">
                  <span style={{ width: `${badge.progress ?? 0}%` }} />
                </div>
                <div className="badge-progress-meta">
                  <span>
                    {badge.current ?? 0}/{badge.target ?? 1} {badge.unit}
                  </span>
                  <strong>
                    {badge.unlocked
                      ? `Unlocked${badge.count > 1 ? ` x${badge.count}` : ""}`
                      : "Locked"}
                  </strong>
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
          {!badges.length && (
            <div className="empty compact">Geen badges beschikbaar.</div>
          )}
          {Object.entries(groupedBadges).map(([family, familyBadges]) => (
            <section className="badge-family" key={family}>
              <div className="badge-family-heading">
                <span
                  className={`badge-family-mark is-${family}`}
                  aria-hidden="true"
                >
                  {familyBadges[0]?.mark ?? "B"}
                </span>
                <div>
                  <h4>{badgeFamilyLabel(family, familyBadges[0]?.mascot)}</h4>
                  <p>{familyBadges[0]?.mascot ?? "Badge familie"}</p>
                </div>
              </div>
              <div className="badge-catalog-grid">
                {familyBadges.map((badge) => (
                  <article
                    className={`badge-catalog-card is-${badge.family}`}
                    key={badge.key}
                  >
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
  const [quizDraft, setQuizDraft] = useState({
    answer: "",
  });
  const [leeuwtjeActive, setLeeuwtjeActive] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!match) return;
    const existingPrediction = poolPredictions(pool)[match.id] ?? {};
    const existingQuiz = poolQuizPredictions(pool)[match.id] ?? {};
    const currentLeeuwtjes = new Set(poolLeeuwtjeMatchIds(pool));
    setScores({
      home_score: existingPrediction.home_score ?? "",
      away_score: existingPrediction.away_score ?? "",
    });
    setQuizDraft({
      answer: existingQuiz.answer ?? "",
    });
    setLeeuwtjeActive(currentLeeuwtjes.has(match.id));
    setError("");
  }, [match?.id, pool]);

  if (!match) return null;

  const leeuwtjeTotal = leeuwtjesTotal(pool);
  const currentLeeuwtjes = new Set(poolLeeuwtjeMatchIds(pool));
  const leeuwtjesRemaining = Math.max(0, leeuwtjeTotal - currentLeeuwtjes.size);
  const canToggleLeeuwtje =
    leeuwtjeActive ||
    currentLeeuwtjes.has(match.id) ||
    currentLeeuwtjes.size < leeuwtjeTotal;
  const locked = Boolean(match.locked);
  const quizComplete = quizAnswerComplete(match.quiz, quizDraft);
  const canSave = scoreComplete(scores) && quizComplete && !saving && !locked;

  function setScore(_matchId, key, value) {
    setScores((current) => ({ ...current, [key]: value }));
  }

  function setQuizAnswer(_matchId, value) {
    setQuizDraft((current) => ({ ...current, answer: value }));
  }

  async function savePrediction() {
    if (!canSave) return;
    setSaving(true);
    setError("");
    const body = {
      home_score: Number(scores.home_score),
      away_score: Number(scores.away_score),
      leeuwtje: leeuwtjeActive,
    };
    if (match.quiz) {
      body.quiz_answer = String(quizDraft.answer ?? "").trim();
    }

    try {
      const result = await apiJson(`/api/predictions/${match.id}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      onPoolUpdate(patchPoolAfterMatchPrediction(pool, match.id, result));
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <article
        className="prediction-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Match prediction"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="prediction-modal-header">
          <div>
            <h3>
              <TeamLabel id={match.home_team_id} teams={teams} /> vs{" "}
              <TeamLabel id={match.away_team_id} teams={teams} />
            </h3>
            <p>
              {formatDate(match, true)} · {formatTime(match)}
            </p>
          </div>
          <button className="text-button" type="button" onClick={onClose}>
            Close
          </button>
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
            showSubmit={false}
          />
          <MatchQuizEditor
            match={match}
            teams={teams}
            prediction={quizDraft}
            locked={locked}
            onAnswer={setQuizAnswer}
          />
          <div className="matchday-modal-actions">
            <LeeuwtjeButton
              active={leeuwtjeActive}
              disabled={locked || !canToggleLeeuwtje}
              remaining={leeuwtjesRemaining}
              onToggle={() => setLeeuwtjeActive((current) => !current)}
            />
            <button
              className="primary-button"
              type="button"
              onClick={savePrediction}
              disabled={!canSave}
            >
              {saving ? "Saving..." : "Save prediction"}
            </button>
          </div>
          {!quizComplete && match.quiz && (
            <span className="form-hint">
              Vul ook de quizvraag in om deze voorspelling op te slaan.
            </span>
          )}
          {error && <span className="form-error">{error}</span>}
        </div>
      </article>
    </div>
  );
}

function MatchdayPage({ pool, teams, venues, onMatch }) {
  const summary = pool.matchday;
  const [openPointsId, setOpenPointsId] = useState(null);
  const popoverScope = useMemo(
    () => `matchday-${Math.random().toString(36).slice(2)}`,
    [],
  );
  const sessions = summary?.sessions?.length
    ? summary.sessions
    : summary?.matches
      ? [summary]
      : [];
  const defaultSessionIndex = Math.min(
    Math.max(0, summary?.current_session_index ?? 0),
    Math.max(0, sessions.length - 1),
  );
  const [selectedSessionIndex, setSelectedSessionIndex] =
    useState(defaultSessionIndex);
  const selectedSession =
    sessions[Math.min(selectedSessionIndex, Math.max(0, sessions.length - 1))] ??
    null;
  const visibleMatches = selectedSession?.matches ?? [];
  const sessionDateLabel = formatSessionDate(selectedSession?.date);
  const canMovePrevious = selectedSessionIndex > 0;
  const canMoveNext = selectedSessionIndex < sessions.length - 1;

  useEffect(() => {
    setSelectedSessionIndex((current) =>
      Math.min(current, Math.max(0, sessions.length - 1)),
    );
  }, [sessions.length]);

  useEffect(() => {
    function closeOtherPopover(event) {
      if (event.detail?.scope !== popoverScope) setOpenPointsId(null);
    }
    window.addEventListener(POINTS_POPOVER_EVENT, closeOtherPopover);
    return () => {
      window.removeEventListener(POINTS_POPOVER_EVENT, closeOtherPopover);
    };
  }, [popoverScope]);

  function sessionTitle() {
    if (selectedSession?.is_historic) return "Historische wedstrijddag";
    if (selectedSession?.is_today) return "Wedstrijddag";
    return "Volgende wedstrijddag";
  }

  function statusMessage(match) {
    if (match.locked && match.has_my_prediction) {
      return "Je voorspelling is gesloten. Klik om de wedstrijdpagina te bekijken.";
    }
    if (match.locked) {
      return "Deze wedstrijd is gesloten. Klik om de wedstrijdpagina te bekijken.";
    }
    if (match.has_my_prediction) {
      return "Je voorspelling is ingevuld. Klik om de wedstrijdpagina te bekijken.";
    }
    return "Klik om de wedstrijdpagina te bekijken.";
  }

  function openMatch(match) {
    onMatch?.(match.id ?? match.match_id);
  }

  function moveSession(direction) {
    setSelectedSessionIndex((current) =>
      Math.min(Math.max(0, current + direction), Math.max(0, sessions.length - 1)),
    );
  }

  return (
    <div className="matchday-layout">
      <article className="panel">
        <div className="panel-header">
          <div>
            <h3>{sessionTitle()}</h3>
            <p>
              Wedstrijden, voorspellingen, quizreacties en ingezette Leeuwtjes.
              {sessionDateLabel && (
                <>
                  {" "}
                  <span className="matchday-session-date">{sessionDateLabel}</span>
                </>
              )}
            </p>
          </div>
          <div className="matchday-session-controls">
            <button
              className="matchday-arrow"
              type="button"
              onClick={() => moveSession(-1)}
              disabled={!canMovePrevious}
              aria-label="Vorige wedstrijddag"
            >
              ‹
            </button>
            <span className="pill">
              {sessions.length ? selectedSessionIndex + 1 : 0}/{sessions.length}
            </span>
            <button
              className="matchday-arrow"
              type="button"
              onClick={() => moveSession(1)}
              disabled={!canMoveNext}
              aria-label="Volgende wedstrijddag"
            >
              ›
            </button>
            <span className="pill">{visibleMatches.length} matches</span>
          </div>
        </div>
        <div className="panel-body matchday-body">
          {!visibleMatches.length && (
            <div className="empty compact">Geen wedstrijden gevonden.</div>
          )}
          {visibleMatches.map((rawMatch) => {
            const match = { ...rawMatch, id: rawMatch.id ?? rawMatch.match_id };
            const venue = venues.get(match.venue_id);
            const matchStatusMessage = statusMessage(match);
            const myPrediction = match.my_prediction;
            const hasMyPrediction = Boolean(myPrediction);
            return (
              <article
                className={`matchday-card ${match.has_my_prediction ? "is-predicted" : "is-missing"} is-clickable`}
                key={match.match_id}
                role="button"
                tabIndex={0}
                onClick={() => openMatch(match)}
                onKeyDown={(event) => {
                  if (event.key !== "Enter" && event.key !== " ") return;
                  event.preventDefault();
                  openMatch(match);
                }}
              >
                <span
                  className={
                    match.has_my_prediction
                      ? "matchday-status is-done"
                      : "matchday-status is-missing"
                  }
                  aria-label={matchStatusMessage}
                  data-tooltip={matchStatusMessage}
                  title={matchStatusMessage}
                >
                  {match.has_my_prediction ? "✓" : "i"}
                </span>
                <span className="match-time">{formatTime(match)}</span>
                <span className="matchday-main">
                  <strong className="match-teams">
                    <TeamLabel id={match.home_team_id} teams={teams} />{" "}
                    <span className="muted">vs</span>{" "}
                    <TeamLabel id={match.away_team_id} teams={teams} />
                  </strong>
                  <span className="match-meta">
                    {formatDate(match, true)} ·{" "}
                    {venue?.city ?? "Venue to confirm"}
                  </span>
                  {(match.completed || hasMyPrediction) && (
                    <span className="matchday-score-summary">
                      {match.completed && (
                        <span>
                          <strong>Uitslag</strong>
                          {match.home_score ?? "-"} - {match.away_score ?? "-"}
                        </span>
                      )}
                      <span>
                        <strong>Mijn voorspelling</strong>
                        {hasMyPrediction
                          ? `${myPrediction.home_score} - ${myPrediction.away_score}`
                          : "-"}
                      </span>
                      {hasMyPrediction && match.my_points && (
                        <PointsPopoverAnchor
                          label={`Jij: ${match.my_points.total_points ?? 0} pts`}
                          points={match.my_points}
                          open={openPointsId === match.id}
                          onToggle={() => {
                            setOpenPointsId((current) => {
                              const next = current === match.id ? null : match.id;
                              if (next) {
                                window.dispatchEvent(
                                  new CustomEvent(POINTS_POPOVER_EVENT, {
                                    detail: { scope: popoverScope },
                                  }),
                                );
                              }
                              return next;
                            });
                          }}
                          onClose={() => setOpenPointsId(null)}
                        />
                      )}
                    </span>
                  )}
                </span>
                <span className="matchday-side">
                  <OutcomeBreakdown match={match} teams={teams} />
                  <span className="matchday-stats">
                    <span>{match.prediction_count} voorspellingen</span>
                    <span>{match.quiz_answer_count} quiz</span>
                    <span>{match.leeuwtjes_count} Leeuwtjes</span>
                  </span>
                </span>
              </article>
            );
          })}
        </div>
      </article>
    </div>
  );
}

function MatchdayPredictionRow({
  prediction,
  match,
  teams,
  pointsOpen,
  onTogglePoints,
  onClosePoints,
}) {
  return (
    <li className="matchday-prediction-row">
      <div className="matchday-prediction-user">
        <ProfileAvatar player={prediction} size="small" />
        <span>
          <strong>{prediction.name}</strong>
          <em>
            {prediction.quiz_answer
              ? `Quiz: ${prediction.quiz_answer}`
              : "Geen quizantwoord"}
          </em>
        </span>
      </div>
      <strong className="matchday-prediction-score">
        <TeamLabel id={match.home_team_id} teams={teams} />{" "}
        {prediction.home_score} - {prediction.away_score}{" "}
        <TeamLabel id={match.away_team_id} teams={teams} />
      </strong>
      {prediction.points && (
        <PointsPopoverAnchor
          label={`${prediction.points.total_points ?? 0} pts`}
          points={prediction.points}
          open={pointsOpen}
          onToggle={onTogglePoints}
          onClose={onClosePoints}
        />
      )}
      {prediction.leeuwtje && (
        <b className="leeuwtje-mini" title="Leeuwtje ingezet">
          L
        </b>
      )}
    </li>
  );
}

function MatchdayMatchPage({ matchId, teams, venues, onBack }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openPointsId, setOpenPointsId] = useState(null);
  const popoverScope = useMemo(
    () => `match-analysis-${Math.random().toString(36).slice(2)}`,
    [],
  );

  useEffect(() => {
    function closeOtherPopover(event) {
      if (event.detail?.scope !== popoverScope) setOpenPointsId(null);
    }
    window.addEventListener(POINTS_POPOVER_EVENT, closeOtherPopover);
    return () => {
      window.removeEventListener(POINTS_POPOVER_EVENT, closeOtherPopover);
    };
  }, [popoverScope]);

  useEffect(() => {
    let cancelled = false;
    async function loadDetail() {
      setLoading(true);
      setError("");
      try {
        const result = await apiJson(`/api/matchday/matches/${matchId}`);
        if (!cancelled) setDetail(result);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    if (matchId) loadDetail();
    return () => {
      cancelled = true;
    };
  }, [matchId]);

  if (loading) {
    return <div className="loading compact">Loading match predictions...</div>;
  }

  if (error) {
    return (
      <div className="matchday-detail-layout">
        <button className="text-button" type="button" onClick={onBack}>
          Terug naar matchday
        </button>
        <div className="load-error">{error}</div>
      </div>
    );
  }

  const match = detail?.match;
  if (!match) {
    return (
      <div className="matchday-detail-layout">
        <button className="text-button" type="button" onClick={onBack}>
          Terug naar matchday
        </button>
        <div className="empty compact">Wedstrijd niet gevonden.</div>
      </div>
    );
  }

  const venue = venues.get(match.venue_id);
  const myPrediction = match.my_prediction;
  const hasMyPrediction = Boolean(myPrediction);
  return (
    <div className="matchday-detail-layout">
      <button className="text-button" type="button" onClick={onBack}>
        Terug naar matchday
      </button>
      <section className="matchday-detail-hero">
        <div className="matchday-detail-time">
          <span>{formatDate(match, true)}</span>
          <strong>{formatTime(match)}</strong>
          <em>{venue?.city ?? "Venue to confirm"}</em>
        </div>
        <div className="matchday-detail-teams">
          <TeamBadge id={match.home_team_id} teams={teams} />
          <span>vs</span>
          <TeamBadge id={match.away_team_id} teams={teams} align="right" />
        </div>
        <div className="matchday-detail-outcomes">
          <OutcomeBreakdown match={match} teams={teams} />
          <div className="matchday-score-summary is-detail">
            <span>
              <strong>Uitslag</strong>
              {match.home_score ?? "-"} - {match.away_score ?? "-"}
            </span>
            <span>
              <strong>Mijn voorspelling</strong>
              {hasMyPrediction
                ? `${myPrediction.home_score} - ${myPrediction.away_score}`
                : "-"}
            </span>
            {hasMyPrediction && match.my_points && (
              <PointsPopoverAnchor
                label={`Jij: ${match.my_points.total_points ?? 0} pts`}
                points={match.my_points}
                open={openPointsId === "viewer"}
                onToggle={() => {
                  setOpenPointsId((current) => {
                    const next = current === "viewer" ? null : "viewer";
                    if (next) {
                      window.dispatchEvent(
                        new CustomEvent(POINTS_POPOVER_EVENT, {
                          detail: { scope: popoverScope },
                        }),
                      );
                    }
                    return next;
                  });
                }}
                onClose={() => setOpenPointsId(null)}
              />
            )}
          </div>
          <div className="matchday-stats">
            <span>{match.prediction_count} voorspellingen</span>
            <span>{match.quiz_answer_count} quiz</span>
            <span>{match.leeuwtjes_count} Leeuwtjes</span>
          </div>
        </div>
      </section>

      {match.quiz && (
        <section className="matchday-quiz-question">
          <span>Quizvraag</span>
          <strong>{match.quiz.question}</strong>
        </section>
      )}

      <article className="panel">
        <div className="panel-header">
          <div>
            <h3>Voorspellingen</h3>
            <p>Scores, quizantwoorden en Leeuwtjes per speler.</p>
          </div>
          <span className="pill">{detail.predictions?.length ?? 0} spelers</span>
        </div>
        <div className="panel-body">
          {!detail.predictions?.length && (
            <div className="empty compact">Nog geen voorspellingen.</div>
          )}
          {!!detail.predictions?.length && (
            <ul className="matchday-prediction-table">
              {detail.predictions.map((prediction) => (
                <MatchdayPredictionRow
                  prediction={prediction}
                  match={match}
                  teams={teams}
                  pointsOpen={openPointsId === prediction.user_id}
                  onTogglePoints={() => {
                    setOpenPointsId((current) => {
                      const next =
                        current === prediction.user_id ? null : prediction.user_id;
                      if (next) {
                        window.dispatchEvent(
                          new CustomEvent(POINTS_POPOVER_EVENT, {
                            detail: { scope: popoverScope },
                          }),
                        );
                      }
                      return next;
                    });
                  }}
                  onClosePoints={() => setOpenPointsId(null)}
                  key={prediction.user_id}
                />
              ))}
            </ul>
          )}
        </div>
      </article>
    </div>
  );
}

function RankMovement({ movement = 0, showFlat = true }) {
  if (movement > 0) {
    return (
      <span
        className="rank-movement is-up"
        aria-label={`Moved up ${movement} ranks`}
      >
        ▲ {movement}
      </span>
    );
  }
  if (movement < 0) {
    return (
      <span
        className="rank-movement is-down"
        aria-label={`Moved down ${Math.abs(movement)} ranks`}
      >
        ▼ {Math.abs(movement)}
      </span>
    );
  }
  if (!showFlat) return null;
  return (
    <span className="rank-movement is-flat" aria-label="No rank movement">
      -
    </span>
  );
}

function TopScorerPickLabel({ picks }) {
  const names = (picks ?? []).map((pick) => pick.name ?? pick).filter(Boolean);
  if (!names.length) return <span className="muted">Not picked</span>;
  return (
    <span>
      {names.map((name, index) => `${index + 1}. ${name}`).join(" · ")}
    </span>
  );
}

function Leaderboard({
  pool,
  onProfile = () => { },
  profileLinksEnabled = true,
}) {
  return (
    <article className="panel">
      <div className="panel-header">
        <div>
          <h3>Leaderboard</h3>
          <p>Shows everyone who has joined the pool.</p>
        </div>
        <span className="pill green">{pool.leaderboard.length} players</span>
      </div>
      <div className="panel-body">
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
                <th className="numeric">Scorer pts</th>
                <th className="numeric">Leeuwtjes</th>
                <th className="numeric">Predictions</th>
              </tr>
            </thead>
            <tbody>
              {pool.leaderboard.map((row, index) => {
                return (
                  <tr key={row.user_id} className="leaderboard-row">
                    <td>{index + 1}</td>
                    <td>
                      {profileLinksEnabled ? (
                        <button
                          className="leaderboard-player-link"
                          type="button"
                          onClick={() => onProfile(row.user_id)}
                          aria-label={`Open ${row.name} profile`}
                        >
                          <ProfileAvatar player={row} size="small" />
                          <span className="leaderboard-name">
                            <span className="leaderboard-name-primary">
                              <strong>{row.name}</strong>
                              <RankMovement movement={row.rank_movement ?? 0} />
                            </span>
                            {row.full_name && (
                              <em>{row.full_name}</em>
                            )}
                          </span>
                        </button>
                      ) : (
                        <span className="leaderboard-player-link is-static">
                          <ProfileAvatar player={row} size="small" />
                          <span className="leaderboard-name">
                            <span className="leaderboard-name-primary">
                              <strong>{row.name}</strong>
                              <RankMovement movement={row.rank_movement ?? 0} />
                            </span>
                            {row.full_name && (
                              <em>{row.full_name}</em>
                            )}
                          </span>
                        </span>
                      )}
                    </td>
                    <td className="numeric">
                      <strong>{row.points}</strong>
                    </td>
                    <td className="numeric">{row.exact_scores}</td>
                    <td className="numeric">{row.outcomes}</td>
                    <td className="numeric">{row.quiz_points ?? 0}</td>
                    <td className="numeric">
                      {row.scorer_points ?? row.top_scorer_points ?? 0}
                    </td>
                    <td className="numeric">
                      {row.leeuwtjes_available ?? 0}/
                      {row.leeuwtjes_total ?? pool.progress?.leeuwtjes_total ?? 5}
                    </td>
                    <td className="numeric">
                      {row.group_stage_predictions}/{row.group_stage_total}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {!pool.leaderboard.length && (
          <div className="empty">
            No leaderboard entries yet. New accounts will appear here as soon
            as they join.
          </div>
        )}
      </div>
    </article>
  );
}

function WallOfShame({ rows = [], onProfile = () => { } }) {
  return (
    <article className="panel wall-of-shame-panel">
      <div className="panel-header">
        <div>
          <h3>Nog niet ingevuld</h3>
          <p>Open acties voor vandaag en morgen.</p>
        </div>
        <span className={rows.length ? "pill orange" : "pill green"}>
          {rows.length} spelers
        </span>
      </div>
      <div className="panel-body">
        {rows.length ? (
          <div className="wall-of-shame-list">
            {rows.map((row) => (
              <article className="wall-of-shame-row" key={row.user_id}>
                <button
                  className="leaderboard-player-link"
                  type="button"
                  onClick={() => onProfile(row.user_id)}
                >
                  <ProfileAvatar player={row} size="small" />
                  <span className="leaderboard-name">
                    <strong>{row.name}</strong>
                    {row.full_name && <em>{row.full_name}</em>}
                  </span>
                </button>
                <div className="wall-of-shame-items">
                  <strong>{row.missing_count} open</strong>
                  {(row.missing_items ?? []).slice(0, 4).map((item) => (
                    <span key={`${item.kind}-${item.match_id}`}>
                      {item.label} ·{" "}
                      {item.title ??
                        (item.kind === "quiz" ? "quiz" : "prediction")}
                    </span>
                  ))}
                  {(row.missing_items ?? []).length > 4 && (
                    <span>+{row.missing_items.length - 4} meer</span>
                  )}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty compact">
            Iedereen is bij voor de open wedstrijden van vandaag en morgen.
          </div>
        )}
      </div>
    </article>
  );
}

function ProfilePredictionRow({
  prediction,
  teams,
  pointsOpen,
  onTogglePoints,
  onClosePoints,
}) {
  const hasResult =
    prediction.completed &&
    prediction.actual_home_score != null &&
    prediction.actual_away_score != null;

  const scheduleState = hasResult ? "completed" : "upcoming";
  const statusLabel = hasResult ? "Played" : "Prediction";

  return (
    <article className={`profile-prediction-row match-card is-${scheduleState}`}>
      <div className="match-time">{formatTime(prediction)}</div>
      <div>
        <div className="match-teams">
          <TeamLabel id={prediction.home_team_id} teams={teams} />{" "}
          <span className="muted">vs</span>{" "}
          <TeamLabel id={prediction.away_team_id} teams={teams} />
          <span className="schedule-prediction-chip has-score">
            {prediction.home_score} - {prediction.away_score}
          </span>
        </div>
        <div className="match-meta">{formatDate(prediction, true)}</div>
        {prediction.quiz_answer && (
          <div className="match-quiz-line">Quiz: {prediction.quiz_answer}</div>
        )}
        {prediction.leeuwtje && (
          <div className="match-quiz-line">Leeuwtje ingezet</div>
        )}
        {hasResult && (
          <div className="match-result-line">
            <span>
              Final score: {prediction.actual_home_score} -{" "}
              {prediction.actual_away_score}
            </span>
            {prediction.points && (
              <PointsPopoverAnchor
                label={`Points: ${prediction.points.total_points ?? 0}`}
                points={prediction.points}
                open={pointsOpen}
                onToggle={onTogglePoints}
                onClose={onClosePoints}
              />
            )}
          </div>
        )}
      </div>
      <div className="match-actions">
        <span className={`match-status-pill is-${scheduleState}`}>
          {statusLabel}
        </span>
      </div>
    </article>
  );
}

function PlayerPredictions({ player, canView, teams }) {
  const [predictionGroups, setPredictionGroups] = useState([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [limited, setLimited] = useState(false);
  const [openPointsId, setOpenPointsId] = useState(null);
  const popoverScope = useMemo(
    () => `profile-${Math.random().toString(36).slice(2)}`,
    [],
  );

  useEffect(() => {
    function closeOtherPopover(event) {
      if (event.detail?.scope !== popoverScope) setOpenPointsId(null);
    }
    window.addEventListener(POINTS_POPOVER_EVENT, closeOtherPopover);
    return () => {
      window.removeEventListener(POINTS_POPOVER_EVENT, closeOtherPopover);
    };
  }, [popoverScope]);

  useEffect(() => {
    let cancelled = false;
    setPredictionGroups([]);
    setError("");
    setLoaded(false);
    setLimited(false);
    setOpenPointsId(null);

    if (!player || !canView) {
      setLoaded(true);
      return () => {
        cancelled = true;
      };
    }

    async function loadPredictions() {
      try {
        const result = await apiJson(
          `/api/profiles/${player.user_id}/predictions`,
        );
        if (!cancelled) {
          setPredictionGroups(scheduleGroupedPredictions(result.groups ?? []));
          setLimited(
            Boolean(
              result.limited_to_locked_matches ??
              result.limited_to_completed_matches,
            ),
          );
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
          <p>
            {limited
              ? "Andere spelers tonen alleen wedstrijden die al gesloten zijn."
              : "In dezelfde volgorde als het wedstrijdschema."}
          </p>
        </div>
      </div>
      <div className="panel-body profile-prediction-body">
        {!canView && (
          <div className="empty compact">Predictions are not available.</div>
        )}
        {canView && !loaded && (
          <div className="empty compact">Loading predictions...</div>
        )}
        {canView && error && <div className="form-error">{error}</div>}
        {canView && loaded && !error && !predictionGroups.length && (
          <div className="empty compact">
            {limited
              ? "Nog geen gesloten wedstrijdvoorspellingen zichtbaar."
              : "No predictions filled in yet."}
          </div>
        )}
        {canView &&
          predictionGroups.map((group) => (
            <section className="profile-prediction-group" key={group.group}>
              <h4>{formatDate(group.predictions[0])}</h4>
              <div className="profile-prediction-list">
                {group.predictions.map((prediction) => (
                  <ProfilePredictionRow
                    key={prediction.match_id}
                    prediction={prediction}
                    teams={teams}
                    pointsOpen={openPointsId === prediction.match_id}
                    onTogglePoints={() => {
                      setOpenPointsId((current) =>
                        current === prediction.match_id ? null : prediction.match_id,
                      );
                      if (openPointsId !== prediction.match_id) {
                        window.dispatchEvent(
                          new CustomEvent(POINTS_POPOVER_EVENT, {
                            detail: { scope: popoverScope },
                          }),
                        );
                      }
                    }}
                    onClosePoints={() => setOpenPointsId(null)}
                  />
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
  isSelf,
  viewerIsAdmin,
  viewerPrizePot,
  badgeCatalog,
  data,
  rules,
  tournamentPicksVisible,
  onUpdateName,
  onUpdateImage,
  onJoinPrizePot,
  onAdmin,
}) {
  const playerOptions = useMemo(() => topScorerOptions(data), [data]);
  const [prizePotBusy, setPrizePotBusy] = useState(false);
  const [prizePotError, setPrizePotError] = useState("");

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
    {
      label: "Scorers",
      value: player.scorer_points ?? player.top_scorer_points ?? 0,
      detail: "Top scorer + strikers",
    },
    { label: "Shooting", value: player.shooting, detail: "Winner goals" },
    { label: "Defence", value: player.defence, detail: "Loser goals" },
  ];
  const canViewPredictions = true;
  const canViewTournamentPicks = isSelf || tournamentPicksVisible;
  const rankLabel = rank ? `Rank #${rank}` : "Nog niet gerankt";
  const teams = new Map((data?.teams ?? []).map((team) => [team.id, team]));
  const prizePotLabel =
    player.prize_pot_status === "joined"
      ? "Doet mee aan de prijspot"
      : player.prize_pot_status === "declined"
        ? "Doet niet mee aan de prijspot"
        : "Prijspot nog niet gekozen";
  const joinedPrizePotCount = viewerPrizePot?.participant_count;
  const canSeePrizePotStatus = isSelf || viewerIsAdmin;

  async function joinPrizePot() {
    setPrizePotBusy(true);
    setPrizePotError("");
    try {
      await onJoinPrizePot?.();
    } catch (err) {
      setPrizePotError(err.message);
    } finally {
      setPrizePotBusy(false);
    }
  }

  function pickClassName(impossible) {
    return impossible ? "profile-pick-row is-impossible" : "profile-pick-row";
  }

  function pointsLabel(value) {
    return `${value ?? 0} pts`;
  }

  return (
    <div className="profile-page">
      <div className="profile-top-layout">
        <article className="fifa-card">
          <div className="fifa-card-top">
            <div>
              <span className="fifa-rating">{player.points}</span>
              <span className="fifa-position">PTS</span>
              <span className="fifa-rank">{rankLabel}</span>
            </div>
            <ProfileImageEditor
              player={player}
              canEdit={isSelf}
              onUpdateImage={onUpdateImage}
            />
          </div>
          <div className="fifa-card-name">
            <ProfileNameEditor
              player={player}
              canEdit={isSelf}
              onUpdateName={onUpdateName}
            />
            {player.email && (
              <span className="profile-email">{player.email}</span>
            )}
            {canSeePrizePotStatus && (
              <span className={`profile-prize-pot ${player.prize_pot_status ?? "undecided"}`}>
                {prizePotLabel}
              </span>
            )}
            {isSelf && player.prize_pot_status === "joined" && Number.isFinite(joinedPrizePotCount) && (
              <span className="profile-prize-pot-count">
                {joinedPrizePotCount} people are in the prize pot.
              </span>
            )}
            {isSelf && player.prize_pot_status !== "joined" && (
              <button
                className="text-button profile-prize-pot-join"
                type="button"
                disabled={prizePotBusy}
                onClick={joinPrizePot}
              >
                {prizePotBusy ? "Joining..." : "Join prize pot"}
              </button>
            )}
            {prizePotError && <span className="form-error compact">{prizePotError}</span>}
            {viewerIsAdmin && player.is_admin && (
              <button className="text-button profile-admin-link" type="button" onClick={onAdmin}>
                Admin
              </button>
            )}
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
        <article className="profile-picks-panel">
          <div className="profile-picks-header">
            <h3>Toernooi picks</h3>
            <span>
              {canViewTournamentPicks
                ? pointsLabel(
                  (player.winner_points ?? 0) + (player.scorer_points ?? 0),
                )
                : "Geheim"}
            </span>
          </div>
          {!canViewTournamentPicks ? (
            <div className="profile-pick-row is-private">
              <div>
                <strong>Geheim tot de deadline</strong>
                <span>
                  Deze toernooi picks worden zichtbaar 1 uur voor de eerste
                  wedstrijd.
                </span>
              </div>
            </div>
          ) : (
            <>
              <div className={pickClassName(player.winner_impossible)}>
                <div>
                  <strong>WK winnaar</strong>
                  <span className="winner-team-title">
                    {player.winner_pick ? (
                      <>
                        <TeamFlag id={player.winner_pick} />{" "}
                        {teams.get(player.winner_pick)?.name ??
                          player.winner_pick_name ??
                          "Niet gekozen"}
                      </>
                    ) : (
                      "Niet gekozen"
                    )}
                  </span>
                </div>
                <b>{pointsLabel(player.winner_points)}</b>
              </div>
              <div className={pickClassName(player.top_scorer_impossible)}>
                <div>
                  <strong>Topscorer</strong>
                  <PlayerPickDisplay
                    pick={player.top_scorer_pick}
                    options={playerOptions}
                  />
                </div>
                <b>{pointsLabel(player.top_scorer_points)}</b>
              </div>
              <div className="profile-pick-section-title">
                <strong>Spitsen totaal</strong>
                <b>{pointsLabel(player.striker_points)}</b>
              </div>
              <div className="profile-striker-list">
                {(player.striker_picks ?? []).map((pick, index) => (
                  <div
                    className="profile-pick-row"
                    key={`${pick.name}-${index}`}
                  >
                    <div>
                      <strong>{`Spits ${index + 1}`}</strong>
                      <PlayerPickDisplay pick={pick.name} options={playerOptions} />
                    </div>
                    <b>{pointsLabel(pick.points)}</b>
                  </div>
                ))}
                {!(player.striker_picks ?? []).length && (
                  <div className="profile-pick-row">
                    <div>
                      <strong>Spitsen</strong>
                      <span>Niet gekozen</span>
                    </div>
                    <b>{pointsLabel(0)}</b>
                  </div>
                )}
              </div>
            </>
          )}
        </article>
      </div>
      <div className="profile-help-row">
        <LeeuwtjesHelpToggle used={player.leeuwtjes_used ?? 0} total={5} />
        <PointsHelpToggle rules={rules} />
      </div>
      <BadgeProgressSection
        player={player}
        badgeCatalog={badgeCatalog}
        canView
      />
      <PlayerPredictions
        player={player}
        canView={canViewPredictions}
        teams={teams}
      />
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

function LeeuwtjesInfo({ used = null, total = 5 }) {
  return (
    <div className="leeuwtjes-info">
      <div className="leeuwtjes-mark" aria-hidden="true">
        2x
      </div>
      <div>
        <strong>Leeuwtjes</strong>
        <p>
          Je hebt {total} Leeuwtjes. Zet er eentje op een wedstrijd voor de lock
          en je scorepunten voor die wedstrijd tellen dubbel. Quizpunten en
          groepsstandpunten tellen niet dubbel.
        </p>
        {used !== null && (
          <span>
            {used}/{total} Leeuwtjes gebruikt
          </span>
        )}
      </div>
    </div>
  );
}

function LeeuwtjesHelpToggle({ used = 0, total = 5 }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="profile-help">
      <button
        className="text-button"
        type="button"
        onClick={() => setOpen((current) => !current)}
      >
        {open ? "Leeuwtjes uitleg verbergen" : "Leeuwtjes uitleg"}
      </button>
      {open && <LeeuwtjesInfo used={used} total={total} />}
    </section>
  );
}

function PointsInfo({ rules }) {
  const groupRule = rules?.match_scores?.["Group Stage"] ?? {};
  const finalRule = rules?.match_scores?.["Final"] ?? {};
  const strikerRule = rules?.world_cup_strikers ?? {};
  const groupOutcome = groupRule.outcome ?? 6;
  const groupHomeGoals = groupRule.home_goals ?? 2;
  const groupAwayGoals = groupRule.away_goals ?? 2;
  const groupExactBonus = groupRule.exact_bonus ?? 2;
  const groupExact = groupRule.exact ?? 12;
  const finalExact = finalRule.exact ?? 48;
  const strikerGoal = strikerRule.points_per_goal ?? 6;

  return (
    <div className="leeuwtjes-info points-info">
      <div className="leeuwtjes-mark" aria-hidden="true">
        P
      </div>
      <div>
        <strong>Punten</strong>
        <p>
          In de poulefase krijg je {groupOutcome} punten voor de juiste
          winnaar/gelijkspel, {groupHomeGoals} voor het juiste aantal
          thuisgoals, {groupAwayGoals} voor het juiste aantal uitgoals en{" "}
          {groupExactBonus} extra voor exact. Exact is dus {groupExact} punten
          en telt ook als juiste outcome.
        </p>
        <p>
          Knock-outwedstrijden gebruiken dezelfde onderdelen met een multiplier,
          tot {finalExact} punten voor een exacte finale. Quizantwoorden hebben
          per vraag eigen punten op basis van kans. Spitsen leveren {strikerGoal}{" "}
          basispunten per goal, ook met de ronde-multiplier.
        </p>
      </div>
    </div>
  );
}

function PointsHelpToggle({ rules }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="profile-help">
      <button
        className="text-button"
        type="button"
        onClick={() => setOpen((current) => !current)}
      >
        {open ? "Punten uitleg verbergen" : "Punten uitleg"}
      </button>
      {open && <PointsInfo rules={rules} />}
    </section>
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
            This is the Talpa WK Pool for the 2026 World Cup. Check the
            leaderboard to see who is in, then add predictions whenever you are
            ready. Your account is already part of the pool.
          </p>
          <LeeuwtjesInfo />
          <OnboardingActions nextLabel="View leaderboard" onNext={onNext} />
        </div>
      </article>
    </div>
  );
}

function LeaderboardPreviewStep({ pool, onBack, onNext }) {
  return (
    <div className="onboarding-layout">
      <Leaderboard pool={pool} profileLinksEnabled={false} />
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
            <p>Your account already has a spot on the leaderboard.</p>
          </div>
          <span className="pill orange">Step 2</span>
        </div>
        <div className="panel-body">
          <p className="onboarding-message">
            Your predictions can be adjusted later until each match locks one
            hour before kickoff. Start with any group now, or continue and come
            back when you are ready.
          </p>
          <OnboardingActions
            nextLabel="Start predictions"
            onBack={onBack}
            onNext={onNext}
          />
        </div>
      </article>
    </div>
  );
}

function PredictionPanel({
  data,
  teams,
  venues,
  pool,
  onPoolUpdate,
  onContinue,
  onBack,
}) {
  const groupMatches = useMemo(
    () =>
      data.matches
        .filter((match) => match.round === "Group Stage")
        .sort((a, b) => escapeDate(a) - escapeDate(b)),
    [data],
  );
  const matchesByGroup = useMemo(() => {
    const groups = new Map(data.groups.map((group) => [group.id, []]));
    for (const match of groupMatches) {
      groups.get(match.group)?.push(match);
    }
    return groups;
  }, [data.groups, groupMatches]);
  const requiredGroup =
    data.groups.find((group) => group.teams.includes(NETHERLANDS_ID)) ??
    data.groups[0];
  const requiredGroupId = requiredGroup?.id ?? "";
  const initialGroupId = requiredGroupId || data.groups[0]?.id || "";
  const [draft, setDraft] = useState({});
  const [quizDraft, setQuizDraft] = useState({});
  const [leeuwtjeMatchIds, setLeeuwtjeMatchIds] = useState(
    () => new Set(poolLeeuwtjeMatchIds(pool)),
  );
  const [selectedGroupId, setSelectedGroupId] = useState(initialGroupId);
  const [editingMatchId, setEditingMatchId] = useState("");
  const [winner, setWinner] = useState(pool.winner_pick ?? "");
  const [winnerDirty, setWinnerDirty] = useState(false);
  const [topScorer, setTopScorer] = useState(() => topScorerPickFromPool(pool));
  const [strikers, setStrikers] = useState(() => strikerPicksFromPool(pool));
  const [tournamentPicksDirty, setTournamentPicksDirty] = useState(false);
  const [tournamentPicksEditing, setTournamentPicksEditing] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const selectedGroup = data.groups.find(
    (group) => group.id === selectedGroupId,
  );
  const selectedMatches = selectedGroupId
    ? (matchesByGroup.get(selectedGroupId) ?? [])
    : [];
  const winnerTeam = winner ? teams.get(winner) : null;
  const lockedWinner = winnerLocked(pool);
  const topScorerSuggestions = useMemo(() => topScorerOptions(data), [data]);
  const leeuwtjeTotal = leeuwtjesTotal(pool);
  const leeuwtjeUsedCount = leeuwtjeMatchIds.size;
  const leeuwtjesRemaining = Math.max(0, leeuwtjeTotal - leeuwtjeUsedCount);

  useEffect(() => {
    const nextDraft = {};
    const nextQuizDraft = {};
    const predictions = poolPredictions(pool);
    const quizPredictions = poolQuizPredictions(pool);
    for (const match of groupMatches) {
      const prediction = predictions[match.id];
      nextDraft[match.id] = {
        home_score: prediction?.home_score ?? "",
        away_score: prediction?.away_score ?? "",
      };
      const quizPrediction = quizPredictions[match.id];
      nextQuizDraft[match.id] = {
        answer: quizPrediction?.answer ?? "",
      };
    }
    setDraft(nextDraft);
    setQuizDraft(nextQuizDraft);
    setLeeuwtjeMatchIds(new Set(poolLeeuwtjeMatchIds(pool)));
    setSelectedGroupId((current) => current || initialGroupId);
  }, [pool, groupMatches, initialGroupId]);

  useEffect(() => {
    if (!winnerDirty) setWinner(pool.winner_pick ?? "");
  }, [pool.winner_pick, winnerDirty]);

  useEffect(() => {
    if (!tournamentPicksDirty) {
      setTopScorer(topScorerPickFromPool(pool));
      setStrikers(strikerPicksFromPool(pool));
    }
  }, [
    pool.top_scorer_pick,
    pool.striker_picks,
    pool.top_scorer_picks,
    tournamentPicksDirty,
  ]);

  useEffect(() => {
    if (lockedWinner) setTournamentPicksEditing(false);
  }, [lockedWinner]);

  function hasPrediction(match) {
    return scoreComplete(draft[match.id]);
  }

  function groupPredictionCount(groupId) {
    return (matchesByGroup.get(groupId) ?? []).filter(hasPrediction).length;
  }

  const predictedMatchCount = groupMatches.filter(hasPrediction).length;
  const quizPredictedCount = groupMatches.filter((match) =>
    quizAnswerComplete(match.quiz, quizDraft[match.id]),
  ).length;
  const requiredMatches = requiredGroupId
    ? (matchesByGroup.get(requiredGroupId) ?? [])
    : groupMatches;
  const requiredPredictedCount = requiredMatches.filter(hasPrediction).length;
  const requiredPredictionsComplete = Boolean(
    requiredMatches.length && requiredPredictedCount >= requiredMatches.length,
  );
  const missingRequiredCount = Math.max(
    0,
    requiredMatches.length - requiredPredictedCount,
  );
  const selectedGroupPredictionCount = selectedGroup
    ? groupPredictionCount(selectedGroup.id)
    : 0;
  const progressPercent = groupMatches.length
    ? Math.round((predictedMatchCount / groupMatches.length) * 100)
    : 0;
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

  function chooseTopScorer(value) {
    setTopScorer(value);
    setTournamentPicksDirty(true);
    setError("");
  }

  function chooseStriker(index, value) {
    setStrikers((current) =>
      current.map((pick, pickIndex) => (pickIndex === index ? value : pick)),
    );
    setTournamentPicksDirty(true);
    setError("");
  }

  async function save(closeEditor = false, options = {}) {
    setSaving(true);
    setError("");
    const predictions = draftPredictions(draft);
    const body = {
      predictions,
      quiz_predictions: draftQuizPredictions(quizDraft, poolQuizPredictions(pool)),
      leeuwtjes_match_ids: [...leeuwtjeMatchIds],
      winner_team_id: winner || null,
      top_scorer_name: topScorer || null,
      striker_names: strikers,
    };
    if (Object.hasOwn(options, "winnerTeamId")) {
      body.winner_team_id = options.winnerTeamId || null;
    }
    if (Object.hasOwn(options, "topScorerName")) {
      body.top_scorer_name = options.topScorerName || null;
    }
    if (Object.hasOwn(options, "strikerNames")) {
      body.striker_names = options.strikerNames;
    }

    try {
      const updated = await apiJson("/api/predictions", {
        method: "POST",
        body: JSON.stringify(body),
      });
      onPoolUpdate(updated);
      setWinnerDirty(false);
      setTournamentPicksDirty(false);
      setTournamentPicksEditing(false);
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
    const updated = await save(true, {
      winnerTeamId: winner,
      topScorerName: topScorer,
      strikerNames: strikers,
    });
    if (updated) onContinue(updated);
  }

  return (
    <div className="pool-layout">
      <article className="panel prediction-guide">
        <div className="panel-header">
          <div>
            <h3>
              {selectedGroup
                ? `Group ${selectedGroup.id}: make predictions`
                : "Make predictions"}
            </h3>
            <p>
              Work through the schedule and watch your predicted table update.
            </p>
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
          <section
            className={
              winnerTeam
                ? "winner-spotlight-card has-winner"
                : "winner-spotlight-card"
            }
            aria-label="Tournament picks"
          >
            <div className="winner-trophy" aria-hidden="true">
              <img src={TROPHY_SRC} alt="" />
            </div>
            <div className="winner-spotlight-copy">
              <span className="game-kicker">Tournament picks</span>
              <h4>
                {winnerTeam ? (
                  <span className="winner-team-title">
                    <TeamFlag id={winnerTeam.id} /> {winnerTeam.name}
                  </span>
                ) : (
                  "Pick your champion"
                )}
              </h4>
              <p>
                Add your champion, final top scorer and five strikers before the
                tournament starts.
              </p>
            </div>
            {tournamentPicksEditing ? (
              <div className="tournament-pick-controls">
                <label className="winner-select winner-select-inline">
                  Kampioen
                  <select
                    value={winner}
                    onChange={(event) => chooseWinner(event.target.value)}
                    disabled={lockedWinner}
                  >
                    <option value="">Kies kampioen</option>
                    {data.teams
                      .slice()
                      .sort((a, b) => a.name.localeCompare(b.name))
                      .map((team) => (
                        <option key={team.id} value={team.id}>
                          {teamOptionLabel(team)}
                        </option>
                      ))}
                  </select>
                </label>
                <PlayerSearchSelect
                  label="Topscorer"
                  value={topScorer}
                  options={topScorerSuggestions}
                  locked={lockedWinner}
                  onChange={chooseTopScorer}
                  idPrefix="top-scorer"
                />
                <PlayerPickSelects
                  label="Spits"
                  picks={strikers}
                  options={topScorerSuggestions}
                  locked={lockedWinner}
                  onChange={chooseStriker}
                  idPrefix="striker"
                />
              </div>
            ) : (
              <TournamentPickSummary
                winnerTeam={winnerTeam}
                topScorer={topScorer}
                strikers={strikers}
                options={topScorerSuggestions}
                locked={lockedWinner}
                editing={tournamentPicksEditing}
                onEdit={() => setTournamentPicksEditing(true)}
              />
            )}
          </section>

          <section
            className="prediction-game-card"
            aria-label="Prediction progress"
          >
            <div>
              <span className="game-kicker">Total prediction progress</span>
              <h4>
                {predictedMatchCount} of {groupMatches.length} group fixtures
                predicted
              </h4>
              <p>
                {quizPredictedCount} quizvragen ingevuld · {leeuwtjeUsedCount}/
                {leeuwtjeTotal} Leeuwtjes ingezet.
              </p>
            </div>
            <div className="game-score">
              <strong>{progressPercent}%</strong>
              <span>complete</span>
            </div>
            <div className="prediction-progress-track" aria-hidden="true">
              <span style={{ width: `${progressPercent}%` }} />
            </div>
          </section>

          <div
            className="prediction-group-switcher"
            aria-label="Prediction groups"
          >
            {data.groups.map((group) => {
              const total = matchesByGroup.get(group.id)?.length ?? 0;
              const predicted = groupPredictionCount(group.id);
              return (
                <button
                  className={
                    group.id === selectedGroupId
                      ? "group-switch is-active"
                      : "group-switch"
                  }
                  key={group.id}
                  type="button"
                  onClick={() => chooseGroup(group.id)}
                >
                  <span className="group-mini-flags">
                    {group.teams.map((teamId) => (
                      <TeamFlag key={teamId} id={teamId} />
                    ))}
                  </span>
                  <strong>Group {group.id}</strong>
                  <em>
                    {predicted}/{total}
                  </em>
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
                    <p>
                      Type scores directly in each match row, then save once
                      below.
                    </p>
                  </div>
                </div>

                <div
                  className="prediction-fixture-list"
                  aria-label={`Group ${selectedGroup.id} schedule`}
                >
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
                        canToggleLeeuwtje={
                          leeuwtjeMatchIds.has(match.id) ||
                          leeuwtjeMatchIds.size < leeuwtjeTotal
                        }
                        leeuwtjesRemaining={leeuwtjesRemaining}
                        onScore={setScore}
                        onQuizAnswer={setQuizAnswer}
                        onToggleLeeuwtje={() => toggleLeeuwtje(match.id)}
                        onSubmit={() => save(true)}
                        compact
                        quickEntry
                      />
                    );
                  })}
                </div>

                <div className="prediction-actions">
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() => save(true)}
                    disabled={saving}
                  >
                    {saving ? "Saving..." : "Save progress"}
                  </button>
                  {error && <span className="form-error">{error}</span>}
                </div>
              </section>
            </div>
          )}

          <article
            className={
              requiredPredictionsComplete
                ? "prediction-continue-card is-ready"
                : "prediction-continue-card"
            }
          >
            <div>
              <h4>
                {requiredPredictionsComplete
                  ? "Ready for the leaderboard"
                  : "You are already on the leaderboard"}
              </h4>
              <p>
                {requiredPredictionsComplete &&
                  winner &&
                  topScorer &&
                  strikers.filter(Boolean).length >= 5 &&
                  allPredictionsComplete
                  ? "Full card, champion, top scorer and strikers set. Time to check the leaderboard."
                  : requiredPredictionsComplete &&
                    winner &&
                    topScorer &&
                    strikers.filter(Boolean).length >= 5
                    ? "Your prediction card still has some empty spots. No prediction, no points — the scoreboard is strict like that."
                    : requiredPredictionsComplete
                      ? "You can pick your champion, top scorer and strikers above now or continue to the leaderboard."
                      : requiredPredictedCount === 0
                        ? "You can continue now with an empty card, or save predictions here first."
                        : `${missingRequiredCount} Netherlands group score prediction${missingRequiredCount === 1 ? "" : "s"} still open. You can continue now and finish them later.`}
              </p>
            </div>
            <button
              className="primary-button"
              type="button"
              onClick={continueToLeaderboard}
              disabled={saving}
            >
              {saving ? "Saving..." : "Continue"}
            </button>
          </article>
        </div>
      </article>
    </div>
  );
}

function AdjustPredictionsPanel({
  data,
  teams,
  venues,
  pool,
  onPoolUpdate,
  onBack,
  focusTarget,
}) {
  const groupMatches = useMemo(
    () =>
      data.matches
        .filter((match) => match.round === "Group Stage")
        .sort((a, b) => escapeDate(a) - escapeDate(b)),
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
  const [leeuwtjeMatchIds, setLeeuwtjeMatchIds] = useState(
    () => new Set(poolLeeuwtjeMatchIds(pool)),
  );
  const [selectedGroupId, setSelectedGroupId] = useState(
    data.groups[0]?.id ?? "",
  );
  const [editingMatchId, setEditingMatchId] = useState("");
  const [winner, setWinner] = useState(pool.winner_pick ?? "");
  const [topScorer, setTopScorer] = useState(() => topScorerPickFromPool(pool));
  const [strikers, setStrikers] = useState(() => strikerPicksFromPool(pool));
  const [tournamentPicksEditing, setTournamentPicksEditing] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [pendingScoreMatchId, setPendingScoreMatchId] = useState("");
  const editVersionRef = useRef(0);
  const saveSequenceRef = useRef(0);
  const focusedMatchId = focusTarget?.match_id ?? "";

  function markDirty() {
    editVersionRef.current += 1;
    setDirty(true);
  }

  const selectedGroup = data.groups.find(
    (group) => group.id === selectedGroupId,
  );
  const selectedMatches = selectedGroupId
    ? (matchesByGroup.get(selectedGroupId) ?? [])
    : [];
  const lockedWinner = winnerLocked(pool);
  const winnerTeam = winner ? teams.get(winner) : null;
  const topScorerSuggestions = useMemo(() => topScorerOptions(data), [data]);
  const leeuwtjeTotal = leeuwtjesTotal(pool);
  const leeuwtjesRemaining = Math.max(0, leeuwtjeTotal - leeuwtjeMatchIds.size);

  useEffect(() => {
    if (lockedWinner) setTournamentPicksEditing(false);
  }, [lockedWinner]);

  useEffect(() => {
    if (!focusedMatchId) return;
    const match = groupMatches.find((candidate) => candidate.id === focusedMatchId);
    if (!match?.group) return;
    setSelectedGroupId(match.group);
    setEditingMatchId(match.id);
  }, [focusedMatchId, groupMatches]);

  useEffect(() => {
    if (initialized) return;
    const nextDraft = {};
    const nextQuizDraft = {};
    const predictions = poolPredictions(pool);
    const quizPredictions = poolQuizPredictions(pool);
    for (const match of groupMatches) {
      const prediction = predictions[match.id];
      nextDraft[match.id] = {
        home_score: prediction?.home_score ?? "",
        away_score: prediction?.away_score ?? "",
      };
      const quizPrediction = quizPredictions[match.id];
      nextQuizDraft[match.id] = {
        answer: quizPrediction?.answer ?? "",
      };
    }
    setDraft(nextDraft);
    setQuizDraft(nextQuizDraft);
    setLeeuwtjeMatchIds(new Set(poolLeeuwtjeMatchIds(pool)));
    setWinner(pool.winner_pick ?? "");
    setTopScorer(topScorerPickFromPool(pool));
    setStrikers(strikerPicksFromPool(pool));
    setInitialized(true);
    setDirty(false);
    setPendingScoreMatchId("");
  }, [pool, groupMatches, initialized]);

  function setScore(matchId, key, value) {
    setDraft((current) => ({
      ...current,
      [matchId]: { ...current[matchId], [key]: value },
    }));
    setPendingScoreMatchId(matchId);
    markDirty();
  }

  function chooseWinner(value) {
    setWinner(value);
    markDirty();
  }

  function chooseTopScorer(value) {
    setTopScorer(value);
    markDirty();
  }

  function chooseStriker(index, value) {
    setStrikers((current) =>
      current.map((pick, pickIndex) => (pickIndex === index ? value : pick)),
    );
    markDirty();
  }

  function setQuizAnswer(matchId, value) {
    setQuizDraft((current) => ({
      ...current,
      [matchId]: { ...current[matchId], answer: value },
    }));
    markDirty();
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
    markDirty();
  }

  function hasPrediction(match) {
    return scoreComplete(draft[match.id]);
  }

  function groupPredictionCount(groupId) {
    return (matchesByGroup.get(groupId) ?? []).filter(hasPrediction).length;
  }

  async function save(closeEditor = false) {
    const saveVersion = editVersionRef.current;
    const saveSequence = saveSequenceRef.current + 1;
    saveSequenceRef.current = saveSequence;
    setSaving(true);
    setError("");
    try {
      const updated = await apiJson("/api/predictions", {
        method: "POST",
        body: JSON.stringify({
          predictions: draftPredictions(draft),
          quiz_predictions: draftQuizPredictions(
            quizDraft,
            poolQuizPredictions(pool),
          ),
          leeuwtjes_match_ids: [...leeuwtjeMatchIds],
          winner_team_id: winner || null,
          top_scorer_name: topScorer || null,
          striker_names: strikers,
        }),
      });
      if (saveVersion !== editVersionRef.current) {
        return null;
      }
      setDirty(false);
      setPendingScoreMatchId("");
      setTournamentPicksEditing(false);
      onPoolUpdate(updated);
      if (closeEditor) setEditingMatchId("");
      return updated;
    } catch (err) {
      if (saveVersion !== editVersionRef.current) {
        return null;
      }
      setError(err.message);
      return null;
    } finally {
      if (saveSequence === saveSequenceRef.current) {
        setSaving(false);
      }
    }
  }

  useEffect(() => {
    if (!initialized || !dirty) return undefined;
    if (pendingScoreMatchId && !scoreComplete(draft[pendingScoreMatchId])) {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      save();
    }, 700);
    return () => window.clearTimeout(timer);
  }, [
    draft,
    quizDraft,
    leeuwtjeMatchIds,
    winner,
    topScorer,
    strikers,
    initialized,
    dirty,
    pendingScoreMatchId,
  ]);

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
            <p>Change scores and tournament picks until each lock moment.</p>
          </div>
          <div className="panel-header-actions">
            {onBack && (
              <button className="text-button" type="button" onClick={onBack}>
                Back home
              </button>
            )}
            <button
              className="primary-button"
              type="button"
              onClick={saveAndGoHome}
              disabled={saving}
            >
              {saving ? "Saving..." : "Save & back"}
            </button>
          </div>
        </div>
        <div className="panel-body">
          <section
            className={
              winnerTeam
                ? "winner-spotlight-card has-winner"
                : "winner-spotlight-card"
            }
            aria-label="Tournament picks"
          >
            <div className="winner-trophy" aria-hidden="true">
              <img src={TROPHY_SRC} alt="" />
            </div>
            <div className="winner-spotlight-copy">
              <span className="game-kicker">Tournament picks</span>
              <h4>
                {winnerTeam ? (
                  <span className="winner-team-title">
                    <TeamFlag id={winnerTeam.id} /> {winnerTeam.name}
                  </span>
                ) : (
                  "Pick your champion"
                )}
              </h4>
              <p>
                Champion, top scorer and striker picks are editable until one
                hour before the tournament opener.
              </p>
            </div>
            {tournamentPicksEditing ? (
              <div className="tournament-pick-controls">
                <label className="winner-select winner-select-inline">
                  Kampioen
                  <select
                    value={winner}
                    onChange={(event) => chooseWinner(event.target.value)}
                    disabled={lockedWinner}
                  >
                    <option value="">Kies kampioen</option>
                    {data.teams
                      .slice()
                      .sort((a, b) => a.name.localeCompare(b.name))
                      .map((team) => (
                        <option key={team.id} value={team.id}>
                          {teamOptionLabel(team)}
                        </option>
                      ))}
                  </select>
                </label>
                <PlayerSearchSelect
                  label="Topscorer"
                  value={topScorer}
                  options={topScorerSuggestions}
                  locked={lockedWinner}
                  onChange={chooseTopScorer}
                  idPrefix="adjust-top-scorer"
                />
                <PlayerPickSelects
                  label="Spits"
                  picks={strikers}
                  options={topScorerSuggestions}
                  locked={lockedWinner}
                  onChange={chooseStriker}
                  idPrefix="adjust-striker"
                />
              </div>
            ) : (
              <TournamentPickSummary
                winnerTeam={winnerTeam}
                topScorer={topScorer}
                strikers={strikers}
                options={topScorerSuggestions}
                locked={lockedWinner}
                editing={tournamentPicksEditing}
                onEdit={() => setTournamentPicksEditing(true)}
              />
            )}
            <LockPill lock={{ locked: lockedWinner }} />
          </section>

          <div
            className="prediction-group-switcher"
            aria-label="Prediction groups"
          >
            {data.groups.map((group) => {
              const total = matchesByGroup.get(group.id)?.length ?? 0;
              const predicted = groupPredictionCount(group.id);
              return (
                <button
                  className={
                    group.id === selectedGroupId
                      ? "group-switch is-active"
                      : "group-switch"
                  }
                  key={group.id}
                  type="button"
                  onClick={() => {
                    setSelectedGroupId(group.id);
                    setEditingMatchId("");
                  }}
                >
                  <span className="group-mini-flags">
                    {group.teams.map((teamId) => (
                      <TeamFlag key={teamId} id={teamId} />
                    ))}
                  </span>
                  <strong>Group {group.id}</strong>
                  <em>
                    {predicted}/{total}
                  </em>
                </button>
              );
            })}
          </div>

          {selectedGroup && (
            <div className="prediction-workspace">
              <section
                className="comparison-grid"
                aria-label={`Group ${selectedGroup.id} table comparison`}
              >
                <article className="prediction-table-panel">
                  <div className="prediction-step-header">
                    <div>
                      <h4>Live Group {selectedGroup.id} table</h4>
                      <p>Current table from completed match results.</p>
                    </div>
                    <span className="pill">Live</span>
                  </div>
                  <StandingsTable
                    group={selectedGroup}
                    matches={data.matches}
                    teams={teams}
                  />
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
                    <p>
                      Change open scores inline; changes are saved
                      automatically.
                    </p>
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
                        canToggleLeeuwtje={
                          leeuwtjeMatchIds.has(match.id) ||
                          leeuwtjeMatchIds.size < leeuwtjeTotal
                        }
                        leeuwtjesRemaining={leeuwtjesRemaining}
                        onScore={setScore}
                        onQuizAnswer={setQuizAnswer}
                        onToggleLeeuwtje={() => toggleLeeuwtje(match.id)}
                        onSubmit={() => save(true)}
                        focused={focusedMatchId === match.id}
                        compact
                        quickEntry
                      />
                    );
                  })}
                </div>
              </section>
            </div>
          )}
          {error && (
            <div className="prediction-actions">
              <span className="form-error">{error}</span>
            </div>
          )}
        </div>
      </article>
    </div>
  );
}

function NotificationBell({
  notifications,
  open,
  onToggle,
  onPredictions,
  onNotificationAction,
  onCelebrateBadge,
  onDismissNotification,
}) {
  const count = notifications.reduce(
    (total, notification) => total + notification.count,
    0,
  );
  const actionableCount = notifications.reduce(
    (total, notification) => total + (notification.items?.length ?? 0),
    0,
  );
  return (
    <div className="notification-wrap">
      <button
        className={
          count ? "notification-button has-items" : "notification-button"
        }
        type="button"
        onClick={onToggle}
        aria-label={`${count} open acties`}
        aria-expanded={open}
      >
        <span aria-hidden="true">🔔</span>
        {count > 0 && <b>{Math.min(count, 99)}</b>}
      </button>
      {open && (
        <div
          className="notification-popover"
          role="dialog"
          aria-label="Open acties"
        >
          <div className="notification-title">
            <strong>Nog te doen</strong>
            <span>{notifications.length} meldingen</span>
          </div>
          {notifications.length ? (
            notifications.map((notification) => (
              <article
                key={`${notification.type}-${notification.id ?? notification.title}`}
                className={[
                  "notification-item",
                  notification.type === "broadcast" ? "is-broadcast" : "",
                  notification.type === "sync_issue" ? "is-sync-issue" : "",
                  notification.type === "badge_unlocked"
                    ? "is-badge-unlocked"
                    : "",
                  notification.severity
                    ? `severity-${notification.severity}`
                    : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                {notification.type === "sync_issue" && (
                  <button
                    className="notification-dismiss"
                    type="button"
                    onClick={() => onDismissNotification?.(notification)}
                    aria-label="Dismiss notification"
                    title="Dismiss notification"
                  >
                    x
                  </button>
                )}
                <strong>{notification.title}</strong>
                <p>{notification.body}</p>
                {notification.type === "badge_unlocked" ? (
                  <button
                    className="badge-celebrate-button"
                    type="button"
                    onClick={() => onCelebrateBadge?.(notification)}
                    aria-label="Vier badge"
                    title="Vier badge"
                  >
                    <span aria-hidden="true">🎉</span>
                  </button>
                ) : null}
                {notification.items?.length ? (
                  <div className="notification-actions">
                    {notification.items.map((item) => (
                      <button
                        key={`${item.kind}-${item.match_id}`}
                        className="notification-action"
                        type="button"
                        onClick={() => onNotificationAction?.(item)}
                      >
                        <span>{item.label}</span>
                        <em>
                          {item.title ??
                            (item.kind === "quiz" ? "Quiz" : "Prediction")}
                          {item.subtitle ? ` · ${item.subtitle}` : ""}
                        </em>
                      </button>
                    ))}
                  </div>
                ) : null}
                {notification.actions?.length ? (
                  <div className="notification-actions is-inline">
                    {notification.actions.map((action) => (
                      <button
                        key={`${notification.type}-${action.id}`}
                        className="notification-action"
                        type="button"
                        onClick={() =>
                          onNotificationAction?.({
                            notification_type: notification.type,
                            action: action.id,
                          })
                        }
                      >
                        <span>{action.label}</span>
                      </button>
                    ))}
                  </div>
                ) : null}
              </article>
            ))
          ) : (
            <div className="empty compact">
              Geen open acties voor vandaag of morgen.
            </div>
          )}
          <button
            className="primary-button"
            type="button"
            onClick={onPredictions}
          >
            {actionableCount ? "Open predictions" : "Mijn voorspellingen"}
          </button>
        </div>
      )}
    </div>
  );
}

function ConfettiBurst({ active }) {
  if (!active) return null;
  const pieces = Array.from({ length: 72 }, (_, index) => ({
    id: index,
    left: `${(index * 37) % 100}%`,
    delay: `${(index % 12) * 0.045}s`,
    duration: `${1.9 + (index % 7) * 0.13}s`,
    color: [
      "#f36c21",
      "#21468b",
      "#ae1c28",
      "#00a7b5",
      "#8cc63f",
      "#f7c948",
      "#d7257b",
    ][index % 7],
    drift: `${((index % 13) - 6) * 9}px`,
    rotate: `${(index * 29) % 180}deg`,
  }));
  return (
    <div className="confetti-layer" aria-hidden="true">
      {pieces.map((piece) => (
        <span
          key={piece.id}
          style={{
            left: piece.left,
            animationDelay: piece.delay,
            animationDuration: piece.duration,
            background: piece.color,
            "--drift": piece.drift,
            transform: `rotate(${piece.rotate})`,
          }}
        />
      ))}
    </div>
  );
}

function BadgeReveal({ badge }) {
  if (!badge) return null;
  return (
    <div className="badge-reveal-layer" aria-live="polite" aria-atomic="true">
      <article className={`badge-reveal-card is-${badge.family ?? "trophy"}`}>
        <span className="badge-reveal-mark" aria-hidden="true">
          {badge.mark ?? "B"}
        </span>
        <div>
          <p>Badge unlocked</p>
          <h2>{badge.label ?? "Nieuwe badge"}</h2>
          {badge.detail && <span>{badge.detail}</span>}
        </div>
      </article>
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
    email: user.email,
    prize_pot_status: user.prize_pot_status ?? "undecided",
    prize_pot: user.prize_pot,
    points: 0,
    precision: 0,
    shooting: 0,
    defence: 0,
    scoring_games: 0,
    top_scorer_points: 0,
    striker_points: 0,
    scorer_points: 0,
    winner_points: 0,
    winner_impossible: false,
    top_scorer_impossible: false,
    winner_pick_name: null,
    top_scorer_pick: null,
    top_scorer_picks: [],
    striker_picks: [],
    profile_picture: {
      image_url: user.profile_picture?.image_url,
      initials:
        user.name
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
  const [authChecked, setAuthChecked] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [view, setView] = useState(
    () => viewFromRoute(window.location.pathname) ?? "leaderboard",
  );
  const [selectedProfileId, setSelectedProfileId] = useState(() =>
    profileIdFromRoute(window.location.pathname),
  );
  const [selectedTeamId, setSelectedTeamId] = useState(() =>
    teamIdFromRoute(window.location.pathname),
  );
  const [selectedMatchdayMatchId, setSelectedMatchdayMatchId] = useState(() =>
    matchdayMatchIdFromRoute(window.location.pathname),
  );
  const [selectedKnockoutMatchId, setSelectedKnockoutMatchId] = useState("");
  const [now, setNow] = useState(() => new Date());
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [changePasswordOpen, setChangePasswordOpen] = useState(false);
  const [predictionFocusTarget, setPredictionFocusTarget] = useState(null);
  const [celebrationBadge, setCelebrationBadge] = useState(null);
  const [confettiActive, setConfettiActive] = useState(false);
  const [dismissedBadgeNotificationKeys, setDismissedBadgeNotificationKeys] =
    useState(() => new Set(readDismissedBadgeNotificationKeys()));
  const celebrationTimerRef = useRef(null);

  function replacePath(path) {
    if (normalizeRoute(window.location.pathname) !== path) {
      window.history.replaceState({}, "", path);
    }
  }

  function navigateToView(nextView, options = {}) {
    setNotificationsOpen(false);
    setView(nextView);
    const route = routeForView(
      nextView,
      selectedProfileId,
      selectedTeamId,
      selectedMatchdayMatchId,
    );
    const historyMethod = options.replace ? "replaceState" : "pushState";
    if (normalizeRoute(window.location.pathname) !== route) {
      window.history[historyMethod]({}, "", route);
    }
  }

  function navigateToPredictionTarget(item) {
    if (item?.target_view === "knockout") {
      setSelectedKnockoutMatchId(item?.target_match_id ?? item?.match_id ?? "");
      navigateToView("knockout");
      return;
    }
    setPredictionFocusTarget({
      match_id: item?.target_match_id ?? item?.match_id ?? "",
      kind: item?.target_kind ?? item?.kind ?? "prediction",
    });
    navigateToView(item?.target_view === "pool" ? "pool" : "adjust");
  }

  function navigateToMyPredictions() {
    const knockout = poolKnockout(pool);
    if (knockout.is_relevant) {
      const firstMissing = knockout.missing_actions?.[0];
      setSelectedKnockoutMatchId(firstMissing?.match_id ?? "");
      navigateToView("knockout");
      return;
    }
    navigateToView("adjust");
  }

  async function handleNotificationAction(item) {
    if (item?.notification_type === "prize_pot") {
      setNotificationsOpen(false);
      try {
        await savePrizePotParticipation(item.action, { optimistic: true });
      } catch (err) {
        setLoadError(err.message);
      }
      return;
    }
    navigateToPredictionTarget(item);
  }

  async function dismissNotification(notification) {
    if (notification?.type !== "sync_issue" || !notification.id) return;
    setPool((current) =>
      current
        ? {
            ...current,
            notifications: (current.notifications ?? []).filter(
              (item) =>
                item.type !== "sync_issue" || item.id !== notification.id,
            ),
          }
        : current,
    );
    try {
      await apiJson(`/api/admin/notifications/sync-issues/${notification.id}/dismiss`, {
        method: "POST",
        body: "{}",
      });
    } catch (err) {
      setLoadError(err.message);
      loadPool();
    }
  }

  function celebrateBadge(notification) {
    const badge = notification?.badges?.[0] ?? {
      label: notification?.title ?? "Badge unlocked",
      detail: notification?.body ?? "",
      family: "trophy",
      mark: "B",
    };
    const notificationKey = badgeNotificationKey(notification);
    setDismissedBadgeNotificationKeys((current) => {
      const next = new Set(current);
      if (notificationKey) next.add(notificationKey);
      writeDismissedBadgeNotificationKeys(next);
      return next;
    });
    setPool((current) =>
      current
        ? {
          ...current,
          notifications: (current.notifications ?? []).filter(
            (item) =>
              item.type !== "badge_unlocked" ||
              badgeNotificationKey(item) !== notificationKey,
          ),
        }
        : current,
    );
    window.clearTimeout(celebrationTimerRef.current);
    setNotificationsOpen(false);
    setCelebrationBadge(badge);
    setConfettiActive(true);
    celebrationTimerRef.current = window.setTimeout(() => {
      setConfettiActive(false);
      setCelebrationBadge(null);
    }, 3600);
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

  function navigateToMatchdayMatch(matchId) {
    const nextMatchId = String(matchId);
    setSelectedMatchdayMatchId(nextMatchId);
    setView("matchdayMatch");
    const route = matchdayMatchRoute(nextMatchId);
    if (normalizeRoute(window.location.pathname) !== route) {
      window.history.pushState({}, "", route);
    }
  }

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 30000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(
    () => () => {
      window.clearTimeout(celebrationTimerRef.current);
    },
    [],
  );

  useEffect(() => {
    function handlePopState() {
      const profileId = profileIdFromRoute(window.location.pathname);
      const teamId = teamIdFromRoute(window.location.pathname);
      const matchdayMatchId = matchdayMatchIdFromRoute(window.location.pathname);
      setSelectedProfileId(profileId);
      setSelectedTeamId(teamId);
      setSelectedMatchdayMatchId(matchdayMatchId);
      if (pool?.me) {
        const nextView = authenticatedViewFromRoute(
          pool,
          window.location.pathname,
        );
        setView(nextView);
        if (
          normalizeRoute(window.location.pathname) !==
          routeForView(nextView, profileId, teamId, matchdayMatchId)
        ) {
          replacePath(routeForView(nextView, profileId, teamId, matchdayMatchId));
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
        const meState = await apiJson("/api/me");
        if (cancelled) return;

        if (!meState.user) {
          setPool({ me: null });
          replacePath("/login");
          return;
        }

        const [poolState, worldCup] = await Promise.all([
          apiJson("/api/pool"),
          apiJson("/api/world-cup"),
        ]);
        if (!cancelled) {
          setPool(poolState);
          setData(worldCup);
          const nextView = authenticatedViewFromRoute(
            poolState,
            window.location.pathname,
          );
          const profileId = profileIdFromRoute(window.location.pathname);
          const teamId = teamIdFromRoute(window.location.pathname);
          const matchdayMatchId = matchdayMatchIdFromRoute(
            window.location.pathname,
          );
          setSelectedProfileId(profileId);
          setSelectedTeamId(teamId);
          setSelectedMatchdayMatchId(matchdayMatchId);
          setView(nextView);
          if (
            normalizeRoute(window.location.pathname) !==
            routeForView(nextView, profileId, teamId, matchdayMatchId)
          ) {
            replacePath(routeForView(nextView, profileId, teamId, matchdayMatchId));
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

  const visibleNotifications = useMemo(
    () =>
      (pool?.notifications ?? []).filter(
        (notification) =>
          notification.type !== "badge_unlocked" ||
          !dismissedBadgeNotificationKeys.has(badgeNotificationKey(notification)),
      ),
    [pool?.notifications, dismissedBadgeNotificationKeys],
  );

  async function handleLogin() {
    setLoadError("");
    const [worldCup, poolState] = await Promise.all([
      apiJson("/api/world-cup"),
      apiJson("/api/pool"),
    ]);
    setData(worldCup);
    setPool(poolState);
    navigateToView(defaultAuthenticatedView(poolState), { replace: true });
  }

  async function logout() {
    await apiJson("/api/auth/logout", { method: "POST", body: "{}" });
    setData(null);
    setPool({ me: null });
    setView("leaderboard");
    replacePath("/login");
  }

  function updatePoolOnly(updatedPool) {
    setPool(updatedPool);
  }

  async function refreshPool() {
    const updatedPool = await apiJson("/api/pool");
    setPool(updatedPool);
    return updatedPool;
  }

  function continueToLeaderboard(updatedPool) {
    if (updatedPool) setPool(updatedPool);
    navigateToView("leaderboard", { replace: true });
  }

  async function updateUserName(name) {
    const updatedPool = await apiJson("/api/me", {
      method: "PATCH",
      body: JSON.stringify({ name }),
    });
    setPool(updatedPool);
    return updatedPool;
  }

  async function updateUserImage(profileImageUrl) {
    const updatedPool = await apiJson("/api/me", {
      method: "PATCH",
      body: JSON.stringify({ profile_image_url: profileImageUrl }),
    });
    setPool(updatedPool);
    return updatedPool;
  }

  async function changePassword(payload) {
    return apiJson("/api/me/password", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async function refreshPoolAfterPasswordChange() {
    const updatedPool = await apiJson("/api/pool");
    setPool(updatedPool);
  }

  async function savePrizePotParticipation(status, options = {}) {
    if (options.optimistic) {
      setPool((current) => {
        if (!current?.me) return current;
        const optimisticPrizePot = {
          ...(current.prize_pot ?? current.me.prize_pot ?? {}),
          status,
        };
        const optimisticUser = {
          ...current.me,
          prize_pot_status: status,
          prize_pot: optimisticPrizePot,
        };
        return {
          ...current,
          me: optimisticUser,
          prize_pot: optimisticPrizePot,
          notifications: (current.notifications ?? []).filter(
            (notification) => notification.type !== "prize_pot",
          ),
          leaderboard: (current.leaderboard ?? []).map((row) =>
            row.user_id === optimisticUser.id
              ? {
                ...row,
                prize_pot_status: status,
                prize_pot: optimisticPrizePot,
              }
              : row,
          ),
        };
      });
    }

    const updated = await apiJson("/api/prize-pot/participation", {
      method: "POST",
      body: JSON.stringify({ status }),
    });
    if (updated.user) {
      setPool((current) => ({
        ...current,
        me: updated.user,
        prize_pot: updated.prize_pot,
        notifications: (current?.notifications ?? []).filter(
          (notification) => notification.type !== "prize_pot",
        ),
        leaderboard: (current?.leaderboard ?? []).map((row) =>
          row.user_id === updated.user.id
            ? {
              ...row,
              prize_pot_status: updated.user.prize_pot_status,
              prize_pot: updated.user.prize_pot,
            }
            : row,
        ),
      }));
    }
    return updated;
  }

  if (!authChecked) {
    return <div className="loading">Loading Talpa WK Pool...</div>;
  }

  if (loadError) {
    return (
      <div className="loading">
        <div className="load-error">
          Could not load Talpa WK Pool: {loadError}
        </div>
      </div>
    );
  }

  if (!pool?.me) {
    return <LoginPage onLogin={handleLogin} />;
  }

  if (pool.me.must_change_password) {
    return (
      <ForcePasswordChangePage
        onChangePassword={changePassword}
        onComplete={refreshPoolAfterPasswordChange}
        onLogout={logout}
      />
    );
  }

  if (!data) {
    return <div className="loading">Loading Talpa WK Pool...</div>;
  }

  const selectedProfile =
    pool.leaderboard.find((row) => String(row.user_id) === selectedProfileId) ??
    (String(pool.me?.id) === selectedProfileId ? fallbackProfile(pool) : null);
  const selectedProfileRank = selectedProfile
    ? pool.leaderboard.findIndex(
      (row) => row.user_id === selectedProfile.user_id,
    ) + 1
    : 0;
  const selectedTeam = maps.teams.get(selectedTeamId) ?? null;
  const venueRows = data.venues;
  const knockout = poolKnockout(pool);
  const navItems = [
    "home",
    "matchday",
    knockout.is_relevant ? "knockout" : null,
    "leaderboard",
    "groups",
    "teams",
    "schedule",
    "venues",
    "faq",
  ].filter(Boolean);

  return (
    <>
      <ConfettiBurst active={confettiActive} />
      <BadgeReveal badge={celebrationBadge} />
      <header className="app-header">
        <button
          className="brand-lockup"
          type="button"
          onClick={() => navigateToView("home")}
          aria-label="Go to homepage"
        >
          <FieldMark />
          <div>
            <p className="eyebrow">FIFA World Cup 2026</p>
            <h1>Talpa WK Pool</h1>
          </div>
        </button>
        <div className="header-actions">
          <NotificationBell
            notifications={visibleNotifications}
            open={notificationsOpen}
            onToggle={() => setNotificationsOpen((current) => !current)}
            onPredictions={navigateToMyPredictions}
            onNotificationAction={handleNotificationAction}
            onCelebrateBadge={celebrateBadge}
            onDismissNotification={dismissNotification}
          />
          <button
            className="faq-button"
            type="button"
            onClick={() => navigateToView("faq")}
            aria-label="Veelgestelde vragen"
            title="Veelgestelde vragen"
          >
            <span aria-hidden="true">?</span>
            <span>FAQ</span>
          </button>
          <button
            className="my-predictions-button"
            type="button"
            onClick={navigateToMyPredictions}
          >
            <span>Mijn voorspellingen</span>
            <b>
              {knockout.is_relevant
                ? knockout.missing_actions?.length ?? 0
                : `${pool.progress?.group_stage_predictions ?? 0}/${pool.progress?.group_stage_total ?? 0}`}
            </b>
          </button>
          <button
            className="data-badge is-clickable"
            type="button"
            onClick={() => navigateToProfile(pool.me.id)}
          >
            {pool.me.name}
          </button>
          <button
            className="text-button"
            type="button"
            onClick={() => setChangePasswordOpen(true)}
          >
            Change password
          </button>
          <button className="text-button" type="button" onClick={logout}>
            Logout
          </button>
        </div>
      </header>

      {changePasswordOpen && (
        <ChangePasswordModal
          onClose={() => setChangePasswordOpen(false)}
          onChangePassword={changePassword}
        />
      )}

      <main>
        <section className="hero-panel">
          <div className="hero-copy">
            <p className="eyebrow">FIFA World Cup 2026</p>
            <h2>Talpa WK Pool</h2>
            <p>
              Predict group-stage scores, pick the World Cup winner, top scorer
              and five strikers, and follow the leaderboard.
            </p>
          </div>
          <div className="hero-oranje" aria-label="World Cup is underway">
            <div className="dutch-flag-card" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <div className="lion-crest" aria-hidden="true">
              🦁
            </div>
            <div>
              <span>Het WK is begonnen</span>
              <strong>Oranje leeft</strong>
              <p>Volg de dagscore, movers en gespeelde wedstrijden live.</p>
            </div>
          </div>
        </section>

        <nav className="tabs" aria-label="Dashboard views">
          {navItems.map((item) => {
            const active =
              view === item ||
              (view === "team" && item === "teams") ||
              (view === "matchdayMatch" && item === "matchday");
            return (
              <button
                key={item}
                className={active ? "tab is-active" : "tab"}
                type="button"
                onClick={() => navigateToView(item)}
              >
                {viewLabel(item)}
              </button>
            );
          })}
        </nav>

        {view === "welcome" && (
          <section className="view is-active">
            <WelcomeStep
              pool={pool}
              onNext={() => navigateToView("leaderboardPreview")}
            />
          </section>
        )}

        {view === "leaderboardPreview" && (
          <section className="view is-active">
            <LeaderboardPreviewStep
              pool={pool}
              onBack={() => navigateToView("welcome")}
              onNext={() => navigateToView("join")}
            />
          </section>
        )}

        {view === "home" && (
          <section className="view is-active">
            <HomePage
              onSchedule={() => navigateToView("schedule")}
              recap={pool.daily_recap}
              rules={pool.rules}
              newsletters={pool.newsletters ?? []}
            />
          </section>
        )}

        {view === "matchday" && (
          <section className="view is-active">
            <MatchdayPage
              pool={pool}
              teams={maps.teams}
              venues={maps.venues}
              onMatch={navigateToMatchdayMatch}
            />
          </section>
        )}

        {view === "knockout" && (
          <section className="view is-active">
            <KnockoutPage
              pool={pool}
              teams={maps.teams}
              onPoolUpdate={updatePoolOnly}
              focusMatchId={selectedKnockoutMatchId}
            />
          </section>
        )}

        {view === "matchdayMatch" && (
          <section className="view is-active">
            <MatchdayMatchPage
              matchId={selectedMatchdayMatchId}
              teams={maps.teams}
              venues={maps.venues}
              onBack={() => navigateToView("matchday")}
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
              onBack={() => navigateToView("home")}
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
              focusTarget={predictionFocusTarget}
            />
          </section>
        )}

        {view === "leaderboard" && (
          <section className="view is-active">
            <Leaderboard pool={pool} onProfile={navigateToProfile} />
            <WallOfShame
              rows={pool.wall_of_shame ?? []}
              onProfile={navigateToProfile}
            />
          </section>
        )}

        {view === "admin" && pool.me?.is_admin && (
          <section className="view is-active">
            <AdminPage
              currentUser={pool.me}
              teams={maps.teams}
              onSyncComplete={refreshPool}
            />
          </section>
        )}

        {view === "profile" && (
          <section className="view is-active">
            <PlayerProfile
              player={selectedProfile}
              rank={selectedProfileRank}
              isSelf={selectedProfile?.user_id === pool.me?.id}
              viewerIsAdmin={Boolean(pool.me?.is_admin)}
              viewerPrizePot={pool.prize_pot}
              badgeCatalog={pool.badge_catalog ?? []}
              data={data}
              rules={pool.rules}
              tournamentPicksVisible={tournamentPicksRevealed(pool)}
              onUpdateName={updateUserName}
              onUpdateImage={updateUserImage}
              onJoinPrizePot={() => savePrizePotParticipation("joined")}
              onAdmin={() => navigateToView("admin")}
            />
          </section>
        )}

        {view === "groups" && (
          <section className="view is-active">
            <div className="groups-grid">
              {data.groups.map((group) => (
                <GroupPanel
                  key={group.id}
                  group={group}
                  data={data}
                  teams={maps.teams}
                />
              ))}
            </div>
          </section>
        )}

        {view === "teams" && (
          <section className="view is-active">
            <TeamDirectoryPage
              data={data}
              teams={maps.teams}
              onTeam={navigateToTeam}
            />
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
            <Schedule
              matches={sortedMatches}
              teams={maps.teams}
              venues={maps.venues}
              pool={pool}
              onPoolUpdate={updatePoolOnly}
              onMatch={navigateToMatchdayMatch}
            />
          </section>
        )}

        {view === "faq" && (
          <section className="view is-active">
            <FaqPage rules={pool.rules} />
          </section>
        )}

        {view === "venues" && (
          <section className="view is-active">
            <div className="grid">
              {venueRows.map((venue) => {
                const matchCount = data.matches.filter(
                  (match) => match.venue_id === venue.id,
                ).length;
                return (
                  <article key={venue.id} className="venue-row">
                    <div>
                      <h3>{venue.name}</h3>
                      <div className="meta">
                        {venue.city}, {venue.country} · {venue.timezone}
                      </div>
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
