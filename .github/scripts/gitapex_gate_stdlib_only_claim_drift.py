#!/usr/bin/env python3
"""CI gate: flag a "standard library only"/"stdlib-only" claim, or a bare
`python3 <file>.py` invocation example, left stale after a diff adds a real
top-level third-party import to a `.github/scripts/*.py` or
`evals/scripts/*.py` file.

Issue #1047 (merge retrospective for PR #1044, issue #1040 wave 1) proposed
this gate after PR #1044 needed a follow-up commit to fix stale "standard
library only" claims left inside the 3 pydantic-converted files themselves,
plus a second follow-up fixing the identical stale claim in files that
reference or transitively import them (workflow YAML comments, a caller
script's own docstring). Issue #1049 (merge retrospective for PR #1048, wave
2) re-proposed the same gate, widened, after a manual grep sweep (self-
applying #1047's proposal by hand) caught one stale claim but missed a
second, earlier one in the same file's own top-of-file rationale comment --
caught only by a second, independent adversarial-review pass. Both
retrospectives concluded a manual sweep repeated each wave is not a reliable
substitute for a deterministic gate; this is that gate (issue #1052).

Deliberately a sibling of `gitapex_gate_bare_python3_invocation.py`, not an
extension of it: that gate checks actual invocation safety (is a real call
site bare `python3`); this one checks documentation-claim staleness (does a
doc/comment still assert a property the diff just made false). Two distinct
concerns, matching this repository's own established convention of keeping
one gate per concern (see `gitapex_gate_skill_audit_disclosure.py`'s own
docstring on why `checker-script-adversarial-review` and
`deterministic-gate-quality` stay two separate checks rather than one).

Three text sources are checked for every `.github/scripts/*.py`/
`evals/scripts/*.py` file whose diff adds a top-level import of a package
not in `sys.stdlib_module_names`:

1. That same file's own current content (its docstring/leading comments are
   where such a claim actually lives in this repository's own history, but
   the whole file is scanned rather than trying to delimit "the docstring"
   precisely -- a stale claim anywhere in the file is equally stale).
2. Every other `.github/scripts/*.py`/`evals/scripts/*.py` file that imports
   the changed file directly by module name (a static `import x`/`from x
   import ...` scan -- a dynamic `importlib.import_module()` caller is a
   known, currently-not-live gap, not covered).
3. Every `.github/workflows/*.yml` file that references the changed file's
   own filename anywhere (a `run:` step or a comment) -- checked whole-file,
   not only text adjacent to a `run:` step, since issue #1049's own missed
   instance was in a top-of-file rationale comment, not next to the
   invocation itself.

The staleness check itself is two independent patterns, either one
sufficient to flag: a case-insensitive "standard library only"/"stdlib-only"
phrase, or a bare `python3 <changed file>.py` invocation example not
immediately preceded by `uv run` (the same adjacency shape
`gitapex_gate_bare_python3_invocation.py` already uses to tell "wraps this
invocation" from "merely co-occurs with it"). Deliberately not exhaustive --
a paraphrased claim with neither literal phrase, or a claim reformatted
across multiple lines, can still false-negative; this trades completeness
for a bounded, explainable false-positive rate, the same trade-off this
repository's own provenance-marker hook already makes.

Usage::

    git diff -U0 "$BASE_SHA...$HEAD_SHA" -- '.github/scripts/*.py' 'evals/scripts/*.py' \\
      | uv run --frozen python3 .github/scripts/gitapex_gate_stdlib_only_claim_drift.py

Exit codes: 0 clean (including "no file in this diff gained a third-party
import" -- a legitimate pass, not an error), 1 stale claim(s) found, 2 the
scan could not be trusted (a malformed diff, an unreadable file, or a
`--root` pointing nowhere).
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from dataclasses import dataclass

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

_TARGET_DIR_RE = re.compile(r"^(?:\.github/scripts/|evals/scripts/)([^/]+)\.py$")

# A top-level (column-0) `import x` or `from x import ...`. Matches only the
# first identifier -- a dotted import (`import os.path`) is classified by
# its own leading component, matching Python's own import-resolution unit.
_IMPORT_RE = re.compile(r"^(?:import\s+([A-Za-z_]\w*)|from\s+([A-Za-z_]\w*)\s+import\b)")

# Either literal phrase, case-insensitive, anywhere in the text.
_STALE_PHRASE_RE = re.compile(r"standard library only|stdlib-only|stdlib only", re.IGNORECASE)

# A negation cue immediately before a phrase match (e.g. "... issue #1040
# added a real pydantic import, so it is no longer stdlib-only ...", the
# real corrected text in plugin-root-brace-notation-gate.yml) means the
# match is the accurate, already-corrected statement, not a stale one --
# the substring "stdlib-only" is still present, but negated.
_NEGATION_RE = re.compile(r"(?:no longer|not|isn't|is not|n't)\s*$", re.IGNORECASE)

# How far around a phrase match to look for a "uv run" mention before
# treating the phrase as stale. Wide enough to cover the same docstring
# paragraph (measured live against this repository's own real corrected
# text -- gitapex_compute_skill_audit_flags.py's own "my own code is
# standard library only, but ... uv run" disclosure carries its "uv run"
# mention 291 characters after the phrase, in the same paragraph), narrow
# enough not to cross into an unrelated section of a long docstring.
_PROXIMITY_WINDOW = 400
_UV_RUN_MENTION_RE = re.compile(r"\buv\s+run\b", re.IGNORECASE)


class ScanError(Exception):
    """The scan could not be trusted -- exit 2, never a silent pass."""


@dataclass(frozen=True)
class Finding:
    changed_file: str
    source: str
    location: str

    def describe(self) -> str:
        return f"{self.changed_file}: stale claim found in {self.source} ({self.location})"


def _is_stdlib(module_name: str) -> bool:
    return module_name in sys.stdlib_module_names


def parse_diff_added_third_party_imports(diff_text: str) -> set[str]:
    """Return the set of `.github/scripts/*.py`/`evals/scripts/*.py`
    relative paths whose diff adds a top-level import of a package not in
    the standard library. An empty diff, or a diff touching no such file,
    returns an empty set -- a legitimate "nothing to check" result, not an
    error."""
    changed: set[str] = set()
    current_path: str | None = None
    in_hunk = False
    for line in diff_text.split("\n"):
        if line.startswith("+++ "):
            path = line[len("+++ ") :]
            if path.startswith("b/"):
                path = path[2:]
            current_path = None if path == "/dev/null" else path
            in_hunk = False
            continue
        if line.startswith("diff --git ") or line.startswith("--- "):
            in_hunk = False
            continue
        if line.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk or current_path is None:
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        content = line[1:]
        if content != content.lstrip():
            # Indented -- not a top-level (module-scope) import.
            continue
        if not _TARGET_DIR_RE.match(current_path):
            continue
        match = _IMPORT_RE.match(content)
        if not match:
            continue
        module_name = match.group(1) or match.group(2)
        if module_name and not _is_stdlib(module_name):
            changed.add(current_path)
    return changed


def _bare_invocation_pattern(filename: str) -> re.Pattern[str]:
    escaped = re.escape(filename)
    return re.compile(rf"python3\s+\S*{escaped}\b")


def _uv_wrapped_pattern(filename: str) -> re.Pattern[str]:
    escaped = re.escape(filename)
    return re.compile(rf"\buv\s+run(?:\s+-{{1,2}}[\w-]+(?:=\S+)?)*\s+python3\s+\S*{escaped}\b")


def has_bare_invocation_example(text: str, filename: str) -> bool:
    """True iff `text` shows a `python3 <filename>` invocation not
    immediately preceded by `uv run` on the same line -- the same
    end-position-comparison technique `gitapex_gate_bare_python3_invocation.py`
    uses to prove `uv run` wraps this SPECIFIC invocation, not merely
    co-occurs with it elsewhere on the line."""
    bare_re = _bare_invocation_pattern(filename)
    wrapped_re = _uv_wrapped_pattern(filename)
    for line in text.split("\n"):
        wrapped_ends = {m.end() for m in wrapped_re.finditer(line)}
        for match in bare_re.finditer(line):
            if match.end() not in wrapped_ends:
                return True
    return False


def has_stale_phrase(text: str, *, check_uv_run_proximity: bool) -> bool:
    """True iff a "standard library only"/"stdlib-only" phrase appears
    un-negated (see `_NEGATION_RE`). When `check_uv_run_proximity` is set,
    also suppress a match with a "uv run" mention within
    `_PROXIMITY_WINDOW` characters -- an accurate disclosure like "my own
    code is standard library only, but ... uv run" (a real false positive
    found while measuring this gate against
    `gitapex_compute_skill_audit_flags.py`'s own post-fix docstring)
    legitimately still contains the phrase. Deliberately NOT applied to a
    workflow YAML's own text (the caller passes `check_uv_run_proximity=
    False` there): a correctly-wired workflow's `run:` step always
    contains "uv run" somewhere in the file, so proximity-suppressing on
    that basis would blind this check to a genuinely stale, unrelated
    top-of-file comment merely for being a short file -- exactly issue
    #1049's own real regression shape. The negation guard alone is what
    must catch an already-corrected workflow comment (see
    `test_negated_stale_phrase_is_not_flagged`)."""
    for match in _STALE_PHRASE_RE.finditer(text):
        preceding = text[max(0, match.start() - 30) : match.start()]
        if _NEGATION_RE.search(preceding):
            continue
        if check_uv_run_proximity:
            window = text[max(0, match.start() - _PROXIMITY_WINDOW) : match.end() + _PROXIMITY_WINDOW]
            if _UV_RUN_MENTION_RE.search(window):
                continue
        return True
    return False


def has_stale_claim(text: str, filename: str, *, check_uv_run_proximity: bool = True) -> bool:
    """True iff `text` carries a stale "standard library only"/"stdlib-only"
    phrase, or an unwrapped bare-`python3` invocation example naming
    `filename`. See `has_stale_phrase` for `check_uv_run_proximity`."""
    return has_stale_phrase(text, check_uv_run_proximity=check_uv_run_proximity) or has_bare_invocation_example(
        text, filename
    )


def _read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ScanError(f"{path}: cannot be read as UTF-8 text: {error}") from error


def find_direct_importers(module_stem: str, root: pathlib.Path, exclude: pathlib.Path) -> list[pathlib.Path]:
    """Return every `.github/scripts/*.py`/`evals/scripts/*.py` file (other
    than `exclude`) that imports `module_stem` directly by a static
    `import`/`from ... import` statement."""
    import_re = re.compile(rf"(?m)^(?:import\s+{re.escape(module_stem)}\b|from\s+{re.escape(module_stem)}\s+import\b)")
    importers: list[pathlib.Path] = []
    candidates = sorted((root / ".github" / "scripts").glob("*.py")) + sorted((root / "evals" / "scripts").glob("*.py"))
    for candidate in candidates:
        if candidate.resolve() == exclude.resolve():
            continue
        if import_re.search(_read_text(candidate)):
            importers.append(candidate)
    return importers


def find_referencing_workflows(filename: str, root: pathlib.Path) -> list[pathlib.Path]:
    """Return every `.github/workflows/*.yml`/`*.yaml` file whose content
    mentions `filename` anywhere (a `run:` step or a comment)."""
    workflows_dir = root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return []
    matches: list[pathlib.Path] = []
    for workflow in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
        if filename in _read_text(workflow):
            matches.append(workflow)
    return matches


def find_stale_claims(diff_text: str, root: pathlib.Path) -> list[Finding]:
    """Return every stale-claim finding for files whose diff adds a
    top-level third-party import. Raises `ScanError` rather than returning
    an empty list when any file this check needs to read cannot be read --
    an empty *result* (no file in the diff gained a third-party import) is
    legitimate and distinct from an incomplete scan."""
    findings: list[Finding] = []
    for rel_path in sorted(parse_diff_added_third_party_imports(diff_text)):
        abs_path = root / rel_path
        filename = abs_path.name
        module_stem = abs_path.stem

        own_text = _read_text(abs_path)
        if has_stale_claim(own_text, filename):
            findings.append(Finding(rel_path, "the changed file's own content", str(abs_path)))

        for importer in find_direct_importers(module_stem, root, abs_path):
            if has_stale_claim(_read_text(importer), filename):
                findings.append(Finding(rel_path, "a direct importer", str(importer)))

        for workflow in find_referencing_workflows(filename, root):
            if has_stale_claim(_read_text(workflow), filename, check_uv_run_proximity=False):
                findings.append(Finding(rel_path, "a referencing workflow file", str(workflow)))

    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Flag a stale 'standard library only'/'stdlib-only' claim, or a bare "
        "python3 invocation example, left behind after a diff adds a real third-party "
        "import to a .github/scripts/*.py or evals/scripts/*.py file."
    )
    parser.add_argument(
        "--diff",
        type=pathlib.Path,
        help="Read the unified diff from this file instead of standard input.",
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Repository root the diff's paths resolve against (defaults to this checkout).",
    )
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        print(f"{args.root}: --root must be an existing directory", file=sys.stderr)
        return 2

    if args.diff is not None:
        try:
            diff_text = args.diff.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            print(f"{args.diff}: diff cannot be read as UTF-8 text: {error}", file=sys.stderr)
            return 2
    else:
        try:
            diff_text = sys.stdin.buffer.read().decode("utf-8")
        except UnicodeDecodeError as error:
            print(f"standard input: diff cannot be read as UTF-8 text: {error}", file=sys.stderr)
            return 2

    try:
        findings = find_stale_claims(diff_text, args.root)
    except ScanError as error:
        print(f"{error}", file=sys.stderr)
        return 2

    if findings:
        for finding in findings:
            print(finding.describe(), file=sys.stderr)
        print(
            f"\n{len(findings)} stale stdlib-only/bare-python3 claim(s) found. A file in this "
            "diff gained a real third-party import; update the claim(s) above to say `uv run` "
            "instead (issue #1047, #1049).",
            file=sys.stderr,
        )
        return 1

    print("OK: no stale stdlib-only/bare-python3 claims found for files gaining a third-party import.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
