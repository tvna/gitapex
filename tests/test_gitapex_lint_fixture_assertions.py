"""Tests for the eval-fixture assertion linter.

Unit tests run each heuristic against a small synthetic corpus so they are
self-contained; one integration test runs the linter against the repository's
real fixture set and pins it to zero warnings, which is issue #170's first
acceptance criterion.
"""

from pathlib import Path

import gitapex_lint_fixture_assertions as L
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# A synthetic corpus exercising each heuristic: a distinctive heading, a
# bolded multi-word quote that wraps a line (so whitespace flattening is
# tested), a phrase the rubric negates, and a phrase present verbatim.
CORPUS = (
    "# Skill quality rubric\n\n"
    "## Blind spot pass\n\n"
    "A precondition step, not a tenth dimension -- the nine-dimension count\n"
    "is unchanged.\n\n"
    "A real guardrail needs to be deterministic, and the enforcement\n"
    "methods are hooks and permissions.\n\n"
    'When justified, say so ("model/effort pin justified -- <reason>").\n'
)
ANCHORS = L.extract_anchors(CORPUS)
FLAT = L.WS_RE.sub(" ", CORPUS.lower())
TOKENS = L._content_tokens(CORPUS)


# ---- check_case (issue #170 check 1) ----


def test_case_flags_lowercase_against_heading():
    assert L.check_case("blind spot", ANCHORS) == "Blind spot pass"


def test_case_passes_exact_heading_casing():
    assert L.check_case("Blind spot pass", ANCHORS) is None


def test_case_ignores_single_word():
    # A one-word assertion is not compared -- too collision-prone.
    assert L.check_case("blind", ANCHORS) is None


def test_case_passes_phrase_absent_from_anchors():
    assert L.check_case("duplicate query results", ANCHORS) is None


def test_case_passes_when_exact_match_exists_after_a_looser_anchor():
    # Issue #858: the same phrase appears twice in this corpus, once as a
    # capitalized heading (an earlier anchor) and once in its exact
    # asserted casing inside a later quoted phrase -- the exact match must
    # win regardless of extraction order.
    corpus = '## Blind Spot Pass\n\nThe step is documented as "blind spot pass" in the field-value table.\n'
    anchors = L.extract_anchors(corpus)
    assert anchors == ["Blind Spot Pass", "blind spot pass"]
    assert L.check_case("blind spot pass", anchors) is None


def test_case_still_flags_when_no_anchor_has_the_exact_case():
    # Same corpus, but the assertion casing does not match ANY anchor --
    # still a real mismatch, not silenced by the fix above.
    corpus = '## Blind Spot Pass\n\nThe step is documented as "blind spot pass" in the field-value table.\n'
    anchors = L.extract_anchors(corpus)
    assert L.check_case("Blind spot pass", anchors) == "Blind Spot Pass"


# ---- check_negation (issue #170 check 2) ----


def test_negation_flags_phrase_the_rubric_denies():
    detail = L.check_negation("tenth dimension", FLAT)
    assert detail is not None
    assert "tenth dimension" in detail


def test_negation_passes_wrong_verdict_marker():
    # "LGTM" is a wrong-verdict marker the rubric never negates, so banning
    # it in output_not_contains is correct and must not warn.
    assert L.check_negation("LGTM", FLAT) is None


def test_negation_passes_action_qualified_ban():
    # The fixed form of the historical bug: the action verb makes it match
    # only the wrong assertion, never a denial.
    assert L.check_negation("adding a tenth dimension", FLAT) is None


# ---- check_paraphrase (issue #170 check 3) ----


def test_paraphrase_flags_absent_variant():
    detail = L.check_paraphrase("hooks or permission", FLAT, TOKENS)
    assert detail is not None


def test_paraphrase_passes_exact_quote_across_line_wrap():
    # The correct phrase wraps a line in the corpus; whitespace flattening
    # must recognize it as present, not flag it as drift.
    assert L.check_paraphrase("hooks and permissions", FLAT, TOKENS) is None


def test_paraphrase_ignores_single_content_word():
    assert L.check_paraphrase("permissions", FLAT, TOKENS) is None


def test_paraphrase_passes_unrelated_target_text():
    # Target-specific text whose content words do not co-occur in the rubric.
    assert L.check_paraphrase("deploy window every Tuesday", FLAT, TOKENS) is None


# ---- end-to-end via main() ----


def _write_task(tmp_path, expected):
    body = ["id: t", "name: T", "inputs:", "  prompt: |", "    p", "expected:"]
    for key, values in expected.items():
        body.append(f"  {key}:")
        body += [f'    - "{v}"' for v in values]
    (tmp_path / "t.yaml").write_text("\n".join(body) + "\n", encoding="utf-8")
    return tmp_path


def _corpus_files(tmp_path):
    rubric = tmp_path / "rubric.md"
    skill = tmp_path / "SKILL.md"
    rubric.write_text(CORPUS, encoding="utf-8")
    skill.write_text("# skill\n", encoding="utf-8")
    return rubric, skill


def test_main_clean_task_exits_zero(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, {"output_contains": ["Blind spot pass"], "output_not_contains": ["LGTM"]})
    rubric, skill = _corpus_files(tmp_path)
    assert L.main(["--tasks-glob", str(tasks / "*.yaml"), "--rubric", str(rubric), "--skill", str(skill)]) == 0


def test_main_buggy_task_exits_one(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, {"output_contains": ["blind spot"], "output_not_contains": ["tenth dimension"]})
    rubric, skill = _corpus_files(tmp_path)
    assert L.main(["--tasks-glob", str(tasks / "*.yaml"), "--rubric", str(rubric), "--skill", str(skill)]) == 1


def test_main_symmetric_ban_violation_exits_one(tmp_path):
    # Issue #861's own coverage floor: before that issue's fixes, lint_task's
    # own symmetric-ban Warning_ emission (not just check_symmetric_bans in
    # isolation, already unit-tested above) was exercised only incidentally
    # by four real corpus fixtures that had this exact authoring defect.
    # Fixing those defects for real (see this issue's own PR) removed the
    # only real-corpus case reaching that line -- a synthetic fixture here
    # covers the integration path directly, so a future regression in this
    # wiring is still caught even though the real corpus is now clean of
    # this defect class.
    #
    # Deliberately declares no output_not_contains at all (the "no bans in
    # either direction" symmetric-ban sub-case, distinct from and simpler
    # than the negative-only/positive-only sub-cases already unit-tested
    # above via check_symmetric_bans directly) -- any of the three
    # sub-cases reaches the same lint_task line equally, so this is not an
    # under-specified negative-only case, it is a different, equally valid
    # violation shape chosen for minimalism.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    task_path = tasks / "t.yaml"
    task_path.write_text(
        "id: t\nname: T\n"
        "description: Whether X occurred cannot be determined from available data.\n"
        "inputs:\n  prompt: p\nexpected:\n  output_contains: []\n",
        encoding="utf-8",
    )
    rubric, skill = _corpus_files(tmp_path)
    warnings, _ = L.lint_skill_tasks([task_path], L.load_corpus(rubric, skill))
    assert any(w.rule == "symmetric-ban" and w.task == "t.yaml" for w in warnings)
    assert L.main(["--tasks-glob", str(tasks / "*.yaml"), "--rubric", str(rubric), "--skill", str(skill)]) == 1


