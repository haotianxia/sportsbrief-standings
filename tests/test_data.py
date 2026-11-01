"""The bundled seasons: well formed, hashed as the rules record, and holding the ties the task is about."""

from __future__ import annotations

import pytest

from plugin import rules
from plugin.data import SEASONS


@pytest.mark.parametrize("name", sorted(SEASONS))
def test_each_season_is_well_formed_and_matches_its_recorded_hash(name: str) -> None:
    assert rules.season_problem(name, SEASONS[name]) is None
    assert rules.sha256(SEASONS[name]) == rules.DATA_SHA256[name]
    assert set(rules.DATA_SHA256) == set(SEASONS)


def table(name: str, date: str) -> list[tuple]:
    return [(row["rank"], row["team"], row["wins"], row["losses"], row["point_diff"], row["games_behind"]) for row in rules.standings(rules.through(SEASONS[name], date))]


def test_every_team_plays_nine_games_in_2026_and_six_in_2025() -> None:
    for name, played in (("gcbl-2026", 9), ("gcbl-2025", 6)):
        assert all(record["wins"] + record["losses"] == played for record in rules.records(SEASONS[name]))


def test_a_date_before_the_season_gives_eight_zero_rows_ranked_by_name() -> None:
    rows = rules.standings(rules.through(SEASONS["gcbl-2026"], "2026-10-19"))
    assert [row["team"] for row in rows] == list(rules.TEAMS)
    assert all((row["wins"], row["losses"], row["win_pct"], row["games_behind"], row["point_diff"]) == (0, 0, 0.0, 0.0, 0) for row in rows)


def test_on_2026_10_26_three_teams_tie_at_2_2_with_the_same_differential() -> None:
    assert table("gcbl-2026", "2026-10-26") == [
        (1, "Harbor Lynx", 4, 0, 17, 0.0),
        (2, "Delta Otters", 3, 1, 15, 1.0),
        (3, "Bayou Herons", 2, 2, 6, 2.0),
        (4, "Canyon Hawks", 2, 2, 3, 2.0),
        (5, "Lakeside Cranes", 2, 2, 3, 2.0),
        (6, "Summit Foxes", 2, 2, 3, 2.0),
        (7, "Prairie Bison", 1, 3, -18, 3.0),
        (8, "Ridge Wolves", 0, 4, -29, 4.0),
    ]


def test_on_2026_10_29_two_teams_tie_at_3_2_with_plus_11() -> None:
    rows = table("gcbl-2026", "2026-10-29")
    assert rows[:4] == [(1, "Harbor Lynx", 4, 1, 14, 0.0), (2, "Bayou Herons", 3, 2, 11, 1.0), (3, "Delta Otters", 3, 2, 11, 1.0), (4, "Summit Foxes", 3, 2, 9, 1.0)]
    assert [row["win_pct"] for row in rules.standings(rules.through(SEASONS["gcbl-2026"], "2026-10-29"))] == [0.8, 0.6, 0.6, 0.6, 0.4, 0.4, 0.4, 0.2]


def test_at_the_end_of_2026_the_top_two_tie_on_record_and_differential() -> None:
    rows = table("gcbl-2026", "2026-11-07")
    assert rows[:3] == [(1, "Bayou Herons", 6, 3, 21, 0.0), (2, "Harbor Lynx", 6, 3, 21, 0.0), (3, "Delta Otters", 6, 3, 19, 0.0)]
    assert [row["win_pct"] for row in rules.standings(SEASONS["gcbl-2026"])][:4] == [0.667, 0.667, 0.667, 0.556]


def test_the_2025_season_ends_with_an_unbeaten_leader_and_a_winless_last() -> None:
    rows = table("gcbl-2025", "2025-11-01")
    assert rows[0] == (1, "Harbor Lynx", 6, 0, 37, 0.0) and rows[-1] == (8, "Ridge Wolves", 0, 6, -45, 6.0)
    assert rows[3:5] == [(4, "Bayou Herons", 3, 3, -1, 3.0), (5, "Delta Otters", 3, 3, -1, 3.0)]
