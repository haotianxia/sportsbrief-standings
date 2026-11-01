"""The tools: the games, the records and their receipt, and the answer key, built into their contract classes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

from contract import GamesInput, GamesOutput, PinStandingsOutput, Season, StandingsInput, TallyInput, TallyOutput, Team, TeamRecord
from plugin import rules
from plugin.standings import list_games, pin_standings, receipt_path, tally_records


def test_list_games_gives_the_games_through_the_date(tmp_path: Path) -> None:
    listed = list_games(build_output({"season": "gcbl-2026", "through_date": "2026-10-22"}, GamesInput), tmp_path)
    build_output(plain_output(listed), GamesOutput)
    assert listed.season is Season.GCBL_2026 and len(listed.games) == 8
    assert listed.season_sha256 == rules.DATA_SHA256["gcbl-2026"]
    assert listed.games[0].home is Team.HARBOR_LYNX and listed.games[0].away is Team.BAYOU_HERONS
    assert all(game.date <= "2026-10-22" for game in listed.games)
    assert list_games(build_output({"season": "gcbl-2026", "through_date": "2026-10-19"}, GamesInput), tmp_path).games == []


def test_tally_records_counts_the_games_and_writes_its_receipt(tmp_path: Path) -> None:
    tallied = tally_records(build_output({"season": "gcbl-2026", "through_date": "2026-10-26"}, TallyInput), tmp_path)
    build_output(plain_output(tallied), TallyOutput)
    assert tallied.games_counted == 16 and [record.team.value for record in tallied.teams] == list(rules.TEAMS)
    lynx = next(record for record in tallied.teams if record.team is Team.HARBOR_LYNX)
    assert (lynx.wins, lynx.losses, lynx.points_for, lynx.points_against) == (4, 0, 406, 389)
    receipt = json.loads(receipt_path(tmp_path, "gcbl-2026", "2026-10-26").read_text())
    assert receipt["season"] == "gcbl-2026" and receipt["through_date"] == "2026-10-26"
    assert len(receipt["games"]) == 36, "the receipt holds the whole season, so the verifier can check its hash"
    assert receipt["season_sha256"] == tallied.season_sha256 == rules.sha256(receipt["games"]) == rules.DATA_SHA256["gcbl-2026"]


def test_pin_standings_gives_the_rules_answer(tmp_path: Path) -> None:
    pinned = pin_standings(build_output({"season": "gcbl-2026", "through_date": "2026-10-29"}, StandingsInput), tmp_path)
    build_output(plain_output(pinned), PinStandingsOutput)
    assert len(pinned.games) == 36 and pinned.season_sha256 == rules.DATA_SHA256["gcbl-2026"]
    assert [(row.rank, row.team.value, row.wins, row.losses, row.win_pct, row.games_behind, row.point_diff) for row in pinned.rows][:3] == [
        (1, "Harbor Lynx", 4, 1, 0.8, 0.0, 14),
        (2, "Bayou Herons", 3, 2, 0.6, 1.0, 11),
        (3, "Delta Otters", 3, 2, 0.6, 1.0, 11),
    ]
    assert not list(tmp_path.iterdir()), "the answer key writes nothing"


@pytest.mark.parametrize("date", ["2026-02-30", "2026-13-01", "10/26/2026", ""])
def test_a_date_that_is_not_a_calendar_day_is_refused(tmp_path: Path, date: str) -> None:
    with pytest.raises(ValueError, match="through_date"):
        list_games(build_output({"season": "gcbl-2026", "through_date": date}, GamesInput), tmp_path)
    with pytest.raises(ValueError, match="through_date"):
        tally_records(build_output({"season": "gcbl-2026", "through_date": date}, TallyInput), tmp_path)
    with pytest.raises(ValueError, match="through_date"):
        pin_standings(build_output({"season": "gcbl-2026", "through_date": date}, StandingsInput), tmp_path)


def test_an_unknown_season_or_team_is_refused_by_the_contract() -> None:
    with pytest.raises(ValueError, match="not a valid Season"):
        build_output({"season": "gcbl-1999", "through_date": "2026-10-26"}, GamesInput)
    with pytest.raises(ValueError, match="not a valid Team"):
        build_output({"team": "Houston Rockets", "wins": 0, "losses": 0, "points_for": 0, "points_against": 0}, TeamRecord)
