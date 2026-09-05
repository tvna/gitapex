#!/usr/bin/env python3
"""Compute `skill-audit-gate.yml`'s applicability flags from a git diff.

Issue #874. This is the *single* implementation of that gate's
applicability computation. It used to live as ~150 lines of bash embedded
in `.github/workflows/skill-audit-gate.yml`'s own `run:` block, which made
it reachable only from CI: the local pre-push mirror
(`hooks/gitapex_check_skill_audit_disclosure_or_waiver.py`) said so in its
own docstring ("CI covers them") and deliberately checked only the base
two-audit disclosure. The practical consequence, re-raised as unresolved
across 14 merge-retrospective cycles (#856, #855, #853, #841, #837, #810,
#802, #789, #759, #735, #733, #723, #622, #616), is that an agent learned
it owed a `deterministic-gate-quality` or `eval-coverage-disclosure` line
only after CI failed on an already-open PR.

The fix is extraction, not a second copy. Re-implementing the same flags
in a local script is what every one of those retrospectives explicitly
warned against ("reuse the CI computation; do not re-implement it as a
parallel, independently-drifting copy"), so the workflow step now calls
this module and so does
`gitapex_gate_skill_audit_disclosure.py --check-diff`. There is exactly one
place where a flag rule can change.

**No behavioural change is intended relative to the bash it replaces.**
Every rule below is a direct port, including the parts that look
inconsistent and are not:

- The SKILL.md, design-doc, and checker-script signals exclude `D` and
  `R100` statuses -- a deleted or byte-identically-renamed file has no new
  content to audit. The gate signal deliberately does *not* exclude them:
  removing a gate is the highest-blast-radius change that can be made to
  one, and a `git rm` of a gate script was verified live to report
  `applicable=false` before that was fixed.
- The checker-script pathspecs carry `:(glob)` so `*` cannot cross `/`
  (git's *default* pathspec `*` does cross it); the design-doc pathspec
  deliberately does not, so a nested `docs/superpowers/specs/<dir>/<f>.md`
  reaches the single-level shape check and hard-fails loudly instead of
  silently leaving scope.
- Three-dot (merge-base) diffs throughout, never two-dot: a change merged
  to the base branch after this PR forked must not be misattributed to it.
- Shape validation before any comma-join is load-bearing, not decoration.
  A PR author fully controls these filenames and both sinks
  (`$GITHUB_OUTPUT` and the gate script's comma-split) are
  comma-delimited, so a filename carrying a literal comma would otherwise
  split into two bogus entries downstream.

Fail-closed, never a silent empty result (`skills/`
`evaluating-deterministic-gate-quality/references/dimensions.md`
dimension 15): every git failure, unparseable `--name-status` line,
unsupported filename shape, and untrustworthy gate registry raises
`FlagComputationError`, which the CLI reports on stderr and exits 1 for.
Nothing is written to stdout unless the whole computation succeeded, so a
caller redirecting stdout into `$GITHUB_OUTPUT` can never persist a
partially-computed flag set.

Reuses, rather than re-deriving, the three helper scripts the bash shelled
out to: `gitapex_detect_changed_gate_scripts` (gate membership),
`gitapex_skill_description_diff` (parsed-description comparison) and
`gitapex_skill_security_relevance` (frontmatter keyword heuristic). Their
*parsing* logic is imported; only the `git show` that feeds it is done
here, so every git invocation is anchored to an explicit `repo_root`
instead of the ambient process directory the bash relied on.

This module's own code is standard library only, but issue #1040 gave
one of the three helper scripts it imports
(`gitapex_detect_changed_gate_scripts`) a real `pydantic` import for its
own CLI-arg validation -- so a dependency install is now required
transitively. `skill-audit-gate.yml`'s own invocation already runs this
module under `uv run`, so that path is unaffected; a bare `python3`
invocation (see Usage below) now requires pydantic on the ambient
interpreter.

Issue #998 (refs #982, #997): adds `changed_checker_or_gate_scripts`, the
sorted union of `changed_checker_scripts` and `changed_gate_scripts`. No
new detection logic -- both source signals already exist and are
independently tested; this only unions two already-trustworthy sets, for
`gitapex_gate_skill_audit_disclosure.py`'s new `defeat-test-disclosure`
check, which the issue's own title scopes to "checker **or** gate script"
and therefore needs a scope neither existing signal alone covers (a
`hooks/check-*.sh` gate matches `changed_gate_scripts` but no
checker-script glob; see `2026-08-10-defeat-test-disclosure-design.md`).

Issue #1796: adds two more skill-name signals, both consumed by
`gitapex_gate_skill_audit_disclosure.py`'s new
`drafting-a-skill-invocation-disclosure` check --

- `changed_reference_skills`: skill names whose own `skills/<name>/references/**`
  was added or modified in this diff. Widens this gate's own scope to match
  `drafting-a-skill`'s own delegation trigger, which issue #1796 also widened
  to `references/**` (a behavior-shaping references edit used to fall
  through both triggers entirely -- see the branch plan's row 2).
- `changed_skill_md_skills`: every skill whose own `SKILL.md` was added or
  modified in this diff -- unconditionally, unlike `description_changed_skills`
  (narrower: only a frontmatter `description:` edit) or
  `security_relevant_skills` (narrower still: only a keyword match). Exists
  because `drafting-a-skill-invocation-disclosure` must fire for *either*
  signal (a SKILL.md touch or a references touch) and grades a real
  skill-name list either way, following the same collector pattern
  `_collect_paths` already uses for design docs and checker scripts rather
  than boolean `skill_md_changed` alone -- see that check's own registry-row
  comment for why one row needs two independent list sources.

Usage::

    uv run --frozen python3 gitapex_compute_skill_audit_flags.py \\
        --base-ref BASE --head-ref HEAD --format github-output >> "$GITHUB_OUTPUT"

Exit codes: 0 flags computed, 1 the flags could not be trusted.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import re
import subprocess
import sys
import unicodedata

import gitapex_detect_changed_gate_scripts as detect_gates
import gitapex_skill_description_diff as description_diff
import gitapex_skill_security_relevance as security_relevance

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# The `$GITHUB_OUTPUT` key order, and the authoritative answer to "which
# keys does the diff step publish". The bash wrote this list twice -- once
# on the early-exit path and once on the applicable path -- and a key
# present on only one of them left the check step reading an empty string
# on the other, a silent skip rather than an error. One serializer
# (`SkillAuditFlags.as_output_pairs`) now makes that divergence
# unrepresentable; `tests/test_gitapex_skill_audit_gate_workflow_wiring.py`
# pins the correspondence between these keys and the grader's own CLI
# flags.
OUTPUT_KEYS = (
    "applicable",
    "description-changed-skills",
    "needs-eval-coverage-skills",
    "security-relevant-skills",
    "changed-design-docs",
    "changed-checker-scripts",
    "changed-gate-scripts",
    "changed-checker-or-gate-scripts",
    "changed-reference-skills",
    "changed-skill-md-skills",
    "skill-md-changed",
)

# Shape patterns, always applied with `re.fullmatch`. The bash used
# `grep -E '^...$'`; `$` in Python also matches immediately before a
# trailing newline, and `[^/]`/`.` match `\n`, so an anchored `re.search`
# would accept a newline-bearing path into the single-line
# `$GITHUB_OUTPUT` sink. `gitapex_detect_changed_gate_scripts.py`
# documents the same pitfall and resolves it the same way.
_DESIGN_DOC_SHAPE_RE = re.compile(r"docs/(?:superpowers|gitapex)/specs/[A-Za-z0-9._-]+\.md")
_CHECKER_SCRIPT_SHAPE_RE = re.compile(
    r"skills/[A-Za-z0-9_-]+/scripts/[A-Za-z0-9._-]+\.py"
    r"|evals/scripts/[A-Za-z0-9._-]+\.py"
    r"|\.github/scripts/[A-Za-z0-9._-]+\.py"
)
_SKILL_MD_PATH_RE = re.compile(r"skills/([^/]+)/SKILL\.md")
_SKILL_NAME_RE = re.compile(r"[A-Za-z0-9_-]+")
# Issue #1796: unlike the design-doc/checker-script shapes above, a
# reference file's own depth under `references/` is unconstrained (a skill
# may nest its references in subdirectories), so this shape deliberately
# does not enforce single-level-only the way `_DESIGN_DOC_SHAPE_RE` does --
# there is no "unsupported shape" case here to hard-fail loudly on, only
# the skill-directory-name validation `_skill_name` already applies to
# every other signal's captured group.
_REFERENCE_PATH_RE = re.compile(r"skills/([^/]+)/references/.+")

_SKILL_MD_PATHSPECS = ("skills/*/SKILL.md",)
# No `:(glob)`, deliberately -- see this module's docstring.
_DESIGN_DOC_PATHSPECS = ("docs/superpowers/specs/*.md", "docs/gitapex/specs/*.md")
_CHECKER_SCRIPT_PATHSPECS = (
    ":(glob)skills/*/scripts/*.py",
    ":(glob)evals/scripts/*.py",
    ":(glob).github/scripts/*.py",
)
# No `:(glob)`, deliberately, same reason as the design-doc pathspec above:
# a plain `*` crosses `/` in git's default pathspec syntax, which is exactly
# what lets one entry reach `references/` content at any depth (confirmed
# live: `git diff --name-status -- "skills/*/references/*"` matches a
# `skills/foo/references/sub/deep.md` two levels down).
_REFERENCE_PATHSPECS = ("skills/*/references/*",)

_EXCLUDED_STATUS_RE = re.compile(r"(D|R100)\s")


class FlagComputationError(Exception):
    """The flag set could not be trusted -- exit 1, never a silent pass."""


@dataclasses.dataclass(frozen=True)
class SkillAuditFlags:
    """The applicability facts `gitapex_gate_skill_audit_disclosure.py` grades a
    PR body against. Ordering inside each tuple is the order the bash
    produced it in (diff order for the collected path lists, sorted for the
    gate list, which the detector sorts); the grader sorts and dedupes
    every list it receives, so ordering is presentational only."""

    applicable: bool
    skill_md_changed: bool = False
    description_changed_skills: tuple[str, ...] = ()
    needs_eval_coverage_skills: tuple[str, ...] = ()
    security_relevant_skills: tuple[str, ...] = ()
    changed_design_docs: tuple[str, ...] = ()
    changed_checker_scripts: tuple[str, ...] = ()
    changed_gate_scripts: tuple[str, ...] = ()
    changed_checker_or_gate_scripts: tuple[str, ...] = ()
    changed_reference_skills: tuple[str, ...] = ()
    changed_skill_md_skills: tuple[str, ...] = ()

    def as_output_pairs(self) -> list[tuple[str, str]]:
        """The `$GITHUB_OUTPUT` key/value pairs, in `OUTPUT_KEYS` order."""
        return [
            ("applicable", _bool_text(self.applicable)),
            ("description-changed-skills", ",".join(self.description_changed_skills)),
            ("needs-eval-coverage-skills", ",".join(self.needs_eval_coverage_skills)),
            ("security-relevant-skills", ",".join(self.security_relevant_skills)),
            ("changed-design-docs", ",".join(self.changed_design_docs)),
            ("changed-checker-scripts", ",".join(self.changed_checker_scripts)),
            ("changed-gate-scripts", ",".join(self.changed_gate_scripts)),
            ("changed-checker-or-gate-scripts", ",".join(self.changed_checker_or_gate_scripts)),
            ("changed-reference-skills", ",".join(self.changed_reference_skills)),
            ("changed-skill-md-skills", ",".join(self.changed_skill_md_skills)),
            ("skill-md-changed", _bool_text(self.skill_md_changed)),
        ]


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


class _GitObjectMissing(FlagComputationError):
    """`git` exited non-zero because the object does not exist at that rev.

    A subclass, not a sibling: an uncaught one still fails the computation
    closed. It exists only so `_git_show` can absorb *this* specific
    failure (a newly added file has no content at the merge base) without
    also absorbing a decode failure, which must never degrade to "the file
    is absent".
    """


def _decode_git_output(raw: bytes, args: tuple[str, ...]) -> str:
    """Decode git output as strict UTF-8, or fail the whole computation.

    Deliberately strict, and this is load-bearing rather than a style
    choice. An earlier revision passed `errors="replace"`, which was a
    silent fail-open regression against the bash this module replaces: a
    SKILL.md carrying non-UTF-8 bytes made
    `gitapex_skill_security_relevance.py` exit 1 inside a `pipefail`
    pipeline, so the whole step exited 1 -- reproduced live against
    `origin/main`'s own step. Under `errors="replace"` every invalid byte
    collapses to U+FFFD instead, so two genuinely different descriptions
    can compare equal and `description-changed-skills` comes back empty:
    the eval-coverage and battle-testing-WAIVED-rejection extensions then
    never fire, on exactly the malformed input dimension 15 says must fail
    closed.
    """
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FlagComputationError(f"git {' '.join(args)} produced output that is not valid UTF-8: {error}") from error


def _run_git(repo_root: pathlib.Path, *args: str) -> str:
    """Run `git` in `repo_root` and return stdout, raising on any failure.

    `git` is intentionally resolved from PATH rather than pinned to an
    absolute path -- the same three environments
    `gitapex_skill_description_diff.py` names (GitHub runner, the nix
    devShell, a contributor's machine) install it in three places.

    Captured as bytes and decoded explicitly, rather than via
    `text=True`, so the decode failure is a distinct, reportable outcome
    instead of something the subprocess layer silently papers over.
    """
    try:
        # S603/S607 waived: a fixed argv list with no shell.
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(repo_root), *args],  # noqa: S607
            capture_output=True,
        )
    except OSError as error:
        raise FlagComputationError(f"git {' '.join(args)} could not be run: {error}") from error
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise _GitObjectMissing(f"git {' '.join(args)} failed: {stderr}")
    return _decode_git_output(result.stdout, args)


def _git_show(repo_root: pathlib.Path, rev: str, path: str) -> str | None:
    """File content at `rev`, or None when it does not exist there.

    None is a legitimate answer, not an error: a newly added SKILL.md has
    no content at the merge base, and `description_changed` fails closed on
    it (treating an unreadable description as *changed*, never unchanged).

    Only `_GitObjectMissing` is absorbed. A file that exists but does not
    decode raises through -- see `_decode_git_output`.
    """
    try:
        return _run_git(repo_root, "show", f"{rev}:{path}")
    except _GitObjectMissing:
        return None


def _diff_name_status(repo_root: pathlib.Path, base_ref: str, head_ref: str, pathspecs: tuple[str, ...]) -> str:
    return _run_git(repo_root, "diff", "--name-status", f"{base_ref}...{head_ref}", "--", *pathspecs)


def _added_or_modified(name_status_text: str) -> list[str]:
    """Drop `D` and `R100` lines -- deleted or byte-identically-renamed
    files have no new content to audit. Applies to every signal except the
    gate one; see this module's docstring."""
    return [
        line
        for line in name_status_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip() and not _EXCLUDED_STATUS_RE.match(line)
    ]


def _parse_name_status_line(line: str) -> tuple[str, str, str]:
    """Return `(status, old_path, new_path)` for one `--name-status` line."""
    fields = line.split("\t")
    if len(fields) < 2 or not fields[0].strip():
        raise FlagComputationError(f"unparseable --name-status line: {line!r}")
    status = fields[0].strip()
    old_path = fields[1].strip()
    if status.startswith("R"):
        if len(fields) < 3 or not fields[2].strip():
            raise FlagComputationError(f"rename line carries no destination path: {line!r}")
        return status, old_path, fields[2].strip()
    return status, old_path, old_path


def _collect_paths(
    repo_root: pathlib.Path,
    base_ref: str,
    head_ref: str,
    label: str,
    shape_re: re.Pattern[str],
    pathspecs: tuple[str, ...],
) -> tuple[list[str], list[str]]:
    """Return `(raw added/modified lines, validated new paths)` for one signal.

    One collector for the design-doc and checker-script signals, as in the
    bash: issue #673's review found that block hand-copied a third time,
    with the copies' shape regexes already drifted apart over an
    overlapping path set.
    """
    lines = _added_or_modified(_diff_name_status(repo_root, base_ref, head_ref, pathspecs))
    if lines:
        print(f"Added/modified {label} requiring disclosure:", file=sys.stderr)
        for line in lines:
            print(f"  {line}", file=sys.stderr)
    paths = []
    for line in lines:
        _, _, new_path = _parse_name_status_line(line)
        if not shape_re.fullmatch(new_path):
            raise FlagComputationError(f"unsupported {label} filename for signal computation: {new_path}")
        paths.append(new_path)
    return lines, paths


def _collect_gate_scripts(repo_root: pathlib.Path, base_ref: str, head_ref: str) -> list[str]:
    """Gate paths touched by the whole diff, deletions and renames included.

    The diff is unscoped because gate membership spans `.github/scripts/`,
    `hooks/`, `.github/workflows/` and `.gitapex/ssot.json`; the detector
    owns the membership rule, so it stays in one place rather than becoming
    a pathspec list here that must be kept in sync with a registry.
    """
    text = _run_git(repo_root, "diff", "--name-status", f"{base_ref}...{head_ref}")
    try:
        registered = detect_gates.registered_gate_paths(repo_root)
        return detect_gates.select(text, registered)
    except detect_gates.ScopeError as error:
        raise FlagComputationError(
            f"gate-path detection failed; refusing to report this check green on a scope that could not be computed: {error}"
        ) from error


def _skill_name(new_path: str, path_re: re.Pattern[str] = _SKILL_MD_PATH_RE) -> str:
    """The `skills/<name>/...` directory name, validated.

    A PR author fully controls this directory name in their own diff and it
    reaches both `$GITHUB_OUTPUT` and a comma-split downstream, so an
    unexpected shape is a hard error rather than a trusted passthrough.

    `path_re` defaults to the `SKILL.md` shape (every existing caller's own
    use); issue #1796 passes `_REFERENCE_PATH_RE` instead for a
    `references/**` path, since both shapes capture the skill name as the
    same first group and both need the same `_SKILL_NAME_RE` validation --
    one function, not a second near-duplicate.
    """
    match = path_re.fullmatch(new_path)
    skill = match.group(1) if match else new_path
    if not _SKILL_NAME_RE.fullmatch(skill):
        raise FlagComputationError(f"unsupported skill directory name for signal computation: {new_path}")
    return skill


def _has_eval_coverage(skill: str, all_changed: list[str]) -> bool:
    """True if this diff touches the skill's own `evals/<skill>/tasks/` or
    `evals/<skill>/eval-status.md` (issue #499 moved the latter here from a
    single central `docs/skill-eval-status.md`)."""
    prefix = f"evals/{skill}/tasks/"
    status_file = f"evals/{skill}/eval-status.md"
    return any(path.startswith(prefix) or path == status_file for path in all_changed)


def _skill_signals(
    repo_root: pathlib.Path,
    base_ref: str,
    head_ref: str,
    skill_md_lines: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Return `(description-changed, needs-eval-coverage, security-relevant)`
    skill names for the changed SKILL.md files.

    The description comparison is anchored to the merge base rather than
    `base_ref`'s own tip, matching the three-dot diffs above: a description
    change merged to the base branch after this PR forked must not be
    misattributed to this PR either.
    """
    if not skill_md_lines:
        return [], [], []
    merge_base = _run_git(repo_root, "merge-base", base_ref, head_ref).strip()
    all_changed = _run_git(repo_root, "diff", "--name-only", f"{base_ref}...{head_ref}").splitlines()

    description_changed: list[str] = []
    needs_eval_coverage: list[str] = []
    security_relevant: list[str] = []
    for line in skill_md_lines:
        _, old_path, new_path = _parse_name_status_line(line)
        skill = _skill_name(new_path)

        head_text = _git_show(repo_root, head_ref, new_path)
        if head_text is None:
            raise FlagComputationError(f"could not read {new_path} at {head_ref} for security-relevance scoring")
        if security_relevance.is_security_relevant(head_text):
            security_relevant.append(skill)

        base_text = _git_show(repo_root, merge_base, old_path)
        if description_diff.description_changed(base_text, head_text):
            description_changed.append(skill)
            if not _has_eval_coverage(skill, all_changed):
                needs_eval_coverage.append(skill)
    return description_changed, needs_eval_coverage, security_relevant


def _is_blank(value: str) -> bool:
    """True iff every character in `value` is ordinary whitespace or a
    Unicode Format-category (Cf) mark -- invisible either way. Cf covers
    U+200B ZERO WIDTH SPACE, U+FEFF ZERO WIDTH NO-BREAK SPACE, and U+180E
    MONGOLIAN VOWEL SEPARATOR, none of which str.strip() removes. A
    Cf-only `--base-ref`/`--head-ref` used to pass this function's own
    blank check and fail downstream instead, as a raw `git` error rather
    than this function's own self-describing one -- reproduced live
    (issue #1094): a ZWSP-only ref reached `git diff ...` and failed with
    ``fatal: bad revision '\u200b...HEAD'`` instead of the clean
    ``FlagComputationError`` below."""
    return all(char.isspace() or unicodedata.category(char) == "Cf" for char in value)


def compute_flags(
    base_ref: str,
    head_ref: str,
    repo_root: pathlib.Path = REPO_ROOT,
) -> SkillAuditFlags:
    """Compute `skill-audit-gate.yml`'s applicability flags for one diff.

    Raises `FlagComputationError` for anything that would otherwise make
    the answer a guess.

    The blank-ref check lives here, not only in `main()`, because the ref
    pair reaches this function from two callers and only one of them is
    that CLI. `gitapex_gate_skill_audit_disclosure.py --check-diff` calls
    straight in, so a CLI-only guard left `--check-diff "" HEAD` resolving
    to `git diff "...HEAD"` -- which git reads as `HEAD...HEAD`, an empty
    diff -- and the wrapper printed "this diff triggers no skill-audit
    disclosure requirement" and exited 0 for a diff that in fact owed two
    disclosures. Reproduced live before this guard existed. That path is
    reachable from the hook's own suggested command whenever the base
    variable is unset but quoted, so it is a fail-open in the mode built
    to close one.
    """
    blank = [name for name, value in (("--base-ref", base_ref), ("--head-ref", head_ref)) if _is_blank(value)]
    if blank:
        raise FlagComputationError(
            "blank " + " and ".join(blank) + "; refusing to compute a flag set from an unresolved ref"
        )
    skill_md_lines = _added_or_modified(
        _diff_name_status(repo_root, base_ref, head_ref, _SKILL_MD_PATHSPECS),
    )
    design_doc_lines, design_docs = _collect_paths(
        repo_root, base_ref, head_ref, "design doc", _DESIGN_DOC_SHAPE_RE, _DESIGN_DOC_PATHSPECS
    )
    checker_lines, checker_scripts = _collect_paths(
        repo_root, base_ref, head_ref, "checker script", _CHECKER_SCRIPT_SHAPE_RE, _CHECKER_SCRIPT_PATHSPECS
    )
    # Tested as an independent term, not folded into the checker-script one
    # it overlaps with today: narrowing the checker-script globs later must
    # never silently disable the gate check by making the whole computation
    # report `applicable=false`. It is also the only term here that can be
    # non-empty for a pure deletion.
    gate_scripts = _collect_gate_scripts(repo_root, base_ref, head_ref)
    # Issue #1796: independent of skill_md_lines below for the same reason
    # gate_scripts is independent of checker_lines above -- a
    # references-only change with no SKILL.md touched must still make this
    # diff applicable, not silently skip the whole gate.
    reference_lines, reference_paths = _collect_paths(
        repo_root, base_ref, head_ref, "reference file", _REFERENCE_PATH_RE, _REFERENCE_PATHSPECS
    )

    if not (skill_md_lines or design_doc_lines or checker_lines or gate_scripts or reference_lines):
        print(
            "No added/modified skills/*/SKILL.md, skills/*/references/**, "
            "docs/superpowers/specs/*.md or docs/gitapex/specs/*.md, or "
            "deterministic checker script, and no changed deterministic "
            "gate, in this diff; skipping disclosure check.",
            file=sys.stderr,
        )
        return SkillAuditFlags(applicable=False)

    if skill_md_lines:
        print("Added/modified SKILL.md files requiring disclosure:", file=sys.stderr)
        for line in skill_md_lines:
            print(f"  {line}", file=sys.stderr)
    description_changed, needs_eval_coverage, security_relevant = _skill_signals(
        repo_root, base_ref, head_ref, skill_md_lines
    )
    # Every SKILL.md-changed skill, unconditionally -- unlike
    # description_changed above (narrower: only a frontmatter description
    # edit). Re-derives the skill name from the same already-validated
    # skill_md_lines rather than threading a fourth return value through
    # _skill_signals, which stays scoped to the three signals its own git
    # reads (merge-base description diff, security-relevance) compute.
    changed_skill_md_skills = tuple(
        dict.fromkeys(_skill_name(_parse_name_status_line(line)[2]) for line in skill_md_lines)
    )
    changed_reference_skills = tuple(dict.fromkeys(_skill_name(path, _REFERENCE_PATH_RE) for path in reference_paths))
    return SkillAuditFlags(
        applicable=True,
        skill_md_changed=bool(skill_md_lines),
        description_changed_skills=tuple(description_changed),
        needs_eval_coverage_skills=tuple(needs_eval_coverage),
        security_relevant_skills=tuple(security_relevant),
        changed_design_docs=tuple(design_docs),
        changed_checker_scripts=tuple(checker_scripts),
        changed_gate_scripts=tuple(gate_scripts),
        changed_checker_or_gate_scripts=tuple(sorted(set(checker_scripts) | set(gate_scripts))),
        changed_reference_skills=changed_reference_skills,
        changed_skill_md_skills=changed_skill_md_skills,
    )


def _render(flags: SkillAuditFlags, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(dict(flags.as_output_pairs()), indent=2, sort_keys=False)
    return "\n".join(f"{key}={value}" for key, value in flags.as_output_pairs())


def main(argv: list[str] | None = None) -> int:
    """CLI: print the computed flags on stdout, diagnostics on stderr."""
    parser = argparse.ArgumentParser(
        description="Compute skill-audit-gate.yml's applicability flags for a "
        "three-dot diff between two refs. Prints `key=value` lines suitable "
        "for appending to $GITHUB_OUTPUT."
    )
    parser.add_argument("--base-ref", required=True, help="The PR's base commit-ish.")
    parser.add_argument("--head-ref", required=True, help="The PR's head commit-ish.")
    parser.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="Repository root holding .gitapex/ssot.json (defaults to this checkout).",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("github-output", "json"),
        default="github-output",
        help="Output encoding (default: github-output).",
    )
    args = parser.parse_args(argv)

    if not args.repo_root.is_dir():
        print(f"{args.repo_root}: --repo-root must be an existing directory", file=sys.stderr)
        return 1

    # Blank refs are rejected by `compute_flags` itself, so every caller
    # gets the guard rather than only this one; see its docstring.
    try:
        flags = compute_flags(args.base_ref, args.head_ref, args.repo_root)
    except FlagComputationError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1

    # Written only once the whole computation succeeded, so a caller
    # redirecting stdout into $GITHUB_OUTPUT can never persist a
    # partially-computed flag set.
    print(_render(flags, args.output_format))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