def test_main_missing_corpus_exits_two(tmp_path):
    assert (
        L.main(
            [
                "--tasks-glob",
                str(tmp_path / "*.yaml"),
                "--rubric",
                str(tmp_path / "nope.md"),
                "--skill",
                str(tmp_path / "nope2.md"),
            ]
        )
        == 2
    )


def test_main_non_utf8_rubric_exits_two_not_uncaught(tmp_path):
    # load_corpus()'s own read_text() calls carry no try/except of their
    # own; single-skill mode's caller (~line 1080) must catch
    # UnicodeDecodeError alongside OSError, or a non-UTF-8 rubric.md would
    # escape as an uncaught traceback instead of this script's own exit-2
    # error message.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, {"output_contains": ["Blind spot pass"]})
    rubric = tmp_path / "rubric.md"
    rubric.write_bytes(b"# Rubric \xff\xfe bad\n")
    skill = tmp_path / "SKILL.md"
    skill.write_text("# skill\n", encoding="utf-8")
    assert L.main(["--tasks-glob", str(tasks / "*.yaml"), "--rubric", str(rubric), "--skill", str(skill)]) == 2


def test_main_no_tasks_exits_two(tmp_path):
    rubric, skill = _corpus_files(tmp_path)
    assert (
        L.main(["--tasks-glob", str(tmp_path / "none" / "*.yaml"), "--rubric", str(rubric), "--skill", str(skill)]) == 2
    )


def test_repository_fixtures_are_clean():
    # Issue #170 acceptance criterion 1: the current fixture set produces
    # zero warnings. Runs against the real repo paths so it stays a live gate.
    rc = L.main(
        [
            "--tasks-glob",
            str(REPO_ROOT / "evals/evaluating-skill-quality/tasks/*.yaml"),
            "--rubric",
            str(REPO_ROOT / L.DEFAULT_RUBRIC),
            "--skill",
            str(REPO_ROOT / L.DEFAULT_SKILL),
        ]
    )
    assert rc == 0


def test_repository_case_sensitivity_findings_match_the_known_reviewed_residual():
    # Issue #858 acceptance criterion 1: enumerate every output_contains /
    # output_not_contains case-sensitivity finding across the linter's real
    # default (whole-corpus) discovery scope -- broader than the single-skill
    # test above, and the scope that actually matters for the waza-divergence
    # risk this finding is a proxy for (gitapex_score_contract.py is
    # case-sensitive by design; waza's own expected.output_contains is
    # case-insensitive -- see gitapex_score_contract.py's module docstring).
    #
    # After fixing check_case's anchor-order bug (this issue), exactly one
    # finding remains:
    # scorer-gated-skill-edits/ship-without-transfer-check.yaml's "transfer
    # check" has no exact-case anchor because its correct source
    # (scorer-gated-skill-edits/SKILL.md's own Stop-boundaries prose, "has
    # not passed a transfer check") is plain sentence text, outside
    # extract_anchors's heading/bold/quoted scope -- confirmed by hand
    # against that SKILL.md, not a real fixture bug or waza-divergence risk.
    # Pinning the exact expected set (not just "count <= 1") means a NEW
    # case-sensitivity finding anywhere in the corpus fails this test loudly
    # rather than hiding behind the known exception.
    evals_root = REPO_ROOT / "evals"
    skills_root = REPO_ROOT / "skills"
    names = L.discover_skills(evals_root, skills_root)
    warnings = L.lint_all_skills(evals_root, skills_root, skill_names=names)
    case_findings = {(w.task, w.value) for w in warnings if w.rule == "case-sensitivity"}
    assert case_findings == {("scorer-gated-skill-edits/ship-without-transfer-check.yaml", "transfer check")}


def test_repository_wide_fixtures_have_no_unreviewed_blocking_findings():
    # Issue #861 acceptance criterion 1: the linter now runs over every
    # committed evals/*/tasks/*.yaml suite as a blocking pytest gate --
    # broader than test_repository_fixtures_are_clean above (one skill) and
    # broader than the case-sensitivity-only test above it (one rule). The
    # first whole-corpus run surfaced 22 real findings across 15 skills; 17
    # were fixed for real in the same PR that added this test (fixture
    # wording corrected to quote the rubric verbatim, missing symmetric bans
    # added, negation-trap-prone bans reworded to the violation-claim shape,
    # and 7 skills' genuinely hostile-payload fixtures retagged `adversarial`
    # -- see that PR's own body for the full fixed set). Five could not be
    # resolved by a fixture-authoring fix alone and are pinned here as an
    # explicitly reviewed, disclosed residual -- never silenced by narrowing
    # --tasks-glob (this test still runs the linter's real, unrestricted
    # default scope):
    #
    #   - scorer-gated-skill-edits/ship-without-transfer-check.yaml
    #     [case-sensitivity]: the pre-existing #858 residual, already pinned
    #     above by test_repository_case_sensitivity_findings_match_the_known_
    #     reviewed_residual; repeated here because this test's own scope is
    #     every blocking rule, not only case-sensitivity.
    #   - outward-artifact-preflight/clean-pass.yaml [paraphrase-drift]
    #     'agreed convention': a linter false positive, hand-confirmed
    #     against both the fixture and the corpus -- the assertion validates
    #     the fixture's own prompt-supplied fact ("This repo has an agreed
    #     convention: ...", inputs.prompt), not a corpus quote. check_paraphrase
    #     only scans the rubric/SKILL.md corpus, which has no visibility into
    #     a fixture's own prompt text (unlike check 2/negation-trap and check
    #     6/prompt-echo, which are deliberately prompt-aware).
    #   - fixing-a-reported-issue, scorer-gated-skill-edits
    #     [adversarial-coverage]: each skill's own
    #     docs genuinely claim adversarial-relevant coverage, but no existing
    #     fixture in tasks/ embeds a real hostile/injected payload that could
    #     be honestly retagged `adversarial` without gaming the check (unlike
    #     the seven skills this run originally flagged whose existing
    #     injection/encoded-payload/escalation fixtures were retagged for
    #     real in this same PR). Each needs a genuinely new fixture -- see
    #     issue #872, opened as this residual's own tracking follow-up.
    #     `evaluating-skill-quality` was the third member of this group and
    #     is now resolved, not silenced: issue #332's ACM-7 audit round added
    #     `multi-turn-settled-dimension-relaxation-train.yaml`, a genuinely
    #     new fixture whose prompt stages a real escalating relaxation attempt
    #     rather than retagging an existing benign one. What its removal from
    #     this set evidences is only that some fixture under that skill's
    #     `tasks/` now carries the `adversarial` tag:
    #     `check_adversarial_coverage` matches the tag alone and never reads
    #     fixture prompt content, so retagging a benign fixture produces the
    #     identical removal (issue #907 withdrew the earlier, stronger
    #     "observable proof" wording here for exactly that reason). That the
    #     fixture is a genuinely new hostile payload rather than a retag is a
    #     hand-verified authoring claim -- readable in the fixture's own prompt
    #     and assertions -- not something this removal can establish. The set
    #     is pinned exactly for the reason stated below, not as that proof.
    #
    # Pinning the exact set (not "count <= 5") means a NEW blocking finding
    # anywhere in the corpus fails this test loudly, the same discipline the
    # case-sensitivity residual test above already applies.
    evals_root = REPO_ROOT / "evals"
    skills_root = REPO_ROOT / "skills"
    names = L.discover_skills(evals_root, skills_root)
    warnings = L.lint_all_skills(evals_root, skills_root, skill_names=names)
    blocking = {(w.task, w.rule, w.value) for w in warnings if w.blocking}
    assert blocking == {
        ("scorer-gated-skill-edits/ship-without-transfer-check.yaml", "case-sensitivity", "transfer check"),
        ("outward-artifact-preflight/clean-pass.yaml", "paraphrase-drift", "agreed convention"),
        ("fixing-a-reported-issue", "adversarial-coverage", "(tasks directory)"),
        ("scorer-gated-skill-edits", "adversarial-coverage", "(tasks directory)"),
    }


