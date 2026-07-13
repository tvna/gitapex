#!/usr/bin/env python3
"""Validate generated Issue/PR templates for a single platform.

Self-check for the seeding-issue-pr-templates skill: after the skill writes
template files, it runs this on the target repo root to confirm the output is
structurally valid before presenting it. A run targets exactly one platform
(a repo remote is GitHub or GitLab, never both), so this checks one platform
per invocation.

Usage:
    uv run --with pyyaml python validate_templates.py <repo_root> \\
        [--platform {github,gitlab}]

Exit codes:
    0  all templates valid
    1  validation failures found (each printed, one per line)
    2  usage / environment error (bad dir, ambiguous platform, missing pyyaml)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:  # pyyaml is the one runtime dependency.
    sys.stderr.write(
        "error: pyyaml is required. Run via: "
        "uv run --with pyyaml python validate_templates.py <repo_root>\n"
    )
    raise SystemExit(2)


def detect_platform(repo_root: Path) -> str:
    """Return 'github' or 'gitlab' from the repo layout, else raise ValueError.

    .github/ISSUE_TEMPLATE marks GitHub; .gitlab/issue_templates marks GitLab.
    If both or neither are present, the caller must pass --platform rather
    than guess.
    """
    has_github = (repo_root / ".github" / "ISSUE_TEMPLATE").is_dir()
    has_gitlab = (repo_root / ".gitlab" / "issue_templates").is_dir()
    if has_github and not has_gitlab:
        return "github"
    if has_gitlab and not has_github:
        return "gitlab"
    raise ValueError(
        f"cannot auto-detect platform (github={has_github}, "
        f"gitlab={has_gitlab}); pass --platform"
    )
