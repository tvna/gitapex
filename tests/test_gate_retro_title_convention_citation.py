"""Tests for the retro title convention citation gate
(.github/scripts/gate_retro_title_convention_citation.py).

Issue #520 (row 1, refs #344): a file asserting a title/identity string is
"this repo's own convention" must cite a real, resolvable issue number as
evidence in the same file.

No test in this file makes a real network call -- the network layer is
exercised through an injected `opener`, mirroring test_gate_acm_issue_disclosure.py's
own fixture style.
"""

from __future__ import annotations

import io
import json

import gate_retro_title_convention_citation as gate
import pytest

_UNCITED_TITLE_CLAIM = (
    "The retro-identity.toml spec's title_pattern matches 'Merge retrospective: "
    "PR #N', which is this repository's established convention for the title.\n"
)

_CITED_TITLE_CLAIM = (
    "Refs #341.\n\n"
    "The retro-identity.toml spec's title_pattern matches 'chore(retrospective): "
    "merge retrospective for PR #N', this repository's actual convention for "
    "the title, corrected per #341.\n"
)

_UNRELATED_CONVENTION_CLAIM = (
    "Default to no em dashes or curly quotes -- gitapex's own convention, "
    "this repository's own established convention for character-set policy.\n"
)


class Response:
    def __init__(self, status: int, body: str = "") -> None:
        self.status = status
        self.body = body.encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body


def test_find_offending_paragraphs_flags_title_claim():
    assert len(gate.find_offending_paragraphs(_UNCITED_TITLE_CLAIM)) == 1


def test_find_offending_paragraphs_ignores_unrelated_convention_claim():
    assert gate.find_offending_paragraphs(_UNRELATED_CONVENTION_CLAIM) == []


def test_find_offending_paragraphs_ignores_plain_prose():
    assert gate.find_offending_paragraphs("Nothing to see here.\n") == []


def test_find_offending_paragraphs_matches_compound_modifier():
    text = "this repository's own, long-established convention for the title"
    assert len(gate.find_offending_paragraphs(text)) == 1


def test_find_offending_paragraphs_matches_extra_qualifier_word():
    text = "this repository's own established naming convention for retrospective titles"
    assert len(gate.find_offending_paragraphs(text)) == 1


def test_cited_issue_numbers_dedupes_in_order():
    text = "Refs #341, #342, and #341 again."
    assert gate.cited_issue_numbers(text) == [341, 342]


def test_cited_issue_numbers_respects_digit_boundary():
    # "#3410" and "#12341" must not be mistaken for a citation of #341.
    text = "See #3410 and #12341, neither is #341."
    assert gate.cited_issue_numbers(text) == [3410, 12341, 341]


def test_has_citation():
    assert gate.has_citation("Refs #341.") is True
    assert gate.has_citation("No citation here.") is False


