import { worldCupData } from "./data/worldcup-2026.js";

const AMSTERDAM_TZ = "Europe/Amsterdam";
const NETHERLANDS_ID = "ned";
const API_BASE = "https://api.wc2026api.com";

const state = {
  view: "groups",
  data: worldCupData,
  group: "all",
  team: "all",
  query: "",
  provider: "fallback",
};

const els = {
  dataBadge: document.querySelector("#dataBadge"),
  refreshButton: document.querySelector("#refreshButton"),
  tabs: document.querySelectorAll(".tab"),
  groupFilter: document.querySelector("#groupFilter"),
  teamFilter: document.querySelector("#teamFilter"),
  searchInput: document.querySelector("#searchInput"),
  daysToKickoff: document.querySelector("#daysToKickoff"),
  matchCount: document.querySelector("#matchCount"),
  groupCount: document.querySelector("#groupCount"),
  venueCount: document.querySelector("#venueCount"),
  views: {
    groups: document.querySelector("#groupsView"),
    schedule: document.querySelector("#scheduleView"),
    netherlands: document.querySelector("#netherlandsView"),
    venues: document.querySelector("#venuesView"),
  },
};

const teamById = new Map(state.data.teams.map((team) => [team.id, team]));
const venueById = new Map(state.data.venues.map((venue) => [venue.id, venue]));

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function teamName(id) {
  if (!id) return "TBD";
  return teamById.get(id)?.name ?? id;
}

function teamCode(id) {
  if (!id) return "TBD";
  return teamById.get(id)?.code ?? "TBD";
}

function venueName(id) {
  if (id === "to_confirm") return "Venue to confirm";
  const venue = venueById.get(id);
  return venue ? `${venue.name}, ${venue.city}` : id;
}

function dateTime(match) {
  return new Date(`${match.date}T${match.time_utc}:00Z`);
}

function formatDate(match, opts = {}) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: AMSTERDAM_TZ,
    weekday: opts.short ? "short" : "long",
    day: "numeric",
    month: opts.short ? "short" : "long",
    year: "numeric",
  }).format(dateTime(match));
}

function formatTime(match) {
  return new Intl.DateTimeFormat("nl-NL", {
    timeZone: AMSTERDAM_TZ,
    hour: "2-digit",
    minute: "2-digit",
  }).format(dateTime(match));
}

function localDateKey(match) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: AMSTERDAM_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(dateTime(match));
}

function normalize(value) {
  return String(value ?? "").toLowerCase();
}

function hasNetherlands(match) {
  return match.home_team_id === NETHERLANDS_ID || match.away_team_id === NETHERLANDS_ID;
}

function matchSearchText(match) {
  const venue = venueById.get(match.venue_id);
  return [
    teamName(match.home_team_id),
    teamName(match.away_team_id),
    teamCode(match.home_team_id),
    teamCode(match.away_team_id),
    match.group,
    match.round,
    venue?.name,
    venue?.city,
    venue?.country,
  ].join(" ");
}

function resolveTeamId(value) {
  const input = normalize(value).replaceAll("&", "and");
  const aliases = {
    "bosnia-herzegovina": "bih",
    "bosnia and herzegovina": "bih",
    "czech republic": "cze",
    czechia: "cze",
    "cote d'ivoire": "civ",
    "côte d'ivoire": "civ",
    "ivory coast": "civ",
    curacao: "cuw",
    "curaçao": "cuw",
    "dr congo": "cod",
    "congo dr": "cod",
    "south korea": "kor",
    "korea republic": "kor",
    "south africa": "rsa",
    "united states": "usa",
    usa: "usa",
    turkiye: "tur",
    turkey: "tur",
    iraq: "irq",
  };
  if (aliases[input]) return aliases[input];
  return state.data.teams.find((team) => normalize(team.name) === input || normalize(team.code) === input)?.id;
}

function resolveVenueId(value) {
  const input = normalize(value);
  if (!input) return "to_confirm";
  const cityAliases = {
    dallas: "att",
    arlington: "att",
    houston: "nrg",
    "kansas city": "arrowhead",
    "new york new jersey": "metlife",
    "new york - new jersey": "metlife",
    "los angeles": "sofi",
    "san francisco": "levis",
    seattle: "lumen",
    atlanta: "mercedes_benz",
    miami: "hard_rock",
    boston: "gillette",
    philadelphia: "lincoln",
    toronto: "bmo",
    vancouver: "bc_place",
    monterrey: "bbva",
    guadalajara: "akron",
    "mexico city": "azteca",
  };
  if (cityAliases[input]) return cityAliases[input];
  return state.data.venues.find((venue) => normalize(venue.name) === input || input.includes(normalize(venue.name)))?.id ?? "to_confirm";
}

