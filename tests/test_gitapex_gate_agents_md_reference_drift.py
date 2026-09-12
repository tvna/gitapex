"""Unit tests for `.github/scripts/gitapex_gate_agents_md_reference_drift.py`.

Issue #1963 (ACM row 6). Several cases are built to DEFEAT the gate's own
detection logic rather than to exercise its happy path:

- a hyphenated identifier inside a fenced code block, which is sample
  text and must not be graded as a reference the file is making;
- a hyphen-free code span (`catch`), which is prose and must be skipped
  without an allowlist naming it;
- a renamed skill, the exact drift this gate exists to catch, asserted to
  FAIL rather than to be quietly tolerated;
- every path where the gate cannot evaluate its inputs, each asserted to
  exit 2 rather than pass silently.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))

import gitapex_gate_agents_md_reference_drift as gate  # noqa: E402


def _write_repo(
    tmp_path: pathlib.Path,
    *,
    agents_md: str,
    skills: tuple[str, ...] = (),
    gate_ids: tuple[str, ...] = (),
) -> pathlib.Path:
    (tmp_path / "AGENTS.md").write_text(agents_md, encoding="utf-8")
    for name in skills:
        (tmp_path / "skills" / name).mkdir(parents=True, exist_ok=True)
        (tmp_path / "skills" / name / "SKILL.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "skills").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".gitapex").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".gitapex" / "ssot.json").write_text(
        json.dumps({"gates": [{"id": gate_id} for gate_id in gate_ids]}), encoding="utf-8"
    )
    return tmp_path


# --- which tokens are checked -----------------------------------------


def test_a_skill_name_resolves(tmp_path: pathlib.Path) -> None:
    repo = _write_repo(tmp_path, agents_md="see `drafting-issues`\n", skills=("drafting-issues",))
    assert gate.evaluate(repo) == [
        ("drafting-issues", True, "resolves to skills/drafting-issues/SKILL.md"),
    ]


def test_a_gate_id_resolves(tmp_path: pathlib.Path) -> None:
    repo = _write_repo(tmp_path, agents_md="backed by `except-fail-open`\n", gate_ids=("except-fail-open",))
    assert gate.evaluate(repo)[0][1] is True


def test_a_renamed_skill_fails(tmp_path: pathlib.Path) -> None:
    """The drift this gate exists to catch: the prose still names the old
    identifier after the directory was renamed."""
    repo = _write_repo(tmp_path, agents_md="see `drafting-issues`\n", skills=("drafting-an-issue",))
    assert gate.evaluate(repo) == [
        ("drafting-issues", False, "resolves to no skill and no gate id"),
    ]


def test_a_hyphen_free_span_is_not_a_reference() -> None:
    """DEFEAT CASE: `catch` is a language keyword AGENTS.md backticks as
    prose. It must be skipped by shape, with no allowlist naming it."""
    assert gate.referenced_identifiers("never a silent `catch`\n") == []


def test_a_fenced_identifier_is_not_a_reference() -> None:
    """DEFEAT CASE: a hyphenated identifier inside a fenced block is sample
    text. Grading it would flag an example the file never claimed as a
    live reference."""
    text = "prose `real-skill`\n\n```\nrun `sample-skill` here\n```\n\nmore prose\n"
    assert gate.referenced_identifiers(text) == ["real-skill"]


def test_a_tilde_fence_is_also_stripped() -> None:
    text = "`real-skill`\n\n~~~\n`sample-skill`\n~~~\n"
    assert gate.referenced_identifiers(text) == ["real-skill"]


def test_an_unterminated_fence_swallows_the_rest() -> None:
    """An unclosed fence means everything after it is inside a block; the
    conservative reading is to grade none of it, not to guess where the
    author meant it to end."""
    assert gate.referenced_identifiers("`a-skill`\n\n```\n`b-skill`\n") == ["a-skill"]


def test_a_span_cannot_straddle_a_newline() -> None:
    assert gate.referenced_identifiers("`a-\nskill`\n") == []


def test_duplicates_are_reported_once_in_first_appearance_order() -> None:
    assert gate.referenced_identifiers("`b-two` `a-one` `b-two`\n") == ["b-two", "a-one"]


@pytest.mark.parametrize(
    "token",
    ["UPPER-CASE", "trailing-", "-leading", "no_underscore-ok", "a b-c"],
)
def test_tokens_outside_the_identifier_shape_are_skipped(token: str) -> None:
    assert gate.referenced_identifiers(f"`{token}`\n") == []


# --- unrunnable paths all exit 2, never a silent pass ------------------


def test_missing_agents_md_is_unrunnable(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gate.GateUnrunnable, match=r"cannot read AGENTS\.md"):
        gate.evaluate(tmp_path)


def test_undecodable_agents_md_is_unrunnable(tmp_path: pathlib.Path) -> None:
    (tmp_path / "AGENTS.md").write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(gate.GateUnrunnable, match=r"cannot read AGENTS\.md"):
        gate.evaluate(tmp_path)


def test_missing_ssot_is_unrunnable(tmp_path: pathlib.Path) -> None:
    (tmp_path / "AGENTS.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "skills").mkdir()
    with pytest.raises(gate.GateUnrunnable, match="cannot read"):
        gate.evaluate(tmp_path)


def test_malformed_ssot_is_unrunnable(tmp_path: pathlib.Path) -> None:
    repo = _write_repo(tmp_path, agents_md="x\n")
    (repo / ".gitapex" / "ssot.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(gate.GateUnrunnable, match="cannot parse"):
        gate.known_gate_ids(repo)


def test_ssot_without_a_gates_list_is_unrunnable(tmp_path: pathlib.Path) -> None:
    """DEFEAT CASE: a registry whose `gates` key is present but not a list
    would otherwise yield an empty id set, turning every gate reference
    into a false FAIL instead of an honest 'cannot evaluate'."""
    repo = _write_repo(tmp_path, agents_md="x\n")
    (repo / ".gitapex" / "ssot.json").write_text('{"gates": {}}', encoding="utf-8")
    with pytest.raises(gate.GateUnrunnable, match="no gates"):
        gate.known_gate_ids(repo)


def test_gate_entries_without_a_string_id_are_ignored(tmp_path: pathlib.Path) -> None:
    repo = _write_repo(tmp_path, agents_md="x\n")
    (repo / ".gitapex" / "ssot.json").write_text('{"gates": [{"id": 7}, "str", {"id": "ok-id"}]}', encoding="utf-8")
    assert gate.known_gate_ids(repo) == {"ok-id"}


def test_missing_skills_dir_is_unrunnable(tmp_path: pathlib.Path) -> None:
    (tmp_path / "AGENTS.md").write_text("x\n", encoding="utf-8")
    with pytest.raises(gate.GateUnrunnable, match="not a directory"):
        gate.known_skill_names(tmp_path)


def test_a_skills_subdir_without_skill_md_is_not_a_skill(tmp_path: pathlib.Path) -> None:
    repo = _write_repo(tmp_path, agents_md="x\n")
    (repo / "skills" / "not-a-skill").mkdir()
    assert gate.known_skill_names(repo) == set()


# --- CLI ---------------------------------------------------------------


def test_main_returns_0_when_everything_resolves(tmp_path: pathlib.Path) -> None:
    repo = _write_repo(tmp_path, agents_md="`a-skill`\n", skills=("a-skill",))
    assert gate.main(["--repo-root", str(repo)]) == 0


def test_main_returns_1_on_a_dangling_reference(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _write_repo(tmp_path, agents_md="`a-skill`\n")
    assert gate.main(["--repo-root", str(repo)]) == 1
    assert "do not resolve" in capsys.readouterr().out


def test_main_returns_2_when_unrunnable(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--repo-root", str(tmp_path)]) == 2
    assert "ERROR" in capsys.readouterr().err


def test_the_real_repository_passes() -> None:
    """The live check ACM row 6's proof method names: every backticked
    reference in this repository's own AGENTS.md must resolve today."""
    assert gate.main(["--repo-root", str(REPO_ROOT)]) == 0


def test_a_non_object_ssot_payload_is_unrunnable(tmp_path: pathlib.Path) -> None:
    """DEFEAT CASE: `[]`, `"x"`, `1` and `null` are all valid JSON. Calling
    .get() on one raises AttributeError, which would escape as a crash
    rather than this gate's own typed 'cannot evaluate'."""
    repo = _write_repo(tmp_path, agents_md="x\n")
    (repo / ".gitapex" / "ssot.json").write_text("[]", encoding="utf-8")
    with pytest.raises(gate.GateUnrunnable, match="not an object"):
        gate.known_gate_ids(repo)
