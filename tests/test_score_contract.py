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


def test_string_valued_assertion_raises_value_error():
    # a bare string instead of a list must fail loudly, not be scored
    # per-character (which would silently miscount)
    with pytest.raises(ValueError):
        score_contract.score("the L G T M report", {"output_contains": "LGTM"})


def test_non_dict_assertions_raises_value_error():
    with pytest.raises(ValueError):
        score_contract.score("anything", ["output_contains", "Facts"])


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


def test_pruning_compare_keeps_matched_correctness_with_lower_context_cost():
    assert score_contract.pruning_compare(0.9, 0.9, 1400, 1120) == "KEEP"


def test_pruning_compare_uses_the_cli_published_correctness_precision():
    recomputed_same_scores = 0.9398148333333333
    assert (
        score_contract.pruning_compare(
            0.939815,
            recomputed_same_scores,
            1400,
            1120,
        )
        == "KEEP"
    )
    assert score_contract.strict_compare(0.939815, recomputed_same_scores) == "REJECT"


def test_pruning_compare_rejects_regression_beyond_published_precision():
    assert score_contract.pruning_compare(0.939815, 0.9398144, 1400, 1) == "REJECT"


def test_pruning_compare_rejects_an_unpublished_prior_precision():
    with pytest.raises(ValueError, match="published six-decimal precision"):
        score_contract.pruning_compare(0.9000004, 0.9, 100, 99)


def test_pruning_compare_rejects_correctness_regression_even_if_context_falls():
    assert score_contract.pruning_compare(0.9, 0.8, 1400, 1) == "REJECT"


def test_pruning_compare_rejects_matched_correctness_without_strict_cost_drop():
    assert score_contract.pruning_compare(0.9, 0.9, 1400, 1400) == "REJECT"
    assert score_contract.pruning_compare(0.9, 0.9, 1400, 1500) == "REJECT"


def test_ordinary_scalar_tie_remains_rejected():
    assert score_contract.strict_compare(0.9, 0.9) == "REJECT"


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -0.01, 1.01])
def test_strict_compare_rejects_invalid_correctness(invalid):
    with pytest.raises(ValueError, match=r"finite number in \[0,1\]"):
        score_contract.strict_compare(invalid, 0.9)
    with pytest.raises(ValueError, match=r"finite number in \[0,1\]"):
        score_contract.strict_compare(0.9, invalid)


def test_correctness_validators_reject_booleans():
    with pytest.raises(ValueError, match=r"finite number in \[0,1\]"):
        score_contract.strict_compare(False, 0.9)
    with pytest.raises(ValueError, match=r"finite number in \[0,1\]"):
        score_contract.split_mean([0.9, True])


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -1])
def test_pruning_compare_rejects_invalid_context_cost(invalid):
    with pytest.raises(ValueError, match="finite non-negative"):
        score_contract.pruning_compare(0.9, 0.9, invalid, 100)
    with pytest.raises(ValueError, match="finite non-negative"):
        score_contract.pruning_compare(0.9, 0.9, 100, invalid)


def test_context_cost_validator_rejects_booleans():
    with pytest.raises(ValueError, match="finite non-negative"):
        score_contract.pruning_compare(0.9, 0.9, False, 100)
    with pytest.raises(ValueError, match="finite non-negative"):
        score_contract.pruning_compare(0.9, 0.9, 100, True)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -0.01, 1.01])
def test_pruning_compare_rejects_invalid_correctness(invalid):
    with pytest.raises(ValueError, match=r"finite number in \[0,1\]"):
        score_contract.pruning_compare(invalid, 0.9, 100, 90)
    with pytest.raises(ValueError, match=r"finite number in \[0,1\]"):
        score_contract.pruning_compare(0.9, invalid, 100, 90)


def test_split_mean_rejects_non_finite_and_out_of_range_correctness():
    for invalid in (float("nan"), float("inf"), -0.01, 1.01):
        with pytest.raises(ValueError, match=r"finite number in \[0,1\]"):
            score_contract.split_mean([0.9, invalid])


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


def test_main_pruning_gate_keeps_matched_correctness_with_lower_cost(
    tmp_path, capsys
):
    scores = tmp_path / "scores.txt"
    scores.write_text("0.9\n0.9\n", encoding="utf-8")
    rc = score_contract.main(
        [
            "--compare-to",
            "0.9",
            "--scores",
            str(scores),
            "--pruning-only",
            "--prior-context-cost",
            "1400",
            "--candidate-context-cost",
            "1120",
        ]
    )
    assert rc == 0
    assert capsys.readouterr().out.strip() == "0.900000 KEEP"


def test_main_rejects_context_costs_without_pruning_declaration(capsys):
    rc = score_contract.main(
        ["--compare-to", "0.9", "--prior-context-cost", "1400"]
    )
    assert rc == 1
    assert "require --pruning-only" in capsys.readouterr().err


def test_main_judge_agree_appends_agree_marker(tmp_path, capsys):
    scores = tmp_path / "scores.txt"
    scores.write_text("0.9\n1.0\n", encoding="utf-8")
    rc = score_contract.main(
        ["--compare-to", "0.9", "--scores", str(scores), "--judge-verdict", "agree"]
    )
    assert rc == 0
    assert capsys.readouterr().out.strip() == "0.950000 KEEP JUDGE_AGREE"