function filteredMatches({ onlyNetherlands = false } = {}) {
  return state.data.matches
    .filter((match) => !onlyNetherlands || hasNetherlands(match))
    .filter((match) => state.group === "all" || match.group === state.group)
    .filter(
      (match) =>
        state.team === "all" ||
        match.home_team_id === state.team ||
        match.away_team_id === state.team,
    )
    .filter((match) => !state.query || normalize(matchSearchText(match)).includes(state.query))
    .sort((a, b) => dateTime(a) - dateTime(b));
}

function renderTeamLabel(id) {
  const label = escapeHtml(teamName(id));
  const code = escapeHtml(teamCode(id));
  const classes = id === NETHERLANDS_ID ? "team-name highlight-text" : "team-name";
  return `<span class="${classes}">${label}</span> <span class="muted">${code}</span>`;
}

function renderMatchCard(match) {
  const group = match.group ? `Group ${match.group}` : match.round;
  const netherlandsClass = hasNetherlands(match) ? " orange" : "";
  return `
    <article class="match-card">
      <div class="match-time">${escapeHtml(formatTime(match))}</div>
      <div>
        <div class="match-teams">
          ${renderTeamLabel(match.home_team_id)}
          <span class="muted">vs</span>
          ${renderTeamLabel(match.away_team_id)}
        </div>
        <div class="match-meta">
          ${escapeHtml(formatDate(match, { short: true }))} · ${escapeHtml(venueName(match.venue_id))}
        </div>
      </div>
      <span class="pill${netherlandsClass}">${escapeHtml(group)}</span>
    </article>
  `;
}

function groupMatchesByLocalDate(matches) {
  return matches.reduce((days, match) => {
    const key = localDateKey(match);
    if (!days.has(key)) days.set(key, []);
    days.get(key).push(match);
    return days;
  }, new Map());
}

function renderSchedule(matches) {
  if (!matches.length) {
    return `<div class="empty">No matches match the current filters.</div>`;
  }

  return [...groupMatchesByLocalDate(matches).entries()]
    .map(([, dayMatches]) => {
      const heading = formatDate(dayMatches[0]);
      return `
        <h3 class="date-heading">${escapeHtml(heading)}</h3>
        <div class="match-list">${dayMatches.map(renderMatchCard).join("")}</div>
      `;
    })
    .join("");
}

function calculateStandings(groupId) {
  const group = state.data.groups.find((item) => item.id === groupId);
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
  state.data.matches
    .filter((match) => match.group === groupId && match.status === "completed")
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

  return rows.sort((a, b) => {
    const gdA = a.goalsFor - a.goalsAgainst;
    const gdB = b.goalsFor - b.goalsAgainst;
    return b.points - a.points || gdB - gdA || b.goalsFor - a.goalsFor;
  });
}

function renderStandingsTable(groupId) {
  const rows = calculateStandings(groupId);
  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Team</th>
            <th class="numeric">P</th>
            <th class="numeric">W</th>
            <th class="numeric">D</th>
            <th class="numeric">L</th>
            <th class="numeric">GD</th>
            <th class="numeric">Pts</th>
          </tr>
        </thead>
        <tbody>
          ${rows
            .map((row) => {
              const gd = row.goalsFor - row.goalsAgainst;
              const highlight = row.teamId === NETHERLANDS_ID ? " class=\"highlight\"" : "";
              return `
                <tr${highlight}>
                  <td>${renderTeamLabel(row.teamId)}</td>
                  <td class="numeric">${row.played}</td>
                  <td class="numeric">${row.won}</td>
                  <td class="numeric">${row.drawn}</td>
                  <td class="numeric">${row.lost}</td>
                  <td class="numeric">${gd}</td>
                  <td class="numeric"><strong>${row.points}</strong></td>
                </tr>
              `;
            })
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderGroupPanel(group) {
  const teams = group.teams.map((id) => teamName(id)).join(", ");
  const matches = state.data.matches.filter((match) => match.group === group.id);
  return `
    <article class="panel">
      <div class="panel-header">
        <div>
          <h3>Group ${escapeHtml(group.id)}</h3>
          <p>${escapeHtml(teams)}</p>
        </div>
        <span class="pill${group.id === "F" ? " orange" : ""}">${matches.length} matches</span>
      </div>
      <div class="panel-body">
        ${renderStandingsTable(group.id)}
      </div>
    </article>
  `;
}

function renderGroups() {
  const groups = state.data.groups.filter((group) => state.group === "all" || group.id === state.group);
  els.views.groups.innerHTML = `
    <div class="groups-grid">
      ${groups.map(renderGroupPanel).join("")}
    </div>
  `;
}

function renderVenues() {
  const query = state.query;
  const venues = state.data.venues.filter((venue) =>
    query
      ? normalize([venue.name, venue.city, venue.country, venue.region].join(" ")).includes(query)
      : true,
  );

  els.views.venues.innerHTML = `
    <div class="grid">
      ${venues
        .map((venue) => {
          const matches = state.data.matches.filter((match) => match.venue_id === venue.id).length;
          return `
            <article class="venue-row">
              <div>
                <h3>${escapeHtml(venue.name)}</h3>
                <div class="meta">
                  ${escapeHtml(venue.city)}, ${escapeHtml(venue.country)} · ${escapeHtml(venue.timezone)}
                </div>
              </div>
              <span class="pill">${matches} matches</span>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderNetherlands() {
  const matches = filteredMatches({ onlyNetherlands: true });
  els.views.netherlands.innerHTML = `
    <article class="panel">
      <div class="panel-header">
        <div>
          <h3>Netherlands match plan</h3>
          <p>Use this as the shared planning list for watch moments in Amsterdam time.</p>
        </div>
        <span class="pill orange">Group F</span>
      </div>
      <div class="panel-body">
        ${renderSchedule(matches)}
      </div>
    </article>
  `;
}

function renderScheduleView() {
  els.views.schedule.innerHTML = renderSchedule(filteredMatches());
}

function renderMetrics() {
  const kickoff = new Date("2026-06-11T19:00:00Z");
  const today = new Date();
  els.daysToKickoff.textContent = Math.max(0, Math.ceil((kickoff - today) / 86400000));
  els.matchCount.textContent = state.data.matches.length;
  els.groupCount.textContent = state.data.groups.length;
  els.venueCount.textContent = state.data.venues.length;
  els.dataBadge.textContent = state.provider === "live" ? "Live provider" : "Fallback data";
}

function render() {
  renderMetrics();
  renderGroups();
  renderScheduleView();
  renderNetherlands();
  renderVenues();

  Object.entries(els.views).forEach(([view, node]) => {
    node.classList.toggle("is-active", view === state.view);
  });
  els.tabs.forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.view === state.view);
  });
}