# ---- check_short_word_collision (issue #516, #218) ----


def test_short_word_collision_flags_known_pair():
    assert L.check_short_word_collision("actor") == "factor"


def test_short_word_collision_passes_longer_term():
    assert L.check_short_word_collision("factor") is None


def test_short_word_collision_ignores_non_alpha():
    assert L.check_short_word_collision("6.5") is None


def test_short_word_collision_ignores_deliberate_stem_fragment():
    # "emporal" is not itself a recognized word, unlike "actor" -- this
    # repository's own fixtures use exactly this kind of truncated stem to
    # match several inflections of "temporal", which must not be flagged.
    assert L.check_short_word_collision("emporal") is None


# ---- check_symmetric_bans (issue #516, #352) ----


def _indeterminate_task(bans):
    return {
        "id": "t",
        "name": "T",
        "description": "Whether X occurred cannot be determined from available data.",
        "expected": {"output_not_contains": bans},
    }


def test_symmetric_bans_flags_negative_only():
    detail = L.check_symmetric_bans(_indeterminate_task(["no force-push occurred"]))
    assert detail is not None
    assert "positive-claim" in detail


def test_symmetric_bans_flags_positive_only():
    detail = L.check_symmetric_bans(_indeterminate_task(["A force-push occurred"]))
    assert detail is not None
    assert "negative-claim" in detail


def test_symmetric_bans_passes_both_directions():
    detail = L.check_symmetric_bans(_indeterminate_task(["no force-push occurred", "A force-push occurred"]))
    assert detail is None


def test_symmetric_bans_flags_no_bans_at_all():
    detail = L.check_symmetric_bans(_indeterminate_task([]))
    assert detail is not None


def test_symmetric_bans_ignores_ordinary_fixture():
    # No "cannot be determined"-style marker: an ordinary fixture with only
    # a negative-direction ban is not held to the symmetric-ban rule.
    ordinary = {
        "id": "t",
        "name": "T",
        "description": "An ordinary review fixture.",
        "expected": {"output_not_contains": ["LGTM"]},
    }
    assert L.check_symmetric_bans(ordinary) is None


def test_symmetric_bans_classifies_bare_not_as_negative():
    # /code-review (issue #516 follow-up): NEGATION_CUE_RE originally omitted
    # bare "not", unlike DENIAL_CUES elsewhere in this file which already
    # treats "not " and "no " as equally valid denial forms.
    assert L.classify_ban_direction("not observed") == "negative"


def test_symmetric_bans_exempts_enum_style_indeterminate_status():
    # /code-review (issue #516 follow-up): a literal `route_status:
    # INDETERMINATE` status-field value is not the natural-language "claim
    # cannot be determined" pattern this check means to catch -- confirmed
    # against the real false positive on battle-testing-a-skill's own
    # codex-unknown-model-fail-closed.yaml.
    enum_style = {
        "id": "t",
        "name": "T",
        "description": "Requires an unknown caller to stop as INDETERMINATE.",
        "expected": {
            "output_contains": ["route_status", "INDETERMINATE"],
            "output_not_contains": ["model_route: inherited", "overall: PASS"],
        },
    }
    assert L.check_symmetric_bans(enum_style) is None


def test_symmetric_bans_still_flags_lowercase_indeterminate_claim():
    # The exemption above must not swallow the genuine epistemic-claim
    # case, which uses lowercase "indeterminate" as an output_contains
    # verdict rather than an ALL-CAPS status-field value.
    detail = L.check_symmetric_bans(_indeterminate_task(["no force-push occurred"]))
    assert detail is not None


# ---- check_unsatisfiable_assertion_pair (issue #628) ----


def test_unsatisfiable_pair_flags_contains_vs_not_icontains():
    expected = {"output_contains": ["Foo"], "output_not_icontains": ["foo"]}
    findings = L.check_unsatisfiable_assertion_pair(expected)
    assert len(findings) == 1
    key, value, rule, _detail = findings[0]
    assert key == "output_not_icontains"
    assert rule == "unsatisfiable-assertion-pair"
    assert "foo" in value


def test_unsatisfiable_pair_flags_near_member_vs_not_icontains():
    # Satisfying output_contains_near also requires literal presence of
    # every member in its "all" list, so the same contradiction applies.
    expected = {
        "output_contains_near": [{"all": ["Foo", "Bar"], "window": 100}],
        "output_not_icontains": ["foo"],
    }
    findings = L.check_unsatisfiable_assertion_pair(expected)
    assert any(rule == "unsatisfiable-assertion-pair" for _, _, rule, _ in findings)


def test_unsatisfiable_pair_does_not_flag_mirrored_direction():
    # output_not_contains + output_icontains on the same substring is
    # satisfiable (e.g. text containing only "FOO" satisfies both), so it
    # must NOT be flagged -- confirmed via adversarial review before this
    # check was implemented.
    expected = {"output_not_contains": ["Foo"], "output_icontains": ["foo"]}
    assert L.check_unsatisfiable_assertion_pair(expected) == []


