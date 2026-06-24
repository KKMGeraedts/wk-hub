from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
except ImportError as error:  # pragma: no cover - exercised with an import harness
    BaseModel = object  # type: ignore[assignment,misc]
    ConfigDict = dict  # type: ignore[assignment,misc]
    Field = None  # type: ignore[assignment]
    ValidationError = ValueError  # type: ignore[assignment,misc]

    def field_validator(*_fields: str) -> Any:  # type: ignore[no-redef]
        def decorator(func: Any) -> Any:
            return func

        return decorator

    PYDANTIC_IMPORT_ERROR: str | None = str(error)
else:
    PYDANTIC_IMPORT_ERROR = None

GENAI_PROVIDER_MISTRAL = "mistral"
GENAI_DEFAULT_MODEL = "mistral-small-latest"
GENAI_DEFAULT_TIMEOUT_SECONDS = 10
GENAI_JOB_QUIZ_ANSWER = "quiz_answer_from_match_facts"
GENAI_JOB_PLAYER_MATCH = "player_match_from_candidates"
GENAI_TARGET_MATCH_QUIZ = "match_quiz"
GENAI_TARGET_MATCH_SCORER = "match_scorer"
GENAI_TARGET_STRIKER_PICK = "striker_pick"
GENAI_STATUS_ACCEPTED = "accepted"
GENAI_STATUS_REJECTED = "rejected"
GENAI_STATUS_FAILED = "failed"
GENAI_STATUS_SKIPPED_MANUAL_OVERRIDE = "skipped_manual_override"
GENAI_STATUS_DISABLED = "disabled"
GENAI_REVIEW_APPROVED = "approved"
GENAI_REVIEW_DISAPPROVED = "disapproved"
SYNC_NOTIFICATION_GENAI_JOB_FAILED = "genai_job_failed"
SYNC_NOTIFICATION_SCORER_PLAYER_NOT_IN_SQUAD = "scorer_player_not_in_squad"
SYNC_NOTIFICATION_STRIKER_PICK_NOT_IN_SQUAD = "striker_pick_not_in_squad"
SYNC_TARGET_MATCH_RESULT = "match_result"
SYNC_TARGET_STRIKER_PICK = "striker_pick"

TEAM_PROFILES_PATH = Path()
USING_POSTGRES = False
logger = logging.getLogger("wk_hub.genai")
_structured_completion_override: Any | None = None

__all__ = [
    "GENAI_TARGET_MATCH_SCORER",
    "QuizReviewError",
    "configure",
    "genai_config",
    "run_genai_jobs_after_data_sync",
    "apply_auto_quiz_label",
    "canonical_squad_player_rows",
    "notification_target_id",
    "player_counter_keys",
    "player_counter_value",
    "quiz_genai_review_payload",
    "quiz_genai_payload_from_row",
    "player_genai_link_payload",
    "static_squad_player_rows",
    "verify_player_database_matches",
    "review_quiz_answer",
]

_RUNTIME_DEPENDENCIES = {
    "get_db",
    "label_audit",
    "recompute_all_computed_points",
}


def _unconfigured(*_args: Any, **_kwargs: Any) -> Any:
    raise RuntimeError("GenAI Service runtime is not configured")


get_db = _unconfigured
label_audit = _unconfigured
recompute_all_computed_points = _unconfigured


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_identity(value: Any) -> str:
    return clean_text(value).casefold()


def normalize_answer(value: Any) -> str:
    return clean_text(value).casefold()