function populateFilters() {
  els.groupFilter.innerHTML = [
    `<option value="all">All groups</option>`,
    ...state.data.groups.map((group) => `<option value="${group.id}">Group ${group.id}</option>`),
  ].join("");

  els.teamFilter.innerHTML = [
    `<option value="all">All teams</option>`,
    ...state.data.teams
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((team) => `<option value="${team.id}">${escapeHtml(team.name)}</option>`),
  ].join("");
}

async function tryLoadLiveData() {
  const apiKey = localStorage.getItem("WC2026_API_KEY");
  if (!apiKey) return false;

  try {
    const response = await fetch(`${API_BASE}/matches`, {
      headers: { Authorization: `Bearer ${apiKey}` },
    });
    if (!response.ok) throw new Error(`Provider returned ${response.status}`);
    const providerMatches = await response.json();
    if (!Array.isArray(providerMatches) || providerMatches.length === 0) return false;
    const mappedMatches = providerMatches
      .map((match, index) => {
        const kickoff = new Date(match.kickoff_utc || match.kickoffUtc || match.kickoff);
        const homeId = resolveTeamId(match.home_team || match.homeTeam);
        const awayId = resolveTeamId(match.away_team || match.awayTeam);
        if (!homeId || !awayId || Number.isNaN(kickoff.getTime())) return null;
        return {
          id: String(match.id ?? `provider-${index}`),
          match_number: Number(match.match_number ?? match.matchNumber ?? index + 1),
          date: kickoff.toISOString().slice(0, 10),
          time_utc: kickoff.toISOString().slice(11, 16),
          venue_id: resolveVenueId(match.stadium || match.venue || match.venue_name),
          group: String(match.group_name || match.group || "").replace("Group ", "") || undefined,
          round: normalize(match.round) === "group" ? "Group Stage" : match.round || "Group Stage",
          home_team_id: homeId,
          away_team_id: awayId,
          status: match.status || "scheduled",
          home_score: match.home_score,
          away_score: match.away_score,
        };
      })
      .filter(Boolean)
      .sort((a, b) => dateTime(a) - dateTime(b));
    if (mappedMatches.length) {
      state.data = { ...state.data, matches: mappedMatches };
    }
    state.provider = "live";
    return true;
  } catch (error) {
    console.warn("Live provider unavailable, using fallback data.", error);
    state.provider = "fallback";
    return false;
  }
}

function bindEvents() {
  els.tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      state.view = tab.dataset.view;
      render();
    });
  });

  els.groupFilter.addEventListener("change", (event) => {
    state.group = event.target.value;
    render();
  });

  els.teamFilter.addEventListener("change", (event) => {
    state.team = event.target.value;
    render();
  });

  els.searchInput.addEventListener("input", (event) => {
    state.query = normalize(event.target.value.trim());
    render();
  });

  els.refreshButton.addEventListener("click", async () => {
    await tryLoadLiveData();
    render();
  });
}

async function init() {
  populateFilters();
  bindEvents();
  await tryLoadLiveData();
  render();
}

init();
