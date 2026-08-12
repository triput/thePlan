"""CLI entrypoint for schedule runs."""

from __future__ import annotations

import argparse
from uuid import UUID

from app.scheduler.replan import run_replan


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a schedule replan worker")
    parser.add_argument("--run-id", required=True, type=UUID, help="Schedule run UUID")
    args = parser.parse_args()
    run_replan(args.run_id)


if __name__ == "__main__":
    main()
