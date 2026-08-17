"""Tests for gitapex_check_retro_gate_resolved.py.

Refs #1176: merge-retrospective's Step 1 must partition retrospective
issue numbers using the same two-signal check (citing commit AND
`.gitapex/ssot.json` `gates[].tracking_issue` entry)
`.github/scripts/gitapex_scan_retrospective_gate_drift.py` already
implements, instead of a weaker citation-only re-derivation. This file
tests the standalone re-implementation in the sibling module.

No test in this file makes a real subprocess or filesystem call outside
`tmp_path` -- the git layer is exercised through an injected `runner`,
mirroring test_gitapex_scan_retrospective_gate_drift.py's own fixture style.

Not wired into the root pyproject.toml testpaths -- this skill's checker is
meant to stand alone; run directly with:
    python3 -m pytest skills/merge-retrospective/scripts/
"""

from __future__ import annotations

import json
import pathlib
import subprocess

import gitapex_check_retro_gate_resolved as checker
import pytest

# ---------------------------------------------------------------------------
# citation_count
# ---------------------------------------------------------------------------


def test_citation_count_matches_bare_hash_number():
    assert checker.citation_count(["fix(gate): close gaps (Refs #187)"], 187) == 1


def test_citation_count_matches_multiple_bracketed_citations_in_one_message():
    message = "docs(skills): re-escalate (refs #242, #246)"
    assert checker.citation_count([message], 242) == 1
    assert checker.citation_count([message], 246) == 1


def test_citation_count_does_not_match_longer_number_containing_target_as_prefix():
    assert checker.citation_count(["Refs #1870"], 187) == 0


def test_citation_count_does_not_match_longer_number_containing_target_as_suffix():
    assert checker.citation_count(["Refs #2187"], 187) == 0


def test_citation_count_sums_across_multiple_citing_commits():
    messages = ["feat: a (Refs #242)", "fix: b (Refs #242)", "chore: c"]
    assert checker.citation_count(messages, 242) == 2


def test_citation_count_zero_when_no_commit_cites_it():
    assert checker.citation_count(["chore: unrelated"], 118) == 0


# ---------------------------------------------------------------------------
# partition_by_resolution -- the two-signal AND-not-OR semantics (issue #709)
# ---------------------------------------------------------------------------


def test_partition_resolves_when_citation_and_tracking_issue_both_present():
    messages = ["fix(gates): close gaps (Refs #650)"]
    resolved, unresolved = checker.partition_by_resolution([650], messages, {650})
    assert resolved == [650]
    assert unresolved == []


def test_partition_keeps_unresolved_when_citation_present_but_no_tracking_issue():
    # Defeat test for an OR-shaped bug: a citing commit alone must never be
    # enough. Reproduces #314's real false negative shape: a commit cited
    # "#314" while changing something unrelated, and no ssot.json gate was
    # ever registered with tracking_issue == 314.
    messages = ["chore(gates): document budget caps and permanent human-review-of-merge (#318)", "Refs #314"]
    resolved, unresolved = checker.partition_by_resolution([314], messages, set())
    assert resolved == []
    assert unresolved == [314]


def test_partition_keeps_unresolved_when_tracking_issue_present_but_no_citation():
    # Defeat test for the opposite OR-shaped bug: a registered gate alone,
    # with zero citing commits, must never be enough either.
    resolved, unresolved = checker.partition_by_resolution([650], ["chore: unrelated"], {650})
    assert resolved == []
    assert unresolved == [650]


def test_partition_keeps_unresolved_when_neither_signal_present():
    resolved, unresolved = checker.partition_by_resolution([118], ["chore: unrelated"], set())
    assert resolved == []
    assert unresolved == [118]


def test_partition_keeps_multi_proposal_issue_665_shape_when_only_one_subproposal_has_a_tracking_entry():
    # Reproduces #665's real false negative: a commit cited "refs #665
    # repair 6" (repair 6 landed as tracking_issue 702, not 665), while
    # #665's other proposed repairs remain unimplemented. 665 itself must
    # stay unresolved even though a commit cites it.
    messages = ["feat(ci): add a repository-wide hidden-character gate (refs #665 repair 6)"]
    resolved, unresolved = checker.partition_by_resolution([665], messages, {702})
    assert resolved == []
    assert unresolved == [665]


