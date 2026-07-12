"""Tests for the deterministic substring-contract scorer (gitapex#30)."""

import json

import pytest

import score_contract


def test_all_contains_present_scores_one():
    assertions = {"output_contains": ["Facts", "Next Move"]}
    assert score_contract.score("Facts ... Next Move", assertions) == 1.0


def test_no_contains_present_scores_zero():
    assertions = {"output_contains": ["Facts", "Next Move"]}
    assert score_contract.score("nothing relevant here", assertions) == 0.0


def test_partial_contains_scores_fraction():
    assertions = {"output_contains": ["Facts", "Next Move", "Branch Plan", "Output"]}
    # one of four present
    assert score_contract.score("only Facts here", assertions) == 0.25


def test_not_contains_satisfied_when_absent():
    assertions = {"output_not_contains": ["LGTM"]}
    assert score_contract.score("a careful review", assertions) == 1.0


def test_not_contains_violated_when_present():
    assertions = {"output_not_contains": ["LGTM"]}
    assert score_contract.score("LGTM ship it", assertions) == 0.0


def test_mixed_contains_and_not_contains():
    assertions = {
        "output_contains": ["Facts", "Next Move"],
        "output_not_contains": ["LGTM"],
    }
    # Facts present (1), Next Move absent (0), LGTM absent -> satisfied (1) => 2/3
    assert score_contract.score("Facts only, no verdict", assertions) == pytest.approx(2 / 3)


def test_missing_keys_treated_as_empty_lists():
    # only output_contains given; no output_not_contains key at all
    assertions = {"output_contains": ["Facts"]}
    assert score_contract.score("Facts", assertions) == 1.0


def test_none_valued_keys_treated_as_empty():
    assertions = {"output_contains": ["Facts"], "output_not_contains": None}
    assert score_contract.score("Facts", assertions) == 1.0


def test_empty_assertion_set_raises_value_error():
    with pytest.raises(ValueError):
        score_contract.score("anything", {})


def test_empty_assertion_lists_raise_value_error():
    with pytest.raises(ValueError):
        score_contract.score("anything", {"output_contains": [], "output_not_contains": []})


def test_none_output_treated_as_empty_string():
    assertions = {
        "output_contains": ["Facts"],
        "output_not_contains": ["LGTM"],
    }
    # None output: Facts absent (0), LGTM absent -> satisfied (1) => 1/2
    assert score_contract.score(None, assertions) == 0.5


def test_deterministic_same_inputs_same_output():
    assertions = {"output_contains": ["Facts"], "output_not_contains": ["LGTM"]}
    first = score_contract.score("Facts and no verdict", assertions)
    second = score_contract.score("Facts and no verdict", assertions)
    assert first == second == 1.0


def test_main_scores_assertions_json_and_output_file(tmp_path, capsys):
    apath = tmp_path / "assertions.json"
    apath.write_text(json.dumps({"output_contains": ["Facts"], "output_not_contains": ["LGTM"]}), encoding="utf-8")
    opath = tmp_path / "run.txt"
    opath.write_text("Facts and no verdict", encoding="utf-8")
    rc = score_contract.main(["--assertions", str(apath), "--output", str(opath)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "1.000000"


def test_main_reads_output_from_stdin(tmp_path, capsys, monkeypatch):
    apath = tmp_path / "assertions.json"
    apath.write_text(json.dumps({"output_contains": ["Facts", "Missing"]}), encoding="utf-8")
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("only Facts"))
    rc = score_contract.main(["--assertions", str(apath)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "0.500000"
