"""Worktree runner for trust-only disconnect baseline @ fdfaa448^ (evidence only)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

BASELINE_PARENT_SHA = "8c83c03aec2f92b92ac1251ff66d20ca1efd43f4"
BASELINE_PARENT_SHORT = "8c83c03"
BASELINE_TEST_REL = Path("apps/api/tests/baseline/t1_trust_only_disconnect_pre_fdfaa448.py")
WORKTREE_DIRNAME = f"t1-disconnect-baseline-{BASELINE_PARENT_SHORT}"


def repo_root_from_here() -> Path:
    # .../apps/api/tests/support/this_file.py → repo root
    return Path(__file__).resolve().parents[4]


def baseline_worktree_path(repo_root: Path | None = None) -> Path:
    root = repo_root or repo_root_from_here()
    return root / ".worktrees" / WORKTREE_DIRNAME


def ensure_baseline_worktree(repo_root: Path | None = None) -> Path:
    root = repo_root or repo_root_from_here()
    wt = baseline_worktree_path(root)
    git_dir = wt / ".git"
    if not git_dir.exists():
        wt.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "--detach",
                str(wt),
                BASELINE_PARENT_SHA,
            ],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    src_test = root / BASELINE_TEST_REL
    if not src_test.is_file():
        raise FileNotFoundError(f"baseline test missing on tip: {src_test}")
    dst_test = wt / BASELINE_TEST_REL
    dst_test.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_test, dst_test)
    return wt


def run_baseline_pytest(
    *,
    repo_root: Path | None = None,
    python_exe: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    root = repo_root or repo_root_from_here()
    wt = ensure_baseline_worktree(root)
    api_root = wt / "apps" / "api"
    tip_api = root / "apps" / "api"
    venv_python = tip_api / ".venv" / "Scripts" / "python.exe"
    py = python_exe or (venv_python if venv_python.is_file() else Path(sys.executable))
    env = os.environ.copy()
    env.setdefault("T1A_REQUIRE_DISPOSABLE_DSN", "1")
    env.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg://t1a@127.0.0.1:5433/theplan_t1a_test",
    )
    return subprocess.run(
        [
            str(py),
            "-m",
            "pytest",
            "tests/baseline/t1_trust_only_disconnect_pre_fdfaa448.py",
            "-q",
            "--tb=short",
        ],
        cwd=api_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


if __name__ == "__main__":
    proc = run_baseline_pytest()
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    raise SystemExit(proc.returncode)