def normalize_api_name(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return "".join(char.casefold() if char.isalnum() else " " for char in ascii_text)


def compact_name(value: Any) -> str:
    return " ".join(normalize_api_name(value).split())


def normalized_player_name(value: Any) -> str:
    return compact_name(value)


def int_env_value(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def row_has_key(row: Any, key: str) -> bool:
    try:
        row[key]
    except (KeyError, IndexError):
        return False
    return True


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


def json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return (
            value.astimezone(UTC).isoformat().replace("+00:00", "Z")
            if value.tzinfo
            else value.isoformat()
        )
    if isinstance(value, sqlite3.Row):
        keys = value.keys()
        return {key: json_ready(value[key]) for key in keys}
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [json_ready(item) for item in value]
    return value


def execute(conn: Any, query: str, params: tuple[Any, ...] = ()) -> Any:
    return conn.execute(query.replace("?", "%s") if USING_POSTGRES else query, params)


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
        SELECT id FROM admin_sync_notifications
        WHERE type = ? AND target_type = ? AND target_id = ? AND is_active = 1
        """,
        (notification_type, target_type, target_id),
    ).fetchone()
    if existing:
        execute(
            conn,
            """
            UPDATE admin_sync_notifications
            SET title = ?, body = ?, severity = ?, related_attempt_id = ?,
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
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
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
        SET is_active = 0, resolved_at = CURRENT_TIMESTAMP
        WHERE type = ? AND target_type = ? AND target_id = ? AND is_active = 1
        """,
        (notification_type, target_type, target_id),
    )


STRIKER_COLUMN_NAMES = tuple(f"striker_name_{index}" for index in range(1, 6))


def striker_pick_names(row: Any | None) -> list[str]:
    if not row:
        return []
    names = [
        clean_text(row[column] if row_has_key(row, column) else None)
        for column in STRIKER_COLUMN_NAMES
    ]
    names = [name for name in names if name]
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


def configure(
    *,
    team_profiles_path: Path,
    using_postgres: bool,
    structured_completion: Any | None = None,
    **dependencies: Any,
) -> None:
    """Bind app-owned infrastructure while keeping dependency direction one-way."""
    missing = _RUNTIME_DEPENDENCIES - dependencies.keys()
    if missing:
        raise ValueError(f"Missing GenAI runtime dependencies: {sorted(missing)}")
    unexpected = dependencies.keys() - _RUNTIME_DEPENDENCIES
    if unexpected:
        raise ValueError(f"Unexpected GenAI runtime dependencies: {sorted(unexpected)}")
    globals().update(dependencies)
    globals()["TEAM_PROFILES_PATH"] = team_profiles_path
    globals()["USING_POSTGRES"] = using_postgres
    globals()["_structured_completion_override"] = structured_completion


if PYDANTIC_IMPORT_ERROR is None:

    class QuizGenAIInputModel(BaseModel):
        model_config = ConfigDict(extra="forbid")

        question: str = Field(min_length=1)
        choices: list[str] = Field(min_length=1)
        match_data: dict[str, Any]

        @field_validator("question")
        @classmethod
        def quiz_question_must_have_text(cls, value: str) -> str:
            cleaned = value.strip()
            if not cleaned:
                raise ValueError("question must not be blank")
            return cleaned

        @field_validator("choices")
        @classmethod
        def quiz_choices_must_have_text(cls, value: list[str]) -> list[str]:
            choices = [str(choice).strip() for choice in value if str(choice).strip()]
            if not choices:
                raise ValueError("choices must contain at least one option")
            return choices

    class QuizGenAIOutputModel(BaseModel):
        model_config = ConfigDict(extra="forbid")

        choice: str
        confidence: float = Field(ge=0, le=1)
        reason: str = ""

        @field_validator("choice", "reason")
        @classmethod
        def text_fields_are_stripped(cls, value: str) -> str:
            return value.strip()

else:

    class QuizGenAIInputModel:  # type: ignore[no-redef]
        def __init__(self, question: str, choices: list[str], match_data: dict[str, Any]) -> None:
            self.question = question
            self.choices = choices
            self.match_data = match_data

        @classmethod
        def model_validate(cls, payload: Any) -> QuizGenAIInputModel:
            if not isinstance(payload, dict):
                raise ValueError("input must be a JSON object")
            question = clean_text(payload.get("question"))
            choices_payload = payload.get("choices")
            match_data = payload.get("match_data")
            if not question:
                raise ValueError("question must not be blank")
            if not isinstance(choices_payload, list):
                raise ValueError("choices must be a list")
            choices = [clean_text(choice) for choice in choices_payload if clean_text(choice)]
            if not choices:
                raise ValueError("choices must contain at least one option")
            if not isinstance(match_data, dict):
                raise ValueError("match_data must be a JSON object")
            return cls(question=question, choices=choices, match_data=match_data)

        def model_dump(self) -> dict[str, Any]:
            return {
                "question": self.question,
                "choices": self.choices,
                "match_data": self.match_data,
            }

    class QuizGenAIOutputModel:  # type: ignore[no-redef]
        def __init__(self, choice: str, confidence: float, reason: str) -> None:
            self.choice = choice
            self.confidence = confidence
            self.reason = reason

        @classmethod
        def model_validate(cls, payload: Any) -> QuizGenAIOutputModel:
            if not isinstance(payload, dict):
                raise ValueError("output must be a JSON object")
            choice = clean_text(payload.get("choice"))
            reason = clean_text(payload.get("reason"))
            confidence_value = payload.get("confidence")
            if confidence_value is None:
                raise ValueError("confidence must be a number")
            try:
                confidence = float(confidence_value)
            except (TypeError, ValueError) as error:
                raise ValueError("confidence must be a number") from error
            if confidence < 0 or confidence > 1:
                raise ValueError("confidence must be between 0 and 1")
            return cls(choice=choice, confidence=confidence, reason=reason)


QUIZ_GENAI_CONFIDENCE_THRESHOLD = 0.7


def quiz_genai_input_model_from_job_input(job_input: dict[str, Any]) -> QuizGenAIInputModel:
    payload = {
        "question": job_input.get("question"),
        "choices": job_input.get("choices") or job_input.get("answer_options"),
        "match_data": job_input.get("match_data") or job_input.get("facts") or {},
    }
    return QuizGenAIInputModel.model_validate(payload)


def quiz_genai_prompt_messages(job_input: dict[str, Any]) -> list[dict[str, str]]:
    quiz_input = quiz_genai_input_model_from_job_input(job_input)
    payload = quiz_input.model_dump()
    return [
        {
            "role": "system",
            "content": (
                "You answer football quiz questions using only the supplied JSON. "
                "Return JSON only with exactly these keys: choice, confidence, reason. "
                "choice must be one of choices, or an empty string when impossible. "
                "confidence must be a number from 0 to 1. Use confidence 0 when the "
                "facts do not contain enough information. Do not infer missing stats as no."
            ),
        },
        {
            "role": "user",
            "content": (
                "Examples:\n"
                'Input question: "Zijn er meer dan 4 gele kaarten?", choices ["ja","nee"], '
                "match_data has no yellow-card facts.\n"
                'Output: {"choice":"","confidence":0,'
                '"reason":"No yellow-card facts are supplied."}\n\n'
                'Input question: "Scoort Lamine Yamal in deze wedstrijd?", choices ["ja","nee"], '
                "match_data has completed player_stats for Lamine Yamal with goals 0.\n"
                'Output: {"choice":"nee","confidence":0.9,'
                '"reason":"The supplied player stats show 0 goals."}\n\n'
                "Now answer this input:\n"
                f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
            ),
        },
    ]


def player_genai_prompt_messages(job_input: dict[str, Any]) -> list[dict[str, str]]:
    payload = {
        "raw_player_name": clean_text(job_input.get("raw_player_name")),
        "match_id": clean_text(job_input.get("match_id")),
        "local_team_id": clean_text(job_input.get("local_team_id")),
        "candidates": job_input.get("candidates") or [],
    }
    return [
        {
            "role": "system",
            "content": (
                "You match one football player name to one supplied squad candidate. "
                "Use only the supplied candidates. Return JSON only with exactly these keys: "
                "status, matched_candidate_id, confidence, evidence, reason. status must be "
                "matched, ambiguous, or no_match. confidence must be high or low. Only use "
                "status matched when one candidate is clearly the same player. evidence must "
                'cite the chosen candidate as [{"type":"candidate","id":"..."}].'
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        },
    ]


def quiz_answer_options(quiz: dict[str, Any]) -> list[str]:
    choices = quiz.get("choices")
    if isinstance(choices, list):
        options = [clean_text(choice) for choice in choices]
        return [choice for choice in options if choice]
    if quiz.get("type") == "yes_no":
        return ["yes", "no"]
    correct_answers = quiz.get("correct_answers")
    if correct_answers is None and quiz.get("correct_answer") is not None:
        correct_answers = [quiz.get("correct_answer")]
    if isinstance(correct_answers, list):
        return [answer for answer in (clean_text(value) for value in correct_answers) if answer]
    return []


def quiz_genai_fact_payload(conn: Any, match_id: str) -> dict[str, Any]:
    result = execute(
        conn,
        """
        SELECT match_id, status_short, status_long, elapsed, home_score, away_score
        FROM match_results
        WHERE match_id = ?
        """,
        (match_id,),
    ).fetchone()
    events = execute(
        conn,
        """
        SELECT provider_event_key, elapsed, extra, local_team_id, team_name,
               player_name, assist_name, event_type, detail, comments
        FROM match_events
        WHERE match_id = ?
        ORDER BY COALESCE(elapsed, 999), COALESCE(extra, 0), provider_event_key
        """,
        (match_id,),
    ).fetchall()
    clean_sheets = execute(
        conn,
        """
        SELECT local_team_id, team_name
        FROM match_clean_sheets
        WHERE match_id = ?
        ORDER BY local_team_id
        """,
        (match_id,),
    ).fetchall()
    player_stats = execute(
        conn,
        """
        SELECT provider_player_key, local_team_id, team_name, player_name, minutes,
               position, goals, assists, yellow_cards, red_cards, clean_sheet
        FROM player_match_stats
        WHERE match_id = ?
        ORDER BY team_name, position, player_name, provider_player_key
        """,
        (match_id,),
    ).fetchall()
    return {
        "result": (
            {
                "id": match_id,
                "status_short": result["status_short"],
                "status_long": result["status_long"],
                "elapsed": result["elapsed"],
                "home_score": result["home_score"],
                "away_score": result["away_score"],
            }
            if result
            else None
        ),
        "events": [
            {
                "id": row["provider_event_key"],
                "elapsed": row["elapsed"],
                "extra": row["extra"],
                "local_team_id": row["local_team_id"],
                "team_name": row["team_name"],
                "player_name": row["player_name"],
                "assist_name": row["assist_name"],
                "event_type": row["event_type"],
                "detail": row["detail"],
                "comments": row["comments"],
            }
            for row in events
        ],
        "clean_sheets": [
            {
                "id": row["local_team_id"],
                "local_team_id": row["local_team_id"],
                "team_name": row["team_name"],
            }
            for row in clean_sheets
        ],
        "player_stats": [
            {
                "id": row["provider_player_key"],
                "local_team_id": row["local_team_id"],
                "team_name": row["team_name"],
                "player_name": row["player_name"],
                "minutes": row["minutes"],
                "position": row["position"],
                "goals": row["goals"],
                "assists": row["assists"],
                "yellow_cards": row["yellow_cards"],
                "red_cards": row["red_cards"],
                "clean_sheet": bool(row["clean_sheet"]),
            }
            for row in player_stats
        ],
    }


def build_quiz_genai_input(conn: Any, match: dict[str, Any]) -> dict[str, Any]:
    quiz = match.get("quiz") if isinstance(match, dict) else None
    if not isinstance(quiz, dict):
        quiz = {}
    facts = quiz_genai_fact_payload(conn, clean_text(match.get("id")))
    choices = quiz_answer_options(quiz)
    validated_input = QuizGenAIInputModel.model_validate(
        {
            "question": clean_text(quiz.get("question")),
            "choices": choices,
            "match_data": facts,
        }
    )
    return {
        "job_type": GENAI_JOB_QUIZ_ANSWER,
        "match_id": match.get("id"),
        "question": validated_input.question,
        "choices": validated_input.choices,
        "match_data": validated_input.match_data,
        "answer_options": validated_input.choices,
        "facts": validated_input.match_data,
    }


def quiz_genai_evidence_ids(job_input: dict[str, Any]) -> set[tuple[str, str]]:
    facts = job_input.get("facts") if isinstance(job_input, dict) else {}
    if not isinstance(facts, dict):
        return set()
    allowed: set[tuple[str, str]] = set()
    result = facts.get("result")
    if isinstance(result, dict) and result.get("id"):
        allowed.add(("match_result", clean_text(result.get("id"))))
    for row in facts.get("events") or []:
        if isinstance(row, dict) and row.get("id"):
            allowed.add(("match_event", clean_text(row.get("id"))))
    for row in facts.get("clean_sheets") or []:
        if isinstance(row, dict) and row.get("id"):
            allowed.add(("clean_sheet", clean_text(row.get("id"))))
    for row in facts.get("player_stats") or []:
        if isinstance(row, dict) and row.get("id"):
            allowed.add(("player_stat", clean_text(row.get("id"))))
    return allowed


def quiz_genai_has_supplied_facts(job_input: dict[str, Any]) -> bool:
    facts = job_input.get("match_data") or job_input.get("facts")
    if not isinstance(facts, dict):
        return False
    return bool(
        facts.get("result")
        or facts.get("events")
        or facts.get("clean_sheets")
        or facts.get("player_stats")
    )


def validate_quiz_genai_output(output: Any, job_input: dict[str, Any]) -> dict[str, Any]:
    def rejected(code: str, message: str) -> dict[str, Any]:
        return {
            "accepted": False,
            "correct_answers": [],
            "evidence": [],
            "failure_code": code,
            "failure_message": message,
        }

    if not isinstance(output, dict):
        return rejected("invalid_output", "GenAI output must be a JSON object.")
    if "choice" in output:
        try:
            parsed_input = quiz_genai_input_model_from_job_input(job_input)
            parsed_output = QuizGenAIOutputModel.model_validate(output)
        except (ValidationError, ValueError) as error:
            return rejected("invalid_output", str(error))
        if parsed_output.confidence == 0:
            return rejected("insufficient_evidence", "Quiz GenAI could not answer from facts.")
        if not quiz_genai_has_supplied_facts(job_input):
            return rejected("insufficient_evidence", "Quiz GenAI answered without supplied facts.")
        if parsed_output.confidence < QUIZ_GENAI_CONFIDENCE_THRESHOLD:
            return rejected("low_confidence", "Quiz GenAI confidence was too low.")
        option_by_normalized = {
            normalize_answer(option): option for option in parsed_input.choices if option
        }
        normalized_choice = normalize_answer(parsed_output.choice)
        if normalized_choice not in option_by_normalized:
            return rejected("answer_outside_options", "Quiz GenAI selected an unknown option.")
        return {
            "accepted": True,
            "correct_answers": [option_by_normalized[normalized_choice]],
            "evidence": [],
            "failure_code": None,
            "failure_message": None,
            "confidence": parsed_output.confidence,
            "reason": parsed_output.reason,
        }

    status = clean_text(output.get("status")).casefold()
    if status != "answered":
        return rejected("unsupported_status", "Quiz GenAI did not answer the question.")
    selected_answers = output.get("selected_answers")
    if not isinstance(selected_answers, list) or not selected_answers:
        return rejected("invalid_output", "Quiz GenAI output must select at least one answer.")
    confidence = clean_text(output.get("confidence")).casefold()
    if confidence != "high":
        return rejected("low_confidence", "Quiz GenAI confidence was not high.")
    options = [clean_text(option) for option in job_input.get("answer_options") or []]
    option_by_normalized = {normalize_answer(option): option for option in options if option}
    correct_answers: list[str] = []
    for answer in selected_answers:
        normalized = normalize_answer(answer)
        if normalized not in option_by_normalized:
            return rejected("answer_outside_options", "Quiz GenAI selected an unknown option.")
        correct_answers.append(option_by_normalized[normalized])
    evidence = output.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return rejected("missing_evidence", "Quiz GenAI output did not cite supplied facts.")
    allowed_ids = quiz_genai_evidence_ids(job_input)
    compact_evidence: list[dict[str, str]] = []
    for item in evidence:
        if not isinstance(item, dict):
            return rejected("invalid_evidence", "Quiz GenAI evidence must be object references.")
        ref = (clean_text(item.get("type")), clean_text(item.get("id")))
        if ref not in allowed_ids:
            return rejected("unsupported_evidence", "Quiz GenAI evidence was not supplied.")
        compact_evidence.append({"type": ref[0], "id": ref[1]})
    return {
        "accepted": True,
        "correct_answers": correct_answers,
        "evidence": compact_evidence,
        "failure_code": None,
        "failure_message": None,
        "confidence": confidence,
        "reason": clean_text(output.get("reason")),
    }


def manual_quiz_override_exists(conn: Any, match_id: str) -> bool:
    row = execute(
        conn,
        "SELECT 1 FROM quiz_label_overrides WHERE match_id = ? LIMIT 1",
        (match_id,),
    ).fetchone()
    return row is not None


def json_list_or_empty(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def quiz_genai_payload_from_row(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "job_type": GENAI_JOB_QUIZ_ANSWER,
        "status": row["job_status"] if row_has_key(row, "job_status") else GENAI_STATUS_ACCEPTED,
        "provider_key": row["provider_key"] if row_has_key(row, "provider_key") else None,
        "model": row["model"] if row_has_key(row, "model") else None,
        "source": row["source"],
        "confidence": row["confidence"],
        "evidence": json_list_or_empty(row["evidence_json"]),
        "resolved_at": row["resolved_at"],
        "job_result_id": row["job_result_id"],
    }


def quiz_genai_review_payload(
    conn: Any,
    *,
    match: dict[str, Any],
    job_result_id: int,
) -> dict[str, Any]:
    quiz = match.get("quiz") or {}
    auto_label = execute(
        conn,
        "SELECT * FROM quiz_auto_labels WHERE match_id = ? AND job_result_id = ?",
        (clean_text(match.get("id")), job_result_id),
    ).fetchone()
    review = execute(
        conn,
        "SELECT * FROM quiz_genai_reviews WHERE job_result_id = ?",
        (job_result_id,),
    ).fetchone()
    return {
        "job_result_id": job_result_id,
        "match_id": clean_text(match.get("id")),
        "question": clean_text(quiz.get("question")),
        "choices": [clean_text(choice) for choice in quiz.get("choices") or []],
        "genai_answers": parse_correct_answers_json(
            auto_label["correct_answers_json"] if auto_label is not None else None
        ),
        "confidence": auto_label["confidence"] if auto_label is not None else None,
        "review_status": review["decision"] if review is not None else "pending",
        "reviewed_answers": parse_correct_answers_json(
            review["selected_answers_json"] if review is not None else None
        ),
        "reviewed_at": review["reviewed_at"] if review is not None else None,
    }


class QuizReviewError(ValueError):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def review_quiz_answer(
    conn: Any,
    data: dict[str, Any],
    *,
    job_result_id: int,
    decision: str,
    correct_answer: Any,
    reviewed_by_user_id: int,
) -> dict[str, Any]:
    if decision not in {GENAI_REVIEW_APPROVED, GENAI_REVIEW_DISAPPROVED}:
        raise QuizReviewError("decision must be approved or disapproved.", 400)
    auto_label = execute(
        conn,
        """
        SELECT qal.*, gjr.status AS job_status
        FROM quiz_auto_labels qal
        JOIN genai_job_results gjr ON gjr.id = qal.job_result_id
        WHERE qal.job_result_id = ?
          AND gjr.job_type = ?
          AND gjr.status = ?
        """,
        (job_result_id, GENAI_JOB_QUIZ_ANSWER, GENAI_STATUS_ACCEPTED),
    ).fetchone()
    if auto_label is None:
        raise QuizReviewError("This GenAI quiz answer is no longer active.", 404)
    match_id = clean_text(auto_label["match_id"])
    match = next(
        (item for item in data.get("matches", []) if clean_text(item.get("id")) == match_id),
        None,
    )
    if match is None or not isinstance(match.get("quiz"), dict):
        raise QuizReviewError("Quiz match not found.", 404)
    quiz = match["quiz"]
    choices = [clean_text(choice) for choice in quiz.get("choices") or []]
    selected_answers = parse_correct_answers_json(auto_label["correct_answers_json"])
    before_override = execute(
        conn,
        "SELECT * FROM quiz_label_overrides WHERE match_id = ?",
        (match_id,),
    ).fetchone()
    if decision == GENAI_REVIEW_DISAPPROVED:
        requested_answer = clean_text(correct_answer)
        selected_answer = next(
            (
                choice
                for choice in choices
                if normalize_answer(choice) == normalize_answer(requested_answer)
            ),
            None,
        )
        if selected_answer is None:
            raise QuizReviewError("Select one of the available quiz answers.", 400)
        selected_answers = [selected_answer]
        execute(
            conn,
            """
            INSERT INTO quiz_label_overrides (
                match_id, question, choices_json, correct_answers_json,
                viewership_answer, source, updated_by_user_id, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'manual', ?, CURRENT_TIMESTAMP)
            ON CONFLICT(match_id) DO UPDATE SET
                question = excluded.question,
                choices_json = excluded.choices_json,
                correct_answers_json = excluded.correct_answers_json,
                viewership_answer = excluded.viewership_answer,
                source = 'manual',
                updated_by_user_id = excluded.updated_by_user_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                match_id,
                clean_text(quiz.get("question")),
                json.dumps(choices),
                json.dumps(selected_answers),
                quiz.get("viewership_answer"),
                reviewed_by_user_id,
            ),
        )
    execute(
        conn,
        """
        INSERT INTO quiz_genai_reviews (
            job_result_id, match_id, decision, selected_answers_json,
            reviewed_by_user_id, reviewed_at
        )
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(job_result_id) DO UPDATE SET
            decision = excluded.decision,
            selected_answers_json = excluded.selected_answers_json,
            reviewed_by_user_id = excluded.reviewed_by_user_id,
            reviewed_at = CURRENT_TIMESTAMP
        """,
        (
            job_result_id,
            match_id,
            decision,
            json.dumps(selected_answers),
            reviewed_by_user_id,
        ),
    )
    after_override = execute(
        conn,
        "SELECT * FROM quiz_label_overrides WHERE match_id = ?",
        (match_id,),
    ).fetchone()
    label_audit(
        conn,
        reviewed_by_user_id,
        "quiz_genai_review",
        match_id,
        before_override,
        after_override,
        source=f"genai_review:{decision}",
    )
    return quiz_genai_review_payload(conn, match=match, job_result_id=job_result_id)


