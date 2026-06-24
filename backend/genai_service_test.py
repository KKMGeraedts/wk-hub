from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from backend import genai_service


class StructuredCompletionFake:
    def __init__(self, output: dict[str, Any]) -> None:
        self.output = output
        self.messages: list[list[dict[str, str]]] = []

    def __call__(self, *, messages: list[dict[str, str]]) -> dict[str, Any]:
        self.messages.append(messages)
        return self.output


class GenAIServiceModuleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_runtime = {
            name: getattr(genai_service, name) for name in genai_service._RUNTIME_DEPENDENCIES
        }
        self.original_team_profiles_path = genai_service.TEAM_PROFILES_PATH
        self.original_using_postgres = genai_service.USING_POSTGRES
        self.original_completion = genai_service._structured_completion_override
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "genai.db"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE genai_job_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                provider_key TEXT,
                model TEXT,
                status TEXT NOT NULL,
                failure_code TEXT,
                failure_message TEXT,
                accepted_output_json TEXT,
                evidence_json TEXT,
                input_hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE admin_sync_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                severity TEXT NOT NULL,
                related_attempt_id INTEGER,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                resolved_at TEXT
            )
            """
        )
        completion = StructuredCompletionFake({"status": "ok"})
        genai_service.configure(
            team_profiles_path=Path(self.temp_dir.name) / "profiles.json",
            using_postgres=False,
            structured_completion=completion,
            get_db=lambda: self.conn,
            label_audit=lambda *_args, **_kwargs: None,
            recompute_all_computed_points=lambda _data: None,
        )
        self.completion = completion

    def tearDown(self) -> None:
        genai_service.__dict__.update(self.original_runtime)
        genai_service.TEAM_PROFILES_PATH = self.original_team_profiles_path
        genai_service.USING_POSTGRES = self.original_using_postgres
        genai_service._structured_completion_override = self.original_completion
        self.conn.close()
        self.temp_dir.cleanup()

    def test_public_interface_is_workflow_level(self) -> None:
        self.assertEqual(
            set(genai_service.__all__),
            {
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
            },
        )

    def test_module_does_not_import_flask_app(self) -> None:
        self.assertNotIn("backend.app", genai_service.__dict__.get("__name__", ""))

    def test_disabled_config_and_injected_completion(self) -> None:
        with patch.dict(
            genai_service.os.environ,
            {"GENAI_PROVIDER": "mistral", "GENAI_MODEL": "test-model"},
            clear=True,
        ):
            config = genai_service.genai_config()
        self.assertFalse(config["enabled"])
        self.assertEqual(config["disabled_reason"], "missing_mistral_api_key")

        result = genai_service.run_genai_structured_completion(
            messages=[{"role": "user", "content": "bounded input"}]
        )
        self.assertEqual(result, {"status": "ok"})
        self.assertEqual(self.completion.messages[0][0]["content"], "bounded input")

    def test_job_result_storage_is_compact(self) -> None:
        result_id = genai_service.record_genai_job_result(
            self.conn,
            job_type=genai_service.GENAI_JOB_QUIZ_ANSWER,
            target_type=genai_service.GENAI_TARGET_MATCH_QUIZ,
            target_id="m001",
            status=genai_service.GENAI_STATUS_REJECTED,
            input_payload={"prompt": "must not be stored"},
            accepted_output={"selected_answers": ["yes"]},
            failure_code="low_confidence",
        )
        row = genai_service.genai_job_result_by_id(self.conn, result_id)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertIsNotNone(row["input_hash"])
        self.assertNotIn("must not be stored", str(dict(row)))
        self.assertNotIn("prompt", row.keys())

    def test_quiz_validation_accepts_only_supplied_choices_and_facts(self) -> None:
        job_input = {
            "question": "Who wins?",
            "choices": ["Netherlands", "USA"],
            "match_data": {"result": {"id": "m001"}},
        }
        accepted = genai_service.validate_quiz_genai_output(
            {"choice": "Netherlands", "confidence": 0.9, "reason": "Result fact."},
            job_input,
        )
        rejected = genai_service.validate_quiz_genai_output(
            {"choice": "Germany", "confidence": 0.9, "reason": "Unsupported."},
            job_input,
        )
        self.assertTrue(accepted["accepted"])
        self.assertEqual(accepted["correct_answers"], ["Netherlands"])
        self.assertFalse(rejected["accepted"])
        self.assertEqual(rejected["failure_code"], "answer_outside_options")

    def test_player_validation_constrains_matches_to_candidates(self) -> None:
        job_input = {
            "candidates": [
                {
                    "candidate_id": "ned:1",
                    "player_name": "Cody Gakpo",
                    "local_team_id": "ned",
                }
            ]
        }
        accepted = genai_service.validate_player_genai_output(
            {
                "status": "matched",
                "matched_candidate_id": "ned:1",
                "confidence": "high",
                "evidence": [{"type": "candidate", "id": "ned:1"}],
            },
            job_input,
        )
        rejected = genai_service.validate_player_genai_output(
            {
                "status": "matched",
                "matched_candidate_id": "ned:2",
                "confidence": "high",
                "evidence": [{"type": "candidate", "id": "ned:2"}],
            },
            job_input,
        )
        self.assertTrue(accepted["accepted"])
        self.assertEqual(accepted["matched_candidate"]["player_name"], "Cody Gakpo")
        self.assertFalse(rejected["accepted"])
        self.assertEqual(rejected["failure_code"], "candidate_outside_shortlist")

    def test_failure_notifications_deduplicate_and_resolve(self) -> None:
        kwargs = {
            "job_type": genai_service.GENAI_JOB_QUIZ_ANSWER,
            "target_type": genai_service.GENAI_TARGET_MATCH_QUIZ,
            "target_id": "m001",
            "failure_code": "low_confidence",
            "title": "Quiz unresolved",
            "body": "The answer was not safe.",
        }
        for _ in range(2):
            genai_service.create_genai_failure_notification(
                self.conn,
                job_type=kwargs["job_type"],
                target_type=kwargs["target_type"],
                target_id=kwargs["target_id"],
                failure_code=kwargs["failure_code"],
                title=kwargs["title"],
                body=kwargs["body"],
            )
        count = self.conn.execute(
            "SELECT COUNT(*) FROM admin_sync_notifications WHERE is_active = 1"
        ).fetchone()[0]
        self.assertEqual(count, 1)
        genai_service.resolve_genai_failure_notification(
            self.conn,
            job_type=kwargs["job_type"],
            target_type=kwargs["target_type"],
            target_id=kwargs["target_id"],
            failure_code=kwargs["failure_code"],
        )
        active = self.conn.execute(
            "SELECT COUNT(*) FROM admin_sync_notifications WHERE is_active = 1"
        ).fetchone()[0]
        self.assertEqual(active, 0)


if __name__ == "__main__":
    unittest.main()
