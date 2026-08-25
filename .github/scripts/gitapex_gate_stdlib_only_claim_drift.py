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
import ast
import pathlib
import re
import sys
from dataclasses import dataclass

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

_TARGET_DIR_RE = re.compile(r"^(?:\.github/scripts/|evals/scripts/)([^/]+)\.py$")

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

# `git diff` always emits at least one `diff --git ` line per file, even
# for a single-file diff -- so a non-empty input with no LINE starting with
# one of these markers is not a unified diff at all (garbage input, a
# truncated pipe, a caller pointing `--diff` at the wrong file). Code
# review correctly found that silently returning "nothing found" for such
# input contradicted this module's own documented exit-2 promise for "a
# malformed diff": unstructured text should never be indistinguishable
# from a genuinely empty, clean diff. Anchored to line-start (matching how
# `parse_diff_added_third_party_imports` itself recognizes these same
# markers), not a bare substring-anywhere search: adversarial review found
# ordinary prose merely mentioning "---" or "@@" mid-sentence (e.g. a PR
# comment "looks fine --- go ahead (cc @@release-bot)") otherwise satisfied
# a substring check without being a diff at all.
_DIFF_STRUCTURE_MARKERS = ("diff --git ", "--- ", "+++ ", "@@")

# Issue #1316: bounds `in_hunk` by a hunk's own declared pre-/post-image
# line counts (mirroring `gitapex_gate_detection_logic_property_coverage.py`'s
# own `_HUNK_RE`/`_reject_if_hunk_incomplete` pattern, issues #1184/#1193's
# precedent), not only by the next `diff --git `/`--- ` line. Both counts
# are tracked, not the post-image count alone, for the identical reason
# that sibling file's own docstring records: a pure-deletion hunk
# (`@@ -a,b +c,0 @@`, real `git diff -U0` output) would otherwise read
# `new_remaining` as already exhausted on the `@@` line itself, before its
# own `b` removal lines are consumed.
_HUNK_RE = re.compile(r"@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")


def _looks_like_a_diff(diff_text: str) -> bool:
    return any(line.startswith(marker) for line in diff_text.split("\n") for marker in _DIFF_STRUCTURE_MARKERS)


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