def player_genai_link_payload(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "job_type": GENAI_JOB_PLAYER_MATCH,
        "status": row["job_status"] if row_has_key(row, "job_status") else GENAI_STATUS_ACCEPTED,
        "source": row["source"],
        "provider_key": row["provider_key"] if row_has_key(row, "provider_key") else None,
        "model": row["model"] if row_has_key(row, "model") else None,
        "confidence": row["confidence"],
        "raw_player_name": row["raw_player_name"],
        "matched_player_name": row["matched_player_name"],
        "matched_local_team_id": row["matched_local_team_id"],
        "matched_api_player_id": row["matched_api_player_id"],
        "evidence": json_list_or_empty(row["evidence_json"]),
        "job_result_id": row["job_result_id"],
    }


def apply_auto_quiz_label(match: dict[str, Any], row: Any) -> None:
    quiz = match.get("quiz")
    if not isinstance(quiz, dict):
        return
    correct_answers = parse_correct_answers_json(row["correct_answers_json"])
    if not correct_answers:
        return
    quiz["correct_answers"] = correct_answers
    quiz["correct_answer"] = correct_answers[0]
    quiz["label_source"] = row["source"] or "genai"
    quiz["label_updated_at"] = row["updated_at"]
    quiz["manual_override_active"] = False
    quiz["genai"] = quiz_genai_payload_from_row(row)


