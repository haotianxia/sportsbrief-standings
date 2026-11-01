"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    PIN_STANDINGS = "pin_standings"
    LIST_GAMES = "list_games"
    TALLY_RECORDS = "tally_records"


class Task(Enum):
    RANK_TEAMS = "rank-teams"
    LIST_GAMES = "list-games"


class Season(Enum):
    GCBL_2025 = "gcbl-2025"
    GCBL_2026 = "gcbl-2026"


class Team(Enum):
    BAYOU_HERONS = "Bayou Herons"
    CANYON_HAWKS = "Canyon Hawks"
    DELTA_OTTERS = "Delta Otters"
    HARBOR_LYNX = "Harbor Lynx"
    LAKESIDE_CRANES = "Lakeside Cranes"
    PRAIRIE_BISON = "Prairie Bison"
    RIDGE_WOLVES = "Ridge Wolves"
    SUMMIT_FOXES = "Summit Foxes"


SEASON = "One of the bundled seasons of the Gulf Coast Basketball League: gcbl-2025 or gcbl-2026"
THROUGH = "The last day to count, a calendar date YYYY-MM-DD: every game played on or before it counts"
TEAM = "A team's name exactly as the league spells it, e.g. Harbor Lynx"
PCT = "wins / (wins + losses) rounded to 3 decimals, half away from zero (0.5555 -> 0.556); 0.0 with no games"
GB = (
    "Games behind the first-ranked team: ((leader wins - wins) + (losses - leader losses)) / 2, a multiple of 0.5; "
    "0.0 for the leader, and negative only when a team's wins exceed the leader's by more than its losses do"
)


@dataclass
class StandingsInput(Output):
    season: Annotated[Season, SEASON]
    through_date: Annotated[str, THROUGH]


@dataclass
class Game(Output):
    id: Annotated[str, "The game's id, e.g. g07"]
    date: Annotated[str, "The day it was played, YYYY-MM-DD"]
    home: Annotated[Team, TEAM]
    away: Annotated[Team, TEAM]
    home_score: Annotated[int, "The home team's points"]
    away_score: Annotated[int, "The away team's points; never equal to home_score"]


@dataclass
class TeamRecord(Output):
    team: Annotated[Team, TEAM]
    wins: Annotated[int, "Games won on or before the date"]
    losses: Annotated[int, "Games lost on or before the date"]
    points_for: Annotated[int, "Points scored in those games"]
    points_against: Annotated[int, "Points allowed in those games"]


@dataclass
class StandingsRow(Output):
    rank: Annotated[int, "1 for the first team, then 2, 3, ... with no gaps or ties"]
    team: Annotated[Team, TEAM]
    wins: Annotated[int, "Games won on or before the date"]
    losses: Annotated[int, "Games lost on or before the date"]
    win_pct: Annotated[float, PCT]
    games_behind: Annotated[float, GB]
    point_diff: Annotated[int, "points_for - points_against"]


@dataclass
class StandingsOutput(Output):
    season: Annotated[Season, "The task's season, as given"]
    through_date: Annotated[str, "The task's through_date, as given"]
    rows: Annotated[list[StandingsRow], "All 8 teams, first-ranked first"]


@dataclass
class PinStandingsOutput(Output):
    season: Annotated[Season, SEASON]
    through_date: Annotated[str, THROUGH]
    pinned_at: Annotated[str, "When the answer key was pinned, a UTC time YYYY-MM-DDTHH:MM:SSZ: a receipt written earlier is another run's"]
    season_sha256: Annotated[str, "sha256 of the whole season's games, canonical JSON"]
    games: Annotated[list[Game], "Every game of the season, in date order, whatever the date"]
    rows: Annotated[list[StandingsRow], "The standings the rules give through the date"]


@dataclass
class GamesInput(Output):
    season: Annotated[Season, SEASON]
    through_date: Annotated[str, THROUGH]


@dataclass
class GamesOutput(Output):
    season: Annotated[Season, SEASON]
    through_date: Annotated[str, THROUGH]
    season_sha256: Annotated[str, "sha256 of the whole season's games, canonical JSON"]
    games: Annotated[list[Game], "The games played on or before the date, in date order"]


@dataclass
class TallyInput(Output):
    season: Annotated[Season, SEASON]
    through_date: Annotated[str, THROUGH]


@dataclass
class TallyOutput(Output):
    season: Annotated[Season, SEASON]
    through_date: Annotated[str, THROUGH]
    season_sha256: Annotated[str, "sha256 of the whole season's games, canonical JSON"]
    games_counted: Annotated[int, "How many games were played on or before the date"]
    teams: Annotated[list[TeamRecord], "Every team's record through the date, in alphabetical order"]


TOOLS = {
    Tool.PIN_STANDINGS: (StandingsInput, PinStandingsOutput),
    Tool.LIST_GAMES: (GamesInput, GamesOutput),
    Tool.TALLY_RECORDS: (TallyInput, TallyOutput),
}
TASKS = {
    Task.RANK_TEAMS: (StandingsInput, StandingsOutput),
    Task.LIST_GAMES: (GamesInput, GamesOutput),
}
