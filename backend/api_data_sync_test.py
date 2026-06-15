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

    def test_vercel_crons_are_hobby_plan_compatible(self) -> None:
        config = json.loads((Path(__file__).resolve().parent.parent / "vercel.json").read_text())
        crons = {item["path"]: item["schedule"] for item in config["crons"]}

        self.assertEqual(crons["/api/cron/api-football-sync"], "0 8 * * *")
        self.assertEqual(crons["/api/cron/api-football-squad-sync"], "30 8 * * *")
        self.assertEqual(crons["/api/cron/newsletters-refresh"], "0 7 * * *")

    def test_talpa_email_validation_for_new_accounts(self) -> None:
        self.assertEqual(
            wk_app.validate_talpa_account_email(" First.Last@TalpaStudios.com "),
            "first.last@talpastudios.com",
        )
        self.assertEqual(
            wk_app.validate_talpa_account_email(" First.Last@TalpaNetwork.com "),
            "first.last@talpanetwork.com",
        )
        with self.assertRaises(ValueError):
            wk_app.validate_talpa_account_email("first.middle.last@talpastudios.com")
        with self.assertRaises(ValueError):
            wk_app.validate_talpa_account_email("first.last@example.com")

    def test_login_creates_only_talpa_accounts(self) -> None:
        def scenario(_conn):
            client = wk_app.app.test_client()
            invalid = client.post(
                "/api/auth/login",
                json={
                    "email": "first.last@example.com",
                    "password": "valid-password",
                },
            )
            network_valid = client.post(
                "/api/auth/login",
                json={
                    "email": " First.Last@TalpaNetwork.com ",
                    "password": "valid-password",
                },
            )
            studios_valid = client.post(
                "/api/auth/login",
                json={
                    "email": " Studio.User@TalpaStudios.com ",
                    "password": "valid-password",
                },
            )
            with wk_app.get_db() as check_conn:
                rows = wk_app.execute(
                    check_conn,
                    """
                    SELECT email, prize_pot_status
                    FROM users
                    WHERE LOWER(TRIM(email)) IN (?, ?)
                    ORDER BY email
                    """,
                    ("first.last@talpanetwork.com", "studio.user@talpastudios.com"),
                ).fetchall()
            return invalid, network_valid, studios_valid, rows

        invalid_response, network_response, studios_response, rows = self.run_with_temp_db(scenario)

        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(network_response.status_code, 200)
        self.assertEqual(studios_response.status_code, 200)
        self.assertEqual(
            [row["email"] for row in rows],
            [
                "first.last@talpanetwork.com",
                "studio.user@talpastudios.com",
            ],
        )
        self.assertTrue(all(row["prize_pot_status"] == wk_app.PRIZE_POT_UNDECIDED for row in rows))

    def test_prize_pot_participation_endpoint_updates_current_user(self) -> None:
        def scenario(_conn):
            client = wk_app.app.test_client()
            login_response = client.post(
                "/api/auth/login",
                json={
                    "email": "pool.player@talpastudios.com",
                    "password": "valid-password",
                },
            )
            update_response = client.post(
                "/api/prize-pot/participation",
                json={"status": wk_app.PRIZE_POT_JOINED},
            )
            with wk_app.get_db() as check_conn:
                row = wk_app.execute(
                    check_conn,
                    "SELECT prize_pot_status FROM users WHERE email = ?",
                    ("pool.player@talpastudios.com",),
                ).fetchone()
            return login_response, update_response, row

        login_response, update_response, row = self.run_with_temp_db(scenario)

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(update_response.status_code, 200)
        payload = update_response.get_json()
        self.assertEqual(payload["prize_pot"]["status"], wk_app.PRIZE_POT_JOINED)
        self.assertEqual(row["prize_pot_status"], wk_app.PRIZE_POT_JOINED)
        self.assertEqual(wk_app.prize_pot_notification(wk_app.PRIZE_POT_JOINED), [])

    def test_prize_pot_declined_user_can_join_but_joined_user_cannot_decline(self) -> None:
        def scenario(_conn):
            client = wk_app.app.test_client()
            login_response = client.post(
                "/api/auth/login",
                json={
                    "email": "pool.player@talpastudios.com",
                    "password": "valid-password",
                },
            )
            declined_response = client.post(
                "/api/prize-pot/participation",
                json={"status": wk_app.PRIZE_POT_DECLINED},
            )
            joined_response = client.post(
                "/api/prize-pot/participation",
                json={"status": wk_app.PRIZE_POT_JOINED},
            )
            opt_out_response = client.post(
                "/api/prize-pot/participation",
                json={"status": wk_app.PRIZE_POT_DECLINED},
            )
            pool_response = client.get("/api/pool")
            with wk_app.get_db() as check_conn:
                row = wk_app.execute(
                    check_conn,
                    "SELECT prize_pot_status FROM users WHERE email = ?",
                    ("pool.player@talpastudios.com",),
                ).fetchone()
            return (
                login_response,
                declined_response,
                joined_response,
                opt_out_response,
                pool_response,
                row,
            )

        (
            login_response,
            declined_response,
            joined_response,
            opt_out_response,
            pool_response,
            row,
        ) = self.run_with_temp_db(scenario)

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(declined_response.status_code, 200)
        self.assertNotIn("participant_count", declined_response.get_json()["prize_pot"])
        self.assertEqual(joined_response.status_code, 200)
        self.assertEqual(joined_response.get_json()["prize_pot"]["participant_count"], 1)
        self.assertEqual(opt_out_response.status_code, 400)
        self.assertEqual(pool_response.get_json()["prize_pot"]["participant_count"], 1)
        self.assertEqual(row["prize_pot_status"], wk_app.PRIZE_POT_JOINED)

    def test_prize_pot_participant_count_does_not_expose_names_to_participants(self) -> None:
        def scenario(_conn):
            admin_client = wk_app.app.test_client()
            player_client = wk_app.app.test_client()
            admin_client.post(
                "/api/auth/login",
                json={
                    "email": "admin.user@talpastudios.com",
                    "password": "valid-password",
                },
            )
            admin_client.post(
                "/api/prize-pot/participation",
                json={"status": wk_app.PRIZE_POT_JOINED},
            )
            player_client.post(
                "/api/auth/login",
                json={
                    "email": "pool.player@talpastudios.com",
                    "password": "valid-password",
                },
            )
            player_client.post(
                "/api/prize-pot/participation",
                json={"status": wk_app.PRIZE_POT_JOINED},
            )
            player_pool = player_client.get("/api/pool").get_json()
            admin_pool = admin_client.get("/api/pool").get_json()
            return player_pool, admin_pool

        player_pool, admin_pool = self.run_with_temp_db(scenario)

        self.assertEqual(player_pool["prize_pot"]["participant_count"], 2)
        self.assertEqual(
            [
                row["prize_pot_status"]
                for row in player_pool["leaderboard"]
                if row["user_id"] != player_pool["me"]["id"]
            ],
            [None],
        )
        self.assertEqual(
            sorted(row["prize_pot_status"] for row in admin_pool["leaderboard"]),
            [wk_app.PRIZE_POT_JOINED, wk_app.PRIZE_POT_JOINED],
        )

    def test_single_match_prediction_endpoint_returns_compact_patch(self) -> None:
        kickoff = datetime(2026, 6, 20, 18, 0, tzinfo=UTC)
        data = {
            "matches": [
                {
                    **make_match("m001", kickoff),
                    "status": "scheduled",
                    "quiz": {
                        "question": "Blijft het 0-0 in de eerste helft?",
                        "choices": ["ja", "nee"],
                    },
                }
            ],
            "teams": [
                {"id": "ned", "name": "Netherlands", "code": "NED"},
                {"id": "usa", "name": "United States", "code": "USA"},
            ],
            "groups": [{"id": "A", "teams": ["ned", "usa"]}],
            "venues": [],
            "meta": {},
        }

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash)
                VALUES (1, 'Player', 'player.user@talpastudios.com', 'x')
                """,
            )
            conn.commit()
            client = wk_app.app.test_client()
            with client.session_transaction() as session:
                session["user_id"] = 1
            with patch.object(wk_app, "load_world_cup_data", return_value=data):
                response = client.post(
                    "/api/predictions/m001",
                    json={
                        "home_score": 2,
                        "away_score": 1,
                        "quiz_answer": "ja",
                        "leeuwtje": True,
                    },
                )
            rows = {
                "prediction": wk_app.execute(
                    conn,
                    "SELECT home_score, away_score FROM match_predictions WHERE user_id = 1",
                ).fetchone(),
                "quiz": wk_app.execute(
                    conn,
                    "SELECT answer FROM quiz_predictions WHERE user_id = 1",
                ).fetchone(),
                "leeuwtje": wk_app.execute(
                    conn,
                    "SELECT match_id FROM leeuwtje_predictions WHERE user_id = 1",
                ).fetchone(),
            }
            return response, rows

        response, rows = self.run_with_temp_db(scenario)

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["prediction"], {"home_score": 2, "away_score": 1})
        self.assertEqual(payload["quiz_prediction"]["answer"], "ja")
        self.assertEqual(payload["leeuwtjes_match_ids"], ["m001"])
        self.assertNotIn("leaderboard", payload)
        self.assertEqual(rows["prediction"]["home_score"], 2)
        self.assertEqual(rows["quiz"]["answer"], "ja")
        self.assertEqual(rows["leeuwtje"]["match_id"], "m001")

    def test_early_post_match_attempt_is_due_after_five_minutes(self) -> None:
        kickoff = datetime(2026, 6, 11, 18, 0, tzinfo=UTC)
        match = make_match("m001", kickoff)
        postmatch_anchor = kickoff + wk_app.API_FOOTBALL_POSTMATCH_BUFFER

        due = wk_app.due_result_sync_attempt_kinds(
            match,
            now=postmatch_anchor + wk_app.RESULT_SYNC_EARLY_AFTER,
            terminal_attempt_kinds=set(),
        )

        self.assertEqual(due, [wk_app.SYNC_ATTEMPT_EARLY_POST_MATCH])

    def test_first_post_match_attempt_waits_for_early_terminal_attempt(self) -> None:
        kickoff = datetime(2026, 6, 11, 18, 0, tzinfo=UTC)
        match = make_match("m001", kickoff)
        postmatch_anchor = kickoff + wk_app.API_FOOTBALL_POSTMATCH_BUFFER

        due_without_early = wk_app.due_result_sync_attempt_kinds(
            match,
            now=postmatch_anchor + wk_app.RESULT_SYNC_FIRST_AFTER,
            terminal_attempt_kinds=set(),
        )
        due_with_early = wk_app.due_result_sync_attempt_kinds(
            match,
            now=postmatch_anchor + wk_app.RESULT_SYNC_FIRST_AFTER,
            terminal_attempt_kinds={wk_app.SYNC_ATTEMPT_EARLY_POST_MATCH},
        )

        self.assertEqual(due_without_early, [wk_app.SYNC_ATTEMPT_EARLY_POST_MATCH])
        self.assertEqual(due_with_early, [wk_app.SYNC_ATTEMPT_FIRST_POST_MATCH])

    def test_second_post_match_attempt_waits_for_early_and_first_terminal_attempts(self) -> None:
        kickoff = datetime(2026, 6, 11, 18, 0, tzinfo=UTC)
        match = make_match("m001", kickoff)
        postmatch_anchor = kickoff + wk_app.API_FOOTBALL_POSTMATCH_BUFFER

        due_without_early = wk_app.due_result_sync_attempt_kinds(
            match,
            now=postmatch_anchor + wk_app.RESULT_SYNC_SECOND_AFTER,
            terminal_attempt_kinds=set(),
        )
        due_without_first = wk_app.due_result_sync_attempt_kinds(
            match,
            now=postmatch_anchor + wk_app.RESULT_SYNC_SECOND_AFTER,
            terminal_attempt_kinds={wk_app.SYNC_ATTEMPT_EARLY_POST_MATCH},
        )
        due_with_first = wk_app.due_result_sync_attempt_kinds(
            match,
            now=postmatch_anchor + wk_app.RESULT_SYNC_SECOND_AFTER,
            terminal_attempt_kinds={
                wk_app.SYNC_ATTEMPT_EARLY_POST_MATCH,
                wk_app.SYNC_ATTEMPT_FIRST_POST_MATCH,
            },
        )

        self.assertEqual(due_without_early, [wk_app.SYNC_ATTEMPT_EARLY_POST_MATCH])
        self.assertEqual(due_without_first, [wk_app.SYNC_ATTEMPT_FIRST_POST_MATCH])
        self.assertEqual(due_with_first, [wk_app.SYNC_ATTEMPT_SECOND_POST_MATCH])

    def test_no_attempt_due_before_early_window_or_after_all_terminal(self) -> None:
        kickoff = datetime(2026, 6, 11, 18, 0, tzinfo=UTC)
        match = make_match("m001", kickoff)
        postmatch_anchor = kickoff + wk_app.API_FOOTBALL_POSTMATCH_BUFFER

        early = wk_app.due_result_sync_attempt_kinds(
            match,
            now=postmatch_anchor + timedelta(minutes=4),
            terminal_attempt_kinds=set(),
        )
        complete = wk_app.due_result_sync_attempt_kinds(
            match,
            now=postmatch_anchor + timedelta(hours=3),
            terminal_attempt_kinds={
                wk_app.SYNC_ATTEMPT_EARLY_POST_MATCH,
                wk_app.SYNC_ATTEMPT_FIRST_POST_MATCH,
                wk_app.SYNC_ATTEMPT_SECOND_POST_MATCH,
            },
            has_result=True,
        )

        self.assertEqual(early, [])
        self.assertEqual(complete, [])

    def test_missing_result_after_both_windows_is_retried_as_backlog(self) -> None:
        kickoff = datetime.now(UTC) - wk_app.API_FOOTBALL_POSTMATCH_BUFFER - timedelta(hours=3)
        match = make_match("m001", kickoff)
        data = {"matches": [match], "teams": []}

        def scenario(conn):
            for attempt_kind in (
                wk_app.SYNC_ATTEMPT_EARLY_POST_MATCH,
                wk_app.SYNC_ATTEMPT_FIRST_POST_MATCH,
                wk_app.SYNC_ATTEMPT_SECOND_POST_MATCH,
            ):
                attempt_id = wk_app.create_provider_sync_attempt(
                    conn,
                    provider_key=wk_app.API_FOOTBALL_PROVIDER_KEY,
                    target_type=wk_app.SYNC_TARGET_MATCH_RESULT,
                    target_id="m001",
                    attempt_kind=attempt_kind,
                    scheduled_for=wk_app.result_sync_scheduled_for(match, attempt_kind),
                    status=wk_app.SYNC_STATUS_SKIPPED,
                )
                wk_app.finish_provider_sync_attempt(
                    conn,
                    attempt_id,
                    status=wk_app.SYNC_STATUS_SKIPPED,
                    failure_code="missing_provider_fixture_link",
                )
            conn.commit()
            return wk_app.due_api_football_match_attempts(data, limit=1)

        candidates = self.run_with_temp_db(scenario)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["attempt_kind"], wk_app.SYNC_ATTEMPT_MISSING_DATA_RETRY)

    def test_missing_result_backlog_stops_after_result_exists(self) -> None:
        kickoff = datetime.now(UTC) - wk_app.API_FOOTBALL_POSTMATCH_BUFFER - timedelta(hours=3)
        match = make_match("m001", kickoff)
        data = {"matches": [match], "teams": []}

        def scenario(conn):
            for attempt_kind in (
                wk_app.SYNC_ATTEMPT_EARLY_POST_MATCH,
                wk_app.SYNC_ATTEMPT_FIRST_POST_MATCH,
                wk_app.SYNC_ATTEMPT_SECOND_POST_MATCH,
            ):
                attempt_id = wk_app.create_provider_sync_attempt(
                    conn,
                    provider_key=wk_app.API_FOOTBALL_PROVIDER_KEY,
                    target_type=wk_app.SYNC_TARGET_MATCH_RESULT,
                    target_id="m001",
                    attempt_kind=attempt_kind,
                    scheduled_for=wk_app.result_sync_scheduled_for(match, attempt_kind),
                    status=wk_app.SYNC_STATUS_SKIPPED,
                )
                wk_app.finish_provider_sync_attempt(
                    conn,
                    attempt_id,
                    status=wk_app.SYNC_STATUS_SKIPPED,
                    failure_code="missing_provider_fixture_link",
                )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_results (
                    match_id, source, status_short, home_score, away_score
                )
                VALUES (?, ?, 'FT', 2, 1)
                """,
                ("m001", wk_app.API_FOOTBALL_PROVIDER_KEY),
            )
            for index, player_name in enumerate(("One", "Two", "Three"), start=1):
                wk_app.execute(
                    conn,
                    """
                    INSERT INTO match_events (
                        match_id, provider_event_key, event_type, player_name, raw_json
                    )
                    VALUES (?, ?, 'Goal', ?, '{}')
                    """,
                    ("m001", f"provider:event:{index}", player_name),
                )
            conn.commit()
            return wk_app.due_api_football_match_attempts(data, limit=1)

        candidates = self.run_with_temp_db(scenario)

        self.assertEqual(candidates, [])

    def test_final_result_with_missing_goal_events_is_retried_as_backlog(self) -> None:
        kickoff = datetime.now(UTC) - wk_app.API_FOOTBALL_POSTMATCH_BUFFER - timedelta(hours=3)
        match = make_match("m001", kickoff)
        data = {"matches": [match], "teams": []}

        def scenario(conn):
            for attempt_kind in (
                wk_app.SYNC_ATTEMPT_EARLY_POST_MATCH,
                wk_app.SYNC_ATTEMPT_FIRST_POST_MATCH,
                wk_app.SYNC_ATTEMPT_SECOND_POST_MATCH,
            ):
                attempt_id = wk_app.create_provider_sync_attempt(
                    conn,
                    provider_key=wk_app.API_FOOTBALL_PROVIDER_KEY,
                    target_type=wk_app.SYNC_TARGET_MATCH_RESULT,
                    target_id="m001",
                    attempt_kind=attempt_kind,
                    scheduled_for=wk_app.result_sync_scheduled_for(match, attempt_kind),
                    status=wk_app.SYNC_STATUS_SUCCEEDED,
                )
                wk_app.finish_provider_sync_attempt(
                    conn,
                    attempt_id,
                    status=wk_app.SYNC_STATUS_SUCCEEDED,
                )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_results (
                    match_id, source, status_short, home_score, away_score
                )
                VALUES (?, ?, 'FT', 2, 1)
                """,
                ("m001", wk_app.API_FOOTBALL_PROVIDER_KEY),
            )
            conn.commit()
            missing_ids = wk_app.missing_result_match_ids(data)
            candidates = wk_app.due_api_football_match_attempts(data, limit=1)
            return missing_ids, candidates

        missing_ids, candidates = self.run_with_temp_db(scenario)

        self.assertEqual(missing_ids, ["m001"])
        self.assertEqual(candidates[0]["attempt_kind"], wk_app.SYNC_ATTEMPT_MISSING_DATA_RETRY)

    def test_backlog_missing_link_notifies_admins_and_remains_retryable(self) -> None:
        kickoff = datetime.now(UTC) - wk_app.API_FOOTBALL_POSTMATCH_BUFFER - timedelta(hours=3)
        match = make_match("m001", kickoff)
        data = {"matches": [match], "teams": []}

        def scenario(conn):
            for attempt_kind in (
                wk_app.SYNC_ATTEMPT_EARLY_POST_MATCH,
                wk_app.SYNC_ATTEMPT_FIRST_POST_MATCH,
                wk_app.SYNC_ATTEMPT_SECOND_POST_MATCH,
            ):
                attempt_id = wk_app.create_provider_sync_attempt(
                    conn,
                    provider_key=wk_app.API_FOOTBALL_PROVIDER_KEY,
                    target_type=wk_app.SYNC_TARGET_MATCH_RESULT,
                    target_id="m001",
                    attempt_kind=attempt_kind,
                    scheduled_for=wk_app.result_sync_scheduled_for(match, attempt_kind),
                    status=wk_app.SYNC_STATUS_SKIPPED,
                )
                wk_app.finish_provider_sync_attempt(
                    conn,
                    attempt_id,
                    status=wk_app.SYNC_STATUS_SKIPPED,
                    failure_code="missing_provider_fixture_link",
                )

            conn.commit()
            result = wk_app.run_api_football_completed_sync(data, limit=1)
            notifications = wk_app.active_admin_sync_notifications(conn)
            retry_candidates = wk_app.due_api_football_match_attempts(data, limit=1)
            return result, notifications, retry_candidates

        previous_key = wk_app.API_FOOTBALL_KEY
        wk_app.API_FOOTBALL_KEY = "test-key"
        try:
            with patch.object(
                wk_app,
                "api_football_link_fixtures",
                return_value={"linked": 0, "skipped": 1, "fixtures_seen": 0},
            ):
                result, notifications, retry_candidates = self.run_with_temp_db(scenario)
        finally:
            wk_app.API_FOOTBALL_KEY = previous_key

        self.assertEqual(
            result["attempts"][0]["attempt_kind"], wk_app.SYNC_ATTEMPT_MISSING_DATA_RETRY
        )
        self.assertTrue(
            any(item["type"] == "missing_match_data" for item in notifications),
            notifications,
        )
        self.assertEqual(
            retry_candidates[0]["attempt_kind"], wk_app.SYNC_ATTEMPT_MISSING_DATA_RETRY
        )

    def test_result_sync_links_fixtures_before_skipping_missing_link(self) -> None:
        kickoff = datetime.now(UTC) - wk_app.API_FOOTBALL_POSTMATCH_BUFFER - timedelta(minutes=30)
        match = make_match("m001", kickoff, home_team_id="mex", away_team_id="rsa")
        data = {
            "matches": [match],
            "teams": [
                {"id": "mex", "name": "Mexico", "code": "MEX"},
                {"id": "rsa", "name": "South Africa", "code": "RSA"},
            ],
            "groups": [],
            "venues": [],
            "meta": {},
        }
        fixture = {
            "fixture": {"id": 123, "status": {"long": "Match Finished", "short": "FT"}},
            "teams": {
                "home": {"id": 16, "name": "Mexico"},
                "away": {"id": 1531, "name": "South Africa"},
            },
            "goals": {"home": 2, "away": 0},
            "events": [],
            "players": [],
        }

        def link_fixture(_data):
            with wk_app.get_db() as link_conn:
                wk_app.execute(
                    link_conn,
                    """
                    INSERT INTO api_football_fixture_links (
                        match_id, api_fixture_id, confidence
                    )
                    VALUES (?, ?, ?)
                    """,
                    ("m001", 123, "test"),
                )
                link_conn.commit()
            return {"linked": 1, "skipped": 0, "fixtures_seen": 1}

        def scenario(_conn):
            return wk_app.run_api_football_completed_sync(data, limit=1)

        previous_key = wk_app.API_FOOTBALL_KEY
        wk_app.API_FOOTBALL_KEY = "test-key"
        try:
            with (
                patch.object(wk_app, "api_football_link_fixtures", side_effect=link_fixture),
                patch.object(wk_app, "api_football_get", return_value={"response": [fixture]}),
            ):
                result = self.run_with_temp_db(scenario)
        finally:
            wk_app.API_FOOTBALL_KEY = previous_key

        self.assertEqual(result["linking"]["linked"], 1)
        self.assertEqual(result["synced"][0]["match_id"], "m001")
        self.assertEqual(result["synced"][0]["home_score"], 2)
        self.assertEqual(result["skipped"], [])

    def test_admin_sync_dry_run_accepts_match_id_without_provider_key(self) -> None:
        previous_token = wk_app.API_FOOTBALL_SYNC_TOKEN
        previous_key = wk_app.API_FOOTBALL_KEY
        wk_app.API_FOOTBALL_SYNC_TOKEN = "test-token"
        wk_app.API_FOOTBALL_KEY = ""
        kickoff = datetime.now(UTC) - wk_app.API_FOOTBALL_POSTMATCH_BUFFER - timedelta(minutes=30)
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

    def test_match_prediction_points_use_detailed_group_rules(self) -> None:
        kickoff = datetime.now(UTC) - timedelta(hours=3)
        match = make_match("m001", kickoff)
        match["status"] = "completed"
        match["home_score"] = 2
        match["away_score"] = 1

        exact_points, exact_kind = wk_app.match_prediction_points(
            {"home_score": 2, "away_score": 1}, match
        )
        margin_points, margin_kind = wk_app.match_prediction_points(
            {"home_score": 3, "away_score": 1}, match
        )
        goal_only_points, goal_only_kind = wk_app.match_prediction_points(
            {"home_score": 0, "away_score": 1}, match
        )

        self.assertEqual((exact_points, exact_kind), (12, "exact"))
        self.assertEqual((margin_points, margin_kind), (8, "outcome"))
        self.assertEqual((goal_only_points, goal_only_kind), (2, "partial"))

    def test_exact_score_counts_as_exact_and_outcome_on_leaderboard(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
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
            conn.commit()
            return wk_app.build_leaderboard(data, use_computed_points=False)[0]

        row = self.run_with_temp_db(scenario)

        self.assertEqual(row["match_score_points"], 12)
        self.assertEqual(row["exact_scores"], 1)
        self.assertEqual(row["outcomes"], 1)

    def test_user_match_points_include_component_breakdown(self) -> None:
        data = self.scoring_data(done=True)

        points_by_match = wk_app.user_match_points_by_match(
            data,
            {"m001": {"home_score": 2, "away_score": 1}},
            {"m001": {"answer": "Netherlands", "viewership_prediction": None}},
            ["m001"],
        )

        points = points_by_match["m001"]
        self.assertEqual(points["score_points"], 12)
        self.assertEqual(points["leeuwtje_points"], 12)
        self.assertEqual(points["quiz_points"], 5)
        self.assertEqual(points["total_points"], 29)
        self.assertEqual(points["score_breakdown"]["outcome_points"], 6)
        self.assertEqual(points["score_breakdown"]["home_goals_points"], 2)
        self.assertEqual(points["score_breakdown"]["away_goals_points"], 2)
        self.assertEqual(points["score_breakdown"]["exact_bonus_points"], 2)

    def test_badge_unlocked_notification_is_shown_for_viewer(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES (1, 'Player', 'player@example.com', 'x', 0)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_predictions (user_id, match_id, home_score, away_score)
                VALUES (1, 'm001', 2, 1)
                """,
            )
            conn.commit()
            return wk_app.user_pool_state(
                {"id": 1, "name": "Player", "email": "player@example.com", "is_admin": False},
                data,
            )

        payload = self.run_with_temp_db(scenario)

        badge_notifications = [
            item for item in payload["notifications"] if item["type"] == "badge_unlocked"
        ]
        self.assertEqual(len(badge_notifications), 1)
        self.assertIn("Perfect Score", badge_notifications[0]["body"])

    def test_match_prediction_points_apply_round_multiplier(self) -> None:
        kickoff = datetime.now(UTC) - timedelta(hours=3)
        match = make_match("m001", kickoff)
        match["round"] = "Final"
        match["status"] = "completed"
        match["home_score"] = 2
        match["away_score"] = 1

        exact_points, _ = wk_app.match_prediction_points({"home_score": 2, "away_score": 1}, match)
        outcome_points, _ = wk_app.match_prediction_points(
            {"home_score": 4, "away_score": 2}, match
        )

        self.assertEqual(exact_points, 48)
        self.assertEqual(outcome_points, 24)

    def test_striker_points_apply_round_multiplier(self) -> None:
        group_kickoff = datetime.now(UTC) - timedelta(days=2)
        final_kickoff = datetime.now(UTC) - timedelta(hours=3)
        group_match = make_match("m001", group_kickoff)
        group_match["round"] = "Group Stage"
        final_match = make_match("m002", final_kickoff)
        final_match["round"] = "Final"
        data = {"matches": [group_match, final_match]}

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, event_type, player_name, raw_json
                )
                VALUES
                    ('m001', 'provider:event:1', 'Goal', 'Cody Gakpo', '{}'),
                    ('m002', 'provider:event:2', 'Goal', 'Cody Gakpo', '{}')
                """,
            )
            conn.commit()
            counts, points = wk_app.goal_counts_and_points_by_player(data)
            return (
                counts[wk_app.normalized_player_name("Cody Gakpo")],
                points[wk_app.normalized_player_name("Cody Gakpo")],
            )

        goals, points = self.run_with_temp_db(scenario)

        self.assertEqual(goals, 2)
        self.assertEqual(points, 30)

    def test_striker_points_match_initial_surname_goal_events(self) -> None:
        kickoff = datetime.now(UTC) - timedelta(hours=3)
        match = make_match("m012", kickoff, home_team_id="swe", away_team_id="tun")
        match["status"] = "completed"
        data = {"matches": [match]}

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES (1, 'Player', 'player@example.com', 'x', 0)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO top_scorer_predictions (
                    user_id, player_name, striker_name_1, striker_name_2,
                    striker_name_3, striker_name_4, striker_name_5
                )
                VALUES (
                    1, 'Alexander Isak', 'Omar Rekik', 'Mattias Svanberg',
                    'Alexander Isak', 'Viktor Gyökeres', 'Yasin Ayari'
                )
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, event_type, player_name, raw_json
                )
                VALUES
                    ('m012', 'provider:event:1', 'Goal', 'A. Isak', '{}'),
                    ('m012', 'provider:event:2', 'Goal', 'O. Rekik', '{}'),
                    ('m012', 'provider:event:3', 'Goal', 'V. Gyokeres', '{}'),
                    ('m012', 'provider:event:4', 'Goal', 'Y. Ayari', '{}'),
                    ('m012', 'provider:event:5', 'Goal', 'M. Svanberg', '{}'),
                    ('m012', 'provider:event:6', 'Goal', 'Y. Ayari', '{}')
                """
            )
            conn.commit()
            row = wk_app.execute(
                conn,
                """
                SELECT player_name, striker_name_1, striker_name_2, striker_name_3,
                       striker_name_4, striker_name_5
                FROM top_scorer_predictions
                WHERE user_id = 1
                """,
            ).fetchone()
            counts, points = wk_app.goal_counts_and_points_by_player(data)
            return wk_app.striker_pick_score_rows(row, counts, points)

        picks = self.run_with_temp_db(scenario)

        points_by_name = {pick["name"]: pick["points"] for pick in picks}
        goals_by_name = {pick["name"]: pick["goals"] for pick in picks}
        self.assertEqual(goals_by_name["Yasin Ayari"], 2)
        self.assertEqual(sum(points_by_name.values()), 36)

    def test_tournament_session_date_groups_overnight_matches(self) -> None:
        evening_match = make_match("m001", datetime(2026, 6, 11, 19, 0, tzinfo=UTC))
        overnight_match = make_match("m002", datetime(2026, 6, 12, 1, 59, tzinfo=UTC))
        four_oclock_match = make_match("m004", datetime(2026, 6, 12, 2, 0, tzinfo=UTC))
        west_coast_late_match = make_match("m005", datetime(2026, 6, 12, 4, 0, tzinfo=UTC))
        next_evening_match = make_match("m003", datetime(2026, 6, 12, 19, 0, tzinfo=UTC))

        self.assertEqual(
            wk_app.tournament_session_date(evening_match),
            wk_app.tournament_session_date(overnight_match),
        )
        self.assertEqual(
            wk_app.tournament_session_date(evening_match),
            wk_app.tournament_session_date(four_oclock_match),
        )
        self.assertEqual(
            wk_app.tournament_session_date(evening_match),
            wk_app.tournament_session_date(west_coast_late_match),
        )
        self.assertNotEqual(
            wk_app.tournament_session_date(evening_match),
            wk_app.tournament_session_date(next_evening_match),
        )

    def test_daily_recap_uses_tournament_session_window(self) -> None:
        evening_match = make_match("m001", datetime(2026, 6, 11, 19, 0, tzinfo=UTC))
        overnight_match = make_match("m002", datetime(2026, 6, 12, 1, 59, tzinfo=UTC))
        next_evening_match = make_match("m003", datetime(2026, 6, 12, 19, 0, tzinfo=UTC))
        for match in (evening_match, overnight_match, next_evening_match):
            match["status"] = "completed"
            match["home_score"] = 1
            match["away_score"] = 0
        data = {
            "matches": [evening_match, overnight_match, next_evening_match],
            "teams": [
                {"id": "ned", "name": "Netherlands", "code": "NED"},
                {"id": "usa", "name": "United States", "code": "USA"},
            ],
            "groups": [{"id": "A", "teams": ["ned", "usa"]}],
            "venues": [],
            "meta": {},
        }

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES (1, 'Karel', 'karel@example.com', 'x', 0)
                """,
            )
            return wk_app.build_daily_recap(
                data,
                now=datetime(2026, 6, 12, 4, 30, tzinfo=UTC),
                leaderboard=[],
                viewer_user_id=1,
            )

        recap = self.run_with_temp_db(scenario)

        self.assertEqual(recap["title"], "Recap 2026-06-11")
        self.assertEqual(
            [moment["match_id"] for moment in recap["moments"]],
            ["m001", "m002"],
        )

    def test_daily_recap_movers_use_target_session_only(self) -> None:
        previous_match = make_match("m000", datetime(2026, 6, 10, 19, 0, tzinfo=UTC))
        target_match = make_match("m001", datetime(2026, 6, 11, 19, 0, tzinfo=UTC))
        next_match = make_match("m002", datetime(2026, 6, 12, 19, 0, tzinfo=UTC))
        for match in (previous_match, target_match, next_match):
            match["status"] = "completed"
            match["home_score"] = 1
            match["away_score"] = 0
        data = {
            "matches": [previous_match, target_match, next_match],
            "teams": [
                {"id": "ned", "name": "Netherlands", "code": "NED"},
                {"id": "usa", "name": "United States", "code": "USA"},
            ],
            "groups": [{"id": "A", "teams": ["ned", "usa"]}],
            "venues": [],
            "meta": {},
        }

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES
                    (1, 'Anna', 'anna@example.com', 'x', 0),
                    (2, 'Bram', 'bram@example.com', 'x', 0),
                    (3, 'Chris', 'chris@example.com', 'x', 0)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_predictions (user_id, match_id, home_score, away_score)
                VALUES
                    (1, 'm000', 1, 0),
                    (2, 'm000', 2, 0),
                    (1, 'm001', 0, 1),
                    (3, 'm001', 1, 0),
                    (1, 'm002', 1, 0)
                """,
            )
            wk_app.execute(
                conn,
                "INSERT INTO leeuwtje_predictions (user_id, match_id) VALUES (3, 'm001')",
            )
            conn.commit()
            return wk_app.build_daily_recap(
                data,
                now=datetime(2026, 6, 12, 4, 30, tzinfo=UTC),
                leaderboard=[],
            )

        recap = self.run_with_temp_db(scenario)

        movers = {row["name"]: row["rank_movement"] for row in recap["top_movers"]}
        self.assertEqual(movers["Chris"], 2)
        self.assertEqual(movers["Anna"], -1)
        self.assertEqual(movers["Bram"], -1)

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
                patch.object(
                    wk_app,
                    "api_football_link_fixtures",
                    return_value={"linked": 0, "skipped": 1, "fixtures_seen": 0},
                ),
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
        self.assertTrue(
            any(item["type"] == "missing_provider_link" for item in notifications),
            notifications,
        )
        self.assertTrue(
            any(item["type"] == "missing_match_data" for item in notifications),
            notifications,
        )

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
        self.assertTrue(
            any(item["type"] == "provider_request_failed" for item in notifications),
            notifications,
        )
        self.assertTrue(
            any(item["type"] == "missing_match_data" for item in notifications),
            notifications,
        )

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

    def test_unmatched_striker_pick_notifies_admins_until_player_exists(self) -> None:
        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES (1, 'Player', 'player@example.com', 'x', 0)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO top_scorer_predictions (
                    user_id, player_name, striker_name_1, striker_name_2
                )
                VALUES (1, 'Cody Gakpo', 'Cody Gakpo', 'Typo Scorer')
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO team_squad_players (
                    local_team_id, provider_player_key, api_player_id, player_name, raw_json
                )
                VALUES ('ned', '1', 1, 'Cody Gakpo', '{}')
                """,
            )
            first = wk_app.verify_player_database_matches(conn)
            first_notifications = wk_app.active_admin_sync_notifications(conn)
            wk_app.execute(
                conn,
                """
                INSERT INTO team_squad_players (
                    local_team_id, provider_player_key, api_player_id, player_name, raw_json
                )
                VALUES ('usa', '2', 2, 'Typo Scorer', '{}')
                """,
            )
            second = wk_app.verify_player_database_matches(conn)
            second_notifications = wk_app.active_admin_sync_notifications(conn)
            return first, first_notifications, second, second_notifications

        first, first_notifications, second, second_notifications = self.run_with_temp_db(scenario)

        self.assertEqual(first["invalid_striker_picks"], 1)
        self.assertTrue(
            any(
                item["type"] == wk_app.SYNC_NOTIFICATION_STRIKER_PICK_NOT_IN_SQUAD
                for item in first_notifications
            ),
            first_notifications,
        )
        self.assertEqual(second["invalid_striker_picks"], 0)
        self.assertFalse(
            any(
                item["type"] == wk_app.SYNC_NOTIFICATION_STRIKER_PICK_NOT_IN_SQUAD
                for item in second_notifications
            ),
            second_notifications,
        )

    def test_unmatched_match_scorer_notifies_admins_until_player_exists(self) -> None:
        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO team_squad_players (
                    local_team_id, provider_player_key, api_player_id, player_name, raw_json
                )
                VALUES ('ned', '1', 1, 'Cody Gakpo', '{}')
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, event_type, player_name, raw_json
                )
                VALUES ('m001', 'provider:event:1', 'Goal', 'Unknown Hero', '{}')
                """,
            )
            first = wk_app.verify_player_database_matches(conn)
            first_notifications = wk_app.active_admin_sync_notifications(conn)
            wk_app.execute(
                conn,
                """
                INSERT INTO team_squad_players (
                    local_team_id, provider_player_key, api_player_id, player_name, raw_json
                )
                VALUES ('usa', '2', 2, 'Unknown Hero', '{}')
                """,
            )
            second = wk_app.verify_player_database_matches(conn)
            second_notifications = wk_app.active_admin_sync_notifications(conn)
            return first, first_notifications, second, second_notifications

        first, first_notifications, second, second_notifications = self.run_with_temp_db(scenario)

        self.assertEqual(first["invalid_goal_scorers"], 1)
        self.assertTrue(
            any(
                item["type"] == wk_app.SYNC_NOTIFICATION_SCORER_PLAYER_NOT_IN_SQUAD
                for item in first_notifications
            ),
            first_notifications,
        )
        self.assertEqual(second["invalid_goal_scorers"], 0)
        self.assertFalse(
            any(
                item["type"] == wk_app.SYNC_NOTIFICATION_SCORER_PLAYER_NOT_IN_SQUAD
                for item in second_notifications
            ),
            second_notifications,
        )

    def test_scorer_notification_is_admin_only_and_clears_when_player_matches(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES (1, 'Admin', 'admin@example.com', 'x', 1),
                       (2, 'Player', 'player@example.com', 'x', 0)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, event_type, player_name, raw_json
                )
                VALUES ('m001', 'provider:event:1', 'Goal', 'Unknown Hero', '{}')
                """,
            )
            wk_app.verify_player_database_matches(conn)
            conn.commit()
            admin_with_issue = wk_app.user_pool_state(
                {"id": 1, "name": "Admin", "email": "admin@example.com", "is_admin": True},
                data,
            )
            player_with_issue = wk_app.user_pool_state(
                {"id": 2, "name": "Player", "email": "player@example.com", "is_admin": False},
                data,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO team_squad_players (
                    local_team_id, provider_player_key, api_player_id, player_name, raw_json
                )
                VALUES ('ned', '1', 1, 'Unknown Hero', '{}')
                """,
            )
            wk_app.verify_player_database_matches(conn)
            conn.commit()
            admin_after_match = wk_app.user_pool_state(
                {"id": 1, "name": "Admin", "email": "admin@example.com", "is_admin": True},
                data,
            )
            return admin_with_issue, player_with_issue, admin_after_match

        admin_with_issue, player_with_issue, admin_after_match = self.run_with_temp_db(scenario)

        self.assertTrue(
            any(
                item["type"] == "sync_issue"
                and item["title"] == "Goal scorer is not in the player database"
                for item in admin_with_issue["notifications"]
            ),
            admin_with_issue["notifications"],
        )
        self.assertFalse(
            any(item["type"] == "sync_issue" for item in player_with_issue["notifications"]),
            player_with_issue["notifications"],
        )
        self.assertFalse(
            any(
                item["type"] == "sync_issue"
                and item["title"] == "Goal scorer is not in the player database"
                for item in admin_after_match["notifications"]
            ),
            admin_after_match["notifications"],
        )

    def test_player_database_matching_accepts_initial_surname_variants(self) -> None:
        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO team_squad_players (
                    local_team_id, provider_player_key, api_player_id, player_name, raw_json
                )
                VALUES
                    ('swe', '1', 1, 'O. Rekik', '{}'),
                    ('swe', '2', 2, 'M. Svanberg', '{}'),
                    ('swe', '3', 3, 'A. Isak', '{}'),
                    ('swe', '4', 4, 'V. Gyokeres', '{}'),
                    ('swe', '5', 5, 'Y. Ayari', '{}')
                """
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, event_type, player_name, raw_json
                )
                VALUES
                    ('m012', 'provider:event:1', 'Goal', 'Omar Rekik', '{}'),
                    ('m012', 'provider:event:2', 'Goal', 'Mattias Svanberg', '{}'),
                    ('m012', 'provider:event:3', 'Goal', 'Alexander Isak', '{}'),
                    ('m012', 'provider:event:4', 'Goal', 'Viktor Gyökeres', '{}'),
                    ('m012', 'provider:event:5', 'Goal', 'Yasin Ayari', '{}')
                """
            )
            result = wk_app.verify_player_database_matches(conn)
            notifications = wk_app.active_admin_sync_notifications(conn)
            return result, notifications

        result, notifications = self.run_with_temp_db(scenario)

        self.assertEqual(result["invalid_goal_scorers"], 0)
        self.assertFalse(
            any(
                item["type"] == wk_app.SYNC_NOTIFICATION_SCORER_PLAYER_NOT_IN_SQUAD
                for item in notifications
            ),
            notifications,
        )

    def test_player_database_matching_rejects_ambiguous_initial_surname(self) -> None:
        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO team_squad_players (
                    local_team_id, provider_player_key, api_player_id, player_name, raw_json
                )
                VALUES
                    ('team', '1', 1, 'A. Smith', '{}'),
                    ('team', '2', 2, 'Adam Smith', '{}')
                """
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, event_type, player_name, raw_json
                )
                VALUES ('m001', 'provider:event:1', 'Goal', 'Alex Smith', '{}')
                """
            )
            result = wk_app.verify_player_database_matches(conn)
            notifications = wk_app.active_admin_sync_notifications(conn)
            return result, notifications

        result, notifications = self.run_with_temp_db(scenario)

        self.assertEqual(result["invalid_goal_scorers"], 1)
        self.assertTrue(
            any(
                item["type"] == wk_app.SYNC_NOTIFICATION_SCORER_PLAYER_NOT_IN_SQUAD
                for item in notifications
            ),
            notifications,
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

    def test_admin_reset_password_issues_temporary_and_forces_change(self) -> None:
        def scenario(_conn):
            admin = wk_app.app.test_client()
            player = wk_app.app.test_client()
            # The first account to log in becomes the admin.
            admin.post(
                "/api/auth/login",
                json={"email": "admin.user@talpanetwork.com", "password": "admin-password"},
            )
            player.post(
                "/api/auth/login",
                json={"email": "player.user@talpanetwork.com", "password": "player-password"},
            )
            with wk_app.get_db() as conn:
                player_row = wk_app.execute(
                    conn,
                    "SELECT id FROM users WHERE email = ?",
                    ("player.user@talpanetwork.com",),
                ).fetchone()
            player_id = player_row["id"]

            reset = admin.post(f"/api/admin/users/{player_id}/reset-password", json={})
            temp_password = reset.get_json().get("temporary_password", "")

            old_login = wk_app.app.test_client().post(
                "/api/auth/login",
                json={"email": "player.user@talpanetwork.com", "password": "player-password"},
            )
            temp_client = wk_app.app.test_client()
            temp_login = temp_client.post(
                "/api/auth/login",
                json={"email": "player.user@talpanetwork.com", "password": temp_password},
            )
            change = temp_client.patch(
                "/api/me/password",
                json={
                    "current_password": temp_password,
                    "password": "fresh-password",
                    "confirm_password": "fresh-password",
                },
            )
            me_after = temp_client.get("/api/me").get_json()
            new_login = wk_app.app.test_client().post(
                "/api/auth/login",
                json={"email": "player.user@talpanetwork.com", "password": "fresh-password"},
            )
            return (
                reset.status_code,
                temp_password,
                old_login.status_code,
                temp_login.status_code,
                temp_login.get_json(),
                change.status_code,
                me_after,
                new_login.status_code,
            )

        (
            reset_status,
            temp_password,
            old_login_status,
            temp_login_status,
            temp_login_payload,
            change_status,
            me_after,
            new_login_status,
        ) = self.run_with_temp_db(scenario)

        self.assertEqual(reset_status, 200)
        self.assertGreaterEqual(len(temp_password), wk_app.PASSWORD_MIN_LENGTH)
        self.assertEqual(old_login_status, 401)
        self.assertEqual(temp_login_status, 200)
        self.assertTrue(temp_login_payload["user"]["must_change_password"])
        self.assertEqual(change_status, 200)
        self.assertFalse(me_after["user"]["must_change_password"])
        self.assertEqual(new_login_status, 200)

    def test_non_admin_cannot_reset_password(self) -> None:
        def scenario(_conn):
            admin = wk_app.app.test_client()
            player = wk_app.app.test_client()
            admin.post(
                "/api/auth/login",
                json={"email": "admin.user@talpanetwork.com", "password": "admin-password"},
            )
            player.post(
                "/api/auth/login",
                json={"email": "player.user@talpanetwork.com", "password": "player-password"},
            )
            with wk_app.get_db() as conn:
                admin_row = wk_app.execute(
                    conn,
                    "SELECT id FROM users WHERE email = ?",
                    ("admin.user@talpanetwork.com",),
                ).fetchone()
            forbidden = player.post(f"/api/admin/users/{admin_row['id']}/reset-password", json={})
            return forbidden.status_code

        status = self.run_with_temp_db(scenario)
        self.assertEqual(status, 403)

    def test_forgot_password_no_longer_resets_to_default(self) -> None:
        def scenario(_conn):
            client = wk_app.app.test_client()
            client.post(
                "/api/auth/login",
                json={"email": "known.user@talpanetwork.com", "password": "known-password"},
            )
            forgot = client.post(
                "/api/auth/forgot-password",
                json={"email": "known.user@talpanetwork.com"},
            )
            default_attempt = wk_app.app.test_client().post(
                "/api/auth/login",
                json={
                    "email": "known.user@talpanetwork.com",
                    "password": wk_app.DEFAULT_PASSWORD,
                },
            )
            known_attempt = wk_app.app.test_client().post(
                "/api/auth/login",
                json={"email": "known.user@talpanetwork.com", "password": "known-password"},
            )
            return forgot.status_code, default_attempt.status_code, known_attempt.status_code

        forgot_status, default_status, known_status = self.run_with_temp_db(scenario)
        self.assertEqual(forgot_status, 200)
        self.assertEqual(default_status, 401)
        self.assertEqual(known_status, 200)


if __name__ == "__main__":
    unittest.main()
