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

No test in this file makes a real subprocess call, or a real filesystem
call outside pytest's own tmp_path, except the marker drift-gate tests
near the bottom of this file, which deliberately read this repository's
real canonical marker sources -- the git layer above that is exercised
through an injected `runner`, mirroring
test_gitapex_scan_retrospective_gate_drift.py's own fixture style.
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
# is_gate_less (issue #1297)
# ---------------------------------------------------------------------------


def test_is_gate_less_matches_ci_stub_marker() -> None:
    body = "Automated stub opened by the post-merge-auto-retro gate for PR #42."
    assert checker.is_gate_less(body) is True


def test_is_gate_less_matches_zero_repair_fast_close_marker() -> None:
    body = "PR #63 merged with zero repairs.\nRetrospective status: zero-repair-fast-close\nRefs #63."
    assert checker.is_gate_less(body) is True


def test_is_gate_less_false_when_neither_marker_present() -> None:
    body = "1. [Failed CI rerun] ...\n   Status: `missing-deterministic-gate`\n   Proposed gate: add a pre-push hook."
    assert checker.is_gate_less(body) is False


def test_is_gate_less_false_for_empty_body() -> None:
    assert checker.is_gate_less("") is False


def test_is_gate_less_matches_zero_repair_marker_with_bullet_prefix() -> None:
    body = "PR #63 merged with zero repairs.\n- Retrospective status: zero-repair-fast-close\nRefs #63."
    assert checker.is_gate_less(body) is True


def test_is_gate_less_matches_zero_repair_marker_with_crlf_line_endings() -> None:
    # Defeat case: GitHub is known to deliver an issue body with CRLF
    # endings for one authored or edited via the web UI -- the marker
    # line's own `\r` must not defeat the standalone-line match.
    body = "PR #63 merged with zero repairs.\r\nRetrospective status: zero-repair-fast-close\r\nRefs #63."
    assert checker.is_gate_less(body) is True


def test_is_gate_less_false_when_zero_repair_marker_only_quoted_mid_sentence() -> None:
    # Defeat case (issue #1297): this repo's own retrospectives routinely
    # re-quote an earlier issue's text verbatim inside a later, real
    # retrospective's Carried-forward section -- a bare substring match
    # would misclassify that later, real issue as gate-less merely for
    # quoting a fast-closed one.
    body = (
        "1. [Carried-forward] Issue #63 was fast-closed "
        "(`Retrospective status: zero-repair-fast-close`), but the real "
        "gate proposed in this cycle remains unimplemented.\n"
        "   Status: `missing-deterministic-gate`\n"
        "   Proposed gate: add a pre-push hook."
    )
    assert checker.is_gate_less(body) is False


# ---------------------------------------------------------------------------
# partition_gate_less (issue #1297)
# ---------------------------------------------------------------------------


def test_partition_gate_less_separates_matching_from_remaining() -> None:
    bodies = {
        118: "Automated stub opened by the post-merge-auto-retro gate.",
        187: "Retrospective status: zero-repair-fast-close",
        242: "1. [Repair] ... Status: `missing-deterministic-gate` Proposed gate: ...",
    }
    gate_less, remaining = checker.partition_gate_less([118, 187, 242], bodies)
    assert gate_less == [118, 187]
    assert remaining == [242]


def test_partition_gate_less_missing_body_treated_as_not_gate_less() -> None:
    # An issue number with no entry in the bodies mapping (caller supplied
    # no body for it) must not be silently excluded -- absence of evidence
    # is not evidence of gate-less-ness.
    gate_less, remaining = checker.partition_gate_less([999], {})
    assert gate_less == []
    assert remaining == [999]


def test_partition_gate_less_deduplicates_preserving_first_occurrence_order() -> None:
    bodies = {118: "Automated stub opened by the post-merge-auto-retro gate.", 242: "no marker here"}
    gate_less, remaining = checker.partition_gate_less([118, 242, 118, 242], bodies)
    assert gate_less == [118]
    assert remaining == [242]


