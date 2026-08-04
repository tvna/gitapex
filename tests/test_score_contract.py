"""Tests for the deterministic substring-contract scorer (gitapex#30)."""

import json

import pytest
import score_contract
from conftest import FakeStdin as _FakeStdin


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


# ---------------------------------------------------------------------------
# output_contains_near (issue #328's fix to gitapex#312)
# ---------------------------------------------------------------------------


def test_near_satisfied_when_both_substrings_close_together():
    assertions = {"output_contains_near": [{"all": ["mypy", "missing deterministic gate"], "window": 60}]}
    assert score_contract.score("mypy failure: missing deterministic gate.", assertions) == 1.0


def test_near_unsatisfied_when_one_substring_missing():
    assertions = {"output_contains_near": [{"all": ["mypy", "missing deterministic gate"], "window": 60}]}
    assert score_contract.score("only mypy is mentioned here, nothing else.", assertions) == 0.0


def test_near_unsatisfied_when_substrings_too_far_apart():
    assertions = {"output_contains_near": [{"all": ["mypy", "missing deterministic gate"], "window": 20}]}
    far_apart = "mypy failure happened. " + ("padding " * 10) + "Classification: missing deterministic gate."
    assert score_contract.score(far_apart, assertions) == 0.0


def test_near_defaults_to_400_char_window_when_omitted():
    assertions = {"output_contains_near": [{"all": ["A", "B"]}]}
    assert score_contract.score("A" + ("x" * 350) + "B", assertions) == 1.0
    assert score_contract.score("A" + ("x" * 450) + "B", assertions) == 0.0


def test_near_unsatisfied_across_a_blank_line_even_within_window():
    """The character window alone is not enough (see this module's
    docstring): a blank line -- this repository's own paragraph/list-item
    separator -- between the two substrings defeats the pairing even when
    both fall well inside the window."""
    assertions = {"output_contains_near": [{"all": ["mypy", "missing deterministic gate"], "window": 400}]}
    text = "1. mypy failure noted here.\n\n2. missing deterministic gate mentioned in an unrelated repair."
    assert score_contract.score(text, assertions) == 0.0


def test_near_satisfied_within_one_paragraph_even_if_verbose():
    assertions = {"output_contains_near": [{"all": ["mypy", "missing deterministic gate"], "window": 400}]}
    text = (
        "1. mypy failure: a long explanation of exactly what went wrong here, "
        "including the fix that was applied and why it was the right call. "
        "Classification: missing deterministic gate."
    )
    assert score_contract.score(text, assertions) == 1.0


def test_near_regression_reproduces_the_review_finding():
    """The exact adversarial completion the Codex review on PR #328 cited
    (all three classification labels present, but bound to the wrong
    repairs) must no longer score 1.0 once a near-binding assertion ties
    each repair's own content keyword to its correct classification."""
    assertions = {
        "output_contains": ["missing deterministic gate", "unclear agent instruction", "external/human decision"],
        "output_contains_near": [{"all": ["mypy", "missing deterministic gate"], "window": 200}],
    }
    swapped = (
        "Repair 1 is unclear agent instruction; repair 2 is external/human "
        "decision; repair 3 is missing deterministic gate. Refs #240."
    )
    assert score_contract.score(swapped, assertions) < 1.0


def test_near_mixed_with_contains_and_not_contains():
    assertions = {
        "output_contains": ["Refs #240"],
        "output_not_contains": ["LGTM"],
        "output_contains_near": [{"all": ["ALPHA", "BETA"], "window": 10}],
    }
    # Refs #240 present (1), LGTM absent -> satisfied (1), near unsatisfied (0,
    # ALPHA/BETA both absent) => 2/3
    assert score_contract.score("Refs #240, no pairing here", assertions) == pytest.approx(2 / 3)


def test_near_entry_missing_all_key_raises_value_error():
    with pytest.raises(ValueError):
        score_contract.score("anything", {"output_contains_near": [{"window": 50}]})


def test_near_entry_all_with_one_substring_raises_value_error():
    with pytest.raises(ValueError):
        score_contract.score("anything", {"output_contains_near": [{"all": ["only-one"]}]})


def test_near_non_list_raises_value_error():
    with pytest.raises(ValueError):
        score_contract.score("anything", {"output_contains_near": "not-a-list"})


