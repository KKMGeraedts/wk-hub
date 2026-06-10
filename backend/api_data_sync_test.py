from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from backend import app as wk_app


def make_match(
    match_id: str,
    kickoff: datetime,
    home_team_id: str = "ned",
    away_team_id: str = "usa",
) -> dict[str, object]:
    return {
        "id": match_id,
        "round": "Group Stage",
        "group": "A",
        "date": kickoff.date().isoformat(),
        "time_utc": kickoff.strftime("%H:%M"),
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
    }


class ApiDataSyncSchedulingTest(unittest.TestCase):
    def run_with_temp_db(self, callback):
        old_db_path = wk_app.DB_PATH
        old_init_done = wk_app.DB_INIT_DONE
        old_init_error = wk_app.DB_INIT_ERROR
        with tempfile.TemporaryDirectory() as tmpdir:
            wk_app.DB_PATH = Path(tmpdir) / "pool.db"
            wk_app.DB_INIT_DONE = False
            wk_app.DB_INIT_ERROR = None
            try:
                wk_app.init_db()
                with wk_app.get_db() as conn:
                    return callback(conn)
            finally:
                wk_app.DB_PATH = old_db_path
                wk_app.DB_INIT_DONE = old_init_done
                wk_app.DB_INIT_ERROR = old_init_error

    def test_test_harness_imports_backend_app(self) -> None:
        self.assertEqual(wk_app.API_FOOTBALL_PROVIDER_KEY, "api-football")

    def test_match_factory_uses_utc_kickoff(self) -> None:
        kickoff = datetime(2026, 6, 11, 18, 0, tzinfo=UTC)
        match = make_match("m001", kickoff)

        self.assertEqual(match["id"], "m001")
        self.assertEqual(match["date"], "2026-06-11")
        self.assertEqual(match["time_utc"], "18:00")

    def test_timedelta_import_available_for_sync_windows(self) -> None:
        self.assertEqual(timedelta(minutes=15).total_seconds(), 900)

    def test_first_post_match_attempt_is_due_after_first_window(self) -> None:
        kickoff = datetime(2026, 6, 11, 18, 0, tzinfo=UTC)
        match = make_match("m001", kickoff)

        due = wk_app.due_result_sync_attempt_kinds(
            match,
            now=kickoff + wk_app.RESULT_SYNC_FIRST_AFTER,
            terminal_attempt_kinds=set(),
        )

        self.assertEqual(due, [wk_app.SYNC_ATTEMPT_FIRST_POST_MATCH])

    def test_second_post_match_attempt_waits_for_first_terminal_attempt(self) -> None:
        kickoff = datetime(2026, 6, 11, 18, 0, tzinfo=UTC)
        match = make_match("m001", kickoff)

        due_without_first = wk_app.due_result_sync_attempt_kinds(
            match,
            now=kickoff + wk_app.RESULT_SYNC_SECOND_AFTER,
            terminal_attempt_kinds=set(),
        )
        due_with_first = wk_app.due_result_sync_attempt_kinds(
            match,
            now=kickoff + wk_app.RESULT_SYNC_SECOND_AFTER,
            terminal_attempt_kinds={wk_app.SYNC_ATTEMPT_FIRST_POST_MATCH},
        )

        self.assertEqual(due_without_first, [wk_app.SYNC_ATTEMPT_FIRST_POST_MATCH])
        self.assertEqual(due_with_first, [wk_app.SYNC_ATTEMPT_SECOND_POST_MATCH])

    def test_no_attempt_due_before_first_window_or_after_both_terminal(self) -> None:
        kickoff = datetime(2026, 6, 11, 18, 0, tzinfo=UTC)
        match = make_match("m001", kickoff)

        early = wk_app.due_result_sync_attempt_kinds(
            match,
            now=kickoff + timedelta(minutes=14),
            terminal_attempt_kinds=set(),
        )
        complete = wk_app.due_result_sync_attempt_kinds(
            match,
            now=kickoff + timedelta(hours=3),
            terminal_attempt_kinds={
                wk_app.SYNC_ATTEMPT_FIRST_POST_MATCH,
                wk_app.SYNC_ATTEMPT_SECOND_POST_MATCH,
            },
        )

        self.assertEqual(early, [])
        self.assertEqual(complete, [])

    def test_admin_sync_dry_run_accepts_match_id_without_provider_key(self) -> None:
        previous_token = wk_app.API_FOOTBALL_SYNC_TOKEN
        previous_key = wk_app.API_FOOTBALL_KEY
        wk_app.API_FOOTBALL_SYNC_TOKEN = "test-token"
        wk_app.API_FOOTBALL_KEY = ""
        kickoff = datetime.now(UTC) - timedelta(hours=3)
        data = {
            "matches": [make_match("m001", kickoff)],
            "teams": [
                {"id": "ned", "name": "Netherlands", "code": "NED"},
                {"id": "usa", "name": "United States", "code": "USA"},
            ],
            "groups": [],
            "venues": [],
            "meta": {},
        }
        try:
            with (
                patch.object(wk_app, "load_world_cup_data", return_value=data),
                patch.object(wk_app, "api_football_fixture_links", return_value={"m001": 123}),
            ):
                response = wk_app.app.test_client().post(
                    "/api/admin/api-football/sync",
                    json={"match_id": "m001", "dry_run": True},
                    headers={"Authorization": "Bearer test-token"},
                )
        finally:
            wk_app.API_FOOTBALL_SYNC_TOKEN = previous_token
            wk_app.API_FOOTBALL_KEY = previous_key

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["candidates"][0]["match_id"], "m001")
        self.assertEqual(payload["candidates"][0]["fixture_id"], 123)

    def test_participant_reads_do_not_call_provider_retrieval(self) -> None:
        with patch.object(wk_app, "api_football_get", side_effect=AssertionError):
            data = wk_app.load_world_cup_data()
            response = wk_app.app.test_client().get("/api/world-cup")

        self.assertIn("matches", data)
        self.assertEqual(response.status_code, 200)

    def test_fixture_snapshot_publishes_app_owned_current_result_fact(self) -> None:
        kickoff = datetime(2026, 6, 11, 18, 0, tzinfo=UTC)
        match = make_match("m001", kickoff)
        data = {
            "matches": [match],
            "teams": [
                {"id": "ned", "name": "Netherlands", "code": "NED"},
                {"id": "usa", "name": "United States", "code": "USA"},
            ],
        }
        fixture = {
            "fixture": {"id": 123, "status": {"long": "Match Finished", "short": "FT"}},
            "teams": {
                "home": {"id": 1, "name": "Netherlands"},
                "away": {"id": 2, "name": "United States"},
            },
            "goals": {"home": 2, "away": 1},
            "events": [],
            "players": [],
        }

        def scenario(conn):
            wk_app.store_api_football_fixture_snapshot(conn, match, fixture, data)
            return wk_app.execute(
                conn,
                "SELECT source, home_score, away_score FROM match_results WHERE match_id = ?",
                ("m001",),
            ).fetchone()

        row = self.run_with_temp_db(scenario)

        self.assertIsNotNone(row)
        self.assertEqual(row["source"], wk_app.API_FOOTBALL_PROVIDER_KEY)
        self.assertEqual(row["home_score"], 2)
        self.assertEqual(row["away_score"], 1)

    def test_fixture_snapshot_history_is_permanent_and_provider_facts_update(self) -> None:
        kickoff = datetime(2026, 6, 11, 18, 0, tzinfo=UTC)
        match = make_match("m001", kickoff)
        data = {"matches": [match], "teams": []}
        first = {
            "fixture": {"id": 123, "status": {"long": "Finished", "short": "FT"}},
            "teams": {"home": {"id": 1}, "away": {"id": 2}},
            "goals": {"home": 2, "away": 1},
            "events": [],
            "players": [],
        }
        second = {**first, "goals": {"home": 3, "away": 1}}

        def scenario(conn):
            wk_app.store_api_football_fixture_snapshot(conn, match, first, data)
            wk_app.store_api_football_fixture_snapshot(conn, match, second, data)
            history = wk_app.execute(
                conn,
                "SELECT COUNT(*) AS count FROM api_football_fixture_snapshot_history",
            ).fetchone()["count"]
            result = wk_app.execute(
                conn,
                "SELECT home_score, away_score FROM match_results WHERE match_id = ?",
                ("m001",),
            ).fetchone()
            return history, result

        history, result = self.run_with_temp_db(scenario)

        self.assertEqual(history, 2)
        self.assertEqual(result["home_score"], 3)
        self.assertEqual(result["away_score"], 1)

    def test_manual_result_wins_until_reverted_to_provider_snapshot(self) -> None:
        kickoff = datetime(2026, 6, 11, 18, 0, tzinfo=UTC)
        match = make_match("m001", kickoff)
        data = {"matches": [match], "teams": []}
        fixture = {
            "fixture": {"id": 123, "status": {"long": "Finished", "short": "FT"}},
            "teams": {"home": {"id": 1}, "away": {"id": 2}},
            "goals": {"home": 2, "away": 1},
            "events": [],
            "players": [],
        }
        corrected = {**fixture, "goals": {"home": 4, "away": 1}}

        def scenario(conn):
            wk_app.store_api_football_fixture_snapshot(conn, match, fixture, data)
            wk_app.execute(
                conn,
                """
                UPDATE match_results
                SET source = 'manual', home_score = 9, away_score = 9
                WHERE match_id = ?
                """,
                ("m001",),
            )
            wk_app.store_api_football_fixture_snapshot(conn, match, corrected, data)
            manual = wk_app.execute(
                conn,
                "SELECT source, home_score FROM match_results WHERE match_id = ?",
                ("m001",),
            ).fetchone()
            wk_app.restore_provider_facts_from_latest_snapshot(
                conn, match_id="m001", data=data, clear_result=True
            )
            restored = wk_app.execute(
                conn,
                "SELECT source, home_score FROM match_results WHERE match_id = ?",
                ("m001",),
            ).fetchone()
            return manual, restored

        manual, restored = self.run_with_temp_db(scenario)

        self.assertEqual(manual["source"], "manual")
        self.assertEqual(manual["home_score"], 9)
        self.assertEqual(restored["source"], wk_app.API_FOOTBALL_PROVIDER_KEY)
        self.assertEqual(restored["home_score"], 4)

    def test_manual_event_and_stat_rows_are_not_overwritten_by_provider(self) -> None:
        kickoff = datetime(2026, 6, 11, 18, 0, tzinfo=UTC)
        match = make_match("m001", kickoff)
        data = {"matches": [match], "teams": []}
        fixture = {
            "fixture": {"id": 123, "status": {"long": "Finished", "short": "FT"}},
            "teams": {"home": {"id": 1}, "away": {"id": 2}},
            "goals": {"home": 1, "away": 0},
            "events": [{"time": {"elapsed": 10}, "player": {"name": "Provider"}, "type": "Goal"}],
            "players": [
                {
                    "team": {"id": 1, "name": "Netherlands"},
                    "players": [
                        {
                            "player": {"id": 7, "name": "Provider"},
                            "statistics": [{"games": {"minutes": 90}, "goals": {"total": 1}}],
                        }
                    ],
                }
            ],
        }

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, event_type, player_name, raw_json
                )
                VALUES (?, ?, 'Goal', 'Manual', '{}')
                """,
                ("m001", "manual:m001:1"),
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO player_match_stats (
                    match_id, provider_player_key, player_name, goals, raw_json
                )
                VALUES (?, ?, 'Manual', 2, '{}')
                """,
                ("m001", "manual:m001:1"),
            )
            wk_app.store_api_football_fixture_snapshot(conn, match, fixture, data)
            event = wk_app.execute(
                conn,
                "SELECT player_name FROM match_events WHERE match_id = ?",
                ("m001",),
            ).fetchone()
            stat = wk_app.execute(
                conn,
                "SELECT player_name, goals FROM player_match_stats WHERE match_id = ?",
                ("m001",),
            ).fetchone()
            return event, stat

        event, stat = self.run_with_temp_db(scenario)

        self.assertEqual(event["player_name"], "Manual")
        self.assertEqual(stat["player_name"], "Manual")
        self.assertEqual(stat["goals"], 2)

    def test_label_audit_includes_source_and_reason_metadata(self) -> None:
        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES (1, 'Admin', 'admin.user@talpanetwork.com', 'x', 1)
                """,
            )
            wk_app.label_audit(
                conn,
                1,
                "result_revert",
                "m001",
                {"home_score": 9},
                {"home_score": 2},
                source="reverted",
                reason="Provider data corrected",
            )
            return wk_app.execute(
                conn,
                "SELECT before_json, after_json FROM label_audit_log",
            ).fetchone()

        row = self.run_with_temp_db(scenario)
        after = json.loads(row["after_json"])

        self.assertEqual(after["source"], "reverted")
        self.assertEqual(after["reason"], "Provider data corrected")

    def scoring_data(self, done: bool = True) -> dict[str, object]:
        kickoff = datetime.now(UTC) - timedelta(hours=3)
        match = make_match("m001", kickoff)
        if done:
            match["status"] = "completed"
            match["home_score"] = 2
            match["away_score"] = 1
        match["quiz"] = {
            "question": "Who wins?",
            "type": "multiple_choice",
            "choices": ["Netherlands", "USA"],
            "correct_answers": ["Netherlands"],
        }
        return {
            "matches": [match],
            "teams": [
                {"id": "ned", "name": "Netherlands", "code": "NED"},
                {"id": "usa", "name": "United States", "code": "USA"},
            ],
            "groups": [{"id": "A", "teams": ["ned", "usa"]}],
            "venues": [],
            "meta": {"world_cup_winner_id": "ned", "top_scorer": "Cody Gakpo"},
        }

    def seed_scoring_user(self, conn) -> None:
        wk_app.execute(
            conn,
            """
            INSERT INTO users (id, name, email, password_hash, is_admin)
            VALUES (1, 'Karel', 'karel@example.com', 'x', 0)
            """,
        )
        wk_app.execute(
            conn,
            """
            INSERT INTO match_predictions (user_id, match_id, home_score, away_score)
            VALUES (1, 'm001', 2, 1)
            """,
        )
        wk_app.execute(
            conn,
            """
            INSERT INTO quiz_predictions (user_id, match_id, answer)
            VALUES (1, 'm001', 'Netherlands')
            """,
        )
        wk_app.execute(
            conn,
            "INSERT INTO leeuwtje_predictions (user_id, match_id) VALUES (1, 'm001')",
        )
        wk_app.execute(
            conn,
            "INSERT INTO winner_predictions (user_id, team_id) VALUES (1, 'ned')",
        )
        wk_app.execute(
            conn,
            """
            INSERT INTO top_scorer_predictions (
                user_id, player_name, striker_name_1
            )
            VALUES (1, 'Cody Gakpo', 'Cody Gakpo')
            """,
        )
        wk_app.execute(
            conn,
            """
            INSERT INTO match_events (
                match_id, provider_event_key, event_type, player_name, raw_json
            )
            VALUES ('m001', 'provider:event:1', 'Goal', 'Cody Gakpo', '{}')
            """,
        )
        wk_app.execute(
            conn,
            """
            INSERT INTO player_match_stats (
                match_id, provider_player_key, player_name, goals, raw_json
            )
            VALUES ('m001', 'provider:7', 'Cody Gakpo', 3, '{}')
            """,
        )
        conn.commit()

    def test_computed_points_persist_all_scoring_categories_after_recompute(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            self.seed_scoring_user(conn)
            wk_app.recompute_all_computed_points(data)
            return wk_app.computed_point_rows(
                conn, user_id=1, scope_type="leaderboard", scope_id="current"
            )

        rows = self.run_with_temp_db(scenario)
        categories = {row["category"]: row["points"] for row in rows}

        self.assertGreater(categories["match_score_points"], 0)
        self.assertGreater(categories["quiz_points"], 0)
        self.assertGreater(categories["leeuwtje_points"], 0)
        self.assertGreater(categories["winner_points"], 0)
        self.assertGreater(categories["top_scorer_points"], 0)
        self.assertGreater(categories["striker_points"], 0)

    def test_manual_labels_do_not_score_before_match_is_done(self) -> None:
        data = self.scoring_data(done=False)

        def scenario(conn):
            self.seed_scoring_user(conn)
            wk_app.execute(
                conn,
                """
                INSERT INTO match_results (
                    match_id, source, status_long, status_short, home_score, away_score
                )
                VALUES ('m001', 'manual', 'Manual pending', 'NS', 2, 1)
                """,
            )
            return wk_app.build_leaderboard(data, use_computed_points=False)[0]

        row = self.run_with_temp_db(scenario)

        self.assertEqual(row["match_score_points"], 0)
        self.assertEqual(row["leeuwtje_points"], 0)

    def test_leaderboard_and_profile_read_stored_computed_points(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            self.seed_scoring_user(conn)
            for category, points in {
                "match_score_points": 11,
                "group_position_points": 0,
                "quiz_points": 7,
                "winner_points": 0,
                "top_scorer_points": 0,
                "striker_points": 0,
                "leeuwtje_points": 5,
            }.items():
                wk_app.upsert_computed_point(
                    conn,
                    user_id=1,
                    scope_type="leaderboard",
                    scope_id="current",
                    category=category,
                    points=points,
                )
            conn.commit()
            with patch.object(wk_app, "load_world_cup_data", return_value=data):
                leaderboard = wk_app.build_leaderboard(data, viewer_user_id=1)
                client = wk_app.app.test_client()
                with client.session_transaction() as session:
                    session["user_id"] = 1
                response = client.get("/api/profiles/1/predictions")
            return leaderboard, response.status_code, response.get_json()

        leaderboard, status_code, payload = self.run_with_temp_db(scenario)

        self.assertEqual(status_code, 200)
        self.assertEqual(leaderboard[0]["points"], 23)
        self.assertEqual(payload["leaderboard_entry"]["points"], 23)

    def test_missing_fixture_link_creates_admin_sync_notification(self) -> None:
        data = self.scoring_data(done=False)
        previous_key = wk_app.API_FOOTBALL_KEY
        wk_app.API_FOOTBALL_KEY = "test-key"
        try:
            with (
                patch.object(wk_app, "api_football_fixture_links", return_value={}),
                patch.object(wk_app, "api_football_get", side_effect=AssertionError),
            ):
                result, notifications = self.run_with_temp_db(
                    lambda conn: (
                        wk_app.run_api_football_completed_sync(data, force=True, match_id="m001"),
                        wk_app.active_admin_sync_notifications(conn),
                    )
                )
        finally:
            wk_app.API_FOOTBALL_KEY = previous_key

        self.assertTrue(result["ok"])
        self.assertEqual(result["attempts"][0]["status"], wk_app.SYNC_STATUS_SKIPPED)
        self.assertEqual(notifications[0]["type"], "missing_provider_link")

    def test_provider_request_failure_creates_admin_sync_notification(self) -> None:
        data = self.scoring_data(done=False)
        previous_key = wk_app.API_FOOTBALL_KEY
        wk_app.API_FOOTBALL_KEY = "test-key"

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO api_football_fixture_links (
                    match_id, api_fixture_id, confidence
                )
                VALUES ('m001', 123, 'test')
                """,
            )
            conn.commit()
            with patch.object(wk_app, "api_football_get", side_effect=RuntimeError("boom")):
                result = wk_app.run_api_football_completed_sync(data, force=True, match_id="m001")
            notifications = wk_app.active_admin_sync_notifications(conn)
            return result, notifications

        try:
            result, notifications = self.run_with_temp_db(scenario)
        finally:
            wk_app.API_FOOTBALL_KEY = previous_key

        self.assertFalse(result["ok"])
        self.assertEqual(result["attempts"][0]["status"], wk_app.SYNC_STATUS_FAILED)
        self.assertEqual(notifications[0]["type"], "provider_request_failed")

    def test_sync_issue_notifications_are_admin_only_in_pool_state(self) -> None:
        data = self.scoring_data(done=False)

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES (1, 'Admin', 'admin@example.com', 'x', 1),
                       (2, 'Player', 'player@example.com', 'x', 0)
                """,
            )
            wk_app.create_admin_sync_notification(
                conn,
                notification_type="missing_provider_link",
                target_type=wk_app.SYNC_TARGET_MATCH_RESULT,
                target_id="m001",
                title="Result sync needs a fixture link",
                body="A due match could not be synced.",
            )
            conn.commit()
            admin_state = wk_app.user_pool_state(
                {
                    "id": 1,
                    "name": "Admin",
                    "email": "admin@example.com",
                    "is_admin": True,
                },
                data,
            )
            player_state = wk_app.user_pool_state(
                {
                    "id": 2,
                    "name": "Player",
                    "email": "player@example.com",
                    "is_admin": False,
                },
                data,
            )
            return admin_state, player_state

        admin_state, player_state = self.run_with_temp_db(scenario)

        self.assertTrue(any(item["type"] == "sync_issue" for item in admin_state["notifications"]))
        self.assertFalse(
            any(item["type"] == "sync_issue" for item in player_state["notifications"])
        )

    def test_world_cup_payload_hides_provider_failure_details(self) -> None:
        data = self.scoring_data(done=False)

        def scenario(conn):
            wk_app.create_admin_sync_notification(
                conn,
                notification_type="provider_request_failed",
                target_type=wk_app.SYNC_TARGET_MATCH_RESULT,
                target_id="m001",
                title="Result sync request failed",
                body="A due match could not be retrieved.",
            )

        self.run_with_temp_db(scenario)
        with patch.object(wk_app, "load_world_cup_data", return_value=data):
            response = wk_app.app.test_client().get("/api/world-cup")

        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("admin_sync_notifications", json.dumps(payload))
        self.assertNotIn("provider_request_failed", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