def test_main_judge_disagree_appends_review_required_marker(tmp_path, capsys):
    scores = tmp_path / "scores.txt"
    scores.write_text("0.9\n1.0\n", encoding="utf-8")
    rc = score_contract.main(
        ["--compare-to", "0.9", "--scores", str(scores), "--judge-verdict", "disagree"]
    )
    assert rc == 0
    assert (
        capsys.readouterr().out.strip()
        == "0.950000 KEEP JUDGE_DISAGREE_REVIEW_REQUIRED"
    )


def test_main_judge_agree_on_reject_path_does_not_override_verdict(tmp_path, capsys):
    # 0.95 < 0.99 -> REJECT; a judge "agree" must never flip this to KEEP.
    # This is the exact override Decision 1 forbids -- caught by mutation
    # testing during adversarial verification of gitapex#175.
    scores = tmp_path / "scores.txt"
    scores.write_text("0.9\n1.0\n", encoding="utf-8")
    rc = score_contract.main(
        ["--compare-to", "0.99", "--scores", str(scores), "--judge-verdict", "agree"]
    )
    assert rc == 0
    assert capsys.readouterr().out.strip() == "0.950000 REJECT JUDGE_AGREE"


def test_main_judge_disagree_on_reject_path_appends_review_required_marker(
    tmp_path, capsys
):
    scores = tmp_path / "scores.txt"
    scores.write_text("0.9\n1.0\n", encoding="utf-8")
    rc = score_contract.main(
        ["--compare-to", "0.99", "--scores", str(scores), "--judge-verdict", "disagree"]
    )
    assert rc == 0
    assert (
        capsys.readouterr().out.strip()
        == "0.950000 REJECT JUDGE_DISAGREE_REVIEW_REQUIRED"
    )


@pytest.mark.parametrize("compare_to,gate_verdict", [("0.9", "KEEP"), ("0.99", "REJECT")])
@pytest.mark.parametrize("judge_verdict", ["agree", "disagree"])
def test_main_judge_verdict_never_changes_recorded_mean_or_verdict(
    tmp_path, capsys, compare_to, gate_verdict, judge_verdict
):
    scores = tmp_path / "scores.txt"
    scores.write_text("0.9\n1.0\n", encoding="utf-8")
    rc_plain = score_contract.main(["--compare-to", compare_to, "--scores", str(scores)])
    plain = capsys.readouterr().out.strip()
    assert plain == f"0.950000 {gate_verdict}"
    rc_judged = score_contract.main(
        ["--compare-to", compare_to, "--scores", str(scores), "--judge-verdict", judge_verdict]
    )
    judged = capsys.readouterr().out.strip()
    assert rc_plain == rc_judged == 0
    assert judged.startswith(plain + " ")
    assert judged != plain


def test_main_rejects_judge_verdict_without_compare_to(capsys):
    rc = score_contract.main(["--judge-verdict", "agree"])
    assert rc == 1
    assert "--judge-verdict requires --compare-to" in capsys.readouterr().err


def test_main_rejects_judge_verdict_with_pruning_only(tmp_path, capsys):
    scores = tmp_path / "scores.txt"
    scores.write_text("0.9\n0.9\n", encoding="utf-8")
    rc = score_contract.main(
        [
            "--compare-to",
            "0.9",
            "--scores",
            str(scores),
            "--judge-verdict",
            "agree",
            "--pruning-only",
            "--prior-context-cost",
            "1400",
            "--candidate-context-cost",
            "1120",
        ]
    )
    assert rc == 1
    assert "not defined for --pruning-only" in capsys.readouterr().err


@pytest.mark.parametrize("invalid", ["nan", "inf", "-0.1", "1.1"])
def test_main_rejects_invalid_correctness_scores(tmp_path, capsys, invalid):
    scores = tmp_path / "scores.txt"
    scores.write_text(f"0.9\n{invalid}\n", encoding="utf-8")
    rc = score_contract.main(
        ["--compare-to", "0.9", "--scores", str(scores)]
    )
    assert rc == 1
    assert "finite number in [0,1]" in capsys.readouterr().err


@pytest.mark.parametrize("invalid", ["nan", "inf", "-0.1", "1.1"])
def test_main_rejects_invalid_prior_correctness(tmp_path, capsys, invalid):
    scores = tmp_path / "scores.txt"
    scores.write_text("0.9\n", encoding="utf-8")
    rc = score_contract.main(
        ["--compare-to", invalid, "--scores", str(scores)]
    )
    assert rc == 1
    assert "finite number in [0,1]" in capsys.readouterr().err


@pytest.mark.parametrize("invalid", ["nan", "inf"])
def test_main_rejects_non_finite_context_costs(tmp_path, capsys, invalid):
    scores = tmp_path / "scores.txt"
    scores.write_text("0.9\n", encoding="utf-8")
    rc = score_contract.main(
        [
            "--compare-to",
            "0.9",
            "--scores",
            str(scores),
            "--pruning-only",
            "--prior-context-cost",
            invalid,
            "--candidate-context-cost",
            "100",
        ]
    )
    assert rc == 1
    assert "finite non-negative" in capsys.readouterr().err