def test_near_non_mapping_entry_raises_value_error():
    with pytest.raises(ValueError):
        score_contract.score("anything", {"output_contains_near": ["not-a-mapping"]})


def test_only_near_assertions_is_a_valid_nonempty_set():
    assertions = {"output_contains_near": [{"all": ["A", "B"], "window": 5}]}
    assert score_contract.score("AB", assertions) == 1.0


# ---------------------------------------------------------------------------
# output_not_contains_near
# ---------------------------------------------------------------------------


def test_not_near_satisfied_when_pairing_absent_entirely():
    assertions = {"output_not_contains_near": [{"all": ["mypy", "external decision"], "window": 60}]}
    assert score_contract.score("mypy failure fixed elsewhere", assertions) == 1.0


def test_not_near_satisfied_when_both_present_but_far_apart():
    assertions = {"output_not_contains_near": [{"all": ["mypy", "external decision"], "window": 20}]}
    far_apart = "mypy failure. " + ("padding " * 10) + "external decision made."
    assert score_contract.score(far_apart, assertions) == 1.0


def test_not_near_unsatisfied_when_wrongly_bound_close_together():
    assertions = {"output_not_contains_near": [{"all": ["mypy", "external decision"], "window": 60}]}
    assert score_contract.score("mypy issue is an external decision.", assertions) == 0.0


def test_near_and_not_near_together_reject_the_swap_the_correct_response_survives():
    """Regression for the terse-swap variant that a bare `output_contains_near`
    positive check alone could not catch (see PR #328's review discussion):
    pairing a positive near-check with a not-near ban on the wrong pairing
    rejects a compact, keyword-bearing but mis-bound response, while a
    correctly-bound (if more verbose) response still passes."""
    assertions = {
        "output_contains_near": [{"all": ["mypy", "missing deterministic gate"], "window": 200}],
        "output_not_contains_near": [{"all": ["mypy", "unclear agent instruction"], "window": 200}],
    }
    correct = (
        "1. mypy failure fixed by a type conversion. "
        "Classification: missing deterministic gate."
    )
    wrongly_bound_compact = "Repair 1 (mypy failure) is unclear agent instruction."
    assert score_contract.score(correct, assertions) == 1.0
    # Neither assertion holds: "missing deterministic gate" never appears
    # (near fails), and mypy IS wrongly bound to "unclear agent instruction"
    # (not_near fails too) -> 0/2.
    assert score_contract.score(wrongly_bound_compact, assertions) == 0.0


def test_deterministic_same_inputs_same_output():
    assertions = {"output_contains": ["Facts"], "output_not_contains": ["LGTM"]}
    first = score_contract.score("Facts and no verdict", assertions)
    second = score_contract.score("Facts and no verdict", assertions)
    assert first == second == 1.0


def test_pruning_compare_keeps_matched_correctness_with_lower_context_cost():
    assert score_contract.pruning_compare(0.9, 0.9, 1400, 1120) == "KEEP"


