"""The rank-teams verdict: a gold run holds every constraint on every date, and each of the 10 constraints
fails on its own case with its own message; plus the per-call checks."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

import verifier
from contract import GamesInput, GamesOutput, PinStandingsOutput, StandingsInput, StandingsOutput, TallyInput, TallyOutput
from plugin.standings import expected_output, list_games, pin_standings, receipt_path, tally_records
from verifier.task import TEXT


class Run:
    """A rank-teams run: the answer key pinned, tally_records called in the workspace (its receipt
    written), and the correct submission ready to be judged or broken."""

    def __init__(self, workspace: Path, season: str = "gcbl-2026", through_date: str = "2026-10-29", read: bool = True) -> None:
        self.workspace = workspace
        self.task = {"season": season, "through_date": through_date}
        self.given = build_output(self.task, StandingsInput)
        self.pin = plain_output(pin_standings(self.given, workspace / "scratch"))
        if read:
            self.tally = plain_output(tally_records(build_output(self.task, TallyInput), workspace))
        self.gold = plain_output(expected_output(self.given))

    def verdict(self, submission: dict | None = None, pin: dict | None = None, reference: bool = True) -> dict:
        submission = self.gold if submission is None else submission
        pinned = None if not reference else build_output(self.pin if pin is None else pin, PinStandingsOutput)
        return verifier.verify_task("rank-teams", self.given, build_output(submission, StandingsOutput), pinned, str(self.workspace))

    def rows(self) -> list[dict]:
        return copy.deepcopy(self.gold["rows"])


def failed(found: dict) -> list[str]:
    return [check["id"] for check in found["details"]["constraints"] if check["ok"] is False]


def unchecked(found: dict) -> list[str]:
    return [check["id"] for check in found["details"]["constraints"] if check["ok"] is None]


@pytest.mark.parametrize(
    ("season", "date"),
    [
        ("gcbl-2026", "2026-10-19"),
        ("gcbl-2026", "2026-10-22"),
        ("gcbl-2026", "2026-10-26"),
        ("gcbl-2026", "2026-10-29"),
        ("gcbl-2026", "2026-11-03"),
        ("gcbl-2026", "2026-11-07"),
        ("gcbl-2026", "2099-12-31"),
        ("gcbl-2025", "2025-10-21"),
        ("gcbl-2025", "2025-10-28"),
        ("gcbl-2025", "2025-11-01"),
    ],
)
def test_a_gold_run_holds_every_constraint(tmp_path: Path, season: str, date: str) -> None:
    run = Run(tmp_path, season, date)
    found = run.verdict()
    assert found["valid"], found["message"]
    assert found["score"] == 1.0 and found["message"].startswith("All 10 checks hold")
    assert [check["ok"] for check in found["details"]["constraints"]] == [True] * 10
    assert [check["id"] for check in found["details"]["constraints"]] == list(TEXT)
    assert found["details"]["expected"] == run.gold["rows"] and found["details"]["right_rows"] == 8
    assert len(json.dumps(found)) < 6000, "the verdict lands in the chat's context: keep it small"


def test_no_answer_key_fails_first_and_scores_zero(tmp_path: Path) -> None:
    run = Run(tmp_path)
    found = run.verdict(reference=False)
    assert not found["valid"] and found["score"] == 0.0
    assert failed(found) == ["answer-key"] and "pin_standings was not run" in found["message"]
    assert unchecked(found) == list(TEXT)[1:]


def test_an_answer_key_for_another_date_fails_answer_key(tmp_path: Path) -> None:
    run = Run(tmp_path)
    other = plain_output(pin_standings(build_output({**run.task, "through_date": "2026-10-26"}, StandingsInput), tmp_path / "other"))
    found = run.verdict(pin=other)
    assert failed(found) == ["answer-key"] and found["score"] == 0.0 and "another task" in found["message"]


def test_a_tampered_pinned_game_fails_answer_key_data(tmp_path: Path) -> None:
    run = Run(tmp_path)
    pin = copy.deepcopy(run.pin)
    pin["games"][0]["home_score"] += 1
    found = run.verdict(pin=pin)
    assert failed(found) == ["answer-key-data"] and found["score"] == 0.0
    assert "The pinned games are not the bundled gcbl-2026: the games are not the bundled season gcbl-2026: sha256" in found["message"]
    assert unchecked(found) == list(TEXT)[2:]


def test_pinned_rows_that_break_the_rules_fail_answer_key_data(tmp_path: Path) -> None:
    run = Run(tmp_path)
    pin = copy.deepcopy(run.pin)
    pin["rows"][0], pin["rows"][1] = pin["rows"][1], pin["rows"][0]
    found = run.verdict(pin=pin)
    assert failed(found) == ["answer-key-data"] and "not what the rules give" in found["message"]


def test_a_submission_for_another_task_fails_task_echo(tmp_path: Path) -> None:
    run = Run(tmp_path)
    found = run.verdict({**run.gold, "through_date": "2026-10-30"})
    assert failed(found) == ["task-echo"] and found["score"] == 0.0
    assert "task-echo: The submission is for {'season': 'gcbl-2026', 'through_date': '2026-10-30'}, not the task" in found["message"]


def test_submitting_without_calling_tally_records_fails_agent_read(tmp_path: Path) -> None:
    run = Run(tmp_path, read=False)
    found = run.verdict()
    assert failed(found) == ["agent-read"] and found["score"] == 0.0
    assert "agent-read: No readable receipt at standings/gcbl-2026-2026-10-29.json: tally_records was not called" in found["message"]
    assert [check["ok"] for check in found["details"]["constraints"]][4:] == [True] * 6, "the table itself is still judged"


def test_a_receipt_for_another_date_does_not_count(tmp_path: Path) -> None:
    run = Run(tmp_path, read=False)
    tally_records(build_output({"season": "gcbl-2026", "through_date": "2026-10-26"}, TallyInput), tmp_path)
    assert failed(run.verdict()) == ["agent-read"]


def test_a_receipt_altered_after_tally_records_fails_agent_read(tmp_path: Path) -> None:
    run = Run(tmp_path)
    path = receipt_path(tmp_path, "gcbl-2026", "2026-10-29")
    receipt = json.loads(path.read_text())
    receipt["games"][16]["home_score"] = 90  # the Wolves' first win becomes a loss
    path.write_text(json.dumps(receipt))
    found = run.verdict()
    assert failed(found) == ["agent-read"] and "was altered after tally_records" in found["message"]
    path.write_text("[1, 2, 3]")
    found = run.verdict()
    assert failed(found) == ["agent-read"] and "does not hold exactly season, through_date, season_sha256, games and written_at" in found["message"]
    path.write_text("[" * 50000 + "]" * 50000)  # nested past the decoder's depth: not JSON the verifier can read
    assert "No readable receipt" in run.verdict()["message"]
    path.unlink()
    assert "No readable receipt" in run.verdict()["message"]


def test_a_receipt_left_by_an_earlier_run_fails_agent_read(tmp_path: Path) -> None:
    run = Run(tmp_path)
    path = receipt_path(tmp_path, "gcbl-2026", "2026-10-29")
    receipt = json.loads(path.read_text())
    receipt["written_at"] = "2026-10-01T00:00:00Z"  # before this task's answer key was pinned
    path.write_text(json.dumps(receipt))
    found = run.verdict()
    assert failed(found) == ["agent-read"] and found["score"] == 0.0
    assert "was written at 2026-10-01T00:00:00Z, before the answer key was pinned at" in found["message"] and "Call tally_records in this run." in found["message"]
    receipt["written_at"] = 12345
    path.write_text(json.dumps(receipt))
    assert "the receipt's written_at is not a UTC time" in run.verdict()["message"]
    pin = copy.deepcopy(run.pin)
    pin["pinned_at"] = "2026-13-01T00:00:00Z"
    found = run.verdict(pin=pin)
    assert failed(found) == ["answer-key-data"] and "The pinned time is not a UTC time" in found["message"]


def test_a_missing_or_repeated_team_fails_teams_complete_and_stops_the_judgement(tmp_path: Path) -> None:
    run = Run(tmp_path)
    found = run.verdict({**run.gold, "rows": run.rows()[:7]})
    assert failed(found) == ["teams-complete"] and found["score"] == 0.0
    assert "teams-complete: The table is malformed: Ridge Wolves is missing." == found["message"]
    assert unchecked(found) == list(TEXT)[5:]
    rows = run.rows()
    rows[7] = {**rows[7], "team": "Harbor Lynx"}
    found = run.verdict({**run.gold, "rows": rows})
    assert "Harbor Lynx appears more than once; Ridge Wolves is missing." in found["message"]


def test_a_wrong_record_fails_records_exact(tmp_path: Path) -> None:
    run = Run(tmp_path)
    rows = run.rows()
    rows[1]["wins"], rows[1]["losses"] = 2, 3
    found = run.verdict({**run.gold, "rows": rows})
    assert failed(found) == ["records-exact"]
    assert "records-exact: Bayou Herons is given as 2-3 with point_diff +11, but its record through 2026-10-29 is 3-2 with point_diff +11." == found["message"]
    assert found["score"] == 7 / 8


def test_a_badly_rounded_percentage_fails_pct_exact(tmp_path: Path) -> None:
    run = Run(tmp_path)
    rows = run.rows()
    rows[0]["win_pct"] = 0.8  # right
    rows[1]["win_pct"] = 0.6
    rows[4]["win_pct"] = 0.4
    rows[7]["win_pct"] = 0.2
    assert run.verdict({**run.gold, "rows": rows})["valid"]
    rows[1]["win_pct"] = 0.66
    found = run.verdict({**run.gold, "rows": rows})
    assert failed(found) == ["pct-exact"]
    assert "pct-exact: Bayou Herons's win_pct is given as 0.66, but 3 of 5 games is 0.600 (3 decimals, half away from zero)." == found["message"]


def test_the_wrong_order_fails_order_exact_and_names_the_tiebreaker(tmp_path: Path) -> None:
    run = Run(tmp_path)
    rows = run.rows()
    rows[1], rows[2] = {**rows[2], "rank": 2}, {**rows[1], "rank": 3}  # the Otters above the Herons: same record and differential
    found = run.verdict({**run.gold, "rows": rows})
    assert failed(found) == ["order-exact"]
    assert found["message"] == (
        "order-exact: Position 2 holds Delta Otters, but Bayou Herons belongs there: both are 3-2 with point differential +11, and Bayou Herons comes first by name."
    )
    rows = run.rows()
    rows[2], rows[3] = {**rows[3], "rank": 3}, {**rows[2], "rank": 4}  # the Foxes (+9) above the Otters (+11)
    found = run.verdict({**run.gold, "rows": rows})
    assert "both are 3-2 and Delta Otters's point differential is greater (+11 against +9)" in found["message"]
    rows = run.rows()
    rows[0], rows[1] = {**rows[1], "rank": 1}, {**rows[0], "rank": 2}
    found = run.verdict({**run.gold, "rows": rows})
    assert failed(found) == ["order-exact"], "games_behind is judged per team from the real leader, so a swap at the top breaks only the order"
    assert "Harbor Lynx has won a greater share of its games (4-1 against 3-2)" in found["message"]


def test_ranks_that_do_not_run_1_to_8_fail_ranks_sequential(tmp_path: Path) -> None:
    run = Run(tmp_path)
    rows = run.rows()
    rows[2]["rank"] = 2  # a shared rank for the tie
    found = run.verdict({**run.gold, "rows": rows})
    assert failed(found) == ["ranks-sequential"] and "The ranks are [1, 2, 2, 4, 5, 6, 7, 8], not 1 to 8 down the table." in found["message"]


def test_a_wrong_games_behind_fails_gb_exact(tmp_path: Path) -> None:
    run = Run(tmp_path)
    rows = run.rows()
    rows[7]["games_behind"] = 2.5
    found = run.verdict({**run.gold, "rows": rows})
    assert failed(found) == ["gb-exact"]
    assert "gb-exact: Ridge Wolves's games_behind is given as 2.5, but from the leader Harbor Lynx (4-1) it is ((4 - 1) + (4 - 1)) / 2 = 3.0." == found["message"]
    assert found["score"] == 7 / 8


def test_a_negative_games_behind_is_expected_when_the_rules_give_one(tmp_path: Path) -> None:
    # On 2025-10-23 the Lynx are 2-0 and the Hawks 2-0: no negative figure in the bundled data, so the rule is checked on the verdict's own arithmetic.
    run = Run(tmp_path, "gcbl-2025", "2025-10-23")
    assert run.verdict()["valid"]
    assert all(row["games_behind"] >= 0 for row in run.gold["rows"])


def test_every_constraint_entry_has_the_same_keys_and_is_json(tmp_path: Path) -> None:
    run = Run(tmp_path)
    found = run.verdict({**run.gold, "rows": list(reversed(run.rows()))})
    assert not found["valid"]
    for check in found["details"]["constraints"]:
        assert list(check) == ["id", "constraint", "ok", "expected", "actual", "message"]
        assert check["ok"] in (True, False, None)
    json.dumps(found)


# Every tool call is checked too.
def test_verify_input_refuses_a_date_that_is_not_a_calendar_day() -> None:
    for tool, cls in (("pin_standings", StandingsInput), ("list_games", GamesInput), ("tally_records", TallyInput)):
        assert verifier.verify_input(tool, build_output({"season": "gcbl-2025", "through_date": "2025-02-29"}, cls))["valid"] is False
        assert verifier.verify_input(tool, build_output({"season": "gcbl-2025", "through_date": "2024-02-29"}, cls))["valid"] is True


def test_verify_output_holds_each_tool_to_the_rules(tmp_path: Path) -> None:
    given = build_output({"season": "gcbl-2026", "through_date": "2026-10-26"}, TallyInput)
    tallied = build_output(plain_output(tally_records(given, tmp_path)), TallyOutput)
    assert verifier.verify_output("tally_records", given, tallied, str(tmp_path))["valid"] is True
    bent = plain_output(tallied)
    bent["teams"][0]["wins"] += 1
    assert "not what the rules give" in verifier.verify_output("tally_records", given, build_output(bent, TallyOutput), str(tmp_path))["message"]
    bent = plain_output(tallied)
    bent["games_counted"] = 15
    assert "games_counted is 15, but 16 games" in verifier.verify_output("tally_records", given, build_output(bent, TallyOutput), str(tmp_path))["message"]
    assert "no readable receipt" in verifier.verify_output("tally_records", given, tallied, str(tmp_path / "elsewhere"))["message"]

    asked = build_output({"season": "gcbl-2025", "through_date": "2025-10-25"}, GamesInput)
    listed = build_output(plain_output(list_games(asked, tmp_path)), GamesOutput)
    assert verifier.verify_output("list_games", asked, listed, str(tmp_path))["valid"] is True
    assert verifier.verify_task("list-games", asked, listed, None, str(tmp_path))["valid"] is True
    bent = plain_output(listed)
    bent["games"] = bent["games"][:-1]
    assert "not the bundled season's games played on or before the date" in verifier.verify_task("list-games", asked, build_output(bent, GamesOutput), None, str(tmp_path))["message"]

    task = build_output({"season": "gcbl-2026", "through_date": "2026-11-07"}, StandingsInput)
    pinned = build_output(plain_output(pin_standings(task, tmp_path)), PinStandingsOutput)
    assert verifier.verify_output("pin_standings", task, pinned, str(tmp_path))["valid"] is True
    bent = plain_output(pinned)
    bent["rows"][0]["games_behind"] = 1.0
    assert verifier.verify_output("pin_standings", task, build_output(bent, PinStandingsOutput), str(tmp_path))["valid"] is False