def store_quiz_auto_label(
    conn: Any,
    *,
    match_id: str,
    job_result_id: int | None,
    correct_answers: list[str],
    confidence: str,
    evidence: list[dict[str, str]],
    facts_revision_key: str | None,
) -> None:
    execute(
        conn,
        """
        INSERT INTO quiz_auto_labels (
            match_id, source, job_result_id, correct_answers_json, confidence,
            facts_revision_key, evidence_json, resolved_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(match_id) DO UPDATE SET
            source = excluded.source,
            job_result_id = excluded.job_result_id,
            correct_answers_json = excluded.correct_answers_json,
            confidence = excluded.confidence,
            facts_revision_key = excluded.facts_revision_key,
            evidence_json = excluded.evidence_json,
            resolved_at = excluded.resolved_at,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            match_id,
            f"genai:{GENAI_PROVIDER_MISTRAL}",
            job_result_id,
            json.dumps(correct_answers),
            confidence,
            facts_revision_key,
            json.dumps(evidence, sort_keys=True),
        ),
    )


def publish_quiz_genai_label(
    conn: Any,
    data: dict[str, Any],
    match: dict[str, Any],
    output: Any,
    job_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if job_input is None:
        job_input = build_quiz_genai_input(conn, match)
    match_id = clean_text(match.get("id"))
    validation = validate_quiz_genai_output(output, job_input)
    if not validation["accepted"]:
        result_id = record_genai_job_result(
            conn,
            job_type=GENAI_JOB_QUIZ_ANSWER,
            target_type=GENAI_TARGET_MATCH_QUIZ,
            target_id=match_id,
            status=GENAI_STATUS_REJECTED,
            input_payload=job_input,
            failure_code=validation["failure_code"],
            failure_message=validation["failure_message"],
        )
        create_genai_failure_notification(
            conn,
            job_type=GENAI_JOB_QUIZ_ANSWER,
            target_type=GENAI_TARGET_MATCH_QUIZ,
            target_id=match_id,
            failure_code=validation["failure_code"],
            title="Quiz GenAI needs review",
            body=validation["failure_message"],
            related_attempt_id=result_id,
        )
        return validation

    result_id = record_genai_job_result(
        conn,
        job_type=GENAI_JOB_QUIZ_ANSWER,
        target_type=GENAI_TARGET_MATCH_QUIZ,
        target_id=match_id,
        status=GENAI_STATUS_ACCEPTED,
        input_payload=job_input,
        accepted_output={"selected_answers": validation["correct_answers"]},
        evidence=validation["evidence"],
    )
    store_quiz_auto_label(
        conn,
        match_id=match_id,
        job_result_id=result_id,
        correct_answers=validation["correct_answers"],
        confidence=str(validation.get("confidence") or "high"),
        evidence=validation["evidence"],
        facts_revision_key=genai_input_hash(job_input.get("facts")),
    )
    for failure_code in (
        "invalid_output",
        "insufficient_evidence",
        "unsupported_status",
        "low_confidence",
        "answer_outside_options",
        "missing_evidence",
        "invalid_evidence",
        "unsupported_evidence",
    ):
        resolve_genai_failure_notification(
            conn,
            job_type=GENAI_JOB_QUIZ_ANSWER,
            target_type=GENAI_TARGET_MATCH_QUIZ,
            target_id=match_id,
            failure_code=failure_code,
        )
    if not manual_quiz_override_exists(conn, match_id):
        auto_row = execute(
            conn,
            "SELECT * FROM quiz_auto_labels WHERE match_id = ?",
            (match_id,),
        ).fetchone()
        if auto_row is not None:
            apply_auto_quiz_label(match, auto_row)
    conn.commit()
    recompute_all_computed_points(data)
    validation["job_result_id"] = result_id
    return validation


def genai_config() -> dict[str, Any]:
    provider_key = clean_text(os.environ.get("GENAI_PROVIDER") or GENAI_PROVIDER_MISTRAL).casefold()
    model = clean_text(os.environ.get("GENAI_MODEL") or GENAI_DEFAULT_MODEL)
    timeout_seconds = int_env_value("GENAI_TIMEOUT_SECONDS", GENAI_DEFAULT_TIMEOUT_SECONDS)
    api_key = ""
    disabled_reason = ""
    if provider_key != GENAI_PROVIDER_MISTRAL:
        disabled_reason = "unsupported_provider"
    elif PYDANTIC_IMPORT_ERROR:
        disabled_reason = "missing_pydantic"
    else:
        api_key = clean_text(os.environ.get("MISTRAL_API_KEY"))
        if not api_key:
            disabled_reason = "missing_mistral_api_key"
    return {
        "provider_key": provider_key,
        "model": model,
        "api_key": api_key,
        "timeout_seconds": timeout_seconds,
        "enabled": not disabled_reason,
        "disabled_reason": disabled_reason or None,
    }


def canonical_json(value: Any) -> str:
    return json.dumps(json_ready(value), sort_keys=True, separators=(",", ":"))


def genai_input_hash(input_payload: dict[str, Any] | None) -> str | None:
    if input_payload is None:
        return None
    return hashlib.sha256(canonical_json(input_payload).encode("utf-8")).hexdigest()


def json_dump_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(json_ready(value), sort_keys=True)


def record_genai_job_result(
    conn: Any,
    *,
    job_type: str,
    target_type: str,
    target_id: str,
    status: str,
    provider_key: str | None = None,
    model: str | None = None,
    input_payload: dict[str, Any] | None = None,
    accepted_output: Any | None = None,
    evidence: Any | None = None,
    failure_code: str | None = None,
    failure_message: str | None = None,
) -> int | None:
    config = genai_config()
    provider = provider_key or config["provider_key"]
    model_name = model or config["model"]
    input_digest = genai_input_hash(input_payload)
    if USING_POSTGRES:
        row = execute(
            conn,
            """
            INSERT INTO genai_job_results (
                job_type, target_type, target_id, provider_key, model, status,
                failure_code, failure_message, accepted_output_json, evidence_json,
                input_hash, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (
                job_type,
                target_type,
                target_id,
                provider,
                model_name,
                status,
                failure_code,
                failure_message,
                json_dump_or_none(accepted_output),
                json_dump_or_none(evidence),
                input_digest,
            ),
        ).fetchone()
        return int(row["id"]) if row else None
    cursor = execute(
        conn,
        """
        INSERT INTO genai_job_results (
            job_type, target_type, target_id, provider_key, model, status,
            failure_code, failure_message, accepted_output_json, evidence_json,
            input_hash, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            job_type,
            target_type,
            target_id,
            provider,
            model_name,
            status,
            failure_code,
            failure_message,
            json_dump_or_none(accepted_output),
            json_dump_or_none(evidence),
            input_digest,
        ),
    )
    return int(cursor.lastrowid) if cursor.lastrowid is not None else None


def genai_job_result_by_id(conn: Any, result_id: int | None) -> Any | None:
    if result_id is None:
        return None
    return execute(
        conn,
        """
        SELECT id, job_type, target_type, target_id, provider_key, model, status,
               failure_code, failure_message, accepted_output_json, evidence_json,
               input_hash, created_at, updated_at
        FROM genai_job_results
        WHERE id = ?
        """,
        (result_id,),
    ).fetchone()


def genai_notification_target_type(job_type: str, target_type: str) -> str:
    return f"genai:{job_type}:{target_type}"


def genai_notification_target_id(target_id: str, failure_code: str) -> str:
    return f"{target_id}:{failure_code}"


def create_genai_failure_notification(
    conn: Any,
    *,
    job_type: str,
    target_type: str,
    target_id: str,
    failure_code: str,
    title: str,
    body: str,
    severity: str = "warning",
    related_attempt_id: int | None = None,
) -> None:
    create_admin_sync_notification(
        conn,
        notification_type=SYNC_NOTIFICATION_GENAI_JOB_FAILED,
        target_type=genai_notification_target_type(job_type, target_type),
        target_id=genai_notification_target_id(target_id, failure_code),
        title=title,
        body=body,
        severity=severity,
        related_attempt_id=related_attempt_id,
    )


def resolve_genai_failure_notification(
    conn: Any,
    *,
    job_type: str,
    target_type: str,
    target_id: str,
    failure_code: str,
) -> None:
    resolve_admin_sync_notification(
        conn,
        notification_type=SYNC_NOTIFICATION_GENAI_JOB_FAILED,
        target_type=genai_notification_target_type(job_type, target_type),
        target_id=genai_notification_target_id(target_id, failure_code),
    )


def resolve_genai_failure_notifications_for_target(
    conn: Any,
    *,
    job_type: str,
    target_type: str,
    target_id: str,
) -> None:
    notification_target_type = genai_notification_target_type(job_type, target_type)
    execute(
        conn,
        """
        UPDATE admin_sync_notifications
        SET is_active = 0,
            resolved_at = CURRENT_TIMESTAMP
        WHERE type = ?
          AND target_type = ?
          AND (target_id = ? OR target_id LIKE ?)
          AND is_active = 1
        """,
        (
            SYNC_NOTIFICATION_GENAI_JOB_FAILED,
            notification_target_type,
            target_id,
            f"{target_id}:%",
        ),
    )


class GenAIProviderError(RuntimeError):
    pass


def parse_mistral_json_response(payload: dict[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise GenAIProviderError("missing_choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        content = "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        raise GenAIProviderError("missing_content")
    try:
        parsed = json.loads(content)
    except ValueError as error:
        raise GenAIProviderError("invalid_json_content") from error
    if not isinstance(parsed, dict):
        raise GenAIProviderError("json_content_not_object")
    return parsed


def mistral_structured_completion(
    *,
    messages: list[dict[str, str]],
    model: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    config = genai_config()
    if not config["enabled"]:
        raise GenAIProviderError(config["disabled_reason"] or "genai_disabled")
    body = json.dumps(
        {
            "model": model or config["model"],
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")
    request_obj = Request(
        "https://api.mistral.ai/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(
            request_obj,
            timeout=timeout_seconds or config["timeout_seconds"],
        ) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        raise GenAIProviderError("provider_request_failed") from error
    if not isinstance(response_payload, dict):
        raise GenAIProviderError("invalid_provider_response")
    return parse_mistral_json_response(response_payload)


def run_genai_structured_completion(
    *,
    messages: list[dict[str, str]],
    model: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    if _structured_completion_override is not None:
        return _structured_completion_override(messages=messages)
    config = genai_config()
    if config["provider_key"] != GENAI_PROVIDER_MISTRAL:
        raise GenAIProviderError("unsupported_provider")
    return mistral_structured_completion(
        messages=messages,
        model=model,
        timeout_seconds=timeout_seconds,
    )


def player_initial_surname_key(value: Any) -> str:
    parts = compact_name(value).split()
    if len(parts) < 2:
        return ""
    surname = parts[-1]
    initials = "".join(part[0] for part in parts[:-1] if part)
    if not surname or not initials:
        return ""
    return f"{initials[0]}:{surname}"


def player_counter_keys(value: Any) -> list[str]:
    keys = []
    normalized_name = normalized_player_name(value)
    if normalized_name:
        keys.append(normalized_name)
    signature = player_initial_surname_key(value)
    if signature and signature not in keys:
        keys.append(signature)
    return keys


def player_counter_value(counter: Counter[str], player_name: Any) -> int:
    return max((counter[key] for key in player_counter_keys(player_name)), default=0)


def player_name_match_keys(player_name: Any) -> set[str]:
    normalized = normalized_player_name(player_name)
    if not normalized:
        return set()
    keys = {normalized}
    tokens = normalized.split()
    if len(tokens) > 1:
        keys.add(" ".join([tokens[-1], *tokens[:-1]]))
    return keys


def static_squad_player_rows() -> list[dict[str, Any]]:
    if not TEAM_PROFILES_PATH.exists():
        return []
    try:
        with TEAM_PROFILES_PATH.open(encoding="utf-8") as profiles_file:
            profiles_data = json.load(profiles_file)
    except Exception:
        logger.exception("Could not load static squad player database")
        return []

    rows: list[dict[str, Any]] = []
    for team in profiles_data.get("teams", []):
        if not isinstance(team, dict):
            continue
        local_team_id = clean_text(team.get("id"))
        for player in team.get("squad") or []:
            if not isinstance(player, dict):
                continue
            player_name = clean_text(player.get("name"))
            if player_name and local_team_id:
                rows.append(
                    {
                        "local_team_id": local_team_id,
                        "provider_player_key": compact_name(player_name),
                        "api_player_id": None,
                        "player_name": player_name,
                        "source": "static_profile",
                    }
                )
    return rows


def synced_squad_player_rows(conn: Any) -> list[dict[str, Any]]:
    rows = execute(
        conn,
        """
        SELECT local_team_id, provider_player_key, api_player_id, player_name
        FROM team_squad_players
        """,
    ).fetchall()
    return [
        {
            "local_team_id": row["local_team_id"],
            "provider_player_key": row["provider_player_key"],
            "api_player_id": row["api_player_id"],
            "player_name": row["player_name"],
            "source": "api_football",
        }
        for row in rows
    ]


def canonical_squad_player_rows(conn: Any) -> list[dict[str, Any]]:
    rows_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in static_squad_player_rows():
        rows_by_key[(row["local_team_id"], normalized_player_name(row["player_name"]))] = row
    for row in synced_squad_player_rows(conn):
        rows_by_key[(row["local_team_id"], normalized_player_name(row["player_name"]))] = row
    return list(rows_by_key.values())


def squad_player_database(conn: Any) -> tuple[set[int], set[str], set[str], set[str]]:
    player_rows = canonical_squad_player_rows(conn)
    api_ids = {int(row["api_player_id"]) for row in player_rows if row["api_player_id"] is not None}
    player_names = {
        clean_text(row["player_name"]) for row in player_rows if clean_text(row["player_name"])
    }
    names = {key for player_name in player_names for key in player_name_match_keys(player_name)}
    signature_counts = Counter(
        signature
        for player_name in player_names
        for signature in [player_initial_surname_key(player_name)]
        if signature
    )
    single_token_counts = Counter(
        tokens[0]
        for player_name in player_names
        for tokens in [normalized_player_name(player_name).split()]
        if len(tokens) > 1
    )
    unique_signatures = {signature for signature, count in signature_counts.items() if count == 1}
    unique_single_tokens = {
        token for token, count in single_token_counts.items() if token and count == 1
    }
    return api_ids, names, unique_signatures, unique_single_tokens


def player_matches_squad_database(
    *,
    api_player_id: Any | None,
    player_name: Any,
    squad_api_ids: set[int],
    squad_names: set[str],
    squad_initial_surname_keys: set[str],
    squad_single_token_keys: set[str] | None = None,
) -> bool:
    parsed_api_player_id = int_or_none(api_player_id)
    if parsed_api_player_id is not None and parsed_api_player_id in squad_api_ids:
        return True
    normalized_name = normalized_player_name(player_name)
    if normalized_name and normalized_name in squad_names:
        return True
    tokens = normalized_name.split()
    if (
        squad_single_token_keys is not None
        and len(tokens) == 1
        and tokens[0] in squad_single_token_keys
    ):
        return True
    signature = player_initial_surname_key(player_name)
    return bool(signature and signature in squad_initial_surname_keys)


def player_genai_should_run(
    *,
    api_player_id: Any | None,
    player_name: Any,
    squad_api_ids: set[int],
    squad_names: set[str],
    squad_initial_surname_keys: set[str],
    squad_single_token_keys: set[str] | None = None,
) -> bool:
    return not player_matches_squad_database(
        api_player_id=api_player_id,
        player_name=player_name,
        squad_api_ids=squad_api_ids,
        squad_names=squad_names,
        squad_initial_surname_keys=squad_initial_surname_keys,
        squad_single_token_keys=squad_single_token_keys,
    )


def player_candidate_id(row: Any) -> str:
    return f"{clean_text(row['local_team_id'])}:{clean_text(row['provider_player_key'])}"


def player_genai_candidate_shortlist(
    conn: Any,
    *,
    local_team_id: str | None = None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    team_filter = clean_text(local_team_id)
    rows = [
        row
        for row in canonical_squad_player_rows(conn)
        if not team_filter or row["local_team_id"] == team_filter
    ]
    rows = sorted(
        rows,
        key=lambda row: (
            normalize_identity(row["player_name"]),
            row["local_team_id"],
            row["provider_player_key"],
        ),
    )[: int(limit)]
    return [
        {
            "candidate_id": player_candidate_id(row),
            "api_player_id": row["api_player_id"],
            "player_name": row["player_name"],
            "local_team_id": row["local_team_id"],
            "provider_player_key": row["provider_player_key"],
            "source": row["source"],
        }
        for row in rows
    ]


def build_player_genai_input(
    conn: Any,
    *,
    target_type: str,
    target_id: str,
    raw_player_name: str,
    match_id: str | None = None,
    local_team_id: str | None = None,
) -> dict[str, Any]:
    return {
        "job_type": GENAI_JOB_PLAYER_MATCH,
        "target_type": clean_text(target_type),
        "target_id": clean_text(target_id),
        "raw_player_name": clean_text(raw_player_name),
        "match_id": clean_text(match_id),
        "local_team_id": clean_text(local_team_id),
        "candidates": player_genai_candidate_shortlist(conn, local_team_id=local_team_id),
    }


def validate_player_genai_output(output: Any, job_input: dict[str, Any]) -> dict[str, Any]:
    def rejected(code: str, message: str) -> dict[str, Any]:
        return {
            "accepted": False,
            "matched_candidate": None,
            "evidence": [],
            "failure_code": code,
            "failure_message": message,
        }

    if not isinstance(output, dict):
        return rejected("invalid_output", "GenAI player output must be a JSON object.")
    status = clean_text(output.get("status")).casefold()
    if status in {"ambiguous", "no_match"}:
        return rejected(status, "GenAI player match did not produce one safe candidate.")
    if status != "matched":
        return rejected("unsupported_status", "GenAI player output used an unsupported status.")
    if clean_text(output.get("confidence")).casefold() != "high":
        return rejected("low_confidence", "GenAI player match confidence was not high.")
    candidates = {
        candidate["candidate_id"]: candidate
        for candidate in job_input.get("candidates") or []
        if isinstance(candidate, dict) and candidate.get("candidate_id")
    }
    candidate_id = clean_text(output.get("matched_candidate_id"))
    if candidate_id not in candidates:
        return rejected(
            "candidate_outside_shortlist",
            "GenAI player match selected a candidate outside the supplied shortlist.",
        )
    evidence = output.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return rejected("missing_evidence", "GenAI player match did not cite a candidate.")
    compact_evidence: list[dict[str, str]] = []
    for item in evidence:
        if not isinstance(item, dict):
            return rejected("invalid_evidence", "GenAI player evidence must be object references.")
        ref_type = clean_text(item.get("type"))
        ref_id = clean_text(item.get("id"))
        if ref_type != "candidate" or ref_id not in candidates:
            return rejected("unsupported_evidence", "GenAI player evidence was not supplied.")
        compact_evidence.append({"type": ref_type, "id": ref_id})
    return {
        "accepted": True,
        "matched_candidate": candidates[candidate_id],
        "evidence": compact_evidence,
        "failure_code": None,
        "failure_message": None,
        "confidence": "high",
        "reason": clean_text(output.get("reason")),
    }


def accepted_player_candidate_link_exists(
    conn: Any,
    *,
    target_type: str,
    target_id: str,
) -> bool:
    row = execute(
        conn,
        """
        SELECT 1
        FROM player_candidate_links
        WHERE target_type = ?
          AND target_id = ?
          AND confidence = 'high'
        LIMIT 1
        """,
        (target_type, target_id),
    ).fetchone()
    return row is not None


def store_player_candidate_link(
    conn: Any,
    *,
    job_input: dict[str, Any],
    job_result_id: int | None,
    candidate: dict[str, Any],
    evidence: list[dict[str, str]],
) -> None:
    execute(
        conn,
        """
        INSERT INTO player_candidate_links (
            target_type, target_id, raw_player_name, matched_local_team_id,
            matched_api_player_id, matched_player_name, source, job_result_id,
            confidence, evidence_json, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'high', ?, CURRENT_TIMESTAMP)
        ON CONFLICT(target_type, target_id) DO UPDATE SET
            raw_player_name = excluded.raw_player_name,
            matched_local_team_id = excluded.matched_local_team_id,
            matched_api_player_id = excluded.matched_api_player_id,
            matched_player_name = excluded.matched_player_name,
            source = excluded.source,
            job_result_id = excluded.job_result_id,
            confidence = excluded.confidence,
            evidence_json = excluded.evidence_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            job_input["target_type"],
            job_input["target_id"],
            job_input["raw_player_name"],
            candidate["local_team_id"],
            candidate["api_player_id"],
            candidate["player_name"],
            f"genai:{GENAI_PROVIDER_MISTRAL}",
            job_result_id,
            json.dumps(evidence, sort_keys=True),
        ),
    )