# ---------------------------------------------------------------------------
# load_issue_bodies (issue #1297)
# ---------------------------------------------------------------------------


def test_load_issue_bodies_returns_empty_dict_when_path_is_none() -> None:
    assert checker.load_issue_bodies(None) == {}


def test_load_issue_bodies_reads_json_file(tmp_path: pathlib.Path) -> None:
    bodies_path = tmp_path / "bodies.json"
    bodies_path.write_text(json.dumps({"118": "Automated stub opened by the post-merge-auto-retro gate."}))
    assert checker.load_issue_bodies(str(bodies_path)) == {
        118: "Automated stub opened by the post-merge-auto-retro gate."
    }


def test_load_issue_bodies_reads_stdin_when_path_is_dash(monkeypatch: pytest.MonkeyPatch) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"242": "no marker here"})))
    assert checker.load_issue_bodies("-") == {242: "no marker here"}


def test_load_issue_bodies_skips_non_integer_keys(tmp_path: pathlib.Path) -> None:
    bodies_path = tmp_path / "bodies.json"
    bodies_path.write_text(json.dumps({"not-a-number": "text", "118": "real body"}))
    assert checker.load_issue_bodies(str(bodies_path)) == {118: "real body"}


def test_load_issue_bodies_skips_non_string_values(tmp_path: pathlib.Path) -> None:
    bodies_path = tmp_path / "bodies.json"
    bodies_path.write_text(json.dumps({"118": None, "242": 5, "999": "kept"}))
    assert checker.load_issue_bodies(str(bodies_path)) == {999: "kept"}


def test_load_issue_bodies_raises_on_missing_file() -> None:
    with pytest.raises(checker.BodiesInputError):
        checker.load_issue_bodies("/nonexistent/bodies.json")


def test_load_issue_bodies_raises_on_malformed_json(tmp_path: pathlib.Path) -> None:
    bodies_path = tmp_path / "bodies.json"
    bodies_path.write_text("{not valid json")
    with pytest.raises(checker.BodiesInputError):
        checker.load_issue_bodies(str(bodies_path))


def test_load_issue_bodies_raises_when_not_a_json_object(tmp_path: pathlib.Path) -> None:
    bodies_path = tmp_path / "bodies.json"
    bodies_path.write_text("[]")
    with pytest.raises(checker.BodiesInputError):
        checker.load_issue_bodies(str(bodies_path))


# ---------------------------------------------------------------------------
# partition_resolved
# ---------------------------------------------------------------------------


def test_partition_resolved_clears_when_citation_and_tracking_issue_both_present() -> None:
    messages = ["fix(gates): close gaps (Refs #650)"]
    unresolved, resolved = checker.partition_resolved([650], messages, {650})
    assert unresolved == []
    assert resolved == [650]


def test_partition_resolved_keeps_unresolved_when_citation_lacks_corroboration() -> None:
    # Defeat case mirroring the CI script's own #314 regression: a citing
    # commit exists, but no ssot.json gate was ever registered for it.
    unresolved, resolved = checker.partition_resolved([314], ["Refs #314"], set())
    assert unresolved == [314]
    assert resolved == []


def test_partition_resolved_keeps_unresolved_when_tracking_issue_present_but_no_citation() -> None:
    # Defeat case: the registry has a tracking_issue entry, but no commit
    # actually cites this issue number -- a bare-registry match alone must
    # not be sufficient either (both signals are required, not either).
    unresolved, resolved = checker.partition_resolved([702], ["chore: unrelated"], {702})
    assert unresolved == [702]
    assert resolved == []


def test_partition_resolved_keeps_unresolved_when_neither_signal_present() -> None:
    unresolved, resolved = checker.partition_resolved([999], ["chore: unrelated"], set())
    assert unresolved == [999]
    assert resolved == []


