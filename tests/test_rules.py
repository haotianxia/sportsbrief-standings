"""The rules: dates, records, percentages, the order, games behind; and the verifier's copies of the
rules and the data are byte-for-byte the tools'."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from plugin import rules

ROOT = Path(__file__).resolve().parents[1]


def test_the_verifier_runs_the_very_rules_and_data_the_tools_use() -> None:
    assert (ROOT / "verifier" / "rules.py").read_bytes() == (ROOT / "src" / "plugin" / "rules.py").read_bytes()
    assert (ROOT / "verifier" / "data.py").read_bytes() == (ROOT / "src" / "plugin" / "data.py").read_bytes()


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("2026-10-26", None),
        ("2028-02-29", None),
        ("2026-02-29", "'2026-02-29' is not a calendar day"),
        ("2100-02-29", "'2100-02-29' is not a calendar day"),
        ("2026-04-31", "'2026-04-31' is not a calendar day"),
        ("2026-13-01", "'2026-13-01' has no month 13"),
        ("2026-00-10", "'2026-00-10' has no month 00"),
        ("2026-10-00", "'2026-10-00' is not a calendar day"),
        ("26-10-26", "'26-10-26' is not a date YYYY-MM-DD"),
        ("2026/10/26", "'2026/10/26' is not a date YYYY-MM-DD"),
        ("2026-10-26T00:00:00Z", "'2026-10-26T00:00:00Z' is not a date YYYY-MM-DD"),
        ("2026-10-2６", "'2026-10-2６' is not a date YYYY-MM-DD"),  # a full-width digit, which \\d would accept
    ],
)
def test_a_date_is_a_calendar_day(text: str, problem: str | None) -> None:
    assert rules.date_problem(text) == problem


def test_a_stamp_is_an_ascii_utc_time() -> None:
    assert rules.stamp_problem("2026-10-21T02:10:00Z") is None
    assert rules.stamp_problem("2026-10-21T02:10:00") == "'2026-10-21T02:10:00' is not a UTC time YYYY-MM-DDTHH:MM:SSZ"
    assert rules.stamp_problem("2026-02-30T02:10:00Z") == "'2026-02-30T02:10:00Z' is not a calendar day"
    assert rules.stamp_problem("2026-10-21T24:10:00Z") == "'2026-10-21T24:10:00Z' is not a time of day"
    assert rules.stamp_problem(None) is not None
    assert rules.GAME_ID.fullmatch("g0１") is None


def game(number: int, date: str, home: str, home_score: int, away_score: int, away: str) -> dict:
    return {"id": f"g{number:02d}", "date": date, "home": home, "away": away, "home_score": home_score, "away_score": away_score}


GAMES = [
    game(1, "2026-01-01", "Harbor Lynx", 100, 90, "Bayou Herons"),
    game(2, "2026-01-02", "Harbor Lynx", 80, 85, "Delta Otters"),
    game(3, "2026-01-02", "Bayou Herons", 99, 98, "Canyon Hawks"),
    game(4, "2026-01-03", "Delta Otters", 70, 75, "Harbor Lynx"),
]


def test_through_keeps_the_games_on_or_before_the_date() -> None:
    assert [game["id"] for game in rules.through(GAMES, "2026-01-02")] == ["g01", "g02", "g03"]
    assert rules.through(GAMES, "2025-12-31") == []
    assert len(rules.through(GAMES, "2099-01-01")) == 4


def test_records_count_every_team_even_with_no_games() -> None:
    by_team = {record["team"]: record for record in rules.records(GAMES)}
    assert by_team["Harbor Lynx"] == {"team": "Harbor Lynx", "wins": 2, "losses": 1, "points_for": 255, "points_against": 245}
    assert by_team["Delta Otters"] == {"team": "Delta Otters", "wins": 1, "losses": 1, "points_for": 155, "points_against": 155}
    assert by_team["Summit Foxes"] == {"team": "Summit Foxes", "wins": 0, "losses": 0, "points_for": 0, "points_against": 0}
    assert [record["team"] for record in rules.records([])] == list(rules.TEAMS)


def record(wins: int, losses: int, diff: int = 0, team: str = "Harbor Lynx") -> dict:
    return {"team": team, "wins": wins, "losses": losses, "points_for": 1000 + diff, "points_against": 1000}


@pytest.mark.parametrize(
    ("wins", "losses", "pct"),
    [(4, 1, 0.8), (2, 1, 0.667), (5, 4, 0.556), (1, 15, 0.063), (3, 13, 0.188), (0, 0, 0.0), (0, 5, 0.0), (7, 0, 1.0), (1, 2, 0.333)],
)
def test_win_pct_rounds_half_away_from_zero(wins: int, losses: int, pct: float) -> None:
    assert rules.win_pct(record(wins, losses)) == pct


def test_the_order_is_share_of_games_won_then_differential_then_name() -> None:
    teams = [
        record(2, 0, 5, "Summit Foxes"),  # 1.000, same share as 4-0
        record(4, 0, 3, "Harbor Lynx"),
        record(1, 1, 0, "Delta Otters"),
        record(1, 1, 0, "Bayou Herons"),  # tied with the Otters on everything but the name
        record(1, 1, 7, "Canyon Hawks"),
        record(0, 0, 0, "Ridge Wolves"),  # no games: 0, like 0-3
        record(0, 3, -9, "Prairie Bison"),
    ]
    ordered = [team["team"] for team in sorted(teams, key=rules.order_key)]
    assert ordered == ["Summit Foxes", "Harbor Lynx", "Canyon Hawks", "Bayou Herons", "Delta Otters", "Ridge Wolves", "Prairie Bison"]
    assert rules.fraction_won(record(2, 0)) == rules.fraction_won(record(4, 0)) == Fraction(1)


@pytest.mark.parametrize(
    ("leader", "team", "behind"),
    [((4, 0), (2, 2), 2.0), ((4, 1), (3, 2), 1.0), ((4, 0), (3, 0), 0.5), ((1, 0), (3, 1), -0.5), ((0, 0), (0, 0), 0.0), ((4, 0), (4, 0), 0.0)],
)
def test_games_behind_is_exact_in_halves_and_can_be_negative(leader: tuple, team: tuple, behind: float) -> None:
    assert rules.games_behind(record(*leader), record(*team)) == behind


def test_standings_rank_every_team() -> None:
    rows = rules.standings(GAMES)
    assert [row["rank"] for row in rows] == list(range(1, 9))
    assert [(row["team"], row["wins"], row["losses"], row["win_pct"], row["games_behind"], row["point_diff"]) for row in rows[:4]] == [
        ("Harbor Lynx", 2, 1, 0.667, 0.0, 10),
        ("Delta Otters", 1, 1, 0.5, 0.5, 0),
        ("Bayou Herons", 1, 1, 0.5, 0.5, -9),
        ("Lakeside Cranes", 0, 0, 0.0, 0.5, 0),  # 0-0 is the same share as 0-1, and a differential of 0 beats -1
    ]


def test_standings_order_within_a_tie_is_by_differential_then_name() -> None:
    rows = rules.standings(GAMES)
    assert [row["team"] for row in rows] == [
        "Harbor Lynx",
        "Delta Otters",
        "Bayou Herons",
        "Lakeside Cranes",
        "Prairie Bison",
        "Ridge Wolves",
        "Summit Foxes",
        "Canyon Hawks",  # 0-1 with -1, behind the four 0-0 teams at 0
    ]
    assert [row["games_behind"] for row in rows] == [0.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.0]


def test_season_problem_names_what_is_wrong() -> None:
    assert rules.season_problem("gcbl-1999", []) == "'gcbl-1999' is not a bundled season"
    assert rules.season_problem("gcbl-2026", []) == "the season holds no game"
    good = GAMES[0]
    assert rules.season_problem("gcbl-2026", [good, dict(good)]) == "a game id appears twice"
    assert rules.season_problem("gcbl-2026", [{**good, "id": "x1"}]) == "'x1' is not a game id (g followed by two digits)"
    assert rules.season_problem("gcbl-2026", [{**good, "date": "2026-02-30"}]) == "g01's date: '2026-02-30' is not a calendar day"
    assert rules.season_problem("gcbl-2026", [{**good, "away": "Harbor Lynx"}]) == "g01 is not between two different league teams"
    assert rules.season_problem("gcbl-2026", [{**good, "away_score": 100}]) == "g01 has no winner"
    assert rules.season_problem("gcbl-2026", [GAMES[1], GAMES[0]]) == "the games are not in date order"
    assert rules.season_problem("gcbl-2026", GAMES).startswith("the games are not the bundled season gcbl-2026: sha256 ")