def test_pruning_compare_keeps_a_direct_correctness_improvement():
    # Correctness strictly improves (not matched): the "if after >
    # before_correctness: return KEEP" branch, distinct from the
    # matched-correctness/lower-cost branch covered above.
    assert score_contract.pruning_compare(0.9, 0.95, 1400, 1400) == "KEEP"


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
    monkeypatch.setattr(score_contract.sys, "stdin", _FakeStdin(b"only Facts"))
    rc = score_contract.main(["--assertions", str(apath)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "0.500000"


def test_main_reports_error_for_non_utf8_output_stdin(tmp_path, capsys, monkeypatch):
    apath = tmp_path / "assertions.json"
    apath.write_text(json.dumps({"output_contains": ["Facts"]}), encoding="utf-8")
    monkeypatch.setattr(score_contract.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    rc = score_contract.main(["--assertions", str(apath)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "could not decode standard input" in err
    assert "Traceback" not in err


def test_main_reports_error_for_non_utf8_scores_stdin(capsys, monkeypatch):
    monkeypatch.setattr(score_contract.sys, "stdin", _FakeStdin(b"\xff\xfe bad"))
    rc = score_contract.main(["--compare-to", "0.5"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "codec can't decode" in err
    assert "Traceback" not in err


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


def test_main_dispatch_trace_confirmed_appends_marker(tmp_path, capsys):
    apath = tmp_path / "assertions.json"
    apath.write_text(json.dumps({"output_contains": ["Facts"]}), encoding="utf-8")
    opath = tmp_path / "run.txt"
    opath.write_text("Facts and more", encoding="utf-8")
    rc = score_contract.main([
        "--assertions", str(apath), "--output", str(opath),
        "--dispatch-trace-verdict", "confirmed",
    ])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "1.000000 DISPATCH_TRACE_CONFIRMED"


def test_main_dispatch_trace_not_confirmed_appends_marker(tmp_path, capsys):
    apath = tmp_path / "assertions.json"
    apath.write_text(json.dumps({"output_contains": ["Facts"]}), encoding="utf-8")
    opath = tmp_path / "run.txt"
    opath.write_text("Facts and more", encoding="utf-8")
    rc = score_contract.main([
        "--assertions", str(apath), "--output", str(opath),
        "--dispatch-trace-verdict", "not_confirmed",
    ])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "1.000000 DISPATCH_TRACE_NOT_CONFIRMED"


def test_main_dispatch_trace_unverified_appends_marker(tmp_path, capsys):
    apath = tmp_path / "assertions.json"
    apath.write_text(json.dumps({"output_contains": ["Facts"]}), encoding="utf-8")
    opath = tmp_path / "run.txt"
    opath.write_text("no match here", encoding="utf-8")
    rc = score_contract.main([
        "--assertions", str(apath), "--output", str(opath),
        "--dispatch-trace-verdict", "unverified",
    ])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "0.000000 DISPATCH_TRACE_UNVERIFIED"


def test_main_dispatch_trace_verdict_omitted_leaves_output_unchanged(tmp_path, capsys):
    apath = tmp_path / "assertions.json"
    apath.write_text(json.dumps({"output_contains": ["Facts"]}), encoding="utf-8")
    opath = tmp_path / "run.txt"
    opath.write_text("Facts", encoding="utf-8")
    rc = score_contract.main(["--assertions", str(apath), "--output", str(opath)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "1.000000"


def test_main_rejects_dispatch_trace_verdict_with_compare_to(tmp_path, capsys):
    scores = tmp_path / "scores.txt"
    scores.write_text("0.9\n1.0\n", encoding="utf-8")
    rc = score_contract.main([
        "--compare-to", "0.9", "--scores", str(scores),
        "--dispatch-trace-verdict", "confirmed",
    ])
    assert rc == 1
    assert "not defined for --compare-to" in capsys.readouterr().err


def test_main_rejects_invalid_dispatch_trace_verdict_choice(capsys):
    with pytest.raises(SystemExit):
        score_contract.main(["--dispatch-trace-verdict", "yes"])


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


# ---------------------------------------------------------------------------
# output_icontains / output_not_icontains (issue #628): opt-in
# case-insensitive forms of output_contains/output_not_contains.
# ---------------------------------------------------------------------------


def test_icontains_matches_different_case():
    assertions = {"output_icontains": ["test name"]}
    assert score_contract.score("The **Test name** heading", assertions) == 1.0


def test_icontains_absent_scores_zero():
    assertions = {"output_icontains": ["test name"]}
    assert score_contract.score("nothing relevant here", assertions) == 0.0


def test_not_icontains_satisfied_when_absent_any_case():
    assertions = {"output_not_icontains": ["lgtm"]}
    assert score_contract.score("a careful review", assertions) == 1.0


def test_not_icontains_violated_regardless_of_case():
    assertions = {"output_not_icontains": ["lgtm"]}
    assert score_contract.score("LGTM ship it", assertions) == 0.0


def test_icontains_and_not_icontains_do_not_affect_case_sensitive_keys():
    # output_contains stays case-sensitive even when output_icontains is
    # also present in the same assertion set -- strictly additive.
    assertions = {
        "output_contains": ["TEST NAME"],
        "output_icontains": ["test name"],
    }
    # "TEST NAME" (exact case) is absent; "test name" (any case) is present
    # via "**Test name**" -> 1 of 2 satisfied.
    assert score_contract.score("The **Test name** heading", assertions) == pytest.approx(0.5)


def test_icontains_uses_casefold_not_lower():
    # casefold() normalizes the German sharp s; documented edge case.
    assertions = {"output_icontains": ["strasse"]}
    assert score_contract.score("Die Straße ist lang", assertions) == 1.0


def test_only_icontains_assertions_is_a_valid_nonempty_set():
    assertions = {"output_icontains": ["ok"]}
    assert score_contract.score("OK", assertions) == 1.0


def test_only_not_icontains_assertions_is_a_valid_nonempty_set():
    assertions = {"output_not_icontains": ["lgtm"]}
    assert score_contract.score("fine", assertions) == 1.0


def test_empty_icontains_lists_alone_raise_value_error():
    with pytest.raises(ValueError):
        score_contract.score("anything", {"output_icontains": [], "output_not_icontains": []})


# ---------------------------------------------------------------------------
# Remaining branches: empty score list, TypeError-raising inputs to the
# correctness/context-cost validators, and main()'s CLI-argument and
# file-handling error paths (issue #562 coverage floor).
# ---------------------------------------------------------------------------


def test_split_mean_rejects_empty_score_list():
    with pytest.raises(ValueError, match="cannot take the mean of an empty score list"):
        score_contract.split_mean([])


@pytest.mark.parametrize("invalid", ["not-a-number", None, []])
def test_strict_compare_rejects_non_numeric_correctness(invalid):
    # math.isfinite() raises TypeError on a non-numeric value; _validate_
    # correctness must translate that into the documented ValueError rather
    # than letting the TypeError escape uncaught.
    with pytest.raises(ValueError, match=r"finite number in \[0,1\]"):
        score_contract.strict_compare(invalid, 0.9)


@pytest.mark.parametrize("invalid", ["not-a-number", None, []])
def test_pruning_compare_rejects_non_numeric_context_cost(invalid):
    # Same TypeError-to-ValueError translation as above, for
    # _validate_context_cost's math.isfinite() call.
    with pytest.raises(ValueError, match="finite non-negative"):
        score_contract.pruning_compare(0.9, 0.9, invalid, 100)


def test_main_pruning_only_without_compare_to_or_costs_fails_closed(capsys):
    rc = score_contract.main(["--pruning-only"])
    assert rc == 1
    assert (
        "--pruning-only requires --compare-to, --prior-context-cost, "
        "and --candidate-context-cost" in capsys.readouterr().err
    )


def test_main_pruning_only_missing_one_context_cost_fails_closed(tmp_path, capsys):
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
            "1400",
        ]
    )
    assert rc == 1
    assert "--pruning-only requires --compare-to" in capsys.readouterr().err


def test_main_requires_assertions_or_compare_to(capsys):
    rc = score_contract.main([])
    assert rc == 1
    assert (
        "--assertions is required unless --compare-to is used"
        in capsys.readouterr().err
    )


def test_main_missing_assertions_file_fails_closed(capsys):
    rc = score_contract.main(["--assertions", "/no/such/assertions.json"])
    assert rc == 1
    assert "assertions file not found" in capsys.readouterr().err


def test_main_malformed_assertions_json_fails_closed(tmp_path, capsys):
    apath = tmp_path / "assertions.json"
    apath.write_text("not json{{{", encoding="utf-8")
    rc = score_contract.main(["--assertions", str(apath)])
    assert rc == 1
    assert "invalid JSON" in capsys.readouterr().err


def test_main_missing_output_file_fails_closed(tmp_path, capsys):
    apath = tmp_path / "assertions.json"
    apath.write_text(json.dumps({"output_contains": ["Facts"]}), encoding="utf-8")
    rc = score_contract.main(
        ["--assertions", str(apath), "--output", "/no/such/output.txt"]
    )
    assert rc == 1
    assert "output file not found" in capsys.readouterr().err


def test_main_undecodable_assertions_file_fails_closed(tmp_path, capsys):
    apath = tmp_path / "assertions.json"
    apath.write_bytes(b"\xff\xfe bad")
    rc = score_contract.main(["--assertions", str(apath)])
    assert rc == 1
    assert "could not decode assertions file" in capsys.readouterr().err


def test_main_undecodable_output_file_fails_closed(tmp_path, capsys):
    apath = tmp_path / "assertions.json"
    apath.write_text(json.dumps({"output_contains": ["Facts"]}), encoding="utf-8")
    opath = tmp_path / "output.txt"
    opath.write_bytes(b"\xff\xfe bad")
    rc = score_contract.main(
        ["--assertions", str(apath), "--output", str(opath)]
    )
    assert rc == 1
    assert "could not decode output file" in capsys.readouterr().err
