from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import call, patch

from backend import app as wk_app
from backend import genai_service


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

    def test_local_sqlite_uses_long_busy_timeout_and_wal(self) -> None:
        def scenario(_conn):
            with wk_app.get_db() as conn:
                busy_timeout = wk_app.execute(conn, "PRAGMA busy_timeout").fetchone()[0]
                journal_mode = wk_app.execute(conn, "PRAGMA journal_mode").fetchone()[0]
            return busy_timeout, journal_mode

        busy_timeout, journal_mode = self.run_with_temp_db(scenario)

        self.assertEqual(busy_timeout, 30000)
        self.assertEqual(journal_mode, "wal")

    def test_vercel_crons_are_hobby_plan_compatible(self) -> None:
        config = json.loads((Path(__file__).resolve().parent.parent / "vercel.json").read_text())
        crons = {item["path"]: item["schedule"] for item in config["crons"]}

        self.assertEqual(crons["/api/cron/api-football-sync"], "0 6 * * *")
        self.assertEqual(crons["/api/cron/api-football-squad-sync"], "0 6 * * *")
        self.assertEqual(crons["/api/cron/newsletters-refresh"], "0 7 * * *")
        self.assertEqual(config["functions"]["api/index.py"]["maxDuration"], 300)

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
            with (
                patch.object(wk_app, "load_world_cup_data", return_value=data),
                patch.object(
                    wk_app,
                    "utc_now",
                    return_value=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
                ),
            ):
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

    def test_daily_sweep_catches_up_to_latest_elapsed_sync_window(self) -> None:
        kickoff = datetime.now(UTC) - wk_app.API_FOOTBALL_POSTMATCH_BUFFER - timedelta(hours=3)
        match = make_match("m001", kickoff)
        data = {"matches": [match], "teams": []}

        def scenario(_conn):
            regular = wk_app.due_api_football_match_attempts(data, limit=1)
            daily = wk_app.due_api_football_match_attempts(data, daily_sweep=True, limit=1)
            return regular, daily

        regular, daily = self.run_with_temp_db(scenario)

        self.assertEqual(regular[0]["attempt_kind"], wk_app.SYNC_ATTEMPT_EARLY_POST_MATCH)
        self.assertEqual(daily[0]["attempt_kind"], wk_app.SYNC_ATTEMPT_SECOND_POST_MATCH)

    def test_daily_sweep_skips_matches_that_already_reached_latest_window(self) -> None:
        kickoff = datetime.now(UTC) - wk_app.API_FOOTBALL_POSTMATCH_BUFFER - timedelta(hours=3)
        match = make_match("m001", kickoff)
        data = {"matches": [match], "teams": []}

        def scenario(conn):
            attempt_id = wk_app.create_provider_sync_attempt(
                conn,
                provider_key=wk_app.API_FOOTBALL_PROVIDER_KEY,
                target_type=wk_app.SYNC_TARGET_MATCH_RESULT,
                target_id="m001",
                attempt_kind=wk_app.SYNC_ATTEMPT_SECOND_POST_MATCH,
                scheduled_for=wk_app.result_sync_scheduled_for(
                    match, wk_app.SYNC_ATTEMPT_SECOND_POST_MATCH
                ),
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
                VALUES (?, ?, 'FT', 1, 0)
                """,
                ("m001", wk_app.API_FOOTBALL_PROVIDER_KEY),
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, event_type, player_name, raw_json
                )
                VALUES (?, 'provider:event:1', 'Goal', 'One', '{}')
                """,
                ("m001",),
            )
            conn.commit()
            return wk_app.due_api_football_match_attempts(data, daily_sweep=True, limit=1)

        candidates = self.run_with_temp_db(scenario)

        self.assertEqual(candidates, [])

    def test_cron_result_sync_uses_daily_sweep_mode(self) -> None:
        previous_token = wk_app.API_FOOTBALL_SYNC_TOKEN
        wk_app.API_FOOTBALL_SYNC_TOKEN = "test-token"
        try:
            with (
                patch.object(wk_app, "load_world_cup_data", return_value={"matches": []}),
                patch.object(
                    wk_app,
                    "run_api_football_completed_sync",
                    return_value={"ok": True, "attempts": [], "synced": [], "skipped": []},
                ) as sync_mock,
            ):
                response = wk_app.app.test_client().get(
                    "/api/cron/api-football-sync",
                    headers={"Authorization": "Bearer test-token"},
                )
        finally:
            wk_app.API_FOOTBALL_SYNC_TOKEN = previous_token

        self.assertEqual(response.status_code, 200)
        sync_mock.assert_called_once_with({"matches": []}, daily_sweep=True)

    def test_cron_squad_sync_refreshes_all_player_squads_without_coaches(self) -> None:
        previous_token = wk_app.API_FOOTBALL_SYNC_TOKEN
        wk_app.API_FOOTBALL_SYNC_TOKEN = "test-token"
        try:
            with (
                patch.object(wk_app, "load_world_cup_data", return_value={"teams": []}),
                patch.object(
                    wk_app,
                    "run_api_football_squad_sync",
                    return_value={"ok": True, "synced": [], "skipped": []},
                ) as sync_mock,
            ):
                response = wk_app.app.test_client().get(
                    "/api/cron/api-football-squad-sync",
                    headers={"Authorization": "Bearer test-token"},
                )
        finally:
            wk_app.API_FOOTBALL_SYNC_TOKEN = previous_token

        self.assertEqual(response.status_code, 200)
        sync_mock.assert_called_once_with(
            {"teams": []},
            force=True,
            limit=48,
            include_coaches=False,
        )

    def test_api_football_squad_limit_is_not_capped_by_recorded_request_count(self) -> None:
        with patch.object(wk_app, "api_football_request_count_today", return_value=10_000):
            limit = wk_app.api_football_squad_team_limit(
                requested_limit=48,
                include_coaches=True,
            )

        self.assertEqual(limit, 48)

    def test_admin_data_sync_button_endpoint_runs_missing_results_without_squads(self) -> None:
        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES (1, 'Admin', 'admin.user@talpanetwork.com', 'x', 1)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_results (
                    match_id, source, status_long, status_short, elapsed, home_score, away_score
                )
                VALUES ('m001', 'api-football', 'Match Finished', 'FT', 90, 2, 1)
                """,
            )
            conn.commit()
            client = wk_app.app.test_client()
            with client.session_transaction() as session:
                session["user_id"] = 1
            with (
                patch.object(
                    wk_app, "load_world_cup_data", return_value={"matches": [], "teams": []}
                ),
                patch.object(
                    wk_app,
                    "run_missing_result_sync_batch",
                    return_value={
                        "ok": True,
                        "dry_run": False,
                        "match_ids": ["m001"],
                        "results": [],
                        "synced": [{"match_id": "m001"}],
                        "attempts": [{"match_id": "m001"}],
                        "skipped": [],
                    },
                ) as result_sync,
                patch.object(wk_app, "run_api_football_squad_sync") as squad_sync,
                patch.object(
                    genai_service,
                    "run_genai_jobs_after_data_sync",
                    return_value={"ok": True, "quiz_jobs": [], "player_jobs": []},
                ) as genai_jobs,
                patch.object(wk_app, "recompute_all_computed_points") as recompute,
            ):
                response = client.post("/api/admin/api-football/data-sync", json={})
            return response, result_sync, squad_sync, genai_jobs, recompute

        response, result_sync, squad_sync, genai_jobs, recompute = self.run_with_temp_db(scenario)
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["synced"], [{"match_id": "m001"}])
        self.assertEqual(payload["genai_jobs"], {"ok": True, "quiz_jobs": [], "player_jobs": []})
        result_sync.assert_called_once_with({"matches": [], "teams": []}, dry_run=False)
        squad_sync.assert_not_called()
        genai_jobs.assert_called_once_with(
            {"matches": [], "teams": []},
            result_sync={
                "ok": True,
                "dry_run": False,
                "match_ids": ["m001"],
                "results": [],
                "synced": [{"match_id": "m001"}],
                "attempts": [{"match_id": "m001"}],
                "skipped": [],
            },
        )
        recompute.assert_called_once()

    def test_admin_data_sync_returns_manual_quiz_fill_when_open_quiz_has_no_label(self) -> None:
        data = {
            "matches": [
                {
                    "id": "m001",
                    "match_number": 33,
                    "home_team_id": "ned",
                    "away_team_id": "usa",
                    "home_team": "Netherlands",
                    "away_team": "Sweden",
                    "quiz": {
                        "question": "Welke speler wordt volgens de FIFA man van de wedstrijd?",
                        "type": "open",
                        "viewership": True,
                    },
                }
            ],
            "teams": [],
        }

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES (1, 'Admin', 'admin.user@talpanetwork.com', 'x', 1)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_results (
                    match_id, source, status_long, status_short, elapsed, home_score, away_score
                )
                VALUES ('m001', 'api-football', 'Match Finished', 'FT', 90, 2, 1)
                """,
            )
            conn.commit()
            client = wk_app.app.test_client()
            with client.session_transaction() as session:
                session["user_id"] = 1
            with (
                patch.object(wk_app, "load_world_cup_data", return_value=data),
                patch.object(
                    wk_app,
                    "run_missing_result_sync_batch",
                    return_value={
                        "ok": True,
                        "dry_run": False,
                        "match_ids": ["m001"],
                        "results": [],
                        "synced": [{"match_id": "m001"}],
                        "attempts": [{"match_id": "m001"}],
                        "skipped": [],
                    },
                ),
                patch.object(wk_app, "recompute_all_computed_points") as recompute,
            ):
                response = client.post("/api/admin/api-football/data-sync", json={})
            return response, recompute

        response, recompute = self.run_with_temp_db(scenario)
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        fills = payload["genai_jobs"]["manual_quiz_fills"]
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0]["match_id"], "m001")
        self.assertEqual(fills[0]["home_team_name"], "Netherlands")
        self.assertEqual(fills[0]["home_team_id"], "ned")
        self.assertEqual(fills[0]["away_team_id"], "usa")
        self.assertTrue(fills[0]["viewership_required"])
        self.assertEqual(fills[0]["choices"], [])
        recompute.assert_called_once()

    def test_admin_data_sync_returns_manual_quiz_fill_for_existing_result_facts(self) -> None:
        data = {
            "matches": [
                {
                    "id": "m33",
                    "match_number": 33,
                    "home_team_id": "ned",
                    "away_team_id": "swe",
                    "home_team": "Netherlands",
                    "away_team": "Sweden",
                    "quiz": {
                        "question": "Welke speler wordt volgens de FIFA man van de wedstrijd?",
                        "type": "open",
                        "viewership": True,
                    },
                }
            ],
            "teams": [],
        }

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES (1, 'Admin', 'admin.user@talpanetwork.com', 'x', 1)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_results (
                    match_id, source, status_long, status_short, elapsed, home_score, away_score
                )
                VALUES ('m33', 'api-football', 'Match Finished', 'FT', 90, 5, 1)
                """,
            )
            conn.commit()
            client = wk_app.app.test_client()
            with client.session_transaction() as session:
                session["user_id"] = 1
            with (
                patch.object(wk_app, "load_world_cup_data", return_value=data),
                patch.object(
                    wk_app,
                    "run_missing_result_sync_batch",
                    return_value={
                        "ok": True,
                        "dry_run": False,
                        "match_ids": [],
                        "results": [],
                        "synced": [],
                        "attempts": [],
                        "skipped": [],
                    },
                ),
                patch.object(wk_app, "recompute_all_computed_points"),
            ):
                response = client.post("/api/admin/api-football/data-sync", json={})
            return response

        response = self.run_with_temp_db(scenario)
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        fill = payload["genai_jobs"]["manual_quiz_fills"][0]
        self.assertEqual(fill["match_id"], "m33")
        self.assertEqual(fill["home_team_id"], "ned")
        self.assertEqual(fill["away_team_id"], "swe")

    def test_admin_can_save_open_quiz_label_without_predefined_choices(self) -> None:
        question = "Welke speler wordt volgens de FIFA man van de wedstrijd?"
        data = {
            "matches": [
                {
                    "id": "m33",
                    "quiz": {
                        "question": question,
                        "type": "open",
                        "viewership": True,
                    },
                }
            ],
            "teams": [],
        }

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES (1, 'Admin', 'admin.user@talpanetwork.com', 'x', 1)
                """,
            )
            conn.commit()
            client = wk_app.app.test_client()
            with client.session_transaction() as session:
                session["user_id"] = 1
            with (
                patch.object(wk_app, "load_world_cup_data", return_value=data),
                patch.object(wk_app, "recompute_all_computed_points"),
            ):
                response = client.patch(
                    "/api/admin/labels/m33/quiz",
                    json={
                        "question": question,
                        "choices": [],
                        "correct_answers": ["Brian Brobbey"],
                        "viewership_answer": 1234567,
                    },
                )
            override = wk_app.execute(
                conn,
                "SELECT * FROM quiz_label_overrides WHERE match_id = 'm33'",
            ).fetchone()
            return response, override

        response, override = self.run_with_temp_db(scenario)
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(override["correct_answers_json"]), ["Brian Brobbey"])
        match = next(item for item in payload["matches"] if item["match_id"] == "m33")
        self.assertEqual(match["quiz"]["correct_answers"], ["Brian Brobbey"])
        self.assertEqual(match["quiz"]["viewership_answer"], 1234567)

    def test_missing_result_batch_recomputes_no_points_per_match(self) -> None:
        data: dict[str, Any] = {"matches": [], "teams": []}
        with (
            patch.object(wk_app, "missing_result_match_ids", return_value=["m001", "m002"]),
            patch.object(
                wk_app,
                "run_api_football_completed_sync",
                side_effect=[
                    {"ok": True, "synced": [{"match_id": "m001"}]},
                    {"ok": True, "synced": [{"match_id": "m002"}]},
                ],
            ) as sync,
        ):
            result = wk_app.run_missing_result_sync_batch(data)

        self.assertTrue(result["ok"])
        self.assertEqual(result["match_ids"], ["m001", "m002"])
        self.assertEqual(
            sync.call_args_list,
            [
                call(
                    data,
                    force=True,
                    dry_run=False,
                    limit=1,
                    match_id="m001",
                    recompute_points=False,
                ),
                call(
                    data,
                    force=True,
                    dry_run=False,
                    limit=1,
                    match_id="m002",
                    recompute_points=False,
                ),
            ],
        )

    def test_admin_data_sync_dry_run_does_not_run_genai_jobs(self) -> None:
        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES (1, 'Admin', 'admin.user@talpanetwork.com', 'x', 1)
                """,
            )
            conn.commit()
            client = wk_app.app.test_client()
            with client.session_transaction() as session:
                session["user_id"] = 1
            with (
                patch.object(
                    wk_app, "load_world_cup_data", return_value={"matches": [], "teams": []}
                ),
                patch.object(
                    wk_app,
                    "run_missing_result_sync_batch",
                    return_value={
                        "ok": True,
                        "dry_run": True,
                        "match_ids": ["m001"],
                        "results": [],
                        "synced": [{"match_id": "m001"}],
                        "attempts": [],
                        "skipped": [],
                    },
                ),
                patch.object(wk_app, "run_api_football_squad_sync") as squad_sync,
                patch.object(genai_service, "run_genai_jobs_after_data_sync") as genai_jobs,
                patch.object(wk_app, "recompute_all_computed_points") as recompute,
            ):
                response = client.post("/api/admin/api-football/data-sync", json={"dry_run": True})
            return response, squad_sync, genai_jobs, recompute

        response, squad_sync, genai_jobs, recompute = self.run_with_temp_db(scenario)
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertIsNone(payload["genai_jobs"])
        squad_sync.assert_not_called()
        genai_jobs.assert_not_called()
        recompute.assert_not_called()

    def test_database_recompute_points_endpoint_uses_sync_token(self) -> None:
        previous_token = wk_app.API_FOOTBALL_SYNC_TOKEN
        wk_app.API_FOOTBALL_SYNC_TOKEN = "test-token"

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES (1, 'Admin', 'admin.user@talpanetwork.com', 'x', 1)
                """,
            )
            conn.commit()
            client = wk_app.app.test_client()
            with (
                patch.object(
                    wk_app,
                    "load_world_cup_data",
                    return_value={"matches": [], "teams": [], "groups": [], "venues": []},
                ) as load_data,
                patch.object(
                    wk_app,
                    "recompute_all_computed_points",
                    return_value={"invalid_goal_scorers": 0},
                ) as recompute,
            ):
                forbidden = client.post("/api/admin/database/recompute-points")
                response = client.post(
                    "/api/admin/database/recompute-points",
                    headers={"Authorization": "Bearer test-token"},
                )
            return forbidden, response, load_data, recompute

        try:
            forbidden, response, load_data, recompute = self.run_with_temp_db(scenario)
        finally:
            wk_app.API_FOOTBALL_SYNC_TOKEN = previous_token

        payload = response.get_json()
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["computed_points_updated"])
        self.assertEqual(payload["leaderboard_computed_point_rows"], 0)
        load_data.assert_called_once()
        recompute.assert_called_once_with({"matches": [], "teams": [], "groups": [], "venues": []})

    def test_players_only_squad_sync_populates_all_due_player_rows(self) -> None:
        data = {
            "teams": [
                {"id": "esp", "name": "Spain", "code": "ESP"},
                {"id": "cpv", "name": "Cape Verde", "code": "CPV"},
            ],
            "matches": [],
            "groups": [],
            "venues": [],
            "meta": {},
        }
        squad_payloads = {
            9: {
                "response": [
                    {
                        "team": {"id": 9},
                        "players": [{"id": 101, "name": "Lamine Yamal"}],
                    }
                ]
            },
            1504: {
                "response": [
                    {
                        "team": {"id": 1504},
                        "players": [{"id": 202, "name": "Ryan Mendes"}],
                    }
                ]
            },
        }

        def fake_get(endpoint, params):
            self.assertEqual(endpoint, "players/squads")
            return squad_payloads[params["team"]]

        def scenario(conn):
            wk_app.upsert_api_football_team_link(conn, "esp", 9, "Spain", "test")
            wk_app.upsert_api_football_team_link(conn, "cpv", 1504, "Cabo Verde", "test")
            conn.commit()
            with patch.object(wk_app, "api_football_get", side_effect=fake_get):
                result = wk_app.run_api_football_squad_sync(
                    data,
                    force=True,
                    limit=48,
                    include_coaches=False,
                )
            rows = wk_app.execute(
                conn,
                """
                SELECT local_team_id, player_name
                FROM team_squad_players
                ORDER BY local_team_id, player_name
                """,
            ).fetchall()
            return result, rows

        previous_key = wk_app.API_FOOTBALL_KEY
        wk_app.API_FOOTBALL_KEY = "test-key"
        try:
            result, rows = self.run_with_temp_db(scenario)
        finally:
            wk_app.API_FOOTBALL_KEY = previous_key

        self.assertTrue(result["ok"])
        self.assertFalse(result["include_coaches"])
        self.assertEqual(len(result["synced"]), 2)
        self.assertEqual(
            [(row["local_team_id"], row["player_name"]) for row in rows],
            [("cpv", "Ryan Mendes"), ("esp", "Lamine Yamal")],
        )

    def test_squad_sync_does_not_hold_write_transaction_while_logging_requests(
        self,
    ) -> None:
        data = {
            "teams": [
                {"id": "esp", "name": "Spain", "code": "ESP"},
                {"id": "cpv", "name": "Cape Verde", "code": "CPV"},
            ],
            "matches": [],
            "groups": [],
            "venues": [],
            "meta": {},
        }
        squad_payloads = {
            9: {
                "response": [
                    {
                        "team": {"id": 9},
                        "players": [{"id": 101, "name": "Lamine Yamal"}],
                    }
                ]
            },
            1504: {
                "response": [
                    {
                        "team": {"id": 1504},
                        "players": [{"id": 202, "name": "Ryan Mendes"}],
                    }
                ]
            },
        }

        def fake_get(endpoint, params):
            wk_app.record_api_football_request(endpoint, params, 200, True)
            return squad_payloads[params["team"]]

        def scenario(conn):
            wk_app.upsert_api_football_team_link(conn, "esp", 9, "Spain", "test")
            wk_app.upsert_api_football_team_link(conn, "cpv", 1504, "Cabo Verde", "test")
            conn.commit()
            with patch.object(wk_app, "api_football_get", side_effect=fake_get):
                result = wk_app.run_api_football_squad_sync(
                    data,
                    force=True,
                    limit=48,
                    include_coaches=False,
                )
            request_count = wk_app.execute(
                conn,
                "SELECT COUNT(*) AS count FROM api_football_requests",
            ).fetchone()["count"]
            return result, request_count

        previous_key = wk_app.API_FOOTBALL_KEY
        wk_app.API_FOOTBALL_KEY = "test-key"
        try:
            result, request_count = self.run_with_temp_db(scenario)
        finally:
            wk_app.API_FOOTBALL_KEY = previous_key

        self.assertTrue(result["ok"])
        self.assertEqual(len(result["synced"]), 2)
        self.assertEqual(request_count, 2)

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

    def test_fixture_linking_accepts_cape_verde_islands_provider_name(self) -> None:
        kickoff = datetime(2026, 6, 15, 16, 0, tzinfo=UTC)
        match = make_match("m013", kickoff, home_team_id="esp", away_team_id="cpv")
        data = {
            "matches": [match],
            "teams": [
                {"id": "esp", "name": "Spain", "code": "ESP"},
                {"id": "cpv", "name": "Cape Verde", "code": "CPV"},
            ],
            "groups": [],
            "venues": [],
            "meta": {},
        }
        fixture = {
            "fixture": {"id": 456, "date": "2026-06-15T16:00:00+00:00"},
            "teams": {
                "home": {"id": 9, "name": "Spain"},
                "away": {"id": 1533, "name": "Cape Verde Islands"},
            },
        }

        def scenario(_conn):
            with patch.object(wk_app, "api_football_get", return_value={"response": [fixture]}):
                linking = wk_app.api_football_link_fixtures(data)
            links = wk_app.api_football_fixture_links()
            with wk_app.get_db() as conn:
                team_link = wk_app.execute(
                    conn,
                    """
                    SELECT local_team_id, api_team_name
                    FROM api_football_team_links
                    WHERE local_team_id = 'cpv'
                    """,
                ).fetchone()
            return linking, links, team_link

        linking, links, team_link = self.run_with_temp_db(scenario)

        self.assertEqual(linking["linked"], 1)
        self.assertEqual(links["m013"], 456)
        self.assertEqual(team_link["api_team_name"], "Cape Verde Islands")

    def test_all_provider_world_cup_team_names_map_to_local_teams(self) -> None:
        data = {
            "teams": [
                {"id": "alg", "name": "Algeria", "code": "ALG"},
                {"id": "arg", "name": "Argentina", "code": "ARG"},
                {"id": "aus", "name": "Australia", "code": "AUS"},
                {"id": "aut", "name": "Austria", "code": "AUT"},
                {"id": "bel", "name": "Belgium", "code": "BEL"},
                {"id": "bih", "name": "Bosnia and Herzegovina", "code": "BIH"},
                {"id": "bra", "name": "Brazil", "code": "BRA"},
                {"id": "can", "name": "Canada", "code": "CAN"},
                {"id": "civ", "name": "Cote d'Ivoire", "code": "CIV"},
                {"id": "cod", "name": "DR Congo", "code": "COD"},
                {"id": "col", "name": "Colombia", "code": "COL"},
                {"id": "cpv", "name": "Cape Verde", "code": "CPV"},
                {"id": "cro", "name": "Croatia", "code": "CRO"},
                {"id": "cuw", "name": "Curacao", "code": "CUW"},
                {"id": "cze", "name": "Czech Republic", "code": "CZE"},
                {"id": "ecu", "name": "Ecuador", "code": "ECU"},
                {"id": "egy", "name": "Egypt", "code": "EGY"},
                {"id": "eng", "name": "England", "code": "ENG"},
                {"id": "esp", "name": "Spain", "code": "ESP"},
                {"id": "fra", "name": "France", "code": "FRA"},
                {"id": "ger", "name": "Germany", "code": "GER"},
                {"id": "gha", "name": "Ghana", "code": "GHA"},
                {"id": "hai", "name": "Haiti", "code": "HAI"},
                {"id": "irn", "name": "Iran", "code": "IRN"},
                {"id": "irq", "name": "Iraq", "code": "IRQ"},
                {"id": "jor", "name": "Jordan", "code": "JOR"},
                {"id": "jpn", "name": "Japan", "code": "JPN"},
                {"id": "kor", "name": "Korea Republic", "code": "KOR"},
                {"id": "ksa", "name": "Saudi Arabia", "code": "KSA"},
                {"id": "mar", "name": "Morocco", "code": "MAR"},
                {"id": "mex", "name": "Mexico", "code": "MEX"},
                {"id": "ned", "name": "Netherlands", "code": "NED"},
                {"id": "nor", "name": "Norway", "code": "NOR"},
                {"id": "nzl", "name": "New Zealand", "code": "NZL"},
                {"id": "pan", "name": "Panama", "code": "PAN"},
                {"id": "par", "name": "Paraguay", "code": "PAR"},
                {"id": "por", "name": "Portugal", "code": "POR"},
                {"id": "qat", "name": "Qatar", "code": "QAT"},
                {"id": "rsa", "name": "South Africa", "code": "RSA"},
                {"id": "sco", "name": "Scotland", "code": "SCO"},
                {"id": "sen", "name": "Senegal", "code": "SEN"},
                {"id": "sui", "name": "Switzerland", "code": "SUI"},
                {"id": "swe", "name": "Sweden", "code": "SWE"},
                {"id": "tun", "name": "Tunisia", "code": "TUN"},
                {"id": "tur", "name": "Turkey", "code": "TUR"},
                {"id": "uru", "name": "Uruguay", "code": "URU"},
                {"id": "usa", "name": "United States", "code": "USA"},
                {"id": "uzb", "name": "Uzbekistan", "code": "UZB"},
            ]
        }
        provider_names = {
            "Algeria": "alg",
            "Argentina": "arg",
            "Australia": "aus",
            "Austria": "aut",
            "Belgium": "bel",
            "Bosnia & Herzegovina": "bih",
            "Brazil": "bra",
            "Canada": "can",
            "Cape Verde Islands": "cpv",
            "Colombia": "col",
            "Congo DR": "cod",
            "Croatia": "cro",
            "Curaçao": "cuw",
            "Czechia": "cze",
            "Ecuador": "ecu",
            "Egypt": "egy",
            "England": "eng",
            "France": "fra",
            "Germany": "ger",
            "Ghana": "gha",
            "Haiti": "hai",
            "Iran": "irn",
            "Iraq": "irq",
            "Ivory Coast": "civ",
            "Japan": "jpn",
            "Jordan": "jor",
            "Morocco": "mar",
            "Mexico": "mex",
            "Netherlands": "ned",
            "New Zealand": "nzl",
            "Norway": "nor",
            "Panama": "pan",
            "Paraguay": "par",
            "Portugal": "por",
            "Qatar": "qat",
            "Saudi Arabia": "ksa",
            "Scotland": "sco",
            "Senegal": "sen",
            "South Africa": "rsa",
            "South Korea": "kor",
            "Spain": "esp",
            "Sweden": "swe",
            "Switzerland": "sui",
            "Tunisia": "tun",
            "Türkiye": "tur",
            "Uruguay": "uru",
            "USA": "usa",
            "Uzbekistan": "uzb",
        }

        mapped = {
            provider_name: wk_app.local_team_id_from_name(provider_name, data)
            for provider_name in provider_names
        }

        self.assertEqual(mapped, provider_names)

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

    def test_fixture_snapshot_uses_player_name_when_provider_player_id_is_zero(self) -> None:
        kickoff = datetime(2026, 6, 11, 18, 0, tzinfo=UTC)
        match = make_match("m20", kickoff)
        data = {
            "matches": [match],
            "teams": [
                {"id": "ned", "name": "Netherlands", "code": "NED"},
                {"id": "usa", "name": "United States", "code": "USA"},
            ],
        }

        def player_block(name):
            return {
                "player": {"id": 0, "name": name},
                "statistics": [
                    {
                        "games": {"minutes": 90, "position": "M"},
                        "goals": {"total": 0, "assists": 0},
                        "cards": {"yellow": 0, "red": 0},
                    }
                ],
            }

        fixture = {
            "fixture": {"id": 456, "status": {"long": "Match Finished", "short": "FT"}},
            "teams": {
                "home": {"id": 1, "name": "Netherlands"},
                "away": {"id": 2, "name": "United States"},
            },
            "goals": {"home": 1, "away": 0},
            "events": [],
            "players": [
                {
                    "team": {"id": 1, "name": "Netherlands"},
                    "players": [player_block("Player One"), player_block("Player Two")],
                }
            ],
        }

        def scenario(conn):
            wk_app.store_api_football_fixture_snapshot(conn, match, fixture, data)
            return wk_app.execute(
                conn,
                """
                SELECT provider_player_key, player_name
                FROM player_match_stats
                WHERE match_id = ?
                ORDER BY player_name
                """,
                ("m20",),
            ).fetchall()

        rows = self.run_with_temp_db(scenario)

        self.assertEqual(
            [(row["provider_player_key"], row["player_name"]) for row in rows],
            [("player one", "Player One"), ("player two", "Player Two")],
        )

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

    def scoring_data(self, done: bool = True) -> dict[str, Any]:
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

    def test_user_match_points_include_traceable_striker_points(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, event_type, player_name, raw_json
                )
                VALUES
                    ('m001', 'provider:event:1', 'Goal', 'Cody Gakpo', '{}'),
                    ('m001', 'provider:event:2', 'Goal', 'Cody Gakpo', '{}')
                """,
            )
            conn.commit()
            return wk_app.user_match_points_by_match(
                data,
                {"m001": {"home_score": 2, "away_score": 1}},
                {},
                [],
                ["Cody Gakpo"],
            )

        points_by_match = self.run_with_temp_db(scenario)
        points = points_by_match["m001"]

        self.assertEqual(points["striker_points"], 12)
        self.assertEqual(points["total_points"], 24)
        self.assertEqual(
            points["striker_scorers"],
            [{"name": "Cody Gakpo", "goals": 2, "points": 12}],
        )

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
        self.assertEqual(badge_notifications[0]["badges"][0]["label"], "Perfect Score")
        self.assertIn("mark", badge_notifications[0]["badges"][0])

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
                """,
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
        self.assertNotEqual(
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

    def test_daily_recap_dagscore_shows_top_five_positive_scores(self) -> None:
        target_match = make_match("m001", datetime(2026, 6, 11, 19, 0, tzinfo=UTC))
        target_match["status"] = "completed"
        target_match["home_score"] = 1
        target_match["away_score"] = 0
        data = {
            "matches": [target_match],
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
                    (3, 'Chris', 'chris@example.com', 'x', 0),
                    (4, 'Dina', 'dina@example.com', 'x', 0),
                    (5, 'Evi', 'evi@example.com', 'x', 0),
                    (6, 'Fien', 'fien@example.com', 'x', 0)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_predictions (user_id, match_id, home_score, away_score)
                VALUES
                    (1, 'm001', 1, 0),
                    (2, 'm001', 1, 0),
                    (3, 'm001', 1, 0),
                    (4, 'm001', 1, 0),
                    (5, 'm001', 1, 0),
                    (6, 'm001', 1, 0)
                """,
            )
            conn.commit()
            return wk_app.build_daily_recap(
                data,
                now=datetime(2026, 6, 12, 4, 30, tzinfo=UTC),
                leaderboard=[],
            )

        recap = self.run_with_temp_db(scenario)

        self.assertEqual(
            [row["name"] for row in recap["top_players"]],
            ["Anna", "Bram", "Chris", "Dina", "Evi"],
        )
        self.assertTrue(all(row["points"] > 0 for row in recap["top_players"]))

    def test_daily_recap_dagscore_includes_all_session_match_points(self) -> None:
        target_match = make_match("m001", datetime(2026, 6, 11, 19, 0, tzinfo=UTC))
        target_match["status"] = "completed"
        target_match["home_score"] = 1
        target_match["away_score"] = 0
        target_match["quiz"] = {
            "question": "Scoort Nederland?",
            "type": "yes_no",
            "choices": ["ja", "nee"],
            "correct_answers": ["ja"],
        }
        data = {
            "matches": [target_match],
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
                VALUES (1, 'Anna', 'anna@example.com', 'x', 0)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_predictions (user_id, match_id, home_score, away_score)
                VALUES (1, 'm001', 1, 0)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO quiz_predictions (user_id, match_id, answer)
                VALUES (1, 'm001', 'ja')
                """,
            )
            wk_app.execute(
                conn,
                "INSERT INTO leeuwtje_predictions (user_id, match_id) VALUES (1, 'm001')",
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO top_scorer_predictions (
                    user_id, player_name, striker_name_1
                ) VALUES (1, 'Other Player', 'Cody Gakpo')
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, player_name, event_type, raw_json
                ) VALUES ('m001', 'goal-1', 'Cody Gakpo', 'Goal', '{}')
                """,
            )
            conn.commit()
            return wk_app.build_daily_recap(
                data,
                now=datetime(2026, 6, 12, 4, 30, tzinfo=UTC),
                leaderboard=[],
            )

        recap = self.run_with_temp_db(scenario)

        self.assertEqual(recap["top_players"][0]["name"], "Anna")
        self.assertEqual(recap["top_players"][0]["points"], 33)

    def test_matchday_summary_uses_us_timezone_playing_window(self) -> None:
        evening_match = make_match("m001", datetime(2026, 6, 11, 16, 0, tzinfo=UTC))
        overnight_match = make_match("m002", datetime(2026, 6, 12, 1, 30, tzinfo=UTC))
        daytime_match = make_match("m003", datetime(2026, 6, 12, 10, 0, tzinfo=UTC))
        next_evening_match = make_match("m004", datetime(2026, 6, 12, 16, 0, tzinfo=UTC))
        data = {
            "matches": [evening_match, overnight_match, daytime_match, next_evening_match],
            "teams": [
                {"id": "ned", "name": "Netherlands", "code": "NED"},
                {"id": "usa", "name": "United States", "code": "USA"},
            ],
            "groups": [{"id": "A", "teams": ["ned", "usa"]}],
            "venues": [],
            "meta": {},
        }

        summary = self.run_with_temp_db(
            lambda _conn: wk_app.build_matchday_summary(
                data,
                now=datetime(2026, 6, 11, 18, 0, tzinfo=UTC),
            )
        )

        self.assertEqual([match["id"] for match in summary["matches"]], ["m001", "m002"])

    def test_matchday_summary_stays_on_evening_session_after_midnight(self) -> None:
        evening_match = make_match("m001", datetime(2026, 6, 11, 16, 0, tzinfo=UTC))
        overnight_match = make_match("m002", datetime(2026, 6, 11, 23, 30, tzinfo=UTC))
        next_evening_match = make_match("m003", datetime(2026, 6, 12, 16, 0, tzinfo=UTC))
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

        summary = self.run_with_temp_db(
            lambda _conn: wk_app.build_matchday_summary(
                data,
                now=datetime(2026, 6, 11, 23, 45, tzinfo=UTC),
            )
        )

        self.assertEqual(summary["date"], "2026-06-11")
        self.assertEqual([match["id"] for match in summary["matches"]], ["m001", "m002"])

    def test_matchday_summary_exposes_sessions_and_completed_points(self) -> None:
        completed_match = make_match("m001", datetime(2026, 6, 11, 19, 0, tzinfo=UTC))
        future_match = make_match("m002", datetime(2026, 6, 12, 19, 0, tzinfo=UTC))
        completed_match["status"] = "completed"
        completed_match["home_score"] = 2
        completed_match["away_score"] = 1
        future_match["status"] = "scheduled"
        data = {
            "matches": [completed_match, future_match],
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
            wk_app.execute(
                conn,
                """
                INSERT INTO match_predictions (user_id, match_id, home_score, away_score)
                VALUES (1, 'm001', 2, 1)
                """,
            )
            conn.commit()
            return wk_app.build_matchday_summary(
                data,
                user_id=1,
                now=datetime(2026, 6, 12, 12, 0, tzinfo=UTC),
            )

        summary = self.run_with_temp_db(scenario)

        self.assertEqual(
            [session["date"] for session in summary["sessions"]], ["2026-06-11", "2026-06-12"]
        )
        self.assertEqual(summary["date"], "2026-06-12")
        historic_match = summary["sessions"][0]["matches"][0]
        self.assertTrue(summary["sessions"][0]["is_historic"])
        self.assertTrue(historic_match["completed"])
        self.assertEqual(historic_match["home_score"], 2)
        self.assertEqual(historic_match["away_score"], 1)
        self.assertEqual(historic_match["my_prediction"], {"home_score": 2, "away_score": 1})
        self.assertEqual(historic_match["my_points"]["total_points"], 12)

    def test_matchday_match_detail_requires_locked_predictions(self) -> None:
        match = make_match("m001", datetime(2026, 6, 11, 20, 0, tzinfo=UTC))
        match["status"] = "scheduled"
        data = {
            "matches": [match],
            "teams": [
                {"id": "ned", "name": "Netherlands", "code": "NED"},
                {"id": "usa", "name": "United States", "code": "USA"},
            ],
            "groups": [{"id": "A", "teams": ["ned", "usa"]}],
            "venues": [],
            "meta": {},
        }

        detail, error = self.run_with_temp_db(
            lambda _conn: wk_app.matchday_match_detail(
                data,
                "m001",
                now=datetime(2026, 6, 11, 18, 30, tzinfo=UTC),
            )
        )

        self.assertIsNone(detail)
        self.assertEqual(error, "not_locked")

    def test_matchday_match_detail_groups_predictions_and_quiz_answers(self) -> None:
        match = make_match("m001", datetime(2026, 6, 11, 20, 0, tzinfo=UTC))
        match["status"] = "scheduled"
        match["quiz"] = {
            "question": "Scoort Nederland?",
            "type": "yes_no",
            "choices": ["ja", "nee"],
        }
        data = {
            "matches": [match],
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
                    (1, 'm001', 0, 0),
                    (2, 'm001', 1, 0),
                    (3, 'm001', 0, 0)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO quiz_predictions (user_id, match_id, answer)
                VALUES
                    (1, 'm001', 'ja'),
                    (2, 'm001', 'nee')
                """,
            )
            wk_app.execute(
                conn,
                "INSERT INTO leeuwtje_predictions (user_id, match_id) VALUES (2, 'm001')",
            )
            conn.commit()
            return wk_app.matchday_match_detail(
                data,
                "m001",
                now=datetime(2026, 6, 11, 19, 30, tzinfo=UTC),
            )

        detail, error = self.run_with_temp_db(scenario)

        self.assertIsNone(error)
        self.assertEqual(detail["match"]["prediction_count"], 3)
        self.assertEqual(detail["match"]["home_win_count"], 1)
        self.assertEqual(detail["match"]["draw_count"], 2)
        self.assertEqual(
            [group["score_label"] for group in detail["score_groups"]],
            ["0 - 0", "1 - 0"],
        )
        self.assertEqual(
            [row["name"] for row in detail["score_groups"][0]["predictions"]],
            ["Anna", "Chris"],
        )
        self.assertTrue(detail["score_groups"][1]["predictions"][0]["leeuwtje"])
        self.assertEqual(
            [group["answer"] for group in detail["quiz_answer_groups"]],
            ["ja", "nee"],
        )

    def test_matchday_match_detail_includes_points_after_result_sync(self) -> None:
        match = make_match("m001", datetime(2026, 6, 11, 20, 0, tzinfo=UTC))
        match["status"] = "completed"
        match["home_score"] = 1
        match["away_score"] = 0
        match["quiz"] = {
            "question": "Scoort Nederland?",
            "type": "yes_no",
            "choices": ["ja", "nee"],
            "correct_answers": ["ja"],
        }
        data = {
            "matches": [match],
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
                VALUES (1, 'Anna', 'anna@example.com', 'x', 0)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_predictions (user_id, match_id, home_score, away_score)
                VALUES (1, 'm001', 1, 0)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO quiz_predictions (user_id, match_id, answer)
                VALUES (1, 'm001', 'ja')
                """,
            )
            wk_app.execute(
                conn,
                "INSERT INTO leeuwtje_predictions (user_id, match_id) VALUES (1, 'm001')",
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO top_scorer_predictions (
                    user_id, player_name, striker_name_1
                ) VALUES (1, 'Other Player', 'Cody Gakpo')
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, player_name, event_type, raw_json
                ) VALUES ('m001', 'goal-1', 'Cody Gakpo', 'Goal', '{}')
                """,
            )
            conn.commit()
            return wk_app.matchday_match_detail(
                data,
                "m001",
                user_id=1,
                now=datetime(2026, 6, 11, 21, 30, tzinfo=UTC),
            )

        detail, error = self.run_with_temp_db(scenario)

        self.assertIsNone(error)
        points = detail["predictions"][0]["points"]
        self.assertEqual(points["score_points"], 12)
        self.assertEqual(points["leeuwtje_points"], 12)
        self.assertEqual(points["quiz_points"], 3)
        self.assertEqual(points["striker_points"], 6)
        self.assertEqual(points["total_points"], 33)
        self.assertEqual(points["striker_scorers"][0]["name"], "Cody Gakpo")
        self.assertEqual(detail["match"]["my_prediction"], {"home_score": 1, "away_score": 0})
        self.assertEqual(detail["match"]["my_points"]["total_points"], 33)

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
        now = datetime(2026, 6, 12, 4, 30, tzinfo=UTC)

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
            recap = wk_app.build_daily_recap(
                data,
                now=now,
                leaderboard=[],
            )
            leaderboard = wk_app.build_leaderboard(
                data,
                now=now,
                use_computed_points=False,
            )
            return recap, leaderboard

        recap, leaderboard = self.run_with_temp_db(scenario)

        movers = {row["name"]: row["rank_movement"] for row in recap["top_movers"]}
        self.assertEqual(movers["Chris"], 2)
        self.assertEqual(movers["Anna"], -1)
        self.assertEqual(movers["Bram"], -1)
        self.assertEqual([row["name"] for row in recap["top_winners"]], ["Chris"])
        self.assertEqual([row["name"] for row in recap["top_losers"]], ["Anna", "Bram"])
        leaderboard_movers = {row["name"]: row["rank_movement"] for row in leaderboard}
        self.assertEqual(leaderboard_movers["Chris"], 2)
        self.assertEqual(leaderboard_movers["Anna"], -1)
        self.assertEqual(leaderboard_movers["Bram"], -1)

    def test_daily_recap_ignores_supplied_leaderboard_movements(self) -> None:
        target_match = make_match("m001", datetime(2026, 6, 11, 19, 0, tzinfo=UTC))
        target_match["status"] = "completed"
        target_match["home_score"] = 1
        target_match["away_score"] = 0
        data = {
            "matches": [target_match],
            "teams": [
                {"id": "ned", "name": "Netherlands", "code": "NED"},
                {"id": "usa", "name": "United States", "code": "USA"},
            ],
            "groups": [{"id": "A", "teams": ["ned", "usa"]}],
            "venues": [],
            "meta": {},
        }
        leaderboard = [
            {
                "user_id": 1,
                "name": "Karel",
                "rank": 4,
                "rank_previous": 9,
                "rank_movement": 5,
            },
            {
                "user_id": 2,
                "name": "Olivier",
                "rank": 2,
                "rank_previous": 1,
                "rank_movement": -1,
            },
        ]

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES
                    (1, 'Karel', 'karel@example.com', 'x', 0),
                    (2, 'Olivier', 'olivier@example.com', 'x', 0)
                """,
            )
            conn.commit()
            return wk_app.build_daily_recap(
                data,
                now=datetime(2026, 6, 12, 4, 30, tzinfo=UTC),
                leaderboard=leaderboard,
            )

        recap = self.run_with_temp_db(scenario)

        self.assertEqual(recap["top_winners"], [])
        self.assertEqual(recap["top_losers"], [])

    def test_daily_recap_day_scores_include_all_active_players_and_breakdowns(self) -> None:
        target_match = make_match("m001", datetime(2026, 6, 11, 19, 0, tzinfo=UTC))
        target_match["status"] = "completed"
        target_match["home_score"] = 1
        target_match["away_score"] = 0
        data = {
            "matches": [target_match],
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
                    (2, 'Bram', 'bram@example.com', 'x', 0)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_predictions (user_id, match_id, home_score, away_score)
                VALUES (1, 'm001', 1, 0)
                """,
            )
            conn.commit()
            return wk_app.build_daily_recap(
                data,
                now=datetime(2026, 6, 12, 4, 30, tzinfo=UTC),
                leaderboard=[],
            )

        recap = self.run_with_temp_db(scenario)

        self.assertEqual([row["name"] for row in recap["day_scores"]], ["Anna", "Bram"])
        self.assertEqual([row["points"] for row in recap["day_scores"]], [12, 0])
        self.assertEqual(recap["day_scores"][0]["matches"][0]["match_id"], "m001")
        self.assertEqual(recap["day_scores"][0]["matches"][0]["points"]["total_points"], 12)
        self.assertEqual(recap["day_scores"][1]["matches"][0]["points"]["total_points"], 0)

    def test_leaderboard_leeuwtjes_show_available_not_future_assignments(self) -> None:
        completed_match = make_match("m001", datetime(2026, 6, 11, 18, 0, tzinfo=UTC))
        future_match = make_match("m002", datetime(2026, 6, 12, 18, 0, tzinfo=UTC))
        completed_match["status"] = "completed"
        completed_match["home_score"] = 1
        completed_match["away_score"] = 0
        data = {
            "matches": [completed_match, future_match],
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
                VALUES (1, 'Anna', 'anna@example.com', 'x', 0)
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO leeuwtje_predictions (user_id, match_id)
                VALUES (1, 'm001'), (1, 'm002')
                """,
            )
            conn.commit()
            return wk_app.build_leaderboard(
                data,
                now=datetime(2026, 6, 12, 12, 0, tzinfo=UTC),
                use_computed_points=False,
            )[0]

        row = self.run_with_temp_db(scenario)

        self.assertEqual(row["leeuwtjes_used"], 1)
        self.assertEqual(row["leeuwtjes_assigned"], 2)
        self.assertEqual(row["leeuwtjes_available"], 4)
        self.assertEqual(row["leeuwtjes_total"], 5)

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
                    facts_revision_key=f"{wk_app.SCORING_REVISION}:test",
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

    def test_leaderboard_ignores_stale_stored_computed_points(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            self.seed_scoring_user(conn)
            for category, points in {
                "match_score_points": 999,
                "group_position_points": 0,
                "quiz_points": 0,
                "winner_points": 0,
                "top_scorer_points": 0,
                "striker_points": 0,
                "leeuwtje_points": 0,
            }.items():
                wk_app.upsert_computed_point(
                    conn,
                    user_id=1,
                    scope_type="leaderboard",
                    scope_id="current",
                    category=category,
                    points=points,
                    facts_revision_key="old-scoring-code:stale",
                )
            conn.commit()
            live = wk_app.build_leaderboard(data, use_computed_points=False)[0]
            stored = wk_app.build_leaderboard(data, use_computed_points=True)[0]
            return live, stored

        live, stored = self.run_with_temp_db(scenario)

        self.assertEqual(stored["points"], live["points"])
        self.assertNotEqual(stored["points"], 999)

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

    def test_admin_can_dismiss_sync_issue_notification(self) -> None:
        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO users (id, name, email, password_hash, is_admin)
                VALUES (1, 'Admin', 'admin.user@talpanetwork.com', 'x', 1)
                """,
            )
            wk_app.create_admin_sync_notification(
                conn,
                notification_type="provider_request_failed",
                target_type=wk_app.SYNC_TARGET_MATCH_RESULT,
                target_id="m001",
                title="Provider failed",
                body="Retry later",
            )
            conn.commit()
            notification = wk_app.active_admin_sync_notifications(conn)[0]
            client = wk_app.app.test_client()
            with client.session_transaction() as session:
                session["user_id"] = 1
            response = client.post(
                f"/api/admin/notifications/sync-issues/{notification['id']}/dismiss",
                json={},
            )
            remaining = wk_app.active_admin_sync_notifications(conn)
            return response, remaining

        response, remaining = self.run_with_temp_db(scenario)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(remaining, [])

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

    def test_genai_config_defaults_to_disabled_without_mistral_key(self) -> None:
        with patch.dict(
            wk_app.os.environ,
            {
                "GENAI_PROVIDER": "mistral",
                "GENAI_MODEL": "test-model",
                "GENAI_TIMEOUT_SECONDS": "7",
            },
            clear=False,
        ):
            wk_app.os.environ.pop("MISTRAL_API_KEY", None)
            config = genai_service.genai_config()

        self.assertEqual(config["provider_key"], "mistral")
        self.assertEqual(config["model"], "test-model")
        self.assertEqual(config["timeout_seconds"], 7)
        self.assertFalse(config["enabled"])
        self.assertEqual(config["disabled_reason"], "missing_mistral_api_key")

    def test_genai_config_disables_jobs_when_parser_dependency_is_missing(self) -> None:
        with (
            patch.object(genai_service, "PYDANTIC_IMPORT_ERROR", "No module named pydantic"),
            patch.dict(
                wk_app.os.environ,
                {
                    "GENAI_PROVIDER": "mistral",
                    "MISTRAL_API_KEY": "test-key",
                },
                clear=False,
            ),
        ):
            config = genai_service.genai_config()

        self.assertFalse(config["enabled"])
        self.assertEqual(config["disabled_reason"], "missing_pydantic")

    def test_genai_config_enables_mistral_when_key_is_present(self) -> None:
        with patch.dict(
            wk_app.os.environ,
            {
                "GENAI_PROVIDER": "mistral",
                "MISTRAL_API_KEY": "test-key",
                "GENAI_MODEL": "test-model",
                "GENAI_TIMEOUT_SECONDS": "not-a-number",
            },
            clear=False,
        ):
            config = genai_service.genai_config()

        self.assertTrue(config["enabled"])
        self.assertEqual(config["api_key"], "test-key")
        self.assertEqual(config["timeout_seconds"], genai_service.GENAI_DEFAULT_TIMEOUT_SECONDS)

    def test_genai_job_result_storage_is_compact(self) -> None:
        def scenario(conn):
            result_id = genai_service.record_genai_job_result(
                conn,
                job_type=genai_service.GENAI_JOB_QUIZ_ANSWER,
                target_type=genai_service.GENAI_TARGET_MATCH_QUIZ,
                target_id="m001",
                status=genai_service.GENAI_STATUS_REJECTED,
                provider_key="mistral",
                model="test-model",
                input_payload={
                    "question": "Komt er een goal?",
                    "prompt": "this should not be stored as prompt text",
                },
                accepted_output={"selected_answers": ["ja"]},
                evidence={"facts": [{"type": "match_event", "id": "event-1"}]},
                failure_code="low_confidence",
                failure_message="Model was unsure",
            )
            row = genai_service.genai_job_result_by_id(conn, result_id)
            table_rows = wk_app.execute(conn, "SELECT * FROM genai_job_results").fetchall()
            return row, table_rows

        row, table_rows = self.run_with_temp_db(scenario)

        self.assertEqual(len(table_rows), 1)
        self.assertEqual(row["job_type"], genai_service.GENAI_JOB_QUIZ_ANSWER)
        self.assertEqual(row["status"], genai_service.GENAI_STATUS_REJECTED)
        self.assertEqual(row["failure_code"], "low_confidence")
        self.assertIsNotNone(row["input_hash"])
        serialized = json.dumps(dict(row), default=str)
        self.assertNotIn("this should not be stored", serialized)
        self.assertNotIn("prompt", row.keys())
        self.assertEqual(json.loads(row["accepted_output_json"]), {"selected_answers": ["ja"]})

    def test_genai_failure_notifications_are_deduplicated_and_resolvable(self) -> None:
        def scenario(conn):
            genai_service.create_genai_failure_notification(
                conn,
                job_type=genai_service.GENAI_JOB_QUIZ_ANSWER,
                target_type=genai_service.GENAI_TARGET_MATCH_QUIZ,
                target_id="m001",
                failure_code="invalid_output",
                title="Quiz GenAI needs review",
                body="The GenAI quiz answer could not be used.",
            )
            genai_service.create_genai_failure_notification(
                conn,
                job_type=genai_service.GENAI_JOB_QUIZ_ANSWER,
                target_type=genai_service.GENAI_TARGET_MATCH_QUIZ,
                target_id="m001",
                failure_code="invalid_output",
                title="Quiz GenAI still needs review",
                body="The GenAI quiz answer still could not be used.",
            )
            first = wk_app.active_admin_sync_notifications(conn)
            genai_service.resolve_genai_failure_notification(
                conn,
                job_type=genai_service.GENAI_JOB_QUIZ_ANSWER,
                target_type=genai_service.GENAI_TARGET_MATCH_QUIZ,
                target_id="m001",
                failure_code="invalid_output",
            )
            second = wk_app.active_admin_sync_notifications(conn)
            return first, second

        first, second = self.run_with_temp_db(scenario)

        genai_first = [
            item
            for item in first
            if item["type"] == genai_service.SYNC_NOTIFICATION_GENAI_JOB_FAILED
        ]
        self.assertEqual(len(genai_first), 1)
        self.assertEqual(genai_first[0]["title"], "Quiz GenAI still needs review")
        self.assertFalse(
            any(item["type"] == genai_service.SYNC_NOTIFICATION_GENAI_JOB_FAILED for item in second)
        )

    def test_quiz_genai_accepts_high_confidence_supplied_evidence(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            self.seed_scoring_user(conn)
            job_input = genai_service.build_quiz_genai_input(conn, data["matches"][0])
            output = {
                "status": "answered",
                "selected_answers": ["Netherlands"],
                "confidence": "high",
                "reason": "The stored match result has Netherlands winning 2-1.",
                "evidence": [{"type": "match_event", "id": "provider:event:1"}],
            }
            return genai_service.validate_quiz_genai_output(output, job_input)

        result = self.run_with_temp_db(scenario)

        self.assertTrue(result["accepted"])
        self.assertEqual(result["correct_answers"], ["Netherlands"])
        self.assertEqual(result["evidence"], [{"type": "match_event", "id": "provider:event:1"}])

    def test_quiz_genai_accepts_pydantic_choice_confidence_output(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            self.seed_scoring_user(conn)
            job_input = genai_service.build_quiz_genai_input(conn, data["matches"][0])
            output = {
                "choice": "Netherlands",
                "confidence": 0.92,
                "reason": "The supplied facts support this answer.",
            }
            return job_input, genai_service.validate_quiz_genai_output(output, job_input)

        job_input, result = self.run_with_temp_db(scenario)

        parsed_input = genai_service.QuizGenAIInputModel.model_validate(
            {
                "question": job_input["question"],
                "choices": job_input["choices"],
                "match_data": job_input["match_data"],
            }
        )
        self.assertEqual(parsed_input.question, "Who wins?")
        self.assertEqual(parsed_input.choices, ["Netherlands", "USA"])
        self.assertTrue(result["accepted"])
        self.assertEqual(result["correct_answers"], ["Netherlands"])
        self.assertEqual(result["confidence"], 0.92)

    def test_quiz_genai_choice_confidence_rejects_impossible_and_invalid_output(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            self.seed_scoring_user(conn)
            job_input = genai_service.build_quiz_genai_input(conn, data["matches"][0])
            cases = [
                {"choice": "", "confidence": 0, "reason": "No facts."},
                {"choice": "Netherlands", "confidence": 0.4, "reason": "Unsure."},
                {"choice": "Germany", "confidence": 0.95, "reason": "Bad option."},
                {"choice": "Netherlands", "confidence": 1.5, "reason": "Bad confidence."},
            ]
            return [genai_service.validate_quiz_genai_output(case, job_input) for case in cases]

        results = self.run_with_temp_db(scenario)

        self.assertTrue(all(not result["accepted"] for result in results))
        self.assertEqual(
            [result["failure_code"] for result in results],
            [
                "insufficient_evidence",
                "low_confidence",
                "answer_outside_options",
                "invalid_output",
            ],
        )

    def test_quiz_genai_choice_confidence_rejects_answer_without_facts(self) -> None:
        job_input = {
            "question": "Scoort Haaland in deze wedstrijd?",
            "choices": ["ja", "nee"],
            "match_data": {
                "result": None,
                "events": [],
                "clean_sheets": [],
                "player_stats": [],
            },
        }

        result = genai_service.validate_quiz_genai_output(
            {"choice": "ja", "confidence": 0.95, "reason": "Hallucinated answer."},
            job_input,
        )

        self.assertFalse(result["accepted"])
        self.assertEqual(result["failure_code"], "insufficient_evidence")

    def test_accepted_quiz_genai_label_resolves_prior_insufficient_evidence_issue(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            self.seed_scoring_user(conn)
            job_input = genai_service.build_quiz_genai_input(conn, data["matches"][0])
            genai_service.publish_quiz_genai_label(
                conn,
                data,
                data["matches"][0],
                {"choice": "", "confidence": 0, "reason": "No facts."},
                job_input,
            )
            first = wk_app.active_admin_sync_notifications(conn)
            genai_service.publish_quiz_genai_label(
                conn,
                data,
                data["matches"][0],
                {
                    "choice": "Netherlands",
                    "confidence": 0.95,
                    "reason": "Facts are available now.",
                },
                job_input,
            )
            second = wk_app.active_admin_sync_notifications(conn)
            return first, second

        first, second = self.run_with_temp_db(scenario)

        self.assertTrue(
            any(item["type"] == genai_service.SYNC_NOTIFICATION_GENAI_JOB_FAILED for item in first)
        )
        self.assertFalse(
            any(item["type"] == genai_service.SYNC_NOTIFICATION_GENAI_JOB_FAILED for item in second)
        )

    def test_quiz_genai_prompt_uses_choice_confidence_contract_examples(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            self.seed_scoring_user(conn)
            job_input = genai_service.build_quiz_genai_input(conn, data["matches"][0])
            return genai_service.quiz_genai_prompt_messages(job_input)

        messages = self.run_with_temp_db(scenario)
        serialized = json.dumps(messages)

        self.assertIn("choice", serialized)
        self.assertIn("confidence", serialized)
        self.assertIn("confidence 0", serialized)
        self.assertIn("Do not infer missing stats as no", serialized)

    def test_quiz_genai_rejects_invalid_or_unsafe_output(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            self.seed_scoring_user(conn)
            job_input = genai_service.build_quiz_genai_input(conn, data["matches"][0])
            cases = [
                None,
                {"status": "answered", "selected_answers": ["Germany"], "confidence": "high"},
                {
                    "status": "answered",
                    "selected_answers": ["Netherlands"],
                    "confidence": "medium",
                    "evidence": [{"type": "match_event", "id": "provider:event:1"}],
                },
                {
                    "status": "maybe",
                    "selected_answers": ["Netherlands"],
                    "confidence": "high",
                    "evidence": [{"type": "match_event", "id": "provider:event:1"}],
                },
                {
                    "status": "answered",
                    "selected_answers": ["Netherlands"],
                    "confidence": "high",
                    "evidence": [],
                },
            ]
            return [genai_service.validate_quiz_genai_output(case, job_input) for case in cases]

        results = self.run_with_temp_db(scenario)

        self.assertTrue(all(not result["accepted"] for result in results))
        self.assertEqual(
            [result["failure_code"] for result in results],
            [
                "invalid_output",
                "answer_outside_options",
                "low_confidence",
                "unsupported_status",
                "missing_evidence",
            ],
        )

    def test_rejected_quiz_genai_notifies_once_and_does_not_score(self) -> None:
        data = self.scoring_data(done=True)
        data["matches"][0]["quiz"]["correct_answers"] = ["USA"]
        data["matches"][0]["quiz"]["correct_answer"] = "USA"

        def scenario(conn):
            self.seed_scoring_user(conn)
            job_input = genai_service.build_quiz_genai_input(conn, data["matches"][0])
            output = {
                "status": "answered",
                "selected_answers": ["Germany"],
                "confidence": "high",
                "evidence": [{"type": "match_event", "id": "provider:event:1"}],
            }
            genai_service.publish_quiz_genai_label(
                conn, data, data["matches"][0], output, job_input
            )
            genai_service.publish_quiz_genai_label(
                conn, data, data["matches"][0], output, job_input
            )
            notifications = wk_app.active_admin_sync_notifications(conn)
            leaderboard = wk_app.build_leaderboard(data, use_computed_points=False)
            return notifications, leaderboard[0]

        notifications, row = self.run_with_temp_db(scenario)
        genai_notifications = [
            item
            for item in notifications
            if item["type"] == genai_service.SYNC_NOTIFICATION_GENAI_JOB_FAILED
        ]

        self.assertEqual(len(genai_notifications), 1)
        self.assertEqual(row["quiz_points"], 0)

    def test_manual_quiz_override_wins_over_genai_label_without_mutating_predictions(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            self.seed_scoring_user(conn)
            wk_app.execute(
                conn,
                """
                INSERT INTO quiz_label_overrides (
                    match_id, question, choices_json, correct_answers_json, source
                )
                VALUES ('m001', 'Who wins?', '["Netherlands", "USA"]', '["USA"]', 'manual')
                """,
            )
            job_input = genai_service.build_quiz_genai_input(conn, data["matches"][0])
            genai_service.publish_quiz_genai_label(
                conn,
                data,
                data["matches"][0],
                {
                    "status": "answered",
                    "selected_answers": ["Netherlands"],
                    "confidence": "high",
                    "evidence": [{"type": "match_event", "id": "provider:event:1"}],
                },
                job_input,
            )
            wk_app.apply_quiz_label_overrides(data)
            prediction = wk_app.execute(
                conn,
                "SELECT answer FROM quiz_predictions WHERE user_id = 1 AND match_id = 'm001'",
            ).fetchone()
            return data["matches"][0]["quiz"], prediction["answer"]

        quiz, prediction_answer = self.run_with_temp_db(scenario)

        self.assertEqual(quiz["correct_answers"], ["USA"])
        self.assertEqual(quiz["label_source"], "manual")
        self.assertTrue(quiz["manual_override_active"])
        self.assertEqual(prediction_answer, "Netherlands")

    def test_accepted_quiz_genai_label_recomputes_quiz_points(self) -> None:
        data = self.scoring_data(done=True)
        data["matches"][0]["quiz"]["correct_answers"] = ["USA"]
        data["matches"][0]["quiz"]["correct_answer"] = "USA"

        def scenario(conn):
            self.seed_scoring_user(conn)
            wk_app.recompute_all_computed_points(data)
            before = wk_app.computed_point_rows(
                conn, user_id=1, scope_type="leaderboard", scope_id="current"
            )
            job_input = genai_service.build_quiz_genai_input(conn, data["matches"][0])
            result = genai_service.publish_quiz_genai_label(
                conn,
                data,
                data["matches"][0],
                {
                    "status": "answered",
                    "selected_answers": ["Netherlands"],
                    "confidence": "high",
                    "evidence": [{"type": "match_event", "id": "provider:event:1"}],
                },
                job_input,
            )
            after = wk_app.computed_point_rows(
                conn, user_id=1, scope_type="leaderboard", scope_id="current"
            )
            return result, before, after

        result, before, after = self.run_with_temp_db(scenario)

        before_points = {row["category"]: row["points"] for row in before}
        after_points = {row["category"]: row["points"] for row in after}
        self.assertTrue(result["accepted"])
        self.assertEqual(before_points["quiz_points"], 0)
        self.assertGreater(after_points["quiz_points"], 0)

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
            first = genai_service.verify_player_database_matches(conn)
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
            second = genai_service.verify_player_database_matches(conn)
            second_notifications = wk_app.active_admin_sync_notifications(conn)
            return first, first_notifications, second, second_notifications

        first, first_notifications, second, second_notifications = self.run_with_temp_db(scenario)

        self.assertEqual(first["invalid_striker_picks"], 1)
        self.assertTrue(
            any(
                item["type"] == genai_service.SYNC_NOTIFICATION_STRIKER_PICK_NOT_IN_SQUAD
                for item in first_notifications
            ),
            first_notifications,
        )
        self.assertEqual(second["invalid_striker_picks"], 0)
        self.assertFalse(
            any(
                item["type"] == genai_service.SYNC_NOTIFICATION_STRIKER_PICK_NOT_IN_SQUAD
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
            first = genai_service.verify_player_database_matches(conn)
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
            second = genai_service.verify_player_database_matches(conn)
            second_notifications = wk_app.active_admin_sync_notifications(conn)
            return first, first_notifications, second, second_notifications

        first, first_notifications, second, second_notifications = self.run_with_temp_db(scenario)

        self.assertEqual(first["invalid_goal_scorers"], 1)
        self.assertTrue(
            any(
                item["type"] == genai_service.SYNC_NOTIFICATION_SCORER_PLAYER_NOT_IN_SQUAD
                for item in first_notifications
            ),
            first_notifications,
        )
        self.assertEqual(second["invalid_goal_scorers"], 0)
        self.assertFalse(
            any(
                item["type"] == genai_service.SYNC_NOTIFICATION_SCORER_PLAYER_NOT_IN_SQUAD
                for item in second_notifications
            ),
            second_notifications,
        )

    def test_match_scorer_can_match_static_team_profile_squad_without_synced_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_path = Path(tmpdir) / "team-profiles.json"
            profiles_path.write_text(
                json.dumps(
                    {
                        "teams": [
                            {
                                "id": "rsa",
                                "squad": [
                                    {"name": "Evidence Makgopa", "position": "Forward"},
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            def scenario(conn):
                wk_app.execute(
                    conn,
                    """
                    INSERT INTO match_events (
                        match_id, provider_event_key, event_type, player_name, raw_json
                    )
                    VALUES ('m001', 'provider:event:1', 'Goal', 'E. Makgopa', '{}')
                    """,
                )
                with patch.object(genai_service, "TEAM_PROFILES_PATH", profiles_path):
                    result = genai_service.verify_player_database_matches(conn)
                    notifications = wk_app.active_admin_sync_notifications(conn)
                return result, notifications

            result, notifications = self.run_with_temp_db(scenario)

        self.assertEqual(result["invalid_goal_scorers"], 0)
        self.assertFalse(
            any(
                item["type"] == genai_service.SYNC_NOTIFICATION_SCORER_PLAYER_NOT_IN_SQUAD
                for item in notifications
            ),
            notifications,
        )

    def test_single_token_scorer_can_match_unique_static_profile_first_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_path = Path(tmpdir) / "team-profiles.json"
            profiles_path.write_text(
                json.dumps(
                    {
                        "teams": [
                            {
                                "id": "par",
                                "squad": [
                                    {"name": "Mauricio Magalhães", "position": "Midfielder"},
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            def scenario(conn):
                wk_app.execute(
                    conn,
                    """
                    INSERT INTO match_events (
                        match_id, provider_event_key, event_type, player_name, raw_json
                    )
                    VALUES ('m001', 'provider:event:1', 'Goal', 'Mauricio', '{}')
                    """,
                )
                with patch.object(wk_app, "TEAM_PROFILES_PATH", profiles_path):
                    return genai_service.verify_player_database_matches(conn)

            result = self.run_with_temp_db(scenario)

        self.assertEqual(result["invalid_goal_scorers"], 0)

    def test_scorer_can_match_static_profile_name_order_variant(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_path = Path(tmpdir) / "team-profiles.json"
            profiles_path.write_text(
                json.dumps(
                    {
                        "teams": [
                            {
                                "id": "kor",
                                "squad": [
                                    {"name": "In-beom Hwang", "position": "Midfielder"},
                                    {"name": "Hyeon-gyu Oh", "position": "Forward"},
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            def scenario(conn):
                wk_app.execute(
                    conn,
                    """
                    INSERT INTO match_events (
                        match_id, provider_event_key, event_type, player_name, raw_json
                    )
                    VALUES ('m001', 'provider:event:1', 'Goal', 'Hwang In-Beom', '{}'),
                           ('m001', 'provider:event:2', 'Goal', 'Oh Hyeon-Gyu', '{}')
                    """,
                )
                with patch.object(wk_app, "TEAM_PROFILES_PATH", profiles_path):
                    return genai_service.verify_player_database_matches(conn)

            result = self.run_with_temp_db(scenario)

        self.assertEqual(result["invalid_goal_scorers"], 0)

    def test_own_goal_players_are_not_verified_as_goal_scorers(self) -> None:
        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, event_type, detail, player_name, raw_json
                )
                VALUES ('m001', 'provider:event:1', 'Goal', 'Own Goal', 'Unknown Defender', '{}')
                """,
            )
            result = genai_service.verify_player_database_matches(conn)
            notifications = wk_app.active_admin_sync_notifications(conn)
            return result, notifications

        result, notifications = self.run_with_temp_db(scenario)

        self.assertEqual(result["invalid_goal_scorers"], 0)
        self.assertFalse(
            any(
                item["type"] == genai_service.SYNC_NOTIFICATION_SCORER_PLAYER_NOT_IN_SQUAD
                for item in notifications
            ),
            notifications,
        )

    def test_player_genai_runs_only_after_deterministic_matching_fails(self) -> None:
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
            squad = genai_service.squad_player_database(conn)
            matched = genai_service.player_genai_should_run(
                api_player_id=None,
                player_name="C. Gakpo",
                squad_api_ids=squad[0],
                squad_names=squad[1],
                squad_initial_surname_keys=squad[2],
            )
            unmatched = genai_service.player_genai_should_run(
                api_player_id=None,
                player_name="Gakppo",
                squad_api_ids=squad[0],
                squad_names=squad[1],
                squad_initial_surname_keys=squad[2],
            )
            return matched, unmatched

        matched, unmatched = self.run_with_temp_db(scenario)

        self.assertFalse(matched)
        self.assertTrue(unmatched)

    def test_player_genai_accepts_only_supplied_candidate(self) -> None:
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
            job_input = genai_service.build_player_genai_input(
                conn,
                target_type=genai_service.GENAI_TARGET_MATCH_SCORER,
                target_id="m001:gakppo",
                raw_player_name="Gakppo",
                match_id="m001",
                local_team_id="ned",
            )
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
                    "matched_candidate_id": "ned:999",
                    "confidence": "high",
                    "evidence": [{"type": "candidate", "id": "ned:999"}],
                },
                job_input,
            )
            return accepted, rejected

        accepted, rejected = self.run_with_temp_db(scenario)

        self.assertTrue(accepted["accepted"])
        self.assertEqual(accepted["matched_candidate"]["player_name"], "Cody Gakpo")
        self.assertFalse(rejected["accepted"])
        self.assertEqual(rejected["failure_code"], "candidate_outside_shortlist")

    def test_player_genai_candidates_use_static_and_synced_player_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_path = Path(tmpdir) / "team-profiles.json"
            profiles_path.write_text(
                json.dumps(
                    {
                        "teams": [
                            {
                                "id": "rsa",
                                "squad": [
                                    {"name": "Evidence Makgopa", "position": "Forward"},
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            def scenario(conn):
                wk_app.execute(
                    conn,
                    """
                    INSERT INTO team_squad_players (
                        local_team_id, provider_player_key, api_player_id, player_name, raw_json
                    )
                    VALUES ('rsa', '202', 202, 'Ronwen Williams', '{}')
                    """,
                )
                with patch.object(genai_service, "TEAM_PROFILES_PATH", profiles_path):
                    return genai_service.build_player_genai_input(
                        conn,
                        target_type=genai_service.GENAI_TARGET_MATCH_SCORER,
                        target_id="m001:e-makgopa",
                        raw_player_name="E. Makgopa",
                        match_id="m001",
                        local_team_id="rsa",
                    )

            job_input = self.run_with_temp_db(scenario)

        candidates = {item["player_name"]: item for item in job_input["candidates"]}
        self.assertEqual(candidates["Evidence Makgopa"]["source"], "static_profile")
        self.assertEqual(candidates["Ronwen Williams"]["source"], "api_football")

    def test_player_genai_rejects_ambiguous_no_match_low_confidence_and_invalid(self) -> None:
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
            job_input = genai_service.build_player_genai_input(
                conn,
                target_type=genai_service.GENAI_TARGET_MATCH_SCORER,
                target_id="m001:gakppo",
                raw_player_name="Gakppo",
                match_id="m001",
                local_team_id="ned",
            )
            cases = [
                None,
                {
                    "status": "ambiguous",
                    "matched_candidate_id": None,
                    "confidence": "low",
                    "evidence": [{"type": "candidate", "id": "ned:1"}],
                },
                {
                    "status": "no_match",
                    "matched_candidate_id": None,
                    "confidence": "high",
                    "evidence": [{"type": "candidate", "id": "ned:1"}],
                },
                {
                    "status": "matched",
                    "matched_candidate_id": "ned:1",
                    "confidence": "medium",
                    "evidence": [{"type": "candidate", "id": "ned:1"}],
                },
            ]
            return [genai_service.validate_player_genai_output(case, job_input) for case in cases]

        results = self.run_with_temp_db(scenario)

        self.assertTrue(all(not result["accepted"] for result in results))
        self.assertEqual(
            [result["failure_code"] for result in results],
            ["invalid_output", "ambiguous", "no_match", "low_confidence"],
        )

    def test_player_genai_link_preserves_original_names_and_prediction_rows(self) -> None:
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
                    user_id, player_name, striker_name_1
                )
                VALUES (1, 'Cody Gakpo', 'Gakppo')
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, event_type, player_name, raw_json
                )
                VALUES ('m001', 'event-1', 'Goal', 'Gakppo', '{}')
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
            job_input = genai_service.build_player_genai_input(
                conn,
                target_type=genai_service.GENAI_TARGET_MATCH_SCORER,
                target_id="m001:gakppo",
                raw_player_name="Gakppo",
                match_id="m001",
                local_team_id="ned",
            )
            result = genai_service.publish_player_genai_link(
                conn,
                job_input,
                {
                    "status": "matched",
                    "matched_candidate_id": "ned:1",
                    "confidence": "high",
                    "evidence": [{"type": "candidate", "id": "ned:1"}],
                },
            )
            verification = genai_service.verify_player_database_matches(conn)
            event = wk_app.execute(conn, "SELECT player_name FROM match_events").fetchone()
            pick = wk_app.execute(
                conn, "SELECT striker_name_1 FROM top_scorer_predictions"
            ).fetchone()
            return result, verification, event["player_name"], pick["striker_name_1"]

        result, verification, event_name, pick_name = self.run_with_temp_db(scenario)

        self.assertTrue(result["accepted"])
        self.assertEqual(verification["invalid_goal_scorers"], 0)
        self.assertEqual(event_name, "Gakppo")
        self.assertEqual(pick_name, "Gakppo")

    def test_accepted_player_genai_link_counts_for_striker_scoring(self) -> None:
        data = {
            "matches": [
                make_match(
                    "m001",
                    datetime(2026, 6, 11, 18, 0, tzinfo=UTC),
                    home_team_id="ned",
                    away_team_id="usa",
                )
            ]
        }

        def scenario(conn):
            wk_app.execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, event_type, player_name, raw_json
                )
                VALUES ('m001', 'event-1', 'Goal', 'Gakppo', '{}')
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
            job_input = genai_service.build_player_genai_input(
                conn,
                target_type=genai_service.GENAI_TARGET_MATCH_SCORER,
                target_id="m001:gakppo",
                raw_player_name="Gakppo",
                match_id="m001",
                local_team_id="ned",
            )
            before = wk_app.striker_prediction_points(["Cody Gakpo"])
            genai_service.publish_player_genai_link(
                conn,
                job_input,
                {
                    "status": "matched",
                    "matched_candidate_id": "ned:1",
                    "confidence": "high",
                    "evidence": [{"type": "candidate", "id": "ned:1"}],
                },
            )
            conn.commit()
            after = wk_app.striker_prediction_points(["Cody Gakpo"])
            by_match = wk_app.striker_points_by_match_for_picks(data, ["Cody Gakpo"])
            return before, after, by_match

        before, after, by_match = self.run_with_temp_db(scenario)

        self.assertEqual(before, 0)
        self.assertEqual(after, wk_app.STRIKER_GOAL_POINTS)
        self.assertEqual(by_match["m001"]["scorers"][0]["name"], "Cody Gakpo")

    def test_rejected_player_genai_notifies_once_and_acceptance_resolves(self) -> None:
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
            job_input = genai_service.build_player_genai_input(
                conn,
                target_type=genai_service.GENAI_TARGET_MATCH_SCORER,
                target_id="m001:gakppo",
                raw_player_name="Gakppo",
                match_id="m001",
                local_team_id="ned",
            )
            low_confidence = {
                "status": "matched",
                "matched_candidate_id": "ned:1",
                "confidence": "low",
                "evidence": [{"type": "candidate", "id": "ned:1"}],
            }
            genai_service.publish_player_genai_link(conn, job_input, low_confidence)
            genai_service.publish_player_genai_link(conn, job_input, low_confidence)
            first = wk_app.active_admin_sync_notifications(conn)
            genai_service.publish_player_genai_link(
                conn,
                job_input,
                {
                    "status": "matched",
                    "matched_candidate_id": "ned:1",
                    "confidence": "high",
                    "evidence": [{"type": "candidate", "id": "ned:1"}],
                },
            )
            second = wk_app.active_admin_sync_notifications(conn)
            return first, second

        first, second = self.run_with_temp_db(scenario)

        self.assertEqual(
            len(
                [
                    item
                    for item in first
                    if item["type"] == genai_service.SYNC_NOTIFICATION_GENAI_JOB_FAILED
                ]
            ),
            1,
        )
        self.assertFalse(
            any(item["type"] == genai_service.SYNC_NOTIFICATION_GENAI_JOB_FAILED for item in second)
        )

    def test_participant_reads_do_not_call_genai_or_write_results(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            self.seed_scoring_user(conn)
            client = wk_app.app.test_client()
            with client.session_transaction() as session:
                session["user_id"] = 1
            with (
                patch.object(wk_app, "load_world_cup_data", return_value=data),
                patch.object(
                    genai_service,
                    "run_genai_structured_completion",
                    side_effect=AssertionError("participant read called GenAI"),
                ),
            ):
                statuses = [
                    client.get("/api/world-cup").status_code,
                    client.get("/api/pool").status_code,
                    client.get("/api/profiles/1/predictions").status_code,
                ]
            row = wk_app.execute(conn, "SELECT COUNT(*) AS count FROM genai_job_results").fetchone()
            return statuses, row["count"]

        statuses, result_count = self.run_with_temp_db(scenario)

        self.assertEqual(statuses, [200, 200, 200])
        self.assertEqual(result_count, 0)

    def test_successful_genai_outcomes_are_admin_visible_without_bell_noise(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            self.seed_scoring_user(conn)
            job_input = genai_service.build_quiz_genai_input(conn, data["matches"][0])
            genai_service.publish_quiz_genai_label(
                conn,
                data,
                data["matches"][0],
                {
                    "status": "answered",
                    "selected_answers": ["Netherlands"],
                    "confidence": "high",
                    "evidence": [{"type": "match_event", "id": "provider:event:1"}],
                },
                job_input,
            )
            payload = wk_app.admin_labels_payload(data)
            notifications = wk_app.active_admin_sync_notifications(conn)
            return payload["matches"][0]["quiz"], notifications

        quiz, notifications = self.run_with_temp_db(scenario)

        self.assertEqual(quiz["genai"]["status"], genai_service.GENAI_STATUS_ACCEPTED)
        self.assertEqual(quiz["source"], "genai:mistral")
        self.assertFalse(
            any(
                item["type"] == genai_service.SYNC_NOTIFICATION_GENAI_JOB_FAILED
                for item in notifications
            )
        )

    def test_admin_can_approve_genai_quiz_answer(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            self.seed_scoring_user(conn)
            wk_app.execute(conn, "UPDATE users SET is_admin = 1 WHERE id = 1")
            job_input = genai_service.build_quiz_genai_input(conn, data["matches"][0])
            published = genai_service.publish_quiz_genai_label(
                conn,
                data,
                data["matches"][0],
                {"choice": "Netherlands", "confidence": 0.95},
                job_input,
            )
            client = wk_app.app.test_client()
            with client.session_transaction() as session:
                session["user_id"] = 1
            with (
                patch.object(wk_app, "load_world_cup_data", return_value=data),
                patch.object(wk_app, "recompute_all_computed_points"),
            ):
                response = client.post(
                    f"/api/admin/genai/quiz-reviews/{published['job_result_id']}",
                    json={"decision": "approved"},
                )
            review = wk_app.execute(
                conn,
                "SELECT * FROM quiz_genai_reviews WHERE job_result_id = ?",
                (published["job_result_id"],),
            ).fetchone()
            return response, review

        response, review = self.run_with_temp_db(scenario)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["review"]["review_status"], "approved")
        self.assertEqual(review["decision"], "approved")
        self.assertEqual(json.loads(review["selected_answers_json"]), ["Netherlands"])

    def test_disapproving_genai_quiz_answer_requires_and_saves_available_choice(self) -> None:
        data = self.scoring_data(done=True)

        def scenario(conn):
            self.seed_scoring_user(conn)
            wk_app.execute(conn, "UPDATE users SET is_admin = 1 WHERE id = 1")
            job_input = genai_service.build_quiz_genai_input(conn, data["matches"][0])
            published = genai_service.publish_quiz_genai_label(
                conn,
                data,
                data["matches"][0],
                {"choice": "Netherlands", "confidence": 0.95},
                job_input,
            )
            client = wk_app.app.test_client()
            with client.session_transaction() as session:
                session["user_id"] = 1
            endpoint = f"/api/admin/genai/quiz-reviews/{published['job_result_id']}"
            with (
                patch.object(wk_app, "load_world_cup_data", return_value=data),
                patch.object(wk_app, "recompute_all_computed_points") as recompute,
            ):
                invalid = client.post(
                    endpoint,
                    json={"decision": "disapproved", "correct_answer": "Belgium"},
                )
                corrected = client.post(
                    endpoint,
                    json={"decision": "disapproved", "correct_answer": "USA"},
                )
            override = wk_app.execute(
                conn,
                "SELECT * FROM quiz_label_overrides WHERE match_id = 'm001'",
            ).fetchone()
            return invalid, corrected, override, recompute

        invalid, corrected, override, recompute = self.run_with_temp_db(scenario)

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(corrected.status_code, 200)
        self.assertEqual(corrected.get_json()["review"]["review_status"], "disapproved")
        self.assertEqual(json.loads(override["correct_answers_json"]), ["USA"])
        self.assertEqual(override["source"], "manual")
        recompute.assert_called_once()

    def test_genai_provider_failures_create_admin_only_notifications(self) -> None:
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
            genai_service.record_genai_provider_failure(
                conn,
                job_type=genai_service.GENAI_JOB_QUIZ_ANSWER,
                target_type=genai_service.GENAI_TARGET_MATCH_QUIZ,
                target_id="m001",
                failure_code="provider_timeout",
                failure_message="GenAI provider timed out.",
                input_payload={"match_id": "m001"},
            )
            conn.commit()
            admin_state = wk_app.user_pool_state(
                {"id": 1, "name": "Admin", "email": "admin@example.com", "is_admin": True},
                data,
            )
            player_state = wk_app.user_pool_state(
                {"id": 2, "name": "Player", "email": "player@example.com", "is_admin": False},
                data,
            )
            rows = wk_app.execute(
                conn, "SELECT status, failure_code FROM genai_job_results"
            ).fetchall()
            return admin_state, player_state, [dict(row) for row in rows]

        admin_state, player_state, rows = self.run_with_temp_db(scenario)

        self.assertEqual(rows[0]["status"], genai_service.GENAI_STATUS_FAILED)
        self.assertEqual(rows[0]["failure_code"], "provider_timeout")
        self.assertTrue(any(item["type"] == "sync_issue" for item in admin_state["notifications"]))
        self.assertFalse(
            any(item["type"] == "sync_issue" for item in player_state["notifications"])
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
            genai_service.verify_player_database_matches(conn)
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
            genai_service.verify_player_database_matches(conn)
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
                """,
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
                """,
            )
            result = genai_service.verify_player_database_matches(conn)
            notifications = wk_app.active_admin_sync_notifications(conn)
            return result, notifications

        result, notifications = self.run_with_temp_db(scenario)

        self.assertEqual(result["invalid_goal_scorers"], 0)
        self.assertFalse(
            any(
                item["type"] == genai_service.SYNC_NOTIFICATION_SCORER_PLAYER_NOT_IN_SQUAD
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
                """,
            )
            wk_app.execute(
                conn,
                """
                INSERT INTO match_events (
                    match_id, provider_event_key, event_type, player_name, raw_json
                )
                VALUES ('m001', 'provider:event:1', 'Goal', 'Alex Smith', '{}')
                """,
            )
            result = genai_service.verify_player_database_matches(conn)
            notifications = wk_app.active_admin_sync_notifications(conn)
            return result, notifications

        result, notifications = self.run_with_temp_db(scenario)

        self.assertEqual(result["invalid_goal_scorers"], 1)
        self.assertTrue(
            any(
                item["type"] == genai_service.SYNC_NOTIFICATION_SCORER_PLAYER_NOT_IN_SQUAD
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
