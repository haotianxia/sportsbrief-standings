"""list_games, and the list-games task: the games are the bundled season's through the date, unchanged."""

from . import rules
from .checks import plain, result
from .data import SEASONS


def output_problem(given, made):
    for name in ("season", "through_date"):
        if made[name] != given[name]:
            return f"the games are for {name} {made[name]!r}, not the requested {given[name]!r}"
    problem = rules.date_problem(made["through_date"])
    if problem:
        return f"through_date: {problem}"
    season = SEASONS[made["season"]]
    if made["season_sha256"] != rules.sha256(season) or made["season_sha256"] != rules.DATA_SHA256[made["season"]]:
        return "season_sha256 is not the bundled season's"
    if made["games"] != rules.through(season, made["through_date"]):
        return "the games are not the bundled season's games played on or before the date, in date order"
    return None


def verify_input(value):
    problem = rules.date_problem(value.through_date)
    return result(False, f"through_date: {problem}") if problem else result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    problem = output_problem(plain(input_value), plain(output_value))
    if problem:
        return result(False, problem)
    return result(True, "the games are the bundled season's", games=len(output_value.games))


def verify_task(arguments, output, reference, workspace):
    problem = output_problem(plain(arguments), plain(output))
    if problem:
        return result(False, problem)
    return result(
        True,
        f"the {len(output.games)} games of {output.season.value} through {output.through_date} are listed, unchanged",
        games=len(output.games),
    )
