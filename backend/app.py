from __future__ import annotations

import base64
import binascii
import hashlib
import html
import itertools
import json
import logging
import os
import re
import secrets
import sqlite3
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from flask import Flask, abort, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import genai_service  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file(ROOT / ".env")

DATA_PATH = ROOT / "backend" / "worldcup-2026.json"
QUIZ_PATH = ROOT / "backend" / "quiz-2026.json"
TEAM_PROFILES_PATH = ROOT / "backend" / "team-profiles-2026.json"
DB_PATH = Path(os.environ.get("WK_HUB_SQLITE_PATH", ROOT / "backend" / "pool.db"))
DB_SCHEMA_VERSION = 7
SCORING_REVISION = "2026-06-16-leaderboard-recap"
PROFILE_IMAGE_MAX_BYTES = 750 * 1024
PROFILE_IMAGE_DATA_URL_PATTERN = re.compile(
    r"^data:image/(png|jpeg|jpg|webp|gif);base64,([A-Za-z0-9+/=\s]+)$"
)
TALPA_EMAIL_PATTERN = re.compile(
    r"^[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*@talpa(?:network|studios)\.com$"
)
PASSWORD_MIN_LENGTH = 8
DEFAULT_PASSWORD = "default-password"
# Admin-issued one-time passwords. Length comfortably clears PASSWORD_MIN_LENGTH;
# the alphabet drops easily confused characters (0/O, 1/l/I) for legibility.
TEMPORARY_PASSWORD_LENGTH = 12
TEMPORARY_PASSWORD_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DEFAULT_ADMIN_EMAILS = {
    "karel.geraedts@talpanetwork.com",
    "olivier.thijsen@talpanetwork.com",
    "sem.aslier@talpanetwork.com",
    "karel.geraedts@talpastudios.com",
    "olivier.thijsen@talpastudios.com",
    "sem.aslier@talpastudios.com",
}
PRIZE_POT_UNDECIDED = "undecided"
PRIZE_POT_JOINED = "joined"
PRIZE_POT_DECLINED = "declined"
PRIZE_POT_STATUSES = {PRIZE_POT_UNDECIDED, PRIZE_POT_JOINED, PRIZE_POT_DECLINED}
PRIZE_POT_CONTRIBUTION_AMOUNT = 10
PRIZE_POT_CURRENCY = "EUR"
PRIZE_POT_ORGANIZER_NAME = "Olivier Thijsen"
ADMIN_EMAILS = DEFAULT_ADMIN_EMAILS | {
    email.strip().casefold()
    for email in os.environ.get("WK_HUB_ADMIN_EMAILS", "").split(",")
    if email.strip()
}
DB_BACKUP_TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("users", ("id",)),
    ("match_predictions", ("user_id", "match_id")),
    ("winner_predictions", ("user_id",)),
    ("top_scorer_predictions", ("user_id",)),
    ("quiz_predictions", ("user_id", "match_id")),
    ("leeuwtje_predictions", ("user_id", "match_id")),
    ("user_follows", ("follower_id", "followed_id")),
    ("prediction_audit_log", ("id",)),
    ("api_football_team_links", ("local_team_id",)),
    ("api_football_fixture_links", ("match_id",)),
    ("api_football_requests", ("id",)),
    ("api_football_fixture_snapshots", ("match_id",)),
    ("api_football_fixture_snapshot_history", ("id",)),
    ("api_football_team_squad_snapshots", ("local_team_id",)),
    ("api_football_team_squad_snapshot_history", ("id",)),
    ("team_squad_players", ("local_team_id", "provider_player_key")),
    ("team_coaches", ("local_team_id", "provider_coach_key")),
    ("match_results", ("match_id",)),
    ("match_events", ("match_id", "provider_event_key")),
    ("match_clean_sheets", ("match_id", "local_team_id")),
    ("player_match_stats", ("match_id", "provider_player_key")),
    ("quiz_label_overrides", ("match_id",)),
    ("label_audit_log", ("id",)),
    ("admin_broadcast_notifications", ("created_at", "id")),
    ("provider_sync_attempts", ("id",)),
    ("computed_points", ("user_id", "scope_type", "scope_id", "category")),
    ("admin_sync_notifications", ("created_at", "id")),
    ("genai_job_results", ("created_at", "id")),
    ("quiz_auto_labels", ("match_id",)),
    ("quiz_genai_reviews", ("job_result_id",)),
    ("player_candidate_links", ("target_type", "target_id")),
    ("newsletter_articles", ("published_at", "url")),
)
DIST_DIR = ROOT / "frontend" / "dist"
DATABASE_URL_ENV = "DATABASE_URL" if os.environ.get("DATABASE_URL") else None
if DATABASE_URL_ENV is None and os.environ.get("POSTGRES_URL"):
    DATABASE_URL_ENV = "POSTGRES_URL"
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
SCHEMA_DATABASE_URL_ENV = (
    "DATABASE_URL_UNPOOLED" if os.environ.get("DATABASE_URL_UNPOOLED") else DATABASE_URL_ENV
)
SCHEMA_DATABASE_URL = os.environ.get("DATABASE_URL_UNPOOLED") or DATABASE_URL
USING_POSTGRES = bool(DATABASE_URL)
IS_VERCEL = os.environ.get("VERCEL") == "1"
CONFIG_ERROR = (
    "Set DATABASE_URL from Neon, or POSTGRES_URL, for Talpa WK Pool on Vercel."
    if IS_VERCEL and not DATABASE_URL
    else None
)
DB_INIT_DONE = False
DB_INIT_ERROR: str | None = None
LOG_LEVEL_NAME = os.environ.get("WK_HUB_LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, logging.INFO)
if not isinstance(LOG_LEVEL, int):
    LOG_LEVEL = logging.INFO
PREDICTION_LOCK_BEFORE_KICKOFF = timedelta(hours=1)
# Matches separated by less than this gap belong to the same playing session.
# World Cup 2026 matches are often played overnight (Dutch time): evening and
# early-morning kickoffs are part of the same American matchday for NL viewers.
# Overnight gaps are ~6-8h; the daytime gap to the next evening session is much
# larger, so this threshold cleanly separates one matchday from the next.
MATCHDAY_SESSION_GAP = timedelta(hours=12)
MATCHDAY_SESSION_START_HOUR = 18
MATCHDAY_SESSION_END_HOUR = 4
NETHERLANDS_TEAM_ID = "ned"
AMSTERDAM_TZ = ZoneInfo("Europe/Amsterdam")
LEEUWTJES_LIMIT = 5
GROUP_POSITION_POINTS = 0
WINNER_POINTS = 60
TOP_SCORER_POINTS = 40
STRIKER_PICK_COUNT = 5
STRIKER_GOAL_POINTS = 6
QUIZ_YES_NO_POINTS = 3
QUIZ_OPEN_POINTS = 5
QUIZ_VIEWERSHIP_POINTS = 5
API_FOOTBALL_BASE_URL = os.environ.get(
    "API_FOOTBALL_BASE_URL", "https://v3.football.api-sports.io"
).rstrip("/")
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "")
API_FOOTBALL_LEAGUE_ID = int(os.environ.get("API_FOOTBALL_LEAGUE_ID", "1"))
API_FOOTBALL_SEASON = int(os.environ.get("API_FOOTBALL_SEASON", "2026"))
API_FOOTBALL_DAILY_LIMIT = None
API_FOOTBALL_SQUAD_SYNC_BATCH_SIZE = int(os.environ.get("API_FOOTBALL_SQUAD_SYNC_BATCH_SIZE", "6"))
API_FOOTBALL_SQUAD_REFRESH_HOURS = int(os.environ.get("API_FOOTBALL_SQUAD_REFRESH_HOURS", "24"))
API_FOOTBALL_SYNC_TOKEN = os.environ.get("WK_HUB_SYNC_TOKEN") or os.environ.get("CRON_SECRET", "")
API_FOOTBALL_PROVIDER_KEY = "api-football"
SYNC_TARGET_MATCH_RESULT = "match_result"
SYNC_TARGET_TEAM_SQUAD = "team_squad"
SYNC_TARGET_STRIKER_PICK = "striker_pick"
SYNC_ATTEMPT_EARLY_POST_MATCH = "early_post_match"
SYNC_ATTEMPT_FIRST_POST_MATCH = "first_post_match"
SYNC_ATTEMPT_SECOND_POST_MATCH = "second_post_match"
SYNC_ATTEMPT_MISSING_DATA_RETRY = "missing_data_retry"
SYNC_ATTEMPT_MANUAL = "manual"
SYNC_ATTEMPT_SQUAD_REFRESH = "squad_refresh"
SYNC_ATTEMPT_KINDS = {
    SYNC_ATTEMPT_EARLY_POST_MATCH,
    SYNC_ATTEMPT_FIRST_POST_MATCH,
    SYNC_ATTEMPT_SECOND_POST_MATCH,
    SYNC_ATTEMPT_MISSING_DATA_RETRY,
    SYNC_ATTEMPT_MANUAL,
    SYNC_ATTEMPT_SQUAD_REFRESH,
}
SYNC_STATUS_PENDING = "pending"
SYNC_STATUS_RUNNING = "running"
SYNC_STATUS_SUCCEEDED = "succeeded"
SYNC_STATUS_SKIPPED = "skipped"
SYNC_STATUS_FAILED = "failed"
SYNC_TERMINAL_STATUSES = {SYNC_STATUS_SUCCEEDED, SYNC_STATUS_SKIPPED, SYNC_STATUS_FAILED}
RESULT_SYNC_EARLY_AFTER = timedelta(minutes=5)
RESULT_SYNC_FIRST_AFTER = timedelta(minutes=15)
RESULT_SYNC_SECOND_AFTER = timedelta(hours=2)
API_FOOTBALL_POSTMATCH_BUFFER = timedelta(
    minutes=int(os.environ.get("API_FOOTBALL_POSTMATCH_BUFFER_MINUTES", "135"))
)
API_FOOTBALL_FINAL_RESYNC_AFTER = timedelta(
    hours=int(os.environ.get("API_FOOTBALL_FINAL_RESYNC_HOURS", "12"))
)
API_FOOTBALL_FINAL_STATUSES = {"FT", "AET", "PEN"}
API_FOOTBALL_MAX_BATCH_SIZE = 20
NEWSLETTER_MAX_ARTICLES = int(os.environ.get("NEWSLETTER_MAX_ARTICLES", "6"))
NEWSLETTER_FEEDS: tuple[dict[str, str], ...] = (
    {
        "name": "Google News NL",
        "country": "Netherlands",
        "url": (
            "https://news.google.com/rss/search?"
            "q=WK%202026%20voetbal%20OR%20Wereldkampioenschap%202026%20voetbal"
            "&hl=nl&gl=NL&ceid=NL:nl"
        ),
    },
    {
        "name": "Google News BE",
        "country": "Belgium",
        "url": (
            "https://news.google.com/rss/search?"
            "q=WK%202026%20voetbal%20OR%20Rode%20Duivels%20WK%202026"
            "&hl=nl&gl=BE&ceid=BE:nl"
        ),
    },
)
BASE_MATCH_SCORE_RULE = {
    "outcome": 6,
    "home_goals": 2,
    "away_goals": 2,
    "exact_bonus": 2,
    "exact": 12,
}
MATCH_ROUND_MULTIPLIERS = {
    "Group Stage": 1.0,
    "Round of 32": 1.25,
    "Round of 16": 1.5,
    "Quarter-final": 2.0,
    "Semi-final": 2.5,
    "Third-place play-off": 3.0,
    "Final": 4.0,
}
MATCH_SCORE_RULES = {
    round_name: {
        **BASE_MATCH_SCORE_RULE,
        "multiplier": multiplier,
        "exact": int(BASE_MATCH_SCORE_RULE["exact"] * multiplier + 0.5),
        "outcome": int(BASE_MATCH_SCORE_RULE["outcome"] * multiplier + 0.5),
    }
    for round_name, multiplier in MATCH_ROUND_MULTIPLIERS.items()
}

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("wk_hub")
if CONFIG_ERROR:
    logger.error(CONFIG_ERROR)


def database_label() -> str:
    if CONFIG_ERROR:
        return "unconfigured database"
    if USING_POSTGRES:
        return f"postgres:{DATABASE_URL_ENV or 'unknown env'}"
    return f"sqlite:{DB_PATH}"


def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return iso_utc(value.astimezone(UTC)) if value.tzinfo else value.isoformat()
    if isinstance(value, sqlite3.Row):
        keys = value.keys()
        return {key: json_ready(value[key]) for key in keys}
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [json_ready(item) for item in value]
    return value


def static_data_manifest() -> dict[str, Any]:
    return {
        "worldcup_path": str(DATA_PATH.relative_to(ROOT)),
        "worldcup_sha256": file_sha256(DATA_PATH),
        "quiz_path": str(QUIZ_PATH.relative_to(ROOT)) if QUIZ_PATH.exists() else None,
        "quiz_sha256": file_sha256(QUIZ_PATH),
        "team_profiles_path": (
            str(TEAM_PROFILES_PATH.relative_to(ROOT)) if TEAM_PROFILES_PATH.exists() else None
        ),
        "team_profiles_sha256": file_sha256(TEAM_PROFILES_PATH),
    }


def load_world_cup_data() -> dict[str, Any]:
    with DATA_PATH.open(encoding="utf-8") as data_file:
        data = json.load(data_file)

    if QUIZ_PATH.exists():
        with QUIZ_PATH.open(encoding="utf-8") as quiz_file:
            quiz_data = json.load(quiz_file)
        quizzes = quiz_data.get("matches", {})
        for match in data["matches"]:
            quiz = quizzes.get(match["id"])
            if quiz:
                match["quiz"] = quiz
        data.setdefault("meta", {})["quiz_answer_source"] = quiz_data.get("answerSource")

    apply_static_team_profiles(data)

    if not CONFIG_ERROR:
        apply_quiz_label_overrides(data)
        apply_synced_team_profiles(data)
        apply_synced_match_results(data)

    return data