def resolve_player_match_notifications(conn: Any, target_type: str, target_id: str) -> None:
    if target_type == GENAI_TARGET_MATCH_SCORER:
        resolve_admin_sync_notification(
            conn,
            notification_type=SYNC_NOTIFICATION_SCORER_PLAYER_NOT_IN_SQUAD,
            target_type=SYNC_TARGET_MATCH_RESULT,
            target_id=target_id,
        )
    if target_type == GENAI_TARGET_STRIKER_PICK:
        resolve_admin_sync_notification(
            conn,
            notification_type=SYNC_NOTIFICATION_STRIKER_PICK_NOT_IN_SQUAD,
            target_type=SYNC_TARGET_STRIKER_PICK,
            target_id=target_id,
        )


def publish_player_genai_link(
    conn: Any,
    job_input: dict[str, Any],
    output: Any,
) -> dict[str, Any]:
    target_type = job_input["target_type"]
    target_id = job_input["target_id"]
    validation = validate_player_genai_output(output, job_input)
    if not validation["accepted"]:
        result_id = record_genai_job_result(
            conn,
            job_type=GENAI_JOB_PLAYER_MATCH,
            target_type=target_type,
            target_id=target_id,
            status=GENAI_STATUS_REJECTED,
            input_payload=job_input,
            failure_code=validation["failure_code"],
            failure_message=validation["failure_message"],
        )
        create_genai_failure_notification(
            conn,
            job_type=GENAI_JOB_PLAYER_MATCH,
            target_type=target_type,
            target_id=target_id,
            failure_code=validation["failure_code"],
            title="Player GenAI match needs review",
            body=validation["failure_message"],
            related_attempt_id=result_id,
        )
        return validation

    result_id = record_genai_job_result(
        conn,
        job_type=GENAI_JOB_PLAYER_MATCH,
        target_type=target_type,
        target_id=target_id,
        status=GENAI_STATUS_ACCEPTED,
        input_payload=job_input,
        accepted_output={"matched_candidate_id": validation["matched_candidate"]["candidate_id"]},
        evidence=validation["evidence"],
    )
    store_player_candidate_link(
        conn,
        job_input=job_input,
        job_result_id=result_id,
        candidate=validation["matched_candidate"],
        evidence=validation["evidence"],
    )
    for failure_code in (
        "invalid_output",
        "ambiguous",
        "no_match",
        "unsupported_status",
        "low_confidence",
        "candidate_outside_shortlist",
        "missing_evidence",
        "invalid_evidence",
        "unsupported_evidence",
    ):
        resolve_genai_failure_notification(
            conn,
            job_type=GENAI_JOB_PLAYER_MATCH,
            target_type=target_type,
            target_id=target_id,
            failure_code=failure_code,
        )
    resolve_player_match_notifications(conn, target_type, target_id)
    validation["job_result_id"] = result_id
    return validation