def test_partition_resolved_every_input_number_appears_in_exactly_one_array() -> None:
    issue_numbers = [1109, 1107, 1108, 1114]
    messages = ["Refs #1107", "Refs #1108", "Refs #1114"]
    tracking_issues = {1107, 1108, 1114}
    unresolved, resolved = checker.partition_resolved(issue_numbers, messages, tracking_issues)
    seen = sorted(unresolved) + sorted(resolved)
    assert sorted(seen) == sorted(issue_numbers)
    assert not (set(unresolved) & set(resolved))
    assert unresolved == [1109]
    assert sorted(resolved) == [1107, 1108, 1114]


def test_partition_resolved_handles_empty_issue_numbers() -> None:
    unresolved, resolved = checker.partition_resolved([], [], set())
    assert unresolved == []
    assert resolved == []


def test_partition_resolved_deduplicates_repeated_resolved_issue_number() -> None:
    # Defeat case: merge-retrospective/SKILL.md's own Step 1 builds the CLI
    # candidate list from two separate searches (a label search plus a
    # title-text fallback for pre-label issues) concatenated together --
    # an issue matching both would otherwise appear twice in "resolved".
    unresolved, resolved = checker.partition_resolved([650, 650], ["Refs #650"], {650})
    assert unresolved == []
    assert resolved == [650]


def test_partition_resolved_deduplicates_repeated_unresolved_issue_number() -> None:
    unresolved, resolved = checker.partition_resolved([999, 999], ["chore: unrelated"], set())
    assert unresolved == [999]
    assert resolved == []


def test_partition_resolved_deduplicates_while_preserving_first_occurrence_order() -> None:
    unresolved, resolved = checker.partition_resolved([650, 999, 650, 999], ["Refs #650"], {650})
    assert unresolved == [999]
    assert resolved == [650]


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
# load_gate_tracking_issues
# ---------------------------------------------------------------------------


def test_load_gate_tracking_issues_parses_ints_and_skips_null_or_missing(tmp_path: pathlib.Path) -> None:
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


def test_load_gate_tracking_issues_raises_on_missing_file(tmp_path: pathlib.Path) -> None:
    with pytest.raises(checker.SsotLedgerError):
        checker.load_gate_tracking_issues(str(tmp_path / "nonexistent.json"))


def test_load_gate_tracking_issues_raises_on_malformed_json(tmp_path: pathlib.Path) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text("{not valid json")
    with pytest.raises(checker.SsotLedgerError):
        checker.load_gate_tracking_issues(str(ssot))


def test_load_gate_tracking_issues_raises_when_not_a_json_object(tmp_path: pathlib.Path) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text("[]")
    with pytest.raises(checker.SsotLedgerError):
        checker.load_gate_tracking_issues(str(ssot))


def test_load_gate_tracking_issues_raises_when_gates_list_missing_or_empty(tmp_path: pathlib.Path) -> None:
    ssot = tmp_path / "ssot.json"
    ssot.write_text(json.dumps({"gates": []}))
    with pytest.raises(checker.SsotLedgerError):
        checker.load_gate_tracking_issues(str(ssot))


def test_load_gate_tracking_issues_excludes_non_int_and_bool_values(tmp_path: pathlib.Path) -> None:
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
                    {"id": "f", "tracking_issue": 650},
                ]
            }
        )
    )
    assert checker.load_gate_tracking_issues(str(ssot)) == {650}