def test_partition_every_input_number_appears_in_exactly_one_output_array():
    # The ACM's own required fixture: every input issue number partitions
    # into exactly one of the two arrays, regardless of signal combination.
    issue_numbers = [1, 2, 3, 4]
    messages = ["Refs #1", "Refs #2"]
    tracking_issues = {1, 3}
    resolved, unresolved = checker.partition_by_resolution(issue_numbers, messages, tracking_issues)
    assert sorted(resolved + unresolved) == sorted(issue_numbers)
    assert set(resolved).isdisjoint(unresolved)
    assert resolved == [1]
    assert unresolved == [2, 3, 4]


def test_partition_repeated_issue_number_lands_in_resolved_every_time():
    # Defeat test for a "consume the matched tracking_issues entry" mutation
    # bug: a stateful implementation that discards a number from a local
    # copy of tracking_issues once matched would wrongly flip the second
    # occurrence of a repeated issue number to unresolved. Every occurrence
    # must independently land in resolved.
    resolved, unresolved = checker.partition_by_resolution([650, 650, 650], ["Refs #650"], {650})
    assert resolved == [650, 650, 650]
    assert unresolved == []


def test_partition_preserves_input_order_within_each_bucket():
    messages = ["Refs #3", "Refs #1"]
    tracking_issues = {3, 1}
    resolved, unresolved = checker.partition_by_resolution([3, 2, 1], messages, tracking_issues)
    assert resolved == [3, 1]
    assert unresolved == [2]


# ---------------------------------------------------------------------------
# git_commit_messages
# ---------------------------------------------------------------------------


def _fake_runner(stdout: str, returncode: int = 0, stderr: str = ""):
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr=stderr)

    return runner


def test_git_commit_messages_parses_multiple_commits():
    raw = (
        "\x1eaaa\x1fMerge pull request #292\n\nfeat(skill): add thing\n"
        "\x1ebbb\x1ffeat(skill): adversarial-hardening round\n"
    )
    runner = _fake_runner(raw)
    messages = checker.git_commit_messages("HEAD", ".", runner=runner)
    assert messages == [
        "Merge pull request #292\n\nfeat(skill): add thing",
        "feat(skill): adversarial-hardening round",
    ]


def test_git_commit_messages_handles_empty_body():
    raw = "\x1eaaa\x1fchore: typo\n"
    runner = _fake_runner(raw)
    assert checker.git_commit_messages("HEAD", ".", runner=runner) == ["chore: typo"]


def test_git_commit_messages_empty_log():
    runner = _fake_runner("")
    assert checker.git_commit_messages("HEAD", ".", runner=runner) == []


def test_git_commit_messages_raises_on_nonzero_exit():
    runner = _fake_runner("", returncode=128, stderr="unknown revision")
    with pytest.raises(checker.GitLogError):
        checker.git_commit_messages("bad-ref", ".", runner=runner)


# ---------------------------------------------------------------------------
# load_gate_tracking_issues
# ---------------------------------------------------------------------------


def test_load_gate_tracking_issues_parses_ints_and_skips_null_or_missing(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "gates": [
                    {"id": "a", "tracking_issue": 650},
                    {"id": "b", "tracking_issue": None},
                    {"id": "c"},
                    {"id": "d", "tracking_issue": 297},
                ]
            }
        )
    )
    assert checker.load_gate_tracking_issues(str(ssot)) == {650, 297}


def test_load_gate_tracking_issues_raises_on_missing_file(tmp_path):
    with pytest.raises(checker.SsotLedgerError):
        checker.load_gate_tracking_issues(str(tmp_path / "nonexistent.json"))


def test_load_gate_tracking_issues_raises_on_undecodable_file(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_bytes(b"\xff\xfe bad")
    with pytest.raises(checker.SsotLedgerError):
        checker.load_gate_tracking_issues(str(ssot))


def test_load_gate_tracking_issues_raises_on_malformed_json(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text("{not valid json")
    with pytest.raises(checker.SsotLedgerError):
        checker.load_gate_tracking_issues(str(ssot))


def test_load_gate_tracking_issues_raises_when_not_a_json_object(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text("[]")
    with pytest.raises(checker.SsotLedgerError):
        checker.load_gate_tracking_issues(str(ssot))


def test_load_gate_tracking_issues_raises_when_gates_list_missing_or_empty(tmp_path):
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"gates": []}))
    with pytest.raises(checker.SsotLedgerError):
        checker.load_gate_tracking_issues(str(ssot))