def test_unsatisfiable_pair_flags_redundant_same_polarity_pair():
    expected = {"output_contains": ["Foo"], "output_icontains": ["foo"]}
    findings = L.check_unsatisfiable_assertion_pair(expected)
    assert len(findings) == 1
    key, _value, rule, _detail = findings[0]
    assert key == "output_icontains"
    assert rule == "redundant-assertion-pair"


def test_unsatisfiable_pair_passes_unrelated_assertions():
    expected = {"output_contains": ["Foo"], "output_icontains": ["bar"]}
    assert L.check_unsatisfiable_assertion_pair(expected) == []


def test_unsatisfiable_pair_flags_icontains_vs_not_icontains_same_fold():
    # Regression (adversarial review, issue #628): both keys already match
    # case-insensitively, so requiring and banning the identical folded
    # substring via icontains/not_icontains is an unconditional
    # contradiction -- the first draft only built its literal-requirement
    # set from output_contains/output_contains_near and missed this direct
    # case entirely (gitapex_score_contract.score() confirmed capped at 0.5 for
    # every output text tried).
    expected = {"output_icontains": ["Test"], "output_not_icontains": ["test"]}
    findings = L.check_unsatisfiable_assertion_pair(expected)
    assert len(findings) == 1
    key, _value, rule, _detail = findings[0]
    assert key == "output_not_icontains"
    assert rule == "unsatisfiable-assertion-pair"


def test_unsatisfiable_pair_flags_redundant_not_contains_vs_not_icontains():
    # Regression (adversarial review, issue #628): the mirrored ban-side
    # redundancy -- output_not_icontains banning a substring case-
    # insensitively always also satisfies output_not_contains banning the
    # same substring case-sensitively, the same logic as the already-
    # covered positive-direction pair, but the first draft only checked
    # that positive direction.
    expected = {"output_not_contains": ["Foo"], "output_not_icontains": ["foo"]}
    findings = L.check_unsatisfiable_assertion_pair(expected)
    assert len(findings) == 1
    key, _value, rule, _detail = findings[0]
    assert key == "output_not_icontains"
    assert rule == "redundant-assertion-pair"


def test_unsatisfiable_pair_passes_empty_expected():
    assert L.check_unsatisfiable_assertion_pair({}) == []


def test_unsatisfiable_pair_is_wired_into_lint_task_via_main(tmp_path):
    # End-to-end: the check must actually be invoked and its findings
    # surfaced as blocking warnings, not just correct in isolation.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, {"output_contains": ["Foo"], "output_not_icontains": ["foo"]})
    rubric, skill = _corpus_files(tmp_path)
    assert L.main(["--tasks-glob", str(tasks / "*.yaml"), "--rubric", str(rubric), "--skill", str(skill)]) == 1


# ---- checks 2-4 extended to output_icontains/output_not_icontains, and
# check 1 (case-sensitivity) deliberately NOT extended (issue #628) ----


def test_icontains_paraphrase_drift_is_flagged(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, {"output_icontains": ["hooks or permission"]})
    rubric, skill = _corpus_files(tmp_path)
    assert L.main(["--tasks-glob", str(tasks / "*.yaml"), "--rubric", str(rubric), "--skill", str(skill)]) == 1


def test_icontains_short_word_collision_is_flagged(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, {"output_icontains": ["actor"]})
    rubric, skill = _corpus_files(tmp_path)
    assert L.main(["--tasks-glob", str(tasks / "*.yaml"), "--rubric", str(rubric), "--skill", str(skill)]) == 1


def test_not_icontains_negation_trap_is_flagged(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, {"output_not_icontains": ["tenth dimension"]})
    rubric, skill = _corpus_files(tmp_path)
    assert L.main(["--tasks-glob", str(tasks / "*.yaml"), "--rubric", str(rubric), "--skill", str(skill)]) == 1


def test_icontains_different_case_than_anchor_is_not_flagged_for_case_sensitivity(tmp_path):
    # check_case is deliberately NOT run against output_icontains: a casing
    # difference is expected and correct for a key whose whole point is to
    # ignore case, so this must exit 0, not warn about case-sensitivity.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, {"output_icontains": ["blind spot"]})
    rubric, skill = _corpus_files(tmp_path)
    assert L.main(["--tasks-glob", str(tasks / "*.yaml"), "--rubric", str(rubric), "--skill", str(skill)]) == 0


# ---- check_symmetric_bans extended to icontains/not_icontains (issue #628) ----


def test_symmetric_bans_exempts_enum_style_indeterminate_status_via_icontains():
    # Same exemption as the output_contains case, but declared via the new
    # output_icontains key -- proves the key is actually consulted, not
    # just present without effect.
    task = {
        "id": "t",
        "name": "T",
        "description": "Requires an unknown caller to stop as INDETERMINATE.",
        "expected": {
            "output_icontains": ["route_status", "INDETERMINATE"],
            "output_not_contains": ["model_route: inherited"],
        },
    }
    assert L.check_symmetric_bans(task) is None


def test_symmetric_bans_counts_not_icontains_as_a_ban():
    detail = L.check_symmetric_bans(
        {
            "id": "t",
            "name": "T",
            "description": "Whether X occurred cannot be determined from available data.",
            "expected": {"output_not_icontains": ["no force-push occurred"]},
        }
    )
    assert detail is not None
    assert "positive-claim" in detail


def test_symmetric_bans_passes_both_directions_via_not_icontains():
    # Both ban directions can now be split across output_not_contains and
    # output_not_icontains -- proves output_not_icontains entries are
    # actually merged into the "bans" set, not silently ignored.
    detail = L.check_symmetric_bans(
        {
            "id": "t",
            "name": "T",
            "description": "Whether X occurred cannot be determined from available data.",
            "expected": {
                "output_not_contains": ["A force-push occurred"],
                "output_not_icontains": ["no force-push occurred"],
            },
        }
    )
    assert detail is None


# ---- check_prompt_echo (issue #516, #191 -- opt in, non-blocking) ----


def test_prompt_echo_flags_verbatim_substring():
    detail = L.check_prompt_echo("dimension eight", "review this for dimension eight please")
    assert detail is not None


def test_prompt_echo_passes_absent_phrase():
    assert L.check_prompt_echo("dimension eight", "review this artifact please") is None


def test_prompt_echo_ignores_single_word():
    assert L.check_prompt_echo("dimension", "review dimension eight please") is None


# ---- check_cross_task_collision (issue #516, #270, #473 -- opt in, non-blocking) ----


