# ==============================================================================
#  File: apps/cli/theplan/cli_argv.py
#  Description: Global option placement helpers for thePlan CLI (DEF-047).
#  Component: CLI
#  Version: 1.0
#  Created: 2026-10-14
#  Last Update: 2026-10-14
# ==============================================================================

"""Hoist global flags so they work before or after the subcommand.

Argparse only binds root options before the command token. Operators and agents
often put ``--format`` after the verb; hoist it (and ``--interactive``) to the
front before parse. Conflicting duplicate ``--format`` values are rejected.
"""

from __future__ import annotations

from theplan.errors import CliError

_FORMAT_CHOICES = frozenset({"json", "text"})


def hoist_global_options(argv: list[str]) -> list[str]:
    """Return argv with ``--format`` / ``--interactive`` moved to the front.

    Stops at ``--``. Duplicate ``--format`` with the same value is fine; mixed
    values raise ``CliError``.
    """
    formats: list[str] = []
    interactive = False
    rest: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--":
            rest.extend(argv[i:])
            break
        if arg == "--format":
            if i + 1 >= len(argv):
                rest.append(arg)
                i += 1
                continue
            formats.append(argv[i + 1])
            i += 2
            continue
        if arg.startswith("--format="):
            formats.append(arg.split("=", 1)[1])
            i += 1
            continue
        if arg == "--interactive":
            interactive = True
            i += 1
            continue
        rest.append(arg)
        i += 1

    prefix: list[str] = []
    if formats:
        unique = {value.lower() for value in formats}
        if len(unique) > 1:
            shown = ", ".join(formats)
            raise CliError(
                code="INVALID_USAGE",
                message=(
                    f"Conflicting --format values: {shown}. "
                    "Use a single --format json|text "
                    "(accepted before or after the subcommand)."
                ),
                exit_code=1,
            )
        fmt = formats[-1]
        if fmt.lower() not in _FORMAT_CHOICES:
            # Keep original token for argparse's choice error.
            prefix.extend(["--format", fmt])
        else:
            prefix.extend(["--format", fmt.lower()])
    if interactive:
        prefix.append("--interactive")
    return prefix + rest
