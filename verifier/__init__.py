"""The deterministic verifier: each tool's checks live in its own module, on contract instances."""

from contract import Task, Tool

from . import games, pin, tally, task

TOOLS = {
    Tool.PIN_STANDINGS: pin,
    Tool.LIST_GAMES: games,
    Tool.TALLY_RECORDS: tally,
}
# task -> its output's check, verify_task(arguments, output, reference, workspace)
TASKS = {Task.RANK_TEAMS: task.verify_task, Task.LIST_GAMES: games.verify_task}


def verify_input(tool, value):
    return TOOLS[Tool(tool)].verify_input(value)


def verify_output(tool, input_value, output_value, workspace):
    return TOOLS[Tool(tool)].verify_output(input_value, output_value, workspace)


def verify_task(task, arguments, output, reference, workspace):
    return TASKS[Task(task)](arguments, output, reference, workspace)