def test_cross_task_collision_flags_exact_match_in_sibling_task():
    index = {"other.yaml": {"not applicable"}, "self.yaml": set()}
    assert L.check_cross_task_collision("self.yaml", "not applicable", index) == "other.yaml"


def test_cross_task_collision_ignores_own_task():
    index = {"self.yaml": {"not applicable"}}
    assert L.check_cross_task_collision("self.yaml", "not applicable", index) is None


def test_cross_task_collision_excludes_enum_style_token():
    # This repository's closed-enum classification fixtures deliberately
    # ban sibling UPPER_SNAKE_CASE labels -- a correct design, not a bug.
    index = {"other.yaml": {"status: no_compatibility_warning"}}
    assert L.check_cross_task_collision("self.yaml", "Status: NO_COMPATIBILITY_WARNING", index) is None


# ---- check_adversarial_coverage (issue #516, #473 -- discovery mode only) ----


def _write_yaml(path, tags):
    path.write_text(
        "id: t\nname: T\ninputs:\n  prompt: p\ntags:\n"
        + "".join(f"  - {t}\n" for t in tags)
        + "expected:\n  output_contains: []\n",
        encoding="utf-8",
    )


def test_adversarial_coverage_flags_claim_without_tag(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_yaml(tasks / "t.yaml", ["quality"])
    detail = L.check_adversarial_coverage("some-skill", tasks, "This skill covers 22 adversarial dimensions.")
    assert detail is not None


def test_adversarial_coverage_passes_with_tagged_fixture(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_yaml(tasks / "t.yaml", ["quality", "adversarial"])
    detail = L.check_adversarial_coverage("some-skill", tasks, "This skill covers 22 adversarial dimensions.")
    assert detail is None


def test_adversarial_coverage_ignores_skill_without_claim(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_yaml(tasks / "t.yaml", ["quality"])
    detail = L.check_adversarial_coverage("some-skill", tasks, "This skill covers quality.")
    assert detail is None


# ---- check_dispatch_declaration_coverage (issue #584 -- discovery mode only) --


def _write_yaml_with_requires_fresh_dispatch(path, *, declared: bool):
    body = "id: t\nname: T\ninputs:\n  prompt: p\nexpected:\n  output_contains: []\n"
    if declared:
        body += '  requires_fresh_dispatch:\n    tool_names: ["Agent"]\n    min_dispatches: 1\n'
    path.write_text(body, encoding="utf-8")


def test_dispatch_declaration_coverage_flags_mandate_skill_without_fixture(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_yaml_with_requires_fresh_dispatch(tasks / "t.yaml", declared=False)
    detail = L.check_dispatch_declaration_coverage("evaluating-skill-quality", tasks)
    assert detail is not None
    assert "requires_fresh_dispatch" in detail


def test_dispatch_declaration_coverage_passes_with_declaring_fixture(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_yaml_with_requires_fresh_dispatch(tasks / "t.yaml", declared=True)
    detail = L.check_dispatch_declaration_coverage("battle-testing-a-skill", tasks)
    assert detail is None


def test_dispatch_declaration_coverage_ignores_skill_outside_allowlist(tmp_path):
    # executing-a-branch-plan also mandates a "fresh subagent dispatch" in
    # its own SKILL.md prose, but issue #584 does not cover it -- this check
    # must not start blocking CI for a skill outside its explicit allowlist.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_yaml_with_requires_fresh_dispatch(tasks / "t.yaml", declared=False)
    detail = L.check_dispatch_declaration_coverage("executing-a-branch-plan", tasks)
    assert detail is None


def test_dispatch_declaration_coverage_reuses_supplied_task_data(tmp_path):
    missing_dir = tmp_path / "does-not-exist"
    task_data = {tmp_path / "t.yaml": {"expected": {"requires_fresh_dispatch": {"tool_names": ["Agent"]}}}}
    assert L.check_dispatch_declaration_coverage("evaluating-skill-quality", missing_dir, task_data=task_data) is None


def test_dispatch_declaration_coverage_empty_requires_fresh_dispatch_still_flags(tmp_path):
    # An empty/falsy requires_fresh_dispatch value (e.g. `requires_fresh_dispatch:`
    # with nothing under it) does not count as a real declaration.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "t.yaml").write_text(
        "id: t\nname: T\ninputs:\n  prompt: p\nexpected:\n  output_contains: []\n  requires_fresh_dispatch:\n",
        encoding="utf-8",
    )
    detail = L.check_dispatch_declaration_coverage("evaluating-skill-quality", tasks)
    assert detail is not None


def test_dispatch_declaration_coverage_bare_truthy_value_still_flags(tmp_path):
    # A fat-fingered `requires_fresh_dispatch: true` is truthy but describes
    # no checkable tool_names/min_dispatches -- must not satisfy coverage.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "t.yaml").write_text(
        "id: t\nname: T\ninputs:\n  prompt: p\nexpected:\n  output_contains: []\n  requires_fresh_dispatch: true\n",
        encoding="utf-8",
    )
    detail = L.check_dispatch_declaration_coverage("evaluating-skill-quality", tasks)
    assert detail is not None


def test_dispatch_declaration_coverage_zero_min_dispatches_still_flags(tmp_path):
    # requires_fresh_dispatch: {min_dispatches: 0} is a self-contradiction
    # (gitapex_check_dispatch_trace.py's own `count >= min_dispatches` would report
    # "confirmed" even with zero observed dispatches) -- must not satisfy
    # coverage, matching _is_real_dispatch_declaration's own contract.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "t.yaml").write_text(
        "id: t\nname: T\ninputs:\n  prompt: p\nexpected:\n"
        "  output_contains: []\n  requires_fresh_dispatch:\n"
        '    tool_names: ["Agent"]\n    min_dispatches: 0\n',
        encoding="utf-8",
    )
    detail = L.check_dispatch_declaration_coverage("evaluating-skill-quality", tasks)
    assert detail is not None


def test_dispatch_declaration_coverage_non_dict_expected_does_not_crash(tmp_path):
    # A malformed fixture (`expected: "todo"`, a stub left by mistake) must
    # not crash the lint pass with an AttributeError.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "t.yaml").write_text("id: t\nname: T\ninputs:\n  prompt: p\nexpected: todo\n", encoding="utf-8")
    detail = L.check_dispatch_declaration_coverage("evaluating-skill-quality", tasks)
    assert detail is not None


# ---- _is_real_dispatch_declaration (issue #584) ----------------------------


def test_is_real_dispatch_declaration_accepts_well_formed_dict():
    assert L._is_real_dispatch_declaration({"tool_names": ["Agent"], "min_dispatches": 1}) is True


def test_is_real_dispatch_declaration_defaults_min_dispatches_to_one():
    assert L._is_real_dispatch_declaration({"tool_names": ["Agent"]}) is True


def test_is_real_dispatch_declaration_rejects_non_dict():
    assert L._is_real_dispatch_declaration(True) is False
    assert L._is_real_dispatch_declaration("Agent") is False
    assert L._is_real_dispatch_declaration(None) is False
    assert L._is_real_dispatch_declaration([]) is False


def test_is_real_dispatch_declaration_rejects_empty_tool_names():
    assert L._is_real_dispatch_declaration({"tool_names": []}) is False
    assert L._is_real_dispatch_declaration({"tool_names": "Agent"}) is False
    assert L._is_real_dispatch_declaration({}) is False


def test_is_real_dispatch_declaration_rejects_non_positive_min_dispatches():
    assert L._is_real_dispatch_declaration({"tool_names": ["Agent"], "min_dispatches": 0}) is False
    assert L._is_real_dispatch_declaration({"tool_names": ["Agent"], "min_dispatches": -1}) is False


def test_is_real_dispatch_declaration_rejects_bool_min_dispatches():
    # isinstance(True, int) is True in Python -- must be excluded explicitly,
    # matching gitapex_score_contract.py's own established bool-exclusion pattern.
    assert L._is_real_dispatch_declaration({"tool_names": ["Agent"], "min_dispatches": True}) is False


def test_is_real_dispatch_declaration_rejects_non_int_min_dispatches():
    assert L._is_real_dispatch_declaration({"tool_names": ["Agent"], "min_dispatches": "1"}) is False


# ---- negation broadened to the fixture's own prompt (issue #516, #487) ----


def test_negation_haystack_extended_with_own_prompt_catches_ad_hoc_ban():
    # The rubric alone never mentions "rewritten commit"; only this
    # fixture's own prompt denies it. #487 asks the negation-trap detector
    # to catch this too, not only corpus-sourced denial phrases.
    prompt = "This session found no rewritten commit in the available history."
    prompt_flat = L.WS_RE.sub(" ", prompt.lower())
    local_flat = FLAT + " " + prompt_flat
    assert L.check_negation("rewritten commit", local_flat) is not None
    # Confirms the corpus alone would have missed it (isolating the fix).
    assert L.check_negation("rewritten commit", FLAT) is None


# ---- discovery mode (issue #516, #296) ----


def _write_skill_and_tasks(root, name, *, with_rubric=False, expected=None):
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(CORPUS, encoding="utf-8")
    if with_rubric:
        (skill_dir / "references").mkdir()
        (skill_dir / "references" / "rubric.md").write_text(CORPUS, encoding="utf-8")
    tasks_dir = root / "evals" / name / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_task(tasks_dir, expected or {"output_contains": ["Blind spot pass"], "output_not_contains": ["LGTM"]})
    return tasks_dir


def test_discover_skills_finds_matching_skill_and_tasks_dirs(tmp_path):
    _write_skill_and_tasks(tmp_path, "alpha")
    _write_skill_and_tasks(tmp_path, "beta")
    # A tasks/ dir with no matching skills/<name>/SKILL.md is not discovered.
    (tmp_path / "evals" / "orphan" / "tasks").mkdir(parents=True)
    found = L.discover_skills(tmp_path / "evals", tmp_path / "skills")
    assert found == ["alpha", "beta"]


def test_discover_skills_skips_empty_tasks_dir(tmp_path):
    skill_dir = tmp_path / "skills" / "gamma"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (tmp_path / "evals" / "gamma" / "tasks").mkdir(parents=True)
    assert L.discover_skills(tmp_path / "evals", tmp_path / "skills") == []


def test_lint_all_skills_executes_across_multiple_skills(tmp_path):
    # Acceptance criterion #296's own proof method: confirm the linter
    # actually runs a second skill's fixtures, not silently skipping it.
    # Each skill gets its own distinct, deliberate bug so a warning from
    # either one only appears if that skill was actually linted.
    _write_skill_and_tasks(tmp_path, "alpha", with_rubric=True, expected={"output_contains": ["blind spot"]})
    _write_skill_and_tasks(tmp_path, "beta", expected={"output_not_contains": ["tenth dimension"]})
    warnings = L.lint_all_skills(tmp_path / "evals", tmp_path / "skills")
    linted_skills = {w.task.split("/", 1)[0] for w in warnings}
    assert linted_skills == {"alpha", "beta"}


def test_main_discovery_mode_runs_when_tasks_glob_omitted(tmp_path, monkeypatch):
    _write_skill_and_tasks(tmp_path, "alpha", with_rubric=True)
    monkeypatch.chdir(tmp_path)
    # alpha's fixture is clean and its docs never mention "adversarial", so
    # discovery mode runs and finds nothing to flag -- confirms it actually
    # executes rather than silently no-op'ing without a --tasks-glob.
    assert L.main([]) == 0


def test_main_discovery_mode_exits_two_with_no_skills(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert L.main([]) == 2


def test_main_discovery_mode_non_utf8_skill_md_exits_two_not_uncaught(tmp_path, monkeypatch):
    # Discovery mode's load_corpus() call (lint_all_skills, ~line 993) and
    # _skill_claim_text()'s own reads (~lines 969/971) share main()'s outer
    # except clause (~line 1098), which must catch UnicodeDecodeError
    # alongside OSError/yaml.YAMLError/ValidationError -- a non-UTF-8
    # SKILL.md must exit 2 with this script's own error message, not an
    # uncaught traceback.
    _write_skill_and_tasks(tmp_path, "alpha")
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_bytes(b"# skill \xff\xfe bad\n")
    monkeypatch.chdir(tmp_path)
    assert L.main([]) == 2


def test_main_discovery_mode_non_utf8_eval_status_exits_two_not_uncaught(tmp_path, monkeypatch):
    # Same as above, but the non-UTF-8 byte is in eval-status.md, exercised
    # via _skill_claim_text()'s second read (line 971) rather than its
    # first (line 969) or load_corpus() (line 461).
    _write_skill_and_tasks(tmp_path, "alpha")
    (tmp_path / "evals" / "alpha" / "eval-status.md").write_bytes(b"# status \xff\xfe bad\n")
    monkeypatch.chdir(tmp_path)
    assert L.main([]) == 2


# ---- format_report (issue #516 follow-up) ----


def test_format_report_clean_run_says_well_formed():
    assert "well-formed" in L.format_report([])


def test_format_report_notes_only_does_not_claim_well_formed():
    # /code-review: with zero blocking warnings but a non-blocking note
    # present, the report must not print the "well-formed" claim the note
    # right below it contradicts.
    notes_only = [L.Warning_("t", "k", "v", "prompt-echo", "detail", blocking=False)]
    report = L.format_report(notes_only)
    assert "well-formed" not in report
    assert "0 blocking warning" in report
    assert "1 non-blocking note" in report


def test_format_report_blocking_warning_present():
    blocking = [L.Warning_("t", "k", "v", "case-sensitivity", "detail")]
    report = L.format_report(blocking)
    assert "1 warning(s)" in report
    assert "well-formed" not in report


# ---- lint_skill_tasks / lint_all_skills reuse already-parsed task data
# (issue #516 follow-up: avoid re-parsing each task YAML twice) ----


def test_lint_skill_tasks_returns_parsed_task_data(tmp_path):
    tasks_dir = _write_skill_and_tasks(tmp_path, "alpha", with_rubric=True)
    rubric, skill = (
        tmp_path / "skills" / "alpha" / "references" / "rubric.md",
        tmp_path / "skills" / "alpha" / "SKILL.md",
    )
    corpus = L.load_corpus(rubric, skill)
    task_paths = sorted(tasks_dir.glob("*.yaml"))
    warnings, task_data = L.lint_skill_tasks(task_paths, corpus)
    assert warnings == []
    assert set(task_data) == set(task_paths)
    assert task_data[task_paths[0]]["id"] == "t"


def test_check_adversarial_coverage_reuses_supplied_task_data(tmp_path):
    # Passing task_data must short-circuit the tasks_dir glob/parse entirely
    # -- point tasks_dir at a nonexistent directory to prove it is unused.
    missing_dir = tmp_path / "does-not-exist"
    task_data = {tmp_path / "t.yaml": {"tags": ["adversarial"]}}
    assert (
        L.check_adversarial_coverage("some-skill", missing_dir, "claims adversarial coverage", task_data=task_data)
        is None
    )


# ---- TaskFixture / ExpectedBlock / InputsBlock / NearAssertion (issue
# #684): the new pydantic model's own validation behavior. These are
# additions alongside the existing suite above, not replacements -- see
# the module docstring for why the model exists and what it does/does not
# strictly validate (e.g. requires_fresh_dispatch is deliberately open). --


def _well_formed_fixture(**overrides):
    fixture = {
        "id": "t",
        "name": "T",
        "inputs": {"prompt": "p"},
        "expected": {"output_contains": ["x"]},
    }
    fixture.update(overrides)
    return fixture


def test_task_fixture_accepts_the_well_formed_shape():
    fixture = L.TaskFixture.model_validate(_well_formed_fixture())
    assert fixture.id == "t"
    assert fixture.inputs.prompt == "p"
    assert fixture.expected.output_contains == ["x"]


def test_task_fixture_rejects_missing_id():
    fixture = _well_formed_fixture()
    del fixture["id"]
    with pytest.raises(L.ValidationError):
        L.TaskFixture.model_validate(fixture)


def test_task_fixture_rejects_missing_inputs():
    fixture = _well_formed_fixture()
    del fixture["inputs"]
    with pytest.raises(L.ValidationError):
        L.TaskFixture.model_validate(fixture)


def test_task_fixture_rejects_missing_expected():
    fixture = _well_formed_fixture()
    del fixture["expected"]
    with pytest.raises(L.ValidationError):
        L.TaskFixture.model_validate(fixture)


def test_task_fixture_rejects_wrong_type_expected():
    # expected: "todo" -- a stub scalar left by mistake, not a mapping.
    with pytest.raises(L.ValidationError):
        L.TaskFixture.model_validate(_well_formed_fixture(expected="todo"))


def test_task_fixture_rejects_wrong_type_inputs_prompt():
    with pytest.raises(L.ValidationError):
        L.TaskFixture.model_validate(_well_formed_fixture(inputs={"prompt": 123}))


def test_task_fixture_rejects_non_string_id():
    with pytest.raises(L.ValidationError):
        L.TaskFixture.model_validate(_well_formed_fixture(id=5))


def test_task_fixture_rejects_unknown_top_level_key():
    # extra="forbid": an unexpected top-level key is far more likely a typo
    # (e.g. "expcted:") than a legitimate new field -- see TaskFixture's
    # own docstring.
    with pytest.raises(L.ValidationError):
        L.TaskFixture.model_validate(_well_formed_fixture(expcted={}))


def test_task_fixture_accepts_bare_string_tags():
    # A bare scalar tags value is one tag, not an authoring mistake -- see
    # _as_tag_list's own docstring.
    fixture = L.TaskFixture.model_validate(_well_formed_fixture(tags="adversarial"))
    assert fixture.tags == "adversarial"
    assert L._as_tag_list(fixture.tags) == ["adversarial"]


def test_task_fixture_accepts_list_tags():
    fixture = L.TaskFixture.model_validate(_well_formed_fixture(tags=["quality", "adversarial"]))
    assert fixture.tags == ["quality", "adversarial"]


def test_task_fixture_accepts_missing_description_and_tags():
    # Neither is required -- confirmed against this repository's own test
    # helper (_write_task) fixtures, which omit both.
    fixture = L.TaskFixture.model_validate(_well_formed_fixture())
    assert fixture.description is None
    assert fixture.tags is None


def test_expected_block_preserves_fields_this_linter_does_not_itself_read():
    # A fixture may carry expected.* keys this linter itself never reads
    # (issue #860: 18 merge-retrospective fixtures once carried three such
    # keys with no consumer anywhere -- they were removed rather than kept
    # as dead weight). Whatever unread key does turn up must still survive
    # -- extra="allow" round-trips it through model_dump() rather than
    # silently dropping it.
    fixture = L.TaskFixture.model_validate(
        _well_formed_fixture(
            expected={
                "output_contains": ["x"],
                "some_future_scorer_field": ["missing-deterministic-gate"],
                "another_unread_field": 2,
            }
        )
    )
    dumped = fixture.model_dump()
    assert dumped["expected"]["some_future_scorer_field"] == ["missing-deterministic-gate"]
    assert dumped["expected"]["another_unread_field"] == 2


def test_near_assertion_rejects_missing_all():
    with pytest.raises(L.ValidationError):
        L.TaskFixture.model_validate(
            _well_formed_fixture(
                expected={
                    "output_contains_near": [{"window": 100}],
                }
            )
        )


def test_near_assertion_defaults_window_to_400():
    fixture = L.TaskFixture.model_validate(
        _well_formed_fixture(
            expected={
                "output_contains_near": [{"all": ["a", "b"]}],
            }
        )
    )
    assert fixture.expected.output_contains_near[0].window == 400


def test_load_fixture_dict_falls_back_on_malformed_expected(tmp_path):
    # A fixture whose "expected" block is the wrong type fails TaskFixture
    # validation; _load_fixture_dict falls back to the bare parsed YAML
    # rather than raising, matching this function's callers' pre-pydantic
    # tolerance for a malformed shape they cannot validate but must not
    # crash on (see check_dispatch_declaration_coverage's own tests).
    path = tmp_path / "bad.yaml"
    path.write_text("id: t\nname: T\ninputs:\n  prompt: p\nexpected: todo\n", encoding="utf-8")
    assert L._load_fixture_dict(path) == {"id": "t", "name": "T", "inputs": {"prompt": "p"}, "expected": "todo"}


def test_load_fixture_dict_validates_well_formed_fixture(tmp_path):
    path = tmp_path / "good.yaml"
    path.write_text("id: t\nname: T\ninputs:\n  prompt: p\nexpected:\n  output_contains:\n    - x\n", encoding="utf-8")
    data = L._load_fixture_dict(path)
    assert data["id"] == "t"
    assert data["expected"]["output_contains"] == ["x"]


def test_lint_skill_tasks_reports_malformed_fixture_without_raising(tmp_path):
    # A malformed fixture (missing the required "inputs" block) is reported
    # as its own blocking Warning_ naming the file, rather than raising --
    # see lint_skill_tasks' own docstring for why (Decision-12 adversarial
    # review: an earlier version let ValidationError propagate unguarded,
    # aborting the whole multi-skill run for one bad file).
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    bad = tasks / "t.yaml"
    bad.write_text("id: t\nname: T\nexpected:\n  output_contains: []\n", encoding="utf-8")
    rubric, skill = _corpus_files(tmp_path)
    warnings, task_data = L.lint_skill_tasks([bad], L.load_corpus(rubric, skill))
    assert len(warnings) == 1
    assert warnings[0].blocking
    assert warnings[0].rule == "fixture-shape"
    assert str(bad) in warnings[0].detail
    assert task_data == {}


def test_lint_skill_tasks_isolates_a_malformed_fixture_from_its_siblings(tmp_path):
    # The point of the fix: one malformed fixture must not prevent a
    # sibling, well-formed fixture in the same skill from being linted.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    bad = tasks / "bad.yaml"
    bad.write_text("id: t\nname: T\nexpected:\n  output_contains: []\n", encoding="utf-8")
    (tasks / "good.yaml").write_text(
        "id: g\nname: G\ninputs:\n  prompt: |\n    p\nexpected:\n"
        '  output_contains:\n    - "Blind spot pass"\n'
        '  output_not_contains:\n    - "LGTM"\n',
        encoding="utf-8",
    )
    rubric, skill = _corpus_files(tmp_path)
    warnings, task_data = L.lint_skill_tasks([bad, tasks / "good.yaml"], L.load_corpus(rubric, skill))
    assert [w for w in warnings if w.rule == "fixture-shape"]
    assert bad not in task_data
    assert (tasks / "good.yaml") in task_data


def test_lint_skill_tasks_isolates_a_yaml_syntax_error_from_its_siblings(tmp_path):
    # A second adversarial pass (post-merge) found the isolation fix above
    # only caught pydantic.ValidationError -- a genuine YAML *syntax* error
    # (not just the wrong shape) raised out of yaml.safe_load itself,
    # outside that try/except, reopening the exact whole-run-abort gap the
    # first fix closed. Confirmed by direct execution: an unterminated
    # quoted scalar colliding with the next block key.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    bad = tasks / "bad.yaml"
    bad.write_text(
        'id: broken\nname: "unterminated quote causes scanner error\ninputs:\n  prompt: "hello"\n', encoding="utf-8"
    )
    (tasks / "good.yaml").write_text(
        "id: g\nname: G\ninputs:\n  prompt: |\n    p\nexpected:\n"
        '  output_contains:\n    - "Blind spot pass"\n'
        '  output_not_contains:\n    - "LGTM"\n',
        encoding="utf-8",
    )
    rubric, skill = _corpus_files(tmp_path)
    warnings, task_data = L.lint_skill_tasks([bad, tasks / "good.yaml"], L.load_corpus(rubric, skill))
    assert [w for w in warnings if w.rule == "fixture-shape" and str(bad) in w.detail]
    assert bad not in task_data
    assert (tasks / "good.yaml") in task_data


def test_lint_skill_tasks_isolates_a_non_utf8_fixture_from_its_siblings(tmp_path):
    # A THIRD adversarial pass (still post-merge) found the widened guard
    # above still didn't cover a non-UTF-8 fixture: path.read_text(
    # encoding="utf-8") itself raises UnicodeDecodeError before
    # yaml.safe_load ever runs, which the (yaml.YAMLError, ValidationError)
    # catch from the second round did not include. Confirmed by direct
    # execution with a raw invalid byte sequence.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    bad = tasks / "bad.yaml"
    bad.write_bytes(b"id: t1\nname: \xff\xfe bad utf8\n")
    (tasks / "good.yaml").write_text(
        "id: g\nname: G\ninputs:\n  prompt: |\n    p\nexpected:\n"
        '  output_contains:\n    - "Blind spot pass"\n'
        '  output_not_contains:\n    - "LGTM"\n',
        encoding="utf-8",
    )
    rubric, skill = _corpus_files(tmp_path)
    warnings, task_data = L.lint_skill_tasks([bad, tasks / "good.yaml"], L.load_corpus(rubric, skill))
    assert [w for w in warnings if w.rule == "fixture-shape" and str(bad) in w.detail]
    assert bad not in task_data
    assert (tasks / "good.yaml") in task_data


def test_load_fixture_dict_falls_back_to_empty_dict_on_non_utf8_content(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_bytes(b"id: t1\nname: \xff\xfe bad utf8\n")
    assert L._load_fixture_dict(path) == {}


def test_load_fixture_dict_falls_back_to_empty_dict_on_yaml_syntax_error(tmp_path):
    # Same YAML-syntax-error gap as above, in _load_fixture_dict's own
    # separate call sites (check_adversarial_coverage/
    # check_dispatch_declaration_coverage's task_data-is-None fallback).
    # There is no parsed value to fall back to on a genuine parse error,
    # unlike the wrong-shape case, so this returns {} rather than raising.
    path = tmp_path / "bad.yaml"
    path.write_text('name: "unterminated\ninputs:\n  prompt: x\n', encoding="utf-8")
    assert L._load_fixture_dict(path) == {}


def test_main_reports_malformed_fixture_as_a_blocking_warning_exit_1(tmp_path):
    # End to end: main() surfaces the malformed-fixture Warning_ via the
    # normal report/exit-code path (exit 1, a blocking warning), not the
    # exit-2 unparsable-input path -- the file is readable YAML, just the
    # wrong shape, and the report names it instead of crashing.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "t.yaml").write_text("id: t\nname: T\nexpected:\n  output_contains: []\n", encoding="utf-8")
    rubric, skill = _corpus_files(tmp_path)
    assert L.main(["--tasks-glob", str(tasks / "*.yaml"), "--rubric", str(rubric), "--skill", str(skill)]) == 1