def record_genai_provider_failure(
    conn: Any,
    *,
    job_type: str,
    target_type: str,
    target_id: str,
    failure_code: str,
    failure_message: str,
    input_payload: dict[str, Any] | None = None,
) -> int | None:
    result_id = record_genai_job_result(
        conn,
        job_type=job_type,
        target_type=target_type,
        target_id=target_id,
        status=GENAI_STATUS_FAILED,
        input_payload=input_payload,
        failure_code=failure_code,
        failure_message=failure_message,
    )
    create_genai_failure_notification(
        conn,
        job_type=job_type,
        target_type=target_type,
        target_id=target_id,
        failure_code=failure_code,
        title="GenAI job failed",
        body=failure_message,
        severity="warning",
        related_attempt_id=result_id,
    )
    return result_id


def notification_target_id(*parts: Any) -> str:
    return ":".join(compact_name(part).replace(" ", "-") for part in parts if compact_name(part))


def scorer_player_rows_for_verification(conn: Any) -> list[dict[str, Any]]:
    event_rows = execute(
        conn,
        """
        SELECT match_id, local_team_id, api_player_id, player_name, 'event' AS source
        FROM match_events
        WHERE LOWER(event_type) = 'goal'
          AND LOWER(COALESCE(detail, '')) NOT LIKE ?
          AND LOWER(COALESCE(comments, '')) NOT LIKE ?
          AND COALESCE(TRIM(player_name), '') <> ''
        """,
        ("%own goal%", "%own goal%"),
    ).fetchall()
    stat_rows = execute(
        conn,
        """
        SELECT match_id, local_team_id, api_player_id, player_name, 'stat' AS source
        FROM player_match_stats
        WHERE goals > 0
          AND COALESCE(TRIM(player_name), '') <> ''
        """,
    ).fetchall()
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, Any]] = []
    for row in [*event_rows, *stat_rows]:
        key = (str(row["match_id"]), normalized_player_name(row["player_name"]))
        if key in seen:
            continue
        seen.add(key)
        rows.append(json_ready(row))
    return rows


