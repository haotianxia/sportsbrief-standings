"""The tools: the answer key (pin_standings), the games (list_games) and the records the agent ranks
from (tally_records), each a function of the bundled data and the rules."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from contract import (
    Game,
    GamesInput,
    GamesOutput,
    PinStandingsOutput,
    Season,
    StandingsInput,
    StandingsOutput,
    StandingsRow,
    TallyInput,
    TallyOutput,
    Team,
    TeamRecord,
)
from plugin import rules
from plugin.data import SEASONS


def season(name: str) -> list[dict]:
    """The bundled season ``name``, checked against its recorded hash."""
    games = [dict(game) for game in SEASONS[name]]
    problem = rules.season_problem(name, games)
    if problem:
        raise ValueError(f"season {name}: {problem}")
    return games


def check_date(through_date: str) -> None:
    problem = rules.date_problem(through_date)
    if problem:
        raise ValueError(f"through_date: {problem}")


def receipt_path(workspace: Path, name: str, through_date: str) -> Path:
    return workspace / rules.RECEIPTS / f"{name}-{through_date}.json"


def now() -> str:
    """The clock, a UTC time YYYY-MM-DDTHH:MM:SSZ: the answer key records when it was pinned and a receipt when it was
    written, so the verifier can tell a receipt of this run from one an earlier run left in the workspace."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def as_game(game: dict) -> Game:
    return Game(**{**game, "home": Team(game["home"]), "away": Team(game["away"])})


def as_row(row: dict) -> StandingsRow:
    return StandingsRow(**{**row, "team": Team(row["team"])})


def list_games(given: GamesInput, workspace: Path) -> GamesOutput:
    check_date(given.through_date)
    games = season(given.season.value)
    return GamesOutput(
        season=given.season,
        through_date=given.through_date,
        season_sha256=rules.sha256(games),
        games=[as_game(game) for game in rules.through(games, given.through_date)],
    )


def tally_records(given: TallyInput, workspace: Path) -> TallyOutput:
    """Every team's record through the date, with a receipt of the season it read under the workspace."""
    check_date(given.through_date)
    games = season(given.season.value)
    digest = rules.sha256(games)
    receipt = {"season": given.season.value, "through_date": given.through_date, "season_sha256": digest, "games": games, "written_at": now()}
    path = receipt_path(workspace, given.season.value, given.through_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rules.canonical(receipt) + "\n", encoding="utf-8")
    counted = rules.through(games, given.through_date)
    return TallyOutput(
        season=given.season,
        through_date=given.through_date,
        season_sha256=digest,
        games_counted=len(counted),
        teams=[TeamRecord(**{**record, "team": Team(record["team"])}) for record in rules.records(counted)],
    )


def pin_standings(given: StandingsInput, workspace: Path) -> PinStandingsOutput:
    """The answer key: the whole season and the standings the rules give through the date."""
    check_date(given.through_date)
    games = season(given.season.value)
    return PinStandingsOutput(
        season=given.season,
        through_date=given.through_date,
        pinned_at=now(),
        season_sha256=rules.sha256(games),
        games=[as_game(game) for game in games],
        rows=[as_row(row) for row in rules.standings(rules.through(games, given.through_date))],
    )


def expected_output(given: StandingsInput) -> StandingsOutput:
    """What a correct rank-teams submission is: the rules applied to the season (used by tests)."""
    pinned = pin_standings(given, Path("."))
    return StandingsOutput(season=pinned.season, through_date=pinned.through_date, rows=pinned.rows)


__all__ = ["Season", "expected_output", "list_games", "pin_standings", "receipt_path", "tally_records"]