def test_load_gate_tracking_issues_excludes_non_int_and_bool_values(tmp_path):
    # `bool` is an `int` subclass in Python -- a stray `true`/`false` must
    # not be silently coerced into corroborating issue #1/#0.
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "gates": [
                    {"id": "a", "tracking_issue": True},
                    {"id": "b", "tracking_issue": False},
                    {"id": "c", "tracking_issue": "297"},
                    {"id": "d", "tracking_issue": 297.0},
                    {"id": "e", "tracking_issue": [297]},
                    {"id": "f", "tracking_issue": 650},
                ]
            }
        )
    )
    assert checker.load_gate_tracking_issues(str(ssot)) == {650}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_prints_partition_as_one_json_object_with_unresolved_first(monkeypatch, capsys):
    monkeypatch.setattr(checker, "git_commit_messages", lambda *a, **k: ["Refs #1107"])
    monkeypatch.setattr(checker, "load_gate_tracking_issues", lambda *a, **k: {1107})
    exit_code = checker.main(["1109", "1107"])
    assert exit_code == 0
    out = capsys.readouterr().out.strip()
    assert json.loads(out) == {"unresolved": [1109], "resolved": [1107]}
    # Key order matches the worked example in issue #1176's own Acceptance
    # Criteria Map (unresolved before resolved).
    assert out.startswith('{"unresolved"')


def test_main_accepts_many_issue_numbers_in_one_invocation(monkeypatch, capsys):
    # Batch, one process invocation -- the interface issue #1176 requires,
    # not one invocation per issue number.
    monkeypatch.setattr(checker, "git_commit_messages", lambda *a, **k: ["Refs #1107", "Refs #1114"])
    monkeypatch.setattr(checker, "load_gate_tracking_issues", lambda *a, **k: {1107, 1114})
    exit_code = checker.main(["1109", "1107", "1108", "1114"])
    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert sorted(out["resolved"] + out["unresolved"]) == [1107, 1108, 1109, 1114]
    assert out["resolved"] == [1107, 1114]
    assert out["unresolved"] == [1109, 1108]


def test_main_exits_one_on_git_log_error(monkeypatch, capsys):
    def raise_git_error(*a, **k):
        raise checker.GitLogError("boom")

    monkeypatch.setattr(checker, "git_commit_messages", raise_git_error)
    exit_code = checker.main(["1"])
    assert exit_code == 1
    assert "boom" in capsys.readouterr().err


def test_main_exits_one_on_ssot_ledger_error(monkeypatch, capsys):
    monkeypatch.setattr(checker, "git_commit_messages", lambda *a, **k: [])

    def raise_ssot_error(*a, **k):
        raise checker.SsotLedgerError("boom")

    monkeypatch.setattr(checker, "load_gate_tracking_issues", raise_ssot_error)
    exit_code = checker.main(["1"])
    assert exit_code == 1
    assert "boom" in capsys.readouterr().err


def test_main_never_prints_partial_output_on_ssot_error(monkeypatch, capsys):
    # git_commit_messages succeeds, then load_gate_tracking_issues fails --
    # stdout must stay empty rather than an already-computed-but-wrong
    # partition (this script has no threshold, so any stdout output at all
    # is a claim of a trustworthy full partition).
    monkeypatch.setattr(checker, "git_commit_messages", lambda *a, **k: ["Refs #1"])

    def raise_ssot_error(*a, **k):
        raise checker.SsotLedgerError("boom")

    monkeypatch.setattr(checker, "load_gate_tracking_issues", raise_ssot_error)
    checker.main(["1"])
    assert capsys.readouterr().out == ""


def test_main_uses_default_ref_and_cwd_and_ssot_path(monkeypatch):
    received = {}

    def fake_git_commit_messages(ref, cwd):
        received["ref"] = ref
        received["cwd"] = cwd
        return []

    def fake_load_gate_tracking_issues(path):
        received["ssot_path"] = path
        return set()

    monkeypatch.setattr(checker, "git_commit_messages", fake_git_commit_messages)
    monkeypatch.setattr(checker, "load_gate_tracking_issues", fake_load_gate_tracking_issues)
    checker.main(["1"])
    assert received["ref"] == "HEAD"
    assert received["cwd"] == "."
    assert received["ssot_path"] == str(pathlib.Path(".gitapex/ssot.json"))


def test_main_rejects_non_integer_issue_number(capsys):
    with pytest.raises(SystemExit):
        checker.main(["not-a-number"])
    assert "invalid int value" in capsys.readouterr().err


def test_main_requires_at_least_one_issue_number(capsys):
    with pytest.raises(SystemExit):
        checker.main([])
