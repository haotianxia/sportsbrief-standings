"""The standings rules: pure functions of a season's games, shared by the tools and the verifier.

verifier/rules.py is a byte-for-byte copy of this file (tests/test_rules.py enforces it), so the
verifier re-derives every record, rank and games-behind figure with the very code the tools used,
importing only pure standard-library modules. Values are plain JSON values here.
"""

import hashlib
import json
import re
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

TEAMS = (
    "Bayou Herons",
    "Canyon Hawks",
    "Delta Otters",
    "Harbor Lynx",
    "Lakeside Cranes",
    "Prairie Bison",
    "Ridge Wolves",
    "Summit Foxes",
)
GAME_ID = re.compile(r"^g[0-9]{2}$")
DATE = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$")
PCT = Decimal("0.001")
RECEIPTS = "standings"  # tally_records records what it read under <workspace>/standings/<season>-<through_date>.json
# sha256 of each bundled season's canonical JSON (src/plugin/data.py); tests/test_data.py keeps them current.
DATA_SHA256 = {
    "gcbl-2025": "3d4a8d3d625be968768552cab3e086ea6fb307842adc3831bad2cd327edebdc0",
    "gcbl-2026": "dec665550018a52d74f5b323808d526c1c689b62d0330b1f67a21e5f7142af51",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_month(year, month):
    if month == 2:
        return 29 if is_leap(year) else 28
    return 30 if month in (4, 6, 9, 11) else 31


STAMP = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})Z$")  # a UTC time, comparable as text


def stamp_problem(text):
    """Why ``text`` is not a UTC time YYYY-MM-DDTHH:MM:SSZ, or None. Such times compare as text."""
    found = STAMP.fullmatch(text) if isinstance(text, str) else None
    if not found:
        return f"{text!r} is not a UTC time YYYY-MM-DDTHH:MM:SSZ"
    year, month, day, hour, minute, second = (int(part) for part in found.groups())
    if not 1 <= month <= 12 or not 1 <= day <= days_in_month(year, month):
        return f"{text!r} is not a calendar day"
    if hour > 23 or minute > 59 or second > 59:
        return f"{text!r} is not a time of day"
    return None


def date_problem(text):
    """Why ``text`` is not a calendar date YYYY-MM-DD, or None."""
    found = DATE.fullmatch(text)
    if not found:
        return f"{text!r} is not a date YYYY-MM-DD"
    year, month, day = (int(part) for part in found.groups())
    if not 1 <= month <= 12:
        return f"{text!r} has no month {month:02d}"
    if not 1 <= day <= days_in_month(year, month):
        return f"{text!r} is not a calendar day"
    return None


def through(games, through_date):
    """The games played on or before ``through_date``; dates compare as text, being YYYY-MM-DD."""
    return [game for game in games if game["date"] <= through_date]


def records(games):
    """Every team's wins, losses, points for and against over ``games``, in alphabetical order."""
    tally = {team: {"team": team, "wins": 0, "losses": 0, "points_for": 0, "points_against": 0} for team in TEAMS}
    for game in games:
        home, away = tally[game["home"]], tally[game["away"]]
        home["points_for"] += game["home_score"]
        home["points_against"] += game["away_score"]
        away["points_for"] += game["away_score"]
        away["points_against"] += game["home_score"]
        winner, loser = (home, away) if game["home_score"] > game["away_score"] else (away, home)
        winner["wins"] += 1
        loser["losses"] += 1
    return [tally[team] for team in TEAMS]


def fraction_won(record):
    played = record["wins"] + record["losses"]
    return Fraction(record["wins"], played) if played else Fraction(0)


def win_pct(record):
    """wins / (wins + losses) to 3 decimals, half away from zero; 0.0 with no games."""
    fraction = fraction_won(record)
    exact = Decimal(fraction.numerator) / Decimal(fraction.denominator)
    return float(exact.quantize(PCT, rounding=ROUND_HALF_UP))


def point_diff(record):
    return record["points_for"] - record["points_against"]


def order_key(record):
    """Best first: the exact share of games won, then the point differential, then the name."""
    return (-fraction_won(record), -point_diff(record), record["team"])


def games_behind(leader, record):
    """((leader wins - wins) + (losses - leader losses)) / 2, exact: a multiple of 0.5, possibly negative."""
    return ((leader["wins"] - record["wins"]) + (record["losses"] - leader["losses"])) / 2


def standings(games):
    """The standings rows over ``games``: every team, ranked 1 to 8."""
    ranked = sorted(records(games), key=order_key)
    leader = ranked[0]
    return [
        {
            "rank": index + 1,
            "team": record["team"],
            "wins": record["wins"],
            "losses": record["losses"],
            "win_pct": win_pct(record),
            "games_behind": games_behind(leader, record),
            "point_diff": point_diff(record),
        }
        for index, record in enumerate(ranked)
    ]


def season_problem(name, games):
    """What is wrong with ``games`` as the bundled season ``name``, or None."""
    if name not in DATA_SHA256:
        return f"{name!r} is not a bundled season"
    if not games:
        return "the season holds no game"
    ids = [game["id"] for game in games]
    if len(set(ids)) != len(ids):
        return "a game id appears twice"
    for game in games:
        if not GAME_ID.fullmatch(game["id"]):
            return f"{game['id']!r} is not a game id (g followed by two digits)"
        problem = date_problem(game["date"])
        if problem:
            return f"{game['id']}'s date: {problem}"
        if game["home"] not in TEAMS or game["away"] not in TEAMS or game["home"] == game["away"]:
            return f"{game['id']} is not between two different league teams"
        if game["home_score"] == game["away_score"] or min(game["home_score"], game["away_score"]) < 0:
            return f"{game['id']} has no winner"
    if [game["date"] for game in games] != sorted(game["date"] for game in games):
        return "the games are not in date order"
    if sha256(games) != DATA_SHA256[name]:
        return f"the games are not the bundled season {name}: sha256 {sha256(games)} instead of {DATA_SHA256[name]}"
    return None
