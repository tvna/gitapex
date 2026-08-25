"""Tests for the retrospective gate-resolution checker
(gitapex_check_retro_gate_resolved.py).

Issue #1176: merge-retrospective's Step 1 previously re-derived a weaker,
citation-only approximation of "is this retrospective issue's gate still
open" live, every cycle, producing observed cross-session divergence.
This script bundles the same two-signal check
.github/scripts/gitapex_scan_retrospective_gate_drift.py already
implements (issue #709: a citing commit alone is not proof a gate was
actually built), deliberately re-implemented -- not imported or
subprocess-invoked -- against a local `git log` and `.gitapex/ssot.json`.

No test in this file makes a real subprocess or filesystem call outside
pytest's own tmp_path -- the git layer is exercised through an injected
`runner`, mirroring test_gitapex_scan_retrospective_gate_drift.py's own
fixture style.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
from collections.abc import Callable

import gitapex_check_retro_gate_resolved as checker
import pytest

# ---------------------------------------------------------------------------
# citation_count
# ---------------------------------------------------------------------------


def test_citation_count_matches_bare_hash_number() -> None:
    assert checker.citation_count(["fix(gate): close gaps (Refs #187)"], 187) == 1


def test_citation_count_zero_when_no_commit_cites_it() -> None:
    assert checker.citation_count(["chore: unrelated"], 118) == 0


def test_citation_count_does_not_match_longer_number_containing_target_as_prefix() -> None:
    # Defeat case: a naive substring match would wrongly resolve #187 off
    # a commit that only cites the unrelated, larger issue #1870.
    assert checker.citation_count(["Refs #1870"], 187) == 0


def test_citation_count_does_not_match_longer_number_containing_target_as_suffix() -> None:
    assert checker.citation_count(["Refs #2187"], 187) == 0


def test_citation_count_sums_across_multiple_citing_commits() -> None:
    messages = ["feat: a (Refs #242)", "fix: b (Refs #242)", "chore: c"]
    assert checker.citation_count(messages, 242) == 2


# ---------------------------------------------------------------------------
# partition_resolved
# ---------------------------------------------------------------------------


def test_partition_resolved_clears_when_citation_and_tracking_issue_both_present() -> None:
    messages = ["fix(gates): close gaps (Refs #650)"]
    unresolved, resolved = checker.partition_resolved([650], messages, {650: 1}, {})
    assert unresolved == []
    assert resolved == [650]


def test_partition_resolved_keeps_unresolved_when_citation_lacks_corroboration() -> None:
    # Defeat case mirroring the CI script's own #314 regression: a citing
    # commit exists, but no ssot.json gate was ever registered for it.
    unresolved, resolved = checker.partition_resolved([314], ["Refs #314"], {}, {})
    assert unresolved == [314]
    assert resolved == []


def test_partition_resolved_keeps_unresolved_when_tracking_issue_present_but_no_citation() -> None:
    # Defeat case: the registry has a tracking_issue entry, but no commit
    # actually cites this issue number -- a bare-registry match alone must
    # not be sufficient either (both signals are required, not either).
    unresolved, resolved = checker.partition_resolved([702], ["chore: unrelated"], {702: 1}, {})
    assert unresolved == [702]
    assert resolved == []


def test_partition_resolved_keeps_unresolved_when_neither_signal_present() -> None:
    unresolved, resolved = checker.partition_resolved([999], ["chore: unrelated"], {}, {})
    assert unresolved == [999]
    assert resolved == []


def test_partition_resolved_every_input_number_appears_in_exactly_one_array() -> None:
    issue_numbers = [1109, 1107, 1108, 1114]
    messages = ["Refs #1107", "Refs #1108", "Refs #1114"]
    tracking_issue_counts = {1107: 1, 1108: 1, 1114: 1}
    unresolved, resolved = checker.partition_resolved(issue_numbers, messages, tracking_issue_counts, {})
    seen = sorted(unresolved) + sorted(resolved)
    assert sorted(seen) == sorted(issue_numbers)
    assert not (set(unresolved) & set(resolved))
    assert unresolved == [1109]
    assert sorted(resolved) == [1107, 1108, 1114]


def test_partition_resolved_handles_empty_issue_numbers() -> None:
    unresolved, resolved = checker.partition_resolved([], [], {}, {})
    assert unresolved == []
    assert resolved == []


def test_partition_resolved_deduplicates_repeated_resolved_issue_number() -> None:
    # Defeat case: merge-retrospective/SKILL.md's own Step 1 builds the CLI
    # candidate list from two separate searches (a label search plus a
    # title-text fallback for pre-label issues) concatenated together --
    # an issue matching both would otherwise appear twice in "resolved".
    unresolved, resolved = checker.partition_resolved([650, 650], ["Refs #650"], {650: 1}, {})
    assert unresolved == []
    assert resolved == [650]


def test_partition_resolved_deduplicates_repeated_unresolved_issue_number() -> None:
    unresolved, resolved = checker.partition_resolved([999, 999], ["chore: unrelated"], {}, {})
    assert unresolved == [999]
    assert resolved == []


def test_partition_resolved_deduplicates_while_preserving_first_occurrence_order() -> None:
    unresolved, resolved = checker.partition_resolved([650, 999, 650, 999], ["Refs #650"], {650: 1}, {})
    assert unresolved == [999]
    assert resolved == [650]


# ---------------------------------------------------------------------------
# partition_resolved: per-gate granularity (issue #1177)
# ---------------------------------------------------------------------------


def test_partition_resolved_stays_unresolved_when_multi_proposal_manifest_is_only_partially_built() -> None:
    # Issue #1129 shape: 6 distinct gates proposed, only 1 registered and
    # cited so far. Partial implementation must not resolve the issue.
    messages = ["fix(gates): close one of six gaps (Refs #1129)"]
    unresolved, resolved = checker.partition_resolved([1129], messages, {1129: 1}, {1129: 6})
    assert unresolved == [1129]
    assert resolved == []


def test_partition_resolved_clears_when_multi_proposal_manifest_is_fully_built() -> None:
    messages = ["fix(gates): close the last of two gaps (Refs #1130)"]
    unresolved, resolved = checker.partition_resolved([1130], messages, {1130: 2}, {1130: 2})
    assert unresolved == []
    assert resolved == [1130]


def test_partition_resolved_stays_unresolved_when_gate_count_falls_one_short() -> None:
    messages = ["fix(gates): close gaps (Refs #1131)"]
    unresolved, resolved = checker.partition_resolved([1131], messages, {1131: 2}, {1131: 3})
    assert unresolved == [1131]
    assert resolved == []


# ---------------------------------------------------------------------------
# git_commit_messages
# ---------------------------------------------------------------------------


def _fake_runner(stdout: str, returncode: int = 0, stderr: str = "") -> Callable[..., subprocess.CompletedProcess[str]]:
    def runner(*args: str, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr=stderr)

    return runner


def test_git_commit_messages_parses_multiple_commits() -> None:
    raw = "\x1eaaa\x1fMerge pull request #292\n\nfeat(skill): add thing\n\x1ebbb\x1ffeat(skill): round two\n"
    runner = _fake_runner(raw)
    messages = checker.git_commit_messages("HEAD", ".", runner=runner)
    assert messages == [
        "Merge pull request #292\n\nfeat(skill): add thing",
        "feat(skill): round two",
    ]


def test_git_commit_messages_empty_log() -> None:
    assert checker.git_commit_messages("HEAD", ".", runner=_fake_runner("")) == []


def test_git_commit_messages_raises_on_nonzero_exit() -> None:
    runner = _fake_runner("", returncode=128, stderr="unknown revision")
    with pytest.raises(checker.GitLogError):
        checker.git_commit_messages("bad-ref", ".", runner=runner)


# ---------------------------------------------------------------------------
# load_gate_tracking_issue_counts
# ---------------------------------------------------------------------------


def test_load_gate_tracking_issue_counts_parses_ints_and_skips_null_or_missing(tmp_path: pathlib.Path) -> None:
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
    assert checker.load_gate_tracking_issue_counts(str(ssot)) == {650: 1, 297: 1}


def test_load_gate_tracking_issue_counts_counts_multiple_gates_per_issue(tmp_path: pathlib.Path) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "gates": [
                    {"id": "a", "tracking_issue": 520},
                    {"id": "b", "tracking_issue": 520},
                    {"id": "c", "tracking_issue": 520},
                    {"id": "d", "tracking_issue": 650},
                ]
            }
        )
    )
    assert checker.load_gate_tracking_issue_counts(str(ssot)) == {520: 3, 650: 1}


def test_load_gate_tracking_issue_counts_raises_on_missing_file(tmp_path: pathlib.Path) -> None:
    with pytest.raises(checker.SsotLedgerError):
        checker.load_gate_tracking_issue_counts(str(tmp_path / "nonexistent.json"))


def test_load_gate_tracking_issue_counts_raises_on_malformed_json(tmp_path: pathlib.Path) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text("{not valid json")
    with pytest.raises(checker.SsotLedgerError):
        checker.load_gate_tracking_issue_counts(str(ssot))


def test_load_gate_tracking_issue_counts_raises_when_not_a_json_object(tmp_path: pathlib.Path) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text("[]")
    with pytest.raises(checker.SsotLedgerError):
        checker.load_gate_tracking_issue_counts(str(ssot))


def test_load_gate_tracking_issue_counts_raises_when_gates_list_missing_or_empty(tmp_path: pathlib.Path) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"gates": []}))
    with pytest.raises(checker.SsotLedgerError):
        checker.load_gate_tracking_issue_counts(str(ssot))


def test_load_gate_tracking_issue_counts_excludes_non_int_and_bool_values(tmp_path: pathlib.Path) -> None:
    # Defeat case: `bool` is an `int` subclass in Python -- a stray
    # `true`/`false` must not silently corroborate issue #1/#0.
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
    assert checker.load_gate_tracking_issue_counts(str(ssot)) == {650: 1}


# ---------------------------------------------------------------------------
# load_proposed_gate_requirements (issue #1177)
# ---------------------------------------------------------------------------


def test_load_proposed_gate_requirements_returns_proposal_counts(tmp_path: pathlib.Path) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "proposed_gates": [
                    {"tracking_issue": 1129, "proposals": ["a", "b", "c", "d", "e", "f"]},
                    {"tracking_issue": 1130, "proposals": ["x", "y"]},
                ]
            }
        )
    )
    assert checker.load_proposed_gate_requirements(str(ssot)) == {1129: 6, 1130: 2}


def test_load_proposed_gate_requirements_empty_when_field_missing(tmp_path: pathlib.Path) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"gates": []}))
    assert checker.load_proposed_gate_requirements(str(ssot)) == {}


def test_load_proposed_gate_requirements_empty_when_field_empty(tmp_path: pathlib.Path) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"proposed_gates": []}))
    assert checker.load_proposed_gate_requirements(str(ssot)) == {}


def test_load_proposed_gate_requirements_raises_when_field_not_a_list(tmp_path: pathlib.Path) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"proposed_gates": "not-a-list"}))
    with pytest.raises(checker.SsotLedgerError):
        checker.load_proposed_gate_requirements(str(ssot))


def test_load_proposed_gate_requirements_raises_on_duplicate_tracking_issue(tmp_path: pathlib.Path) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "proposed_gates": [
                    {"tracking_issue": 1129, "proposals": ["a", "b"]},
                    {"tracking_issue": 1129, "proposals": ["c", "d"]},
                ]
            }
        )
    )
    with pytest.raises(checker.SsotLedgerError):
        checker.load_proposed_gate_requirements(str(ssot))


def test_load_proposed_gate_requirements_raises_on_non_dict_entry(tmp_path: pathlib.Path) -> None:
    # Issue #1177 adversarial-gate-quality review: unlike gates[]'s tolerant
    # skip of a malformed tracking_issue (safe -- under-counts a citation),
    # silently skipping a malformed proposed_gates[] entry would fall its
    # requirement back to the weaker default of 1, which can falsely
    # resolve a multi-gate issue -- so a malformed entry raises instead.
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"proposed_gates": ["not-a-dict", {"tracking_issue": 1131, "proposals": ["a", "b"]}]}))
    with pytest.raises(checker.SsotLedgerError):
        checker.load_proposed_gate_requirements(str(ssot))


def test_load_proposed_gate_requirements_raises_on_non_integer_tracking_issue(tmp_path: pathlib.Path) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"proposed_gates": [{"tracking_issue": "1129", "proposals": ["a", "b"]}]}))
    with pytest.raises(checker.SsotLedgerError):
        checker.load_proposed_gate_requirements(str(ssot))


def test_load_proposed_gate_requirements_raises_on_non_list_proposals(tmp_path: pathlib.Path) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"proposed_gates": [{"tracking_issue": 1130, "proposals": "not-a-list"}]}))
    with pytest.raises(checker.SsotLedgerError):
        checker.load_proposed_gate_requirements(str(ssot))


def test_load_proposed_gate_requirements_raises_on_missing_file(tmp_path: pathlib.Path) -> None:
    with pytest.raises(checker.SsotLedgerError):
        checker.load_proposed_gate_requirements(str(tmp_path / "nonexistent.json"))


# ---------------------------------------------------------------------------
# load_gate_and_proposed_gate_corroboration (issue #1177)
# ---------------------------------------------------------------------------


def test_load_gate_and_proposed_gate_corroboration_matches_the_two_separate_readers(
    tmp_path: pathlib.Path,
) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "gates": [
                    {"id": "a", "tracking_issue": 520},
                    {"id": "b", "tracking_issue": 520},
                ],
                "proposed_gates": [{"tracking_issue": 1129, "proposals": ["a", "b", "c"]}],
            }
        )
    )
    counts, requirements = checker.load_gate_and_proposed_gate_corroboration(str(ssot))
    assert counts == checker.load_gate_tracking_issue_counts(str(ssot))
    assert requirements == checker.load_proposed_gate_requirements(str(ssot))
    assert counts == {520: 2}
    assert requirements == {1129: 3}


def test_load_gate_and_proposed_gate_corroboration_reads_the_file_only_once(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"gates": [{"id": "a", "tracking_issue": 1}], "proposed_gates": []}))
    read_calls: list[int] = []
    original_read_text = pathlib.Path.read_text

    def counting_read_text(self: pathlib.Path, *args: object, **kwargs: object) -> str:
        if self == ssot:
            read_calls.append(1)
        return original_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(pathlib.Path, "read_text", counting_read_text)
    checker.load_gate_and_proposed_gate_corroboration(str(ssot))
    assert len(read_calls) == 1


def test_load_gate_and_proposed_gate_corroboration_raises_on_missing_file(tmp_path: pathlib.Path) -> None:
    with pytest.raises(checker.SsotLedgerError):
        checker.load_gate_and_proposed_gate_corroboration(str(tmp_path / "nonexistent.json"))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_prints_json_partition_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(checker, "git_commit_messages", lambda *a, **k: ["Refs #1107"])
    monkeypatch.setattr(checker, "load_gate_and_proposed_gate_corroboration", lambda *a, **k: ({1107: 1}, {}))
    exit_code = checker.main(["1109", "1107"])
    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"unresolved": [1109], "resolved": [1107]}


def test_main_exits_one_on_git_log_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def raise_git_error(*a: object, **k: object) -> list[str]:
        raise checker.GitLogError("boom")

    monkeypatch.setattr(checker, "git_commit_messages", raise_git_error)
    exit_code = checker.main(["1"])
    assert exit_code == 1
    assert "boom" in capsys.readouterr().err


def test_main_exits_one_on_ssot_ledger_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(checker, "git_commit_messages", lambda *a, **k: [])

    def raise_ssot_error(*a: object, **k: object) -> tuple[dict[int, int], dict[int, int]]:
        raise checker.SsotLedgerError("boom")

    monkeypatch.setattr(checker, "load_gate_and_proposed_gate_corroboration", raise_ssot_error)
    exit_code = checker.main(["1"])
    assert exit_code == 1
    assert "boom" in capsys.readouterr().err


def test_main_passes_default_ssot_path_joined_with_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    received: dict[str, str] = {}

    def fake_load(path: str) -> tuple[dict[int, int], dict[int, int]]:
        received["path"] = path
        return {}, {}

    monkeypatch.setattr(checker, "git_commit_messages", lambda *a, **k: [])
    monkeypatch.setattr(checker, "load_gate_and_proposed_gate_corroboration", fake_load)
    checker.main(["1", "--cwd", "/repo"])
    assert received["path"] == str(pathlib.Path("/repo") / ".gitapex/ssot.json")


def test_main_requires_at_least_one_issue_number() -> None:
    with pytest.raises(SystemExit):
        checker.main([])
