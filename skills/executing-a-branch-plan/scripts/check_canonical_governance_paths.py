"""Deterministic pre-filter for step 6's per-task diff screening.

references/threat-model-and-authorization.md's "Per-task screening"
section delegates the full diff review to screening-a-low-trust-
contribution's checks 2-5 (workflow-file edits, edits to existing
governance/instruction files, hook/script changes, dependency
additions). This script mechanizes only the literal/canonical subset of
those checks -- an exact filename or exact-prefix match against the
illustrative examples those checks already name -- leaving every other
case (a glob-shaped path, a rename, a non-canonical execution surface
such as a composite GitHub Action under .github/actions/**) to the
model's own full-diff review. A pre-filter, not a full replacement: a
clean result from this script is never itself grounds to skip that
review.

Read-only: classifies a given list of file paths only; makes no git
calls itself and reads no repository state beyond the paths it is
handed. Deliberately no glob module and no regex wildcard beyond the
one documented "skills/<name>/..." two-segment shape, checked via
explicit path-segment splitting -- pure string matching, matching the
issue's own framing of what a pre-filter this narrow can safely claim.

Usage:
  python3 check_canonical_governance_paths.py --files <path-to-file-list>
  git diff --name-only BASE HEAD | python3 check_canonical_governance_paths.py

Input: one file path per line (a file, via --files, or stdin).

Exit code: 0 on a successful run (this is an informational classifier,
not a gate -- a "no-match" classification is not itself a pass/fail
verdict, only a signal that the model's own review is where that path
gets judged). 2 on usage error (e.g. the given --files path does not
exist).
"""
from __future__ import annotations

import argparse
import sys

# Exact-prefix or exact-filename matches only, drawn from
# screening-a-low-trust-contribution/SKILL.md checks 2, 4, and 5's own
# illustrative examples -- not exhaustive, and deliberately not meant to
# be: this is the literal/canonical subset only, matching this script's
# own module docstring.
_WORKFLOW_PREFIXES = (".github/workflows/", ".gitlab/", ".circleci/")
_WORKFLOW_FILENAMES = (".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile")

_GOVERNANCE_FILENAMES = (
    "CLAUDE.md",
    "AGENTS.md",
    "CODEOWNERS",
    ".gitmodules",
    ".github/dependabot.yml",
    "renovate.json",
    ".claude/settings.json",
)

_HOOK_SCRIPT_PREFIXES = ("hooks/", ".github/scripts/")

_DEPENDENCY_MANIFEST_FILENAMES = (
    "pyproject.toml",
    "uv.lock",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "Gemfile",
    "Gemfile.lock",
    "requirements.txt",
)


def _normalize(path):
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _is_skill_governance_path(segments):
    """skills/<name>/SKILL.md or skills/<name>/metadata/gitapex.yaml --
    checked by explicit segment count/shape, not a glob pattern."""
    if len(segments) == 3 and segments[0] == "skills" and segments[2] == "SKILL.md":
        return True
    if len(segments) == 4 and segments[0] == "skills" and segments[2] == "metadata" and segments[3] == "gitapex.yaml":
        return True
    return False


def _is_skill_scripts_path(segments):
    """skills/<name>/scripts/... -- checked by explicit segment shape."""
    return len(segments) >= 4 and segments[0] == "skills" and segments[2] == "scripts"


def classify(path):
    """Return one of 'workflow', 'governance', 'hook-script',
    'dependency-manifest', or 'no-match' for a single (already-relative)
    file path."""
    normalized = _normalize(path)
    segments = normalized.split("/")

    if normalized.startswith(_WORKFLOW_PREFIXES) or normalized in _WORKFLOW_FILENAMES:
        return "workflow"
    if normalized in _GOVERNANCE_FILENAMES or _is_skill_governance_path(segments):
        return "governance"
    if normalized.startswith(_HOOK_SCRIPT_PREFIXES) or _is_skill_scripts_path(segments):
        return "hook-script"
    if normalized in _DEPENDENCY_MANIFEST_FILENAMES:
        return "dependency-manifest"
    return "no-match"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Classify changed file paths as a literal/canonical "
        "workflow, governance, hook-script, or dependency-manifest match, "
        "or 'no-match' (needs the model's own full-diff review)."
    )
    parser.add_argument(
        "--files",
        help="Path to a file listing one changed path per line; reads "
        "standard input when omitted.",
    )
    args = parser.parse_args(argv)
    try:
        raw_text = (
            open(args.files, encoding="utf-8").read() if args.files else sys.stdin.read()
        )
    except FileNotFoundError:
        print(f"error: files list not found: {args.files}", file=sys.stderr)
        return 2

    paths = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not paths:
        print("no paths given")
        return 0

    no_match_count = 0
    for path in paths:
        category = classify(path)
        if category == "no-match":
            no_match_count += 1
        print(f"{category}: {path}")

    print(
        f"SUMMARY: {len(paths)} path(s), {len(paths) - no_match_count} "
        f"canonical match(es), {no_match_count} needing the model's own "
        "full-diff review. A clean pre-filter result is never itself "
        "grounds to skip that review."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