def _imported_root_modules(content: str) -> list[str]:
    """Return every root module name a single line of `import ...`/
    `from ... import ...` source names, via `ast.parse` -- the same
    approach `gitapex_gate_exception_handler_gaps.py` and
    `gitapex_gate_registry_wiring.py` already use to classify Python
    source structurally rather than re-deriving import-statement grammar
    by hand (reuse finding from adversarial review, issue #1052's own
    PR). A hand-rolled comma/whitespace split was tried first and found,
    by that same review, to mis-tokenize a trailing inline comment
    containing a comma (`import os  # note: os, urllib3 unrelated`), a
    semicolon-chained statement (`import os; import sys`), and a
    backslash line-continuation (`import os, \\`) -- three independent
    false-positive shapes `ast.parse` does not share, since it parses
    real Python grammar rather than approximating it. Content that is
    not valid standalone Python (e.g. a truncated continuation, or
    `import "os";`) raises `SyntaxError`; treated as "no import here",
    the same as a line that never matched the old regexes at all."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    roots: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            roots.extend(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.append(node.module.split(".", 1)[0])
    return roots


def parse_diff_added_third_party_imports(diff_text: str) -> set[str]:
    """Return the set of `.github/scripts/*.py`/`evals/scripts/*.py`
    relative paths whose diff adds a top-level import of a package not in
    the standard library. An empty diff, or a diff touching no such file,
    returns an empty set -- a legitimate "nothing to check" result, not an
    error.

    Issue #1316: this function now mirrors
    `gitapex_gate_detection_logic_property_coverage.py`'s own
    `parse_added_lines` state machine directly (issues #1184/#1193's
    precedent), rather than a partial, independently-reasoned
    reconstruction of it -- an earlier revision of this fix diverged from
    that sibling in three ways, each a confirmed live defect found by a
    dispatched adversarial review before landing:

    1. `current_path` was never cleared on `diff --git `, so a file
       contributing no third-party import of its own could still absorb a
       later, unrelated file's real added import under its own path (a
       false positive).
    2. No `saw_source_header` tracking: a `+++ b/<path>` header with no
       preceding `--- ` was accepted as genuine, letting a hand-fed patch
       misattribute a real added import to an attacker-named path the
       diff's own real headers never legitimately introduced.
    3. An `if not in_hunk: continue` early-exit silently dropped a real
       added import whenever a hunk's own declared post-image count
       under-stated its real body (the mirror-image of issue #1193's
       over-declaration case) -- exactly the kind of silent miss this
       issue exists to close, reintroduced by that early-exit. The sibling
       file processes every `+`/` `/`-` line unconditionally on `path is
       not None`, never gated on `in_hunk`, for this reason.

    `in_hunk` is still bounded by each hunk's own declared pre-/post-image
    line counts (`old_remaining`/`new_remaining`), not only by the next
    `diff --git `/`@@` line, via the same `_reject_if_hunk_incomplete`
    pattern; `ScanError` (exit 2, fail-closed) on an over-declared hunk.
    `diff --git ` and `@@` are unconditional boundaries even `in_hunk`
    (neither literal prefix can appear as real hunk content -- every
    content line always carries its own `+`/`-`/` ` prefix first); `--- `
    is deliberately gated on `not in_hunk` instead, so a *removed* line
    whose own content starts with `-- ` (diff-prefixed to `--- ...`,
    indistinguishable from a real source header) falls through to normal
    `-`-prefixed handling rather than being misread as a header or
    aborting the scan -- an even earlier revision of this fix treated
    `--- ` as an unconditional boundary too, which correctly closed the
    misattribution risk but reintroduced a live false positive: an
    ordinary, correctly-declared diff removing a real source line that
    happens to start with `-- ` (13 such lines exist today under this
    gate's own `.github/scripts/*.py`/`evals/scripts/*.py` scope, e.g.
    `gitapex_scan_ruleset_drift.py`'s own line 6) aborted the whole scan.
    """
    changed: set[str] = set()
    current_path: str | None = None
    in_hunk = False
    old_remaining = 0
    new_remaining = 0
    saw_source_header = False

    def _reject_if_hunk_incomplete(boundary: str) -> None:
        if in_hunk:
            raise ScanError(
                f"hunk header for {current_path!r} declared more pre-/post-image line(s) than "
                f"its body actually had ({old_remaining} pre-image, {new_remaining} post-image "
                f"line(s) still unconsumed) before {boundary}. Real `git diff` output always "
                "emits accurate counts; a hand-fed or foreign patch's inaccurate ones would "
                "otherwise leak this hunk's state into whatever follows it."
            )

    # Normalize CRLF before splitting: without this, a trailing "\r" stays
    # attached to a `+++ b/<path>` header's path (git's own local-plane
    # invocation, or a re-saved `--diff` file, can carry CRLF even though
    # this repo's CI pipes LF-only output), which then fails
    # `_TARGET_DIR_RE`'s `$`-anchored match and silently drops the file --
    # a false negative found by adversarial review (issue #1052's own PR).
    for line in diff_text.replace("\r\n", "\n").split("\n"):
        if line.startswith("diff --git "):
            _reject_if_hunk_incomplete(f"the next `diff --git ` line: {line!r}")
            current_path = None
            in_hunk = False
            saw_source_header = False
            continue
        # `not in_hunk` guard: see this function's own docstring for why
        # `--- ` is deliberately not treated as an unconditional boundary
        # the way `diff --git `/`@@` are.
        if not in_hunk and line.startswith("--- "):
            saw_source_header = True
            continue
        # A real `+++ b/<path>` header only ever appears before the first
        # `@@` of a file (never `in_hunk`). Gating on that -- rather than
        # matching the literal `+++ ` prefix unconditionally -- is load-
        # bearing: an *added* line whose own content starts with `++ `
        # (e.g. a docstring discussing diff/patch anatomy, exactly the kind
        # of prose this repository's own gate scripts already contain) is
        # diff-prefixed to `+++ <that content>` and would otherwise be
        # misread as a second file header mid-hunk, silently dropping every
        # real added line -- including the one this gate exists to catch --
        # for the rest of that hunk. Found by adversarial review (issue
        # #1052's own PR). A `+++ ` with no preceding `--- ` fails closed
        # instead of being accepted as genuine -- a hand-fed patch could
        # otherwise misattribute a real added import to an attacker-named
        # path (found by a dispatched adversarial review, issue #1316).
        if not in_hunk and line.startswith("+++ "):
            if not saw_source_header:
                raise ScanError(
                    f"unified diff post-image header with no `--- ` source header before it: "
                    f"{line!r}. This gate reads default `git diff` output, which always emits "
                    "both; ignoring the header instead would drop every added line that follows "
                    "it from grading."
                )
            path = line[len("+++ ") :]
            if path.startswith("b/"):
                path = path[2:]
            current_path = None if path == "/dev/null" else path
            saw_source_header = False
            continue
        if line.startswith("@@"):
            _reject_if_hunk_incomplete(f"the next hunk header: {line!r}")
            match = _HUNK_RE.match(line)
            if not match:
                raise ScanError(f"unparseable hunk header: {line!r}")
            old_remaining = 1 if match.group(1) is None else int(match.group(1))
            new_remaining = 1 if match.group(2) is None else int(match.group(2))
            in_hunk = old_remaining > 0 or new_remaining > 0
            continue
        # Processed unconditionally on `current_path is not None`, never
        # gated on `in_hunk` -- matches
        # gitapex_gate_detection_logic_property_coverage.py's own
        # `parse_added_lines` exactly. An under-declared hunk (its own
        # counters already at zero while real hunk content continues)
        # must still have its real added imports recorded, not silently
        # dropped (issue #1316's own defeat-test finding).
        if line.startswith("+"):
            content = line[1:]
            # Indented content is never a top-level (module-scope) import.
            if (
                current_path is not None
                and content == content.lstrip()
                and _TARGET_DIR_RE.match(current_path)
                and any(not _is_stdlib(name) for name in _imported_root_modules(content))
            ):
                changed.add(current_path)
            new_remaining -= 1
        elif line.startswith(" "):
            old_remaining -= 1
            new_remaining -= 1
        elif line.startswith("-"):
            old_remaining -= 1
        # `\ No newline at end of file` is a marker, not content, and
        # advances neither counter -- matches
        # gitapex_gate_detection_logic_property_coverage.py's own identical
        # handling (its `parse_added_lines` docstring explains why: a
        # deletion hunk's own removal lines must still be consumed via the
        # pre-image counter, or `in_hunk` would stay true straight through
        # whatever follows).
        if old_remaining <= 0 and new_remaining <= 0:
            in_hunk = False
    _reject_if_hunk_incomplete("the diff ended")
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


def _unindented_uv_run_nearby(text: str, start: int, end: int) -> bool:
    """True iff a "uv run" mention appears within `_PROXIMITY_WINDOW`
    characters of `[start, end)`, counting only *unindented* lines.
    Excluding indented lines is load-bearing, not tidiness: this
    repository's own `Usage::` docstring convention shows an indented `uv
    run --frozen python3 <file>.py` example in nearly every
    `.github/scripts/*.py` file's docstring, regardless of whether that
    file needs a third-party dependency -- so a bare "is there a 'uv run'
    anywhere nearby" check would suppress a genuinely stale, uncorrected
    claim sitting near that routine boilerplate, exactly the flagship PR
    #1044 defect shape this gate exists to catch. A real corrective
    disclosure (e.g. gitapex_compute_skill_audit_flags.py's own post-fix
    text) states the "uv run" mention in ordinary, unindented prose, not
    inside the indented Usage:: example -- found by adversarial review
    (issue #1052's own PR)."""
    window = text[max(0, start - _PROXIMITY_WINDOW) : end + _PROXIMITY_WINDOW]
    unindented = "\n".join(line for line in window.split("\n") if not line[:1].isspace())
    return bool(_UV_RUN_MENTION_RE.search(unindented))


def has_stale_phrase(text: str, *, check_uv_run_proximity: bool) -> bool:
    """True iff a "standard library only"/"stdlib-only" phrase appears
    un-negated (see `_NEGATION_RE`). When `check_uv_run_proximity` is set,
    also suppress a match with an unindented "uv run" mention within
    `_PROXIMITY_WINDOW` characters (see `_unindented_uv_run_nearby`) -- an
    accurate disclosure like "my own code is standard library only, but
    ... uv run" (a real false positive found while measuring this gate
    against `gitapex_compute_skill_audit_flags.py`'s own post-fix
    docstring) legitimately still contains the phrase. Deliberately NOT
    applied to a workflow YAML's own text (the caller passes
    `check_uv_run_proximity=False` there): a correctly-wired workflow's
    `run:` step always contains "uv run" somewhere in the file, so
    proximity-suppressing on that basis would blind this check to a
    genuinely stale, unrelated top-of-file comment merely for being a
    short file -- exactly issue #1049's own real regression shape. The
    negation guard alone is what must catch an already-corrected workflow
    comment (see `test_negated_stale_phrase_is_not_flagged`)."""
    for match in _STALE_PHRASE_RE.finditer(text):
        preceding = text[max(0, match.start() - 30) : match.start()]
        if _NEGATION_RE.search(preceding):
            continue
        if check_uv_run_proximity and _unindented_uv_run_nearby(text, match.start(), match.end()):
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
    an empty list when any file this check needs to read cannot be read,
    or when `diff_text` is non-empty but carries none of `git diff`'s own
    structural markers (not a unified diff at all -- see
    `_DIFF_STRUCTURE_MARKERS`) -- an empty *result* (no file in a
    genuinely empty or genuinely clean diff gained a third-party import)
    is legitimate and distinct from an incomplete or untrustworthy scan."""
    if diff_text.strip() and not _looks_like_a_diff(diff_text):
        raise ScanError(
            f"input does not look like a unified diff (no diff --git/---/+++/@@ line found): {diff_text[:80]!r}"
        )
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
