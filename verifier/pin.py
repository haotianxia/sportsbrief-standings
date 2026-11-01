"""pin_standings, the rank-teams reference: its date is a calendar day and its answer key follows the rules."""

from . import rules
from .checks import plain, result


def key_problem(pin):
    """What is wrong with the plain answer key ``pin``, or None: its games are the bundled season and
    its rows are the standings the rules give through its date."""
    problem = rules.date_problem(pin["through_date"])
    if problem:
        return f"the pinned through_date is not a calendar date: {problem}"
    problem = rules.stamp_problem(pin["pinned_at"])
    if problem:
        return f"the pinned time is not a UTC time: {problem}"
    problem = rules.season_problem(pin["season"], pin["games"])
    if problem:
        return f"the pinned games are not the bundled {pin['season']}: {problem}"
    if pin["season_sha256"] != rules.sha256(pin["games"]):
        return "the pinned games do not match their own sha256"
    if pin["rows"] != rules.standings(rules.through(pin["games"], pin["through_date"])):
        return "the pinned standings are not what the rules give on the pinned games through the date"
    return None


def verify_input(value):
    problem = rules.date_problem(value.through_date)
    return result(False, f"through_date: {problem}") if problem else result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    given, pin = plain(input_value), plain(output_value)
    for name in ("season", "through_date"):
        if pin[name] != given[name]:
            return result(False, f"the answer key's {name} is {pin[name]!r}, not the task's {given[name]!r}")
    problem = key_problem(pin)
    if problem:
        return result(False, problem)
    return result(True, "the answer key follows the rules", games=len(rules.through(pin["games"], pin["through_date"])))