def test_load_gate_tracking_issues_flattens_list_values(tmp_path: pathlib.Path) -> None:
    # Issue #1425: a gate legitimately tracked under more than one issue
    # (a shared umbrella issue plus the issue whose repair actually
    # implemented it) stores tracking_issue as a list -- every int in it
    # corroborates, and non-int/bool entries within the list are excluded
    # the same as a bare scalar value would be.
    ssot = tmp_path / "ssot.json"
    ssot.write_text(
        json.dumps(
            {
                "gates": [
                    {"id": "a", "tracking_issue": [520, 350]},
                    {"id": "b", "tracking_issue": [297, 422, 426]},
                    {"id": "c", "tracking_issue": [650, True, "297", 297.0]},
                    {"id": "d", "tracking_issue": 999},
                ]
            }
        )
    )
    assert checker.load_gate_tracking_issues(str(ssot)) == {520, 350, 297, 422, 426, 650, 999}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_prints_json_partition_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(checker, "git_commit_messages", lambda *a, **k: ["Refs #1107"])
    monkeypatch.setattr(checker, "load_gate_tracking_issues", lambda *a, **k: {1107})
    exit_code = checker.main(["1109", "1107"])
    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"unresolved": [1109], "resolved": [1107], "gate_less": []}


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

    def raise_ssot_error(*a: object, **k: object) -> set[int]:
        raise checker.SsotLedgerError("boom")

    monkeypatch.setattr(checker, "load_gate_tracking_issues", raise_ssot_error)
    exit_code = checker.main(["1"])
    assert exit_code == 1
    assert "boom" in capsys.readouterr().err


def test_main_passes_default_ssot_path_joined_with_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    received: dict[str, str] = {}

    def fake_load(path: str) -> set[int]:
        received["path"] = path
        return set()

    monkeypatch.setattr(checker, "git_commit_messages", lambda *a, **k: [])
    monkeypatch.setattr(checker, "load_gate_tracking_issues", fake_load)
    checker.main(["1", "--cwd", "/repo"])
    assert received["path"] == str(pathlib.Path("/repo") / ".gitapex/ssot.json")


def test_main_requires_at_least_one_issue_number() -> None:
    with pytest.raises(SystemExit):
        checker.main([])


def test_main_output_has_empty_gate_less_when_bodies_omitted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Backward-compat: no --bodies means every candidate flows through the
    # existing two-signal check exactly as before this batch.
    monkeypatch.setattr(checker, "git_commit_messages", lambda *a, **k: ["Refs #1107"])
    monkeypatch.setattr(checker, "load_gate_tracking_issues", lambda *a, **k: {1107})
    exit_code = checker.main(["1109", "1107"])
    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"unresolved": [1109], "resolved": [1107], "gate_less": []}


def test_main_excludes_gate_less_issue_from_unresolved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bodies_path = tmp_path / "bodies.json"
    bodies_path.write_text(json.dumps({"118": "Automated stub opened by the post-merge-auto-retro gate."}))
    monkeypatch.setattr(checker, "git_commit_messages", lambda *a, **k: [])
    monkeypatch.setattr(checker, "load_gate_tracking_issues", lambda *a, **k: set())
    exit_code = checker.main(["118", "242", "--bodies", str(bodies_path)])
    assert exit_code == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"unresolved": [242], "resolved": [], "gate_less": [118]}


def test_main_exits_one_on_bodies_input_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(checker, "git_commit_messages", lambda *a, **k: [])
    monkeypatch.setattr(checker, "load_gate_tracking_issues", lambda *a, **k: set())
    exit_code = checker.main(["1", "--bodies", "/nonexistent/bodies.json"])
    assert exit_code == 1
    assert "error:" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Marker drift gate (issue #1297): _CI_STUB_MARKER and _ZERO_REPAIR_MARKER
# are literal copies of two canonical sources, not imports (this repo keeps
# skill-bundled and .github/scripts/*.py files independent of one another)
# -- assert directly against those sources' own text so the two cannot
# silently re-diverge the way the title/query pair did before #341, per
# tests/test_gitapex_stale_retro_stub_autoclose.py's own
# test_stub_marker_matches_post_merge_retro_source precedent for the
# identical drift risk on the CI-stub marker half of this pair.
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def test_ci_stub_marker_matches_post_merge_retro_source() -> None:
    source = (REPO_ROOT / ".github" / "scripts" / "gitapex_post_merge_retro.py").read_text(encoding="utf-8")
    assert checker._CI_STUB_MARKER in source


def test_zero_repair_marker_matches_skill_md_source() -> None:
    source = (REPO_ROOT / "skills" / "merge-retrospective" / "SKILL.md").read_text(encoding="utf-8")
    assert checker._ZERO_REPAIR_MARKER in source