def test_check_only_passes_when_no_offending_paragraph(tmp_path, capsys):
    path = tmp_path / "doc.md"
    path.write_text(_UNRELATED_CONVENTION_CLAIM, encoding="utf-8")
    exit_code = gate.main(["--check-only", str(path)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_check_only_passes_when_cited(tmp_path, capsys):
    path = tmp_path / "doc.md"
    path.write_text(_CITED_TITLE_CLAIM, encoding="utf-8")
    exit_code = gate.main(["--check-only", str(path)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_check_only_fails_when_uncited(tmp_path, capsys):
    path = tmp_path / "doc.md"
    path.write_text(_UNCITED_TITLE_CLAIM, encoding="utf-8")
    exit_code = gate.main(["--check-only", str(path)])
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().err


def test_check_only_missing_file_errors(tmp_path, capsys):
    exit_code = gate.main(["--check-only", str(tmp_path / "missing.md")])
    assert exit_code == 1
    assert "error" in capsys.readouterr().err


def test_full_mode_requires_owner_repo(tmp_path, capsys):
    path = tmp_path / "doc.md"
    path.write_text(_CITED_TITLE_CLAIM, encoding="utf-8")
    exit_code = gate.main([str(path)])
    assert exit_code == 1
    assert "--owner and --repo are required" in capsys.readouterr().err


def test_full_mode_requires_token(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    path = tmp_path / "doc.md"
    path.write_text(_CITED_TITLE_CLAIM, encoding="utf-8")
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", str(path)])
    assert exit_code == 1
    assert "GITHUB_TOKEN" in capsys.readouterr().err


def test_is_resolvable_issue_true_on_200():
    opener = lambda request: Response(200, json.dumps({"number": 341}))  # noqa: E731
    assert gate.is_resolvable_issue("tvna", "gitapex", 341, "tok", opener=opener, sleeper=lambda s: None) is True


def test_is_resolvable_issue_false_on_404():
    opener = lambda request: Response(404, "{}")  # noqa: E731
    assert gate.is_resolvable_issue("tvna", "gitapex", 999999, "tok", opener=opener, sleeper=lambda s: None) is False


def test_is_resolvable_issue_retries_then_raises_on_5xx():
    calls = {"n": 0}

    def opener(request):
        calls["n"] += 1
        raise __import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
            request.full_url, 500, "boom", None, io.BytesIO(b"{}")
        )

    with pytest.raises(gate.GitHubApiError):
        gate.is_resolvable_issue("tvna", "gitapex", 341, "tok", opener=opener, sleeper=lambda s: None)
    assert calls["n"] == 3


def test_find_unresolvable_offenders_none_when_not_offending(tmp_path):
    opener = lambda request: Response(200, "{}")  # noqa: E731
    result = gate.find_unresolvable_offenders(
        tmp_path / "doc.md",
        _UNRELATED_CONVENTION_CLAIM,
        "tvna",
        "gitapex",
        "tok",
        opener=opener,
        sleeper=lambda s: None,
    )
    assert result is None


def test_find_unresolvable_offenders_none_when_no_citation(tmp_path):
    result = gate.find_unresolvable_offenders(
        tmp_path / "doc.md",
        _UNCITED_TITLE_CLAIM,
        "tvna",
        "gitapex",
        "tok",
        opener=lambda request: Response(200, "{}"),
        sleeper=lambda s: None,
    )
    assert result is not None
    assert "no #<number> citation" in result


def test_find_unresolvable_offenders_resolvable_passes(tmp_path):
    opener = lambda request: Response(200, json.dumps({"number": 341}))  # noqa: E731
    result = gate.find_unresolvable_offenders(
        tmp_path / "doc.md",
        _CITED_TITLE_CLAIM,
        "tvna",
        "gitapex",
        "tok",
        opener=opener,
        sleeper=lambda s: None,
    )
    assert result is None


def test_find_unresolvable_offenders_unresolvable_fails(tmp_path):
    opener = lambda request: Response(404, "{}")  # noqa: E731
    result = gate.find_unresolvable_offenders(
        tmp_path / "doc.md",
        _CITED_TITLE_CLAIM,
        "tvna",
        "gitapex",
        "tok",
        opener=opener,
        sleeper=lambda s: None,
    )
    assert result is not None
    assert "none resolve" in result


def test_check_only_end_to_end_pass_does_not_touch_network(tmp_path, capsys):
    path = tmp_path / "doc.md"
    path.write_text(_CITED_TITLE_CLAIM, encoding="utf-8")
    exit_code = gate.main(["--check-only", str(path)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_full_mode_end_to_end_pass(tmp_path, monkeypatch, capsys):
    # main()'s full mode forwards to find_unresolvable_offenders with no
    # injected opener, so it always resolves to the real _default_opener.
    # Unlike _default_opener itself (a default *argument value*, bound once
    # at function-definition time -- monkeypatching the module-level name
    # afterward never reaches an already-bound default), _default_opener's
    # own body looks up urllib.request.urlopen fresh on every call, so
    # patching that attribute IS the correct seam for exercising main()'s
    # full-mode wiring end to end without a real network call.
    path = tmp_path / "doc.md"
    path.write_text(_CITED_TITLE_CLAIM, encoding="utf-8")
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(
        gate.urllib.request, "urlopen", lambda request, timeout=None: Response(200, json.dumps({"number": 341}))
    )
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", str(path)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_full_mode_end_to_end_fail(tmp_path, monkeypatch, capsys):
    path = tmp_path / "doc.md"
    path.write_text(_UNCITED_TITLE_CLAIM, encoding="utf-8")
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(gate.urllib.request, "urlopen", lambda request, timeout=None: Response(200, "{}"))
    exit_code = gate.main(["--owner", "tvna", "--repo", "gitapex", str(path)])
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().err
