"""Tests for .github/scripts/gitapex_gate_metadata_outcome_lines.py (issue #877).

Two planes, deliberately kept separate:

- **Fixture plane.** Synthetic sidecars in a real temporary git repository,
  covering the detection heuristic's positive and negative cases, the
  commit-resolution order, and every fail-closed branch. The mismatched-claim
  case is built as fixture metadata plus fixture git history, which is what
  issue #877's own Acceptance Criteria Map asks for.
- **Real-repository plane.** ``test_real_repository_has_no_outcome_lines_drift``
  runs ``find_drift()`` against this repository's own skills/ tree with no
  fixture override. That test IS this gate's CI enforcement -- pytest is a
  required check (``.github/workflows/test.yml``), and that workflow already
  checks out with ``fetch-depth: '0'`` so a cited commit resolves there.
"""

from __future__ import annotations

import pathlib
import subprocess
import textwrap

import gitapex_gate_metadata_outcome_lines as gate
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _git(root: pathlib.Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(root: pathlib.Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "gitapex test")
    _git(root, "config", "commit.gpgsign", "false")


def _commit(root: pathlib.Path, message: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD")


SHORT_SHA_LEN = 8

# Enough re-rolls that exhausting them is not a thing that happens. A single
# candidate misses with probability (10/16)**8 ~= 0.0233, and the loop below
# evaluates _MAX_SHA_REROLLS + 1 = 21 of them, so giving up needs 21
# consecutive misses: (10/16)**(8*21) ~= 5e-35. Bounded anyway rather than
# `while True`, so a future change that makes the condition unsatisfiable
# fails loudly instead of hanging the suite.
_MAX_SHA_REROLLS = 20


def _is_citable_short_sha(sha: str) -> bool:
    """Whether the gate would read `sha[:SHORT_SHA_LEN]` as a commit citation.

    One predicate, called from both the loop and the post-loop check below, so
    the candidate named in the failure message is necessarily one that was
    actually evaluated by the same rule.
    """
    return bool(gate._SHA_TOKEN_RE.fullmatch(sha[:SHORT_SHA_LEN]))


def _commit_with_citable_short_sha(root: pathlib.Path, message: str) -> str:
    """Commit, re-rolling until `sha[:SHORT_SHA_LEN]` is a token the gate reads
    as a commit citation.

    `gate._SHA_TOKEN_RE` requires at least one a-f digit, deliberately, so that
    a seven-or-more-digit line count (`1234567->89`) is never sent to
    `git rev-parse` as a candidate revision -- see that regex's own comment. An
    all-numeric short SHA is excluded by that rule and is therefore not a
    commit citation as far as this gate is concerned.

    A commit's SHA is effectively random, so a test that embeds `sha[:8]`
    verbatim lands on that excluded shape (10/16)**8 ~= 2.3% of runs and then
    fails on the fixture's own value rather than on any gate behavior. Issue
    #960 records the CI failure that cost, on a pull request whose diff could
    not reach this code at all. Amending re-rolls the SHA (the commit's own
    message changes, the tree does not), so the fixture lands inside the
    documented contract instead of sampling from outside it.
    """
    sha = _commit(root, message)
    for attempt in range(_MAX_SHA_REROLLS):
        if _is_citable_short_sha(sha):
            return sha
        _git(root, "commit", "-q", "--amend", "-m", f"{message} (reroll {attempt})")
        sha = _git(root, "rev-parse", "HEAD")
    # The final amend's own result still has to be evaluated. Without this the
    # loop would amend once more than it checks: the SHA named below would be a
    # candidate no rule ever ran against, and the fixture repository would be
    # left one rewrite past the last evaluated state.
    if _is_citable_short_sha(sha):
        return sha
    raise AssertionError(
        f"no commit in {_MAX_SHA_REROLLS + 1} candidates produced a {SHORT_SHA_LEN}-character short SHA "
        f"matching the gate's own commit-ish token rule; last evaluated was {sha[:SHORT_SHA_LEN]!r}"
    )


def _write_skill(
    root: pathlib.Path,
    name: str,
    *,
    skill_lines: int = 3,
    references: str = "",
    reference_files: dict[str, int] | None = None,
) -> pathlib.Path:
    """Create skills/<name>/ with a SKILL.md of `skill_lines` lines, optional
    references/ files, and a sidecar whose spec.references block is `references`."""
    skill_dir = root / "skills" / name
    (skill_dir / "metadata").mkdir(parents=True, exist_ok=True)
    (skill_dir / _SKILL_MD).write_text("x\n" * skill_lines, encoding="utf-8")
    for filename, count in (reference_files or {}).items():
        target = skill_dir / "references" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("y\n" * count, encoding="utf-8")
    sidecar = skill_dir / "metadata" / "gitapex.yaml"
    body = textwrap.dedent(
        f"""\
        apiVersion: gitapex.io/v1alpha1
        kind: SkillMetadata
        metadata:
          name: {name}
        spec:
          portability: Portable
          capabilityAssumption: Broad
        """
    )
    if references:
        body += "  references:\n" + textwrap.indent(textwrap.dedent(references), "    ")
    sidecar.write_text(body, encoding="utf-8")
    return sidecar


_SKILL_MD = "SKILL.md"


def _entry(summary: str, outcome: str) -> str:
    return textwrap.dedent(
        f"""\
        - kind: decision
          anchor: "https://github.com/tvna/gitapex/issues/877"
          summary: "{summary}"
          outcome:
        """
    ) + textwrap.indent(textwrap.dedent(outcome), "    ")


def _scan(root: pathlib.Path) -> tuple[list[gate.Finding], list[gate.Note]]:
    return gate.find_drift(skills_dir=root / "skills", repo_root=root)


# --------------------------------------------------------------------------
# Detection heuristic: positive cases
# --------------------------------------------------------------------------


def test_bare_lines_claim_matching_skill_md_is_clean(tmp_path: pathlib.Path) -> None:
    _write_skill(tmp_path, "alpha", skill_lines=12, references=_entry("t", "lines: 4->12\n"))
    findings, _ = _scan(tmp_path)
    assert findings == []


def test_bare_lines_claim_mismatching_skill_md_is_a_finding(tmp_path: pathlib.Path) -> None:
    _write_skill(tmp_path, "alpha", skill_lines=12, references=_entry("t", "lines: 4->99\n"))
    findings, _ = _scan(tmp_path)
    assert len(findings) == 1
    assert "asserts skills/alpha/SKILL.md is 99 lines" in findings[0].message
    assert "has 12" in findings[0].message


def test_bare_total_only_claim_is_recognized(tmp_path: pathlib.Path) -> None:
    _write_skill(tmp_path, "alpha", skill_lines=7, references=_entry("t", "lines: 8\n"))
    findings, _ = _scan(tmp_path)
    assert len(findings) == 1
    assert "is 8 lines" in findings[0].message


def test_multi_file_claim_binds_each_pair_to_its_own_file(tmp_path: pathlib.Path) -> None:
    _write_skill(
        tmp_path,
        "alpha",
        skill_lines=20,
        reference_files={"one.md": 5, "two.md": 6},
        references=_entry("t", 'lines: "SKILL.md 1->20, one.md 2->5, two.md 3->77"\n'),
    )
    findings, _ = _scan(tmp_path)
    assert len(findings) == 1
    assert "skills/alpha/references/two.md is 77 lines" in findings[0].message
    assert "has 6" in findings[0].message


def test_the_same_file_named_twice_yields_two_claims(tmp_path: pathlib.Path) -> None:
    """Regression, found by an independent review on PR #882: consumption
    keyed on the resolved path let the first delta take the file, so the
    second -- the current-state one -- bound nothing and was skipped
    unverified. Per-occurrence tracking checks the later delta instead."""
    _write_skill(
        tmp_path,
        "alpha",
        reference_files={"one.md": 5},
        references=_entry("t", 'lines: "one.md 1->5, one.md 5->99"\n'),
    )
    findings, notes = _scan(tmp_path)
    assert [finding.message for finding in findings] == [
        "claim '5->99' asserts skills/alpha/references/one.md is 99 lines; the checked-out tree has 5"
    ]
    assert not [note for note in notes if "binds to no file" in note.message]
    assert any("superseded by a later claim" in note.message for note in notes)


def test_reference_path_with_directory_component_resolves(tmp_path: pathlib.Path) -> None:
    _write_skill(
        tmp_path,
        "alpha",
        reference_files={"one.md": 5},
        references=_entry("t", 'lines: "references/one.md 2->5"\n'),
    )
    findings, notes = _scan(tmp_path)
    assert findings == []
    assert not [note for note in notes if "binds to no file" in note.message]


# --------------------------------------------------------------------------
# Detection heuristic: negative cases (documented false-negative surface)
# --------------------------------------------------------------------------


def test_non_line_key_is_never_read(tmp_path: pathlib.Path) -> None:
    _write_skill(tmp_path, "alpha", skill_lines=3, references=_entry("t", 'fixtures: "22->26"\n'))
    findings, notes = _scan(tmp_path)
    assert findings == []
    assert notes == []


def test_trailing_non_file_pair_does_not_rebind_an_already_bound_file(tmp_path: pathlib.Path) -> None:
    """The real branch-final shape: `... output-schema.json 271->348, fixtures 29->33`.
    A plain nearest-preceding rule would bind 29->33 to output-schema.json."""
    _write_skill(
        tmp_path,
        "alpha",
        reference_files={"one.md": 5},
        references=_entry("t", 'lines: "one.md 2->5, fixtures 29->33"\n'),
    )
    findings, notes = _scan(tmp_path)
    assert findings == []
    assert any("'29->33' binds to no file" in note.message for note in notes)


def test_suffixed_lines_key_without_a_filename_is_not_guessed(tmp_path: pathlib.Path) -> None:
    _write_skill(tmp_path, "alpha", skill_lines=3, references=_entry("t", 'worked_examples_lines: "468->328"\n'))
    findings, notes = _scan(tmp_path)
    assert findings == []
    assert any("'468->328' binds to no file" in note.message for note in notes)


def test_suffixed_lines_key_with_a_bare_total_is_not_guessed(tmp_path: pathlib.Path) -> None:
    _write_skill(tmp_path, "alpha", skill_lines=3, references=_entry("t", "worked_examples_lines: 328\n"))
    findings, notes = _scan(tmp_path)
    assert findings == []
    assert any("bare count 328 names no file" in note.message for note in notes)


def test_bare_key_fallback_does_not_apply_when_the_value_names_files(tmp_path: pathlib.Path) -> None:
    _write_skill(
        tmp_path,
        "alpha",
        skill_lines=3,
        reference_files={"one.md": 5},
        references=_entry("t", 'lines: "one.md 2->5, and separately 10->11"\n'),
    )
    findings, notes = _scan(tmp_path)
    assert findings == []
    assert any("'10->11' binds to no file" in note.message for note in notes)


def test_historically_scoped_claim_is_skipped(tmp_path: pathlib.Path) -> None:
    _write_skill(
        tmp_path,
        "alpha",
        skill_lines=3,
        references=_entry("t", 'lines: "SKILL.md at time of this commit: 1->999"\n'),
    )
    findings, notes = _scan(tmp_path)
    assert findings == []
    assert any("scoped to a past commit in prose" in note.message for note in notes)


def test_superseded_claim_is_skipped_and_the_last_one_is_checked(tmp_path: pathlib.Path) -> None:
    references = _entry("first", "lines: 1->4\n") + _entry("second", "lines: 4->9\n")
    _write_skill(tmp_path, "alpha", skill_lines=9, references=references)
    findings, notes = _scan(tmp_path)
    assert findings == []
    assert any("superseded by a later claim" in note.message for note in notes)


def test_traversal_token_is_refused(tmp_path: pathlib.Path) -> None:
    (tmp_path / "outside.md").write_text("z\n" * 4, encoding="utf-8")
    _write_skill(
        tmp_path,
        "alpha",
        skill_lines=3,
        references=_entry("t", 'worked_examples_lines: "../../outside.md 1->4"\n'),
    )
    findings, notes = _scan(tmp_path)
    assert findings == []
    assert any("names no file" in note.message or "binds to no file" in note.message for note in notes)


def test_traversal_segment_inside_a_token_is_refused(tmp_path: pathlib.Path) -> None:
    """`../../x.md` alone never reaches _resolve_in_skill (the token regex must
    start with an alphanumeric), but a token that *starts* legally and then
    escapes does -- so the `..` guard is reachable, not decoration."""
    (tmp_path / "outside.md").write_text("z\n" * 4, encoding="utf-8")
    assert gate._resolve_in_skill("references/../../../outside.md", tmp_path / "skills" / "alpha") is None


def test_symlink_escaping_the_skill_directory_is_refused(tmp_path: pathlib.Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text("z\n" * 4, encoding="utf-8")
    skill_dir = tmp_path / "skills" / "alpha"
    skill_dir.mkdir(parents=True)
    (skill_dir / "escape.md").symlink_to(outside)
    assert gate._resolve_in_skill("escape.md", skill_dir) is None


def test_sidecar_without_references_is_clean(tmp_path: pathlib.Path) -> None:
    _write_skill(tmp_path, "alpha")
    findings, notes = _scan(tmp_path)
    assert findings == []
    assert notes == []


def test_missing_target_file_is_a_finding(tmp_path: pathlib.Path) -> None:
    sidecar = _write_skill(tmp_path, "alpha", references=_entry("t", "lines: 1->4\n"))
    (sidecar.parent.parent / _SKILL_MD).unlink()
    findings, _ = _scan(tmp_path)
    assert len(findings) == 1
    assert "does not exist" in findings[0].message


# --------------------------------------------------------------------------
# Commit resolution
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_outcome_commit_key_is_checked_at_that_commit(tmp_path: pathlib.Path) -> None:
    _init_repo(tmp_path)
    _write_skill(tmp_path, "alpha", skill_lines=4)
    old_sha = _commit(tmp_path, "four lines")

    _write_skill(
        tmp_path,
        "alpha",
        skill_lines=40,
        references=_entry("t", f'lines: "1->4"\ncommit: "{old_sha}"\n'),
    )
    findings, notes = _scan(tmp_path)
    assert findings == [], [note.render() for note in notes]

    _write_skill(
        tmp_path,
        "alpha",
        skill_lines=40,
        references=_entry("t", f'lines: "1->40"\ncommit: "{old_sha}"\n'),
    )
    findings, _ = _scan(tmp_path)
    assert len(findings) == 1
    assert f"commit {old_sha} has 4" in findings[0].message


@pytest.mark.slow
def test_the_commit_helper_yields_a_short_sha_the_gate_reads_as_a_citation(tmp_path: pathlib.Path) -> None:
    """Issue #960: pins `_commit_with_citable_short_sha`'s own postcondition.

    Without it the re-roll loop could silently stop re-rolling -- returning an
    all-numeric short SHA again -- and the only symptom would be the ~2.3%
    flake coming back in the test below, which is exactly the failure mode
    that is expensive to diagnose from CI.
    """
    _init_repo(tmp_path)
    _write_skill(tmp_path, "alpha", skill_lines=4)
    sha = _commit_with_citable_short_sha(tmp_path, "four lines")
    assert gate._SHA_TOKEN_RE.fullmatch(sha[:SHORT_SHA_LEN])


@pytest.mark.slow
def test_the_commit_helper_rerolls_until_the_short_sha_is_citable(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue #960: exercises the re-roll branch, which a passing first roll skips.

    ~97.7% of runs satisfy the condition immediately, so the loop body is dead
    code in almost every run of the two tests above -- it could stop amending
    entirely and they would still pass. Rejecting the first two candidates
    forces it, and the assertions check the two things that make the loop
    worth having: it kept going, and what it returned is a real commit.
    """
    _init_repo(tmp_path)
    _write_skill(tmp_path, "alpha", skill_lines=4)

    seen: list[str] = []

    class _RejectFirstTwo:
        def fullmatch(self, token: str) -> object | None:
            seen.append(token)
            return None if len(seen) <= 2 else token

    monkeypatch.setattr(gate, "_SHA_TOKEN_RE", _RejectFirstTwo())
    sha = _commit_with_citable_short_sha(tmp_path, "four lines")

    assert len(seen) == 3, f"expected two re-rolls before acceptance, saw candidates {seen}"
    assert len(set(seen)) == 3, f"re-rolling must change the SHA, got repeats: {seen}"
    assert sha == _git(tmp_path, "rev-parse", "HEAD")
    assert _git(tmp_path, "rev-parse", f"{sha}^{{commit}}") == sha


@pytest.mark.slow
def test_the_commit_helper_names_an_evaluated_candidate_when_it_gives_up(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue #960, review round 1: the give-up message must not name a candidate
    no rule ever ran against.

    The first version amended once after its final check, so the SHA in the
    `AssertionError` was the untested result of that trailing amend and the
    fixture repository was left one rewrite past the last evaluated state --
    reachable exactly when the rule is stubbed or narrowed so nothing can
    satisfy it, which is the path the message exists for.
    """
    _init_repo(tmp_path)
    _write_skill(tmp_path, "alpha", skill_lines=4)

    evaluated: list[str] = []

    class _RejectEverything:
        def fullmatch(self, token: str) -> object | None:
            evaluated.append(token)
            return None

    monkeypatch.setattr(gate, "_SHA_TOKEN_RE", _RejectEverything())
    with pytest.raises(AssertionError) as excinfo:
        _commit_with_citable_short_sha(tmp_path, "four lines")

    named = str(excinfo.value).split("last evaluated was ")[1].strip().strip("'\"")
    assert named in evaluated, f"give-up message names {named!r}, which was never evaluated: {evaluated}"
    assert named == evaluated[-1]
    assert named == _git(tmp_path, "rev-parse", "HEAD")[:SHORT_SHA_LEN], (
        "the repository was left past the last evaluated candidate"
    )
    assert len(evaluated) == _MAX_SHA_REROLLS + 1


def test_an_all_numeric_short_sha_is_not_read_as_a_commit_citation(tmp_path: pathlib.Path) -> None:
    """Issue #960: pins the exclusion `gate._SHA_TOKEN_RE`'s comment documents.

    A token of only digits is not a commit citation even when it is a real
    commit's real short SHA, because the rule that keeps a seven-or-more-digit
    line count out of `git rev-parse` cannot tell the two apart. The claim
    below therefore parses as unanchored and is checked against the working
    tree, not against any commit. Deliberately built without a git repository:
    that is the point -- nothing here reaches git at all.

    Note what the assertion below actually says: the result is a `Finding`, not
    a note. On a real sidecar this is a blocking false positive against a
    correct claim, not a citation quietly downgraded to "unverified" -- issue
    #965 tracks narrowing the rule so a resolvable all-numeric short SHA
    anchors its claim. This test pins current behavior so that change is a
    deliberate act with a failing test attached, rather than a silent drift.
    """
    _write_skill(
        tmp_path,
        "alpha",
        skill_lines=40,
        references=_entry("t", 'lines: "measured at 12345678: 1->4"\n'),
    )
    findings, _ = _scan(tmp_path)
    assert len(findings) == 1
    assert "the checked-out tree has 40" in findings[0].message


@pytest.mark.slow
def test_inline_sha_in_the_claim_value_anchors_it(tmp_path: pathlib.Path) -> None:
    _init_repo(tmp_path)
    _write_skill(tmp_path, "alpha", skill_lines=4)
    # Issue #960: not `_commit`, whose short SHA is all digits ~2.3% of runs --
    # a shape this gate documents as not a commit citation, which made this
    # test fail on its own fixture value rather than on gate behavior.
    old_sha = _commit_with_citable_short_sha(tmp_path, "four lines")
    short = old_sha[:SHORT_SHA_LEN]

    _write_skill(
        tmp_path,
        "alpha",
        skill_lines=40,
        references=_entry("t", f'lines: "measured at {short}: 1->4"\n'),
    )
    findings, notes = _scan(tmp_path)
    assert findings == [], [note.render() for note in notes]


@pytest.mark.slow
def test_an_anchored_claim_is_not_superseded_by_a_later_unanchored_one(tmp_path: pathlib.Path) -> None:
    _init_repo(tmp_path)
    _write_skill(tmp_path, "alpha", skill_lines=4)
    old_sha = _commit(tmp_path, "four lines")

    references = _entry("historical", f'lines: "1->9"\ncommit: "{old_sha}"\n') + _entry("current", "lines: 4->40\n")
    _write_skill(tmp_path, "alpha", skill_lines=40, references=references)
    findings, _ = _scan(tmp_path)
    assert len(findings) == 1
    assert f"commit {old_sha}" in findings[0].message


@pytest.mark.slow
def test_cited_commit_absent_from_the_checkout_is_unverifiable_not_a_finding(tmp_path: pathlib.Path) -> None:
    _init_repo(tmp_path)
    _write_skill(tmp_path, "alpha", skill_lines=40)
    _commit(tmp_path, "initial")

    absent = "0" * 39 + "a"
    _write_skill(
        tmp_path,
        "alpha",
        skill_lines=40,
        references=_entry("t", f'lines: "1->9"\ncommit: "{absent}"\n'),
    )
    findings, notes = _scan(tmp_path)
    # Never downgraded to the working-tree comparison: doing so would report a
    # mismatch against a claim that is accurate at the commit it cites.
    assert findings == []
    assert any("absent from this checkout" in note.message for note in notes)


@pytest.mark.slow
def test_cited_commit_missing_the_named_path_is_a_finding(tmp_path: pathlib.Path) -> None:
    _init_repo(tmp_path)
    _write_skill(tmp_path, "alpha", skill_lines=4)
    old_sha = _commit(tmp_path, "no references dir yet")

    _write_skill(
        tmp_path,
        "alpha",
        skill_lines=4,
        reference_files={"one.md": 5},
        references=_entry("t", f'lines: "one.md 2->5"\ncommit: "{old_sha}"\n'),
    )
    findings, _ = _scan(tmp_path)
    assert len(findings) == 1
    assert "does not contain skills/alpha/references/one.md" in findings[0].message


def test_a_citation_is_recorded_without_consulting_git(tmp_path: pathlib.Path) -> None:
    """Extraction must not confirm a citation first: doing so downgraded an
    unresolvable one to the working-tree comparison, inventing a mismatch."""
    sidecar = _write_skill(
        tmp_path,
        "alpha",
        skill_lines=40,
        references=_entry("t", 'lines: "1->9"\ncommit: "deadbee"\n'),
    )
    claims, _, findings = gate.collect_claims(sidecar, tmp_path)
    assert findings == []
    assert [claim.rev for claim in claims] == ["deadbee"]


# --------------------------------------------------------------------------
# Fail-closed behaviour (dimensions.md dimension 15)
# --------------------------------------------------------------------------


def test_zero_sidecars_is_a_finding(tmp_path: pathlib.Path) -> None:
    (tmp_path / "skills").mkdir()
    findings, _ = _scan(tmp_path)
    assert len(findings) == 1
    assert "refusing to report clean" in findings[0].message


def test_unparseable_yaml_is_a_finding(tmp_path: pathlib.Path) -> None:
    sidecar = _write_skill(tmp_path, "alpha")
    sidecar.write_text("spec: [unclosed\n", encoding="utf-8")
    findings, _ = _scan(tmp_path)
    assert len(findings) == 1
    assert "not valid YAML" in findings[0].message


def test_unreadable_sidecar_is_a_finding(tmp_path: pathlib.Path) -> None:
    sidecar = _write_skill(tmp_path, "alpha")
    sidecar.unlink()
    sidecar.mkdir()
    findings, _ = _scan(tmp_path)
    assert len(findings) == 1
    assert "could not be read" in findings[0].message


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("- just a list\n", "does not parse as a YAML mapping"),
        ("apiVersion: gitapex.io/v1alpha1\n", "has no spec block"),
        ("spec: not-a-mapping\n", "spec is not a mapping"),
        ("spec:\n  references: not-a-list\n", "spec.references is not a list"),
        ("spec:\n  references:\n    - not-a-mapping\n", "entry is not a mapping"),
        ("spec:\n  references:\n    - outcome: not-a-mapping\n", "outcome is not a mapping"),
    ],
)
def test_malformed_shapes_are_findings(tmp_path: pathlib.Path, body: str, expected: str) -> None:
    sidecar = _write_skill(tmp_path, "alpha")
    sidecar.write_text(body, encoding="utf-8")
    findings, _ = _scan(tmp_path)
    assert len(findings) == 1
    assert expected in findings[0].message


def test_non_scalar_lines_value_is_a_finding(tmp_path: pathlib.Path) -> None:
    """str() on a mapping yields text no claim regex matches -- a fail-open
    skip if it is not caught explicitly."""
    sidecar = _write_skill(tmp_path, "alpha")
    sidecar.write_text(
        "spec:\n  references:\n    - outcome:\n        lines:\n          nested: 4->9\n",
        encoding="utf-8",
    )
    findings, _ = _scan(tmp_path)
    assert len(findings) == 1
    assert "is not a scalar" in findings[0].message


def test_unrecognized_lines_value_is_reported_as_a_note(tmp_path: pathlib.Path) -> None:
    _write_skill(tmp_path, "alpha", references=_entry("t", 'lines: "unchanged this round"\n'))
    findings, notes = _scan(tmp_path)
    assert findings == []
    assert any("no line-count claim recognized" in note.message for note in notes)


def test_a_broken_git_root_raises_instead_of_reporting_unverifiable(tmp_path: pathlib.Path) -> None:
    """tmp_path is not a git repository at all, so an anchored claim must not
    read as a benign shallow-clone note."""
    _write_skill(
        tmp_path,
        "alpha",
        references=_entry("t", 'lines: "1->9"\ncommit: "deadbee"\n'),
    )
    with pytest.raises(RuntimeError, match="not a usable git repository"):
        _scan(tmp_path)


def test_git_binary_missing_raises_rather_than_reporting_clean(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> object:
        raise OSError("git not found")

    monkeypatch.setattr(gate.subprocess, "run", boom)
    with pytest.raises(RuntimeError, match="could not be run"):
        gate.resolve_commitish("HEAD", tmp_path)


def test_unreadable_target_file_raises(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "a-directory"
    target.mkdir()
    with pytest.raises(RuntimeError, match="could not read"):
        gate.line_count_in_worktree(target)


def test_absent_target_file_reads_as_none(tmp_path: pathlib.Path) -> None:
    assert gate.line_count_in_worktree(tmp_path / "nope.md") is None


# --------------------------------------------------------------------------
# CLI surface
# --------------------------------------------------------------------------


def test_format_report_clean() -> None:
    assert "No outcome.lines claim drift found." in gate.format_report([], [])


def test_format_report_lists_findings_and_notes() -> None:
    report = gate.format_report(
        [gate.Finding("loc", "wrong")],
        [gate.Note("loc2", "skipped")],
    )
    assert "note: loc2: skipped" in report
    assert "1 line-count claim finding(s):" in report
    assert "  - loc: wrong" in report
    assert "git show <sha>:<path> | wc -l" in report


def test_main_returns_zero_against_the_real_repository(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main() == 0
    assert "No outcome.lines claim drift found." in capsys.readouterr().out


def test_main_reports_a_runtime_error_as_exit_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(**kwargs: object) -> object:
        raise RuntimeError("git exploded")

    monkeypatch.setattr(gate, "find_drift", boom)
    assert gate.main() == 1
    assert "error: git exploded" in capsys.readouterr().err


def test_main_returns_one_when_a_finding_exists(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "find_drift", lambda: ([gate.Finding("loc", "wrong")], []))
    assert gate.main() == 1
    assert "loc: wrong" in capsys.readouterr().out


# --------------------------------------------------------------------------
# Real repository -- this test IS the gate's CI enforcement
# --------------------------------------------------------------------------


def test_real_repository_has_no_outcome_lines_drift() -> None:
    findings, _ = gate.find_drift()
    assert findings == [], "\n".join(finding.render() for finding in findings)


def test_real_repository_verifies_at_least_one_claim() -> None:
    """A gate whose heuristic silently matched nothing would pass the test
    above vacuously. Assert real coverage, not just absence of findings."""
    sidecar = REPO_ROOT / "skills" / "evaluating-deterministic-gate-quality" / "metadata" / "gitapex.yaml"
    claims, _, findings = gate.collect_claims(sidecar, REPO_ROOT)
    assert findings == []
    checkable, _ = gate._partition_unanchored(claims)
    assert len(checkable) >= 5
    assert any(claim.target.endswith("SKILL.md") for claim in checkable)


def test_gate_is_registered_in_the_ssot() -> None:
    import json

    registry = json.loads((REPO_ROOT / ".gitapex" / "ssot.json").read_text(encoding="utf-8"))
    row = next(gate_row for gate_row in registry["gates"] if gate_row["id"] == "metadata-outcome-lines-drift")
    assert row["script"] == ".github/scripts/gitapex_gate_metadata_outcome_lines.py"
    assert row["cluster"] in registry["clusters"]
    assert "skill-metadata-sidecar" in row["policy_refs"]
