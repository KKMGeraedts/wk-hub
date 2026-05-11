from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from flask import Flask, abort, g, jsonify, request, send_from_directory, session

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "backend" / "worldcup-2026.json"
QUIZ_PATH = ROOT / "backend" / "quiz-2026.json"
DB_PATH = Path(os.environ.get("WK_HUB_SQLITE_PATH", ROOT / "backend" / "pool.db"))
DIST_DIR = ROOT / "frontend" / "dist"
DATABASE_URL = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
USING_POSTGRES = bool(DATABASE_URL)
IS_VERCEL = os.environ.get("VERCEL") == "1"
LOG_LEVEL_NAME = os.environ.get("WK_HUB_LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, logging.INFO)
if not isinstance(LOG_LEVEL, int):
    LOG_LEVEL = logging.INFO
PREDICTION_LOCK_BEFORE_KICKOFF = timedelta(hours=1)
NETHERLANDS_TEAM_ID = "ned"
AMSTERDAM_TZ = ZoneInfo("Europe/Amsterdam")
LEEUWTJES_LIMIT = 5
GROUP_POSITION_POINTS = 25
WINNER_POINTS = 250
QUIZ_YES_NO_POINTS = 15
QUIZ_OPEN_POINTS = 50
QUIZ_VIEWERSHIP_POINTS = 30
MATCH_SCORE_RULES = {
    "Group Stage": {"exact": 45, "outcome": 30},
    "Round of 32": {"exact": 90, "outcome": 60},
    "Round of 16": {"exact": 135, "outcome": 90},
    "Quarter-final": {"exact": 180, "outcome": 120},
    "Semi-final": {"exact": 225, "outcome": 150},
    "Third-place play-off": {"exact": 225, "outcome": 150},
    "Final": {"exact": 270, "outcome": 180},
}

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("wk_hub")

if IS_VERCEL and not DATABASE_URL:
    raise RuntimeError("Set POSTGRES_URL or DATABASE_URL for Talpa WK Pool on Vercel.")


def database_label() -> str:
    if USING_POSTGRES:
        return "postgres"
    return f"sqlite:{DB_PATH}"


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

    return data


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


def winner_lock_time(data: dict[str, Any]) -> datetime:
    group_matches = [match for match in data["matches"] if match["round"] == "Group Stage"]
    first_match = min(group_matches, key=match_kickoff)
    return match_lock_time(first_match)


def is_winner_locked(data: dict[str, Any], now: datetime | None = None) -> bool:
    return (now or utc_now()) >= winner_lock_time(data)


def iso_utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


app = Flask(__name__, static_folder=None)
app.secret_key = os.environ.get("WK_HUB_SECRET", "wk-hub-local-dev-secret")
logger.info("Starting Talpa WK Pool backend with %s", database_label())


@app.before_request
def track_request_start() -> None:
    g.request_start_time = time.perf_counter()


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


def get_db() -> Any:
    if USING_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row

        assert DATABASE_URL is not None
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    sqlite_schema = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
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
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            match_id TEXT,
            audience TEXT NOT NULL DEFAULT 'pool',
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
        CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at
        ON chat_messages(created_at, id)
        """,
    ]
    postgres_schema = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
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
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            user_id INTEGER NOT NULL,
            match_id TEXT,
            audience TEXT NOT NULL DEFAULT 'pool',
            message TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
        CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at
        ON chat_messages(created_at, id)
        """,
    ]

    with get_db() as conn:
        if USING_POSTGRES:
            for statement in postgres_schema:
                conn.execute(statement)
            chat_audience_column = conn.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'chat_messages'
                  AND column_name = 'audience'
                """
            ).fetchone()
            if chat_audience_column is None:
                conn.execute(
                    "ALTER TABLE chat_messages ADD COLUMN audience TEXT NOT NULL DEFAULT 'pool'"
                )
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
        else:
            conn.executescript(";\n".join(sqlite_schema))
            chat_columns = conn.execute("PRAGMA table_info(chat_messages)").fetchall()
            if not any(row["name"] == "audience" for row in chat_columns):
                conn.execute(
                    "ALTER TABLE chat_messages ADD COLUMN audience TEXT NOT NULL DEFAULT 'pool'"
                )
            quiz_columns = conn.execute("PRAGMA table_info(quiz_predictions)").fetchall()
            if not any(row["name"] == "viewership_prediction" for row in quiz_columns):
                conn.execute(
                    "ALTER TABLE quiz_predictions ADD COLUMN viewership_prediction INTEGER"
                )
    logger.info("Database schema ready")


def row_to_user(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return {"id": row["id"], "name": row["name"], "email": row["email"]}


def current_user() -> dict[str, Any] | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    with get_db() as conn:
        row = execute(conn, "SELECT id, name, email FROM users WHERE id = ?", (user_id,)).fetchone()
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


def normalize_answer(value: Any) -> str:
    return clean_text(value).casefold()


def local_match_date(match: dict[str, Any]) -> Any:
    return match_kickoff(match).astimezone(AMSTERDAM_TZ).date()


def score_rule_for_match(match: dict[str, Any]) -> dict[str, int]:
    return MATCH_SCORE_RULES.get(match["round"], MATCH_SCORE_RULES["Group Stage"])


def match_prediction_points(prediction: Any, match: dict[str, Any]) -> tuple[int, str | None]:
    result = match_result(match)
    if result is None:
        return 0, None
    rule = score_rule_for_match(match)
    exact_score = prediction["home_score"] == match.get("home_score") and prediction[
        "away_score"
    ] == match.get("away_score")
    if exact_score:
        return rule["exact"], "exact"
    if prediction_result(prediction) == result:
        return rule["outcome"], "outcome"
    return 0, None


def quiz_complete(quiz: dict[str, Any] | None, prediction: Any | None) -> bool:
    if not quiz:
        return True
    answer = clean_text(prediction["answer"] if prediction else "")
    if not answer:
        return False
    if quiz.get("viewership") and prediction:
        return prediction["viewership_prediction"] is not None
    return True


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
    return QUIZ_YES_NO_POINTS if quiz.get("type") == "yes_no" else QUIZ_OPEN_POINTS


def quiz_viewership_winners(
    data: dict[str, Any], quiz_predictions: list[Any]
) -> set[tuple[int, str]]:
    predictions_by_match: dict[str, list[Any]] = {}
    for prediction in quiz_predictions:
        if prediction["viewership_prediction"] is not None:
            predictions_by_match.setdefault(prediction["match_id"], []).append(prediction)

    winners = set()
    for match in data["matches"]:
        quiz = match.get("quiz")
        if not quiz or quiz.get("viewership_answer") is None:
            continue
        try:
            correct_value = int(quiz["viewership_answer"])
        except (TypeError, ValueError):
            continue
        match_predictions = predictions_by_match.get(match["id"], [])
        if not match_predictions:
            continue
        deltas = [
            (abs(int(row["viewership_prediction"]) - correct_value), row)
            for row in match_predictions
        ]
        closest_delta = min(delta for delta, _ in deltas)
        for delta, row in deltas:
            if delta == closest_delta:
                winners.add((row["user_id"], row["match_id"]))
    return winners


def quiz_points_for_prediction(
    match: dict[str, Any], prediction: Any | None, viewership_winners: set[tuple[int, str]]
) -> int:
    quiz = match.get("quiz")
    if not quiz:
        return 0
    points = quiz_answer_points(quiz, prediction)
    if prediction and (prediction["user_id"], prediction["match_id"]) in viewership_winners:
        points += QUIZ_VIEWERSHIP_POINTS
    return points


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


def group_position_score(
    user_predictions: dict[str, Any], data: dict[str, Any]
) -> tuple[int, int]:
    points = 0
    correct_positions = 0
    group_matches_by_id = {
        match["id"]: match for match in data["matches"] if match["round"] == "Group Stage"
    }
    for group in data["groups"]:
        matches = [
            match
            for match in group_matches_by_id.values()
            if match.get("group") == group["id"]
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


def badge_list(
    *,
    exact_scores: int,
    outcomes: int,
    all_predictions_complete: bool,
    leeuwtjes_used: int,
    quiz_answer_count: int,
    group_positions: int,
) -> list[dict[str, str]]:
    badges = []
    if exact_scores:
        badges.append({"label": "Precisie", "detail": "Minstens een exacte uitslag"})
    if outcomes >= 5:
        badges.append({"label": "Toto-talent", "detail": "Vijf uitslagen goed"})
    if all_predictions_complete:
        badges.append({"label": "Volle kaart", "detail": "Alle groepswedstrijden ingevuld"})
    if leeuwtjes_used >= LEEUWTJES_LIMIT:
        badges.append({"label": "Leeuwentemmer", "detail": "Alle Leeuwtjes ingezet"})
    if quiz_answer_count:
        badges.append({"label": "Quizstarter", "detail": "Quizvragen ingevuld"})
    if group_positions:
        badges.append({"label": "Groepskenner", "detail": "Groepsposities correct"})
    return badges[:5]


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


def social_state(user: dict[str, Any]) -> dict[str, Any]:
    with get_db() as conn:
        users = execute(
            conn,
            "SELECT id, name, email FROM users WHERE id != ? ORDER BY name",
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
                "profile_picture": {
                    "initials": initials(row["name"]),
                    "hue": avatar_hue(row["name"]),
                },
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


def user_prediction_groups(profile_user_id: int, data: dict[str, Any]) -> list[dict[str, Any]]:
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

    by_match = {row["match_id"]: row for row in rows}
    quiz_by_match = {row["match_id"]: row for row in quiz_rows}
    leeuwtjes = {row["match_id"] for row in leeuwtje_rows}
    groups = []
    for group in data["groups"]:
        group_predictions = []
        group_matches = sorted(
            [
                match
                for match in data["matches"]
                if match["round"] == "Group Stage" and match.get("group") == group["id"]
            ],
            key=match_kickoff,
        )
        for match in group_matches:
            prediction = by_match.get(match["id"])
            if prediction is None:
                continue
            quiz_prediction = quiz_by_match.get(match["id"])
            group_predictions.append(
                {
                    "match_id": match["id"],
                    "date": match["date"],
                    "time_utc": match["time_utc"],
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
                    "quiz_question": match.get("quiz", {}).get("question"),
                    "quiz_answer": quiz_prediction["answer"] if quiz_prediction else None,
                    "viewership_prediction": (
                        quiz_prediction["viewership_prediction"] if quiz_prediction else None
                    ),
                    "leeuwtje": match["id"] in leeuwtjes,
                }
            )
        if group_predictions:
            groups.append({"group": group["id"], "predictions": group_predictions})
    return groups


def build_leaderboard(data: dict[str, Any]) -> list[dict[str, Any]]:
    matches = {match["id"]: match for match in data["matches"]}
    teams = {team["id"]: team for team in data["teams"]}
    champion_id = data.get("meta", {}).get("world_cup_winner_id")
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
        users = execute(conn, "SELECT id, name, email FROM users ORDER BY name").fetchall()
        predictions = execute(conn, "SELECT * FROM match_predictions").fetchall()
        quiz_predictions = execute(conn, "SELECT * FROM quiz_predictions").fetchall()
        leeuwtjes = execute(conn, "SELECT user_id, match_id FROM leeuwtje_predictions").fetchall()
        winners = {
            row["user_id"]: row["team_id"]
            for row in execute(conn, "SELECT user_id, team_id FROM winner_predictions").fetchall()
        }

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

    leaderboard = []
    for user in users:
        points = 0
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
        user_prediction_ids = {prediction["match_id"] for prediction in user_predictions}
        group_stage_predictions = sum(
            1 for match_id in user_prediction_ids if match_id in group_stage_ids
        )
        required_group_predictions = sum(
            1 for match_id in user_prediction_ids if match_id in required_group_ids
        )
        required_group_complete = bool(required_group_ids) and required_group_predictions >= len(
            required_group_ids
        )
        if not required_group_complete:
            continue

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
            if score_kind == "exact":
                exact_scores += 1
                scoring_games += 1
            elif score_kind == "outcome":
                outcomes += 1
                scoring_games += 1

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
        if champion_id and winner_pick == champion_id:
            points += WINNER_POINTS
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

        leaderboard.append(
            {
                "user_id": user["id"],
                "name": user["name"],
                "profile_picture": {
                    "initials": initials(user["name"]),
                    "hue": avatar_hue(user["name"]),
                },
                "points": points,
                "exact_scores": exact_scores,
                "precision": exact_scores,
                "shooting": shooting,
                "defence": defence,
                "scoring_games": scoring_games,
                "outcomes": outcomes,
                "quiz_points": quiz_points,
                "quiz_answers": quiz_answer_count,
                "group_position_points": group_position_points,
                "group_positions_correct": correct_group_positions,
                "leeuwtjes_used": len(user_leeuwtjes),
                "leeuwtje_points": leeuwtje_points,
                "predictions_count": len(user_predictions),
                "group_stage_predictions": group_stage_predictions,
                "group_stage_total": len(group_stage_ids),
                "required_group_predictions": required_group_predictions,
                "required_group_total": len(required_group_ids),
                "all_predictions_complete": all_group_predictions_complete,
                "entry_complete": all_group_predictions_complete and winner_pick is not None,
                "missing_group_stage_predictions": max(
                    0, len(group_stage_ids) - group_stage_predictions
                ),
                "winner_pick": winner_pick,
                "winner_pick_name": teams.get(winner_pick, {}).get("name") if winner_pick else None,
                "badges": badge_list(
                    exact_scores=exact_scores,
                    outcomes=outcomes,
                    all_predictions_complete=all_group_predictions_complete,
                    leeuwtjes_used=len(user_leeuwtjes),
                    quiz_answer_count=quiz_answer_count,
                    group_positions=correct_group_positions,
                ),
            }
        )

    return sorted(leaderboard, key=lambda row: (-row["points"], row["name"].lower()))


def build_notifications(
    data: dict[str, Any],
    predictions: dict[str, dict[str, Any]],
    quiz_predictions: dict[str, Any],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    current = now or utc_now()
    today = current.astimezone(AMSTERDAM_TZ).date()
    visible_dates = {today, today + timedelta(days=1)}
    relevant_matches = [
        match
        for match in data["matches"]
        if local_match_date(match) in visible_dates
        and match.get("home_team_id")
        and match.get("away_team_id")
        and not is_prediction_locked(match, current)
    ]
    missing_predictions = [match for match in relevant_matches if match["id"] not in predictions]
    missing_quizzes = [
        match
        for match in relevant_matches
        if match.get("quiz") and not quiz_complete(match["quiz"], quiz_predictions.get(match["id"]))
    ]

    notifications = []
    if missing_predictions:
        notifications.append(
            {
                "type": "predictions",
                "count": len(missing_predictions),
                "match_ids": [match["id"] for match in missing_predictions],
                "title": "Wedstrijdvoorspellingen open",
                "body": (
                    f"{len(missing_predictions)} wedstrijd"
                    f"{'' if len(missing_predictions) == 1 else 'en'} "
                    f"{'moet' if len(missing_predictions) == 1 else 'moeten'} "
                    "nog ingevuld worden."
                ),
            }
        )
    if missing_quizzes:
        notifications.append(
            {
                "type": "quiz",
                "count": len(missing_quizzes),
                "match_ids": [match["id"] for match in missing_quizzes],
                "title": "Quizvragen open",
                "body": (
                    f"{len(missing_quizzes)} quizvraag"
                    f"{'' if len(missing_quizzes) == 1 else 'en'} "
                    f"{'moet' if len(missing_quizzes) == 1 else 'moeten'} "
                    "nog ingevuld worden."
                ),
            }
        )
    return notifications[:2]


def outcome_bucket(prediction: Any) -> str:
    result = prediction_result(prediction)
    if result > 0:
        return "home"
    if result < 0:
        return "away"
    return "draw"


def build_matchday_summary(data: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    current = now or utc_now()
    today = current.astimezone(AMSTERDAM_TZ).date()
    matches_with_dates = [(local_match_date(match), match) for match in data["matches"]]
    match_dates = sorted({match_date for match_date, _ in matches_with_dates})
    target_date = today if today in match_dates else None
    if target_date is None:
        target_date = next((match_date for match_date in match_dates if match_date > today), None)
    if target_date is None and match_dates:
        target_date = match_dates[-1]

    if target_date is None:
        return {"available": False, "matches": []}

    target_matches = [
        match
        for match_date, match in matches_with_dates
        if match_date == target_date and match.get("home_team_id") and match.get("away_team_id")
    ]
    target_ids = {match["id"] for match in target_matches}

    with get_db() as conn:
        predictions = execute(
            conn,
            "SELECT user_id, match_id, home_score, away_score FROM match_predictions",
        ).fetchall()
        quiz_predictions = execute(
            conn,
            "SELECT user_id, match_id FROM quiz_predictions WHERE COALESCE(answer, '') != ''",
        ).fetchall()
        leeuwtjes = execute(conn, "SELECT user_id, match_id FROM leeuwtje_predictions").fetchall()

    predictions_by_match: dict[str, list[Any]] = {}
    for prediction in predictions:
        if prediction["match_id"] in target_ids:
            predictions_by_match.setdefault(prediction["match_id"], []).append(prediction)
    quiz_counts = Counter(
        row["match_id"] for row in quiz_predictions if row["match_id"] in target_ids
    )
    leeuwtje_counts = Counter(row["match_id"] for row in leeuwtjes if row["match_id"] in target_ids)

    matches = []
    for match in sorted(target_matches, key=match_kickoff):
        match_predictions = predictions_by_match.get(match["id"], [])
        outcomes = Counter(outcome_bucket(prediction) for prediction in match_predictions)
        exact_scores = Counter(
            f"{prediction['home_score']}-{prediction['away_score']}"
            for prediction in match_predictions
        )
        matches.append(
            {
                "match_id": match["id"],
                "date": match["date"],
                "time_utc": match["time_utc"],
                "home_team_id": match["home_team_id"],
                "away_team_id": match["away_team_id"],
                "prediction_count": len(match_predictions),
                "home_win_count": outcomes["home"],
                "draw_count": outcomes["draw"],
                "away_win_count": outcomes["away"],
                "top_scores": [
                    {"score": score, "count": count}
                    for score, count in exact_scores.most_common(3)
                ],
                "quiz_answer_count": quiz_counts[match["id"]],
                "leeuwtjes_count": leeuwtje_counts[match["id"]],
            }
        )

    return {
        "available": True,
        "date": target_date.isoformat(),
        "is_today": target_date == today,
        "matches": matches,
    }


def build_daily_recap(data: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    current = now or utc_now()
    today = current.astimezone(AMSTERDAM_TZ).date()
    completed_matches = [
        match
        for match in data["matches"]
        if match_result(match) is not None and local_match_date(match) <= today
    ]
    if not completed_matches:
        return {
            "available": False,
            "title": "Daily recap",
            "body": "De recap verschijnt zodra er gespeelde wedstrijden met uitslagen zijn.",
            "moments": [],
        }

    target_date = max(local_match_date(match) for match in completed_matches)
    target_matches = [
        match for match in completed_matches if local_match_date(match) == target_date
    ]
    target_ids = {match["id"] for match in target_matches}
    teams = {team["id"]: team for team in data["teams"]}

    with get_db() as conn:
        predictions = execute(conn, "SELECT * FROM match_predictions").fetchall()
        users = execute(conn, "SELECT id, name FROM users").fetchall()
        leeuwtjes = execute(conn, "SELECT user_id, match_id FROM leeuwtje_predictions").fetchall()

    user_names = {user["id"]: user["name"] for user in users}
    leeuwtjes_by_user: dict[int, set[str]] = {}
    for row in leeuwtjes:
        leeuwtjes_by_user.setdefault(row["user_id"], set()).add(row["match_id"])

    daily_points: Counter[int] = Counter()
    matches = {match["id"]: match for match in data["matches"]}
    for prediction in predictions:
        if prediction["match_id"] not in target_ids:
            continue
        match = matches.get(prediction["match_id"])
        if not match:
            continue
        base_points, _ = match_prediction_points(prediction, match)
        if prediction["match_id"] in leeuwtjes_by_user.get(prediction["user_id"], set()):
            base_points *= 2
        daily_points[prediction["user_id"]] += base_points

    top_user_id, top_points = (None, 0)
    if daily_points:
        top_user_id, top_points = daily_points.most_common(1)[0]

    moments = []
    for match in sorted(target_matches, key=match_kickoff):
        moments.append(
            {
                "match_id": match["id"],
                "label": (
                    f"{teams.get(match['home_team_id'], {}).get('name', match['home_team_id'])} "
                    f"{match['home_score']}-{match['away_score']} "
                    f"{teams.get(match['away_team_id'], {}).get('name', match['away_team_id'])}"
                ),
            }
        )

    return {
        "available": True,
        "title": f"Recap {target_date.isoformat()}",
        "body": f"{len(target_matches)} gespeelde wedstrijden verwerkt.",
        "moments": moments,
        "top_player": (
            {"name": user_names.get(top_user_id), "points": top_points}
            if top_user_id is not None
            else None
        ),
    }


def user_pool_state(user: dict[str, Any] | None, data: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    prediction_rows = []
    quiz_prediction_rows = []
    leeuwtje_rows = []
    winner_pick = None
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

    return {
        "me": user,
        "predictions": predictions,
        "quiz_predictions": quiz_predictions,
        "leeuwtjes_match_ids": leeuwtje_match_ids,
        "winner_pick": winner_pick,
        "leaderboard": build_leaderboard(data),
        "notifications": build_notifications(data, predictions, quiz_predictions, now),
        "matchday": build_matchday_summary(data, now),
        "daily_recap": build_daily_recap(data, now),
        "progress": {
            "group_stage_predictions": group_stage_predictions,
            "group_stage_total": len(group_stage_ids),
            "group_stage_quiz_predictions": group_stage_quiz_predictions,
            "group_stage_quiz_total": group_stage_quiz_total,
            "required_group_id": required_group_id,
            "required_group_predictions": required_group_predictions,
            "required_group_total": len(required_group_ids),
            "winner_selected": winner_pick is not None,
            "knockout_open_count": len(knockout_open),
            "leeuwtjes_used": len(leeuwtje_match_ids),
            "leeuwtjes_total": LEEUWTJES_LIMIT,
        },
        "locks": {
            "matches": match_locks,
            "winner_locked": is_winner_locked(data, now),
            "winner_lock_at": iso_utc(winner_lock_time(data)),
        },
        "rules": {
            "match_scores": MATCH_SCORE_RULES,
            "group_position": GROUP_POSITION_POINTS,
            "world_cup_winner": WINNER_POINTS,
            "quiz_yes_no": QUIZ_YES_NO_POINTS,
            "quiz_open": QUIZ_OPEN_POINTS,
            "quiz_viewership": QUIZ_VIEWERSHIP_POINTS,
            "leeuwtjes_total": LEEUWTJES_LIMIT,
            "note": (
                "Predictions, quiz answers and Leeuwtjes can be adjusted until one hour "
                "before kickoff."
            ),
        },
    }


init_db()


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/world-cup")
def world_cup():
    return jsonify(load_world_cup_data())


@app.get("/api/me")
def me():
    return jsonify({"user": current_user()})


@app.post("/api/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    if len(name) < 2:
        return jsonify({"error": "Name must be at least 2 characters."}), 400
    if "@" not in email or "." not in email:
        return jsonify({"error": "Use a valid Talpa email address."}), 400

    with get_db() as conn:
        row = execute(
            conn, "SELECT id, name, email FROM users WHERE email = ?", (email,)
        ).fetchone()
        if row is None:
            execute(conn, "INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
            row = execute(
                conn, "SELECT id, name, email FROM users WHERE email = ?", (email,)
            ).fetchone()
        elif row["name"] != name:
            execute(conn, "UPDATE users SET name = ? WHERE id = ?", (name, row["id"]))
            row = execute(
                conn, "SELECT id, name, email FROM users WHERE id = ?", (row["id"],)
            ).fetchone()

    user = row_to_user(row)
    if user is None:
        logger.error("Failed to load user after login for email %s", email)
        return jsonify({"error": "Could not complete login."}), 500
    session["user_id"] = user["id"]
    logger.info("User %s logged in", user["id"])
    return jsonify({"user": user})


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
        return jsonify({"error": "Choose a person to follow."}), 400
    try:
        followed_id = int(raw_followed_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Choose a person to follow."}), 400
    if followed_id == user["id"]:
        return jsonify({"error": "You cannot follow yourself."}), 400

    with get_db() as conn:
        target = execute(conn, "SELECT id FROM users WHERE id = ?", (followed_id,)).fetchone()
        if target is None:
            return jsonify({"error": "That person is not in the pool."}), 404
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
            "SELECT id, name FROM users WHERE id = ?",
            (profile_user_id,),
        ).fetchone()
    if profile is None:
        return jsonify({"error": "Player profile not found."}), 404

    data = load_world_cup_data()
    return jsonify(
        {
            "user_id": profile_user_id,
            "name": profile["name"],
            "groups": user_prediction_groups(profile_user_id, data),
        }
    )


@app.get("/api/chat")
def chat_messages():
    user, error_response = require_current_user()
    if error_response:
        return error_response
    assert user is not None

    with get_db() as conn:
        rows = execute(
            conn,
            """
            SELECT chat_messages.id,
                   chat_messages.user_id,
                   chat_messages.match_id,
                   chat_messages.audience,
                   chat_messages.message,
                   chat_messages.created_at,
                   users.name
            FROM chat_messages
            JOIN users ON users.id = chat_messages.user_id
            WHERE chat_messages.audience = 'pool'
               OR chat_messages.user_id = ?
               OR (
                   chat_messages.audience = 'friends'
                   AND EXISTS (
                       SELECT 1
                       FROM user_follows outbound
                       JOIN user_follows inbound
                         ON inbound.follower_id = outbound.followed_id
                        AND inbound.followed_id = outbound.follower_id
                       WHERE outbound.follower_id = ?
                         AND outbound.followed_id = chat_messages.user_id
                   )
               )
            ORDER BY chat_messages.created_at DESC, chat_messages.id DESC
            LIMIT 150
            """,
            (user["id"], user["id"]),
        ).fetchall()

    messages = [
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "match_id": row["match_id"],
            "audience": row["audience"],
            "message": row["message"],
            "created_at": str(row["created_at"]),
            "author": {
                "name": row["name"],
                "profile_picture": {
                    "initials": initials(row["name"]),
                    "hue": avatar_hue(row["name"]),
                },
            },
        }
        for row in reversed(rows)
    ]
    return jsonify({"messages": messages})


@app.post("/api/chat")
def save_chat_message():
    user, error_response = require_current_user()
    if error_response:
        return error_response
    assert user is not None

    data = load_world_cup_data()
    match_ids = {match["id"] for match in data["matches"]}
    payload = request.get_json(silent=True) or {}
    message = " ".join(str(payload.get("message", "")).split())
    audience = str(payload.get("audience", "pool")).strip().lower()
    match_id = payload.get("match_id")
    match_id = str(match_id) if match_id else None

    if audience not in {"pool", "friends"}:
        return jsonify({"error": "Choose pool chat or friends chat."}), 400
    if not message:
        return jsonify({"error": "Write a message before sending."}), 400
    if len(message) > 500:
        return jsonify({"error": "Messages can be at most 500 characters."}), 400
    if match_id and match_id not in match_ids:
        return jsonify({"error": "Choose a valid match for this chat."}), 400

    with get_db() as conn:
        execute(
            conn,
            """
            INSERT INTO chat_messages (user_id, match_id, audience, message, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (user["id"], match_id, audience, message),
        )

    logger.info(
        "Saved chat message for user %s audience=%s match=%s",
        user["id"],
        audience,
        match_id or "general",
    )
    return jsonify({"ok": True})


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
    now = utc_now()

    if not isinstance(prediction_items, list):
        return jsonify({"error": "Predictions must be a list."}), 400
    if quiz_items is not None and not isinstance(quiz_items, list):
        return jsonify({"error": "Quiz predictions must be a list."}), 400
    if leeuwtje_items is not None and not isinstance(leeuwtje_items, list):
        return jsonify({"error": "Leeuwtjes must be a list."}), 400

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

            viewership_prediction = item.get("viewership_prediction")
            if viewership_prediction in ("", None):
                viewership_prediction = None
            else:
                try:
                    viewership_prediction = int(viewership_prediction)
                except (TypeError, ValueError):
                    return jsonify({"error": "Kijkcijfers must be a whole number."}), 400
                if viewership_prediction < 0 or viewership_prediction > 50_000_000:
                    return jsonify({"error": "Kijkcijfers must be between 0 and 50,000,000."}), 400
            if viewership_prediction is not None and not quiz.get("viewership"):
                return jsonify({"error": f"Match {match_id} has no kijkcijfers question."}), 400

            existing = existing_quizzes.get(match_id)
            existing_answer = clean_text(existing["answer"] if existing else "")
            existing_viewership = existing["viewership_prediction"] if existing else None
            changed = answer != existing_answer or viewership_prediction != existing_viewership
            if changed and is_prediction_locked(match, now):
                return jsonify({"error": f"Quiz for match {match_id} is closed."}), 400
            if answer or viewership_prediction is not None:
                cleaned_quizzes.append((user["id"], match_id, answer, viewership_prediction))
            else:
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
        and is_winner_locked(data, now)
        and (not existing_winner or existing_winner["team_id"] != winner_team_id)
    )
    if winner_change_locked:
        return jsonify({"error": "The tournament winner pick is closed."}), 400

    with get_db() as conn:
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

    logger.info(
        "Saved %s match predictions, %s quiz answers and winner=%s for user %s",
        len(cleaned),
        len(cleaned_quizzes),
        bool(winner_team_id),
        user["id"],
    )
    return jsonify(user_pool_state(user, data))


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
