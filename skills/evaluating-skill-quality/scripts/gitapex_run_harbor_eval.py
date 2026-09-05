#!/usr/bin/env python3
"""Thin Harbor invocation wrapper for evaluating-skill-quality (issue #1813).

Builds and runs `uv run --group harbor harbor run ...` against a Harbor
dataset directory. Deliberately thin: no grading, no aggregation, no secret
handling -- model credentials travel by environment passthrough (e.g.
OPENCODE_API_KEY for the `opencode` provider), resolved inside the Harbor
agent itself and never passed as arguments here.

Preflight failures (no Docker daemon, no harbor) exit 2 with guidance text,
never a traceback. The exact invocation is this module's own `--help`.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

# Harbor agent default: the pre-integrated agent needing no custom adapter.
DEFAULT_AGENT = "opencode"
# Model default: the free Zen tier verified live for Harbor runs (issue #1813).
DEFAULT_MODEL = "opencode/muse-spark-1.3-contributor-free"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments (see `--help` for the exact invocation)."""
    parser = argparse.ArgumentParser(description="Run a Harbor dataset directory (thin wrapper, issue #1813).")
    parser.add_argument(
        "--tasks",
        required=True,
        help="Harbor dataset directory to run (passed as harbor -p).",
    )
    parser.add_argument("--agent", default=DEFAULT_AGENT, help="Harbor agent (default: opencode).")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model in provider/name form.")
    parser.add_argument(
        "--setup-timeout-multiplier",
        type=float,
        default=1.0,
        help="Multiplier for the agent-setup timeout (slow egress).",
    )
    parser.add_argument(
        "--build-timeout-multiplier",
        type=float,
        default=1.0,
        help="Multiplier for the environment-build timeout.",
    )
    return parser.parse_args(argv)


def build_command(args: argparse.Namespace) -> list[str]:
    """Assemble the harbor invocation (pure; no secrets ever enter it)."""
    tasks: str = args.tasks
    agent: str = args.agent
    model: str = args.model
    setup_mult: float = args.setup_timeout_multiplier
    build_mult: float = args.build_timeout_multiplier
    cmd = [
        "uv",
        "run",
        "--group",
        "harbor",
        "harbor",
        "run",
        "-p",
        tasks,
        "-a",
        agent,
        "-m",
        model,
    ]
    if setup_mult != 1.0:
        cmd += ["--agent-setup-timeout-multiplier", str(setup_mult)]
    if build_mult != 1.0:
        cmd += ["--environment-build-timeout-multiplier", str(build_mult)]
    return cmd


def check_docker() -> str | None:
    """Return guidance text when Docker is unusable, else None."""
    if shutil.which("docker") is None:
        return "Docker CLI not found. Install Docker Desktop and ensure `docker` is on PATH, then retry."
    proc = subprocess.run(
        ["docker", "ps"],  # noqa: S607 -- resolved via shutil.which above
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return "Docker daemon is not reachable (`docker ps` failed). Start Docker Desktop and retry."
    return None


def check_harbor() -> str | None:
    """Return guidance text when harbor is unavailable, else None."""
    proc = subprocess.run(
        ["uv", "run", "--group", "harbor", "harbor", "--version"],  # noqa: S607 -- PATH-resolved tool names only
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return (
            "Harbor is not available via the project's `harbor` dependency "
            "group. Run `uv sync --group harbor` first (see pyproject.toml)."
        )
    return None


def main(argv: list[str] | None = None) -> int:
    """Run preflight checks, then exec harbor. Returns the exit code."""
    args = parse_args(argv)
    problem = check_docker()
    if problem is None:
        problem = check_harbor()
    if problem is not None:
        print(f"gitapex_run_harbor_eval: {problem}", file=sys.stderr)
        return 2
    proc = subprocess.run(build_command(args))  # noqa: S603 -- argv built by build_command from fixed strings + a local path, no shell
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
