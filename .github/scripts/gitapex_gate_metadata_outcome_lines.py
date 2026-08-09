#!/usr/bin/env python3
"""Cross-check every ``outcome.lines``-style line-count claim in a skill's
``metadata/gitapex.yaml`` sidecar against the real file it names.

Issue #877 (re-raised unresolved across #856, #855, #841). The sidecar's
``spec.references[].outcome`` mapping is deliberately free-form --
``skills/evaluating-skill-quality/references/skill-metadata.schema.json``
states outright that it carries "free-form key/value atoms ... no closed
vocabulary". Several real entries use that freedom to assert a line-count
delta for the change the entry records (``lines: 499->481``,
``lines: "dimensions.md 287->349, gitapex-worked-examples.md 418->511"``).
Nothing verified those numbers, and the sidecars themselves record the
consequence twice: one correction entry fixes "all 4 line-count
inaccuracies", a later one records that "five of six outcome.lines claims
in this sidecar were measured at the branch's first commit and never
refreshed". This gate is the missing arithmetic check.

**Scope, deliberately narrow** (issue #877's own Constraints section): only
``outcome.lines``-style claims. It imposes no vocabulary on ``outcome``
generally, validates no other claim type, and does not change the schema.

Detection heuristic
-------------------
Because the field is genuinely free-form, "is this a line-count claim" is a
documented heuristic, not a schema rule. A claim is recognized when ALL of:

1. It lives under ``spec.references[].outcome`` at a key matching
   ``LINE_CLAIM_KEY_RE`` -- exactly ``lines``, or a ``<something>_lines``
   suffix (the real corpus's ``worked_examples_lines``). A key without that
   suffix is never read, which is why ``fixtures: "22->26"`` and
   ``dimensions_cited: "12/22 -> 13/23"`` -- real entries counting things
   that are not file lines -- are outside this gate by construction rather
   than by luck.
2. The stringified value carries either an arrow delta (``N->M``,
   ``_ARROW_CLAIM_RE``) or is a bare integer total (``_TOTAL_ONLY_RE``, the
   real ``lines: 484`` shape). Only ``M`` (the "after" count) is ever
   verified: ``N`` describes a state before an unnamed commit, and nothing
   in the sidecar says which one, so asserting anything about it would be
   guesswork. That limit is disclosed, not silently dropped.
3. A target file resolves (see below).

**Target resolution.** Filename-shaped tokens in the value are collected and
kept only when they resolve to a real file inside the owning skill's own
directory (either ``<skill>/<token>`` or ``<skill>/references/<token>``),
which is what makes ``0.75`` and ``origin/main`` non-targets. Each claim
binds to the nearest such token *before* it that no earlier claim in the
same value already consumed -- consumed per token *occurrence*, not per
resolved path, so ``"one.md 1->5, one.md 5->99"`` yields two claims about
``one.md`` rather than one claim and one silent skip (see ``_bind_target``).
That no-earlier-claim condition is load-bearing rather than decorative: the
real branch-final entry ends
``... output-schema.json 271->348, fixtures 29->33``, and a plain
nearest-preceding rule would bind ``29->33`` to ``output-schema.json`` and
report a mismatch against a claim about eval fixtures. A claim that binds
nothing is skipped as unresolved -- except the one documented convention in
this corpus: a bare ``lines`` key whose value names no file at all
(``lines: 499->481``) targets that skill's own ``SKILL.md``. The bare-key
fallback applies only when the value names no resolvable file anywhere,
so a segment without its own filename inside a multi-file value is skipped
rather than silently attributed to ``SKILL.md``.

Traversal is refused, not merely unlikely to resolve: a token containing
``..`` or an absolute path is dropped, and the resolved path must still sit
inside the skill directory (``pathlib``'s ``/`` operator discards the left
operand entirely for an absolute right operand -- the same trap
``skill-metadata.schema.json``'s own ``skillNameRef`` pattern documents).

Which commit the claim is checked against
-----------------------------------------
Issue #877 asks for the comparison to run "against the real file at the
cited commit". In the real corpus almost no claim cites one -- ``anchor``
holds an issue URL, and a bare ``lines: 440->437`` names no revision. So
this gate resolves a revision in a fixed, documented order rather than
assuming a citation is present:

1. **Explicitly anchored.** An ``outcome.commit`` sibling key, or a
   commit-ish hex token (7-40 chars, at least one ``a-f``) inside the claim
   value itself. The count is read with ``git show <rev>:<path>``, i.e. the
   ``git show <sha>:<path> | wc -l`` comparison the issue specifies. A
   citation is recorded at extraction time without consulting git -- see
   ``_explicit_rev`` for why confirming it first is the wrong order, and for
   the false negative that ordering costs.
2. **Unanchored, and the most recent claim for that file.** Read as a claim
   about the file as it stands now, and compared against the checked-out
   working tree. In CI the working tree *is* the commit under test, so this
   is the same comparison; locally it means an author who edits a file and
   refreshes its claim in one uncommitted change is not failed by a stale
   ``HEAD``.
3. **Unanchored and superseded** by a later claim for the same file in the
   same sidecar: skipped. A superseded claim describes a past state no
   revision in the sidecar identifies; checking it against today's file
   would manufacture a failure out of accurate history.

An explicitly historical claim is skipped too: the corpus already disclaims
currency in prose (``at time of this commit``, ``at this commit``), and
``HISTORICAL_MARKERS`` honours that wording instead of overruling it.

Line counting matches ``wc -l`` -- newline characters, not visible lines --
because that is the command the existing claims were measured with. A file
with no trailing newline therefore counts one lower than its last line
number, deliberately.

Fail-closed behaviour
---------------------
``skills/evaluating-deterministic-gate-quality/references/dimensions.md``
dimension 15 (fail-closed default on incomplete or malformed input):

- A sidecar that will not parse, or whose ``spec.references`` / ``outcome``
  is the wrong YAML shape, is a blocking finding -- never a silent pass.
  (``skill-metadata-schema-drift`` also rejects those shapes; this gate does
  not depend on that gate having run first.)
- Zero discovered sidecars is a blocking finding, not a clean exit.
- An anchored claim whose cited commit is not present in this checkout is
  reported as **unverifiable** and does not fail: a shallow clone is the
  documented cause (the audit behind issue #877 hit exactly that against
  ``gitapex_scan_retrospective_gate_drift.py``), and failing on it would
  punish checkout depth rather than a wrong claim. Its CI wiring closes the
  hole from the other side: the pytest step in ``.github/workflows/test.yml``
  already checks out with ``fetch-depth: '0'``, so in CI every cited commit
  in this repository's own history does resolve. An unresolvable revision is
  never quietly downgraded to the working-tree comparison, which would
  compare a historical claim against today's file.
- An anchored claim whose cited commit resolves but does not contain the
  named path IS a blocking finding: the citation, not the checkout, is wrong.
- A ``lines``-shaped key whose value is not a scalar at all (a mapping or a
  list, which ``str()`` would flatten into something no claim regex matches)
  is a blocking finding rather than a silent skip.
- A ``lines``-shaped key in which the heuristic recognizes no claim is
  reported as an unverified note. A false negative that appears nowhere in
  the report cannot be measured, and narrowing this heuristic later depends
  on being able to see them.
- ``git`` that cannot be executed at all raises. So does a ``root`` in which
  ``git rev-parse HEAD`` resolves nothing: without that second probe, "not a
  git repository" and "corrupt object database" would both be indistinguishable
  from the benign shallow-clone note, leaving every anchored claim unverified
  behind a clean exit.

Registered in ``.gitapex/ssot.json`` as ``metadata-outcome-lines-drift``.
Enforced through ``tests/test_gitapex_gate_metadata_outcome_lines.py``'s
real-repository test inside the pytest step of ``.github/workflows/test.yml``
-- the same wiring shape ``skill-metadata-schema-drift`` and
``ssot-schema-drift`` already use, rather than a second redundant workflow
step. Also runnable standalone (exit 0 clean, 1 on a finding).
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"

# Mirrors gitapex_scan_skill_metadata_schema.py's own sidecar path convention.
SIDECAR_GLOB = "*/metadata/gitapex.yaml"

# `lines`, or a `<prefix>_lines` key (the corpus's own worked_examples_lines).
LINE_CLAIM_KEY_RE = re.compile(r"^(?:[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*_)?lines$")

# `499->481`, `440 -> 437`, `364-->418`. The arrow's own tail is `-+>` so a
# doubled dash stays one claim rather than reading as two.
_ARROW_CLAIM_RE = re.compile(r"(?P<before>\d+)\s*-+>\s*(?P<after>\d+)")

# A whole value that is nothing but a count (`lines: 484`).
_TOTAL_ONLY_RE = re.compile(r"^\s*(?P<after>\d+)\s*$")

# A filename-shaped token: at least one dot-separated extension. Slashes are
# allowed so `references/dimensions.md` is one token, not two.
_PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*\.[A-Za-z0-9]+")

# A commit-ish token. Confirmed against git before use -- never trusted on
# shape alone, since an ordinary lowercase word can be all-hex. At least one
# a-f digit is required so a seven-or-more-digit line count (`1234567->89`)
# is not sent to `git rev-parse` as a candidate revision; an all-numeric
# short SHA is the accepted loss, and the alternative is treating every
# large line count in the corpus as a possible commit citation.
#
# Issue #960: that loss was called "theoretical" here until a real commit
# hit it. An 8-character short SHA is all digits (10/16)**8 ~= 2.3% of the
# time, so any test minting a real commit and citing `sha[:8]` verbatim
# fails at that rate -- which is what happened on PR #957, whose diff could
# not reach this file. The tradeoff stands; only the word was wrong. The
# behavior is pinned by
# tests/test_gitapex_gate_metadata_outcome_lines.py::
# test_an_all_numeric_short_sha_is_not_read_as_a_commit_citation, so
# narrowing or widening it now requires changing a failing test on purpose.
_SHA_TOKEN_RE = re.compile(r"\b(?=[0-9a-f]{7,40}\b)[0-9a-f]*[a-f][0-9a-f]*\b")

# Prose the corpus already uses to scope a claim to a past commit rather than
# to the file's current state. Honoured, not overruled.
HISTORICAL_MARKERS = ("at this commit", "at time of this commit")

_SKILL_MD = "SKILL.md"

# The one key with a documented default target in this corpus: a bare
# `lines` claim naming no file is about that skill's own SKILL.md.
_BARE_KEY = "lines"


@dataclass(frozen=True)
class Finding:
    """One blocking defect: a wrong claim, or input this gate refuses to
    grade as clean."""

    location: str
    message: str

    def render(self) -> str:
        return f"{self.location}: {self.message}"


@dataclass(frozen=True)
class Note:
    """One claim this gate deliberately did not verify, with the reason.
    Printed, never blocking -- an unverified claim must be visible rather
    than absent from the report entirely."""

    location: str
    message: str

    def render(self) -> str:
        return f"{self.location}: {self.message}"


@dataclass(frozen=True)
class Claim:
    """One recognized line-count claim, already bound to a target file."""

    location: str
    target: str
    """Repo-root-relative POSIX path of the file the claim is about."""
    after: int
    rev: str | None
    """An explicitly cited commit-ish, or None for an unanchored claim."""
    raw: str


def _git(args: list[str], root: pathlib.Path) -> subprocess.CompletedProcess[str]:
    """Run a git subcommand, capturing output. Raises RuntimeError if git
    itself cannot be executed -- fail loudly rather than let an OSError read
    as a clean scan."""
    try:
        return subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:  # git missing, cwd gone
        raise RuntimeError(f"`git {' '.join(args)}` could not be run in {root}: {exc}") from exc


def resolve_commitish(rev: str, root: pathlib.Path) -> str | None:
    """Return the full SHA `rev` names, or None when this checkout does not
    contain it (a shallow-clone boundary, or a citation that never existed)."""
    result = _git(["rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"], root)
    return result.stdout.strip() or None


def line_count_at_commit(rev: str, path: str, root: pathlib.Path) -> int | None:
    """`wc -l` for `path` as of `rev`, or None when `rev` does not contain
    that path."""
    result = _git(["show", f"{rev}:{path}"], root)
    if result.returncode != 0:
        return None
    return result.stdout.count("\n")


def line_count_in_worktree(path: pathlib.Path) -> int | None:
    """`wc -l` for the checked-out file, or None when it is absent."""
    try:
        return path.read_text(encoding="utf-8").count("\n")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        # Fail loudly: an unreadable target must not read as "claim verified".
        raise RuntimeError(f"could not read {path} to verify a line-count claim: {exc}") from exc


def _resolvable_targets(text: str, skill_dir: pathlib.Path) -> list[tuple[int, str]]:
    """Every filename-shaped token in `text` that names a real file inside
    `skill_dir`, as (token end offset, repo-relative POSIX path) pairs in
    document order."""
    found: list[tuple[int, str]] = []
    for match in _PATH_TOKEN_RE.finditer(text):
        resolved = _resolve_in_skill(match.group(), skill_dir)
        if resolved is not None:
            found.append((match.end(), resolved))
    return found


def _resolve_in_skill(token: str, skill_dir: pathlib.Path) -> str | None:
    """Resolve a filename token against the skill's own directory, refusing
    anything that escapes it."""
    if token.startswith("/") or ".." in pathlib.PurePosixPath(token).parts:
        return None
    for candidate in (skill_dir / token, skill_dir / "references" / token):
        if not candidate.is_file():
            continue
        # Belt and braces against a token that still escapes via a symlink or
        # an absolute path pathlib's `/` would have swallowed.
        if not candidate.resolve().is_relative_to(skill_dir.resolve()):
            continue
        return candidate.resolve().relative_to(skill_dir.parent.parent.resolve()).as_posix()
    return None


def _bind_target(targets: list[tuple[int, str]], claim_start: int, consumed: set[int]) -> tuple[int, str] | None:
    """The nearest target token ending at or before `claim_start` that no
    earlier claim in the same value already took, as (token index, path).

    Consumption is tracked per token *occurrence*, not per resolved path. An
    independent review caught the difference with `"one.md 1->5, one.md 5->99"`:
    keying on the path alone let the first delta consume the file, so the
    second delta -- the current-state one -- bound nothing and was skipped
    unverified instead of being checked. Two occurrences of one filename are
    two separate claims about it, and the supersession pass downstream is what
    decides which of them still describes the file today.
    """
    for index in range(len(targets) - 1, -1, -1):
        end, path = targets[index]
        if end <= claim_start and index not in consumed:
            return index, path
    return None


def _explicit_rev(value_text: str, outcome: dict[str, object]) -> str | None:
    """The commit-ish this claim cites, or None. `outcome.commit` wins over an
    inline token.

    Resolvability is deliberately NOT consulted here. An earlier revision
    accepted a citation only once ``git rev-parse`` confirmed it, which
    silently downgraded an unresolvable citation to the unanchored
    working-tree comparison -- turning a shallow clone into a false mismatch
    against a claim that was accurate at the commit it cites. Extraction now
    records the citation; :func:`_verify` decides what a citation this
    checkout cannot resolve means (an unverifiable note, never a pass and
    never a fabricated failure).

    The cost of that ordering, disclosed rather than hidden: a plain word
    that happens to be seven-or-more hex characters inside a line-count claim
    would be read as a citation and make that claim unverifiable instead of
    checked. No value in this repository's corpus contains such a token
    today, measured -- but it is a false negative, not an impossibility.
    """
    declared = outcome.get("commit")
    if isinstance(declared, str | int):
        return str(declared)
    inline = _SHA_TOKEN_RE.search(value_text)
    return inline.group() if inline else None


def _claims_in_value(
    key: str,
    value: object,
    outcome: dict[str, object],
    skill_dir: pathlib.Path,
    location: str,
) -> tuple[list[Claim], list[Note], list[Finding]]:
    """Recognize every claim in one `outcome.<key>` value."""
    if not isinstance(value, str | int | float | bool):
        # The schema restricts an outcome atom to string/number/boolean, but
        # this gate must not depend on skill-metadata-schema-drift having run
        # first: str() on a mapping or list would silently yield a value no
        # claim regex can match, i.e. a fail-open skip.
        return [], [], [Finding(location, f"outcome.{key} is not a scalar; a line-count claim cannot be read from it")]

    text = str(value)
    if any(marker in text.lower() for marker in HISTORICAL_MARKERS):
        return [], [Note(location, f"outcome.{key} is scoped to a past commit in prose; not verified")], []

    rev = _explicit_rev(text, outcome)
    targets = _resolvable_targets(text, skill_dir)
    total = _TOTAL_ONLY_RE.match(text)
    if total:
        # A bare count carries no filename; only the `lines` key has a
        # documented default target in this corpus.
        if key != _BARE_KEY:
            return [], [Note(location, f"outcome.{key}: bare count {text.strip()} names no file; not verified")], []
        return [Claim(location, _skill_relative(skill_dir, _SKILL_MD), int(total["after"]), rev, text)], [], []

    claims: list[Claim] = []
    notes: list[Note] = []
    consumed: set[int] = set()
    for match in _ARROW_CLAIM_RE.finditer(text):
        bound = _bind_target(targets, match.start(), consumed)
        if bound is not None:
            consumed.add(bound[0])
            target = bound[1]
        elif key == _BARE_KEY and not targets:
            target = _skill_relative(skill_dir, _SKILL_MD)
        else:
            notes.append(
                Note(location, f"outcome.{key}: claim {match.group()!r} binds to no file in this skill; not verified")
            )
            continue
        claims.append(Claim(location, target, int(match["after"]), rev, match.group()))

    if not claims and not notes:
        # A `lines`-shaped key this heuristic recognized nothing in must be
        # visible in the report, not silently absent from it -- the false
        # negatives are the documented cost of a free-form field, and an
        # unreported one cannot be measured or narrowed later.
        notes.append(Note(location, f"outcome.{key}: no line-count claim recognized in {text.strip()!r}"))
    return claims, notes, []


def _skill_relative(skill_dir: pathlib.Path, name: str) -> str:
    return (skill_dir / name).relative_to(skill_dir.parent.parent).as_posix()


def _iter_outcomes(doc: object, sidecar_label: str) -> tuple[list[tuple[int, dict[str, object]]], list[Finding]]:
    """Every `spec.references[].outcome` mapping, with its entry index.
    Wrong shapes are findings, not skips."""
    if not isinstance(doc, dict):
        return [], [Finding(sidecar_label, "sidecar does not parse as a YAML mapping")]
    spec = doc.get("spec")
    if spec is None:
        return [], [Finding(sidecar_label, "sidecar has no spec block")]
    if not isinstance(spec, dict):
        return [], [Finding(sidecar_label, "spec is not a mapping")]
    references = spec.get("references")
    if references is None:
        return [], []
    if not isinstance(references, list):
        return [], [Finding(sidecar_label, "spec.references is not a list")]

    outcomes: list[tuple[int, dict[str, object]]] = []
    findings: list[Finding] = []
    for index, entry in enumerate(references):
        if not isinstance(entry, dict):
            findings.append(Finding(f"{sidecar_label} spec.references[{index}]", "entry is not a mapping"))
            continue
        outcome = entry.get("outcome")
        if outcome is None:
            continue
        if not isinstance(outcome, dict):
            findings.append(Finding(f"{sidecar_label} spec.references[{index}]", "outcome is not a mapping"))
            continue
        outcomes.append((index, outcome))
    return outcomes, findings


def _load_sidecar(sidecar: pathlib.Path, label: str) -> tuple[object, Finding | None]:
    try:
        return yaml.safe_load(sidecar.read_text(encoding="utf-8")), None
    except (OSError, UnicodeDecodeError) as exc:
        return None, Finding(label, f"sidecar could not be read: {exc}")
    except yaml.YAMLError as exc:
        return None, Finding(label, f"sidecar is not valid YAML: {exc}")


def collect_claims(sidecar: pathlib.Path, root: pathlib.Path) -> tuple[list[Claim], list[Note], list[Finding]]:
    """Every recognized claim in one sidecar, in document order."""
    skill_dir = sidecar.parent.parent
    label = sidecar.relative_to(root).as_posix() if sidecar.is_relative_to(root) else str(sidecar)
    doc, read_finding = _load_sidecar(sidecar, label)
    if read_finding is not None:
        return [], [], [read_finding]

    outcomes, findings = _iter_outcomes(doc, label)
    claims: list[Claim] = []
    notes: list[Note] = []
    for index, outcome in outcomes:
        for key, value in outcome.items():
            if not (isinstance(key, str) and LINE_CLAIM_KEY_RE.match(key)):
                continue
            location = f"{label} spec.references[{index}]"
            found, skipped, bad = _claims_in_value(key, value, outcome, skill_dir, location)
            claims.extend(found)
            notes.extend(skipped)
            findings.extend(bad)
    return claims, notes, findings


def _partition_unanchored(claims: list[Claim]) -> tuple[list[Claim], list[Note]]:
    """Keep only the last unanchored claim per target; the rest are superseded
    history that no revision in the sidecar identifies."""
    last_index: dict[str, int] = {}
    for position, claim in enumerate(claims):
        if claim.rev is None:
            last_index[claim.target] = position

    keep: list[Claim] = []
    notes: list[Note] = []
    for position, claim in enumerate(claims):
        if claim.rev is not None or last_index.get(claim.target) == position:
            keep.append(claim)
        else:
            notes.append(
                Note(
                    claim.location,
                    f"claim {claim.raw!r} for {claim.target} is superseded by a later claim; not verified",
                )
            )
    return keep, notes


def _verify(claim: Claim, root: pathlib.Path) -> Finding | Note | None:
    """Compare one claim's "after" count against the real file."""
    if claim.rev is None:
        actual = line_count_in_worktree(root / claim.target)
        if actual is None:
            return Finding(claim.location, f"claim {claim.raw!r} names {claim.target}, which does not exist")
        where = "the checked-out tree"
    else:
        resolved = resolve_commitish(claim.rev, root)
        if resolved is None:
            # `git rev-parse` exiting non-zero means "this rev is not here" only
            # if git can resolve anything at all in `root`. Without this second
            # probe, "not a git repository" and "corrupt object database" both
            # read as a benign shallow-clone note -- every anchored claim in the
            # sidecar silently unverified, with a clean exit.
            if resolve_commitish("HEAD", root) is None:
                raise RuntimeError(
                    f"{root} is not a usable git repository (`git rev-parse HEAD` resolves nothing), "
                    f"so the commit {claim.rev} cited at {claim.location} cannot be checked; "
                    "refusing to report it as merely unverifiable"
                )
            return Note(
                claim.location,
                f"claim {claim.raw!r} cites commit {claim.rev}, absent from this checkout "
                "(shallow clone?); not verified",
            )
        actual = line_count_at_commit(resolved, claim.target, root)
        if actual is None:
            return Finding(
                claim.location,
                f"claim {claim.raw!r} cites commit {claim.rev}, which does not contain {claim.target}",
            )
        where = f"commit {claim.rev}"

    if actual != claim.after:
        return Finding(
            claim.location,
            f"claim {claim.raw!r} asserts {claim.target} is {claim.after} lines; {where} has {actual}",
        )
    return None