def verify_player_database_matches(conn: Any) -> dict[str, int]:
    (
        squad_api_ids,
        squad_names,
        squad_initial_surname_keys,
        squad_single_token_keys,
    ) = squad_player_database(conn)
    invalid_targets: set[tuple[str, str, str]] = set()
    invalid_strikers = 0
    invalid_scorers = 0

    striker_rows = execute(
        conn,
        """
        SELECT users.id AS user_id, users.name AS user_name, users.email,
               top_scorer_predictions.striker_name_1,
               top_scorer_predictions.striker_name_2,
               top_scorer_predictions.striker_name_3,
               top_scorer_predictions.striker_name_4,
               top_scorer_predictions.striker_name_5
        FROM top_scorer_predictions
        JOIN users ON users.id = top_scorer_predictions.user_id
        """,
    ).fetchall()
    for row in striker_rows:
        for player_name in striker_pick_names(row):
            if player_matches_squad_database(
                api_player_id=None,
                player_name=player_name,
                squad_api_ids=squad_api_ids,
                squad_names=squad_names,
                squad_initial_surname_keys=squad_initial_surname_keys,
                squad_single_token_keys=squad_single_token_keys,
            ):
                continue
            target_id = notification_target_id(row["user_id"], player_name)
            if not target_id:
                continue
            if accepted_player_candidate_link_exists(
                conn,
                target_type=GENAI_TARGET_STRIKER_PICK,
                target_id=target_id,
            ):
                continue
            invalid_targets.add(
                (SYNC_NOTIFICATION_STRIKER_PICK_NOT_IN_SQUAD, SYNC_TARGET_STRIKER_PICK, target_id)
            )
            invalid_strikers += 1
            create_admin_sync_notification(
                conn,
                notification_type=SYNC_NOTIFICATION_STRIKER_PICK_NOT_IN_SQUAD,
                target_type=SYNC_TARGET_STRIKER_PICK,
                target_id=target_id,
                title="Striker pick is not in the player database",
                body=(
                    f"{row['user_name']} picked '{player_name}' as a striker, but that "
                    "name does not match any player in the synced squad database."
                ),
            )

    for row in scorer_player_rows_for_verification(conn):
        if player_matches_squad_database(
            api_player_id=row.get("api_player_id"),
            player_name=row.get("player_name"),
            squad_api_ids=squad_api_ids,
            squad_names=squad_names,
            squad_initial_surname_keys=squad_initial_surname_keys,
            squad_single_token_keys=squad_single_token_keys,
        ):
            continue
        target_id = notification_target_id(row.get("match_id"), row.get("player_name"))
        if not target_id:
            continue
        if accepted_player_candidate_link_exists(
            conn,
            target_type=GENAI_TARGET_MATCH_SCORER,
            target_id=target_id,
        ):
            continue
        invalid_targets.add(
            (
                SYNC_NOTIFICATION_SCORER_PLAYER_NOT_IN_SQUAD,
                SYNC_TARGET_MATCH_RESULT,
                target_id,
            )
        )
        invalid_scorers += 1
        create_admin_sync_notification(
            conn,
            notification_type=SYNC_NOTIFICATION_SCORER_PLAYER_NOT_IN_SQUAD,
            target_type=SYNC_TARGET_MATCH_RESULT,
            target_id=target_id,
            title="Goal scorer is not in the player database",
            body=(
                f"Match {row.get('match_id')} has scorer '{row.get('player_name')}', "
                "but that name/id does not match any player in the synced squad database."
            ),
        )

    active_rows = execute(
        conn,
        """
        SELECT type, target_type, target_id
        FROM admin_sync_notifications
        WHERE is_active = 1
          AND type IN (?, ?)
        """,
        (
            SYNC_NOTIFICATION_SCORER_PLAYER_NOT_IN_SQUAD,
            SYNC_NOTIFICATION_STRIKER_PICK_NOT_IN_SQUAD,
        ),
    ).fetchall()
    for row in active_rows:
        key = (row["type"], row["target_type"], row["target_id"])
        if key in invalid_targets:
            continue
        resolve_admin_sync_notification(
            conn,
            notification_type=row["type"],
            target_type=row["target_type"],
            target_id=row["target_id"],
        )

    return {
        "invalid_striker_picks": invalid_strikers,
        "invalid_goal_scorers": invalid_scorers,
    }


def quiz_auto_label_current_for_input(
    conn: Any,
    *,
    match_id: str,
    job_input: dict[str, Any],
) -> bool:
    row = execute(
        conn,
        """
        SELECT qal.facts_revision_key, gjr.status
        FROM quiz_auto_labels qal
        LEFT JOIN genai_job_results gjr ON gjr.id = qal.job_result_id
        WHERE qal.match_id = ?
        """,
        (match_id,),
    ).fetchone()
    return bool(
        row
        and row["status"] == GENAI_STATUS_ACCEPTED
        and row["facts_revision_key"] == genai_input_hash(job_input.get("facts"))
    )


def synced_match_ids_from_result_sync(result_sync: dict[str, Any]) -> list[str]:
    match_ids: list[str] = []
    for item in result_sync.get("synced") or []:
        if isinstance(item, dict) and clean_text(item.get("match_id")):
            match_ids.append(clean_text(item.get("match_id")))
    for child in result_sync.get("results") or []:
        if isinstance(child, dict):
            match_ids.extend(synced_match_ids_from_result_sync(child))
    seen: set[str] = set()
    unique_match_ids: list[str] = []
    for match_id in match_ids:
        if match_id in seen:
            continue
        seen.add(match_id)
        unique_match_ids.append(match_id)
    return unique_match_ids


def quiz_has_static_or_persisted_label(conn: Any, match: dict[str, Any]) -> bool:
    quiz = match.get("quiz") if isinstance(match, dict) else None
    if not isinstance(quiz, dict):
        return True
    if quiz.get("correct_answers") or quiz.get("correct_answer") is not None:
        return True
    match_id = clean_text(match.get("id"))
    override = execute(
        conn,
        "SELECT correct_answers_json FROM quiz_label_overrides WHERE match_id = ?",
        (match_id,),
    ).fetchone()
    if override is not None and parse_correct_answers_json(override["correct_answers_json"]):
        return True
    auto_label = execute(
        conn,
        "SELECT correct_answers_json FROM quiz_auto_labels WHERE match_id = ?",
        (match_id,),
    ).fetchone()
    return bool(auto_label and parse_correct_answers_json(auto_label["correct_answers_json"]))


def manual_quiz_fill_requests(
    conn: Any,
    data: dict[str, Any],
    match_ids: list[str],
) -> list[dict[str, Any]]:
    matches_by_id = {clean_text(match.get("id")): match for match in data.get("matches", [])}
    requests: list[dict[str, Any]] = []
    for match_id in match_ids:
        match = matches_by_id.get(match_id)
        quiz = match.get("quiz") if isinstance(match, dict) else None
        if not isinstance(match, dict) or not isinstance(quiz, dict):
            continue
        facts = quiz_genai_fact_payload(conn, match_id)
        if not quiz_genai_has_supplied_facts({"facts": facts}):
            continue
        if quiz_has_static_or_persisted_label(conn, match):
            continue
        requests.append(
            {
                "match_id": match_id,
                "match_number": match.get("match_number"),
                "home_team_id": match.get("home_team_id"),
                "away_team_id": match.get("away_team_id"),
                "home_team_name": match.get("home_team"),
                "away_team_name": match.get("away_team"),
                "question": clean_text(quiz.get("question")),
                "type": clean_text(quiz.get("type")),
                "choices": quiz_answer_options(quiz),
                "viewership_required": bool(quiz.get("viewership")),
                "reason": "manual_quiz_label_required",
            }
        )
    return requests


