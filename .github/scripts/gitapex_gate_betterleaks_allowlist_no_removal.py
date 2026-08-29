#!/usr/bin/env python3
"""Gate: fail when a PR removes a `.betterleaks.toml` `[allowlist].paths`
entry that was present at the PR's base commit, unless the removal carries
an explicit waiver comment (issue #1427, retrospective #1308 repair 3).

**The regression this closes.** During PR #1305, a fix-up commit touched
`.betterleaks.toml`'s allowlist while resolving an unrelated CI failure and,
in doing so, replaced a renamed fixture's old-path entries instead of
keeping both old and new paths -- directly against that file's own
documented rule ("a renamed fixture needs BOTH names, never replace"; see
`.betterleaks.toml`'s own `[allowlist].description`). Nothing caught this
deterministically before CI's `betterleaks-merge-gate` (issue #894) full-
history scan surfaced it as four confusing false-positive "leak" reports
against already-reviewed historical content. This gate diffs the allowlist
itself, structurally, so the same class of edit fails fast and legibly
instead of surfacing as an unrelated secret-scan detour.

**Structural, not line-based.** `.betterleaks.toml`'s `paths` array is
parsed with `tomllib` at both the PR's base commit and its head (`HEAD`),
so reordering or reformatting the array never false-positives -- only an
actual entry present at base and absent at head does.

**Base-ref resolution reuses `_gitapex_base_ref.py`** (issue #1345), the
same shared helper family `gitapex_gate_behind_base.py` (issue #985) and
`gitapex_run_base_diff.py` (issue #1178's own `local_stdin` producer)
already use, rather than a new bespoke fetch/diff mechanism. On the
`local` plane this gate fetches `origin/main` and resolves the merge-base
with `HEAD` itself, mirroring `gitapex_gate_behind_base.py`'s own
fetch-every-run posture. On the `ci` plane the calling workflow already
has full history (`fetch-depth: '0'`) and both endpoints' SHAs from the
pull_request event, so it computes the merge-base itself and passes it via
`--merge-base` -- no network fetch needed there, matching how
`detection-logic-property-coverage-gate.yml` computes its own merge-base
inline rather than reusing the local-only `gitapex_run_base_diff.py`.

**Waiver.** A legitimate full removal (an old-path fixture permanently
deleted, not renamed) is not blocked forever: a
`# betterleaks-allowlist-no-removal: WAIVED: <reason>` comment anywhere in
the head version of `.betterleaks.toml` that quotes the removed entry's
`'''<entry>'''` TOML array literal verbatim (the same triple-single-quoted
syntax the entry is written with in `paths`) waives that one entry -- a
bare substring match of the entry's raw text is deliberately not enough,
so a short or common entry cannot be waived merely by coincidental overlap
with the waiver comment's own prose.

Exit codes: 0 no unwaived removal, 1 an unwaived removal was found, 2 the
check could not be trusted (fetch failure, no common ancestor, malformed
TOML, or `--root` not a usable directory) -- mirrors
`gitapex_gate_behind_base.py`'s own 0/1/2 convention.

Run via `uv run` (needed for the pydantic import): `uv run --frozen
python3 .github/scripts/gitapex_gate_betterleaks_allowlist_no_removal.py`
(local plane, fetches `origin/main` itself), or with `--merge-base <sha>`
(CI plane, no fetch).
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import tomllib

import _gitapex_base_ref
from pydantic import BaseModel, ValidationError, field_validator

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Hardcoded per the same posture gitapex_gate_behind_base.py's own
# BASE_REMOTE/BASE_BRANCH constants document (issue #985) -- this
# repository has exactly one base branch today.
BASE_REMOTE = "origin"
BASE_BRANCH = "main"

ALLOWLIST_RELATIVE_PATH = ".betterleaks.toml"

GIT_TIMEOUT_SECONDS = _gitapex_base_ref.GIT_TIMEOUT_SECONDS

# Waiver vocabulary matching this repository's other WAIVED-comment gates
# (e.g. gitapex_gate_detection_logic_property_coverage.py's own
# _WAIVER_RE): "# betterleaks-allowlist-no-removal: WAIVED: <reason>".
# A non-empty reason is required (\S.*); an empty "WAIVED:" waives nothing.
_WAIVER_RE = re.compile(r"#\s*betterleaks-allowlist-no-removal\s*:\s*WAIVED\s*:\s*(?P<body>\S.*)", re.IGNORECASE)


class GateError(Exception):
    """The check could not be trusted -- exit 2, never a silent pass and
    never conflated with a genuine unwaived-removal FAIL (exit 1)."""


def extract_allowlist_paths(toml_text: str) -> list[str]:
    """The `[allowlist].paths` array from `.betterleaks.toml` text, as the
    literal strings they were written with. A missing `[allowlist]` table
    or a missing `paths` key both read as "no entries" -- not a parse
    failure -- since a base commit predating the block, or a head commit
    that deletes the block entirely, are both meaningful states for the
    comparison to catch, not malformed input. A document that is not valid
    TOML at all raises :class:`GateError`."""
    try:
        data = tomllib.loads(toml_text)
    except tomllib.TOMLDecodeError as error:
        raise GateError(f"cannot parse .betterleaks.toml as TOML: {error}") from error
    allowlist = data.get("allowlist", {})
    paths = allowlist.get("paths", []) if isinstance(allowlist, dict) else []
    if not isinstance(paths, list):
        raise GateError("`.betterleaks.toml`'s [allowlist].paths must be an array")
    return [str(entry) for entry in paths]


def waiver_bodies(head_text: str) -> list[str]:
    """Every `<reason>` body from a
    `# betterleaks-allowlist-no-removal: WAIVED: <reason>` comment anywhere
    in `head_text`, in file order. An entry is waived when its own TOML
    array literal (`'''<entry>'''`) appears verbatim inside one of these
    bodies -- see :func:`find_unwaived_removals`."""
    return [match.group("body") for match in _WAIVER_RE.finditer(head_text)]


def find_unwaived_removals(base_text: str, head_text: str) -> list[str]:
    """Entries present in `base_text`'s `[allowlist].paths` and absent from
    `head_text`'s, excluding any entry whose `'''<entry>'''` TOML array
    literal is quoted inside a waiver comment in `head_text` (see
    :func:`waiver_bodies`). Order matches `base_text`'s own array order.

    Matched as `'''<entry>'''`, the same triple-single-quoted syntax the
    entry is written with in `.betterleaks.toml`'s own `paths` array --
    not a bare substring match of the entry's raw text -- so a short or
    common entry (a single character, a short word) cannot be waived by
    coincidence merely because it happens to appear inside the waiver
    comment's ordinary prose."""
    base_paths = extract_allowlist_paths(base_text)
    head_paths = set(extract_allowlist_paths(head_text))
    bodies = waiver_bodies(head_text)
    removed = [entry for entry in base_paths if entry not in head_paths]
    return [entry for entry in removed if not any(f"'''{entry}'''" in body for body in bodies)]


def show_file_at_ref(root: pathlib.Path, ref: str, relative_path: str) -> str:
    """`git show <ref>:<relative_path>`'s content, or `""` when the path
    did not exist at that ref -- `git show` exits nonzero for a missing
    path the same way it does for a genuine failure, and distinguishing
    the two reliably from stderr text alone is not portable across git
    versions, so this treats every nonzero exit as "not present at that
    ref" (a meaningful, legitimate state for the comparison itself to
    read, per :func:`extract_allowlist_paths`'s own docstring) rather than
    raising. A ref that cannot be resolved at all was already caught
    earlier, by :func:`_gitapex_base_ref.require_common_ancestor` or the
    caller's own `--merge-base` validation."""
    result = _gitapex_base_ref.run_git(
        root,
        ["show", f"{ref}:{relative_path}"],
        label=f"read {relative_path} at {ref}",
        timeout=GIT_TIMEOUT_SECONDS,
        error_cls=GateError,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def resolve_merge_base(root: pathlib.Path, base_ref: str) -> str:
    """`git merge-base <base_ref> HEAD`'s own stdout, stripped. Callers run
    :func:`_gitapex_base_ref.require_common_ancestor` first, so a genuine
    "no common ancestor" case is already raised with that function's own
    message before this one ever runs."""
    result = _gitapex_base_ref.run_git(
        root,
        ["merge-base", base_ref, "HEAD"],
        label=f"find a common ancestor with {base_ref}",
        timeout=GIT_TIMEOUT_SECONDS,
        error_cls=GateError,
    )
    if result.returncode != 0:
        raise GateError(f"git merge-base {base_ref} HEAD failed: {result.stderr.strip()}")
    return result.stdout.strip()


def check(root: pathlib.Path, *, merge_base: str | None = None) -> list[str]:
    """The unwaived-removed allowlist entries between the PR's base commit
    and `HEAD` (empty list = pass). When `merge_base` is `None` (the
    `local` plane), fetches `origin/main` and resolves the merge-base with
    `HEAD` itself via `_gitapex_base_ref`. When `merge_base` is given (the
    `ci` plane, the calling workflow's own already-computed merge-base
    SHA), no network fetch runs -- the workflow's `fetch-depth: '0'`
    checkout already makes both commits' content available locally."""
    if merge_base is None:
        _gitapex_base_ref.fetch_destination_refspec(
            root, BASE_REMOTE, BASE_BRANCH, timeout=GIT_TIMEOUT_SECONDS, error_cls=GateError
        )
        qualified_ref = f"refs/remotes/{BASE_REMOTE}/{BASE_BRANCH}"
        _gitapex_base_ref.require_common_ancestor(root, qualified_ref, timeout=GIT_TIMEOUT_SECONDS, error_cls=GateError)
        merge_base = resolve_merge_base(root, qualified_ref)

    base_text = show_file_at_ref(root, merge_base, ALLOWLIST_RELATIVE_PATH)
    head_text = show_file_at_ref(root, "HEAD", ALLOWLIST_RELATIVE_PATH)
    return find_unwaived_removals(base_text, head_text)


class GateBetterleaksAllowlistNoRemovalArgs(BaseModel):
    """Typed view of `main`'s parsed CLI namespace, mirroring
    `gitapex_gate_behind_base.py`'s own `GateBehindBaseArgs`: a `--root`
    pointing nowhere gets a clear, early error instead of the deeper git
    failure it would otherwise surface as an indistinguishable
    `GateError`."""

    root: pathlib.Path
    merge_base: str | None

    @field_validator("root")
    @classmethod
    def _root_must_exist(cls, value: pathlib.Path) -> pathlib.Path:
        if not value.is_dir():
            raise ValueError(f"--root must be an existing directory, got {value}")
        return value


def main(argv: list[str] | None = None) -> int:
    """CLI: 0 no unwaived removal, 1 an unwaived removal was found, 2 the
    check could not be trusted."""
    parser = argparse.ArgumentParser(
        description=(
            "Fail when a PR removes a .betterleaks.toml [allowlist].paths entry present "
            "at its base commit without a waiver comment (issue #1427)."
        )
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Git working tree to check (defaults to this checkout).",
    )
    parser.add_argument(
        "--merge-base",
        default=None,
        help=(
            "Pre-resolved base commit SHA (ci plane: the calling workflow already has full "
            "history and both endpoint SHAs). Omit for the local plane, which fetches "
            "origin/main and resolves the merge-base with HEAD itself."
        ),
    )
    args = parser.parse_args(argv)

    try:
        validated = GateBetterleaksAllowlistNoRemovalArgs(root=args.root, merge_base=args.merge_base)
    except ValidationError:
        print(f"{args.root}: --root must be an existing directory", file=sys.stderr)
        return 2

    try:
        removed = check(validated.root, merge_base=validated.merge_base)
    except GateError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if removed:
        print(
            "FAIL: .betterleaks.toml [allowlist].paths removed the following entries without a waiver (issue #1427):",
            file=sys.stderr,
        )
        for entry in removed:
            print(f"  - {entry}", file=sys.stderr)
        print(
            "Add the entry back -- a renamed fixture needs BOTH names, never a replace, per "
            ".betterleaks.toml's own [allowlist].description -- or, for a genuine permanent "
            "removal, add a `# betterleaks-allowlist-no-removal: WAIVED: <reason>` comment to "
            ".betterleaks.toml that quotes the removed entry's '''<entry>''' TOML array literal "
            "verbatim inside <reason>.",
            file=sys.stderr,
        )
        return 1

    print("OK: no .betterleaks.toml [allowlist].paths entries were removed without a waiver.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
