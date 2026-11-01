"""tally_records: its records are the rules applied to the season its receipt records, through the date."""

from pathlib import Path

from . import rules
from .checks import plain, read_json, result

RECEIPT_KEYS = ("season", "through_date", "season_sha256", "games", "written_at")
GAME_KEYS = ("away", "away_score", "date", "home", "home_score", "id")


def receipt_path(workspace, season, through_date):
    return Path(workspace) / rules.RECEIPTS / f"{season}-{through_date}.json"


def receipt_problem(receipt, season, through_date):
    """What is wrong with ``receipt`` as tally_records's record of reading ``season`` through ``through_date``, or None."""
    if not isinstance(receipt, dict) or sorted(receipt) != sorted(RECEIPT_KEYS):
        return "the receipt does not hold exactly season, through_date, season_sha256, games and written_at"
    if receipt["season"] != season or receipt["through_date"] != through_date:
        return f"the receipt is for {receipt['season']!r} through {receipt['through_date']!r}"
    problem = rules.stamp_problem(receipt["written_at"])
    if problem:
        return f"the receipt's written_at is not a UTC time: {problem}"
    games = receipt["games"]
    if not isinstance(games, list) or not all(
        isinstance(game, dict)
        and tuple(sorted(game)) == GAME_KEYS
        and all(isinstance(game[key], str) for key in ("id", "date", "home", "away"))
        and all(isinstance(game[key], int) and not isinstance(game[key], bool) for key in ("home_score", "away_score"))
        for game in games
    ):
        return "the receipt's games are not records of id, date, home, away, home_score and away_score"
    problem = rules.season_problem(season, games)
    if problem:
        return f"the receipt's games are not the bundled {season}: {problem}"
    if receipt["season_sha256"] != rules.sha256(games):
        return "the receipt's games do not match its own sha256"
    return None


def read_receipt(workspace, season, through_date):
    """``(receipt, problem)``: the receipt tally_records wrote for the season and date, or why there is none."""
    path = receipt_path(workspace, season, through_date)
    receipt = read_json(path)
    if receipt is None:
        return None, f"no readable receipt at {rules.RECEIPTS}/{path.name}: tally_records was not called for this season and date"
    problem = receipt_problem(receipt, season, through_date)
    if problem:
        return None, f"the receipt {rules.RECEIPTS}/{path.name} was altered after tally_records: {problem}"
    return receipt, None


def verify_input(value):
    problem = rules.date_problem(value.through_date)
    return result(False, f"through_date: {problem}") if problem else result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    given, made = plain(input_value), plain(output_value)
    if made["season"] != given["season"] or made["through_date"] != given["through_date"]:
        return result(False, "the output is not for the requested season and date")
    receipt, problem = read_receipt(workspace, given["season"], given["through_date"])
    if problem:
        return result(False, problem)
    if made["season_sha256"] != receipt["season_sha256"]:
        return result(False, "season_sha256 is not the receipt's")
    counted = rules.through(receipt["games"], given["through_date"])
    if made["games_counted"] != len(counted):
        return result(False, f"games_counted is {made['games_counted']}, but {len(counted)} games were played on or before the date")
    if made["teams"] != rules.records(counted):
        return result(False, "the records are not what the rules give on the receipt's games through the date")
    return result(True, "the records follow the rules", games=len(counted))
