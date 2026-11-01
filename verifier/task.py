"""The rank-teams verdict: 10 constraints, in order, judged against the standings re-derived from the
pinned season (never a stored answer)."""

from . import rules
from .checks import fail, hold, listed, plain, shown, skip, verdict
from .pin import key_problem
from .tally import read_receipt

TEXT = {
    "answer-key": "The answer key is pinned for this task",
    "answer-key-data": "The pinned games are the bundled season and the pinned standings follow the rules on them",
    "task-echo": "The submission names the task's season and through_date",
    "agent-read": "tally_records was called in this run for this season and date, on the pinned season",
    "teams-complete": "Every team appears exactly once",
    "records-exact": "Each team's wins, losses and point_diff are its record through the date",
    "pct-exact": "Each team's win_pct is its record to 3 decimals, half away from zero",
    "order-exact": "The teams are in standings order: share of games won, then point differential, then name",
    "ranks-sequential": "The ranks run 1 to 8 down the table",
    "gb-exact": "Each team's games_behind is measured from the first-ranked team",
}
INTEGRITY = ("answer-key", "answer-key-data", "task-echo", "agent-read")  # a failure here scores 0


def label(row):
    return f"{row['team']} {row['wins']}-{row['losses']}"


def verify_task(arguments, output, reference, workspace):
    checks = []
    task, given = plain(arguments), plain(output)
    pin = None if reference is None else plain(reference)
    names = {"season": task["season"], "through_date": task["through_date"]}

    # 1 answer-key
    if pin is None:
        fail(checks, "answer-key", TEXT["answer-key"], "No answer key: pin_standings was not run for this task.", expected=names)
    elif any(pin[name] != value for name, value in names.items()):
        pinned = {name: pin[name] for name in names}
        fail(checks, "answer-key", TEXT["answer-key"], f"The answer key is for another task: {pinned}, not {names}.", expected=names, actual=pinned)
    else:
        hold(checks, "answer-key", TEXT["answer-key"], expected=names, actual=names)
    if not checks[-1]["ok"]:
        for name in list(TEXT)[1:]:
            skip(checks, name, TEXT[name], "answer-key")
        return verdict(checks, 0.0, "", expected=None, right_rows=0)

    # 2 answer-key-data
    problem = key_problem(pin)
    if problem:
        fail(checks, "answer-key-data", TEXT["answer-key-data"], f"{problem[0].upper()}{problem[1:]}.", expected=pin["season_sha256"])
        for name in list(TEXT)[2:]:
            skip(checks, name, TEXT[name], "answer-key-data")
        return verdict(checks, 0.0, "", expected=None, right_rows=0)
    hold(checks, "answer-key-data", TEXT["answer-key-data"], expected=pin["season_sha256"], actual=pin["season_sha256"])

    counted = rules.through(pin["games"], task["through_date"])
    expected = rules.standings(counted)
    by_team = {row["team"]: row for row in expected}

    # 3 task-echo
    echoed = {name: given[name] for name in names}
    if echoed != names:
        fail(checks, "task-echo", TEXT["task-echo"], f"The submission is for {echoed}, not the task {names}.", expected=names, actual=echoed)
    else:
        hold(checks, "task-echo", TEXT["task-echo"], expected=names, actual=echoed)

    # 4 agent-read
    receipt, problem = read_receipt(workspace, task["season"], task["through_date"])
    if problem:
        fail(checks, "agent-read", TEXT["agent-read"], f"{problem[0].upper()}{problem[1:]}.", expected=pin["season_sha256"])
    elif receipt["season_sha256"] != pin["season_sha256"] or receipt["games"] != pin["games"]:
        fail(checks, "agent-read", TEXT["agent-read"], "The season tally_records read is not the pinned season.", expected=pin["season_sha256"], actual=receipt["season_sha256"])
    elif receipt["written_at"] < pin["pinned_at"]:
        fail(
            checks,
            "agent-read",
            TEXT["agent-read"],
            f"The receipt was written at {receipt['written_at']}, before the answer key was pinned at {pin['pinned_at']}: it is left over "
            "from an earlier run. Call tally_records in this run.",
            expected=pin["pinned_at"],
            actual=receipt["written_at"],
        )
    else:
        hold(checks, "agent-read", TEXT["agent-read"], expected=pin["season_sha256"], actual=receipt["season_sha256"])

    # 5 teams-complete
    rows = given["rows"]
    teams = [row["team"] for row in rows]
    twice = sorted({team for team in teams if teams.count(team) > 1})
    missing = [team for team in rules.TEAMS if team not in teams]
    if twice or missing:
        problems = []
        if twice:
            problems.append(f"{listed(twice)} {'appears' if len(twice) == 1 else 'appear'} more than once")
        if missing:
            problems.append(f"{listed(missing)} {'is' if len(missing) == 1 else 'are'} missing")
        fail(checks, "teams-complete", TEXT["teams-complete"], "The table is malformed: " + "; ".join(problems) + ".", expected=list(rules.TEAMS), actual=shown(teams))
        for name in list(TEXT)[5:]:
            skip(checks, name, TEXT[name], "teams-complete")
        return verdict(checks, 0.0, "", expected=expected, right_rows=0)
    hold(checks, "teams-complete", TEXT["teams-complete"], expected=list(rules.TEAMS), actual=teams)

    # 6 records-exact
    wrong = [row for row in rows if (row["wins"], row["losses"], row["point_diff"]) != (by_team[row["team"]]["wins"], by_team[row["team"]]["losses"], by_team[row["team"]]["point_diff"])]
    if wrong:
        first, right = wrong[0], by_team[wrong[0]["team"]]
        fail(
            checks,
            "records-exact",
            TEXT["records-exact"],
            f"{first['team']} is given as {first['wins']}-{first['losses']} with point_diff {first['point_diff']:+d}, but its record through "
            f"{task['through_date']} is {right['wins']}-{right['losses']} with point_diff {right['point_diff']:+d}."
            + (f" Also wrong: {listed(row['team'] for row in wrong[1:])}." if len(wrong) > 1 else ""),
            expected=[f"{label(row)} {row['point_diff']:+d}" for row in expected],
            actual=[f"{label(row)} {row['point_diff']:+d}" for row in rows],
        )
    else:
        hold(checks, "records-exact", TEXT["records-exact"], expected=[f"{label(row)} {row['point_diff']:+d}" for row in expected], actual=[f"{label(row)} {row['point_diff']:+d}" for row in rows])

    # 7 pct-exact
    wrong = [row for row in rows if row["win_pct"] != by_team[row["team"]]["win_pct"]]
    if wrong:
        first, right = wrong[0], by_team[wrong[0]["team"]]
        fail(
            checks,
            "pct-exact",
            TEXT["pct-exact"],
            f"{first['team']}'s win_pct is given as {first['win_pct']}, but {right['wins']} of {right['wins'] + right['losses']} games is "
            f"{right['win_pct']:.3f} (3 decimals, half away from zero)." + (f" Also wrong: {listed(row['team'] for row in wrong[1:])}." if len(wrong) > 1 else ""),
            expected=[f"{row['team']} {row['win_pct']:.3f}" for row in expected],
            actual=[f"{row['team']} {row['win_pct']}" for row in rows],
        )
    else:
        hold(checks, "pct-exact", TEXT["pct-exact"], expected=[f"{row['team']} {row['win_pct']:.3f}" for row in expected], actual=[f"{row['team']} {row['win_pct']}" for row in rows])

    # 8 order-exact
    order = [row["team"] for row in expected]
    if teams != order:
        first = next(index for index, (ours, theirs) in enumerate(zip(teams, order)) if ours != theirs)
        above, below = by_team[teams[first]], by_team[order[first]]
        if rules.fraction_won(above) != rules.fraction_won(below):
            why = f"{below['team']} has won a greater share of its games ({below['wins']}-{below['losses']} against {above['wins']}-{above['losses']})"
        elif above["point_diff"] != below["point_diff"]:
            why = f"both are {below['wins']}-{below['losses']} and {below['team']}'s point differential is greater ({below['point_diff']:+d} against {above['point_diff']:+d})"
        else:
            why = f"both are {below['wins']}-{below['losses']} with point differential {below['point_diff']:+d}, and {below['team']} comes first by name"
        fail(
            checks,
            "order-exact",
            TEXT["order-exact"],
            f"Position {first + 1} holds {teams[first]}, but {order[first]} belongs there: {why}.",
            expected=order,
            actual=teams,
        )
    else:
        hold(checks, "order-exact", TEXT["order-exact"], expected=order, actual=teams)

    # 9 ranks-sequential
    ranks = [row["rank"] for row in rows]
    if ranks != list(range(1, len(rows) + 1)):
        fail(checks, "ranks-sequential", TEXT["ranks-sequential"], f"The ranks are {ranks}, not 1 to {len(rows)} down the table.", expected=list(range(1, len(rows) + 1)), actual=ranks)
    else:
        hold(checks, "ranks-sequential", TEXT["ranks-sequential"], expected=ranks, actual=ranks)

    # 10 gb-exact
    leader = expected[0]
    wrong = [row for row in rows if row["games_behind"] != by_team[row["team"]]["games_behind"]]
    if wrong:
        first, right = wrong[0], by_team[wrong[0]["team"]]
        fail(
            checks,
            "gb-exact",
            TEXT["gb-exact"],
            f"{first['team']}'s games_behind is given as {first['games_behind']}, but from the leader {leader['team']} ({leader['wins']}-{leader['losses']}) "
            f"it is (({leader['wins']} - {right['wins']}) + ({right['losses']} - {leader['losses']})) / 2 = {right['games_behind']}."
            + (f" Also wrong: {listed(row['team'] for row in wrong[1:])}." if len(wrong) > 1 else ""),
            expected=[f"{row['team']} {row['games_behind']}" for row in expected],
            actual=[f"{row['team']} {row['games_behind']}" for row in rows],
        )
    else:
        hold(checks, "gb-exact", TEXT["gb-exact"], expected=[f"{row['team']} {row['games_behind']}" for row in expected], actual=[f"{row['team']} {row['games_behind']}" for row in rows])

    # The score: 0 when the data or the submission's integrity fails; otherwise the share of rows that are exactly right.
    right_rows = sum(row == by_team[row["team"]] for row in rows)
    score = 0.0 if any(check["ok"] is False for check in checks if check["id"] in INTEGRITY) else right_rows / len(expected)
    summary = f"{leader['team']} leads {task['season']} through {task['through_date']} at {leader['wins']}-{leader['losses']}, over {len(counted)} games."
    return verdict(checks, score, summary, expected=expected, right_rows=right_rows)
