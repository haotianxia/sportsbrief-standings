# League Standings

A `nanoagent.plugin/v0001` plugin with the structure of NanoAgent's reference
plugin, [arxiv-source](https://github.com/zeyuyang8/arxiv-source). Its task,
`rank-teams`, gives an agent a bundled season of a fictional eight-team league
and a date. The agent must build the standings through that day: every team's
record, winning percentage, games behind and point differential, ranked with
the league's tiebreakers. The answer key pins the whole season's results, and
a rule-based verifier rebuilds the table from them: 10 constraints, every one
of which must hold. Nothing leaves the machine: the data is bundled and the
plugin declares no network host.

## Tools

| Tool | Does | Code |
|---|---|---|
| `pin_standings` | The answer key. Pins every game of the season (with the season's sha256) and the standings the rules give through the date | `src/plugin/standings.py`, `src/plugin/rules.py` |
| `list_games` | The games played on or before a date, in date order, with the season's sha256 | `src/plugin/standings.py` |
| `tally_records` | Every team's wins, losses, points for and against over the games played on or before the date, in alphabetical order. Writes a receipt of the season it read to `standings/<season>-<date>.json` | `src/plugin/standings.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `rank-teams` | Ranks all 8 teams through the date, with record, `win_pct`, `games_behind` and `point_diff`, and submits the table | `agent`, with `tally_records`; reference `pin_standings` |
| `list-games` | Lists a season's games through a date, so a person can read the results | `tool` (`list_games`) |

## The task

Before the agent starts, NanoAgent runs `pin_standings` with the task input in
a scratch workspace the agent never sees, and pins its output. The agent then
has `tally_records` and `submit`, and two steps: `tally_records` once with the
task's season and date, then `submit`.

The tool tallies; the agent ranks. From each team's wins, losses, points for
and points against, the agent computes `point_diff`, `win_pct` (to 3 decimals,
half away from zero), the order (share of games won, then point differential,
then name), the ranks and `games_behind` from the first-ranked team.

## Ground truth

The ground truth is the pinned season, never a stored answer. The rules in
`src/plugin/rules.py` (`verifier/rules.py` is a byte-for-byte copy, and
`verifier/data.py` of `src/plugin/data.py`, both enforced by a test) define
everything the verifier re-derives:

- A **date** is a calendar day `YYYY-MM-DD` (months and leap years checked);
  games on or before it count, compared as text.
- A **record** is wins, losses, points for and against over those games; a
  team with no games is 0-0.
- `win_pct` is `wins / (wins + losses)` as a `Decimal` quantized to 3 places,
  `ROUND_HALF_UP`; 0.0 with no games.
- The **order** sorts by the exact `Fraction` of games won, then point
  differential, then name. Ranks are positions 1 to 8.
- `games_behind` is `((leader wins - wins) + (losses - leader losses)) / 2`,
  exact in halves, and negative only when a team's wins exceed the leader's
  by more than its losses do (possible only when the leader has played fewer
  games; never in the bundled seasons).
- **This run's receipt.** The answer key records when it was pinned and
  `tally_records` records when it wrote its receipt, both UTC times; a
  receipt written before the answer key was pinned is an earlier run's and
  fails `agent-read`.
- Each bundled season's canonical-JSON sha256 is recorded in the rules, so a
  pinned or received season that is not the bundled one is refused.

The two seasons (`src/plugin/data.py`) are fictional. The 2026 season is
built so that on 2026-10-26 three teams are 2-2 with the same +3 differential
(ranked by name), on 2026-10-29 two teams are 3-2 with the same +11, and a
date before the first game gives eight 0-0 rows ranked by name.

## Constraints

`verifier/task.py` judges the submission against 10 constraints, in order.
Every entry of the verdict's `details.constraints` has the keys
`{id, constraint, ok, expected, actual, message}`; `ok` is `true`, `false`, or
`null` when a check it needs did not hold.

| # | id | What it checks |
|---|---|---|
| 1 | `answer-key` | The answer key is pinned for this task's season and date |
| 2 | `answer-key-data` | The pinned games are the bundled season (sha256) and the pinned rows follow the rules on them |
| 3 | `task-echo` | The submission names the task's season and date |
| 4 | `agent-read` | `tally_records` was called in this run for this season and date: its receipt holds the pinned season and was written after the answer key was pinned |
| 5 | `teams-complete` | Every team appears exactly once |
| 6 | `records-exact` | Each team's wins, losses and `point_diff` are its record through the date |
| 7 | `pct-exact` | Each team's `win_pct` is its record to 3 decimals, half away from zero |
| 8 | `order-exact` | The teams are in standings order (the message says which tiebreaker decides) |
| 9 | `ranks-sequential` | The ranks run 1 to 8 down the table |
| 10 | `gb-exact` | Each team's `games_behind` is measured from the first-ranked team |

Valid only when all 10 hold, with score 1.0. Any failure among 1 to 4 scores
0; a malformed table (5) scores 0; otherwise the score is the share of the 8
rows that are exactly right, at most 0.99. Every tool call is checked as well:
`verify_input` refuses a date that is not a calendar day, and `verify_output`
holds `tally_records` to the rules applied to its own receipt, `list_games` to
the bundled season, and the answer key to the rules applied to the pinned games.

## Limitations

- **Fixed seasons.** Only the two bundled seasons can be judged; results the
  person pastes would need a hash the verifier knows.
- **The receipt is tied to the run by the clock, not by a run id.** A receipt
  written before the answer key was pinned is refused, so a receipt an earlier
  task left in the workspace no longer passes; two runs of the same input in
  the same second could still share one. A host-given run id would close that.
- **The plan is guidance.** The verdict judges the submission and the receipt,
  not how many tool calls were made.
- **No head-to-head tiebreaker.** Ties break by point differential and then
  by name, which is simpler than most leagues' rules; the rule is stated and
  checked, not realistic.
- **Eight teams, nine games each.** Small enough for every record to fit one
  tool answer and the agent's reasoning; a long season would need the tool to
  rank as well.

## Layout

```text
.
├── nanoagent.yaml   # manifest (a slimconfig ManifestConfig): id, runtime, permissions (no hosts), tools, tasks
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # environment variable NAMEs this plugin needs (none)
├── src/plugin/      # the MCP server (__main__.py), the tools (standings.py), the rules (rules.py) and the seasons (data.py)
├── tests/           # the rules, the tools, the data's hashes, and the verifier on gold, broken, malformed and boundary runs
├── ui/              # how the page draws the outputs: renderers.js and renderers.css (the schema drawing)
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier: one module per tool, the task's 10 constraints in task.py, copies of rules.py and data.py
```

## Develop and run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

NanoAgent passes the folder the plugin may write to as `NANOAGENT_WORKSPACE`.
`tally_records` writes its receipt there, under `standings/`, so a run that
went wrong can be read back. Run the tool task from NanoAgent with a config
naming `task: list-games` and a JSON file such as
`{"season": "gcbl-2026", "through_date": "2026-10-26"}` as its `arguments`;
run the agent task with `nanoagent plugin agent` and the same input.