def find_drift(
    skills_dir: pathlib.Path | None = None, repo_root: pathlib.Path | None = None
) -> tuple[list[Finding], list[Note]]:
    """Scan every sidecar. Returns (blocking findings, unverified-claim notes)."""
    root = repo_root or REPO_ROOT
    skills = skills_dir or (root / "skills")
    sidecars = sorted(skills.glob(SIDECAR_GLOB))
    if not sidecars:
        # Zero matches is drift in the scan itself, never a clean pass.
        return [Finding(str(skills), f"no sidecars matched {SIDECAR_GLOB}; refusing to report clean")], []

    findings: list[Finding] = []
    notes: list[Note] = []
    for sidecar in sidecars:
        claims, claim_notes, read_findings = collect_claims(sidecar, root)
        findings.extend(read_findings)
        notes.extend(claim_notes)
        checkable, superseded = _partition_unanchored(claims)
        notes.extend(superseded)
        for claim in checkable:
            result = _verify(claim, root)
            if isinstance(result, Finding):
                findings.append(result)
            elif isinstance(result, Note):
                notes.append(result)
    return findings, notes


def format_report(findings: list[Finding], notes: list[Note]) -> str:
    lines = [f"note: {note.render()}" for note in notes]
    if findings:
        lines.append("")
        lines.append(f"{len(findings)} line-count claim finding(s):")
        lines.extend(f"  - {finding.render()}" for finding in findings)
        lines.append("")
        lines.append(
            "Re-measure with `git show <sha>:<path> | wc -l` (or `wc -l <path>` for a "
            "current-state claim) and correct the sidecar, or scope the claim to a past "
            "commit in its own prose."
        )
    else:
        lines.append("No outcome.lines claim drift found.")
    return "\n".join(lines)


def main() -> int:
    try:
        findings, notes = find_drift()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(format_report(findings, notes))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