def parse_correct_answers_json(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [answer for answer in (clean_text(item) for item in parsed) if answer]


def parse_text_list_json(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in (clean_text(value) for value in parsed) if item]


def apply_quiz_label_overrides(data: dict[str, Any]) -> None:
    try:
        with get_db() as conn:
            auto_rows = execute(
                conn,
                """
                SELECT match_id, source, job_result_id, correct_answers_json,
                       confidence, evidence_json, resolved_at, updated_at
                FROM quiz_auto_labels
                """,
            ).fetchall()
            rows = execute(
                conn,
                """
                SELECT match_id, question, choices_json, correct_answers_json,
                       viewership_answer, source, updated_by_user_id, updated_at
                FROM quiz_label_overrides
                """,
            ).fetchall()
    except Exception:
        logger.exception("Could not load quiz label overrides")
        return

    auto_labels = {row["match_id"]: row for row in auto_rows}
    overrides = {row["match_id"]: row for row in rows}
    for match in data.get("matches", []):
        quiz = match.get("quiz")
        row = overrides.get(match["id"])
        if not isinstance(quiz, dict):
            if not row:
                continue
            setup_question = clean_text(row["question"] if row_has_key(row, "question") else None)
            setup_choices = parse_text_list_json(
                row["choices_json"] if row_has_key(row, "choices_json") else None
            )
            if not setup_question:
                continue
            quiz = {
                "question": setup_question,
                "type": (
                    "yes_no"
                    if {normalize_answer(choice) for choice in setup_choices} == {"ja", "nee"}
                    else "choice" if setup_choices else "open"
                ),
            }
            if setup_choices:
                quiz["choices"] = setup_choices
            match["quiz"] = quiz
        auto_row = auto_labels.get(match["id"])
        if auto_row is not None:
            genai_service.apply_auto_quiz_label(match, auto_row)
        if not row:
            continue
        question = clean_text(row["question"] if row_has_key(row, "question") else None)
        if question:
            quiz["question"] = question
        choices = parse_text_list_json(
            row["choices_json"] if row_has_key(row, "choices_json") else None
        )
        if choices:
            quiz["choices"] = choices
        correct_answers = parse_correct_answers_json(row["correct_answers_json"])
        if correct_answers:
            quiz["correct_answers"] = correct_answers
            quiz["correct_answer"] = correct_answers[0]
        if row["viewership_answer"] is not None:
            quiz["viewership_answer"] = int(row["viewership_answer"])
        quiz["label_source"] = row["source"] or "manual"
        quiz["label_updated_at"] = row["updated_at"]
        quiz["label_updated_by_user_id"] = row["updated_by_user_id"]
        quiz["manual_override_active"] = True


def merge_team_profile(team: dict[str, Any], profile: dict[str, Any]) -> None:
    current = dict(team.get("profile") or team.get("team_profile") or {})
    for key, value in profile.items():
        if key == "sources":
            current_sources = list_value(current.get("sources"))
            for source in list_value(value):
                if source not in current_sources:
                    current_sources.append(source)
            if current_sources:
                current["sources"] = current_sources
        elif value not in (None, "", []):
            current[key] = value
    if current:
        team["profile"] = current


def apply_static_team_profiles(data: dict[str, Any]) -> None:
    if not TEAM_PROFILES_PATH.exists():
        return
    try:
        with TEAM_PROFILES_PATH.open(encoding="utf-8") as profiles_file:
            profiles_data = json.load(profiles_file)
    except Exception:
        logger.exception("Could not load static team profiles")
        return

    by_team = {
        team.get("id"): team
        for team in profiles_data.get("teams", [])
        if isinstance(team, dict) and team.get("id")
    }
    source = profiles_data.get("source") or {}
    for team in data.get("teams", []):
        profile = by_team.get(team.get("id"))
        if not profile:
            continue
        profile_payload: dict[str, Any] = {}
        if profile.get("squad"):
            profile_payload["squad"] = profile["squad"]
        if profile.get("head_coach"):
            profile_payload["head_coach"] = profile["head_coach"]
            profile_payload["coaching_staff"] = [profile["head_coach"]]
        if source:
            profile_payload["sources"] = [source]
        merge_team_profile(team, profile_payload)


def utc_now() -> datetime:
    return datetime.now(UTC)


def match_kickoff(match: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(f"{match['date']}T{match['time_utc']}:00+00:00")


def match_lock_time(match: dict[str, Any]) -> datetime:
    return match_kickoff(match) - PREDICTION_LOCK_BEFORE_KICKOFF


def is_prediction_locked(match: dict[str, Any], now: datetime | None = None) -> bool:
    if match.get("status") != "scheduled":
        return True
    return (now or utc_now()) >= match_lock_time(match)


def tournament_picks_lock_time(data: dict[str, Any]) -> datetime:
    group_matches = [match for match in data["matches"] if match["round"] == "Group Stage"]
    first_match = min(group_matches, key=match_kickoff)
    return match_lock_time(first_match)


def are_tournament_picks_locked(data: dict[str, Any], now: datetime | None = None) -> bool:
    return (now or utc_now()) >= tournament_picks_lock_time(data)


def are_tournament_picks_revealed(data: dict[str, Any], now: datetime | None = None) -> bool:
    return are_tournament_picks_locked(data, now)


def winner_lock_time(data: dict[str, Any]) -> datetime:
    return tournament_picks_lock_time(data)


def is_winner_locked(data: dict[str, Any], now: datetime | None = None) -> bool:
    return are_tournament_picks_locked(data, now)


def iso_utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


app = Flask(__name__, static_folder=None)
app.secret_key = os.environ.get("WK_HUB_SECRET", "wk-hub-local-dev-secret")
logger.info("Starting Talpa WK Pool backend with %s", database_label())


@app.before_request
def track_request_start() -> None:
    g.request_start_time = time.perf_counter()


@app.before_request
def reject_misconfigured_deployment() -> Any | None:
    if request.path.startswith("/api/") and request.path != "/api/health":
        init_error = ensure_db_initialized()
        if init_error:
            return jsonify({"ok": False, "error": init_error}), 503
    return None


@app.after_request
def log_request(response: Any) -> Any:
    duration_ms = (
        time.perf_counter() - getattr(g, "request_start_time", time.perf_counter())
    ) * 1000
    logger.info(
        "%s %s -> %s %.1fms", request.method, request.path, response.status_code, duration_ms
    )
    return response


def bind(query: str) -> str:
    if USING_POSTGRES:
        return query.replace("?", "%s")
    return query


def execute(conn: Any, query: str, params: tuple[Any, ...] = ()) -> Any:
    return conn.execute(bind(query), params)


def get_db(*, schema: bool = False) -> Any:
    if USING_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row

        conninfo = SCHEMA_DATABASE_URL if schema else DATABASE_URL
        assert conninfo is not None
        return psycopg.connect(conninfo, row_factory=dict_row)

    if IS_VERCEL:
        raise RuntimeError(CONFIG_ERROR or "Vercel deployments must use Postgres.")

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def sql_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return iso_utc(value.astimezone(UTC))


def result_sync_scheduled_for(match: dict[str, Any], attempt_kind: str) -> datetime:
    postmatch_anchor = match_kickoff(match) + API_FOOTBALL_POSTMATCH_BUFFER
    if attempt_kind == SYNC_ATTEMPT_EARLY_POST_MATCH:
        return postmatch_anchor + RESULT_SYNC_EARLY_AFTER
    if attempt_kind == SYNC_ATTEMPT_FIRST_POST_MATCH:
        return postmatch_anchor + RESULT_SYNC_FIRST_AFTER
    if attempt_kind == SYNC_ATTEMPT_SECOND_POST_MATCH:
        return postmatch_anchor + RESULT_SYNC_SECOND_AFTER
    if attempt_kind == SYNC_ATTEMPT_MISSING_DATA_RETRY:
        return utc_now()
    raise ValueError(f"Unsupported result sync attempt kind: {attempt_kind}")


def due_result_sync_attempt_kinds(
    match: dict[str, Any],
    *,
    now: datetime,
    terminal_attempt_kinds: set[str],
    has_result: bool = False,
) -> list[str]:
    if not match.get("home_team_id") or not match.get("away_team_id"):
        return []

    early_due_at = result_sync_scheduled_for(match, SYNC_ATTEMPT_EARLY_POST_MATCH)
    if SYNC_ATTEMPT_EARLY_POST_MATCH not in terminal_attempt_kinds and now >= early_due_at:
        return [SYNC_ATTEMPT_EARLY_POST_MATCH]

    first_due_at = result_sync_scheduled_for(match, SYNC_ATTEMPT_FIRST_POST_MATCH)
    if (
        SYNC_ATTEMPT_EARLY_POST_MATCH in terminal_attempt_kinds
        and SYNC_ATTEMPT_FIRST_POST_MATCH not in terminal_attempt_kinds
        and now >= first_due_at
    ):
        return [SYNC_ATTEMPT_FIRST_POST_MATCH]

    second_due_at = result_sync_scheduled_for(match, SYNC_ATTEMPT_SECOND_POST_MATCH)
    if (
        SYNC_ATTEMPT_EARLY_POST_MATCH in terminal_attempt_kinds
        and SYNC_ATTEMPT_FIRST_POST_MATCH in terminal_attempt_kinds
        and SYNC_ATTEMPT_SECOND_POST_MATCH not in terminal_attempt_kinds
        and now >= second_due_at
    ):
        return [SYNC_ATTEMPT_SECOND_POST_MATCH]

    if (
        not has_result
        and SYNC_ATTEMPT_EARLY_POST_MATCH in terminal_attempt_kinds
        and SYNC_ATTEMPT_FIRST_POST_MATCH in terminal_attempt_kinds
        and SYNC_ATTEMPT_SECOND_POST_MATCH in terminal_attempt_kinds
        and now >= second_due_at
    ):
        return [SYNC_ATTEMPT_MISSING_DATA_RETRY]

    return []


def latest_due_result_sync_attempt_kind(match: dict[str, Any], now: datetime) -> str | None:
    if not match.get("home_team_id") or not match.get("away_team_id"):
        return None
    if now >= result_sync_scheduled_for(match, SYNC_ATTEMPT_SECOND_POST_MATCH):
        return SYNC_ATTEMPT_SECOND_POST_MATCH
    if now >= result_sync_scheduled_for(match, SYNC_ATTEMPT_FIRST_POST_MATCH):
        return SYNC_ATTEMPT_FIRST_POST_MATCH
    if now >= result_sync_scheduled_for(match, SYNC_ATTEMPT_EARLY_POST_MATCH):
        return SYNC_ATTEMPT_EARLY_POST_MATCH
    return None


def terminal_sync_attempt_kinds(
    conn: Any,
    *,
    provider_key: str,
    target_type: str,
    target_id: str,
) -> set[str]:
    rows = execute(
        conn,
        """
        SELECT attempt_kind
        FROM provider_sync_attempts
        WHERE provider_key = ?
          AND target_type = ?
          AND target_id = ?
          AND status IN (?, ?, ?)
        """,
        (
            provider_key,
            target_type,
            target_id,
            SYNC_STATUS_SUCCEEDED,
            SYNC_STATUS_SKIPPED,
            SYNC_STATUS_FAILED,
        ),
    ).fetchall()
    return {row["attempt_kind"] for row in rows}


def create_provider_sync_attempt(
    conn: Any,
    *,
    provider_key: str,
    target_type: str,
    target_id: str,
    attempt_kind: str,
    scheduled_for: datetime | None,
    status: str = SYNC_STATUS_RUNNING,
) -> int | None:
    started_at = utc_now() if status == SYNC_STATUS_RUNNING else None
    if USING_POSTGRES:
        row = execute(
            conn,
            """
            INSERT INTO provider_sync_attempts (
                provider_key, target_type, target_id, attempt_kind, scheduled_for,
                started_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                provider_key,
                target_type,
                target_id,
                attempt_kind,
                sql_timestamp(scheduled_for),
                sql_timestamp(started_at),
                status,
            ),
        ).fetchone()
        return int(row["id"]) if row else None

    cursor = execute(
        conn,
        """
        INSERT INTO provider_sync_attempts (
            provider_key, target_type, target_id, attempt_kind, scheduled_for,
            started_at, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            provider_key,
            target_type,
            target_id,
            attempt_kind,
            sql_timestamp(scheduled_for),
            sql_timestamp(started_at),
            status,
        ),
    )
    return int(cursor.lastrowid) if cursor.lastrowid is not None else None


def finish_provider_sync_attempt(
    conn: Any,
    attempt_id: int | None,
    *,
    status: str,
    provider_request_id: int | None = None,
    raw_snapshot_id: int | None = None,
    failure_code: str | None = None,
    failure_message: str | None = None,
) -> None:
    if attempt_id is None:
        return
    execute(
        conn,
        """
        UPDATE provider_sync_attempts
        SET status = ?,
            finished_at = CURRENT_TIMESTAMP,
            provider_request_id = ?,
            raw_snapshot_id = ?,
            failure_code = ?,
            failure_message = ?
        WHERE id = ?
        """,
        (
            status,
            provider_request_id,
            raw_snapshot_id,
            failure_code,
            failure_message,
            attempt_id,
        ),
    )


def create_admin_sync_notification(
    conn: Any,
    *,
    notification_type: str,
    target_type: str,
    target_id: str,
    title: str,
    body: str,
    severity: str = "warning",
    related_attempt_id: int | None = None,
) -> None:
    existing = execute(
        conn,
        """
        SELECT id
        FROM admin_sync_notifications
        WHERE type = ?
          AND target_type = ?
          AND target_id = ?
          AND is_active = 1
        """,
        (notification_type, target_type, target_id),
    ).fetchone()
    if existing:
        execute(
            conn,
            """
            UPDATE admin_sync_notifications
            SET title = ?,
                body = ?,
                severity = ?,
                related_attempt_id = ?,
                created_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (title, body, severity, related_attempt_id, existing["id"]),
        )
        return
    execute(
        conn,
        """
        INSERT INTO admin_sync_notifications (
            type, target_type, target_id, title, body, severity, related_attempt_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (notification_type, target_type, target_id, title, body, severity, related_attempt_id),
    )


def resolve_admin_sync_notification(
    conn: Any,
    *,
    notification_type: str,
    target_type: str,
    target_id: str,
) -> None:
    execute(
        conn,
        """
        UPDATE admin_sync_notifications
        SET is_active = 0,
            resolved_at = CURRENT_TIMESTAMP
        WHERE type = ?
          AND target_type = ?
          AND target_id = ?
          AND is_active = 1
        """,
        (notification_type, target_type, target_id),
    )


def active_admin_sync_notifications(conn: Any) -> list[dict[str, Any]]:
    rows = execute(
        conn,
        """
        SELECT id, type, target_type, target_id, title, body, severity, created_at
        FROM admin_sync_notifications
        WHERE is_active = 1
        ORDER BY created_at DESC, id DESC
        """,
    ).fetchall()
    return [json_ready(row) for row in rows]


def int_env_value(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def upsert_computed_point(
    conn: Any,
    *,
    user_id: int,
    scope_type: str,
    scope_id: str,
    category: str,
    points: int,
    details: dict[str, Any] | None = None,
    facts_revision_key: str | None = None,
) -> None:
    execute(
        conn,
        """
        INSERT INTO computed_points (
            user_id, scope_type, scope_id, category, points, details_json,
            facts_revision_key, computed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, scope_type, scope_id, category)
        DO UPDATE SET points = excluded.points,
                      details_json = excluded.details_json,
                      facts_revision_key = excluded.facts_revision_key,
                      computed_at = CURRENT_TIMESTAMP
        """,
        (
            user_id,
            scope_type,
            scope_id,
            category,
            points,
            json.dumps(details or {}, sort_keys=True),
            facts_revision_key,
        ),
    )


def delete_computed_points(
    conn: Any,
    *,
    scope_type: str,
    scope_id: str,
    category: str | None = None,
) -> None:
    if category is None:
        execute(
            conn,
            "DELETE FROM computed_points WHERE scope_type = ? AND scope_id = ?",
            (scope_type, scope_id),
        )
        return
    execute(
        conn,
        """
        DELETE FROM computed_points
        WHERE scope_type = ? AND scope_id = ? AND category = ?
        """,
        (scope_type, scope_id, category),
    )


def computed_point_rows(
    conn: Any,
    *,
    user_id: int | None = None,
    scope_type: str | None = None,
    scope_id: str | None = None,
) -> list[dict[str, Any]]:
    clauses = []
    params: list[Any] = []
    if user_id is not None:
        clauses.append("user_id = ?")
        params.append(user_id)
    if scope_type is not None:
        clauses.append("scope_type = ?")
        params.append(scope_type)
    if scope_id is not None:
        clauses.append("scope_id = ?")
        params.append(scope_id)
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = execute(
        conn,
        f"""
        SELECT user_id, scope_type, scope_id, category, points, details_json,
               facts_revision_key, computed_at
        FROM computed_points
        {where_clause}
        ORDER BY user_id, scope_type, scope_id, category
        """,
        tuple(params),
    ).fetchall()
    return [json_ready(row) for row in rows]


def computed_leaderboard_points_by_user(conn: Any) -> dict[int, dict[str, int]]:
    rows = execute(
        conn,
        """
        SELECT user_id, category, points
        FROM computed_points
        WHERE scope_type = 'leaderboard' AND scope_id = 'current'
          AND facts_revision_key LIKE ?
        """,
        (f"{SCORING_REVISION}:%",),
    ).fetchall()
    by_user: dict[int, dict[str, int]] = {}
    for row in rows:
        by_user.setdefault(int(row["user_id"]), {})[row["category"]] = int(row["points"])
    return by_user


def apply_stored_leaderboard_points(
    user_points: dict[str, int],
    stored_points: dict[str, int],
) -> dict[str, int]:
    merged = dict(user_points)
    for key, value in stored_points.items():
        if key in merged:
            merged[key] = value
    merged["points"] = sum(
        merged.get(key, 0)
        for key in (
            "match_score_points",
            "group_position_points",
            "quiz_points",
            "winner_points",
            "top_scorer_points",
            "striker_points",
            "leeuwtje_points",
        )
    )
    return merged


def recompute_all_computed_points(data: dict[str, Any]) -> dict[str, int]:
    rows = build_leaderboard(data, use_computed_points=False)
    revision_key = f"{SCORING_REVISION}:{iso_utc(utc_now())}"
    point_rows: list[tuple[Any, ...]] = []
    for row in rows:
        user_id = int(row["user_id"])
        category_points = {
            "match_score_points": int(row.get("match_score_points") or 0),
            "group_position_points": int(row.get("group_position_points") or 0),
            "quiz_points": int(row.get("quiz_points") or 0),
            "winner_points": int(row.get("winner_points") or 0),
            "top_scorer_points": int(row.get("top_scorer_points") or 0),
            "striker_points": int(row.get("striker_points") or 0),
            "leeuwtje_points": int(row.get("leeuwtje_points") or 0),
        }
        point_rows.extend(
            (
                user_id,
                "leaderboard",
                "current",
                category,
                points,
                json.dumps({"source": "recompute_all_computed_points"}, sort_keys=True),
                revision_key,
            )
            for category, points in category_points.items()
        )

    with get_db() as conn:
        player_verification = genai_service.verify_player_database_matches(conn)
        delete_computed_points(conn, scope_type="leaderboard", scope_id="current")
        if point_rows:
            cursor = conn.cursor()
            try:
                cursor.executemany(
                    bind(
                        """
                        INSERT INTO computed_points (
                            user_id, scope_type, scope_id, category, points, details_json,
                            facts_revision_key, computed_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(user_id, scope_type, scope_id, category)
                        DO UPDATE SET points = excluded.points,
                                      details_json = excluded.details_json,
                                      facts_revision_key = excluded.facts_revision_key,
                                      computed_at = CURRENT_TIMESTAMP
                        """
                    ),
                    point_rows,
                )
            finally:
                cursor.close()
    return player_verification


def database_snapshot(*, include_rows: bool) -> dict[str, Any]:
    tables: dict[str, Any] = {}
    with get_db() as conn:
        for table_name, order_by in DB_BACKUP_TABLES:
            row = execute(conn, f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
            table_payload: dict[str, Any] = {"count": int(row["count"] if row else 0)}
            if include_rows:
                order_clause = ", ".join(order_by)
                rows = execute(
                    conn, f"SELECT * FROM {table_name} ORDER BY {order_clause}"
                ).fetchall()
                table_payload["rows"] = [json_ready(row) for row in rows]
            tables[table_name] = table_payload

    return {
        "ok": True,
        "generated_at": iso_utc(utc_now()),
        "schema_version": DB_SCHEMA_VERSION,
        "database": database_label(),
        "static_data": static_data_manifest(),
        "tables": tables,
    }


def strip_html(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return clean_text(html.unescape(text))


def parse_rss_datetime(value: str) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    from email.utils import parsedate_to_datetime

    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return iso_utc(parsed.astimezone(UTC))


def fetch_newsletter_feed(feed: dict[str, str]) -> list[dict[str, Any]]:
    request_obj = Request(
        feed["url"],
        headers={
            "User-Agent": "wk-hub/1.0 (+https://wk-hub.local)",
        },
    )
    with urlopen(request_obj, timeout=12) as response:
        payload = response.read(2_000_000)
    root = ET.fromstring(payload)
    articles = []
    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title"))
        url = clean_text(item.findtext("link"))
        if not title or not url:
            continue
        source_node = item.find("source")
        publisher = clean_text(source_node.text if source_node is not None else "") or feed["name"]
        articles.append(
            {
                "title": title,
                "publisher": publisher,
                "country": feed["country"],
                "summary": strip_html(item.findtext("description"))[:320],
                "url": url,
                "source": feed["name"],
                "published_at": parse_rss_datetime(item.findtext("pubDate") or ""),
            }
        )
    return articles


def newsletter_articles_from_db(limit: int = NEWSLETTER_MAX_ARTICLES) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = execute(
            conn,
            """
            SELECT title, publisher, country, summary, url, source, published_at, refreshed_at
            FROM newsletter_articles
            ORDER BY published_at DESC NULLS LAST, refreshed_at DESC, title
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [json_ready(row) for row in rows]


def fallback_newsletter_articles() -> list[dict[str, Any]]:
    return [
        {
            "title": "WK 2026 levert landen recordbedrag op",
            "publisher": "NU.nl",
            "country": "Netherlands",
            "summary": (
                "FIFA raises the prize pool for the 2026 World Cup, with a larger base "
                "payout for every qualified country."
            ),
            "url": (
                "https://www.nu.nl/voetbal/6379805/"
                "wk-2026-levert-landen-recordbedrag-op-wereldkampioen-krijgt-42-miljoen-euro.html"
            ),
            "source": "Static fallback",
            "published_at": None,
            "refreshed_at": None,
        },
        {
            "title": "FIFA WK voetbal 2026 en 2030 live bij de NOS",
            "publisher": "NOS",
            "country": "Netherlands",
            "summary": "NOS outlines its broadcast role for the 2026 and 2030 men's World Cups.",
            "url": "https://over.nos.nl/nieuws/fifa-wk-voetbal-2026-en-2030-live-bij-de-nos/",
            "source": "Static fallback",
            "published_at": None,
            "refreshed_at": None,
        },
        {
            "title": "Het volledige speelschema van de Rode Duivels",
            "publisher": "VoetbalPrimeur.be",
            "country": "Belgium",
            "summary": (
                "Belgian coverage of the Red Devils' group-stage schedule, opponents and "
                "kick-off windows."
            ),
            "url": (
                "https://www.voetbalprimeur.be/nieuws/1718992/"
                "wk-voetbal-2026-ontdek-hier-het-volledige-speelschema-van-de-rode-duivels.html"
            ),
            "source": "Static fallback",
            "published_at": None,
            "refreshed_at": None,
        },
    ]


def newsletter_articles(limit: int = NEWSLETTER_MAX_ARTICLES) -> list[dict[str, Any]]:
    articles = newsletter_articles_from_db(limit)
    return articles if articles else fallback_newsletter_articles()[:limit]


def run_newsletter_refresh() -> dict[str, Any]:
    fetched: list[dict[str, Any]] = []
    errors = []
    seen_urls = set()
    for feed in NEWSLETTER_FEEDS:
        try:
            articles = fetch_newsletter_feed(feed)
        except (ET.ParseError, HTTPError, TimeoutError, URLError, OSError) as error:
            logger.warning("Newsletter feed refresh failed for %s: %s", feed["name"], error)
            errors.append({"source": feed["name"], "error": str(error)})
            continue
        for article in articles:
            if article["url"] in seen_urls:
                continue
            seen_urls.add(article["url"])
            fetched.append(article)

    fetched = sorted(
        fetched,
        key=lambda article: article.get("published_at") or "",
        reverse=True,
    )[:NEWSLETTER_MAX_ARTICLES]
    if fetched:
        with get_db() as conn:
            for article in fetched:
                execute(
                    conn,
                    """
                    INSERT INTO newsletter_articles (
                        url, title, publisher, country, summary, source, published_at, refreshed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(url)
                    DO UPDATE SET title = excluded.title,
                                  publisher = excluded.publisher,
                                  country = excluded.country,
                                  summary = excluded.summary,
                                  source = excluded.source,
                                  published_at = excluded.published_at,
                                  refreshed_at = CURRENT_TIMESTAMP
                    """,
                    (
                        article["url"],
                        article["title"],
                        article.get("publisher"),
                        article.get("country"),
                        article.get("summary"),
                        article["source"],
                        article.get("published_at"),
                    ),
                )
            conn.commit()

    return {
        "ok": bool(fetched) or not errors,
        "fetched": len(fetched),
        "errors": errors,
        "articles": fetched,
    }


def init_db() -> None:
    sqlite_schema = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            profile_image_url TEXT,
            password_hash TEXT,
            must_change_password INTEGER NOT NULL DEFAULT 0,
            prize_pot_status TEXT NOT NULL DEFAULT 'undecided',
            is_admin INTEGER NOT NULL DEFAULT 0,
            archived_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS match_predictions (
            user_id INTEGER NOT NULL,
            match_id TEXT NOT NULL,
            home_score INTEGER NOT NULL,
            away_score INTEGER NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, match_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS winner_predictions (
            user_id INTEGER PRIMARY KEY,
            team_id TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS top_scorer_predictions (
            user_id INTEGER PRIMARY KEY,
            player_name TEXT NOT NULL,
            player_name_2 TEXT,
            player_name_3 TEXT,
            striker_name_1 TEXT,
            striker_name_2 TEXT,
            striker_name_3 TEXT,
            striker_name_4 TEXT,
            striker_name_5 TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS quiz_predictions (
            user_id INTEGER NOT NULL,
            match_id TEXT NOT NULL,
            answer TEXT,
            viewership_prediction INTEGER,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, match_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS leeuwtje_predictions (
            user_id INTEGER NOT NULL,
            match_id TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, match_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_follows (
            follower_id INTEGER NOT NULL,
            followed_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (follower_id, followed_id),
            FOREIGN KEY (follower_id) REFERENCES users(id),
            FOREIGN KEY (followed_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS prediction_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_football_team_links (
            local_team_id TEXT PRIMARY KEY,
            api_team_id INTEGER NOT NULL UNIQUE,
            api_team_name TEXT,
            confidence TEXT NOT NULL,
            linked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_football_fixture_links (
            match_id TEXT PRIMARY KEY,
            api_fixture_id INTEGER NOT NULL UNIQUE,
            api_home_team_id INTEGER,
            api_away_team_id INTEGER,
            api_home_team_name TEXT,
            api_away_team_name TEXT,
            confidence TEXT NOT NULL,
            linked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_football_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            endpoint TEXT NOT NULL,
            params_json TEXT NOT NULL,
            status_code INTEGER,
            ok INTEGER NOT NULL,
            error TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_football_fixture_snapshots (
            match_id TEXT PRIMARY KEY,
            api_fixture_id INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_football_fixture_snapshot_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT NOT NULL,
            api_fixture_id INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_football_team_squad_snapshots (
            local_team_id TEXT PRIMARY KEY,
            api_team_id INTEGER NOT NULL,
            squad_payload_json TEXT NOT NULL,
            coach_payload_json TEXT,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_football_team_squad_snapshot_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            local_team_id TEXT NOT NULL,
            api_team_id INTEGER NOT NULL,
            squad_payload_json TEXT NOT NULL,
            coach_payload_json TEXT,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS team_squad_players (
            local_team_id TEXT NOT NULL,
            provider_player_key TEXT NOT NULL,
            source_team_id INTEGER,
            api_player_id INTEGER,
            player_name TEXT NOT NULL,
            age INTEGER,
            number INTEGER,
            position TEXT,
            photo_url TEXT,
            raw_json TEXT NOT NULL,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (local_team_id, provider_player_key)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS team_coaches (
            local_team_id TEXT NOT NULL,
            provider_coach_key TEXT NOT NULL,
            source_team_id INTEGER,
            api_coach_id INTEGER,
            coach_name TEXT NOT NULL,
            age INTEGER,
            nationality TEXT,
            photo_url TEXT,
            raw_json TEXT NOT NULL,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (local_team_id, provider_coach_key)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS match_results (
            match_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            source_fixture_id INTEGER,
            status_long TEXT,
            status_short TEXT,
            elapsed INTEGER,
            home_score INTEGER,
            away_score INTEGER,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS match_events (
            match_id TEXT NOT NULL,
            provider_event_key TEXT NOT NULL,
            source_fixture_id INTEGER,
            elapsed INTEGER,
            extra INTEGER,
            local_team_id TEXT,
            api_team_id INTEGER,
            team_name TEXT,
            api_player_id INTEGER,
            player_name TEXT,
            api_assist_id INTEGER,
            assist_name TEXT,
            event_type TEXT NOT NULL,
            detail TEXT,
            comments TEXT,
            raw_json TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (match_id, provider_event_key)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS match_clean_sheets (
            match_id TEXT NOT NULL,
            local_team_id TEXT NOT NULL,
            api_team_id INTEGER,
            team_name TEXT,
            source_fixture_id INTEGER,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (match_id, local_team_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS player_match_stats (
            match_id TEXT NOT NULL,
            provider_player_key TEXT NOT NULL,
            source_fixture_id INTEGER,
            local_team_id TEXT,
            api_team_id INTEGER,
            team_name TEXT,
            api_player_id INTEGER,
            player_name TEXT NOT NULL,
            minutes INTEGER,
            position TEXT,
            rating TEXT,
            goals INTEGER NOT NULL DEFAULT 0,
            assists INTEGER NOT NULL DEFAULT 0,
            yellow_cards INTEGER NOT NULL DEFAULT 0,
            red_cards INTEGER NOT NULL DEFAULT 0,
            clean_sheet INTEGER NOT NULL DEFAULT 0,
            raw_json TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (match_id, provider_player_key)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS quiz_label_overrides (
            match_id TEXT PRIMARY KEY,
            question TEXT,
            choices_json TEXT,
            correct_answers_json TEXT,
            viewership_answer INTEGER,
            source TEXT NOT NULL DEFAULT 'manual',
            updated_by_user_id INTEGER,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (updated_by_user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS label_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_user_id INTEGER,
            label_type TEXT NOT NULL,
            match_id TEXT NOT NULL,
            before_json TEXT,
            after_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (admin_user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS admin_broadcast_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            starts_at TEXT,
            expires_at TEXT,
            deactivated_at TEXT,
            created_by_user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by_user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS provider_sync_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_key TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            attempt_kind TEXT NOT NULL,
            scheduled_for TEXT,
            started_at TEXT,
            finished_at TEXT,
            status TEXT NOT NULL,
            provider_request_id INTEGER,
            raw_snapshot_id INTEGER,
            failure_code TEXT,
            failure_message TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS computed_points (
            user_id INTEGER NOT NULL,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            category TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            details_json TEXT NOT NULL DEFAULT '{}',
            facts_revision_key TEXT,
            computed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, scope_type, scope_id, category),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS admin_sync_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'warning',
            is_active INTEGER NOT NULL DEFAULT 1,
            related_attempt_id INTEGER,
            resolved_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_admin_sync_notifications_active_unique
        ON admin_sync_notifications (type, target_type, target_id)
        WHERE is_active = 1
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_match_predictions_match_id
        ON match_predictions (match_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_quiz_predictions_match_id
        ON quiz_predictions (match_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_leeuwtje_predictions_match_id
        ON leeuwtje_predictions (match_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_top_scorer_predictions_user_id
        ON top_scorer_predictions (user_id)
        """,
        """
        CREATE TABLE IF NOT EXISTS genai_job_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            provider_key TEXT NOT NULL,
            model TEXT NOT NULL,
            status TEXT NOT NULL,
            failure_code TEXT,
            failure_message TEXT,
            accepted_output_json TEXT,
            evidence_json TEXT,
            input_hash TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS quiz_auto_labels (
            match_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            job_result_id INTEGER,
            correct_answers_json TEXT NOT NULL,
            confidence TEXT NOT NULL,
            facts_revision_key TEXT,
            evidence_json TEXT,
            resolved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_result_id) REFERENCES genai_job_results(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS quiz_genai_reviews (
            job_result_id INTEGER PRIMARY KEY,
            match_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            selected_answers_json TEXT NOT NULL,
            reviewed_by_user_id INTEGER NOT NULL,
            reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_result_id) REFERENCES genai_job_results(id),
            FOREIGN KEY (reviewed_by_user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS player_candidate_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            raw_player_name TEXT NOT NULL,
            matched_local_team_id TEXT,
            matched_api_player_id INTEGER,
            matched_player_name TEXT NOT NULL,
            source TEXT NOT NULL,
            job_result_id INTEGER,
            confidence TEXT NOT NULL,
            evidence_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_result_id) REFERENCES genai_job_results(id)
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_player_candidate_links_target
        ON player_candidate_links (target_type, target_id)
        """,
        """
        CREATE TABLE IF NOT EXISTS newsletter_articles (
            url TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            publisher TEXT,
            country TEXT,
            summary TEXT,
            source TEXT NOT NULL,
            published_at TEXT,
            refreshed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]
    postgres_schema = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            profile_image_url TEXT,
            password_hash TEXT,
            must_change_password INTEGER NOT NULL DEFAULT 0,
            prize_pot_status TEXT NOT NULL DEFAULT 'undecided',
            is_admin INTEGER NOT NULL DEFAULT 0,
            archived_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS match_predictions (
            user_id INTEGER NOT NULL,
            match_id TEXT NOT NULL,
            home_score INTEGER NOT NULL,
            away_score INTEGER NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, match_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS winner_predictions (
            user_id INTEGER PRIMARY KEY,
            team_id TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS top_scorer_predictions (
            user_id INTEGER PRIMARY KEY,
            player_name TEXT NOT NULL,
            player_name_2 TEXT,
            player_name_3 TEXT,
            striker_name_1 TEXT,
            striker_name_2 TEXT,
            striker_name_3 TEXT,
            striker_name_4 TEXT,
            striker_name_5 TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS quiz_predictions (
            user_id INTEGER NOT NULL,
            match_id TEXT NOT NULL,
            answer TEXT,
            viewership_prediction INTEGER,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, match_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS leeuwtje_predictions (
            user_id INTEGER NOT NULL,
            match_id TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, match_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_follows (
            follower_id INTEGER NOT NULL,
            followed_id INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (follower_id, followed_id),
            FOREIGN KEY (follower_id) REFERENCES users(id),
            FOREIGN KEY (followed_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS prediction_audit_log (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            user_id INTEGER,
            action TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_football_team_links (
            local_team_id TEXT PRIMARY KEY,
            api_team_id INTEGER NOT NULL UNIQUE,
            api_team_name TEXT,
            confidence TEXT NOT NULL,
            linked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_football_fixture_links (
            match_id TEXT PRIMARY KEY,
            api_fixture_id INTEGER NOT NULL UNIQUE,
            api_home_team_id INTEGER,
            api_away_team_id INTEGER,
            api_home_team_name TEXT,
            api_away_team_name TEXT,
            confidence TEXT NOT NULL,
            linked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_football_requests (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            endpoint TEXT NOT NULL,
            params_json TEXT NOT NULL,
            status_code INTEGER,
            ok INTEGER NOT NULL,
            error TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_football_fixture_snapshots (
            match_id TEXT PRIMARY KEY,
            api_fixture_id INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_football_fixture_snapshot_history (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            match_id TEXT NOT NULL,
            api_fixture_id INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_football_team_squad_snapshots (
            local_team_id TEXT PRIMARY KEY,
            api_team_id INTEGER NOT NULL,
            squad_payload_json TEXT NOT NULL,
            coach_payload_json TEXT,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS api_football_team_squad_snapshot_history (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            local_team_id TEXT NOT NULL,
            api_team_id INTEGER NOT NULL,
            squad_payload_json TEXT NOT NULL,
            coach_payload_json TEXT,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS team_squad_players (
            local_team_id TEXT NOT NULL,
            provider_player_key TEXT NOT NULL,
            source_team_id INTEGER,
            api_player_id INTEGER,
            player_name TEXT NOT NULL,
            age INTEGER,
            number INTEGER,
            position TEXT,
            photo_url TEXT,
            raw_json TEXT NOT NULL,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (local_team_id, provider_player_key)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS team_coaches (
            local_team_id TEXT NOT NULL,
            provider_coach_key TEXT NOT NULL,
            source_team_id INTEGER,
            api_coach_id INTEGER,
            coach_name TEXT NOT NULL,
            age INTEGER,
            nationality TEXT,
            photo_url TEXT,
            raw_json TEXT NOT NULL,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (local_team_id, provider_coach_key)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS match_results (
            match_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            source_fixture_id INTEGER,
            status_long TEXT,
            status_short TEXT,
            elapsed INTEGER,
            home_score INTEGER,
            away_score INTEGER,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS match_events (
            match_id TEXT NOT NULL,
            provider_event_key TEXT NOT NULL,
            source_fixture_id INTEGER,
            elapsed INTEGER,
            extra INTEGER,
            local_team_id TEXT,
            api_team_id INTEGER,
            team_name TEXT,
            api_player_id INTEGER,
            player_name TEXT,
            api_assist_id INTEGER,
            assist_name TEXT,
            event_type TEXT NOT NULL,
            detail TEXT,
            comments TEXT,
            raw_json TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (match_id, provider_event_key)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS match_clean_sheets (
            match_id TEXT NOT NULL,
            local_team_id TEXT NOT NULL,
            api_team_id INTEGER,
            team_name TEXT,
            source_fixture_id INTEGER,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (match_id, local_team_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS player_match_stats (
            match_id TEXT NOT NULL,
            provider_player_key TEXT NOT NULL,
            source_fixture_id INTEGER,
            local_team_id TEXT,
            api_team_id INTEGER,
            team_name TEXT,
            api_player_id INTEGER,
            player_name TEXT NOT NULL,
            minutes INTEGER,
            position TEXT,
            rating TEXT,
            goals INTEGER NOT NULL DEFAULT 0,
            assists INTEGER NOT NULL DEFAULT 0,
            yellow_cards INTEGER NOT NULL DEFAULT 0,
            red_cards INTEGER NOT NULL DEFAULT 0,
            clean_sheet INTEGER NOT NULL DEFAULT 0,
            raw_json TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (match_id, provider_player_key)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS quiz_label_overrides (
            match_id TEXT PRIMARY KEY,
            question TEXT,
            choices_json TEXT,
            correct_answers_json TEXT,
            viewership_answer INTEGER,
            source TEXT NOT NULL DEFAULT 'manual',
            updated_by_user_id INTEGER,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (updated_by_user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS label_audit_log (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            admin_user_id INTEGER,
            label_type TEXT NOT NULL,
            match_id TEXT NOT NULL,
            before_json TEXT,
            after_json TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (admin_user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS admin_broadcast_notifications (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            starts_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ,
            deactivated_at TIMESTAMPTZ,
            created_by_user_id INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by_user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS provider_sync_attempts (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            provider_key TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            attempt_kind TEXT NOT NULL,
            scheduled_for TIMESTAMPTZ,
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            status TEXT NOT NULL,
            provider_request_id INTEGER,
            raw_snapshot_id INTEGER,
            failure_code TEXT,
            failure_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS computed_points (
            user_id INTEGER NOT NULL,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            category TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            details_json TEXT NOT NULL DEFAULT '{}',
            facts_revision_key TEXT,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, scope_type, scope_id, category),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS admin_sync_notifications (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            type TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'warning',
            is_active INTEGER NOT NULL DEFAULT 1,
            related_attempt_id INTEGER,
            resolved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_admin_sync_notifications_active_unique
        ON admin_sync_notifications (type, target_type, target_id)
        WHERE is_active = 1
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_match_predictions_match_id
        ON match_predictions (match_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_quiz_predictions_match_id
        ON quiz_predictions (match_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_leeuwtje_predictions_match_id
        ON leeuwtje_predictions (match_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_top_scorer_predictions_user_id
        ON top_scorer_predictions (user_id)
        """,
        """
        CREATE TABLE IF NOT EXISTS genai_job_results (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            job_type TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            provider_key TEXT NOT NULL,
            model TEXT NOT NULL,
            status TEXT NOT NULL,
            failure_code TEXT,
            failure_message TEXT,
            accepted_output_json TEXT,
            evidence_json TEXT,
            input_hash TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS quiz_auto_labels (
            match_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            job_result_id INTEGER,
            correct_answers_json TEXT NOT NULL,
            confidence TEXT NOT NULL,
            facts_revision_key TEXT,
            evidence_json TEXT,
            resolved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_result_id) REFERENCES genai_job_results(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS quiz_genai_reviews (
            job_result_id INTEGER PRIMARY KEY,
            match_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            selected_answers_json TEXT NOT NULL,
            reviewed_by_user_id INTEGER NOT NULL,
            reviewed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_result_id) REFERENCES genai_job_results(id),
            FOREIGN KEY (reviewed_by_user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS player_candidate_links (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            raw_player_name TEXT NOT NULL,
            matched_local_team_id TEXT,
            matched_api_player_id INTEGER,
            matched_player_name TEXT NOT NULL,
            source TEXT NOT NULL,
            job_result_id INTEGER,
            confidence TEXT NOT NULL,
            evidence_json TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_result_id) REFERENCES genai_job_results(id)
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_player_candidate_links_target
        ON player_candidate_links (target_type, target_id)
        """,
        """
        CREATE TABLE IF NOT EXISTS newsletter_articles (
            url TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            publisher TEXT,
            country TEXT,
            summary TEXT,
            source TEXT NOT NULL,
            published_at TIMESTAMPTZ,
            refreshed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]

    with get_db(schema=True) as conn:
        if USING_POSTGRES:
            for statement in postgres_schema:
                conn.execute(statement)
            quiz_viewership_column = conn.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'quiz_predictions'
                  AND column_name = 'viewership_prediction'
                """
            ).fetchone()
            if quiz_viewership_column is None:
                conn.execute(
                    "ALTER TABLE quiz_predictions ADD COLUMN viewership_prediction INTEGER"
                )
            user_profile_image_column = conn.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'users'
                  AND column_name = 'profile_image_url'
                """
            ).fetchone()
            if user_profile_image_column is None:
                conn.execute("ALTER TABLE users ADD COLUMN profile_image_url TEXT")
            user_password_column = conn.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'users'
                  AND column_name = 'password_hash'
                """
            ).fetchone()
            if user_password_column is None:
                conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
            user_prize_pot_column = conn.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'users'
                  AND column_name = 'prize_pot_status'
                """
            ).fetchone()
            if user_prize_pot_column is None:
                conn.execute(
                    "ALTER TABLE users ADD COLUMN prize_pot_status "
                    "TEXT NOT NULL DEFAULT 'undecided'"
                )
            user_admin_column = conn.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'users'
                  AND column_name = 'is_admin'
                """
            ).fetchone()
            if user_admin_column is None:
                conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
            user_archived_column = conn.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'users'
                  AND column_name = 'archived_at'
                """
            ).fetchone()
            if user_archived_column is None:
                conn.execute("ALTER TABLE users ADD COLUMN archived_at TIMESTAMPTZ")
            user_must_change_column = conn.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'users'
                  AND column_name = 'must_change_password'
                """
            ).fetchone()
            if user_must_change_column is None:
                conn.execute(
                    "ALTER TABLE users ADD COLUMN must_change_password "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            # Legacy accounts without a password get a known default; force them
            # to choose their own on next login so the default can't be used to
            # sign in as them.
            execute(
                conn,
                """
                UPDATE users
                SET password_hash = ?, must_change_password = 1
                WHERE password_hash IS NULL OR password_hash = ''
                """,
                (generate_password_hash(DEFAULT_PASSWORD),),
            )
            top_scorer_columns_to_add = (
                "player_name_2",
                "player_name_3",
                "striker_name_1",
                "striker_name_2",
                "striker_name_3",
                "striker_name_4",
                "striker_name_5",
            )
            for column_name in top_scorer_columns_to_add:
                top_scorer_column = conn.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'top_scorer_predictions'
                      AND column_name = %s
                    """,
                    (column_name,),
                ).fetchone()
                if top_scorer_column is None:
                    conn.execute(
                        f"ALTER TABLE top_scorer_predictions ADD COLUMN {column_name} TEXT"
                    )
            quiz_override_columns_to_add = {
                "question": "TEXT",
                "choices_json": "TEXT",
            }
            for column_name, column_type in quiz_override_columns_to_add.items():
                quiz_override_column = conn.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'quiz_label_overrides'
                      AND column_name = %s
                    """,
                    (column_name,),
                ).fetchone()
                if quiz_override_column is None:
                    conn.execute(
                        f"ALTER TABLE quiz_label_overrides ADD COLUMN {column_name} {column_type}"
                    )
        else:
            conn.executescript(";\n".join(sqlite_schema))
            quiz_columns = conn.execute("PRAGMA table_info(quiz_predictions)").fetchall()
            if not any(row["name"] == "viewership_prediction" for row in quiz_columns):
                conn.execute(
                    "ALTER TABLE quiz_predictions ADD COLUMN viewership_prediction INTEGER"
                )
            user_columns = conn.execute("PRAGMA table_info(users)").fetchall()
            if not any(row["name"] == "profile_image_url" for row in user_columns):
                conn.execute("ALTER TABLE users ADD COLUMN profile_image_url TEXT")
            if not any(row["name"] == "password_hash" for row in user_columns):
                conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
            if not any(row["name"] == "prize_pot_status" for row in user_columns):
                conn.execute(
                    "ALTER TABLE users ADD COLUMN prize_pot_status "
                    "TEXT NOT NULL DEFAULT 'undecided'"
                )
            if not any(row["name"] == "is_admin" for row in user_columns):
                conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
            if not any(row["name"] == "archived_at" for row in user_columns):
                conn.execute("ALTER TABLE users ADD COLUMN archived_at TEXT")
            if not any(row["name"] == "must_change_password" for row in user_columns):
                conn.execute(
                    "ALTER TABLE users ADD COLUMN must_change_password "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            # Legacy accounts without a password get a known default; force them
            # to choose their own on next login so the default can't be used to
            # sign in as them.
            execute(
                conn,
                """
                UPDATE users
                SET password_hash = ?, must_change_password = 1
                WHERE password_hash IS NULL OR password_hash = ''
                """,
                (generate_password_hash(DEFAULT_PASSWORD),),
            )
            top_scorer_columns = conn.execute(
                "PRAGMA table_info(top_scorer_predictions)"
            ).fetchall()
            top_scorer_column_names = {row["name"] for row in top_scorer_columns}
            top_scorer_columns_to_add = (
                "player_name_2",
                "player_name_3",
                "striker_name_1",
                "striker_name_2",
                "striker_name_3",
                "striker_name_4",
                "striker_name_5",
            )
            for column_name in top_scorer_columns_to_add:
                if column_name not in top_scorer_column_names:
                    conn.execute(
                        f"ALTER TABLE top_scorer_predictions ADD COLUMN {column_name} TEXT"
                    )
            quiz_override_columns = conn.execute(
                "PRAGMA table_info(quiz_label_overrides)"
            ).fetchall()
            quiz_override_column_names = {row["name"] for row in quiz_override_columns}
            for column_name in ("question", "choices_json"):
                if column_name not in quiz_override_column_names:
                    conn.execute(f"ALTER TABLE quiz_label_overrides ADD COLUMN {column_name} TEXT")
        if ADMIN_EMAILS:
            for admin_email in ADMIN_EMAILS:
                execute(
                    conn,
                    "UPDATE users SET is_admin = 1 WHERE LOWER(TRIM(email)) = ?",
                    (admin_email,),
                )
        admin_row = execute(
            conn,
            "SELECT id FROM users WHERE is_admin = 1 AND archived_at IS NULL LIMIT 1",
        ).fetchone()
        if admin_row is None:
            first_user = execute(
                conn,
                "SELECT id FROM users WHERE archived_at IS NULL ORDER BY id LIMIT 1",
            ).fetchone()
            if first_user is not None:
                execute(
                    conn,
                    "UPDATE users SET is_admin = 1 WHERE id = ?",
                    (first_user["id"],),
                )
    logger.info("Database schema ready using %s", SCHEMA_DATABASE_URL_ENV or database_label())


def ensure_db_initialized() -> str | None:
    global DB_INIT_DONE, DB_INIT_ERROR
    if CONFIG_ERROR:
        return CONFIG_ERROR
    if DB_INIT_DONE:
        return None
    try:
        init_db()
    except Exception:
        if not IS_VERCEL:
            raise
        logger.exception("Database initialization failed")
        DB_INIT_ERROR = (
            "Database initialization failed. Check DATABASE_URL or POSTGRES_URL in Vercel."
        )
        return DB_INIT_ERROR
    DB_INIT_DONE = True
    DB_INIT_ERROR = None
    return None


def is_admin_email(email: Any) -> bool:
    return normalize_email(email) in ADMIN_EMAILS


def normalize_prize_pot_status(value: Any) -> str:
    status = clean_text(value).casefold()
    if status in PRIZE_POT_STATUSES:
        return status
    return PRIZE_POT_UNDECIDED


def prize_pot_payload(status: Any = PRIZE_POT_UNDECIDED) -> dict[str, Any]:
    return {
        "status": normalize_prize_pot_status(status),
        "contribution_amount": PRIZE_POT_CONTRIBUTION_AMOUNT,
        "currency": PRIZE_POT_CURRENCY,
        "organizer_name": PRIZE_POT_ORGANIZER_NAME,
        "payment_in_app": False,
    }


def prize_pot_joined_count(conn: Any | None = None) -> int:
    def count_with_connection(active_conn: Any) -> int:
        row = execute(
            active_conn,
            """
            SELECT COUNT(*) AS count
            FROM users
            WHERE archived_at IS NULL AND prize_pot_status = ?
            """,
            (PRIZE_POT_JOINED,),
        ).fetchone()
        return int(row["count"] if row is not None else 0)

    if conn is not None:
        return count_with_connection(conn)
    with get_db() as active_conn:
        return count_with_connection(active_conn)


def prize_pot_payload_for_user(status: Any, participant_count: int | None = None) -> dict[str, Any]:
    payload = prize_pot_payload(status)
    if normalize_prize_pot_status(status) == PRIZE_POT_JOINED:
        payload["participant_count"] = (
            prize_pot_joined_count() if participant_count is None else participant_count
        )
    return payload


def prize_pot_notification(status: Any) -> list[dict[str, Any]]:
    if normalize_prize_pot_status(status) != PRIZE_POT_UNDECIDED:
        return []
    return [
        {
            "type": "prize_pot",
            "id": "prize-pot",
            "count": 1,
            "title": "Prijspot",
            "body": (
                "Wil je meedoen aan de optionele prijspot van EUR 10? "
                "De uiteindelijke pot wordt nog bepaald. "
                "Olivier Thijsen organiseert de betaling buiten de app."
            ),
            "actions": [
                {"id": PRIZE_POT_JOINED, "label": "Ik doe mee"},
                {"id": PRIZE_POT_DECLINED, "label": "Ik sla over"},
            ],
            **prize_pot_payload(status),
        }
    ]


def row_to_user(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    real_name = derived_real_name(row["email"])
    prize_pot_status = normalize_prize_pot_status(row_value(row, "prize_pot_status"))
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        **real_name,
        "is_admin": bool(row["is_admin"]) or is_admin_email(row["email"]),
        "archived_at": row["archived_at"],
        "must_change_password": bool(row_value(row, "must_change_password")),
        "profile_picture": user_profile_picture(row),
        "prize_pot_status": prize_pot_status,
        "prize_pot": prize_pot_payload(prize_pot_status),
    }


def current_user() -> dict[str, Any] | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    with get_db() as conn:
        row = execute(
            conn,
            """
            SELECT id, name, email, profile_image_url, prize_pot_status, is_admin,
                   archived_at, must_change_password
            FROM users
            WHERE id = ? AND archived_at IS NULL
            """,
            (user_id,),
        ).fetchone()
    if row is None:
        session.clear()
    return row_to_user(row)


def match_result(match: dict[str, Any]) -> int | None:
    home = match.get("home_score")
    away = match.get("away_score")
    if not isinstance(home, int) or not isinstance(away, int):
        return None
    return (home > away) - (home < away)


def prediction_result(prediction: Any) -> int:
    return (prediction["home_score"] > prediction["away_score"]) - (
        prediction["home_score"] < prediction["away_score"]
    )


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def row_value(row: Any, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def user_profile_picture(user: Any) -> dict[str, Any]:
    name = row_value(user, "name", "Unknown") if user is not None else "Unknown"
    image_url = row_value(user, "profile_image_url")
    picture = {
        "initials": initials(name),
        "hue": avatar_hue(name),
    }
    if image_url:
        picture["image_url"] = image_url
    return picture


def validate_profile_image_url(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError("Profile image must be an image upload.")
    match = PROFILE_IMAGE_DATA_URL_PATTERN.match(value.strip())
    if not match:
        raise ValueError("Use a PNG, JPG, WebP or GIF image.")
    try:
        decoded = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("The uploaded image could not be read.") from error
    if len(decoded) > PROFILE_IMAGE_MAX_BYTES:
        raise ValueError("Profile image must be smaller than 750 KB.")
    return value.strip()


def validate_password(value: Any) -> str:
    password = str(value or "")
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
    if len(password) > 256:
        raise ValueError("Password must be at most 256 characters.")
    return password


def generate_temporary_password() -> str:
    return "".join(
        secrets.choice(TEMPORARY_PASSWORD_ALPHABET) for _ in range(TEMPORARY_PASSWORD_LENGTH)
    )


def normalize_identity(value: Any) -> str:
    return clean_text(value).casefold()


def normalize_email(value: Any) -> str:
    return str(value or "").strip().casefold()


def talpa_email_name_parts(email: Any) -> tuple[str, str] | None:
    normalized = normalize_email(email)
    if not TALPA_EMAIL_PATTERN.match(normalized):
        return None
    local_part = normalized.split("@", 1)[0]
    first_name, last_name = local_part.split(".", 1)
    if not first_name or not last_name or "." in last_name:
        return None
    return first_name, last_name


def display_name_part(value: str) -> str:
    return "-".join(part.capitalize() for part in value.split("-") if part)


def derived_real_name(email: Any) -> dict[str, str | None]:
    parts = talpa_email_name_parts(email)
    if not parts:
        return {"first_name": None, "last_name": None, "full_name": None}
    first_name, last_name = (display_name_part(part) for part in parts)
    full_name = clean_text(f"{first_name} {last_name}")
    return {"first_name": first_name, "last_name": last_name, "full_name": full_name}


def validate_talpa_account_email(email: Any) -> str:
    normalized = normalize_email(email)
    if not talpa_email_name_parts(normalized):
        message = (
            "Use firstname.lastname@talpanetwork.com or " "firstname.lastname@talpastudios.com."
        )
        raise ValueError(message)
    return normalized


def default_name_from_email(email: str) -> str:
    local_part = clean_text(email.split("@", 1)[0].replace(".", " ").replace("_", " "))
    return local_part[:60] or "WK speler"


def normalize_answer(value: Any) -> str:
    return clean_text(value).casefold()


def top_scorer_result_name(data: dict[str, Any]) -> str:
    meta = data.get("meta", {})
    for key in (
        "world_cup_top_scorer_name",
        "top_scorer_name",
        "golden_boot_winner_name",
    ):
        value = clean_text(meta.get(key))
        if value:
            return value
    top_scorer = meta.get("world_cup_top_scorer") or meta.get("top_scorer")
    if isinstance(top_scorer, dict):
        return clean_text(top_scorer.get("name"))
    return clean_text(top_scorer)


def eliminated_team_ids(data: dict[str, Any]) -> set[str]:
    meta = data.get("meta", {})
    values = (
        meta.get("eliminated_team_ids")
        or meta.get("eliminated_teams")
        or meta.get("knocked_out_team_ids")
        or []
    )
    if not isinstance(values, list):
        return set()
    eliminated = set()
    for value in values:
        if isinstance(value, dict):
            team_id = clean_text(value.get("id") or value.get("team_id"))
        else:
            team_id = clean_text(value)
        if team_id:
            eliminated.add(team_id)
    return eliminated


def normalized_player_name(value: Any) -> str:
    return compact_name(value)


STRIKER_COLUMN_NAMES = tuple(f"striker_name_{index}" for index in range(1, STRIKER_PICK_COUNT + 1))


def row_has_key(row: Any, key: str) -> bool:
    try:
        row[key]
    except (KeyError, IndexError):
        return False
    return True


def top_scorer_pick_name(row: Any | None) -> str:
    if not row:
        return ""
    return clean_text(row["player_name"] if row_has_key(row, "player_name") else None)


def striker_pick_names(row: Any | None) -> list[str]:
    if not row:
        return []
    names = [
        name
        for name in [
            clean_text(row[column] if row_has_key(row, column) else None)
            for column in STRIKER_COLUMN_NAMES
        ]
        if name
    ]
    if names:
        return names
    return [
        name
        for name in (
            clean_text(row["player_name"] if row_has_key(row, "player_name") else None),
            clean_text(row["player_name_2"] if row_has_key(row, "player_name_2") else None),
            clean_text(row["player_name_3"] if row_has_key(row, "player_name_3") else None),
        )
        if name
    ]


def striker_pick_rows(row: Any | None) -> list[dict[str, Any]]:
    return [
        {"rank": rank, "name": name, "points_per_goal": STRIKER_GOAL_POINTS}
        for rank, name in enumerate(striker_pick_names(row), start=1)
    ]


def striker_pick_score_rows(
    row: Any | None,
    goal_counts: Counter[str] | None = None,
    goal_points: Counter[str] | None = None,
) -> list[dict[str, Any]]:
    counts = goal_counts if goal_counts is not None else goal_counts_by_player()
    points_by_player = goal_points if goal_points is not None else striker_goal_points_by_player()
    scored_rows = []
    for pick in striker_pick_rows(row):
        goals = genai_service.player_counter_value(counts, pick["name"])
        scored_rows.append(
            {
                **pick,
                "goals": goals,
                "points": genai_service.player_counter_value(points_by_player, pick["name"]),
            }
        )
    return scored_rows


def accepted_match_scorer_links(conn: Any) -> dict[str, str]:
    rows = execute(
        conn,
        """
        SELECT target_id, matched_player_name
        FROM player_candidate_links
        WHERE target_type = ?
          AND confidence = 'high'
          AND COALESCE(TRIM(matched_player_name), '') <> ''
        """,
        (genai_service.GENAI_TARGET_MATCH_SCORER,),
    ).fetchall()
    return {row["target_id"]: row["matched_player_name"] for row in rows}


def scorer_names_with_genai_link(row: Any, scorer_links: dict[str, str]) -> list[str]:
    raw_name = clean_text(row["player_name"])
    names = [raw_name] if raw_name else []
    linked_name = clean_text(
        scorer_links.get(genai_service.notification_target_id(row["match_id"], row["player_name"]))
    )
    if linked_name and normalize_answer(linked_name) not in {
        normalize_answer(name) for name in names
    }:
        names.append(linked_name)
    return names


def goal_counts_and_points_by_player(
    data: dict[str, Any] | None = None,
) -> tuple[Counter[str], Counter[str]]:
    matches_by_id = {match["id"]: match for match in data.get("matches", [])} if data else {}
    with get_db() as conn:
        rows = execute(
            conn,
            """
            SELECT match_id, player_name, event_type, detail, comments
            FROM match_events
            WHERE LOWER(event_type) = 'goal'
            """,
        ).fetchall()
        scorer_links = accepted_match_scorer_links(conn)
    counts: Counter[str] = Counter()
    points: Counter[str] = Counter()
    for row in rows:
        detail = normalize_answer(row["detail"])
        comments = normalize_answer(row["comments"])
        if "own goal" in detail or "own goal" in comments:
            continue
        keys = {
            key
            for scorer_name in scorer_names_with_genai_link(row, scorer_links)
            for key in genai_service.player_counter_keys(scorer_name)
        }
        if keys:
            match = matches_by_id.get(row["match_id"]) if matches_by_id else None
            multiplier = float(score_rule_for_match(match).get("multiplier", 1.0)) if match else 1.0
            goal_points = round_match_points(STRIKER_GOAL_POINTS * multiplier)
            for key in keys:
                counts[key] += 1
                points[key] += goal_points
    return counts, points


def goal_counts_by_player(data: dict[str, Any] | None = None) -> Counter[str]:
    counts, _points = goal_counts_and_points_by_player(data)
    return counts


def striker_goal_points_by_player(data: dict[str, Any] | None = None) -> Counter[str]:
    _counts, points = goal_counts_and_points_by_player(data)
    return points


def top_scorer_prediction_points(
    data: dict[str, Any],
    player_name: str | None,
) -> int:
    result_name = top_scorer_result_name(data)
    if result_name and normalize_answer(result_name) == normalize_answer(player_name):
        return TOP_SCORER_POINTS
    return 0


def striker_prediction_points(
    picks: list[str],
    goal_counts: Counter[str] | None = None,
    goal_points: Counter[str] | None = None,
) -> int:
    counts = goal_counts if goal_counts is not None else goal_counts_by_player()
    points_by_player = goal_points if goal_points is not None else striker_goal_points_by_player()
    return sum(
        genai_service.player_counter_value(points_by_player, player_name)
        for player_name in picks
        if genai_service.player_counter_value(counts, player_name)
    )


def striker_points_by_match_for_picks(
    data: dict[str, Any],
    picks: list[str],
) -> dict[str, dict[str, Any]]:
    if not picks:
        return {}
    pick_keys = {
        key: pick for pick in picks for key in genai_service.player_counter_keys(pick) if key
    }
    if not pick_keys:
        return {}
    matches_by_id = {match["id"]: match for match in data.get("matches", [])}
    with get_db() as conn:
        rows = execute(
            conn,
            """
            SELECT match_id, player_name, event_type, detail, comments
            FROM match_events
            WHERE LOWER(event_type) = 'goal'
            """,
        ).fetchall()
        scorer_links = accepted_match_scorer_links(conn)
    by_match: dict[str, dict[str, Any]] = {}
    for row in rows:
        detail = normalize_answer(row["detail"])
        comments = normalize_answer(row["comments"])
        if "own goal" in detail or "own goal" in comments:
            continue
        matched_pick = next(
            (
                pick_keys[key]
                for scorer_name in scorer_names_with_genai_link(row, scorer_links)
                for key in genai_service.player_counter_keys(scorer_name)
                if key in pick_keys
            ),
            None,
        )
        if not matched_pick:
            continue
        match = matches_by_id.get(row["match_id"])
        multiplier = float(score_rule_for_match(match).get("multiplier", 1.0)) if match else 1.0
        goal_points = round_match_points(STRIKER_GOAL_POINTS * multiplier)
        entry = by_match.setdefault(
            row["match_id"],
            {"points": 0, "scorers": {}, "multiplier": multiplier},
        )
        entry["points"] += goal_points
        scorer = entry["scorers"].setdefault(
            matched_pick,
            {"name": matched_pick, "goals": 0, "points": 0},
        )
        scorer["goals"] += 1
        scorer["points"] += goal_points
    return {
        match_id: {
            **entry,
            "scorers": sorted(
                entry["scorers"].values(),
                key=lambda scorer: (-scorer["points"], scorer["name"]),
            ),
        }
        for match_id, entry in by_match.items()
    }


def normalize_api_name(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return "".join(char.casefold() if char.isalnum() else " " for char in ascii_text)


def compact_name(value: Any) -> str:
    return " ".join(normalize_api_name(value).split())


API_FOOTBALL_TEAM_ALIASES = {
    "bosnia herz egovina": "bih",
    "bosnia and herzegovina": "bih",
    "bosnia herzegovina": "bih",
    "cabo verde": "cpv",
    "cape verde": "cpv",
    "cape verde islands": "cpv",
    "congo dr": "cod",
    "curacao": "cuw",
    "czech republic": "cze",
    "czechia": "cze",
    "dr congo": "cod",
    "england": "eng",
    "ha ti": "hai",
    "ivory coast": "civ",
    "korea republic": "kor",
    "netherlands": "ned",
    "paraguay": "par",
    "republic of korea": "kor",
    "scotland": "sco",
    "south korea": "kor",
    "turkey": "tur",
    "turkiye": "tur",
    "united states": "usa",
    "united states of america": "usa",
    "usa": "usa",
}


def local_team_id_from_name(name: Any, data: dict[str, Any]) -> str | None:
    normalized = compact_name(name)
    if normalized in API_FOOTBALL_TEAM_ALIASES:
        return API_FOOTBALL_TEAM_ALIASES[normalized]

    by_name = {compact_name(team["name"]): team["id"] for team in data["teams"]}
    by_code = {compact_name(team["code"]): team["id"] for team in data["teams"]}
    return by_name.get(normalized) or by_code.get(normalized)


def int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def bool_int(value: bool) -> int:
    return 1 if value else 0


def list_value(value: Any) -> list[Any]:
    if not value:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def api_football_request_count_today() -> int:
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    with get_db() as conn:
        row = execute(
            conn,
            """
            SELECT COUNT(*) AS count
            FROM api_football_requests
            WHERE requested_at >= ?
            """,
            (today_start,),
        ).fetchone()
    return int(row["count"] if row else 0)


# API-Football provider adapter boundary. Functions in this section know the
# provider's endpoints, payload names, IDs, and request accounting.
def record_api_football_request(
    endpoint: str,
    params: dict[str, Any],
    status_code: int | None,
    ok: bool,
    error: str | None = None,
) -> None:
    with get_db() as conn:
        execute(
            conn,
            """
            INSERT INTO api_football_requests (
                endpoint, params_json, status_code, ok, error, requested_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                endpoint,
                json.dumps(params, sort_keys=True),
                status_code,
                bool_int(ok),
                error,
            ),
        )


def api_football_get(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    if not API_FOOTBALL_KEY:
        raise RuntimeError("API_FOOTBALL_KEY is not configured.")

    query = urlencode({key: value for key, value in params.items() if value is not None})
    url = f"{API_FOOTBALL_BASE_URL}/{endpoint.lstrip('/')}"
    if query:
        url = f"{url}?{query}"
    request_obj = Request(url, headers={"x-apisports-key": API_FOOTBALL_KEY})

    status_code = None
    try:
        with urlopen(request_obj, timeout=20) as response:
            status_code = response.status
            payload = json.loads(response.read().decode("utf-8"))
        errors = payload.get("errors")
        if errors:
            record_api_football_request(endpoint, params, status_code, False, str(errors)[:500])
            raise RuntimeError(f"API-Football returned errors: {errors}")
        record_api_football_request(endpoint, params, status_code, True)
        return payload
    except HTTPError as error:
        status_code = error.code
        body = error.read().decode("utf-8", errors="replace")
        record_api_football_request(endpoint, params, status_code, False, body[:500])
        raise RuntimeError(f"API-Football HTTP {status_code}: {body[:160]}") from error
    except (URLError, TimeoutError) as error:
        record_api_football_request(endpoint, params, status_code, False, str(error)[:500])
        raise RuntimeError(f"API-Football request failed: {error}") from error


def api_football_status() -> dict[str, Any]:
    with get_db() as conn:
        team_linked_row = execute(
            conn, "SELECT COUNT(*) AS count FROM api_football_team_links"
        ).fetchone()
        linked_row = execute(
            conn, "SELECT COUNT(*) AS count FROM api_football_fixture_links"
        ).fetchone()
        result_row = execute(conn, "SELECT COUNT(*) AS count FROM match_results").fetchone()
        squad_row = execute(
            conn, "SELECT COUNT(*) AS count FROM api_football_team_squad_snapshots"
        ).fetchone()
        player_row = execute(conn, "SELECT COUNT(*) AS count FROM team_squad_players").fetchone()
        coach_row = execute(conn, "SELECT COUNT(*) AS count FROM team_coaches").fetchone()
        canonical_player_count = len(genai_service.canonical_squad_player_rows(conn))
        static_player_count = len(genai_service.static_squad_player_rows())
        latest_request = execute(
            conn,
            """
            SELECT requested_at, endpoint, status_code, ok, error
            FROM api_football_requests
            ORDER BY requested_at DESC
            LIMIT 1
            """,
        ).fetchone()

    return {
        "configured": bool(API_FOOTBALL_KEY),
        "protected": bool(API_FOOTBALL_SYNC_TOKEN),
        "league": API_FOOTBALL_LEAGUE_ID,
        "season": API_FOOTBALL_SEASON,
        "daily_limit": API_FOOTBALL_DAILY_LIMIT,
        "requests_today": api_football_request_count_today(),
        "linked_teams": int(team_linked_row["count"] if team_linked_row else 0),
        "linked_matches": int(linked_row["count"] if linked_row else 0),
        "synced_results": int(result_row["count"] if result_row else 0),
        "synced_squads": int(squad_row["count"] if squad_row else 0),
        "squad_players": int(player_row["count"] if player_row else 0),
        "static_squad_players": static_player_count,
        "canonical_squad_players": canonical_player_count,
        "coaches": int(coach_row["count"] if coach_row else 0),
        "latest_request": dict(latest_request) if latest_request else None,
    }


def apply_synced_match_results(data: dict[str, Any]) -> None:
    try:
        with get_db() as conn:
            rows = execute(
                conn,
                """
                SELECT match_id, source_fixture_id, status_long, status_short, elapsed,
                       home_score, away_score, synced_at
                FROM match_results
                """,
            ).fetchall()
    except Exception:
        logger.exception("Could not load synced match results")
        return

    by_match = {row["match_id"]: row for row in rows}
    for match in data.get("matches", []):
        row = by_match.get(match["id"])
        if not row:
            continue
        match["result_sync"] = {
            "status": row["status_short"],
            "synced_at": row["synced_at"],
        }
        if (
            row["status_short"] in API_FOOTBALL_FINAL_STATUSES
            and row["home_score"] is not None
            and row["away_score"] is not None
        ):
            match["status"] = "completed"
            match["home_score"] = int(row["home_score"])
            match["away_score"] = int(row["away_score"])


def apply_synced_team_profiles(data: dict[str, Any]) -> None:
    def player_merge_key(player: Any) -> str:
        if not isinstance(player, dict):
            return ""
        normalized = unicodedata.normalize("NFKD", str(player.get("name") or ""))
        without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
        return re.sub(r"[^a-z0-9]", "", without_marks.casefold())

    def merged_squad(synced_players: list[dict[str, Any]], fallback_players: Any) -> list[Any]:
        merged: list[Any] = list(synced_players)
        seen = {key for key in (player_merge_key(player) for player in merged) if key}
        if isinstance(fallback_players, list):
            for player in fallback_players:
                key = player_merge_key(player)
                if not key or key in seen:
                    continue
                merged.append(player)
                seen.add(key)
        return merged

    try:
        with get_db() as conn:
            player_rows = execute(
                conn,
                """
                SELECT local_team_id, api_player_id, player_name, age, number,
                       position, photo_url, synced_at
                FROM team_squad_players
                ORDER BY local_team_id, position, number, player_name
                """,
            ).fetchall()
            coach_rows = execute(
                conn,
                """
                SELECT local_team_id, api_coach_id, coach_name, age, nationality,
                       photo_url, synced_at
                FROM team_coaches
                ORDER BY local_team_id, coach_name
                """,
            ).fetchall()
            snapshot_rows = execute(
                conn,
                """
                SELECT local_team_id, api_team_id, synced_at
                FROM api_football_team_squad_snapshots
                """,
            ).fetchall()
    except Exception:
        logger.exception("Could not load synced team profiles")
        return

    players_by_team: dict[str, list[dict[str, Any]]] = {}
    for row in player_rows:
        player = {
            "id": row["api_player_id"],
            "name": row["player_name"],
            "age": row["age"],
            "number": row["number"],
            "position": row["position"],
            "photo": row["photo_url"],
        }
        players_by_team.setdefault(row["local_team_id"], []).append(
            {key: value for key, value in player.items() if value is not None}
        )

    coaches_by_team: dict[str, list[dict[str, Any]]] = {}
    for row in coach_rows:
        coach = {
            "id": row["api_coach_id"],
            "name": row["coach_name"],
            "role": "Head coach",
            "age": row["age"],
            "country": row["nationality"],
            "photo": row["photo_url"],
        }
        coaches_by_team.setdefault(row["local_team_id"], []).append(
            {key: value for key, value in coach.items() if value is not None}
        )

    snapshots_by_team = {row["local_team_id"]: row for row in snapshot_rows}
    for team in data.get("teams", []):
        local_team_id = team.get("id")
        if not local_team_id:
            continue
        players = players_by_team.get(local_team_id)
        coaches = coaches_by_team.get(local_team_id)
        snapshot = snapshots_by_team.get(local_team_id)
        if not players and not coaches and not snapshot:
            continue

        profile = dict(team.get("profile") or team.get("team_profile") or {})
        if players:
            profile["squad"] = merged_squad(players, profile.get("squad"))
        if coaches:
            profile["head_coach"] = coaches[0]
            profile["coaching_staff"] = coaches
        if snapshot:
            profile["squad_sync"] = {"synced_at": snapshot["synced_at"]}
            sources = list_value(profile.get("sources"))
            if not any(
                isinstance(source, dict) and source.get("label") == "Squad sync"
                for source in sources
            ):
                sources.append({"label": "Squad sync"})
            profile["sources"] = sources
        team["profile"] = profile


def api_fixture_datetime(api_fixture: dict[str, Any]) -> datetime | None:
    return parse_iso_datetime(api_fixture.get("fixture", {}).get("date"))


def provider_team_mapping(
    match: dict[str, Any], fixture: dict[str, Any], data: dict[str, Any]
) -> dict[int, str]:
    teams = fixture.get("teams", {})
    mapping: dict[int, str] = {}
    for side in ("home", "away"):
        api_team = teams.get(side) or {}
        api_team_id = int_or_none(api_team.get("id"))
        local_team_id = local_team_id_from_name(api_team.get("name"), data)
        if api_team_id is not None and local_team_id:
            mapping[api_team_id] = local_team_id

    if not mapping:
        home_id = int_or_none((teams.get("home") or {}).get("id"))
        away_id = int_or_none((teams.get("away") or {}).get("id"))
        if home_id is not None:
            mapping[home_id] = match["home_team_id"]
        if away_id is not None:
            mapping[away_id] = match["away_team_id"]
    return mapping


def local_score_from_fixture(
    match: dict[str, Any], fixture: dict[str, Any], data: dict[str, Any]
) -> tuple[int | None, int | None]:
    goals = fixture.get("goals") or {}
    api_home_score = int_or_none(goals.get("home"))
    api_away_score = int_or_none(goals.get("away"))
    if api_home_score is None or api_away_score is None:
        return None, None

    mapping = provider_team_mapping(match, fixture, data)
    api_home_id = int_or_none((fixture.get("teams", {}).get("home") or {}).get("id"))
    api_away_id = int_or_none((fixture.get("teams", {}).get("away") or {}).get("id"))
    api_home_local = mapping.get(api_home_id) if api_home_id is not None else None
    api_away_local = mapping.get(api_away_id) if api_away_id is not None else None

    if api_home_local == match["home_team_id"] and api_away_local == match["away_team_id"]:
        return api_home_score, api_away_score
    if api_home_local == match["away_team_id"] and api_away_local == match["home_team_id"]:
        return api_away_score, api_home_score
    return api_home_score, api_away_score


def team_conceded_by_local_id(
    match: dict[str, Any],
    fixture: dict[str, Any],
    data: dict[str, Any],
) -> dict[str, int]:
    home_score, away_score = local_score_from_fixture(match, fixture, data)
    if home_score is None or away_score is None:
        return {}
    return {
        match["home_team_id"]: away_score,
        match["away_team_id"]: home_score,
    }


def upsert_api_football_team_link(
    conn: Any,
    local_team_id: str | None,
    api_team_id: int | None,
    api_team_name: str | None,
    confidence: str,
) -> None:
    if not local_team_id or api_team_id is None:
        return
    execute(
        conn,
        """
        INSERT INTO api_football_team_links (
            local_team_id, api_team_id, api_team_name, confidence, linked_at
        )
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(local_team_id)
        DO UPDATE SET api_team_id = excluded.api_team_id,
                      api_team_name = excluded.api_team_name,
                      confidence = excluded.confidence,
                      linked_at = CURRENT_TIMESTAMP
        """,
        (local_team_id, api_team_id, api_team_name, confidence),
    )


def api_football_link_fixtures(data: dict[str, Any]) -> dict[str, Any]:
    payload = api_football_get(
        "fixtures",
        {"league": API_FOOTBALL_LEAGUE_ID, "season": API_FOOTBALL_SEASON},
    )
    fixtures = payload.get("response", [])
    matches_by_pair: dict[frozenset[str], list[dict[str, Any]]] = {}
    for match in data["matches"]:
        pair = frozenset([match["home_team_id"], match["away_team_id"]])
        matches_by_pair.setdefault(pair, []).append(match)

    linked = 0
    skipped = 0
    with get_db() as conn:
        for fixture in fixtures:
            teams = fixture.get("teams", {})
            home_team = teams.get("home") or {}
            away_team = teams.get("away") or {}
            home_local = local_team_id_from_name(home_team.get("name"), data)
            away_local = local_team_id_from_name(away_team.get("name"), data)
            api_fixture_id = int_or_none((fixture.get("fixture") or {}).get("id"))
            if not home_local or not away_local or api_fixture_id is None:
                skipped += 1
                continue

            candidates = matches_by_pair.get(frozenset([home_local, away_local]), [])
            fixture_date = api_fixture_datetime(fixture)
            if not candidates:
                skipped += 1
                continue
            if fixture_date:
                match = min(
                    candidates,
                    key=lambda candidate: abs(
                        (match_kickoff(candidate) - fixture_date).total_seconds()
                    ),
                )
                delta_seconds = abs((match_kickoff(match) - fixture_date).total_seconds())
                if delta_seconds > 36 * 60 * 60:
                    skipped += 1
                    continue
                confidence = "team_pair_and_kickoff"
            else:
                match = candidates[0]
                confidence = "team_pair"

            execute(
                conn,
                """
                INSERT INTO api_football_fixture_links (
                    match_id, api_fixture_id, api_home_team_id, api_away_team_id,
                    api_home_team_name, api_away_team_name, confidence, linked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(match_id)
                DO UPDATE SET api_fixture_id = excluded.api_fixture_id,
                              api_home_team_id = excluded.api_home_team_id,
                              api_away_team_id = excluded.api_away_team_id,
                              api_home_team_name = excluded.api_home_team_name,
                              api_away_team_name = excluded.api_away_team_name,
                              confidence = excluded.confidence,
                              linked_at = CURRENT_TIMESTAMP
                """,
                (
                    match["id"],
                    api_fixture_id,
                    int_or_none(home_team.get("id")),
                    int_or_none(away_team.get("id")),
                    home_team.get("name"),
                    away_team.get("name"),
                    confidence,
                ),
            )
            upsert_api_football_team_link(
                conn,
                home_local,
                int_or_none(home_team.get("id")),
                home_team.get("name"),
                confidence,
            )
            upsert_api_football_team_link(
                conn,
                away_local,
                int_or_none(away_team.get("id")),
                away_team.get("name"),
                confidence,
            )
            linked += 1

    return {"linked": linked, "skipped": skipped, "fixtures_seen": len(fixtures)}


def api_football_fixture_links() -> dict[str, int]:
    with get_db() as conn:
        rows = execute(
            conn,
            "SELECT match_id, api_fixture_id FROM api_football_fixture_links",
        ).fetchall()
    return {row["match_id"]: int(row["api_fixture_id"]) for row in rows}


# Provider-agnostic sync orchestration boundary. Functions in this section work
# with app match/team IDs, sync attempts, current facts, and admin notifications.
def match_summary(match: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    teams_by_id = {team["id"]: team for team in data.get("teams", [])}
    home_team = teams_by_id.get(match.get("home_team_id"), {})
    away_team = teams_by_id.get(match.get("away_team_id"), {})
    return {
        "match_id": match.get("id"),
        "match_number": match.get("match_number"),
        "home_team_id": match.get("home_team_id"),
        "away_team_id": match.get("away_team_id"),
        "home_team_name": home_team.get("name") or match.get("home_team_id"),
        "away_team_name": away_team.get("name") or match.get("away_team_id"),
        "kickoff_utc": iso_utc(match_kickoff(match)),
    }


def synced_result_rows() -> dict[str, Any]:
    with get_db() as conn:
        rows = execute(
            conn,
            """
            SELECT mr.match_id,
                   mr.status_short,
                   mr.home_score,
                   mr.away_score,
                   mr.synced_at,
                   COUNT(
                       CASE WHEN LOWER(me.event_type) = 'goal' THEN 1 END
                   ) AS goal_event_count
            FROM match_results mr
            LEFT JOIN match_events me ON me.match_id = mr.match_id
            GROUP BY mr.match_id,
                     mr.status_short,
                     mr.home_score,
                     mr.away_score,
                     mr.synced_at
            """,
        ).fetchall()
    return {row["match_id"]: row for row in rows}


def match_has_final_result(match_id: str, rows: dict[str, Any]) -> bool:
    row = rows.get(match_id)
    return bool(row and row["status_short"] in API_FOOTBALL_FINAL_STATUSES)


def match_has_required_result_facts(match_id: str, rows: dict[str, Any]) -> bool:
    row = rows.get(match_id)
    if not row or row["status_short"] not in API_FOOTBALL_FINAL_STATUSES:
        return False
    home_score = int_or_none(row["home_score"])
    away_score = int_or_none(row["away_score"])
    if home_score is None or away_score is None:
        return False
    total_goals = max(0, home_score) + max(0, away_score)
    if total_goals == 0:
        return True
    return int(row["goal_event_count"] or 0) >= total_goals


def missing_result_match_ids(
    data: dict[str, Any],
    now: datetime | None = None,
) -> list[str]:
    current = now or utc_now()
    result_rows = synced_result_rows()
    return [
        match["id"]
        for match in sorted(data["matches"], key=match_kickoff)
        if match.get("home_team_id")
        and match.get("away_team_id")
        and match_kickoff(match) + API_FOOTBALL_POSTMATCH_BUFFER <= current
        and not match_has_required_result_facts(match["id"], result_rows)
    ]


def due_api_football_matches(
    data: dict[str, Any],
    force: bool = False,
    limit: int = API_FOOTBALL_MAX_BATCH_SIZE,
) -> list[dict[str, Any]]:
    return [
        item["match"] for item in due_api_football_match_attempts(data, force=force, limit=limit)
    ]


def due_api_football_match_attempts(
    data: dict[str, Any],
    force: bool = False,
    dry_run: bool = False,
    daily_sweep: bool = False,
    limit: int = API_FOOTBALL_MAX_BATCH_SIZE,
    match_id: str | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    current = now or utc_now()
    limit = max(1, min(API_FOOTBALL_MAX_BATCH_SIZE, int(limit)))
    candidates = []
    terminal_by_match: dict[str, set[str]] = {}
    results_by_match: dict[str, Any] = {}
    if not dry_run:
        with get_db() as conn:
            result_rows = execute(
                conn,
                """
                SELECT mr.match_id,
                       mr.status_short,
                       mr.home_score,
                       mr.away_score,
                       COUNT(
                           CASE WHEN LOWER(me.event_type) = 'goal' THEN 1 END
                       ) AS goal_event_count
                FROM match_results mr
                LEFT JOIN match_events me ON me.match_id = mr.match_id
                WHERE mr.status_short IN (?, ?, ?)
                  AND mr.home_score IS NOT NULL
                  AND mr.away_score IS NOT NULL
                GROUP BY mr.match_id,
                         mr.status_short,
                         mr.home_score,
                         mr.away_score
                """,
                tuple(API_FOOTBALL_FINAL_STATUSES),
            ).fetchall()
            results_by_match = {
                row["match_id"]: row
                for row in result_rows
                if match_has_required_result_facts(row["match_id"], {row["match_id"]: row})
            }
            for match in data["matches"]:
                if match_id and match["id"] != match_id:
                    continue
                terminal_by_match[match["id"]] = terminal_sync_attempt_kinds(
                    conn,
                    provider_key=API_FOOTBALL_PROVIDER_KEY,
                    target_type=SYNC_TARGET_MATCH_RESULT,
                    target_id=match["id"],
                )

    for match in sorted(data["matches"], key=match_kickoff):
        if match_id and match["id"] != match_id:
            continue
        if not match.get("home_team_id") or not match.get("away_team_id"):
            continue
        if force and match_id:
            attempt_kind = SYNC_ATTEMPT_MANUAL
            scheduled_for = current
        elif daily_sweep:
            terminal_attempt_kinds = terminal_by_match.get(match["id"], set())
            has_result = match["id"] in results_by_match
            latest_due_kind = latest_due_result_sync_attempt_kind(match, current)
            if latest_due_kind is None:
                continue
            if (
                not has_result
                and SYNC_ATTEMPT_EARLY_POST_MATCH in terminal_attempt_kinds
                and SYNC_ATTEMPT_FIRST_POST_MATCH in terminal_attempt_kinds
                and SYNC_ATTEMPT_SECOND_POST_MATCH in terminal_attempt_kinds
            ):
                attempt_kind = SYNC_ATTEMPT_MISSING_DATA_RETRY
                scheduled_for = current
            elif latest_due_kind in terminal_attempt_kinds:
                continue
            else:
                attempt_kind = latest_due_kind
                scheduled_for = result_sync_scheduled_for(match, attempt_kind)
        else:
            terminal_attempt_kinds = terminal_by_match.get(match["id"], set())
            due_kinds = due_result_sync_attempt_kinds(
                match,
                now=current,
                terminal_attempt_kinds=terminal_attempt_kinds,
                has_result=match["id"] in results_by_match,
            )
            if not due_kinds:
                continue
            attempt_kind = due_kinds[0]
            scheduled_for = (
                current
                if attempt_kind == SYNC_ATTEMPT_MISSING_DATA_RETRY
                else result_sync_scheduled_for(match, attempt_kind)
            )
        candidates.append(
            {
                "match": match,
                "match_id": match["id"],
                "attempt_kind": attempt_kind,
                "scheduled_for": scheduled_for,
            }
        )
        if len(candidates) >= limit:
            break
    return candidates


def event_key(event: dict[str, Any], index: int) -> str:
    time_data = event.get("time") or {}
    team = event.get("team") or {}
    player = event.get("player") or {}
    assist = event.get("assist") or {}
    parts = [
        time_data.get("elapsed"),
        time_data.get("extra"),
        team.get("id"),
        player.get("id") or player.get("name"),
        assist.get("id") or assist.get("name"),
        event.get("type"),
        event.get("detail"),
        event.get("comments"),
        index,
    ]
    return "|".join(str(part or "") for part in parts)


def store_api_football_fixture_snapshot(
    conn: Any,
    match: dict[str, Any],
    fixture: dict[str, Any],
    data: dict[str, Any],
) -> dict[str, Any]:
    api_fixture = fixture.get("fixture") or {}
    api_fixture_id = int_or_none(api_fixture.get("id"))
    if api_fixture_id is None:
        raise ValueError(f"API-Football fixture for {match['id']} has no fixture id.")

    status = api_fixture.get("status") or {}
    status_short = status.get("short")
    home_score, away_score = local_score_from_fixture(match, fixture, data)
    elapsed = int_or_none(status.get("elapsed"))
    mapping = provider_team_mapping(match, fixture, data)
    conceded = team_conceded_by_local_id(match, fixture, data)
    final = status_short in API_FOOTBALL_FINAL_STATUSES

    execute(
        conn,
        """
        INSERT INTO api_football_fixture_snapshots (
            match_id, api_fixture_id, payload_json, synced_at
        )
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(match_id)
        DO UPDATE SET api_fixture_id = excluded.api_fixture_id,
                      payload_json = excluded.payload_json,
                      synced_at = CURRENT_TIMESTAMP
        """,
        (match["id"], api_fixture_id, json.dumps(fixture, sort_keys=True)),
    )
    if USING_POSTGRES:
        history_row = execute(
            conn,
            """
            INSERT INTO api_football_fixture_snapshot_history (
                match_id, api_fixture_id, payload_json, synced_at
            )
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (match["id"], api_fixture_id, json.dumps(fixture, sort_keys=True)),
        ).fetchone()
        raw_snapshot_id = int(history_row["id"]) if history_row else None
    else:
        history_cursor = execute(
            conn,
            """
            INSERT INTO api_football_fixture_snapshot_history (
                match_id, api_fixture_id, payload_json, synced_at
            )
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (match["id"], api_fixture_id, json.dumps(fixture, sort_keys=True)),
        )
        raw_snapshot_id = (
            int(history_cursor.lastrowid) if history_cursor.lastrowid is not None else None
        )
    existing_result = execute(
        conn,
        "SELECT source FROM match_results WHERE match_id = ?",
        (match["id"],),
    ).fetchone()
    manual_result = existing_result is not None and existing_result["source"] == "manual"
    if not manual_result:
        execute(
            conn,
            """
            INSERT INTO match_results (
                match_id, source, source_fixture_id, status_long, status_short,
                elapsed, home_score, away_score, synced_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(match_id)
            DO UPDATE SET source = excluded.source,
                          source_fixture_id = excluded.source_fixture_id,
                          status_long = excluded.status_long,
                          status_short = excluded.status_short,
                          elapsed = excluded.elapsed,
                          home_score = excluded.home_score,
                          away_score = excluded.away_score,
                          synced_at = CURRENT_TIMESTAMP
            """,
            (
                match["id"],
                API_FOOTBALL_PROVIDER_KEY,
                api_fixture_id,
                status.get("long"),
                status_short,
                elapsed,
                home_score,
                away_score,
            ),
        )

    manual_events = execute(
        conn,
        """
        SELECT 1 FROM match_events
        WHERE match_id = ? AND provider_event_key LIKE ?
        LIMIT 1
        """,
        (match["id"], "manual:%"),
    ).fetchone()
    if manual_events is None:
        execute(conn, "DELETE FROM match_events WHERE match_id = ?", (match["id"],))
        for index, event in enumerate(fixture.get("events") or []):
            team = event.get("team") or {}
            player = event.get("player") or {}
            assist = event.get("assist") or {}
            api_team_id = int_or_none(team.get("id"))
            time_data = event.get("time") or {}
            execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, source_fixture_id, elapsed, extra,
                    local_team_id, api_team_id, team_name, api_player_id, player_name,
                    api_assist_id, assist_name, event_type, detail, comments, raw_json,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    match["id"],
                    event_key(event, index),
                    api_fixture_id,
                    int_or_none(time_data.get("elapsed")),
                    int_or_none(time_data.get("extra")),
                    mapping.get(api_team_id) if api_team_id is not None else None,
                    api_team_id,
                    team.get("name"),
                    int_or_none(player.get("id")),
                    player.get("name"),
                    int_or_none(assist.get("id")),
                    assist.get("name"),
                    event.get("type") or "",
                    event.get("detail"),
                    event.get("comments"),
                    json.dumps(event, sort_keys=True),
                ),
            )

    execute(conn, "DELETE FROM match_clean_sheets WHERE match_id = ?", (match["id"],))
    if final:
        clean_sheet_api_ids = {
            api_team_id
            for api_team_id, local_team_id in mapping.items()
            if conceded.get(local_team_id) == 0
        }
        teams = fixture.get("teams") or {}
        for side in ("home", "away"):
            api_team = teams.get(side) or {}
            api_team_id = int_or_none(api_team.get("id"))
            if api_team_id is None or api_team_id not in clean_sheet_api_ids:
                continue
            local_team_id = mapping.get(api_team_id)
            if not local_team_id:
                continue
            execute(
                conn,
                """
                INSERT INTO match_clean_sheets (
                    match_id, local_team_id, api_team_id, team_name, source_fixture_id, synced_at
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(match_id, local_team_id)
                DO UPDATE SET api_team_id = excluded.api_team_id,
                              team_name = excluded.team_name,
                              source_fixture_id = excluded.source_fixture_id,
                              synced_at = CURRENT_TIMESTAMP
                """,
                (match["id"], local_team_id, api_team_id, api_team.get("name"), api_fixture_id),
            )

    manual_stats = execute(
        conn,
        """
        SELECT 1 FROM player_match_stats
        WHERE match_id = ? AND provider_player_key LIKE ?
        LIMIT 1
        """,
        (match["id"], "manual:%"),
    ).fetchone()
    if manual_stats is None:
        execute(conn, "DELETE FROM player_match_stats WHERE match_id = ?", (match["id"],))
        for team_block in fixture.get("players") or []:
            api_team = team_block.get("team") or {}
            api_team_id = int_or_none(api_team.get("id"))
            local_team_id = mapping.get(api_team_id) if api_team_id is not None else None
            team_clean_sheet = bool(final and local_team_id and conceded.get(local_team_id) == 0)
            for player_block in team_block.get("players") or []:
                player = player_block.get("player") or {}
                statistics = (player_block.get("statistics") or [{}])[0] or {}
                games = statistics.get("games") or {}
                goals = statistics.get("goals") or {}
                cards = statistics.get("cards") or {}
                api_player_id = int_or_none(player.get("id"))
                player_name = player.get("name") or "Unknown"
                provider_player_key = (
                    str(api_player_id)
                    if api_player_id is not None and api_player_id > 0
                    else compact_name(player_name)
                )
                minutes = int_or_none(games.get("minutes")) or 0
                execute(
                    conn,
                    """
                    INSERT INTO player_match_stats (
                        match_id, provider_player_key, source_fixture_id, local_team_id,
                        api_team_id, team_name, api_player_id, player_name, minutes,
                        position, rating, goals, assists, yellow_cards, red_cards,
                        clean_sheet, raw_json, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        match["id"],
                        provider_player_key,
                        api_fixture_id,
                        local_team_id,
                        api_team_id,
                        api_team.get("name"),
                        api_player_id,
                        player_name,
                        minutes,
                        games.get("position"),
                        games.get("rating"),
                        int_or_none(goals.get("total")) or 0,
                        int_or_none(goals.get("assists")) or 0,
                        int_or_none(cards.get("yellow")) or 0,
                        int_or_none(cards.get("red")) or 0,
                        bool_int(team_clean_sheet and minutes > 0),
                        json.dumps(player_block, sort_keys=True),
                    ),
                )

    return {
        "match_id": match["id"],
        "fixture_id": api_fixture_id,
        "status": status_short,
        "final": final,
        "home_score": home_score,
        "away_score": away_score,
        "raw_snapshot_id": raw_snapshot_id,
        "events": len(fixture.get("events") or []),
        "player_rows": sum(
            len(block.get("players") or []) for block in fixture.get("players") or []
        ),
    }


def restore_provider_facts_from_latest_snapshot(
    conn: Any,
    *,
    match_id: str,
    data: dict[str, Any],
    clear_result: bool = False,
    clear_events: bool = False,
    clear_stats: bool = False,
) -> bool:
    row = execute(
        conn,
        """
        SELECT payload_json
        FROM api_football_fixture_snapshot_history
        WHERE match_id = ?
        ORDER BY synced_at DESC, id DESC
        LIMIT 1
        """,
        (match_id,),
    ).fetchone()
    if row is None:
        if clear_result:
            execute(
                conn,
                "DELETE FROM match_results WHERE match_id = ? AND source = 'manual'",
                (match_id,),
            )
        if clear_events:
            execute(
                conn,
                """
                DELETE FROM match_events
                WHERE match_id = ? AND provider_event_key LIKE ?
                """,
                (match_id, "manual:%"),
            )
        if clear_stats:
            execute(
                conn,
                """
                DELETE FROM player_match_stats
                WHERE match_id = ? AND provider_player_key LIKE ?
                """,
                (match_id, "manual:%"),
            )
        return False

    match = match_by_id(data, match_id)
    if match is None:
        return False
    if clear_result:
        execute(
            conn,
            "DELETE FROM match_results WHERE match_id = ? AND source = 'manual'",
            (match_id,),
        )
    if clear_events:
        execute(
            conn,
            """
            DELETE FROM match_events
            WHERE match_id = ? AND provider_event_key LIKE ?
            """,
            (match_id, "manual:%"),
        )
    if clear_stats:
        execute(
            conn,
            """
            DELETE FROM player_match_stats
            WHERE match_id = ? AND provider_player_key LIKE ?
            """,
            (match_id, "manual:%"),
        )
    store_api_football_fixture_snapshot(conn, match, json.loads(row["payload_json"]), data)
    return True


def run_api_football_completed_sync(
    data: dict[str, Any],
    force: bool = False,
    dry_run: bool = False,
    daily_sweep: bool = False,
    limit: int = API_FOOTBALL_MAX_BATCH_SIZE,
    match_id: str | None = None,
    recompute_points: bool = True,
) -> dict[str, Any]:
    limit = max(1, min(API_FOOTBALL_MAX_BATCH_SIZE, int(limit)))
    candidates = due_api_football_match_attempts(
        data,
        force=force,
        dry_run=dry_run,
        daily_sweep=daily_sweep,
        limit=limit,
        match_id=match_id,
    )
    if not candidates:
        return {"ok": True, "attempts": [], "synced": [], "skipped": [], "dry_run": dry_run}

    links = api_football_fixture_links()
    linking = None
    if (
        not dry_run
        and API_FOOTBALL_KEY
        and any(item["match_id"] not in links for item in candidates)
    ):
        try:
            linking = api_football_link_fixtures(data)
            links = api_football_fixture_links()
        except Exception as error:
            linking = {"ok": False, "error": str(error)}
    linked_candidates = [item for item in candidates if item["match_id"] in links]
    skipped = [
        {
            "target_type": SYNC_TARGET_MATCH_RESULT,
            "target_id": item["match_id"],
            "match_id": item["match_id"],
            "match": match_summary(item["match"], data),
            "attempt_kind": item["attempt_kind"],
            "scheduled_for": iso_utc(item["scheduled_for"]),
            "reason": "missing_api_football_fixture_link",
            "message": "No API-Football fixture link exists for this match.",
        }
        for item in candidates
        if item["match_id"] not in links
    ]
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "candidates": [
                {
                    "target_type": SYNC_TARGET_MATCH_RESULT,
                    "target_id": item["match_id"],
                    "match_id": item["match_id"],
                    "attempt_kind": item["attempt_kind"],
                    "scheduled_for": iso_utc(item["scheduled_for"]),
                    "fixture_id": links.get(item["match_id"]),
                }
                for item in candidates
            ],
            "skipped": skipped,
        }
    if not API_FOOTBALL_KEY:
        return {"ok": False, "error": "API_FOOTBALL_KEY is not configured."}

    attempts = []
    with get_db() as conn:
        for item in skipped:
            attempt_id = create_provider_sync_attempt(
                conn,
                provider_key=API_FOOTBALL_PROVIDER_KEY,
                target_type=SYNC_TARGET_MATCH_RESULT,
                target_id=item["match_id"],
                attempt_kind=item["attempt_kind"],
                scheduled_for=parse_iso_datetime(item.get("scheduled_for")),
                status=SYNC_STATUS_SKIPPED,
            )
            finish_provider_sync_attempt(
                conn,
                attempt_id,
                status=SYNC_STATUS_SKIPPED,
                failure_code="missing_provider_fixture_link",
                failure_message="No API-Football fixture link exists for this due match.",
            )
            create_admin_sync_notification(
                conn,
                notification_type="missing_provider_link",
                target_type=SYNC_TARGET_MATCH_RESULT,
                target_id=item["match_id"],
                title="Result sync needs a fixture link",
                body="A due match could not be synced because no provider fixture link exists.",
                related_attempt_id=attempt_id,
            )
            if linking and linking.get("ok") is False:
                create_admin_sync_notification(
                    conn,
                    notification_type="provider_request_failed",
                    target_type=SYNC_TARGET_MATCH_RESULT,
                    target_id=item["match_id"],
                    title="Fixture link request failed",
                    body="The provider fixture-linking request failed before result sync.",
                    related_attempt_id=attempt_id,
                )
            create_admin_sync_notification(
                conn,
                notification_type="missing_match_data",
                target_type=SYNC_TARGET_MATCH_RESULT,
                target_id=item["match_id"],
                title="Match data is still missing",
                body=(
                    "No result data is stored for this match yet. "
                    "The sync will retry it during later result cron runs."
                ),
                related_attempt_id=attempt_id,
            )
            attempts.append({**item, "status": SYNC_STATUS_SKIPPED})
    if not linked_candidates:
        return {
            "ok": True,
            "dry_run": False,
            "attempts": attempts,
            "synced": [],
            "skipped": skipped,
            "linking": linking,
        }

    running_attempts = {}
    with get_db() as conn:
        for item in linked_candidates:
            attempt_id = create_provider_sync_attempt(
                conn,
                provider_key=API_FOOTBALL_PROVIDER_KEY,
                target_type=SYNC_TARGET_MATCH_RESULT,
                target_id=item["match_id"],
                attempt_kind=item["attempt_kind"],
                scheduled_for=item["scheduled_for"],
            )
            running_attempts[item["match_id"]] = attempt_id

    fixture_ids = [links[item["match_id"]] for item in linked_candidates]
    try:
        payload = api_football_get(
            "fixtures",
            {"ids": "-".join(str(value) for value in fixture_ids)},
        )
    except Exception as error:
        with get_db() as conn:
            for item in linked_candidates:
                attempt_id = running_attempts.get(item["match_id"])
                finish_provider_sync_attempt(
                    conn,
                    attempt_id,
                    status=SYNC_STATUS_FAILED,
                    failure_code="provider_request_failed",
                    failure_message=str(error)[:500],
                )
                create_admin_sync_notification(
                    conn,
                    notification_type="provider_request_failed",
                    target_type=SYNC_TARGET_MATCH_RESULT,
                    target_id=item["match_id"],
                    title="Result sync request failed",
                    body="A due match could not be retrieved from the provider.",
                    related_attempt_id=attempt_id,
                )
                create_admin_sync_notification(
                    conn,
                    notification_type="missing_match_data",
                    target_type=SYNC_TARGET_MATCH_RESULT,
                    target_id=item["match_id"],
                    title="Match data is still missing",
                    body=(
                        "No result data is stored for this match yet. "
                        "The sync will retry it during later result cron runs."
                    ),
                    related_attempt_id=attempt_id,
                )
                attempts.append(
                    {
                        "target_type": SYNC_TARGET_MATCH_RESULT,
                        "target_id": item["match_id"],
                        "match_id": item["match_id"],
                        "attempt_kind": item["attempt_kind"],
                        "status": SYNC_STATUS_FAILED,
                        "reason": "provider_request_failed",
                    }
                )
        return {
            "ok": False,
            "error": str(error),
            "dry_run": False,
            "attempts": attempts,
            "synced": [],
            "skipped": skipped,
            "requests_today": api_football_request_count_today(),
            "daily_limit": API_FOOTBALL_DAILY_LIMIT,
        }

    fixture_by_id = {}
    for fixture in payload.get("response", []):
        api_fixture_id = int_or_none((fixture.get("fixture") or {}).get("id"))
        if api_fixture_id is not None:
            fixture_by_id[api_fixture_id] = fixture
    synced = []
    with get_db() as conn:
        for item in linked_candidates:
            match = item["match"]
            attempt_id = running_attempts.get(item["match_id"])
            fixture = fixture_by_id.get(links[item["match_id"]])
            if fixture is None:
                skipped.append(
                    {
                        "target_type": SYNC_TARGET_MATCH_RESULT,
                        "target_id": item["match_id"],
                        "match_id": item["match_id"],
                        "attempt_kind": item["attempt_kind"],
                        "reason": "fixture_not_returned",
                    }
                )
                finish_provider_sync_attempt(
                    conn,
                    attempt_id,
                    status=SYNC_STATUS_FAILED,
                    failure_code="fixture_not_returned",
                    failure_message="Provider response did not include the requested fixture.",
                )
                create_admin_sync_notification(
                    conn,
                    notification_type="provider_request_failed",
                    target_type=SYNC_TARGET_MATCH_RESULT,
                    target_id=item["match_id"],
                    title="Result sync fixture missing",
                    body="The provider response did not include the requested fixture.",
                    related_attempt_id=attempt_id,
                )
                create_admin_sync_notification(
                    conn,
                    notification_type="missing_match_data",
                    target_type=SYNC_TARGET_MATCH_RESULT,
                    target_id=item["match_id"],
                    title="Match data is still missing",
                    body=(
                        "No result data is stored for this match yet. "
                        "The sync will retry it during later result cron runs."
                    ),
                    related_attempt_id=attempt_id,
                )
                attempts.append(
                    {
                        "target_type": SYNC_TARGET_MATCH_RESULT,
                        "target_id": item["match_id"],
                        "match_id": item["match_id"],
                        "attempt_kind": item["attempt_kind"],
                        "status": SYNC_STATUS_FAILED,
                        "reason": "fixture_not_returned",
                    }
                )
                continue
            synced_item = store_api_football_fixture_snapshot(conn, match, fixture, data)
            synced.append(synced_item)
            finish_provider_sync_attempt(
                conn,
                attempt_id,
                status=SYNC_STATUS_SUCCEEDED,
                raw_snapshot_id=synced_item.get("raw_snapshot_id"),
            )
            resolve_admin_sync_notification(
                conn,
                notification_type="missing_provider_link",
                target_type=SYNC_TARGET_MATCH_RESULT,
                target_id=item["match_id"],
            )
            resolve_admin_sync_notification(
                conn,
                notification_type="provider_request_failed",
                target_type=SYNC_TARGET_MATCH_RESULT,
                target_id=item["match_id"],
            )
            if (
                synced_item.get("final")
                and synced_item.get("home_score") is not None
                and synced_item.get("away_score") is not None
            ):
                resolve_admin_sync_notification(
                    conn,
                    notification_type="missing_match_data",
                    target_type=SYNC_TARGET_MATCH_RESULT,
                    target_id=item["match_id"],
                )
            else:
                create_admin_sync_notification(
                    conn,
                    notification_type="missing_match_data",
                    target_type=SYNC_TARGET_MATCH_RESULT,
                    target_id=item["match_id"],
                    title="Match data is still missing",
                    body=(
                        "The provider returned the fixture, but it does not have a final "
                        "score yet. The sync will retry it during later result cron runs."
                    ),
                    related_attempt_id=attempt_id,
                )
            attempts.append(
                {
                    "target_type": SYNC_TARGET_MATCH_RESULT,
                    "target_id": item["match_id"],
                    "match_id": item["match_id"],
                    "attempt_kind": item["attempt_kind"],
                    "status": SYNC_STATUS_SUCCEEDED,
                    "provider_key": API_FOOTBALL_PROVIDER_KEY,
                    "fixture_id": links[item["match_id"]],
                    "changed_facts": ["result", "events", "player_stats"],
                    "computed_points_updated": False,
                }
            )

    player_verification = None
    if synced and recompute_points:
        player_verification = recompute_all_computed_points(data)

    return {
        "ok": True,
        "dry_run": False,
        "attempts": attempts,
        "synced": synced,
        "skipped": skipped,
        "linking": linking,
        "player_database_verification": player_verification,
        "requests_today": api_football_request_count_today(),
        "daily_limit": API_FOOTBALL_DAILY_LIMIT,
    }


def api_football_team_links() -> dict[str, dict[str, Any]]:
    with get_db() as conn:
        rows = execute(
            conn,
            """
            SELECT local_team_id, api_team_id, api_team_name, confidence, linked_at
            FROM api_football_team_links
            """,
        ).fetchall()
    return {row["local_team_id"]: dict(row) for row in rows}


def seed_api_football_team_links_from_fixture_links(data: dict[str, Any]) -> int:
    matches = {match["id"]: match for match in data["matches"]}
    seeded = 0
    with get_db() as conn:
        rows = execute(
            conn,
            """
            SELECT match_id, api_home_team_id, api_away_team_id,
                   api_home_team_name, api_away_team_name, confidence
            FROM api_football_fixture_links
            """,
        ).fetchall()
        for row in rows:
            match = matches.get(row["match_id"])
            if not match:
                continue
            before = seeded
            if row["api_home_team_id"] is not None:
                upsert_api_football_team_link(
                    conn,
                    match.get("home_team_id"),
                    int(row["api_home_team_id"]),
                    row["api_home_team_name"],
                    row["confidence"],
                )
                seeded += 1
            if row["api_away_team_id"] is not None:
                upsert_api_football_team_link(
                    conn,
                    match.get("away_team_id"),
                    int(row["api_away_team_id"]),
                    row["api_away_team_name"],
                    row["confidence"],
                )
                seeded += 1
            if seeded == before:
                continue
    return seeded


def due_api_football_teams(
    data: dict[str, Any],
    force: bool = False,
    limit: int = API_FOOTBALL_SQUAD_SYNC_BATCH_SIZE,
) -> list[dict[str, Any]]:
    links = api_football_team_links()
    current = utc_now()
    due: list[dict[str, Any]] = []
    with get_db() as conn:
        snapshot_rows = execute(
            conn,
            """
            SELECT local_team_id, synced_at
            FROM api_football_team_squad_snapshots
            """,
        ).fetchall()
    synced_at_by_team = {
        row["local_team_id"]: parse_iso_datetime(row["synced_at"]) for row in snapshot_rows
    }

    for team in sorted(data["teams"], key=lambda item: item["name"]):
        link = links.get(team["id"])
        if not link:
            continue
        synced_at = synced_at_by_team.get(team["id"])
        if synced_at:
            next_refresh = synced_at + timedelta(hours=API_FOOTBALL_SQUAD_REFRESH_HOURS)
            if not force and current < next_refresh:
                continue
        due.append({"team": team, "link": link})
        if len(due) >= max(1, int(limit)):
            break
    return due


def api_football_squad_team_limit(
    *,
    requested_limit: int,
    include_coaches: bool,
) -> int:
    return max(1, min(48, int(requested_limit)))


def coach_name(coach: dict[str, Any]) -> str:
    name = clean_text(coach.get("name"))
    if name:
        return name
    return clean_text(f"{coach.get('firstname', '')} {coach.get('lastname', '')}")


def store_api_football_team_profile_snapshot(
    conn: Any,
    local_team_id: str,
    api_team_id: int,
    squad_payload: dict[str, Any],
    coach_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    squad_json = json.dumps(squad_payload, sort_keys=True)
    coach_json = json.dumps(coach_payload, sort_keys=True) if coach_payload else None
    execute(
        conn,
        """
        INSERT INTO api_football_team_squad_snapshots (
            local_team_id, api_team_id, squad_payload_json, coach_payload_json, synced_at
        )
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(local_team_id)
        DO UPDATE SET api_team_id = excluded.api_team_id,
                      squad_payload_json = excluded.squad_payload_json,
                      coach_payload_json = excluded.coach_payload_json,
                      synced_at = CURRENT_TIMESTAMP
        """,
        (local_team_id, api_team_id, squad_json, coach_json),
    )
    execute(
        conn,
        """
        INSERT INTO api_football_team_squad_snapshot_history (
            local_team_id, api_team_id, squad_payload_json, coach_payload_json, synced_at
        )
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (local_team_id, api_team_id, squad_json, coach_json),
    )

    execute(conn, "DELETE FROM team_squad_players WHERE local_team_id = ?", (local_team_id,))
    player_count = 0
    for squad_block in squad_payload.get("response") or []:
        team = squad_block.get("team") or {}
        source_team_id = int_or_none(team.get("id")) or api_team_id
        if source_team_id != api_team_id:
            continue
        for player in squad_block.get("players") or []:
            api_player_id = int_or_none(player.get("id"))
            player_name = clean_text(player.get("name")) or "Unknown"
            provider_player_key = (
                str(api_player_id)
                if api_player_id is not None and api_player_id > 0
                else compact_name(player_name)
            )
            execute(
                conn,
                """
                INSERT INTO team_squad_players (
                    local_team_id, provider_player_key, source_team_id, api_player_id,
                    player_name, age, number, position, photo_url, raw_json, synced_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    local_team_id,
                    provider_player_key,
                    source_team_id,
                    api_player_id,
                    player_name,
                    int_or_none(player.get("age")),
                    int_or_none(player.get("number")),
                    player.get("position"),
                    player.get("photo"),
                    json.dumps(player, sort_keys=True),
                ),
            )
            player_count += 1

    execute(conn, "DELETE FROM team_coaches WHERE local_team_id = ?", (local_team_id,))
    coach_count = 0
    if coach_payload:
        for coach in coach_payload.get("response") or []:
            api_coach_id = int_or_none(coach.get("id"))
            name = coach_name(coach) or "Unknown"
            provider_coach_key = (
                str(api_coach_id)
                if api_coach_id is not None and api_coach_id > 0
                else compact_name(name)
            )
            execute(
                conn,
                """
                INSERT INTO team_coaches (
                    local_team_id, provider_coach_key, source_team_id, api_coach_id,
                    coach_name, age, nationality, photo_url, raw_json, synced_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    local_team_id,
                    provider_coach_key,
                    api_team_id,
                    api_coach_id,
                    name,
                    int_or_none(coach.get("age")),
                    coach.get("nationality"),
                    coach.get("photo"),
                    json.dumps(coach, sort_keys=True),
                ),
            )
            coach_count += 1

    return {
        "team_id": local_team_id,
        "api_team_id": api_team_id,
        "players": player_count,
        "coaches": coach_count,
    }


def run_api_football_squad_sync(
    data: dict[str, Any],
    force: bool = False,
    dry_run: bool = False,
    limit: int = API_FOOTBALL_SQUAD_SYNC_BATCH_SIZE,
    include_coaches: bool = True,
) -> dict[str, Any]:
    if not API_FOOTBALL_KEY:
        return {"ok": False, "error": "API_FOOTBALL_KEY is not configured."}

    limit = api_football_squad_team_limit(
        requested_limit=max(1, int(limit)),
        include_coaches=include_coaches,
    )
    links = api_football_team_links()
    linking = None
    if len(links) < len(data.get("teams", [])):
        seeded = seed_api_football_team_links_from_fixture_links(data)
        links = api_football_team_links()
        linking = {"seeded_from_fixture_links": seeded}
    if len(links) < len(data.get("teams", [])) and not dry_run:
        next_linking: dict[str, Any] = dict(linking or {})
        next_linking["fixture_linking"] = api_football_link_fixtures(data)
        linking = next_linking
        links = api_football_team_links()

    limit = api_football_squad_team_limit(
        requested_limit=max(1, int(limit)),
        include_coaches=include_coaches,
    )
    candidates = due_api_football_teams(data, force=force, limit=max(1, limit))
    if limit == 0:
        candidates = []
    skipped = [
        {"team_id": team["id"], "reason": "missing_api_football_team_link"}
        for team in data.get("teams", [])
        if team["id"] not in links
    ]
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "candidates": [
                {
                    "team_id": item["team"]["id"],
                    "team_name": item["team"]["name"],
                    "api_team_id": item["link"]["api_team_id"],
                }
                for item in candidates
            ],
            "skipped": skipped,
            "linking": linking,
            "include_coaches": include_coaches,
            "requests_today": api_football_request_count_today(),
            "daily_limit": API_FOOTBALL_DAILY_LIMIT,
        }

    synced = []
    player_verification = None
    for item in candidates:
        local_team_id = item["team"]["id"]
        api_team_id = int(item["link"]["api_team_id"])
        squad_payload = api_football_get("players/squads", {"team": api_team_id})
        coach_payload = None
        if include_coaches:
            try:
                coach_payload = api_football_get("coachs", {"team": api_team_id})
            except Exception as error:
                logger.warning("Could not sync coach for %s: %s", local_team_id, error)
        with get_db() as conn:
            synced.append(
                store_api_football_team_profile_snapshot(
                    conn, local_team_id, api_team_id, squad_payload, coach_payload
                )
            )
    with get_db() as conn:
        player_verification = genai_service.verify_player_database_matches(conn)

    return {
        "ok": True,
        "dry_run": False,
        "synced": synced,
        "skipped": skipped,
        "linking": linking,
        "include_coaches": include_coaches,
        "player_database_verification": player_verification,
        "requests_today": api_football_request_count_today(),
        "daily_limit": API_FOOTBALL_DAILY_LIMIT,
    }


def local_match_date(match: dict[str, Any]) -> Any:
    return match_kickoff(match).astimezone(AMSTERDAM_TZ).date()


def tournament_session_date(match: dict[str, Any]) -> Any:
    local_kickoff = match_kickoff(match).astimezone(AMSTERDAM_TZ)
    if local_kickoff.hour <= MATCHDAY_SESSION_END_HOUR:
        return local_kickoff.date() - timedelta(days=1)
    return local_kickoff.date()


def current_tournament_session_date(current: datetime) -> Any:
    local_current = current.astimezone(AMSTERDAM_TZ)
    if local_current.hour <= MATCHDAY_SESSION_END_HOUR:
        return local_current.date() - timedelta(days=1)
    return local_current.date()


def is_matchday_window_match(match: dict[str, Any]) -> bool:
    local_hour = match_kickoff(match).astimezone(AMSTERDAM_TZ).hour
    return local_hour >= MATCHDAY_SESSION_START_HOUR or local_hour <= MATCHDAY_SESSION_END_HOUR


def score_rule_for_match(match: dict[str, Any]) -> dict[str, Any]:
    return MATCH_SCORE_RULES.get(match["round"], MATCH_SCORE_RULES["Group Stage"])


def round_match_points(points: float) -> int:
    return int(points + 0.5)


def rounded_component_points(components: dict[str, int], multiplier: float) -> dict[str, int]:
    raw_components = {key: value * multiplier for key, value in components.items() if value > 0}
    rounded_total = round_match_points(sum(raw_components.values()))
    floors = {key: int(value) for key, value in raw_components.items()}
    remainder = rounded_total - sum(floors.values())
    ordered_keys = sorted(
        raw_components,
        key=lambda key: (raw_components[key] - floors[key], raw_components[key]),
        reverse=True,
    )
    allocated = dict(floors)
    for key in ordered_keys[:remainder]:
        allocated[key] += 1
    return {key: allocated.get(key, 0) for key in components}


def match_prediction_points(prediction: Any, match: dict[str, Any]) -> tuple[int, str | None]:
    breakdown = match_prediction_breakdown(prediction, match)
    if breakdown["total_points"] <= 0:
        return 0, None
    return int(breakdown["total_points"]), breakdown["score_kind"]


def match_prediction_breakdown(prediction: Any | None, match: dict[str, Any]) -> dict[str, Any]:
    empty = {
        "outcome_points": 0,
        "home_goals_points": 0,
        "away_goals_points": 0,
        "exact_bonus_points": 0,
        "total_points": 0,
        "score_kind": None,
        "outcome_correct": False,
        "home_goals_correct": False,
        "away_goals_correct": False,
        "exact_score": False,
        "multiplier": float(score_rule_for_match(match).get("multiplier", 1.0)),
    }
    if prediction is None:
        return empty
    result = match_result(match)
    if result is None:
        return empty
    rule = score_rule_for_match(match)
    multiplier = float(rule.get("multiplier", 1.0))
    empty["multiplier"] = multiplier
    home_score = match.get("home_score")
    away_score = match.get("away_score")
    if home_score is None or away_score is None:
        return empty
    actual_home_score = int(home_score)
    actual_away_score = int(away_score)
    predicted_home_score = prediction["home_score"]
    predicted_away_score = prediction["away_score"]
    exact_score = (
        predicted_home_score == actual_home_score and predicted_away_score == actual_away_score
    )
    predicted_result = prediction_result(prediction)
    outcome_correct = predicted_result == result
    home_goals_correct = predicted_home_score == actual_home_score
    away_goals_correct = predicted_away_score == actual_away_score

    outcome_points = BASE_MATCH_SCORE_RULE["outcome"] if outcome_correct else 0
    home_goals_points = BASE_MATCH_SCORE_RULE["home_goals"] if home_goals_correct else 0
    away_goals_points = BASE_MATCH_SCORE_RULE["away_goals"] if away_goals_correct else 0
    exact_bonus_points = BASE_MATCH_SCORE_RULE["exact_bonus"] if exact_score else 0
    base_points = outcome_points + home_goals_points + away_goals_points + exact_bonus_points
    total_points = round_match_points(base_points * multiplier)
    component_points = rounded_component_points(
        {
            "outcome_points": outcome_points,
            "home_goals_points": home_goals_points,
            "away_goals_points": away_goals_points,
            "exact_bonus_points": exact_bonus_points,
        },
        multiplier,
    )

    if not total_points:
        score_kind = None
    elif exact_score:
        score_kind = "exact"
    elif outcome_correct:
        score_kind = "outcome"
    else:
        score_kind = "partial"
    return {
        **component_points,
        "total_points": total_points,
        "score_kind": score_kind,
        "outcome_correct": outcome_correct,
        "home_goals_correct": home_goals_correct,
        "away_goals_correct": away_goals_correct,
        "exact_score": exact_score,
        "multiplier": multiplier,
    }


def quiz_complete(quiz: dict[str, Any] | None, prediction: Any | None) -> bool:
    if not quiz:
        return True
    answer = clean_text(prediction["answer"] if prediction else "")
    if not answer:
        return False
    choices = [clean_text(choice) for choice in quiz.get("choices", []) if clean_text(choice)]
    return not (
        choices and normalize_answer(answer) not in {normalize_answer(choice) for choice in choices}
    )


def quiz_answer_points(quiz: dict[str, Any], prediction: Any | None) -> int:
    if not prediction:
        return 0
    correct_answers = quiz.get("correct_answers")
    if correct_answers is None and quiz.get("correct_answer") is not None:
        correct_answers = [quiz.get("correct_answer")]
    if not correct_answers:
        return 0
    user_answer = normalize_answer(prediction["answer"])
    normalized_correct = {normalize_answer(answer) for answer in correct_answers}
    if user_answer not in normalized_correct:
        return 0
    choice_points = quiz.get("choice_points") or {}
    for choice, points in choice_points.items():
        if normalize_answer(choice) == user_answer:
            return int(points)
    dynamic_choice_points = quiz.get("dynamic_choice_points")
    if dynamic_choice_points is not None:
        return int(dynamic_choice_points)
    return QUIZ_YES_NO_POINTS if quiz.get("type") == "yes_no" else QUIZ_OPEN_POINTS


def quiz_viewership_winners(
    _data: dict[str, Any], _quiz_predictions: list[Any]
) -> set[tuple[int, str]]:
    return set()


def quiz_points_for_prediction(
    match: dict[str, Any], prediction: Any | None, _viewership_winners: set[tuple[int, str]]
) -> int:
    quiz = match.get("quiz")
    if not quiz:
        return 0
    return quiz_answer_points(quiz, prediction)


def user_match_points_by_match(
    data: dict[str, Any],
    predictions: dict[str, dict[str, Any]],
    quiz_predictions: dict[str, Any],
    leeuwtje_match_ids: list[str],
    striker_picks: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    viewership_winners = quiz_viewership_winners(data, list(quiz_predictions.values()))
    leeuwtje_set = set(leeuwtje_match_ids)
    striker_points_by_match = striker_points_by_match_for_picks(data, striker_picks or [])
    points_by_match = {}
    for match in data["matches"]:
        if match_result(match) is None:
            continue
        match_prediction = predictions.get(match["id"])
        score_breakdown = match_prediction_breakdown(match_prediction, match)
        score_points = int(score_breakdown["total_points"])
        leeuwtje_points = 0
        if match_prediction and match["id"] in leeuwtje_set:
            leeuwtje_points = score_points
        quiz_points = quiz_points_for_prediction(
            match,
            quiz_predictions.get(match["id"]),
            viewership_winners,
        )
        striker_entry = striker_points_by_match.get(match["id"], {})
        striker_points = int(striker_entry.get("points") or 0)
        quiz = match.get("quiz") or {}
        quiz_prediction = quiz_predictions.get(match["id"])
        points_by_match[match["id"]] = {
            "score_points": score_points,
            "score_breakdown": score_breakdown,
            "leeuwtje_points": leeuwtje_points,
            "quiz_points": quiz_points,
            "striker_points": striker_points,
            "striker_scorers": striker_entry.get("scorers", []),
            "total_points": score_points + leeuwtje_points + quiz_points + striker_points,
            "score_kind": score_breakdown["score_kind"],
            "prediction": (
                {
                    "home_score": match_prediction["home_score"],
                    "away_score": match_prediction["away_score"],
                }
                if match_prediction
                else None
            ),
            "result": {
                "home_score": match.get("home_score"),
                "away_score": match.get("away_score"),
            },
            "quiz": (
                {
                    "question": quiz.get("question"),
                    "answer": quiz_prediction["answer"] if quiz_prediction else None,
                    "points": quiz_points,
                    "answered": quiz_prediction is not None,
                    "correct": quiz_points > 0,
                }
                if quiz
                else None
            ),
            "leeuwtje": match["id"] in leeuwtje_set,
        }
    return points_by_match


def match_points_for_prediction(
    match: dict[str, Any],
    match_prediction: Any | None,
    quiz_prediction: Any | None,
    *,
    leeuwtje: bool = False,
    striker_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    score_breakdown = match_prediction_breakdown(match_prediction, match)
    score_points = int(score_breakdown["total_points"])
    leeuwtje_points = score_points if match_prediction and leeuwtje else 0
    quiz_points = quiz_points_for_prediction(match, quiz_prediction, set())
    striker_entry = striker_entry or {}
    striker_points = int(striker_entry.get("points") or 0)
    quiz = match.get("quiz") or {}
    return {
        "score_points": score_points,
        "score_breakdown": score_breakdown,
        "leeuwtje_points": leeuwtje_points,
        "quiz_points": quiz_points,
        "striker_points": striker_points,
        "striker_scorers": striker_entry.get("scorers", []),
        "total_points": score_points + leeuwtje_points + quiz_points + striker_points,
        "score_kind": score_breakdown["score_kind"],
        "prediction": (
            {
                "home_score": match_prediction["home_score"],
                "away_score": match_prediction["away_score"],
            }
            if match_prediction
            else None
        ),
        "result": {
            "home_score": match.get("home_score"),
            "away_score": match.get("away_score"),
        },
        "quiz": (
            {
                "question": quiz.get("question"),
                "answer": quiz_prediction["answer"] if quiz_prediction else None,
                "points": quiz_points,
                "answered": quiz_prediction is not None,
                "correct": quiz_points > 0,
            }
            if quiz
            else None
        ),
        "leeuwtje": leeuwtje,
    }


def striker_points_for_match_from_picks(
    match: dict[str, Any],
    picks: list[str],
    goal_rows: list[Any],
    scorer_links: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not picks:
        return {"points": 0, "scorers": []}
    pick_keys = {
        key: pick for pick in picks for key in genai_service.player_counter_keys(pick) if key
    }
    if not pick_keys:
        return {"points": 0, "scorers": []}

    multiplier = float(score_rule_for_match(match).get("multiplier", 1.0))
    goal_points = round_match_points(STRIKER_GOAL_POINTS * multiplier)
    scorers: dict[str, dict[str, Any]] = {}
    total_points = 0
    for row in goal_rows:
        detail = normalize_answer(row["detail"])
        comments = normalize_answer(row["comments"])
        if "own goal" in detail or "own goal" in comments:
            continue
        matched_pick = next(
            (
                pick_keys[key]
                for scorer_name in scorer_names_with_genai_link(row, scorer_links or {})
                for key in genai_service.player_counter_keys(scorer_name)
                if key in pick_keys
            ),
            None,
        )
        if not matched_pick:
            continue
        total_points += goal_points
        scorer = scorers.setdefault(
            matched_pick,
            {"name": matched_pick, "goals": 0, "points": 0},
        )
        scorer["goals"] += 1
        scorer["points"] += goal_points
    return {
        "points": total_points,
        "scorers": sorted(
            scorers.values(),
            key=lambda scorer: (-scorer["points"], scorer["name"]),
        ),
        "multiplier": multiplier,
    }


def standings_from_scores(
    group: dict[str, Any],
    matches: list[dict[str, Any]],
    scores_by_match: dict[str, tuple[int, int]],
) -> list[str]:
    rows = {
        team_id: {
            "team_id": team_id,
            "played": 0,
            "points": 0,
            "goals_for": 0,
            "goals_against": 0,
        }
        for team_id in group["teams"]
    }
    for match in matches:
        scores = scores_by_match.get(match["id"])
        if scores is None:
            continue
        home_score, away_score = scores
        home = rows.get(match["home_team_id"])
        away = rows.get(match["away_team_id"])
        if home is None or away is None:
            continue
        home["played"] += 1
        away["played"] += 1
        home["goals_for"] += home_score
        home["goals_against"] += away_score
        away["goals_for"] += away_score
        away["goals_against"] += home_score
        if home_score > away_score:
            home["points"] += 3
        elif home_score < away_score:
            away["points"] += 3
        else:
            home["points"] += 1
            away["points"] += 1

    ordered = sorted(
        rows.values(),
        key=lambda row: (
            -row["points"],
            -(row["goals_for"] - row["goals_against"]),
            -row["goals_for"],
            row["team_id"],
        ),
    )
    return [row["team_id"] for row in ordered]


def group_position_score(user_predictions: dict[str, Any], data: dict[str, Any]) -> tuple[int, int]:
    points = 0
    correct_positions = 0
    group_matches_by_id = {
        match["id"]: match for match in data["matches"] if match["round"] == "Group Stage"
    }
    for group in data["groups"]:
        matches = [
            match for match in group_matches_by_id.values() if match.get("group") == group["id"]
        ]
        if not matches:
            continue
        if any(match_result(match) is None for match in matches):
            continue
        if any(match["id"] not in user_predictions for match in matches):
            continue
        actual_scores = {
            match["id"]: (match["home_score"], match["away_score"]) for match in matches
        }
        predicted_scores = {
            match["id"]: (
                user_predictions[match["id"]]["home_score"],
                user_predictions[match["id"]]["away_score"],
            )
            for match in matches
        }
        actual_order = standings_from_scores(group, matches, actual_scores)
        predicted_order = standings_from_scores(group, matches, predicted_scores)
        for actual_team, predicted_team in zip(actual_order, predicted_order, strict=False):
            if actual_team == predicted_team:
                correct_positions += 1
                points += GROUP_POSITION_POINTS
    return points, correct_positions


BADGE_DEFINITIONS = {
    "perfect_score": {
        "label": "Perfect Score",
        "detail": "Exacte uitslag goed voorspeld.",
        "family": "zayu",
        "mascot": "Zayu Jaguar",
        "mark": "Z",
    },
    "hattrick_hero": {
        "label": "Hattrick Hero",
        "detail": "Drie exacte uitslagen op rij.",
        "family": "zayu",
        "mascot": "Zayu Jaguar",
        "mark": "Z",
    },
    "on_fire": {
        "label": "On Fire",
        "detail": "Drie toto's op rij goed.",
        "family": "zayu",
        "mascot": "Zayu Jaguar",
        "mark": "Z",
    },
    "oranje_treffer": {
        "label": "Oranje Treffer",
        "detail": "Juiste toto bij een wedstrijd van Nederland.",
        "family": "oranje",
        "mascot": "Oranje Leeuw",
        "mark": "NL",
    },
    "oranje_expert": {
        "label": "Oranje Expert",
        "detail": "Exacte uitslag bij een wedstrijd van Nederland.",
        "family": "oranje",
        "mascot": "Oranje Leeuw",
        "mark": "NL",
    },
    "better_next_time": {
        "label": "Better Next Time",
        "detail": "Drie toto's op rij mis.",
        "family": "maple",
        "mascot": "Maple Moose",
        "mark": "M",
    },
    "keep_your_head_up": {
        "label": "Keep your head up",
        "detail": "Vijf keer op rij geen exacte uitslag.",
        "family": "maple",
        "mascot": "Maple Moose",
        "mark": "M",
    },
    "so_close": {
        "label": "So close",
        "detail": "Drie keer op rij maar een doelpunt naast exact.",
        "family": "maple",
        "mascot": "Maple Moose",
        "mark": "M",
    },
    "great_ranker": {
        "label": "Great Ranker",
        "detail": "Een land op de juiste positie in de poule voorspeld.",
        "family": "clutch",
        "mascot": "Clutch Eagle",
        "mark": "C",
    },
    "champ_of_the_day": {
        "label": "Champ of the day",
        "detail": "Bovenaan de league na een speeldag.",
        "family": "trophy",
        "mascot": "WK bokaal",
        "mark": "WC",
    },
}


def add_badge(counter: Counter[str], key: str, amount: int = 1) -> None:
    if amount > 0:
        counter[key] += amount


def close_score_miss(prediction: Any, match: dict[str, Any]) -> bool:
    if match_result(match) is None:
        return False
    goal_delta = abs(prediction["home_score"] - match["home_score"]) + abs(
        prediction["away_score"] - match["away_score"]
    )
    return goal_delta == 1


def materialize_badges(counter: Counter[str]) -> list[dict[str, Any]]:
    badges = []
    for key, definition in BADGE_DEFINITIONS.items():
        count = counter[key]
        if count <= 0:
            continue
        badges.append({"key": key, "count": count, **definition})
    return badges


def badge_catalog() -> list[dict[str, Any]]:
    return [{"key": key, **definition} for key, definition in BADGE_DEFINITIONS.items()]


def badge_counters_and_metrics(
    data: dict[str, Any],
    user_predictions: list[Any],
    correct_group_positions: int,
    champ_days: int,
) -> tuple[Counter[str], dict[str, dict[str, Any]]]:
    matches = {match["id"]: match for match in data["matches"]}
    completed_predictions = sorted(
        [
            prediction
            for prediction in user_predictions
            if match_result(matches.get(prediction["match_id"], {})) is not None
        ],
        key=lambda prediction: match_kickoff(matches[prediction["match_id"]]),
    )
    counter: Counter[str] = Counter()
    exact_streak = 0
    outcome_streak = 0
    wrong_outcome_streak = 0
    wrong_exact_streak = 0
    close_miss_streak = 0
    max_exact_streak = 0
    max_outcome_streak = 0
    max_wrong_outcome_streak = 0
    max_wrong_exact_streak = 0
    max_close_miss_streak = 0
    exact_count = 0
    netherlands_outcomes = 0
    netherlands_exacts = 0

    for prediction in completed_predictions:
        match = matches[prediction["match_id"]]
        points, score_kind = match_prediction_points(prediction, match)
        exact = score_kind == "exact"
        outcome = points > 0 and prediction_result(prediction) == match_result(match)
        netherlands_match = (
            match.get("home_team_id") == NETHERLANDS_TEAM_ID
            or match.get("away_team_id") == NETHERLANDS_TEAM_ID
        )

        if exact:
            exact_count += 1
            add_badge(counter, "perfect_score")
            exact_streak += 1
            wrong_exact_streak = 0
            close_miss_streak = 0
            if exact_streak >= 3:
                add_badge(counter, "hattrick_hero")
        else:
            exact_streak = 0
            wrong_exact_streak += 1
            if wrong_exact_streak >= 5:
                add_badge(counter, "keep_your_head_up")
            if close_score_miss(prediction, match):
                close_miss_streak += 1
                if close_miss_streak >= 3:
                    add_badge(counter, "so_close")
            else:
                close_miss_streak = 0

        if outcome:
            outcome_streak += 1
            wrong_outcome_streak = 0
            if outcome_streak >= 3:
                add_badge(counter, "on_fire")
            if netherlands_match:
                netherlands_outcomes += 1
                add_badge(counter, "oranje_treffer")
        else:
            outcome_streak = 0
            wrong_outcome_streak += 1
            if wrong_outcome_streak >= 3:
                add_badge(counter, "better_next_time")

        if exact and netherlands_match:
            netherlands_exacts += 1
            add_badge(counter, "oranje_expert")

        max_exact_streak = max(max_exact_streak, exact_streak)
        max_outcome_streak = max(max_outcome_streak, outcome_streak)
        max_wrong_outcome_streak = max(max_wrong_outcome_streak, wrong_outcome_streak)
        max_wrong_exact_streak = max(max_wrong_exact_streak, wrong_exact_streak)
        max_close_miss_streak = max(max_close_miss_streak, close_miss_streak)

    add_badge(counter, "great_ranker", correct_group_positions)
    add_badge(counter, "champ_of_the_day", champ_days)

    metrics = {
        "perfect_score": {"current": exact_count, "target": 1, "unit": "exact score"},
        "hattrick_hero": {
            "current": max_exact_streak,
            "target": 3,
            "unit": "exact scores in a row",
        },
        "on_fire": {
            "current": max_outcome_streak,
            "target": 3,
            "unit": "correct outcomes in a row",
        },
        "oranje_treffer": {
            "current": netherlands_outcomes,
            "target": 1,
            "unit": "Netherlands outcome",
        },
        "oranje_expert": {
            "current": netherlands_exacts,
            "target": 1,
            "unit": "Netherlands exact score",
        },
        "better_next_time": {
            "current": max_wrong_outcome_streak,
            "target": 3,
            "unit": "wrong outcomes in a row",
        },
        "keep_your_head_up": {
            "current": max_wrong_exact_streak,
            "target": 5,
            "unit": "non-exact scores in a row",
        },
        "so_close": {
            "current": max_close_miss_streak,
            "target": 3,
            "unit": "one-goal misses in a row",
        },
        "great_ranker": {
            "current": correct_group_positions,
            "target": 1,
            "unit": "correct group position",
        },
        "champ_of_the_day": {
            "current": champ_days,
            "target": 1,
            "unit": "day won",
        },
    }
    return counter, metrics


def badge_progress_list(
    data: dict[str, Any],
    user_predictions: list[Any],
    correct_group_positions: int,
    champ_days: int,
) -> list[dict[str, Any]]:
    counter, metrics = badge_counters_and_metrics(
        data,
        user_predictions,
        correct_group_positions,
        champ_days,
    )
    progress = []
    for key, definition in BADGE_DEFINITIONS.items():
        metric = metrics[key]
        current = int(metric["current"])
        target = max(1, int(metric["target"]))
        progress.append(
            {
                "key": key,
                "count": counter[key],
                "unlocked": counter[key] > 0,
                "current": current,
                "target": target,
                "unit": metric["unit"],
                "progress": min(100, round((current / target) * 100)),
                **definition,
            }
        )
    return progress


def score_through_date(
    data: dict[str, Any],
    user_predictions: list[Any],
    user_quiz_predictions: dict[str, Any],
    user_leeuwtjes: set[str],
    viewership_winners: set[tuple[int, str]],
    target_date: Any,
) -> int:
    matches = {match["id"]: match for match in data["matches"]}
    points = 0
    for prediction in user_predictions:
        match = matches.get(prediction["match_id"])
        if not match or match_result(match) is None or tournament_session_date(match) > target_date:
            continue
        base_points, _ = match_prediction_points(prediction, match)
        points += base_points * (2 if prediction["match_id"] in user_leeuwtjes else 1)

    for match in data["matches"]:
        if match_result(match) is None or tournament_session_date(match) > target_date:
            continue
        points += quiz_points_for_prediction(
            match, user_quiz_predictions.get(match["id"]), viewership_winners
        )
    return points


def champion_day_counts(
    data: dict[str, Any],
    users: list[Any],
    by_user: dict[int, list[Any]],
    quiz_by_user: dict[int, dict[str, Any]],
    leeuwtjes_by_user: dict[int, set[str]],
    viewership_winners: set[tuple[int, str]],
) -> Counter[int]:
    completed_dates = sorted(
        {
            tournament_session_date(match)
            for match in data["matches"]
            if match_result(match) is not None
        }
    )
    counts: Counter[int] = Counter()
    for completed_date in completed_dates:
        daily_scores = {
            user["id"]: score_through_date(
                data,
                by_user.get(user["id"], []),
                quiz_by_user.get(user["id"], {}),
                leeuwtjes_by_user.get(user["id"], set()),
                viewership_winners,
                completed_date,
            )
            for user in users
        }
        top_score = max(daily_scores.values(), default=0)
        if top_score <= 0:
            continue
        for user_id, score in daily_scores.items():
            if score == top_score:
                counts[user_id] += 1
    return counts


def badge_list(
    data: dict[str, Any],
    user_predictions: list[Any],
    correct_group_positions: int,
    champ_days: int,
) -> list[dict[str, Any]]:
    counter, _ = badge_counters_and_metrics(
        data,
        user_predictions,
        correct_group_positions,
        champ_days,
    )
    return materialize_badges(counter)


def initials(name: str) -> str:
    parts = [part for part in name.replace("-", " ").split() if part]
    if not parts:
        return "?"
    return "".join(part[0] for part in parts[:2]).upper()


def avatar_hue(name: str) -> int:
    return sum(ord(char) for char in name) % 360


def require_current_user(
    error_message: str = "Log in before using this feature.",
) -> tuple[dict[str, Any] | None, Any | None]:
    user = current_user()
    if not user:
        return None, (jsonify({"error": error_message}), 401)
    return user, None


def require_admin_user() -> tuple[dict[str, Any] | None, Any | None]:
    user, error_response = require_current_user("Log in as an admin before using this feature.")
    if error_response:
        return None, error_response
    assert user is not None
    if not user.get("is_admin"):
        return None, (jsonify({"error": "Admin access required."}), 403)
    return user, None


def sync_token_from_request() -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.casefold().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return request.headers.get("X-WK-HUB-SYNC-TOKEN", "") or request.args.get("token", "")


def require_sync_token() -> Any | None:
    if not API_FOOTBALL_SYNC_TOKEN:
        return jsonify({"error": "WK_HUB_SYNC_TOKEN or CRON_SECRET is not configured."}), 503
    if sync_token_from_request() != API_FOOTBALL_SYNC_TOKEN:
        return jsonify({"error": "Invalid sync token."}), 403
    return None


def social_state(user: dict[str, Any]) -> dict[str, Any]:
    with get_db() as conn:
        users = execute(
            conn,
            """
            SELECT id, name, email, profile_image_url
            FROM users
            WHERE id != ? AND archived_at IS NULL
            ORDER BY name
            """,
            (user["id"],),
        ).fetchall()
        follows = execute(conn, "SELECT follower_id, followed_id FROM user_follows").fetchall()

    following = {row["followed_id"] for row in follows if row["follower_id"] == user["id"]}
    followers = {row["follower_id"] for row in follows if row["followed_id"] == user["id"]}
    friends = following & followers

    people = []
    for row in users:
        is_following = row["id"] in following
        follows_me = row["id"] in followers
        is_friend = row["id"] in friends
        relationship = "none"
        if is_friend:
            relationship = "friend"
        elif is_following:
            relationship = "following"
        elif follows_me:
            relationship = "follows_you"

        people.append(
            {
                "user_id": row["id"],
                "name": row["name"],
                "profile_picture": user_profile_picture(row),
                "is_following": is_following,
                "follows_me": follows_me,
                "is_friend": is_friend,
                "relationship": relationship,
            }
        )

    return {
        "people": people,
        "counts": {
            "following": len(following),
            "followers": len(followers),
            "friends": len(friends),
        },
    }


def users_are_friends(user_id: int, other_user_id: int) -> bool:
    if user_id == other_user_id:
        return True
    with get_db() as conn:
        row = execute(
            conn,
            """
            SELECT 1
            FROM user_follows outbound
            JOIN user_follows inbound
              ON inbound.follower_id = outbound.followed_id
             AND inbound.followed_id = outbound.follower_id
            WHERE outbound.follower_id = ?
              AND outbound.followed_id = ?
            """,
            (user_id, other_user_id),
        ).fetchone()
    return row is not None


def user_prediction_groups(
    profile_user_id: int,
    data: dict[str, Any],
    include_unplayed: bool = False,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    teams = {team["id"]: team for team in data["teams"]}

    with get_db() as conn:
        rows = execute(
            conn,
            """
            SELECT match_id, home_score, away_score
            FROM match_predictions
            WHERE user_id = ?
            """,
            (profile_user_id,),
        ).fetchall()
        quiz_rows = execute(
            conn,
            """
            SELECT match_id, answer, viewership_prediction
            FROM quiz_predictions
            WHERE user_id = ?
            """,
            (profile_user_id,),
        ).fetchall()
        leeuwtje_rows = execute(
            conn,
            "SELECT match_id FROM leeuwtje_predictions WHERE user_id = ?",
            (profile_user_id,),
        ).fetchall()
        top_scorer_row = execute(
            conn,
            """
            SELECT player_name, player_name_2, player_name_3,
                   striker_name_1, striker_name_2, striker_name_3,
                   striker_name_4, striker_name_5
            FROM top_scorer_predictions
            WHERE user_id = ?
            """,
            (profile_user_id,),
        ).fetchone()

    by_match = {row["match_id"]: row for row in rows}
    quiz_by_match = {row["match_id"]: row for row in quiz_rows}
    leeuwtjes = {row["match_id"] for row in leeuwtje_rows}
    match_points = user_match_points_by_match(
        data,
        by_match,
        quiz_by_match,
        list(leeuwtjes),
        striker_pick_names(top_scorer_row),
    )
    groups = []
    predictions_by_date: dict[str, list[dict[str, Any]]] = {}
    for match in sorted(data["matches"], key=match_kickoff):
        if not include_unplayed and not is_prediction_locked(match, now):
            continue
        prediction = by_match.get(match["id"])
        if prediction is None:
            continue
        quiz_prediction = quiz_by_match.get(match["id"])
        local_date = match_kickoff(match).astimezone(AMSTERDAM_TZ).date().isoformat()
        predictions_by_date.setdefault(local_date, []).append(
            {
                "match_id": match["id"],
                "date": match["date"],
                "time_utc": match["time_utc"],
                "round": match.get("round"),
                "group": match.get("group"),
                "home_team_id": match["home_team_id"],
                "away_team_id": match["away_team_id"],
                "home_team_name": teams.get(match["home_team_id"], {}).get(
                    "name", match["home_team_id"]
                ),
                "away_team_name": teams.get(match["away_team_id"], {}).get(
                    "name", match["away_team_id"]
                ),
                "home_score": prediction["home_score"],
                "away_score": prediction["away_score"],
                "actual_home_score": match.get("home_score"),
                "actual_away_score": match.get("away_score"),
                "completed": match_result(match) is not None,
                "quiz_question": match.get("quiz", {}).get("question"),
                "quiz_answer": quiz_prediction["answer"] if quiz_prediction else None,
                "viewership_prediction": (
                    quiz_prediction["viewership_prediction"] if quiz_prediction else None
                ),
                "leeuwtje": match["id"] in leeuwtjes,
                "points": match_points.get(match["id"]),
            }
        )
    for date_key, predictions in predictions_by_date.items():
        groups.append({"group": date_key, "date": date_key, "predictions": predictions})
    return groups


def build_leaderboard(
    data: dict[str, Any],
    viewer_user_id: int | None = None,
    viewer_is_admin: bool = False,
    now: datetime | None = None,
    use_computed_points: bool = True,
) -> list[dict[str, Any]]:
    matches = {match["id"]: match for match in data["matches"]}
    teams = {team["id"]: team for team in data["teams"]}
    champion_id = data.get("meta", {}).get("world_cup_winner_id")
    top_scorer_result = top_scorer_result_name(data)
    eliminated_teams = eliminated_team_ids(data)
    tournament_picks_revealed = are_tournament_picks_revealed(data, now)
    group_stage_ids = {match["id"] for match in data["matches"] if match["round"] == "Group Stage"}
    required_group_id = next(
        (group["id"] for group in data["groups"] if NETHERLANDS_TEAM_ID in group["teams"]),
        None,
    )
    required_group_ids = {
        match["id"]
        for match in data["matches"]
        if match["round"] == "Group Stage" and match.get("group") == required_group_id
    }

    with get_db() as conn:
        users = execute(
            conn,
            """
            SELECT id, name, email, profile_image_url, prize_pot_status, is_admin
            FROM users
            WHERE archived_at IS NULL
            ORDER BY name
            """,
        ).fetchall()
        predictions = execute(conn, "SELECT * FROM match_predictions").fetchall()
        quiz_predictions = execute(conn, "SELECT * FROM quiz_predictions").fetchall()
        leeuwtjes = execute(conn, "SELECT user_id, match_id FROM leeuwtje_predictions").fetchall()
        winners = {
            row["user_id"]: row["team_id"]
            for row in execute(conn, "SELECT user_id, team_id FROM winner_predictions").fetchall()
        }
        top_scorers = {
            row["user_id"]: row
            for row in execute(
                conn,
                """
                SELECT user_id, player_name, player_name_2, player_name_3,
                       striker_name_1, striker_name_2, striker_name_3,
                       striker_name_4, striker_name_5
                FROM top_scorer_predictions
                """,
            ).fetchall()
        }
        stored_points_by_user = (
            computed_leaderboard_points_by_user(conn) if use_computed_points else {}
        )

    by_user: dict[int, list[Any]] = {}
    for prediction in predictions:
        by_user.setdefault(prediction["user_id"], []).append(prediction)
    quiz_by_user: dict[int, dict[str, Any]] = {}
    for prediction in quiz_predictions:
        quiz_by_user.setdefault(prediction["user_id"], {})[prediction["match_id"]] = prediction
    leeuwtjes_by_user: dict[int, set[str]] = {}
    for row in leeuwtjes:
        leeuwtjes_by_user.setdefault(row["user_id"], set()).add(row["match_id"])
    viewership_winners = quiz_viewership_winners(data, list(quiz_predictions))
    champ_days_by_user = champion_day_counts(
        data,
        list(users),
        by_user,
        quiz_by_user,
        leeuwtjes_by_user,
        viewership_winners,
    )

    goal_counts, striker_goal_points = goal_counts_and_points_by_player(data)
    leaderboard = []
    current = now or utc_now()
    for user in users:
        points = 0
        match_score_points = 0
        exact_scores = 0
        outcomes = 0
        shooting = 0
        defence = 0
        scoring_games = 0
        user_predictions = by_user.get(user["id"], [])
        user_predictions_by_match = {
            prediction["match_id"]: prediction for prediction in user_predictions
        }
        user_quiz_predictions = quiz_by_user.get(user["id"], {})
        user_leeuwtjes = leeuwtjes_by_user.get(user["id"], set())
        user_consumed_leeuwtjes = {
            match_id
            for match_id in user_leeuwtjes
            if matches.get(match_id) is not None and match_kickoff(matches[match_id]) <= current
        }
        user_prediction_ids = {prediction["match_id"] for prediction in user_predictions}
        group_stage_predictions = sum(
            1 for match_id in user_prediction_ids if match_id in group_stage_ids
        )
        required_group_predictions = sum(
            1 for match_id in user_prediction_ids if match_id in required_group_ids
        )
        for prediction in user_predictions:
            match = matches.get(prediction["match_id"])
            if match is None:
                continue
            result = match_result(match)
            if result is None:
                continue
            base_points, score_kind = match_prediction_points(prediction, match)
            if prediction["match_id"] in user_leeuwtjes:
                points += base_points * 2
            else:
                points += base_points
            match_score_points += base_points
            if prediction_result(prediction) == result and base_points > 0:
                outcomes += 1
                scoring_games += 1
            if score_kind == "exact":
                exact_scores += 1

            if result > 0:
                if prediction["home_score"] == match.get("home_score"):
                    shooting += 1
                if prediction["away_score"] == match.get("away_score"):
                    defence += 1
            elif result < 0:
                if prediction["away_score"] == match.get("away_score"):
                    shooting += 1
                if prediction["home_score"] == match.get("home_score"):
                    defence += 1

        group_position_points, correct_group_positions = group_position_score(
            user_predictions_by_match, data
        )
        points += group_position_points

        quiz_points = 0
        quiz_answer_count = 0
        for match in data["matches"]:
            quiz = match.get("quiz")
            if not quiz:
                continue
            quiz_prediction = user_quiz_predictions.get(match["id"])
            if quiz_complete(quiz, quiz_prediction):
                quiz_answer_count += 1
            quiz_points += quiz_points_for_prediction(match, quiz_prediction, viewership_winners)
        points += quiz_points

        winner_pick = winners.get(user["id"])
        winner_points = WINNER_POINTS if champion_id and winner_pick == champion_id else 0
        points += winner_points
        winner_impossible = bool(
            winner_pick
            and ((champion_id and winner_pick != champion_id) or winner_pick in eliminated_teams)
        )
        top_scorer_pick_row = top_scorers.get(user["id"])
        top_scorer_pick = top_scorer_pick_name(top_scorer_pick_row)
        striker_picks = striker_pick_score_rows(
            top_scorer_pick_row,
            goal_counts,
            striker_goal_points,
        )
        top_scorer_points = top_scorer_prediction_points(data, top_scorer_pick)
        top_scorer_impossible = bool(
            top_scorer_pick
            and top_scorer_result
            and normalize_answer(top_scorer_pick) != normalize_answer(top_scorer_result)
        )
        striker_points = sum(pick["points"] for pick in striker_picks)
        scorer_points = top_scorer_points + striker_points
        points += scorer_points
        all_group_predictions_complete = group_stage_predictions >= len(group_stage_ids)
        leeuwtje_points = 0
        for prediction in user_predictions:
            if prediction["match_id"] not in user_leeuwtjes:
                continue
            match = matches.get(prediction["match_id"])
            if match is None:
                continue
            base_points, _ = match_prediction_points(prediction, match)
            leeuwtje_points += base_points
        stored_user_points = stored_points_by_user.get(user["id"], {})
        if stored_user_points:
            merged_points = apply_stored_leaderboard_points(
                {
                    "points": points,
                    "match_score_points": match_score_points,
                    "group_position_points": group_position_points,
                    "quiz_points": quiz_points,
                    "winner_points": winner_points,
                    "top_scorer_points": top_scorer_points,
                    "striker_points": striker_points,
                    "leeuwtje_points": leeuwtje_points,
                },
                stored_user_points,
            )
            points = merged_points["points"]
            match_score_points = merged_points["match_score_points"]
            group_position_points = merged_points["group_position_points"]
            quiz_points = merged_points["quiz_points"]
            winner_points = merged_points["winner_points"]
            top_scorer_points = merged_points["top_scorer_points"]
            striker_points = merged_points["striker_points"]
            scorer_points = top_scorer_points + striker_points
            leeuwtje_points = merged_points["leeuwtje_points"]
        champ_days = champ_days_by_user[user["id"]]
        badges = badge_list(
            data,
            user_predictions,
            correct_group_positions,
            champ_days,
        )

        show_tournament_picks = tournament_picks_revealed or user["id"] == viewer_user_id
        show_prize_pot = viewer_is_admin or user["id"] == viewer_user_id
        prize_pot_status = normalize_prize_pot_status(row_value(user, "prize_pot_status"))
        real_name = derived_real_name(user["email"])
        leaderboard.append(
            {
                "user_id": user["id"],
                "name": user["name"],
                "email": user["email"],
                **real_name,
                "is_admin": bool(user["is_admin"]) or is_admin_email(user["email"]),
                "profile_picture": user_profile_picture(user),
                "prize_pot_status": prize_pot_status if show_prize_pot else None,
                "prize_pot": prize_pot_payload(prize_pot_status) if show_prize_pot else None,
                "points": points,
                "exact_scores": exact_scores,
                "precision": exact_scores,
                "shooting": shooting,
                "defence": defence,
                "scoring_games": scoring_games,
                "outcomes": outcomes,
                "quiz_points": quiz_points,
                "quiz_answers": quiz_answer_count,
                "match_score_points": match_score_points,
                "group_position_points": group_position_points,
                "group_positions_correct": correct_group_positions,
                "leeuwtjes_used": len(user_consumed_leeuwtjes),
                "leeuwtjes_assigned": len(user_leeuwtjes),
                "leeuwtjes_available": max(0, LEEUWTJES_LIMIT - len(user_consumed_leeuwtjes)),
                "leeuwtjes_total": LEEUWTJES_LIMIT,
                "leeuwtje_points": leeuwtje_points,
                "predictions_count": len(user_predictions),
                "group_stage_predictions": group_stage_predictions,
                "group_stage_total": len(group_stage_ids),
                "required_group_predictions": required_group_predictions,
                "required_group_total": len(required_group_ids),
                "all_predictions_complete": all_group_predictions_complete,
                "entry_complete": (
                    all_group_predictions_complete
                    and winner_pick is not None
                    and bool(top_scorer_pick)
                    and len(striker_picks) >= STRIKER_PICK_COUNT
                ),
                "missing_group_stage_predictions": max(
                    0, len(group_stage_ids) - group_stage_predictions
                ),
                "winner_pick": winner_pick if show_tournament_picks else None,
                "winner_pick_name": (
                    teams.get(winner_pick, {}).get("name")
                    if show_tournament_picks and winner_pick
                    else None
                ),
                "winner_points": winner_points if show_tournament_picks else 0,
                "winner_impossible": winner_impossible if show_tournament_picks else False,
                "top_scorer_pick": (top_scorer_pick or None) if show_tournament_picks else None,
                "top_scorer_points": top_scorer_points if show_tournament_picks else 0,
                "top_scorer_impossible": top_scorer_impossible if show_tournament_picks else False,
                "striker_picks": striker_picks if show_tournament_picks else [],
                "striker_points": striker_points if show_tournament_picks else 0,
                "scorer_points": scorer_points if show_tournament_picks else 0,
                "top_scorer_picks": striker_picks if show_tournament_picks else [],
                "badges": badges,
                "badge_count": len(badges),
                "badge_progress": badge_progress_list(
                    data,
                    user_predictions,
                    correct_group_positions,
                    champ_days,
                ),
            }
        )

    ranked = sorted(leaderboard, key=lambda row: (-row["points"], row["name"].lower()))
    current_session = current_tournament_session_date(current)
    completed_dates = sorted(
        {
            tournament_session_date(match)
            for match in data["matches"]
            if match_result(match) is not None
            and match_kickoff(match) <= current
            and tournament_session_date(match) <= current_session
        }
    )
    rank_movement_by_user: dict[int, int] = {}
    if completed_dates:
        target_date = completed_dates[-1]
        previous_dates = [date for date in completed_dates if date < target_date]
        previous_date = previous_dates[-1] if previous_dates else None
        match_dates = {match["id"]: tournament_session_date(match) for match in data["matches"]}
        previous_scores: dict[int, int] = {}
        current_scores: dict[int, int] = {}
        for user in users:
            user_id = user["id"]
            points_by_match = user_match_points_by_match(
                data,
                {prediction["match_id"]: prediction for prediction in by_user.get(user_id, [])},
                quiz_by_user.get(user_id, {}),
                list(leeuwtjes_by_user.get(user_id, set())),
                striker_pick_names(top_scorers.get(user_id)),
            )
            previous_scores[user_id] = (
                sum(
                    int(points.get("total_points") or 0)
                    for match_id, points in points_by_match.items()
                    if previous_date is not None and match_dates.get(match_id) <= previous_date
                )
                if previous_date is not None
                else 0
            )
            current_scores[user_id] = sum(
                int(points.get("total_points") or 0)
                for match_id, points in points_by_match.items()
                if match_dates.get(match_id) <= target_date
            )
        rank_movement_by_user = {
            row["user_id"]: int(row.get("rank_movement") or 0)
            for row in rank_changes_between_scores(
                list(users),
                previous_scores,
                current_scores,
            )
        }

    for index, row in enumerate(ranked, start=1):
        movement = rank_movement_by_user.get(row["user_id"], 0)
        previous_rank = index + movement
        row["rank"] = index
        row["rank_previous"] = previous_rank
        row["rank_movement"] = movement

    return ranked


def match_display_label(match: dict[str, Any]) -> str:
    home = clean_text(match.get("home_team")) or clean_text(match.get("home_team_id"))
    away = clean_text(match.get("away_team")) or clean_text(match.get("away_team_id"))
    if home and away:
        return f"{home} - {away}"
    return clean_text(match.get("id")) or "Wedstrijd"


KNOCKOUT_ROUNDS = (
    "Round of 32",
    "Round of 16",
    "Quarter-final",
    "Semi-final",
    "Third-place play-off",
    "Final",
)


def is_knockout_match(match: dict[str, Any]) -> bool:
    return match.get("round") != "Group Stage"


def bracket_slot_payload(label: Any) -> dict[str, str] | None:
    slot_label = clean_text(label)
    if not slot_label:
        return None
    return {"kind": "slot", "label": slot_label}


def knockout_side_payload(
    match: dict[str, Any],
    side: str,
    teams: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    team_id = clean_text(match.get(f"{side}_team_id"))
    if team_id:
        team = teams.get(team_id, {})
        return {
            "kind": "team",
            "id": team_id,
            "name": clean_text(match.get(f"{side}_team"))
            or clean_text(team.get("name"))
            or team_id,
            "code": clean_text(team.get("code")),
        }
    return bracket_slot_payload(match.get(f"{side}_placeholder"))


def knockout_match_status(match: dict[str, Any], now: datetime) -> str:
    if not match.get("home_team_id") or not match.get("away_team_id"):
        return "not_yet_actionable"
    if match.get("status") == "completed" or (
        match.get("home_score") is not None and match.get("away_score") is not None
    ):
        return "completed"
    if is_prediction_locked(match, now):
        return "locked"
    return "open"


def knockout_missing_action_items(
    data: dict[str, Any],
    predictions: dict[str, dict[str, Any]],
    quiz_predictions: dict[str, Any],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    # Knockout draw and advancing-team prediction semantics are intentionally
    # unresolved; until decided, knockout matches use the existing score shape.
    items: list[dict[str, Any]] = []
    current = now or utc_now()
    for match in sorted(
        (candidate for candidate in data["matches"] if is_knockout_match(candidate)),
        key=match_kickoff,
    ):
        if not match.get("home_team_id") or not match.get("away_team_id"):
            continue
        if is_prediction_locked(match, current):
            continue
        base_item = {
            "match_id": match["id"],
            "label": match_display_label(match),
            "subtitle": " - ".join(
                part
                for part in (str(match.get("date") or ""), clean_text(match.get("round")))
                if part
            ),
            "deadline": iso_utc(match_lock_time(match)),
            "target_view": "knockout",
            "target_match_id": match["id"],
        }
        if match["id"] not in predictions:
            items.append(
                {
                    **base_item,
                    "kind": "prediction",
                    "title": "Knockout voorspelling open",
                    "body": f"{base_item['label']} mist nog een scorevoorspelling.",
                    "target_kind": "prediction",
                }
            )
        quiz = match.get("quiz")
        quiz_prediction = quiz_predictions.get(match["id"])
        if quiz and not quiz_complete(quiz, quiz_prediction):
            items.append(
                {
                    **base_item,
                    "kind": "quiz",
                    "title": "Knockout quizvraag open",
                    "body": f"{base_item['label']} mist nog een quizantwoord.",
                    "target_kind": "quiz",
                }
            )
    return items


def build_knockout_projection(
    data: dict[str, Any],
    *,
    predictions: dict[str, dict[str, Any]],
    quiz_predictions: dict[str, Any],
    leeuwtje_match_ids: list[str],
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or utc_now()
    teams = {team["id"]: team for team in data.get("teams", [])}
    venues = {venue["id"]: venue for venue in data.get("venues", [])}
    missing_items = knockout_missing_action_items(data, predictions, quiz_predictions, current)
    missing_by_match: dict[str, list[dict[str, Any]]] = {}
    for item in missing_items:
        missing_by_match.setdefault(item["match_id"], []).append(item)
    knockout_matches = [match for match in data.get("matches", []) if is_knockout_match(match)]
    known_open = [
        match
        for match in knockout_matches
        if match.get("home_team_id")
        and match.get("away_team_id")
        and not is_prediction_locked(match, current)
    ]
    rounds = []
    for round_name in KNOCKOUT_ROUNDS:
        round_matches = []
        for match in sorted(
            (candidate for candidate in knockout_matches if candidate.get("round") == round_name),
            key=lambda candidate: int(candidate.get("match_number") or 0),
        ):
            venue = venues.get(match.get("venue_id"), {})
            status = knockout_match_status(match, current)
            lock_at = match_lock_time(match)
            round_matches.append(
                {
                    "id": match["id"],
                    "match_number": match.get("match_number"),
                    "round": match.get("round"),
                    "date": match.get("date"),
                    "kickoff_at": iso_utc(match_kickoff(match)),
                    "lock_at": iso_utc(lock_at),
                    "venue": (
                        {
                            "id": match.get("venue_id"),
                            "name": venue.get("name"),
                            "city": venue.get("city"),
                        }
                        if venue
                        else None
                    ),
                    "home": knockout_side_payload(match, "home", teams),
                    "away": knockout_side_payload(match, "away", teams),
                    "status": status,
                    "locked": status in {"locked", "completed"},
                    "prediction": predictions.get(match["id"]),
                    "quiz": match.get("quiz"),
                    "quiz_prediction": quiz_predictions.get(match["id"]),
                    "leeuwtje": match["id"] in set(leeuwtje_match_ids),
                    "missing_actions": missing_by_match.get(match["id"], []),
                }
            )
        if round_matches:
            rounds.append({"round": round_name, "matches": round_matches})
    return {
        "is_relevant": bool(known_open or missing_items)
        or any(
            current <= match_kickoff(match) <= current + timedelta(days=7)
            and match.get("status") != "completed"
            for match in knockout_matches
        ),
        "rounds": rounds,
        "missing_actions": missing_items,
    }


def visible_missing_action_matches(
    data: dict[str, Any],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    current = now or utc_now()
    today = current.astimezone(AMSTERDAM_TZ).date()
    visible_dates = {today, today + timedelta(days=1)}
    return [
        match
        for match in sorted(data["matches"], key=match_kickoff)
        if local_match_date(match) in visible_dates
        and match.get("home_team_id")
        and match.get("away_team_id")
        and not is_prediction_locked(match, current)
    ]


def missing_action_items(
    data: dict[str, Any],
    predictions: dict[str, dict[str, Any]],
    quiz_predictions: dict[str, Any],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    current = now or utc_now()
    for match in visible_missing_action_matches(data, current):
        base_item = {
            "match_id": match["id"],
            "label": match_display_label(match),
            "subtitle": " - ".join(
                part
                for part in (
                    str(match.get("date") or ""),
                    clean_text(match.get("round")),
                    clean_text(match.get("group")),
                )
                if part
            ),
            "deadline": iso_utc(match_lock_time(match)),
            "target_view": "predictions",
            "target_match_id": match["id"],
        }
        if match["id"] not in predictions:
            items.append(
                {
                    **base_item,
                    "kind": "prediction",
                    "title": "Wedstrijdvoorspelling open",
                    "body": f"{base_item['label']} mist nog een scorevoorspelling.",
                    "target_kind": "prediction",
                }
            )
        quiz = match.get("quiz")
        quiz_prediction = quiz_predictions.get(match["id"])
        if quiz and not quiz_complete(quiz, quiz_prediction):
            items.append(
                {
                    **base_item,
                    "kind": "quiz",
                    "title": "Quizvraag open",
                    "body": f"{base_item['label']} mist nog een quizantwoord.",
                    "target_kind": "quiz",
                }
            )
    return items


def active_broadcast_notifications() -> list[dict[str, Any]]:
    try:
        with get_db() as conn:
            rows = execute(
                conn,
                """
                SELECT id, title, body, starts_at, expires_at, created_by_user_id, created_at
                FROM admin_broadcast_notifications
                WHERE is_active = 1
                  AND deactivated_at IS NULL
                  AND (starts_at IS NULL OR starts_at <= CURRENT_TIMESTAMP)
                  AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                ORDER BY created_at DESC, id DESC
                LIMIT 5
                """,
            ).fetchall()
    except Exception:
        logger.exception("Could not load broadcast notifications")
        return []
    return [
        {
            "type": "broadcast",
            "id": row["id"],
            "count": 1,
            "title": row["title"],
            "body": row["body"],
            "created_by_user_id": row["created_by_user_id"],
            "created_at": row["created_at"],
            "starts_at": row["starts_at"],
            "expires_at": row["expires_at"],
        }
        for row in rows
    ]


def active_admin_sync_issue_notifications(user: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not user or not user.get("is_admin"):
        return []
    try:
        with get_db() as conn:
            rows = active_admin_sync_notifications(conn)
    except Exception:
        logger.exception("Could not load admin sync notifications")
        return []
    return [
        {
            "type": "sync_issue",
            "id": row["id"],
            "count": 1,
            "target_type": row["target_type"],
            "target_id": row["target_id"],
            "title": row["title"],
            "body": row["body"],
            "severity": row["severity"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def badge_unlocked_notifications(badges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not badges:
        return []
    badge_labels = [badge["label"] for badge in badges[:3]]
    extra_count = max(0, len(badges) - len(badge_labels))
    label_text = ", ".join(badge_labels)
    if extra_count:
        label_text = f"{label_text} en {extra_count} meer"
    return [
        {
            "type": "badge_unlocked",
            "count": len(badges),
            "title": "Badge unlocked",
            "body": f"Je hebt {label_text} vrijgespeeld.",
            "badges": badges,
        }
    ]


def build_notifications(
    data: dict[str, Any],
    predictions: dict[str, dict[str, Any]],
    quiz_predictions: dict[str, Any],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    missing_items = missing_action_items(data, predictions, quiz_predictions, now)
    prediction_items = [item for item in missing_items if item["kind"] == "prediction"]
    quiz_items = [item for item in missing_items if item["kind"] == "quiz"]

    notifications = []
    if prediction_items:
        notifications.append(
            {
                "type": "predictions",
                "count": len(prediction_items),
                "match_ids": [item["match_id"] for item in prediction_items],
                "items": prediction_items,
                "title": "Wedstrijdvoorspellingen open",
                "body": (
                    f"{len(prediction_items)} wedstrijd"
                    f"{'' if len(prediction_items) == 1 else 'en'} "
                    f"{'moet' if len(prediction_items) == 1 else 'moeten'} "
                    "nog ingevuld worden."
                ),
            }
        )
    if quiz_items:
        notifications.append(
            {
                "type": "quiz",
                "count": len(quiz_items),
                "match_ids": [item["match_id"] for item in quiz_items],
                "items": quiz_items,
                "title": "Quizvragen open",
                "body": (
                    f"{len(quiz_items)} quizvraag"
                    f"{'' if len(quiz_items) == 1 else 'en'} "
                    f"{'moet' if len(quiz_items) == 1 else 'moeten'} "
                    "nog ingevuld worden."
                ),
            }
        )
    return active_broadcast_notifications() + notifications


def build_wall_of_shame(data: dict[str, Any], now: datetime | None = None) -> list[dict[str, Any]]:
    current = now or utc_now()
    with get_db() as conn:
        users = execute(
            conn,
            """
            SELECT id, name, email, profile_image_url
            FROM users
            WHERE archived_at IS NULL
            ORDER BY name
            """,
        ).fetchall()
        prediction_rows = execute(
            conn,
            "SELECT user_id, match_id, home_score, away_score FROM match_predictions",
        ).fetchall()
        quiz_rows = execute(
            conn,
            """
            SELECT user_id, match_id, answer, viewership_prediction
            FROM quiz_predictions
            """,
        ).fetchall()
    predictions_by_user: dict[int, dict[str, dict[str, Any]]] = {}
    for row in prediction_rows:
        predictions_by_user.setdefault(row["user_id"], {})[row["match_id"]] = {
            "home_score": row["home_score"],
            "away_score": row["away_score"],
        }
    quiz_by_user: dict[int, dict[str, dict[str, Any]]] = {}
    for row in quiz_rows:
        quiz_by_user.setdefault(row["user_id"], {})[row["match_id"]] = {
            "answer": row["answer"] or "",
            "viewership_prediction": row["viewership_prediction"],
        }

    shame_rows = []
    for user in users:
        items = missing_action_items(
            data,
            predictions_by_user.get(user["id"], {}),
            quiz_by_user.get(user["id"], {}),
            current,
        )
        if not items:
            continue
        real_name = derived_real_name(user["email"])
        shame_rows.append(
            {
                "user_id": user["id"],
                "name": user["name"],
                "email": user["email"],
                **real_name,
                "profile_picture": user_profile_picture(user),
                "missing_count": len(items),
                "missing_items": items,
            }
        )
    return sorted(shame_rows, key=lambda row: (-row["missing_count"], row["name"].lower()))


def outcome_bucket(prediction: Any) -> str:
    result = prediction_result(prediction)
    if result > 0:
        return "home"
    if result < 0:
        return "away"
    return "draw"


def build_matchday_summary(
    data: dict[str, Any],
    user_id: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or utc_now()
    current_session = current_tournament_session_date(current)
    matches_with_dates = [
        (tournament_session_date(match), match)
        for match in data["matches"]
        if is_matchday_window_match(match)
    ]
    match_dates = sorted({match_date for match_date, _ in matches_with_dates})
    target_date = current_session if current_session in match_dates else None
    if target_date is None:
        target_date = next(
            (match_date for match_date in match_dates if match_date > current_session), None
        )
    if target_date is None and match_dates:
        target_date = match_dates[-1]

    if target_date is None:
        return {"available": False, "matches": [], "sessions": []}

    ordered = [
        (match_date, match)
        for match_date, match in sorted(matches_with_dates, key=lambda item: match_kickoff(item[1]))
        if match.get("home_team_id") and match.get("away_team_id")
    ]
    visible_match_ids = {match["id"] for _match_date, match in ordered}

    with get_db() as conn:
        predictions = execute(
            conn,
            "SELECT user_id, match_id, home_score, away_score FROM match_predictions",
        ).fetchall()
        quiz_predictions = execute(
            conn,
            """
            SELECT user_id, match_id, answer, viewership_prediction
            FROM quiz_predictions
            WHERE COALESCE(answer, '') != ''
            """,
        ).fetchall()
        leeuwtjes = execute(conn, "SELECT user_id, match_id FROM leeuwtje_predictions").fetchall()
        my_predictions = (
            execute(
                conn,
                "SELECT match_id, home_score, away_score FROM match_predictions WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            if user_id is not None
            else []
        )
        my_quiz_predictions = (
            execute(
                conn,
                """
                SELECT match_id, answer, viewership_prediction
                FROM quiz_predictions
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchall()
            if user_id is not None
            else []
        )
        my_leeuwtjes = (
            execute(
                conn, "SELECT match_id FROM leeuwtje_predictions WHERE user_id = ?", (user_id,)
            ).fetchall()
            if user_id is not None
            else []
        )
        my_top_scorer_row = (
            execute(
                conn,
                """
                SELECT player_name, player_name_2, player_name_3,
                       striker_name_1, striker_name_2, striker_name_3,
                       striker_name_4, striker_name_5
                FROM top_scorer_predictions
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            if user_id is not None
            else None
        )

    predictions_by_match: dict[str, list[Any]] = {}
    for prediction in predictions:
        if prediction["match_id"] in visible_match_ids:
            predictions_by_match.setdefault(prediction["match_id"], []).append(prediction)
    quiz_counts = Counter(
        row["match_id"] for row in quiz_predictions if row["match_id"] in visible_match_ids
    )
    leeuwtje_counts = Counter(
        row["match_id"] for row in leeuwtjes if row["match_id"] in visible_match_ids
    )
    my_prediction_ids = {
        row["match_id"] for row in my_predictions if row["match_id"] in visible_match_ids
    }
    my_predictions_by_match = {
        row["match_id"]: {"home_score": row["home_score"], "away_score": row["away_score"]}
        for row in my_predictions
        if row["match_id"] in visible_match_ids
    }
    my_match_points = user_match_points_by_match(
        data,
        {row["match_id"]: row for row in my_predictions},
        {row["match_id"]: row for row in my_quiz_predictions},
        [row["match_id"] for row in my_leeuwtjes],
        striker_pick_names(my_top_scorer_row),
    )

    def session_matches(session_date: Any) -> list[dict[str, Any]]:
        matches = []
        for match_date, match in ordered:
            if match_date != session_date:
                continue
            match_predictions = predictions_by_match.get(match["id"], [])
            outcomes = Counter(outcome_bucket(prediction) for prediction in match_predictions)
            points = my_match_points.get(match["id"])
            matches.append(
                {
                    "match_id": match["id"],
                    "id": match["id"],
                    "date": match["date"],
                    "time_utc": match["time_utc"],
                    "home_team_id": match["home_team_id"],
                    "away_team_id": match["away_team_id"],
                    "home_score": match.get("home_score"),
                    "away_score": match.get("away_score"),
                    "round": match["round"],
                    "group": match.get("group"),
                    "venue_id": match.get("venue_id"),
                    "quiz": match.get("quiz"),
                    "locked": is_prediction_locked(match, current),
                    "completed": match_result(match) is not None,
                    "has_my_prediction": match["id"] in my_prediction_ids,
                    "my_prediction": my_predictions_by_match.get(match["id"]),
                    "my_points": points,
                    "prediction_count": len(match_predictions),
                    "home_win_count": outcomes["home"],
                    "draw_count": outcomes["draw"],
                    "away_win_count": outcomes["away"],
                    "quiz_answer_count": quiz_counts[match["id"]],
                    "leeuwtjes_count": leeuwtje_counts[match["id"]],
                }
            )
        return matches

    sessions = []
    for match_date in match_dates:
        matches = session_matches(match_date)
        if not matches:
            continue
        completed_count = sum(1 for match in matches if match["completed"])
        sessions.append(
            {
                "date": match_date.isoformat(),
                "is_today": match_date == current_session,
                "is_historic": match_date < current_session,
                "is_future": completed_count == 0 and match_date > current_session,
                "completed_count": completed_count,
                "matches": matches,
            }
        )

    if not sessions:
        return {"available": False, "matches": [], "sessions": []}

    current_index = next(
        (
            index
            for index, session in enumerate(sessions)
            if session["date"] == target_date.isoformat()
        ),
        0,
    )
    selected_session = sessions[current_index]

    return {
        "available": True,
        "date": selected_session["date"],
        "is_today": selected_session["is_today"],
        "is_historic": selected_session["is_historic"],
        "is_future": selected_session["is_future"],
        "completed_count": selected_session["completed_count"],
        "current_session_index": current_index,
        "sessions": sessions,
        "matches": selected_session["matches"],
    }


def matchday_match_detail(
    data: dict[str, Any],
    match_id: str,
    user_id: int | None = None,
    now: datetime | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    current = now or utc_now()
    match = match_by_id(data, match_id)
    if match is None:
        return None, "not_found"
    if not is_prediction_locked(match, current):
        return None, "not_locked"

    with get_db() as conn:
        users = execute(
            conn,
            """
            SELECT id, name, profile_image_url
            FROM users
            WHERE archived_at IS NULL
            ORDER BY name
            """,
        ).fetchall()
        predictions = execute(
            conn,
            """
            SELECT user_id, home_score, away_score
            FROM match_predictions
            WHERE match_id = ?
            """,
            (match_id,),
        ).fetchall()
        quiz_rows = execute(
            conn,
            """
            SELECT user_id, answer
            FROM quiz_predictions
            WHERE match_id = ? AND COALESCE(answer, '') != ''
            """,
            (match_id,),
        ).fetchall()
        leeuwtje_rows = execute(
            conn,
            "SELECT user_id FROM leeuwtje_predictions WHERE match_id = ?",
            (match_id,),
        ).fetchall()
        top_scorer_rows = execute(
            conn,
            """
            SELECT user_id, player_name, player_name_2, player_name_3,
                   striker_name_1, striker_name_2, striker_name_3,
                   striker_name_4, striker_name_5
            FROM top_scorer_predictions
            """,
        ).fetchall()
        goal_rows = execute(
            conn,
            """
            SELECT match_id, player_name, event_type, detail, comments
            FROM match_events
            WHERE match_id = ? AND LOWER(event_type) = 'goal'
            """,
            (match_id,),
        ).fetchall()
        scorer_links = accepted_match_scorer_links(conn)

    users_by_id = {row["id"]: row for row in users}
    quiz_by_user = {row["user_id"]: row["answer"] for row in quiz_rows}
    quiz_prediction_by_user = {
        row["user_id"]: {"answer": row["answer"] or "", "viewership_prediction": None}
        for row in quiz_rows
    }
    leeuwtje_user_ids = {row["user_id"] for row in leeuwtje_rows}
    outcomes = Counter(outcome_bucket(prediction) for prediction in predictions)
    predictions_by_user = {
        row["user_id"]: {"home_score": row["home_score"], "away_score": row["away_score"]}
        for row in predictions
    }
    striker_picks_by_user = {row["user_id"]: striker_pick_names(row) for row in top_scorer_rows}

    rows = []
    for prediction in predictions:
        user = users_by_id.get(prediction["user_id"])
        if user is None:
            continue
        striker_entry = striker_points_for_match_from_picks(
            match,
            striker_picks_by_user.get(user["id"], []),
            goal_rows,
            scorer_links,
        )
        points = match_points_for_prediction(
            match,
            predictions_by_user[user["id"]],
            quiz_prediction_by_user.get(user["id"]),
            leeuwtje=user["id"] in leeuwtje_user_ids,
            striker_entry=striker_entry,
        )
        rows.append(
            {
                "user_id": user["id"],
                "name": user["name"],
                "profile_picture": user_profile_picture(user),
                "home_score": prediction["home_score"],
                "away_score": prediction["away_score"],
                "score_label": f"{prediction['home_score']} - {prediction['away_score']}",
                "outcome": outcome_bucket(prediction),
                "leeuwtje": user["id"] in leeuwtje_user_ids,
                "quiz_answer": quiz_by_user.get(user["id"]),
                "points": points,
            }
        )

    rows.sort(
        key=lambda row: (
            int(row["home_score"]),
            int(row["away_score"]),
            normalize_identity(row["name"]),
        )
    )
    score_groups = []
    for score_key, score_rows in itertools.groupby(
        rows, key=lambda row: (row["home_score"], row["away_score"])
    ):
        grouped_rows = list(score_rows)
        score_groups.append(
            {
                "home_score": score_key[0],
                "away_score": score_key[1],
                "score_label": f"{score_key[0]} - {score_key[1]}",
                "count": len(grouped_rows),
                "predictions": grouped_rows,
            }
        )

    quiz_answer_groups = []
    sorted_quiz_rows = sorted(
        [row for row in rows if row.get("quiz_answer")],
        key=lambda row: (normalize_answer(row["quiz_answer"]), normalize_identity(row["name"])),
    )
    for answer, answer_rows in itertools.groupby(
        sorted_quiz_rows, key=lambda row: row["quiz_answer"]
    ):
        grouped_rows = list(answer_rows)
        quiz_answer_groups.append(
            {
                "answer": answer,
                "count": len(grouped_rows),
                "predictions": grouped_rows,
            }
        )

    viewer_prediction = predictions_by_user.get(user_id) if user_id is not None else None
    viewer_points = None
    if user_id is not None:
        viewer_points = match_points_for_prediction(
            match,
            viewer_prediction,
            quiz_prediction_by_user.get(user_id),
            leeuwtje=user_id in leeuwtje_user_ids,
            striker_entry=striker_points_for_match_from_picks(
                match,
                striker_picks_by_user.get(user_id, []),
                goal_rows,
                scorer_links,
            ),
        )

    return (
        {
            "match": {
                "match_id": match["id"],
                "id": match["id"],
                "date": match["date"],
                "time_utc": match["time_utc"],
                "home_team_id": match["home_team_id"],
                "away_team_id": match["away_team_id"],
                "round": match["round"],
                "group": match.get("group"),
                "venue_id": match.get("venue_id"),
                "quiz": match.get("quiz"),
                "locked": True,
                "prediction_count": len(rows),
                "home_win_count": outcomes["home"],
                "draw_count": outcomes["draw"],
                "away_win_count": outcomes["away"],
                "quiz_answer_count": len(sorted_quiz_rows),
                "leeuwtjes_count": len(leeuwtje_user_ids),
                "my_prediction": viewer_prediction,
                "my_points": viewer_points,
            },
            "score_groups": score_groups,
            "quiz_answer_groups": quiz_answer_groups,
            "predictions": rows,
        },
        None,
    )


def top_daily_scores_with_ties(
    daily_points: Counter[int],
    user_names: dict[int, str],
    user_pictures: dict[int, dict[str, Any]] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    sorted_scores = [
        (user_id, points)
        for user_id, points in sorted(
            daily_points.items(),
            key=lambda item: (-item[1], normalize_identity(user_names.get(item[0], ""))),
        )
        if points > 0
    ]
    sorted_scores = sorted_scores[:limit]

    ranked_scores = []
    previous_points = None
    current_rank = 0
    for index, (user_id, points) in enumerate(sorted_scores, start=1):
        if points != previous_points:
            current_rank = index
            previous_points = points
        ranked_scores.append(
            {
                "user_id": user_id,
                "rank": current_rank,
                "name": user_names.get(user_id, "Unknown"),
                "points": points,
                "profile_picture": (user_pictures or {}).get(
                    user_id,
                    {
                        "initials": initials(user_names.get(user_id, "Unknown")),
                        "hue": avatar_hue(user_names.get(user_id, "Unknown")),
                    },
                ),
            }
        )
    return ranked_scores


def top_movers_with_ties(
    leaderboard: list[dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    sorted_movers = sorted(
        [row for row in leaderboard if abs(int(row.get("rank_movement") or 0)) > 0],
        key=lambda row: (
            -abs(int(row.get("rank_movement") or 0)),
            -int(row.get("rank_movement") or 0),
            int(row.get("rank") or 999_999),
            normalize_identity(row.get("name", "")),
        ),
    )
    if len(sorted_movers) > limit:
        cutoff_movement = abs(int(sorted_movers[limit - 1].get("rank_movement") or 0))
        sorted_movers = [
            row
            for row in sorted_movers
            if abs(int(row.get("rank_movement") or 0)) >= cutoff_movement
        ]

    return [
        {
            "user_id": row["user_id"],
            "name": row["name"],
            "rank": row.get("rank"),
            "rank_previous": row.get("rank_previous"),
            "rank_movement": row.get("rank_movement") or 0,
            "profile_picture": row.get("profile_picture"),
        }
        for row in sorted_movers
    ]


def rank_users_by_scores(
    users: list[Any],
    scores: dict[int, int],
) -> dict[int, int]:
    ranked_users = sorted(
        users,
        key=lambda user: (
            -scores.get(user["id"], 0),
            normalize_identity(row_value(user, "name") or ""),
        ),
    )
    return {user["id"]: index for index, user in enumerate(ranked_users, start=1)}


def rank_changes_between_scores(
    users: list[Any],
    previous_scores: dict[int, int],
    current_scores: dict[int, int],
    user_pictures: dict[int, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    previous_ranks = rank_users_by_scores(users, previous_scores)
    current_ranks = rank_users_by_scores(users, current_scores)
    movers = []
    for user in users:
        user_id = user["id"]
        movement = previous_ranks[user_id] - current_ranks[user_id]
        if movement == 0:
            continue
        name = row_value(user, "name") or "Unknown"
        movers.append(
            {
                "user_id": user_id,
                "name": name,
                "rank": current_ranks[user_id],
                "rank_previous": previous_ranks[user_id],
                "rank_movement": movement,
                "profile_picture": (user_pictures or {}).get(
                    user_id,
                    {
                        "initials": initials(name),
                        "hue": avatar_hue(name),
                    },
                ),
            }
        )
    return movers


def daily_movers_with_ties(
    data: dict[str, Any],
    users: list[Any],
    by_user: dict[int, list[Any]],
    quiz_by_user: dict[int, dict[str, Any]],
    leeuwtjes_by_user: dict[int, set[str]],
    viewership_winners: set[tuple[int, str]],
    target_date: Any,
    user_pictures: dict[int, dict[str, Any]] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    previous_dates = sorted(
        {
            tournament_session_date(match)
            for match in data["matches"]
            if match_result(match) is not None and tournament_session_date(match) < target_date
        }
    )
    previous_date = previous_dates[-1] if previous_dates else None
    previous_scores = {
        user["id"]: (
            score_through_date(
                data,
                by_user.get(user["id"], []),
                quiz_by_user.get(user["id"], {}),
                leeuwtjes_by_user.get(user["id"], set()),
                viewership_winners,
                previous_date,
            )
            if previous_date is not None
            else 0
        )
        for user in users
    }
    current_scores = {
        user["id"]: score_through_date(
            data,
            by_user.get(user["id"], []),
            quiz_by_user.get(user["id"], {}),
            leeuwtjes_by_user.get(user["id"], set()),
            viewership_winners,
            target_date,
        )
        for user in users
    }
    return sorted_rank_changes(
        rank_changes_between_scores(users, previous_scores, current_scores, user_pictures),
        mode="absolute",
        limit=limit,
    )


def leaderboard_rank_changes(
    leaderboard: list[dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    movers = [row for row in leaderboard if abs(int(row.get("rank_movement") or 0)) > 0]
    return sorted_rank_changes(movers, mode="absolute", limit=limit)


def sorted_rank_changes(
    movers: list[dict[str, Any]],
    *,
    mode: str,
    limit: int,
) -> list[dict[str, Any]]:
    if mode == "up":
        filtered = [row for row in movers if int(row["rank_movement"]) > 0]

        def up_sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
            return (
                -int(row["rank_movement"]),
                int(row["rank"]),
                normalize_identity(row["name"]),
            )

        sorted_rows = sorted(filtered, key=up_sort_key)
    elif mode == "down":
        filtered = [row for row in movers if int(row["rank_movement"]) < 0]

        def down_sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
            return (
                int(row["rank_movement"]),
                int(row["rank"]),
                normalize_identity(row["name"]),
            )

        sorted_rows = sorted(filtered, key=down_sort_key)
    else:
        filtered = movers

        def absolute_sort_key(row: dict[str, Any]) -> tuple[int, int, int, str]:
            return (
                -abs(int(row["rank_movement"])),
                -int(row["rank_movement"]),
                int(row["rank"]),
                normalize_identity(row["name"]),
            )

        sorted_rows = sorted(filtered, key=absolute_sort_key)

    return sorted_rows[:limit]


def build_daily_recap(
    data: dict[str, Any],
    now: datetime | None = None,
    leaderboard: list[dict[str, Any]] | None = None,
    viewer_user_id: int | None = None,
) -> dict[str, Any]:
    current = now or utc_now()
    current_session = current_tournament_session_date(current)
    completed_matches = [
        match
        for match in data["matches"]
        if match_result(match) is not None
        and match_kickoff(match) <= current
        and tournament_session_date(match) <= current_session
    ]
    if not completed_matches:
        return {
            "available": False,
            "title": "Daily recap",
            "body": "De recap verschijnt zodra er gespeelde wedstrijden met uitslagen zijn.",
            "moments": [],
            "top_players": [],
            "day_scores": [],
            "top_movers": [],
            "top_winners": [],
            "top_losers": [],
        }

    target_date = max(tournament_session_date(match) for match in completed_matches)
    target_matches = [
        match for match in completed_matches if tournament_session_date(match) == target_date
    ]
    target_ids = {match["id"] for match in target_matches}
    teams = {team["id"]: team for team in data["teams"]}

    with get_db() as conn:
        predictions = execute(conn, "SELECT * FROM match_predictions").fetchall()
        quiz_predictions = execute(conn, "SELECT * FROM quiz_predictions").fetchall()
        users = execute(
            conn,
            "SELECT id, name, profile_image_url FROM users WHERE archived_at IS NULL",
        ).fetchall()
        leeuwtjes = execute(conn, "SELECT user_id, match_id FROM leeuwtje_predictions").fetchall()
        top_scorers = {
            row["user_id"]: row
            for row in execute(
                conn,
                """
                SELECT user_id, player_name, player_name_2, player_name_3,
                       striker_name_1, striker_name_2, striker_name_3,
                       striker_name_4, striker_name_5
                FROM top_scorer_predictions
                """,
            ).fetchall()
        }

    user_names = {user["id"]: user["name"] for user in users}
    user_pictures = {user["id"]: user_profile_picture(user) for user in users}
    users_list = list(users)
    by_user: dict[int, list[Any]] = {}
    for prediction in predictions:
        by_user.setdefault(prediction["user_id"], []).append(prediction)
    quiz_by_user: dict[int, dict[str, Any]] = {}
    for prediction in quiz_predictions:
        quiz_by_user.setdefault(prediction["user_id"], {})[prediction["match_id"]] = prediction
    leeuwtjes_by_user: dict[int, set[str]] = {}
    for row in leeuwtjes:
        leeuwtjes_by_user.setdefault(row["user_id"], set()).add(row["match_id"])

    daily_points: Counter[int] = Counter()
    points_by_user: dict[int, dict[str, dict[str, Any]]] = {}
    previous_dates = sorted(
        {
            tournament_session_date(match)
            for match in completed_matches
            if tournament_session_date(match) < target_date
        }
    )
    previous_date = previous_dates[-1] if previous_dates else None
    match_dates = {match["id"]: tournament_session_date(match) for match in data["matches"]}
    previous_scores: dict[int, int] = {}
    current_scores: dict[int, int] = {}
    for user in users_list:
        user_predictions = {
            prediction["match_id"]: prediction for prediction in by_user.get(user["id"], [])
        }
        points_by_match = user_match_points_by_match(
            data,
            user_predictions,
            quiz_by_user.get(user["id"], {}),
            list(leeuwtjes_by_user.get(user["id"], set())),
            striker_pick_names(top_scorers.get(user["id"])),
        )
        points_by_user[user["id"]] = points_by_match
        daily_points[user["id"]] = sum(
            int(points.get("total_points") or 0)
            for match_id, points in points_by_match.items()
            if match_id in target_ids
        )
        previous_scores[user["id"]] = (
            sum(
                int(points.get("total_points") or 0)
                for match_id, points in points_by_match.items()
                if previous_date is not None and match_dates.get(match_id) <= previous_date
            )
            if previous_date is not None
            else 0
        )
        current_scores[user["id"]] = sum(
            int(points.get("total_points") or 0)
            for match_id, points in points_by_match.items()
            if match_dates.get(match_id) <= target_date
        )

    top_user_id, top_points = (None, 0)
    if daily_points:
        top_user_id, top_points = daily_points.most_common(1)[0]
    top_players = top_daily_scores_with_ties(daily_points, user_names, user_pictures)
    rank_changes = rank_changes_between_scores(
        users_list,
        previous_scores,
        current_scores,
        user_pictures,
    )
    top_movers = sorted_rank_changes(rank_changes, mode="absolute", limit=5)
    top_winners = sorted_rank_changes(rank_changes, mode="up", limit=3)
    top_losers = sorted_rank_changes(rank_changes, mode="down", limit=3)

    moments = []
    match_labels: dict[str, str] = {}
    for match in sorted(target_matches, key=match_kickoff):
        label = (
            f"{teams.get(match['home_team_id'], {}).get('name', match['home_team_id'])} "
            f"{match['home_score']}-{match['away_score']} "
            f"{teams.get(match['away_team_id'], {}).get('name', match['away_team_id'])}"
        )
        match_labels[match["id"]] = label
        moments.append({"match_id": match["id"], "label": label})

    day_score_rows = []
    sorted_daily_scores = sorted(
        daily_points.items(),
        key=lambda item: (-item[1], normalize_identity(user_names.get(item[0], ""))),
    )
    previous_points = None
    current_rank = 0
    for index, (user_id, points) in enumerate(sorted_daily_scores, start=1):
        if points != previous_points:
            current_rank = index
            previous_points = points
        day_score_rows.append(
            {
                "user_id": user_id,
                "rank": current_rank,
                "name": user_names.get(user_id, "Unknown"),
                "points": points,
                "profile_picture": user_pictures.get(
                    user_id,
                    {
                        "initials": initials(user_names.get(user_id, "Unknown")),
                        "hue": avatar_hue(user_names.get(user_id, "Unknown")),
                    },
                ),
                "matches": [
                    {
                        "match_id": match["id"],
                        "label": match_labels.get(match["id"], match["id"]),
                        "points": points_by_user.get(user_id, {}).get(match["id"]),
                    }
                    for match in sorted(target_matches, key=match_kickoff)
                ],
            }
        )

    return {
        "available": True,
        "title": f"Recap {target_date.isoformat()}",
        "body": f"{len(target_matches)} gespeelde wedstrijden verwerkt.",
        "date": target_date.isoformat(),
        "moments": moments,
        "top_player": (
            {"name": user_names.get(top_user_id), "points": top_points}
            if top_user_id is not None
            else None
        ),
        "top_players": top_players,
        "day_scores": day_score_rows,
        "top_movers": top_movers,
        "top_winners": top_winners,
        "top_losers": top_losers,
    }


def user_pool_state(user: dict[str, Any] | None, data: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    prediction_rows = []
    quiz_prediction_rows = []
    leeuwtje_rows = []
    winner_pick = None
    top_scorer_pick = ""
    striker_picks: list[str] = []
    if user:
        with get_db() as conn:
            prediction_rows = execute(
                conn,
                "SELECT match_id, home_score, away_score FROM match_predictions WHERE user_id = ?",
                (user["id"],),
            ).fetchall()
            winner_row = execute(
                conn,
                "SELECT team_id FROM winner_predictions WHERE user_id = ?",
                (user["id"],),
            ).fetchone()
            top_scorer_row = execute(
                conn,
                """
                SELECT player_name, player_name_2, player_name_3,
                       striker_name_1, striker_name_2, striker_name_3,
                       striker_name_4, striker_name_5
                FROM top_scorer_predictions
                WHERE user_id = ?
                """,
                (user["id"],),
            ).fetchone()
            quiz_prediction_rows = execute(
                conn,
                """
                SELECT match_id, answer, viewership_prediction
                FROM quiz_predictions
                WHERE user_id = ?
                """,
                (user["id"],),
            ).fetchall()
            leeuwtje_rows = execute(
                conn,
                "SELECT match_id FROM leeuwtje_predictions WHERE user_id = ?",
                (user["id"],),
            ).fetchall()
        winner_pick = winner_row["team_id"] if winner_row else None
        top_scorer_pick = top_scorer_pick_name(top_scorer_row)
        striker_picks = striker_pick_names(top_scorer_row)

    predictions = {
        row["match_id"]: {"home_score": row["home_score"], "away_score": row["away_score"]}
        for row in prediction_rows
    }
    quiz_predictions = {
        row["match_id"]: {
            "answer": row["answer"] or "",
            "viewership_prediction": row["viewership_prediction"],
        }
        for row in quiz_prediction_rows
    }
    leeuwtje_match_ids = [row["match_id"] for row in leeuwtje_rows]
    match_points = user_match_points_by_match(
        data,
        predictions,
        quiz_predictions,
        leeuwtje_match_ids,
        striker_picks,
    )
    group_stage_ids = {match["id"] for match in data["matches"] if match["round"] == "Group Stage"}
    group_stage_predictions = sum(1 for match_id in predictions if match_id in group_stage_ids)
    group_stage_quiz_total = sum(1 for match in data["matches"] if match.get("quiz"))
    group_stage_quiz_predictions = sum(
        1
        for match in data["matches"]
        if match.get("quiz") and quiz_complete(match["quiz"], quiz_predictions.get(match["id"]))
    )
    required_group_id = next(
        (group["id"] for group in data["groups"] if NETHERLANDS_TEAM_ID in group["teams"]),
        None,
    )
    required_group_ids = {
        match["id"]
        for match in data["matches"]
        if match["round"] == "Group Stage" and match.get("group") == required_group_id
    }
    required_group_predictions = sum(
        1 for match_id in predictions if match_id in required_group_ids
    )
    knockout_open = [
        match["id"]
        for match in data["matches"]
        if match["round"] != "Group Stage"
        and match.get("home_team_id")
        and match.get("away_team_id")
    ]
    match_locks = {
        match["id"]: {
            "locked": is_prediction_locked(match, now),
            "kickoff_at": iso_utc(match_kickoff(match)),
            "lock_at": iso_utc(match_lock_time(match)),
        }
        for match in data["matches"]
    }
    tournament_picks_reveal_at = tournament_picks_lock_time(data)
    tournament_picks_locked = are_tournament_picks_locked(data, now)
    tournament_picks_revealed = are_tournament_picks_revealed(data, now)
    leaderboard = build_leaderboard(
        data,
        viewer_user_id=user["id"] if user else None,
        viewer_is_admin=bool(user and user.get("is_admin")),
        now=now,
    )
    prize_pot_status = user.get("prize_pot_status") if user else None
    prize_pot_count = prize_pot_joined_count() if user else 0
    viewer_leaderboard_row = next(
        (row for row in leaderboard if user and row["user_id"] == user["id"]),
        None,
    )
    viewer_badges = viewer_leaderboard_row.get("badges", []) if viewer_leaderboard_row else []

    return {
        "me": user,
        "predictions": predictions,
        "quiz_predictions": quiz_predictions,
        "leeuwtjes_match_ids": leeuwtje_match_ids,
        "match_points": match_points,
        "winner_pick": winner_pick,
        "top_scorer_pick": top_scorer_pick or None,
        "striker_picks": striker_picks,
        "top_scorer_picks": striker_picks,
        "leaderboard": leaderboard,
        "wall_of_shame": build_wall_of_shame(data, now),
        "badge_catalog": badge_catalog(),
        "notifications": (
            active_admin_sync_issue_notifications(user)
            + prize_pot_notification(user.get("prize_pot_status") if user else None)
            + badge_unlocked_notifications(viewer_badges)
            + build_notifications(data, predictions, quiz_predictions, now)
        ),
        "prize_pot": prize_pot_payload_for_user(prize_pot_status, prize_pot_count),
        "matchday": build_matchday_summary(data, user["id"] if user else None, now),
        "knockout": build_knockout_projection(
            data,
            predictions=predictions,
            quiz_predictions=quiz_predictions,
            leeuwtje_match_ids=leeuwtje_match_ids,
            now=now,
        ),
        "daily_recap": build_daily_recap(
            data, now, leaderboard, viewer_user_id=user["id"] if user else None
        ),
        "newsletters": newsletter_articles(),
        "progress": {
            "group_stage_predictions": group_stage_predictions,
            "group_stage_total": len(group_stage_ids),
            "group_stage_quiz_predictions": group_stage_quiz_predictions,
            "group_stage_quiz_total": group_stage_quiz_total,
            "required_group_id": required_group_id,
            "required_group_predictions": required_group_predictions,
            "required_group_total": len(required_group_ids),
            "winner_selected": winner_pick is not None,
            "top_scorer_selected": bool(top_scorer_pick),
            "strikers_selected": len(striker_picks) >= STRIKER_PICK_COUNT,
            "knockout_open_count": len(knockout_open),
            "leeuwtjes_used": len(leeuwtje_match_ids),
            "leeuwtjes_total": LEEUWTJES_LIMIT,
        },
        "locks": {
            "matches": match_locks,
            "winner_locked": tournament_picks_locked,
            "winner_lock_at": iso_utc(tournament_picks_reveal_at),
            "tournament_picks_locked": tournament_picks_locked,
            "tournament_picks_lock_at": iso_utc(tournament_picks_reveal_at),
        },
        "visibility": {
            "tournament_picks_revealed": tournament_picks_revealed,
            "tournament_picks_reveal_at": iso_utc(tournament_picks_reveal_at),
        },
        "rules": {
            "match_scores": MATCH_SCORE_RULES,
            "group_position": GROUP_POSITION_POINTS,
            "world_cup_winner": WINNER_POINTS,
            "world_cup_top_scorer": TOP_SCORER_POINTS,
            "world_cup_strikers": {
                "count": STRIKER_PICK_COUNT,
                "points_per_goal": STRIKER_GOAL_POINTS,
            },
            "quiz_yes_no": QUIZ_YES_NO_POINTS,
            "quiz_open": QUIZ_OPEN_POINTS,
            "leeuwtjes_total": LEEUWTJES_LIMIT,
            "note": (
                "Predictions, quiz answers and Leeuwtjes can be adjusted until one hour "
                "before kickoff."
            ),
        },
    }


def match_result_details(match_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    match = next((candidate for candidate in data["matches"] if candidate["id"] == match_id), None)
    if match is None:
        return None

    with get_db() as conn:
        result = execute(
            conn,
            """
            SELECT match_id, source, source_fixture_id, status_long, status_short,
                   elapsed, home_score, away_score, synced_at
            FROM match_results
            WHERE match_id = ?
            """,
            (match_id,),
        ).fetchone()
        events = execute(
            conn,
            """
            SELECT elapsed, extra, local_team_id, api_team_id, team_name, api_player_id,
                   player_name, api_assist_id, assist_name, event_type, detail, comments
            FROM match_events
            WHERE match_id = ?
            ORDER BY COALESCE(elapsed, 999), COALESCE(extra, 0), provider_event_key
            """,
            (match_id,),
        ).fetchall()
        clean_sheets = execute(
            conn,
            """
            SELECT local_team_id, api_team_id, team_name
            FROM match_clean_sheets
            WHERE match_id = ?
            ORDER BY team_name
            """,
            (match_id,),
        ).fetchall()
        player_stats = execute(
            conn,
            """
            SELECT local_team_id, api_team_id, team_name, api_player_id, player_name,
                   minutes, position, rating, goals, assists, yellow_cards, red_cards,
                   clean_sheet
            FROM player_match_stats
            WHERE match_id = ?
            ORDER BY team_name, position, player_name
            """,
            (match_id,),
        ).fetchall()

    return {
        "match": match,
        "result": dict(result) if result else None,
        "events": [dict(row) for row in events],
        "clean_sheets": [dict(row) for row in clean_sheets],
        "player_stats": [dict(row) for row in player_stats],
    }


def match_by_id(data: dict[str, Any], match_id: str) -> dict[str, Any] | None:
    return next((match for match in data.get("matches", []) if match.get("id") == match_id), None)


def admin_label_source_from_key(value: Any, fallback: str = "api-football") -> str:
    text = clean_text(value)
    if text.startswith("manual:"):
        return "manual"
    return fallback


def int_payload_value(payload: dict[str, Any], key: str, *, required: bool = False) -> int | None:
    value = payload.get(key)
    if value in (None, ""):
        if required:
            raise ValueError(f"{key} is required.")
        return None
    assert value is not None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{key} must be a whole number.") from error


def clean_optional_payload_text(payload: dict[str, Any], key: str, limit: int = 160) -> str | None:
    if key not in payload:
        return None
    value = clean_text(payload.get(key))
    if len(value) > limit:
        raise ValueError(f"{key} must be at most {limit} characters.")
    return value or None


def label_audit(
    conn: Any,
    admin_user_id: int,
    label_type: str,
    match_id: str,
    before: Any,
    after: Any,
    *,
    source: str = "manual",
    reason: str | None = None,
) -> None:
    before_payload = {"value": json_ready(before), "source": source}
    after_payload = {"value": json_ready(after), "source": source}
    if reason:
        after_payload["reason"] = reason
    execute(
        conn,
        """
        INSERT INTO label_audit_log (
            admin_user_id, label_type, match_id, before_json, after_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            admin_user_id,
            label_type,
            match_id,
            json.dumps(before_payload, sort_keys=True),
            json.dumps(after_payload, sort_keys=True),
        ),
    )


def quiz_label_for_admin(
    match: dict[str, Any],
    override: Any | None,
    auto_label: Any | None = None,
) -> dict[str, Any] | None:
    quiz = match.get("quiz")
    if not isinstance(quiz, dict) and override is None:
        return None
    if not isinstance(quiz, dict):
        quiz = {}
    correct_answers = quiz.get("correct_answers")
    if correct_answers is None and quiz.get("correct_answer") is not None:
        correct_answers = [quiz.get("correct_answer")]
    auto_answers = parse_correct_answers_json(
        auto_label["correct_answers_json"] if auto_label is not None else None
    )
    label = {
        "question": quiz.get("question"),
        "type": quiz.get("type"),
        "choices": quiz.get("choices") or [],
        "choice_points": quiz.get("choice_points") or {},
        "dynamic_choice_points": quiz.get("dynamic_choice_points"),
        "viewership_required": bool(quiz.get("viewership")),
        "correct_answer": quiz.get("correct_answer"),
        "correct_answers": correct_answers or [],
        "viewership_answer": quiz.get("viewership_answer"),
        "source": "static",
        "updated_at": None,
        "updated_by_user_id": None,
        "genai": None,
        "manual_override_active": False,
    }
    if auto_label is not None and auto_answers:
        label.update(
            {
                "correct_answer": auto_answers[0],
                "correct_answers": auto_answers,
                "source": auto_label["source"] or "genai",
                "updated_at": auto_label["updated_at"],
                "genai": genai_service.quiz_genai_payload_from_row(auto_label),
            }
        )
    if override is not None:
        override_answers = parse_correct_answers_json(override["correct_answers_json"])
        override_question = clean_text(
            override["question"] if row_has_key(override, "question") else None
        )
        override_choices = parse_text_list_json(
            override["choices_json"] if row_has_key(override, "choices_json") else None
        )
        label.update(
            {
                "question": override_question or quiz.get("question"),
                "choices": override_choices or quiz.get("choices") or [],
                "correct_answer": override_answers[0] if override_answers else None,
                "correct_answers": override_answers,
                "viewership_answer": override["viewership_answer"],
                "source": override["source"] or "manual",
                "updated_at": override["updated_at"],
                "updated_by_user_id": override["updated_by_user_id"],
                "manual_override_active": True,
            }
        )
    return label


def admin_labels_payload(data: dict[str, Any]) -> dict[str, Any]:
    with get_db() as conn:
        result_rows = execute(
            conn,
            """
            SELECT match_id, source, source_fixture_id, status_long, status_short,
                   elapsed, home_score, away_score, synced_at
            FROM match_results
            """,
        ).fetchall()
        event_rows = execute(
            conn,
            """
            SELECT match_id, provider_event_key, source_fixture_id, elapsed, extra,
                   local_team_id, api_team_id, team_name, api_player_id, player_name,
                   api_assist_id, assist_name, event_type, detail, comments, updated_at
            FROM match_events
            ORDER BY match_id, COALESCE(elapsed, 999), COALESCE(extra, 0), provider_event_key
            """,
        ).fetchall()
        stat_rows = execute(
            conn,
            """
            SELECT match_id, provider_player_key, source_fixture_id, local_team_id,
                   api_team_id, team_name, api_player_id, player_name, minutes,
                   position, rating, goals, assists, yellow_cards, red_cards,
                   clean_sheet, updated_at
            FROM player_match_stats
            ORDER BY match_id, team_name, position, player_name
            """,
        ).fetchall()
        player_link_rows = execute(
            conn,
            """
            SELECT pcl.target_type, pcl.target_id, pcl.raw_player_name,
                   pcl.matched_local_team_id, pcl.matched_api_player_id,
                   pcl.matched_player_name, pcl.source, pcl.job_result_id,
                   pcl.confidence, pcl.evidence_json, gjr.status AS job_status,
                   gjr.provider_key, gjr.model
            FROM player_candidate_links pcl
            LEFT JOIN genai_job_results gjr ON gjr.id = pcl.job_result_id
            """,
        ).fetchall()
        genai_status_rows = execute(
            conn,
            """
            SELECT status, COUNT(*) AS count
            FROM genai_job_results
            GROUP BY status
            """,
        ).fetchall()
        quiz_rows = execute(
            conn,
            """
            SELECT match_id, question, choices_json, correct_answers_json,
                   viewership_answer, source, updated_by_user_id, updated_at
            FROM quiz_label_overrides
            """,
        ).fetchall()
        quiz_auto_rows = execute(
            conn,
            """
            SELECT qal.match_id, qal.source, qal.job_result_id,
                   qal.correct_answers_json, qal.confidence, qal.evidence_json,
                   qal.resolved_at, qal.updated_at, gjr.status AS job_status,
                   gjr.provider_key, gjr.model
            FROM quiz_auto_labels qal
            LEFT JOIN genai_job_results gjr ON gjr.id = qal.job_result_id
            """,
        ).fetchall()
        audit_rows = execute(
            conn,
            """
            SELECT label_type, match_id, admin_user_id, created_at
            FROM label_audit_log
            ORDER BY created_at DESC, id DESC
            LIMIT 50
            """,
        ).fetchall()

    results = {row["match_id"]: row for row in result_rows}
    quizzes = {row["match_id"]: row for row in quiz_rows}
    auto_quizzes = {row["match_id"]: row for row in quiz_auto_rows}
    player_links = {(row["target_type"], row["target_id"]): row for row in player_link_rows}
    events_by_match: dict[str, list[dict[str, Any]]] = {}
    for row in event_rows:
        event = dict(row)
        event["source"] = admin_label_source_from_key(row["provider_event_key"])
        event["event_id"] = row["provider_event_key"]
        target_id = genai_service.notification_target_id(row["match_id"], row["player_name"])
        event["genai_link"] = genai_service.player_genai_link_payload(
            player_links.get((genai_service.GENAI_TARGET_MATCH_SCORER, target_id))
        )
        events_by_match.setdefault(row["match_id"], []).append(event)
    stats_by_match: dict[str, list[dict[str, Any]]] = {}
    for row in stat_rows:
        stat = dict(row)
        stat["source"] = admin_label_source_from_key(row["provider_player_key"])
        stat["stat_id"] = row["provider_player_key"]
        target_id = genai_service.notification_target_id(row["match_id"], row["player_name"])
        stat["genai_link"] = genai_service.player_genai_link_payload(
            player_links.get((genai_service.GENAI_TARGET_MATCH_SCORER, target_id))
        )
        stats_by_match.setdefault(row["match_id"], []).append(stat)

    matches = []
    for match in data.get("matches", []):
        result = results.get(match["id"])
        quiz_label = quiz_label_for_admin(
            match,
            quizzes.get(match["id"]),
            auto_quizzes.get(match["id"]),
        )
        quiz_review_reasons = []
        if quiz_label is not None and (result is not None or match_result(match) is not None):
            if not quiz_label.get("correct_answers"):
                quiz_review_reasons.append("Quiz label missing")
            if (
                quiz_label.get("viewership_required")
                and quiz_label.get("viewership_answer") is None
            ):
                quiz_review_reasons.append("Viewership missing")
        matches.append(
            {
                "match_id": match["id"],
                "round": match.get("round"),
                "group": match.get("group"),
                "date": match.get("date"),
                "home_team_id": match.get("home_team_id"),
                "away_team_id": match.get("away_team_id"),
                "home_placeholder": match.get("home_placeholder"),
                "away_placeholder": match.get("away_placeholder"),
                "home_team_name": match.get("home_team"),
                "away_team_name": match.get("away_team"),
                "result": dict(result) if result else None,
                "quiz": quiz_label,
                "quiz_review_needed": bool(quiz_review_reasons),
                "quiz_review_reasons": quiz_review_reasons,
                "events": events_by_match.get(match["id"], []),
                "player_stats": stats_by_match.get(match["id"], []),
            }
        )

    config = genai_service.genai_config()
    return {
        "matches": matches,
        "audit": [json_ready(row) for row in audit_rows],
        "genai": {
            "provider_key": config["provider_key"],
            "model": config["model"],
            "enabled": config["enabled"],
            "disabled_reason": config["disabled_reason"],
            "job_counts": {row["status"]: int(row["count"]) for row in genai_status_rows},
        },
        "tables": {
            "match_results": True,
            "match_events": True,
            "player_match_stats": True,
            "quiz_label_overrides": True,
            "label_audit_log": True,
        },
    }


genai_service.configure(
    team_profiles_path=TEAM_PROFILES_PATH,
    using_postgres=USING_POSTGRES,
    get_db=get_db,
    label_audit=label_audit,
    recompute_all_computed_points=recompute_all_computed_points,
)


@app.get("/api/health")
def health():
    if CONFIG_ERROR:
        return jsonify({"ok": False, "database": database_label(), "error": CONFIG_ERROR}), 503
    try:
        with get_db() as conn:
            execute(conn, "SELECT 1").fetchone()
    except Exception:
        logger.exception("Database health check failed")
        return (
            jsonify(
                {
                    "ok": False,
                    "database": database_label(),
                    "error": "Database connection failed.",
                }
            ),
            503,
        )
    return jsonify(
        {
            "ok": True,
            "database": database_label(),
            "schema_version": DB_SCHEMA_VERSION,
            "static_data": static_data_manifest(),
        }
    )


@app.get("/api/world-cup")
def world_cup():
    return jsonify(load_world_cup_data())


@app.get("/api/me")
def me():
    return jsonify({"user": current_user()})


@app.post("/api/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = normalize_email(payload.get("email", ""))
    raw_password = payload.get("password", "")
    if "@" not in email or "." not in email:
        return jsonify({"error": "Use a valid Talpa email address."}), 400

    with get_db() as conn:
        row = execute(
            conn,
            """
            SELECT id, name, email, profile_image_url, password_hash,
                   prize_pot_status, is_admin, archived_at, must_change_password
            FROM users
            WHERE LOWER(TRIM(email)) = ?
            ORDER BY id
            """,
            (email,),
        ).fetchone()
        if row is None:
            try:
                email = validate_talpa_account_email(email)
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
            try:
                password = validate_password(raw_password)
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
            user_count = execute(
                conn,
                "SELECT COUNT(*) AS count FROM users WHERE archived_at IS NULL",
            ).fetchone()["count"]
            is_admin = int(user_count == 0 or email.casefold() in ADMIN_EMAILS)
            name = clean_text(payload.get("name")) or default_name_from_email(email)
            execute(
                conn,
                """
                INSERT INTO users (name, email, password_hash, is_admin)
                VALUES (?, ?, ?, ?)
                """,
                (name, email, generate_password_hash(password), is_admin),
            )
            row = execute(
                conn,
                """
                SELECT id, name, email, profile_image_url, password_hash,
                       prize_pot_status, is_admin, archived_at
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()
        elif row["archived_at"] is not None:
            return jsonify({"error": "This account has been archived."}), 403
        elif not raw_password or not check_password_hash(row["password_hash"], str(raw_password)):
            return jsonify({"error": "Incorrect password."}), 401
        elif is_admin_email(email) and not bool(row["is_admin"]):
            execute(
                conn,
                "UPDATE users SET is_admin = 1 WHERE id = ?",
                (row["id"],),
            )
            row = execute(
                conn,
                """
                SELECT id, name, email, profile_image_url, password_hash,
                       prize_pot_status, is_admin, archived_at
                FROM users
                WHERE id = ?
                """,
                (row["id"],),
            ).fetchone()
        elif row["email"] != email:
            execute(
                conn,
                "UPDATE users SET email = ? WHERE id = ?",
                (email, row["id"]),
            )
            row = execute(
                conn,
                """
                SELECT id, name, email, profile_image_url, password_hash,
                       prize_pot_status, is_admin, archived_at
                FROM users
                WHERE id = ?
                """,
                (row["id"],),
            ).fetchone()

    user = row_to_user(row)
    if user is None:
        logger.error("Failed to load user after login for email %s", email)
        return jsonify({"error": "Could not complete login."}), 500
    session["user_id"] = user["id"]
    logger.info("User %s logged in", user["id"])
    return jsonify({"user": user})


@app.post("/api/auth/forgot-password")
def forgot_password():
    # Self-service resets are deliberately disabled: there is no email channel to
    # verify ownership, so anyone could otherwise hijack an account by email alone.
    # Password resets are handled by an admin, who issues a one-time password.
    return jsonify(
        {
            "ok": True,
            "message": (
                "Password resets are handled by a pool admin. Ask an admin to reset "
                "your password and they will give you a temporary one to log in with."
            ),
        }
    )


@app.post("/api/prize-pot/participation")
def save_prize_pot_participation():
    user, error_response = require_current_user("Log in before choosing prize pot participation.")
    if error_response:
        return error_response
    assert user is not None

    payload = request.get_json(silent=True) or {}
    status = normalize_prize_pot_status(payload.get("status"))
    if status == PRIZE_POT_UNDECIDED:
        return jsonify({"error": "Choose joined or declined."}), 400
    current_status = normalize_prize_pot_status(user.get("prize_pot_status"))
    if current_status == PRIZE_POT_JOINED and status == PRIZE_POT_DECLINED:
        return jsonify({"error": "You cannot opt out after joining the prize pot."}), 400

    with get_db() as conn:
        execute(
            conn,
            """
            UPDATE users
            SET prize_pot_status = ?
            WHERE id = ?
            """,
            (status, user["id"]),
        )
        participant_count = prize_pot_joined_count(conn)

    user["prize_pot_status"] = status
    user["prize_pot"] = prize_pot_payload_for_user(status, participant_count)
    return jsonify({"ok": True, "prize_pot": user["prize_pot"], "user": user})


@app.patch("/api/me/password")
def change_password():
    user, error_response = require_current_user("Log in before changing your password.")
    if error_response:
        return error_response
    assert user is not None

    payload = request.get_json(silent=True) or {}
    current_password = str(payload.get("current_password", ""))
    new_password = payload.get("password", "")
    confirm_password = payload.get("confirm_password", "")
    if str(new_password) != str(confirm_password):
        return jsonify({"error": "Passwords do not match."}), 400
    try:
        validated_password = validate_password(new_password)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    with get_db() as conn:
        row = execute(
            conn,
            "SELECT id, password_hash FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()
        if row is None:
            return jsonify({"error": "Account not found."}), 404
        if not check_password_hash(row["password_hash"], current_password):
            return jsonify({"error": "Current password is incorrect."}), 401
        execute(
            conn,
            "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
            (generate_password_hash(validated_password), user["id"]),
        )

    logger.info("User %s changed password", user["id"])
    return jsonify({"ok": True})


@app.patch("/api/me")
def update_me():
    user, error_response = require_current_user("Log in before changing your profile.")
    if error_response:
        return error_response
    assert user is not None

    payload = request.get_json(silent=True) or {}
    has_name = "name" in payload
    has_profile_image = "profile_image_url" in payload
    if not has_name and not has_profile_image:
        return jsonify({"error": "No profile changes submitted."}), 400

    name = clean_text(payload.get("name", user["name"]))
    if has_name:
        if len(normalize_identity(name)) < 2:
            return jsonify({"error": "Profile name must be at least 2 characters."}), 400
        if len(name) > 60:
            return jsonify({"error": "Profile name must be at most 60 characters."}), 400

    try:
        profile_image_url = (
            validate_profile_image_url(payload.get("profile_image_url"))
            if has_profile_image
            else row_value(user, "profile_picture", {}).get("image_url")
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    with get_db() as conn:
        if has_name and has_profile_image:
            execute(
                conn,
                "UPDATE users SET name = ?, profile_image_url = ? WHERE id = ?",
                (name, profile_image_url, user["id"]),
            )
        elif has_name:
            execute(conn, "UPDATE users SET name = ? WHERE id = ?", (name, user["id"]))
        else:
            execute(
                conn,
                "UPDATE users SET profile_image_url = ? WHERE id = ?",
                (profile_image_url, user["id"]),
            )
        row = execute(
            conn,
            """
            SELECT id, name, email, profile_image_url, prize_pot_status, is_admin, archived_at
            FROM users
            WHERE id = ? AND archived_at IS NULL
            """,
            (user["id"],),
        ).fetchone()

    updated_user = row_to_user(row)
    if updated_user is None:
        return jsonify({"error": "Could not update your username."}), 500
    logger.info("User %s updated profile", updated_user["id"])
    data = load_world_cup_data()
    return jsonify(user_pool_state(updated_user, data))


@app.post("/api/auth/logout")
def logout():
    user_id = session.get("user_id")
    session.clear()
    if user_id:
        logger.info("User %s logged out", user_id)
    return jsonify({"ok": True})


@app.get("/api/pool")
def pool():
    data = load_world_cup_data()
    return jsonify(user_pool_state(current_user(), data))


@app.get("/api/matchday/matches/<match_id>")
def matchday_match(match_id: str):
    user, error_response = require_current_user()
    if error_response:
        return error_response
    assert user is not None
    data = load_world_cup_data()
    detail, error = matchday_match_detail(data, match_id, user_id=user["id"])
    if error == "not_found":
        return jsonify({"error": "Match not found."}), 404
    if error == "not_locked":
        return jsonify({"error": "Predictions are not locked for this match yet."}), 403
    assert detail is not None
    return jsonify(detail)


@app.get("/api/admin/users")
def admin_users():
    _admin, error_response = require_admin_user()
    if error_response:
        return error_response
    with get_db() as conn:
        rows = execute(
            conn,
            """
            SELECT id, name, email, profile_image_url, prize_pot_status,
                   is_admin, archived_at, created_at
            FROM users
            ORDER BY archived_at IS NOT NULL, name
            """,
        ).fetchall()
    return jsonify({"users": [json_ready(row) for row in rows]})


@app.patch("/api/admin/users/<int:user_id>")
def admin_update_user(user_id: int):
    admin, error_response = require_admin_user()
    if error_response:
        return error_response
    assert admin is not None
    payload = request.get_json(silent=True) or {}
    if "is_admin" not in payload:
        return jsonify({"error": "No admin changes submitted."}), 400

    is_admin = bool(payload.get("is_admin"))
    if user_id == admin["id"] and not is_admin:
        return jsonify({"error": "You cannot remove your own admin access."}), 400
    with get_db() as conn:
        target = execute(
            conn,
            "SELECT id, is_admin, archived_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if target is None:
            return jsonify({"error": "Account not found."}), 404
        if target["archived_at"] is not None:
            return jsonify({"error": "Restore the account before changing admin status."}), 400
        if not is_admin and bool(target["is_admin"]):
            active_admins = execute(
                conn,
                "SELECT COUNT(*) AS count FROM users WHERE is_admin = 1 AND archived_at IS NULL",
            ).fetchone()["count"]
            if active_admins <= 1:
                return jsonify({"error": "At least one active admin is required."}), 400
        execute(
            conn,
            "UPDATE users SET is_admin = ? WHERE id = ?",
            (int(is_admin), user_id),
        )
    logger.info("Admin %s set admin=%s for user %s", admin["id"], is_admin, user_id)
    return admin_users()


@app.post("/api/admin/users/<int:user_id>/archive")
def admin_archive_user(user_id: int):
    admin, error_response = require_admin_user()
    if error_response:
        return error_response
    assert admin is not None
    if user_id == admin["id"]:
        return jsonify({"error": "You cannot archive your own account."}), 400

    with get_db() as conn:
        target = execute(
            conn,
            "SELECT id, is_admin, archived_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if target is None:
            return jsonify({"error": "Account not found."}), 404
        if target["archived_at"] is not None:
            return admin_users()
        if bool(target["is_admin"]):
            active_admins = execute(
                conn,
                "SELECT COUNT(*) AS count FROM users WHERE is_admin = 1 AND archived_at IS NULL",
            ).fetchone()["count"]
            if active_admins <= 1:
                return jsonify({"error": "At least one active admin is required."}), 400
        execute(
            conn,
            "UPDATE users SET archived_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,),
        )
        execute(
            conn,
            "DELETE FROM user_follows WHERE follower_id = ? OR followed_id = ?",
            (user_id, user_id),
        )
    logger.info("Admin %s archived user %s", admin["id"], user_id)
    return admin_users()


@app.post("/api/admin/users/<int:user_id>/restore")
def admin_restore_user(user_id: int):
    admin, error_response = require_admin_user()
    if error_response:
        return error_response
    assert admin is not None
    with get_db() as conn:
        target = execute(conn, "SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if target is None:
            return jsonify({"error": "Account not found."}), 404
        execute(
            conn,
            "UPDATE users SET archived_at = NULL WHERE id = ?",
            (user_id,),
        )
    logger.info("Admin %s restored user %s", admin["id"], user_id)
    return admin_users()


@app.post("/api/admin/users/<int:user_id>/reset-password")
def admin_reset_user_password(user_id: int):
    admin, error_response = require_admin_user()
    if error_response:
        return error_response
    assert admin is not None

    temporary_password = generate_temporary_password()
    with get_db() as conn:
        target = execute(
            conn,
            "SELECT id, archived_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if target is None:
            return jsonify({"error": "Account not found."}), 404
        if target["archived_at"] is not None:
            return jsonify({"error": "Restore the account before resetting its password."}), 400
        execute(
            conn,
            "UPDATE users SET password_hash = ?, must_change_password = 1 WHERE id = ?",
            (generate_password_hash(temporary_password), user_id),
        )
        rows = execute(
            conn,
            """
            SELECT id, name, email, profile_image_url, prize_pot_status,
                   is_admin, archived_at, created_at
            FROM users
            ORDER BY archived_at IS NOT NULL, name
            """,
        ).fetchall()
    logger.info("Admin %s reset password for user %s", admin["id"], user_id)
    return jsonify(
        {
            "ok": True,
            "user_id": user_id,
            "temporary_password": temporary_password,
            "users": [json_ready(row) for row in rows],
        }
    )


@app.get("/api/admin/labels")
def admin_labels():
    _admin, error_response = require_admin_user()
    if error_response:
        return error_response
    return jsonify(admin_labels_payload(load_world_cup_data()))


@app.patch("/api/admin/labels/<match_id>/result")
def admin_update_result_label(match_id: str):
    admin, error_response = require_admin_user()
    if error_response:
        return error_response
    assert admin is not None
    data = load_world_cup_data()
    if match_by_id(data, match_id) is None:
        return jsonify({"error": "Match not found."}), 404
    payload = request.get_json(silent=True) or {}
    reason = clean_optional_payload_text(payload, "reason", 240)
    if payload.get("clear_override"):
        with get_db() as conn:
            before = execute(
                conn,
                "SELECT * FROM match_results WHERE match_id = ?",
                (match_id,),
            ).fetchone()
            restored = restore_provider_facts_from_latest_snapshot(
                conn, match_id=match_id, data=data, clear_result=True
            )
            after = execute(
                conn,
                "SELECT * FROM match_results WHERE match_id = ?",
                (match_id,),
            ).fetchone()
            label_audit(
                conn,
                admin["id"],
                "result_revert",
                match_id,
                before,
                after,
                source="reverted",
                reason=reason,
            )
        updated_data = load_world_cup_data()
        recompute_all_computed_points(updated_data)
        return jsonify(
            {
                **admin_labels_payload(updated_data),
                "restored_provider_snapshot": restored,
            }
        )
    try:
        home_score = int_payload_value(payload, "home_score", required=True)
        away_score = int_payload_value(payload, "away_score", required=True)
        elapsed = int_payload_value(payload, "elapsed")
        status_short = clean_optional_payload_text(payload, "status_short", 24) or "FT"
        status_long = clean_optional_payload_text(payload, "status_long", 80) or "Manual result"
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    assert home_score is not None and away_score is not None
    if home_score < 0 or away_score < 0 or home_score > 30 or away_score > 30:
        return jsonify({"error": "Scores must be between 0 and 30."}), 400

    with get_db() as conn:
        before = execute(
            conn,
            "SELECT * FROM match_results WHERE match_id = ?",
            (match_id,),
        ).fetchone()
        execute(
            conn,
            """
            INSERT INTO match_results (
                match_id, source, source_fixture_id, status_long, status_short,
                elapsed, home_score, away_score, synced_at
            )
            VALUES (?, 'manual', NULL, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(match_id)
            DO UPDATE SET source = 'manual',
                          source_fixture_id = NULL,
                          status_long = excluded.status_long,
                          status_short = excluded.status_short,
                          elapsed = excluded.elapsed,
                          home_score = excluded.home_score,
                          away_score = excluded.away_score,
                          synced_at = CURRENT_TIMESTAMP
            """,
            (match_id, status_long, status_short, elapsed, home_score, away_score),
        )
        after = execute(
            conn,
            "SELECT * FROM match_results WHERE match_id = ?",
            (match_id,),
        ).fetchone()
        label_audit(conn, admin["id"], "result", match_id, before, after, reason=reason)
    updated_data = load_world_cup_data()
    recompute_all_computed_points(updated_data)
    return jsonify(admin_labels_payload(updated_data))


@app.patch("/api/admin/labels/<match_id>/quiz")
def admin_update_quiz_label(match_id: str):
    admin, error_response = require_admin_user()
    if error_response:
        return error_response
    assert admin is not None
    data = load_world_cup_data()
    match = match_by_id(data, match_id)
    if match is None:
        return jsonify({"error": "Match not found."}), 404
    if not match.get("quiz") and not is_knockout_match(match):
        return jsonify({"error": "This match has no quiz label."}), 400
    payload = request.get_json(silent=True) or {}
    reason = clean_optional_payload_text(payload, "reason", 240)

    with get_db() as conn:
        before = execute(
            conn,
            "SELECT * FROM quiz_label_overrides WHERE match_id = ?",
            (match_id,),
        ).fetchone()
        if payload.get("clear_override"):
            execute(conn, "DELETE FROM quiz_label_overrides WHERE match_id = ?", (match_id,))
            after = None
        else:
            question = clean_optional_payload_text(payload, "question", 260)
            if not question and not match.get("quiz"):
                return jsonify({"error": "question is required for new quiz setup."}), 400
            raw_choices = payload.get("choices")
            if raw_choices is None:
                choices = []
            elif isinstance(raw_choices, str):
                choices = [raw_choices]
            elif isinstance(raw_choices, list):
                choices = raw_choices
            else:
                return jsonify({"error": "choices must be a list or text value."}), 400
            choices = [choice for choice in (clean_text(item) for item in choices) if choice]
            if len(choices) > 24:
                return jsonify({"error": "Use at most 24 answer options."}), 400
            if any(len(choice) > 160 for choice in choices):
                return jsonify({"error": "Answer options must be at most 160 characters."}), 400
            raw_answers = payload.get("correct_answers")
            if raw_answers is None and "correct_answer" in payload:
                raw_answers = [payload.get("correct_answer")]
            if isinstance(raw_answers, str):
                raw_answers = [raw_answers]
            if not isinstance(raw_answers, list):
                return jsonify({"error": "correct_answers must be a list or text value."}), 400
            correct_answers = [
                answer for answer in (clean_text(item) for item in raw_answers) if answer
            ]
            if choices:
                choice_set = {normalize_answer(choice) for choice in choices}
                unknown_answers = [
                    answer
                    for answer in correct_answers
                    if normalize_answer(answer) not in choice_set
                ]
                if unknown_answers:
                    return (
                        jsonify({"error": "Correct answers must match one of the answer options."}),
                        400,
                    )
            try:
                viewership_answer = int_payload_value(payload, "viewership_answer")
            except ValueError as error:
                return jsonify({"error": str(error)}), 400
            execute(
                conn,
                """
                INSERT INTO quiz_label_overrides (
                    match_id, question, choices_json, correct_answers_json,
                    viewership_answer, source,
                    updated_by_user_id, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'manual', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(match_id)
                DO UPDATE SET question = excluded.question,
                              choices_json = excluded.choices_json,
                              correct_answers_json = excluded.correct_answers_json,
                              viewership_answer = excluded.viewership_answer,
                              source = 'manual',
                              updated_by_user_id = excluded.updated_by_user_id,
                              updated_at = CURRENT_TIMESTAMP
                """,
                (
                    match_id,
                    question,
                    json.dumps(choices),
                    json.dumps(correct_answers),
                    viewership_answer,
                    admin["id"],
                ),
            )
            genai_service.resolve_genai_failure_notifications_for_target(
                conn,
                job_type=genai_service.GENAI_JOB_QUIZ_ANSWER,
                target_type=genai_service.GENAI_TARGET_MATCH_QUIZ,
                target_id=match_id,
            )
            after = execute(
                conn,
                "SELECT * FROM quiz_label_overrides WHERE match_id = ?",
                (match_id,),
            ).fetchone()
        audit_type = "quiz_revert" if payload.get("clear_override") else "quiz"
        audit_source = "reverted" if payload.get("clear_override") else "manual"
        label_audit(
            conn,
            admin["id"],
            audit_type,
            match_id,
            before,
            after,
            source=audit_source,
            reason=reason,
        )
    updated_data = load_world_cup_data()
    recompute_all_computed_points(updated_data)
    return jsonify(admin_labels_payload(updated_data))


@app.post("/api/admin/genai/quiz-reviews/<int:job_result_id>")
def admin_review_genai_quiz_answer(job_result_id: int):
    admin, error_response = require_admin_user()
    if error_response:
        return error_response
    assert admin is not None
    payload = request.get_json(silent=True) or {}
    data = load_world_cup_data()
    try:
        with get_db() as conn:
            review = genai_service.review_quiz_answer(
                conn,
                data,
                job_result_id=job_result_id,
                decision=clean_text(payload.get("decision")).lower(),
                correct_answer=payload.get("correct_answer"),
                reviewed_by_user_id=int(admin["id"]),
            )
    except genai_service.QuizReviewError as error:
        return jsonify({"error": str(error)}), error.status_code
    recompute_all_computed_points(load_world_cup_data())
    return jsonify({"ok": True, "review": review})


@app.put("/api/admin/labels/<match_id>/events")
def admin_update_event_labels(match_id: str):
    admin, error_response = require_admin_user()
    if error_response:
        return error_response
    assert admin is not None
    data = load_world_cup_data()
    if match_by_id(data, match_id) is None:
        return jsonify({"error": "Match not found."}), 404
    payload = request.get_json(silent=True) or {}
    reason = clean_optional_payload_text(payload, "reason", 240)
    if payload.get("clear_override"):
        with get_db() as conn:
            before = execute(
                conn,
                "SELECT * FROM match_events WHERE match_id = ?",
                (match_id,),
            ).fetchall()
            restored = restore_provider_facts_from_latest_snapshot(
                conn, match_id=match_id, data=data, clear_events=True
            )
            after = execute(
                conn,
                "SELECT * FROM match_events WHERE match_id = ?",
                (match_id,),
            ).fetchall()
            label_audit(
                conn,
                admin["id"],
                "events_revert",
                match_id,
                before,
                after,
                source="reverted",
                reason=reason,
            )
        updated_data = load_world_cup_data()
        recompute_all_computed_points(updated_data)
        return jsonify(
            {
                **admin_labels_payload(updated_data),
                "restored_provider_snapshot": restored,
            }
        )
    events = payload.get("events")
    if not isinstance(events, list):
        return jsonify({"error": "events must be a list."}), 400

    cleaned_events = []
    for index, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            return jsonify({"error": "Each event must be an object."}), 400
        player_name = clean_text(event.get("player_name"))
        event_type = clean_text(event.get("event_type") or "Goal")
        if not player_name:
            return jsonify({"error": "Each event needs a player_name."}), 400
        if len(player_name) > 160 or len(event_type) > 80:
            return jsonify({"error": "Event names are too long."}), 400
        cleaned_events.append(
            {
                "provider_event_key": f"manual:{match_id}:{index}",
                "elapsed": int_or_none(event.get("elapsed")),
                "extra": int_or_none(event.get("extra")),
                "local_team_id": clean_text(event.get("local_team_id")) or None,
                "team_name": clean_text(event.get("team_name")) or None,
                "player_name": player_name,
                "event_type": event_type,
                "detail": clean_text(event.get("detail")) or None,
                "comments": clean_text(event.get("comments")) or None,
            }
        )

    with get_db() as conn:
        before = execute(
            conn,
            "SELECT * FROM match_events WHERE match_id = ?",
            (match_id,),
        ).fetchall()
        execute(conn, "DELETE FROM match_events WHERE match_id = ?", (match_id,))
        for event in cleaned_events:
            execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, source_fixture_id, elapsed, extra,
                    local_team_id, api_team_id, team_name, api_player_id, player_name,
                    api_assist_id, assist_name, event_type, detail, comments, raw_json,
                    updated_at
                )
                VALUES (
                    ?, ?, NULL, ?, ?, ?, NULL, ?, NULL, ?, NULL, NULL, ?, ?, ?, ?,
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    match_id,
                    event["provider_event_key"],
                    event["elapsed"],
                    event["extra"],
                    event["local_team_id"],
                    event["team_name"],
                    event["player_name"],
                    event["event_type"],
                    event["detail"],
                    event["comments"],
                    json.dumps({"source": "manual", **event}, sort_keys=True),
                ),
            )
        after = execute(
            conn,
            "SELECT * FROM match_events WHERE match_id = ?",
            (match_id,),
        ).fetchall()
        label_audit(conn, admin["id"], "events", match_id, before, after, reason=reason)
    updated_data = load_world_cup_data()
    recompute_all_computed_points(updated_data)
    return jsonify(admin_labels_payload(updated_data))


@app.put("/api/admin/labels/<match_id>/player-stats")
def admin_update_player_stat_labels(match_id: str):
    admin, error_response = require_admin_user()
    if error_response:
        return error_response
    assert admin is not None
    data = load_world_cup_data()
    if match_by_id(data, match_id) is None:
        return jsonify({"error": "Match not found."}), 404
    payload = request.get_json(silent=True) or {}
    reason = clean_optional_payload_text(payload, "reason", 240)
    if payload.get("clear_override"):
        with get_db() as conn:
            before = execute(
                conn,
                "SELECT * FROM player_match_stats WHERE match_id = ?",
                (match_id,),
            ).fetchall()
            restored = restore_provider_facts_from_latest_snapshot(
                conn, match_id=match_id, data=data, clear_stats=True
            )
            after = execute(
                conn,
                "SELECT * FROM player_match_stats WHERE match_id = ?",
                (match_id,),
            ).fetchall()
            label_audit(
                conn,
                admin["id"],
                "player_stats_revert",
                match_id,
                before,
                after,
                source="reverted",
                reason=reason,
            )
        updated_data = load_world_cup_data()
        recompute_all_computed_points(updated_data)
        return jsonify(
            {
                **admin_labels_payload(updated_data),
                "restored_provider_snapshot": restored,
            }
        )
    stats = payload.get("player_stats")
    if not isinstance(stats, list):
        return jsonify({"error": "player_stats must be a list."}), 400

    cleaned_stats = []
    for index, stat in enumerate(stats, start=1):
        if not isinstance(stat, dict):
            return jsonify({"error": "Each player stat must be an object."}), 400
        player_name = clean_text(stat.get("player_name"))
        if not player_name:
            return jsonify({"error": "Each player stat needs a player_name."}), 400
        cleaned_stats.append(
            {
                "provider_player_key": f"manual:{match_id}:{index}",
                "local_team_id": clean_text(stat.get("local_team_id")) or None,
                "team_name": clean_text(stat.get("team_name")) or None,
                "player_name": player_name[:160],
                "minutes": int_or_none(stat.get("minutes")) or 0,
                "position": clean_text(stat.get("position")) or None,
                "rating": clean_text(stat.get("rating")) or None,
                "goals": int_or_none(stat.get("goals")) or 0,
                "assists": int_or_none(stat.get("assists")) or 0,
                "yellow_cards": int_or_none(stat.get("yellow_cards")) or 0,
                "red_cards": int_or_none(stat.get("red_cards")) or 0,
                "clean_sheet": bool_int(bool(stat.get("clean_sheet"))),
            }
        )

    with get_db() as conn:
        before = execute(
            conn,
            "SELECT * FROM player_match_stats WHERE match_id = ?",
            (match_id,),
        ).fetchall()
        execute(conn, "DELETE FROM player_match_stats WHERE match_id = ?", (match_id,))
        for stat in cleaned_stats:
            execute(
                conn,
                """
                INSERT INTO player_match_stats (
                    match_id, provider_player_key, source_fixture_id, local_team_id,
                    api_team_id, team_name, api_player_id, player_name, minutes,
                    position, rating, goals, assists, yellow_cards, red_cards,
                    clean_sheet, raw_json, updated_at
                )
                VALUES (
                    ?, ?, NULL, ?, NULL, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    match_id,
                    stat["provider_player_key"],
                    stat["local_team_id"],
                    stat["team_name"],
                    stat["player_name"],
                    stat["minutes"],
                    stat["position"],
                    stat["rating"],
                    stat["goals"],
                    stat["assists"],
                    stat["yellow_cards"],
                    stat["red_cards"],
                    stat["clean_sheet"],
                    json.dumps({"source": "manual", **stat}, sort_keys=True),
                ),
            )
        after = execute(
            conn,
            "SELECT * FROM player_match_stats WHERE match_id = ?",
            (match_id,),
        ).fetchall()
        label_audit(conn, admin["id"], "player_stats", match_id, before, after, reason=reason)
    updated_data = load_world_cup_data()
    recompute_all_computed_points(updated_data)
    return jsonify(admin_labels_payload(updated_data))


def admin_broadcast_payload(limit: int = 25) -> dict[str, Any]:
    with get_db() as conn:
        rows = execute(
            conn,
            """
            SELECT id, title, body, is_active, starts_at, expires_at,
                   deactivated_at, created_by_user_id, created_at
            FROM admin_broadcast_notifications
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return {"broadcasts": [json_ready(row) for row in rows]}


@app.get("/api/admin/notifications/broadcasts")
def admin_broadcasts():
    _admin, error_response = require_admin_user()
    if error_response:
        return error_response
    return jsonify(admin_broadcast_payload())


@app.post("/api/admin/notifications/broadcasts")
def admin_create_broadcast():
    admin, error_response = require_admin_user()
    if error_response:
        return error_response
    assert admin is not None
    payload = request.get_json(silent=True) or {}
    title = clean_text(payload.get("title"))
    body = clean_text(payload.get("body"))
    starts_at = clean_optional_payload_text(payload, "starts_at", 40)
    expires_at = clean_optional_payload_text(payload, "expires_at", 40)
    if not title or not body:
        return jsonify({"error": "Title and message are required."}), 400
    if len(title) > 120 or len(body) > 600:
        return jsonify({"error": "Message is too long."}), 400
    with get_db() as conn:
        execute(
            conn,
            """
            INSERT INTO admin_broadcast_notifications (
                title, body, is_active, starts_at, expires_at, created_by_user_id, created_at
            )
            VALUES (?, ?, 1, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (title, body, starts_at, expires_at, admin["id"]),
        )
    return jsonify(admin_broadcast_payload()), 201


@app.post("/api/admin/notifications/broadcasts/<int:broadcast_id>/deactivate")
def admin_deactivate_broadcast(broadcast_id: int):
    _admin, error_response = require_admin_user()
    if error_response:
        return error_response
    with get_db() as conn:
        execute(
            conn,
            """
            UPDATE admin_broadcast_notifications
            SET is_active = 0, deactivated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (broadcast_id,),
        )
    return jsonify(admin_broadcast_payload())


@app.post("/api/admin/notifications/sync-issues/<int:notification_id>/dismiss")
def admin_dismiss_sync_issue_notification(notification_id: int):
    _admin, error_response = require_admin_user()
    if error_response:
        return error_response
    with get_db() as conn:
        execute(
            conn,
            """
            UPDATE admin_sync_notifications
            SET is_active = 0,
                resolved_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND is_active = 1
            """,
            (notification_id,),
        )
    return jsonify({"ok": True, "notification_id": notification_id})


@app.get("/api/newsletters")
def newsletters_api():
    return jsonify(
        {
            "articles": newsletter_articles(),
            "max_articles": NEWSLETTER_MAX_ARTICLES,
        }
    )


@app.post("/api/admin/newsletters/refresh")
def newsletters_admin_refresh():
    token_error = require_sync_token()
    if token_error:
        return token_error
    result = run_newsletter_refresh()
    status_code = 200 if result.get("ok") else 503
    return jsonify(result), status_code


@app.get("/api/matches/<match_id>/result")
def match_result_api(match_id: str):
    user, error_response = require_current_user()
    if error_response:
        return error_response
    data = load_world_cup_data()
    details = match_result_details(match_id, data)
    if details is None:
        return jsonify({"error": "Match not found."}), 404
    return jsonify(details)


@app.get("/api/admin/api-football/status")
def api_football_admin_status():
    token_error = require_sync_token()
    if token_error:
        return token_error
    return jsonify(api_football_status())


@app.post("/api/admin/api-football/sync")
def api_football_admin_sync():
    token_error = require_sync_token()
    if token_error:
        return token_error
    payload = request.get_json(silent=True) or {}
    match_id = clean_text(payload.get("match_id"))
    raw_match_ids = payload.get("match_ids")
    match_ids = [
        clean_text(value)
        for value in (raw_match_ids if isinstance(raw_match_ids, list) else [])
        if clean_text(value)
    ]
    data = load_world_cup_data()
    try:
        if match_ids:
            results = [
                run_api_football_completed_sync(
                    data,
                    force=True,
                    dry_run=bool(payload.get("dry_run", False)),
                    limit=1,
                    match_id=item,
                )
                for item in match_ids
            ]
            result = {
                "ok": all(item.get("ok") for item in results),
                "results": results,
                "synced": [
                    synced_item for item in results for synced_item in item.get("synced", [])
                ],
                "attempts": [
                    attempt_item for item in results for attempt_item in item.get("attempts", [])
                ],
                "skipped": [
                    skipped_item for item in results for skipped_item in item.get("skipped", [])
                ],
                "requests_today": api_football_request_count_today(),
                "daily_limit": API_FOOTBALL_DAILY_LIMIT,
            }
        else:
            result = run_api_football_completed_sync(
                data,
                force=bool(payload.get("force", False)),
                dry_run=bool(payload.get("dry_run", False)),
                limit=int(payload.get("limit", API_FOOTBALL_MAX_BATCH_SIZE)),
                match_id=match_id or None,
            )
        if not bool(payload.get("dry_run", False)):
            result["genai_jobs"] = genai_service.run_genai_jobs_after_data_sync(
                load_world_cup_data(),
                result_sync=result,
            )
        if bool(payload.get("recompute_points", False)) and not bool(payload.get("dry_run", False)):
            recompute_all_computed_points(load_world_cup_data())
            result["computed_points_updated"] = True
    except Exception as error:
        logger.exception("API-Football manual sync failed")
        result = {
            "ok": False,
            "error": str(error),
            "requests_today": api_football_request_count_today(),
            "daily_limit": API_FOOTBALL_DAILY_LIMIT,
        }
    status_code = 200 if result.get("ok") else 503
    return jsonify(result), status_code


def run_missing_result_sync_batch(data: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    match_ids = missing_result_match_ids(data)
    results = [
        run_api_football_completed_sync(
            data,
            force=True,
            dry_run=dry_run,
            limit=1,
            match_id=match_id,
            recompute_points=False,
        )
        for match_id in match_ids
    ]
    return {
        "ok": all(item.get("ok") for item in results),
        "dry_run": dry_run,
        "match_ids": match_ids,
        "results": results,
        "synced": [synced_item for item in results for synced_item in item.get("synced", [])],
        "attempts": [attempt_item for item in results for attempt_item in item.get("attempts", [])],
        "skipped": [skipped_item for item in results for skipped_item in item.get("skipped", [])],
    }


@app.post("/api/admin/api-football/missing-results/sync")
def api_football_admin_missing_results_sync():
    _admin, error_response = require_admin_user()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    dry_run = bool(payload.get("dry_run", False))
    data = load_world_cup_data()
    match_ids: list[str] = []
    try:
        result = run_missing_result_sync_batch(data, dry_run=dry_run)
        match_ids = result["match_ids"]
        genai_jobs = None
        if not dry_run:
            updated_data = load_world_cup_data()
            genai_jobs = genai_service.run_genai_jobs_after_data_sync(
                updated_data, result_sync=result
            )
            recompute_all_computed_points(load_world_cup_data())
        result["computed_points_updated"] = not dry_run
        result["genai_jobs"] = genai_jobs
        result["requests_today"] = api_football_request_count_today()
        result["daily_limit"] = API_FOOTBALL_DAILY_LIMIT
    except Exception as error:
        logger.exception("API-Football missing-result sync failed")
        result = {
            "ok": False,
            "error": str(error),
            "match_ids": match_ids,
            "requests_today": api_football_request_count_today(),
            "daily_limit": API_FOOTBALL_DAILY_LIMIT,
        }
    status_code = 200 if result.get("ok") else 503
    return jsonify(result), status_code


@app.post("/api/admin/api-football/data-sync")
def api_football_admin_data_sync():
    _admin, error_response = require_admin_user()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    dry_run = bool(payload.get("dry_run", False))
    data = load_world_cup_data()
    try:
        result_sync = run_missing_result_sync_batch(data, dry_run=dry_run)
        genai_jobs = None
        if not dry_run:
            updated_data = load_world_cup_data()
            genai_jobs = genai_service.run_genai_jobs_after_data_sync(
                updated_data, result_sync=result_sync
            )
            recompute_all_computed_points(load_world_cup_data())
        result = {
            "ok": bool(result_sync.get("ok")),
            "dry_run": dry_run,
            "result_sync": result_sync,
            "genai_jobs": genai_jobs,
            "match_ids": result_sync.get("match_ids", []),
            "synced": result_sync.get("synced", []),
            "attempts": result_sync.get("attempts", []),
            "skipped": result_sync.get("skipped", []),
            "computed_points_updated": not dry_run,
            "requests_today": api_football_request_count_today(),
            "daily_limit": API_FOOTBALL_DAILY_LIMIT,
        }
    except Exception as error:
        logger.exception("API-Football admin data sync failed")
        result = {
            "ok": False,
            "error": str(error),
            "requests_today": api_football_request_count_today(),
            "daily_limit": API_FOOTBALL_DAILY_LIMIT,
        }
    status_code = 200 if result.get("ok") else 503
    return jsonify(result), status_code


@app.post("/api/admin/api-football/squads/sync")
def api_football_admin_squad_sync():
    token_error = require_sync_token()
    if token_error:
        return token_error
    payload = request.get_json(silent=True) or {}
    data = load_world_cup_data()
    try:
        result = run_api_football_squad_sync(
            data,
            force=bool(payload.get("force", False)),
            dry_run=bool(payload.get("dry_run", False)),
            limit=int(payload.get("limit", API_FOOTBALL_SQUAD_SYNC_BATCH_SIZE)),
            include_coaches=bool(payload.get("include_coaches", True)),
        )
    except Exception as error:
        logger.exception("API-Football squad sync failed")
        result = {
            "ok": False,
            "error": str(error),
            "requests_today": api_football_request_count_today(),
            "daily_limit": API_FOOTBALL_DAILY_LIMIT,
        }
    status_code = 200 if result.get("ok") else 503
    return jsonify(result), status_code


@app.get("/api/admin/database/status")
def database_admin_status():
    token_error = require_sync_token()
    if token_error:
        return token_error
    return jsonify(database_snapshot(include_rows=False))


@app.get("/api/admin/database/backup")
def database_admin_backup():
    token_error = require_sync_token()
    if token_error:
        return token_error
    snapshot = database_snapshot(include_rows=True)
    response = jsonify(snapshot)
    filename_time = utc_now().strftime("%Y%m%dT%H%M%SZ")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="wk-hub-backup-{filename_time}.json"'
    )
    return response


@app.post("/api/admin/database/recompute-points")
def database_admin_recompute_points():
    token_error = require_sync_token()
    if token_error:
        return token_error
    try:
        player_verification = recompute_all_computed_points(load_world_cup_data())
        with get_db() as conn:
            row = execute(
                conn,
                """
                SELECT COUNT(*) AS count
                FROM computed_points
                WHERE scope_type = 'leaderboard'
                  AND scope_id = 'current'
                """,
            ).fetchone()
        return jsonify(
            {
                "ok": True,
                "computed_points_updated": True,
                "leaderboard_computed_point_rows": int(row["count"] if row else 0),
                "player_database_verification": player_verification,
            }
        )
    except Exception as error:
        logger.exception("Database point recompute failed")
        return jsonify({"ok": False, "error": str(error)}), 503


@app.get("/api/cron/api-football-sync")
def api_football_cron_sync():
    token_error = require_sync_token()
    if token_error:
        return token_error
    data = load_world_cup_data()
    try:
        result = run_api_football_completed_sync(data, daily_sweep=True)
    except Exception as error:
        logger.exception("API-Football cron sync failed")
        result = {
            "ok": False,
            "error": str(error),
            "requests_today": api_football_request_count_today(),
            "daily_limit": API_FOOTBALL_DAILY_LIMIT,
        }
    status_code = 200 if result.get("ok") else 503
    return jsonify(result), status_code


@app.get("/api/cron/api-football-squad-sync")
def api_football_squad_cron_sync():
    token_error = require_sync_token()
    if token_error:
        return token_error
    data = load_world_cup_data()
    try:
        result = run_api_football_squad_sync(
            data,
            force=True,
            limit=48,
            include_coaches=False,
        )
    except Exception as error:
        logger.exception("API-Football squad cron sync failed")
        result = {
            "ok": False,
            "error": str(error),
            "requests_today": api_football_request_count_today(),
            "daily_limit": API_FOOTBALL_DAILY_LIMIT,
        }
    status_code = 200 if result.get("ok") else 503
    return jsonify(result), status_code


@app.get("/api/social")
def social():
    user, error_response = require_current_user()
    if error_response:
        return error_response
    assert user is not None
    return jsonify(social_state(user))


@app.post("/api/social/follow")
def follow_user():
    user, error_response = require_current_user()
    if error_response:
        return error_response
    assert user is not None

    payload = request.get_json(silent=True) or {}
    raw_followed_id = payload.get("user_id")
    if raw_followed_id is None:
        return jsonify({"error": "Choose a player to follow."}), 400
    try:
        followed_id = int(raw_followed_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Choose a player to follow."}), 400
    if followed_id == user["id"]:
        return jsonify({"error": "You cannot follow yourself."}), 400

    with get_db() as conn:
        target = execute(
            conn,
            "SELECT id FROM users WHERE id = ? AND archived_at IS NULL",
            (followed_id,),
        ).fetchone()
        if target is None:
            return jsonify({"error": "That player is not in the pool."}), 404
        execute(
            conn,
            """
            INSERT INTO user_follows (follower_id, followed_id, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(follower_id, followed_id) DO NOTHING
            """,
            (user["id"], followed_id),
        )

    return jsonify(social_state(user))


@app.delete("/api/social/follow/<int:followed_id>")
def unfollow_user(followed_id: int):
    user, error_response = require_current_user()
    if error_response:
        return error_response
    assert user is not None

    with get_db() as conn:
        execute(
            conn,
            "DELETE FROM user_follows WHERE follower_id = ? AND followed_id = ?",
            (user["id"], followed_id),
        )

    return jsonify(social_state(user))


@app.get("/api/profiles/<int:profile_user_id>/predictions")
def profile_predictions(profile_user_id: int):
    user, error_response = require_current_user()
    if error_response:
        return error_response
    assert user is not None

    with get_db() as conn:
        profile = execute(
            conn,
            """
            SELECT id, name, prize_pot_status
            FROM users
            WHERE id = ? AND archived_at IS NULL
            """,
            (profile_user_id,),
        ).fetchone()
    if profile is None:
        return jsonify({"error": "Player profile not found."}), 404

    data = load_world_cup_data()
    now = utc_now()
    include_unplayed = profile_user_id == user["id"]
    leaderboard_row = next(
        (
            row
            for row in build_leaderboard(
                data,
                viewer_user_id=user["id"],
                viewer_is_admin=bool(user.get("is_admin")),
                now=now,
                use_computed_points=True,
            )
            if row["user_id"] == profile_user_id
        ),
        None,
    )
    show_prize_pot = bool(user.get("is_admin")) or profile_user_id == user["id"]
    prize_pot_status = normalize_prize_pot_status(profile["prize_pot_status"])
    return jsonify(
        {
            "user_id": profile_user_id,
            "name": profile["name"],
            "prize_pot_status": prize_pot_status if show_prize_pot else None,
            "prize_pot": prize_pot_payload(prize_pot_status) if show_prize_pot else None,
            "leaderboard_entry": leaderboard_row,
            "limited_to_completed_matches": False,
            "limited_to_locked_matches": not include_unplayed,
            "groups": user_prediction_groups(profile_user_id, data, include_unplayed, now),
        }
    )


@app.post("/api/predictions/<match_id>")
def save_single_match_prediction(match_id: str):
    user, error_response = require_current_user("Log in before saving predictions.")
    if error_response:
        logger.warning("Rejected single prediction save without authenticated session")
        return error_response
    assert user is not None

    data = load_world_cup_data()
    matches = {match["id"]: match for match in data["matches"]}
    match = matches.get(match_id)
    allowed_match_ids = {
        candidate["id"]
        for candidate in data["matches"]
        if candidate["round"] == "Group Stage"
        or (candidate.get("home_team_id") and candidate.get("away_team_id"))
    }
    if match is None or match_id not in allowed_match_ids:
        return jsonify({"error": f"Match {match_id} is not open for predictions."}), 400
    if is_prediction_locked(match, utc_now()):
        return jsonify({"error": f"Predictions for match {match_id} are closed."}), 400

    payload = request.get_json(silent=True) or {}
    try:
        raw_home_score = payload["home_score"]
        raw_away_score = payload["away_score"]
        home_score = int(raw_home_score)
        away_score = int(raw_away_score)
    except (TypeError, ValueError):
        return jsonify({"error": "Scores must be whole numbers."}), 400
    except KeyError:
        return jsonify({"error": "Scores must be whole numbers."}), 400
    if home_score < 0 or away_score < 0 or home_score > 30 or away_score > 30:
        return jsonify({"error": "Scores must be between 0 and 30."}), 400

    quiz_answer: str | None = None
    if match.get("quiz"):
        quiz_answer = clean_text(payload.get("quiz_answer", ""))
        if len(quiz_answer) > 160:
            return jsonify({"error": "Quiz answers can be at most 160 characters."}), 400
        choices = {normalize_answer(choice) for choice in match["quiz"].get("choices", [])}
        if quiz_answer and choices and normalize_answer(quiz_answer) not in choices:
            return jsonify({"error": f"Choose a valid quiz answer for match {match_id}."}), 400

    leeuwtje_submitted = "leeuwtje" in payload
    leeuwtje_active = bool(payload.get("leeuwtje"))
    with get_db() as conn:
        existing_leeuwtjes = {
            row["match_id"]
            for row in execute(
                conn,
                "SELECT match_id FROM leeuwtje_predictions WHERE user_id = ?",
                (user["id"],),
            ).fetchall()
        }
        next_leeuwtjes = set(existing_leeuwtjes)
        if leeuwtje_submitted:
            if leeuwtje_active:
                next_leeuwtjes.add(match_id)
            else:
                next_leeuwtjes.discard(match_id)
            if len(next_leeuwtjes) > LEEUWTJES_LIMIT:
                return jsonify({"error": f"You can use at most {LEEUWTJES_LIMIT} Leeuwtjes."}), 400

        audit_payload = {
            "match_id": match_id,
            "home_score": home_score,
            "away_score": away_score,
            "quiz_answer": quiz_answer,
            "leeuwtje": leeuwtje_active if leeuwtje_submitted else None,
        }
        execute(
            conn,
            """
            INSERT INTO prediction_audit_log (user_id, action, payload_json, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                user["id"],
                "save_single_match_prediction",
                json.dumps(audit_payload, ensure_ascii=False, sort_keys=True),
            ),
        )
        execute(
            conn,
            """
            INSERT INTO match_predictions (
                user_id, match_id, home_score, away_score, updated_at
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, match_id)
            DO UPDATE SET home_score = excluded.home_score,
                          away_score = excluded.away_score,
                          updated_at = CURRENT_TIMESTAMP
            """,
            (user["id"], match_id, home_score, away_score),
        )
        if match.get("quiz"):
            if quiz_answer:
                execute(
                    conn,
                    """
                    INSERT INTO quiz_predictions (
                        user_id, match_id, answer, viewership_prediction, updated_at
                    )
                    VALUES (?, ?, ?, NULL, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, match_id)
                    DO UPDATE SET answer = excluded.answer,
                                  viewership_prediction = NULL,
                                  updated_at = CURRENT_TIMESTAMP
                    """,
                    (user["id"], match_id, quiz_answer),
                )
            else:
                execute(
                    conn,
                    "DELETE FROM quiz_predictions WHERE user_id = ? AND match_id = ?",
                    (user["id"], match_id),
                )
        if leeuwtje_submitted:
            if leeuwtje_active:
                execute(
                    conn,
                    """
                    INSERT INTO leeuwtje_predictions (user_id, match_id, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, match_id)
                    DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                    """,
                    (user["id"], match_id),
                )
            else:
                execute(
                    conn,
                    "DELETE FROM leeuwtje_predictions WHERE user_id = ? AND match_id = ?",
                    (user["id"], match_id),
                )

    logger.info("Saved single match prediction %s for user %s", match_id, user["id"])
    return jsonify(
        {
            "ok": True,
            "match_id": match_id,
            "prediction": {"home_score": home_score, "away_score": away_score},
            "quiz_prediction": (
                {"answer": quiz_answer or "", "viewership_prediction": None}
                if match.get("quiz")
                else None
            ),
            "leeuwtjes_match_ids": sorted(next_leeuwtjes),
            "progress": {
                "leeuwtjes_used": len(next_leeuwtjes),
                "leeuwtjes_total": LEEUWTJES_LIMIT,
            },
        }
    )


@app.post("/api/predictions")
def save_predictions():
    user, error_response = require_current_user("Log in before saving predictions.")
    if error_response:
        logger.warning("Rejected prediction save without authenticated session")
        return error_response
    assert user is not None

    data = load_world_cup_data()
    matches = {match["id"]: match for match in data["matches"]}
    allowed_match_ids = {
        match["id"]
        for match in data["matches"]
        if match["round"] == "Group Stage"
        or (match.get("home_team_id") and match.get("away_team_id"))
    }
    team_ids = {team["id"] for team in data["teams"]}
    payload = request.get_json(silent=True) or {}
    prediction_items = payload.get("predictions", [])
    quiz_items = payload.get("quiz_predictions")
    leeuwtje_items = payload.get("leeuwtjes_match_ids")
    winner_team_id = payload.get("winner_team_id")
    top_scorer_submitted = "top_scorer_name" in payload or "top_scorer_names" in payload
    raw_top_scorer = payload.get("top_scorer_name")
    raw_legacy_top_scorers = payload.get("top_scorer_names")
    if raw_top_scorer is None and isinstance(raw_legacy_top_scorers, list):
        raw_top_scorer = raw_legacy_top_scorers[0] if raw_legacy_top_scorers else ""
    strikers_submitted = "striker_names" in payload or "top_scorer_names" in payload
    raw_strikers = payload.get("striker_names")
    if raw_strikers is None and isinstance(raw_legacy_top_scorers, list):
        raw_strikers = raw_legacy_top_scorers[:STRIKER_PICK_COUNT]
    now = utc_now()

    if not isinstance(prediction_items, list):
        return jsonify({"error": "Predictions must be a list."}), 400
    if quiz_items is not None and not isinstance(quiz_items, list):
        return jsonify({"error": "Quiz predictions must be a list."}), 400
    if leeuwtje_items is not None and not isinstance(leeuwtje_items, list):
        return jsonify({"error": "Leeuwtjes must be a list."}), 400
    if raw_legacy_top_scorers is not None and not isinstance(raw_legacy_top_scorers, list):
        return jsonify({"error": "Top scorer picks must be a list."}), 400
    if raw_strikers is not None and not isinstance(raw_strikers, list):
        return jsonify({"error": "Striker picks must be a list."}), 400

    with get_db() as conn:
        existing_predictions = {
            row["match_id"]: row
            for row in execute(
                conn,
                "SELECT match_id, home_score, away_score FROM match_predictions WHERE user_id = ?",
                (user["id"],),
            ).fetchall()
        }
        existing_winner = execute(
            conn,
            "SELECT team_id FROM winner_predictions WHERE user_id = ?",
            (user["id"],),
        ).fetchone()
        existing_top_scorer = execute(
            conn,
            """
            SELECT player_name, player_name_2, player_name_3,
                   striker_name_1, striker_name_2, striker_name_3,
                   striker_name_4, striker_name_5
            FROM top_scorer_predictions
            WHERE user_id = ?
            """,
            (user["id"],),
        ).fetchone()
        existing_quizzes = {
            row["match_id"]: row
            for row in execute(
                conn,
                """
                SELECT match_id, answer, viewership_prediction
                FROM quiz_predictions
                WHERE user_id = ?
                """,
                (user["id"],),
            ).fetchall()
        }
        existing_leeuwtjes = {
            row["match_id"]
            for row in execute(
                conn,
                "SELECT match_id FROM leeuwtje_predictions WHERE user_id = ?",
                (user["id"],),
            ).fetchall()
        }

    cleaned = []
    for item in prediction_items:
        match_id = str(item.get("match_id", ""))
        if match_id not in allowed_match_ids:
            return jsonify({"error": f"Match {match_id} is not open for predictions."}), 400
        try:
            home_score = int(item.get("home_score"))
            away_score = int(item.get("away_score"))
        except (TypeError, ValueError):
            return jsonify({"error": "Scores must be whole numbers."}), 400
        if home_score < 0 or away_score < 0 or home_score > 30 or away_score > 30:
            return jsonify({"error": "Scores must be between 0 and 30."}), 400
        if is_prediction_locked(matches[match_id], now):
            existing = existing_predictions.get(match_id)
            existing_matches_submission = (
                existing
                and existing["home_score"] == home_score
                and existing["away_score"] == away_score
            )
            if existing_matches_submission:
                continue
            return jsonify({"error": f"Predictions for match {match_id} are closed."}), 400
        cleaned.append((user["id"], match_id, home_score, away_score))

    cleaned_quizzes = []
    quiz_deletes = []
    if quiz_items is not None:
        for item in quiz_items:
            match_id = str(item.get("match_id", ""))
            match = matches.get(match_id)
            if match_id not in allowed_match_ids or match is None or not match.get("quiz"):
                return jsonify({"error": f"Quiz for match {match_id} is not available."}), 400
            quiz = match["quiz"]
            answer = clean_text(item.get("answer", ""))
            if len(answer) > 160:
                return jsonify({"error": "Quiz answers can be at most 160 characters."}), 400
            choices = {normalize_answer(choice) for choice in quiz.get("choices", [])}
            if answer and choices and normalize_answer(answer) not in choices:
                return jsonify({"error": f"Choose a valid quiz answer for match {match_id}."}), 400

            viewership_prediction = None
            existing = existing_quizzes.get(match_id)
            existing_answer = clean_text(existing["answer"] if existing else "")
            changed = answer != existing_answer
            if changed and is_prediction_locked(match, now):
                return jsonify({"error": f"Quiz for match {match_id} is closed."}), 400
            if answer or viewership_prediction is not None:
                cleaned_quizzes.append((user["id"], match_id, answer, viewership_prediction))
            elif existing:
                quiz_deletes.append((user["id"], match_id))

    submitted_leeuwtjes: set[str] | None = None
    if leeuwtje_items is not None:
        submitted_leeuwtjes = {str(match_id) for match_id in leeuwtje_items}
        if len(submitted_leeuwtjes) > LEEUWTJES_LIMIT:
            return jsonify({"error": f"You can use at most {LEEUWTJES_LIMIT} Leeuwtjes."}), 400
        invalid_leeuwtjes = submitted_leeuwtjes - allowed_match_ids
        if invalid_leeuwtjes:
            return jsonify({"error": "Leeuwtjes can only be used on prediction matches."}), 400
        changed_leeuwtjes = submitted_leeuwtjes ^ existing_leeuwtjes
        locked_leeuwtjes = [
            match_id
            for match_id in changed_leeuwtjes
            if is_prediction_locked(matches[match_id], now)
        ]
        if locked_leeuwtjes:
            return jsonify({"error": "Leeuwtjes for locked matches cannot be changed."}), 400

    if winner_team_id and winner_team_id not in team_ids:
        return jsonify({"error": "Winner pick must be one of the participating teams."}), 400
    winner_change_locked = (
        winner_team_id
        and are_tournament_picks_locked(data, now)
        and (not existing_winner or existing_winner["team_id"] != winner_team_id)
    )
    if winner_change_locked:
        return jsonify({"error": "The tournament winner pick is closed."}), 400
    top_scorer_name: str | None = None
    if top_scorer_submitted:
        top_scorer_name = clean_text(raw_top_scorer)
        if len(top_scorer_name) > 120:
            return jsonify({"error": "Top scorer name must be at most 120 characters."}), 400

    striker_names: list[str] | None = None
    if strikers_submitted:
        if raw_strikers and len(raw_strikers) > STRIKER_PICK_COUNT:
            return jsonify({"error": f"Choose at most {STRIKER_PICK_COUNT} strikers."}), 400
        striker_names = [clean_text(name) for name in (raw_strikers or [])]
        striker_names = [name for name in striker_names if name]
        if any(len(name) > 120 for name in striker_names):
            return jsonify({"error": "Striker names must be at most 120 characters."}), 400
        normalized_strikers = [normalized_player_name(name) for name in striker_names]
        if len(set(normalized_strikers)) != len(normalized_strikers):
            return jsonify({"error": "Choose five different strikers."}), 400

    existing_top_scorer_name = top_scorer_pick_name(existing_top_scorer)
    existing_striker_names = striker_pick_names(existing_top_scorer)
    top_scorer_changed = top_scorer_submitted and top_scorer_name != existing_top_scorer_name
    strikers_changed = strikers_submitted and striker_names != existing_striker_names
    if (top_scorer_changed or strikers_changed) and are_tournament_picks_locked(data, now):
        return jsonify({"error": "The top scorer and striker picks are closed."}), 400

    audit_payload = {
        "predictions": [
            {"match_id": match_id, "home_score": home_score, "away_score": away_score}
            for _, match_id, home_score, away_score in cleaned
        ],
        "quiz_predictions": [
            {
                "match_id": match_id,
                "answer": answer,
                "viewership_prediction": viewership_prediction,
            }
            for _, match_id, answer, viewership_prediction in cleaned_quizzes
        ],
        "quiz_deletes": [match_id for _, match_id in quiz_deletes],
        "leeuwtjes_match_ids": (
            sorted(submitted_leeuwtjes) if submitted_leeuwtjes is not None else None
        ),
        "winner_team_id": winner_team_id or None,
        "top_scorer_name": top_scorer_name if top_scorer_submitted else None,
        "striker_names": striker_names if strikers_submitted else None,
    }

    with get_db() as conn:
        execute(
            conn,
            """
            INSERT INTO prediction_audit_log (user_id, action, payload_json, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                user["id"],
                "save_predictions",
                json.dumps(audit_payload, ensure_ascii=False, sort_keys=True),
            ),
        )
        for prediction_row in cleaned:
            execute(
                conn,
                """
                INSERT INTO match_predictions (
                    user_id, match_id, home_score, away_score, updated_at
                )
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, match_id)
                DO UPDATE SET home_score = excluded.home_score,
                              away_score = excluded.away_score,
                              updated_at = CURRENT_TIMESTAMP
                """,
                prediction_row,
            )
        for quiz_row in cleaned_quizzes:
            execute(
                conn,
                """
                INSERT INTO quiz_predictions (
                    user_id, match_id, answer, viewership_prediction, updated_at
                )
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, match_id)
                DO UPDATE SET answer = excluded.answer,
                              viewership_prediction = excluded.viewership_prediction,
                              updated_at = CURRENT_TIMESTAMP
                """,
                quiz_row,
            )
        for quiz_delete in quiz_deletes:
            execute(
                conn,
                "DELETE FROM quiz_predictions WHERE user_id = ? AND match_id = ?",
                quiz_delete,
            )
        if submitted_leeuwtjes is not None:
            execute(conn, "DELETE FROM leeuwtje_predictions WHERE user_id = ?", (user["id"],))
            for match_id in sorted(submitted_leeuwtjes):
                execute(
                    conn,
                    """
                    INSERT INTO leeuwtje_predictions (user_id, match_id, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    """,
                    (user["id"], match_id),
                )
        if winner_team_id:
            execute(
                conn,
                """
                INSERT INTO winner_predictions (user_id, team_id, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id)
                DO UPDATE SET team_id = excluded.team_id,
                              updated_at = CURRENT_TIMESTAMP
                """,
                (user["id"], winner_team_id),
            )
        if top_scorer_submitted or strikers_submitted:
            stored_top_scorer_name = (
                top_scorer_name if top_scorer_submitted else existing_top_scorer_name
            )
            stored_striker_names = striker_names if strikers_submitted else existing_striker_names
            if stored_top_scorer_name:
                padded_strikers = [*(stored_striker_names or []), None, None, None, None, None]
                execute(
                    conn,
                    """
                    INSERT INTO top_scorer_predictions (
                        user_id, player_name, player_name_2, player_name_3,
                        striker_name_1, striker_name_2, striker_name_3,
                        striker_name_4, striker_name_5, updated_at
                    )
                    VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id)
                    DO UPDATE SET player_name = excluded.player_name,
                                  player_name_2 = NULL,
                                  player_name_3 = NULL,
                                  striker_name_1 = excluded.striker_name_1,
                                  striker_name_2 = excluded.striker_name_2,
                                  striker_name_3 = excluded.striker_name_3,
                                  striker_name_4 = excluded.striker_name_4,
                                  striker_name_5 = excluded.striker_name_5,
                                  updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        user["id"],
                        stored_top_scorer_name,
                        padded_strikers[0],
                        padded_strikers[1],
                        padded_strikers[2],
                        padded_strikers[3],
                        padded_strikers[4],
                    ),
                )
            else:
                execute(
                    conn,
                    "DELETE FROM top_scorer_predictions WHERE user_id = ?",
                    (user["id"],),
                )
        if top_scorer_submitted or strikers_submitted:
            genai_service.verify_player_database_matches(conn)

    logger.info(
        (
            "Saved %s match predictions, %s quiz answers, winner=%s, "
            "top_scorer=%s and strikers=%s for user %s"
        ),
        len(cleaned),
        len(cleaned_quizzes),
        bool(winner_team_id),
        bool(top_scorer_name),
        bool(striker_names),
        user["id"],
    )
    return jsonify(user_pool_state(user, data))


@app.get("/api/cron/newsletters-refresh")
def newsletters_cron_refresh():
    token_error = require_sync_token()
    if token_error:
        return token_error
    try:
        result = run_newsletter_refresh()
    except Exception as error:
        logger.exception("Newsletter cron refresh failed")
        result = {"ok": False, "error": str(error), "articles": []}
    status_code = 200 if result.get("ok") else 503
    return jsonify(result), status_code


@app.get("/")
def index():
    return send_from_directory(DIST_DIR, "index.html")


@app.get("/<path:path>")
def frontend(path: str):
    if path.startswith("api/"):
        abort(404)
    target = DIST_DIR / path
    if target.is_file():
        return send_from_directory(DIST_DIR, path)
    return send_from_directory(DIST_DIR, "index.html")


@app.errorhandler(404)
def fallback_to_frontend(error: Any):
    if request.method == "GET" and not request.path.startswith("/api/"):
        return send_from_directory(DIST_DIR, "index.html")
    return jsonify({"error": "Not found"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