def run_quiz_genai_job_for_match(
    conn: Any,
    data: dict[str, Any],
    match: dict[str, Any],
) -> dict[str, Any]:
    match_id = clean_text(match.get("id"))
    try:
        job_input = build_quiz_genai_input(conn, match)
    except ValueError as error:
        result_id = record_genai_provider_failure(
            conn,
            job_type=GENAI_JOB_QUIZ_ANSWER,
            target_type=GENAI_TARGET_MATCH_QUIZ,
            target_id=match_id,
            failure_code="invalid_input",
            failure_message=str(error),
        )
        return {
            "job_type": GENAI_JOB_QUIZ_ANSWER,
            "target_type": GENAI_TARGET_MATCH_QUIZ,
            "target_id": match_id,
            "accepted": False,
            "failure_code": "invalid_input",
            "job_result_id": result_id,
        }
    if quiz_auto_label_current_for_input(conn, match_id=match_id, job_input=job_input):
        return {
            "job_type": GENAI_JOB_QUIZ_ANSWER,
            "target_type": GENAI_TARGET_MATCH_QUIZ,
            "target_id": match_id,
            "skipped": True,
            "reason": "current_auto_label_exists",
        }
    if not quiz_genai_has_supplied_facts(job_input):
        validation = publish_quiz_genai_label(
            conn,
            data,
            match,
            {"choice": "", "confidence": 0, "reason": "No match facts are available."},
            job_input,
        )
    else:
        try:
            output = run_genai_structured_completion(messages=quiz_genai_prompt_messages(job_input))
        except GenAIProviderError as error:
            result_id = record_genai_provider_failure(
                conn,
                job_type=GENAI_JOB_QUIZ_ANSWER,
                target_type=GENAI_TARGET_MATCH_QUIZ,
                target_id=match_id,
                failure_code=str(error),
                failure_message=f"Quiz GenAI provider failed: {error}",
                input_payload=job_input,
            )
            return {
                "job_type": GENAI_JOB_QUIZ_ANSWER,
                "target_type": GENAI_TARGET_MATCH_QUIZ,
                "target_id": match_id,
                "accepted": False,
                "failure_code": str(error),
                "job_result_id": result_id,
            }
        validation = publish_quiz_genai_label(conn, data, match, output, job_input)
    result = {
        "job_type": GENAI_JOB_QUIZ_ANSWER,
        "target_type": GENAI_TARGET_MATCH_QUIZ,
        "target_id": match_id,
        **json_ready(validation),
    }
    if validation.get("accepted") and validation.get("job_result_id"):
        result["review"] = quiz_genai_review_payload(
            conn,
            match=match,
            job_result_id=int(validation["job_result_id"]),
        )
    return result


def unmatched_player_genai_inputs(conn: Any) -> list[dict[str, Any]]:
    (
        squad_api_ids,
        squad_names,
        squad_initial_surname_keys,
        squad_single_token_keys,
    ) = squad_player_database(conn)
    job_inputs: list[dict[str, Any]] = []
    striker_rows = execute(
        conn,
        """
        SELECT users.id AS user_id,
               top_scorer_predictions.striker_name_1,
               top_scorer_predictions.striker_name_2,
               top_scorer_predictions.striker_name_3,
               top_scorer_predictions.striker_name_4,
               top_scorer_predictions.striker_name_5
        FROM top_scorer_predictions
        JOIN users ON users.id = top_scorer_predictions.user_id
        """,
    ).fetchall()
    seen: set[tuple[str, str]] = set()
    for row in striker_rows:
        for player_name in striker_pick_names(row):
            if not player_genai_should_run(
                api_player_id=None,
                player_name=player_name,
                squad_api_ids=squad_api_ids,
                squad_names=squad_names,
                squad_initial_surname_keys=squad_initial_surname_keys,
                squad_single_token_keys=squad_single_token_keys,
            ):
                continue
            target_id = notification_target_id(row["user_id"], player_name)
            key = (GENAI_TARGET_STRIKER_PICK, target_id)
            if not target_id or key in seen:
                continue
            seen.add(key)
            if accepted_player_candidate_link_exists(
                conn,
                target_type=GENAI_TARGET_STRIKER_PICK,
                target_id=target_id,
            ):
                continue
            job_inputs.append(
                build_player_genai_input(
                    conn,
                    target_type=GENAI_TARGET_STRIKER_PICK,
                    target_id=target_id,
                    raw_player_name=player_name,
                )
            )

    for row in scorer_player_rows_for_verification(conn):
        if not player_genai_should_run(
            api_player_id=row.get("api_player_id"),
            player_name=row.get("player_name"),
            squad_api_ids=squad_api_ids,
            squad_names=squad_names,
            squad_initial_surname_keys=squad_initial_surname_keys,
            squad_single_token_keys=squad_single_token_keys,
        ):
            continue
        target_id = notification_target_id(row.get("match_id"), row.get("player_name"))
        key = (GENAI_TARGET_MATCH_SCORER, target_id)
        if not target_id or key in seen:
            continue
        seen.add(key)
        if accepted_player_candidate_link_exists(
            conn,
            target_type=GENAI_TARGET_MATCH_SCORER,
            target_id=target_id,
        ):
            continue
        job_inputs.append(
            build_player_genai_input(
                conn,
                target_type=GENAI_TARGET_MATCH_SCORER,
                target_id=target_id,
                raw_player_name=clean_text(row.get("player_name")),
                match_id=clean_text(row.get("match_id")),
                local_team_id=clean_text(row.get("local_team_id")),
            )
        )
    return job_inputs


def run_player_genai_job(conn: Any, job_input: dict[str, Any]) -> dict[str, Any]:
    target_type = job_input["target_type"]
    target_id = job_input["target_id"]
    if accepted_player_candidate_link_exists(conn, target_type=target_type, target_id=target_id):
        return {
            "job_type": GENAI_JOB_PLAYER_MATCH,
            "target_type": target_type,
            "target_id": target_id,
            "skipped": True,
            "reason": "accepted_player_link_exists",
        }
    if not job_input.get("candidates"):
        validation = publish_player_genai_link(
            conn,
            job_input,
            {
                "status": "no_match",
                "matched_candidate_id": "",
                "confidence": "low",
                "evidence": [],
                "reason": "No squad candidates are available.",
            },
        )
    else:
        try:
            output = run_genai_structured_completion(
                messages=player_genai_prompt_messages(job_input)
            )
        except GenAIProviderError as error:
            result_id = record_genai_provider_failure(
                conn,
                job_type=GENAI_JOB_PLAYER_MATCH,
                target_type=target_type,
                target_id=target_id,
                failure_code=str(error),
                failure_message=f"Player GenAI provider failed: {error}",
                input_payload=job_input,
            )
            return {
                "job_type": GENAI_JOB_PLAYER_MATCH,
                "target_type": target_type,
                "target_id": target_id,
                "accepted": False,
                "failure_code": str(error),
                "job_result_id": result_id,
            }
        validation = publish_player_genai_link(conn, job_input, output)
    return {
        "job_type": GENAI_JOB_PLAYER_MATCH,
        "target_type": target_type,
        "target_id": target_id,
        **json_ready(validation),
    }


def run_genai_jobs_after_data_sync(
    data: dict[str, Any],
    *,
    result_sync: dict[str, Any] | None = None,
) -> dict[str, Any]:
    quiz_results: list[dict[str, Any]] = []
    player_results: list[dict[str, Any]] = []
    synced_match_ids = synced_match_ids_from_result_sync(result_sync or {})
    matches_by_id = {clean_text(match.get("id")): match for match in data.get("matches", [])}
    manual_fill_match_ids = [clean_text(match.get("id")) for match in data.get("matches", [])]
    with get_db() as conn:
        for match_id in synced_match_ids:
            match = matches_by_id.get(match_id)
            if match is None or not isinstance(match.get("quiz"), dict):
                continue
            quiz_results.append(run_quiz_genai_job_for_match(conn, data, match))
        for job_input in unmatched_player_genai_inputs(conn):
            player_results.append(run_player_genai_job(conn, job_input))
        manual_fills = manual_quiz_fill_requests(conn, data, manual_fill_match_ids)
        conn.commit()
    return {
        "ok": True,
        "quiz_jobs": quiz_results,
        "player_jobs": player_results,
        "manual_quiz_fills": manual_fills,
        "accepted": sum(
            1 for item in [*quiz_results, *player_results] if item.get("accepted") is True
        ),
        "failed": sum(
            1 for item in [*quiz_results, *player_results] if item.get("accepted") is False
        ),
        "skipped": sum(1 for item in [*quiz_results, *player_results] if item.get("skipped")),
    }
