"""Tests for the eval-fixture assertion linter.

Unit tests run each heuristic against a small synthetic corpus so they are
self-contained; one integration test runs the linter against the repository's
real fixture set and pins it to zero warnings, which is issue #170's first
acceptance criterion.
"""
from pathlib import Path

import pytest

import lint_fixture_assertions as L

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
    _write_task(tasks, {"output_contains": ["Blind spot pass"],
                        "output_not_contains": ["LGTM"]})
    rubric, skill = _corpus_files(tmp_path)
    assert L.main(["--tasks-glob", str(tasks / "*.yaml"),
                   "--rubric", str(rubric), "--skill", str(skill)]) == 0


def test_main_buggy_task_exits_one(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_task(tasks, {"output_contains": ["blind spot"],
                        "output_not_contains": ["tenth dimension"]})
    rubric, skill = _corpus_files(tmp_path)
    assert L.main(["--tasks-glob", str(tasks / "*.yaml"),
                   "--rubric", str(rubric), "--skill", str(skill)]) == 1


def test_main_missing_corpus_exits_two(tmp_path):
    assert L.main(["--tasks-glob", str(tmp_path / "*.yaml"),
                   "--rubric", str(tmp_path / "nope.md"),
                   "--skill", str(tmp_path / "nope2.md")]) == 2


def test_main_no_tasks_exits_two(tmp_path):
    rubric, skill = _corpus_files(tmp_path)
    assert L.main(["--tasks-glob", str(tmp_path / "none" / "*.yaml"),
                   "--rubric", str(rubric), "--skill", str(skill)]) == 2


def test_repository_fixtures_are_clean():
    # Issue #170 acceptance criterion 1: the current fixture set produces
    # zero warnings. Runs against the real repo paths so it stays a live gate.
    rc = L.main([
        "--tasks-glob", str(REPO_ROOT / "evals/evaluating-skill-quality/tasks/*.yaml"),
        "--rubric", str(REPO_ROOT / L.DEFAULT_RUBRIC),
        "--skill", str(REPO_ROOT / L.DEFAULT_SKILL),
    ])
    assert rc == 0


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
        "id": "t", "name": "T",
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
    detail = L.check_symmetric_bans(_indeterminate_task(
        ["no force-push occurred", "A force-push occurred"]))
    assert detail is None


def test_symmetric_bans_flags_no_bans_at_all():
    detail = L.check_symmetric_bans(_indeterminate_task([]))
    assert detail is not None


def test_symmetric_bans_ignores_ordinary_fixture():
    # No "cannot be determined"-style marker: an ordinary fixture with only
    # a negative-direction ban is not held to the symmetric-ban rule.
    ordinary = {
        "id": "t", "name": "T", "description": "An ordinary review fixture.",
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
        "id": "t", "name": "T",
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
    assert L.check_cross_task_collision(
        "self.yaml", "not applicable", index) == "other.yaml"


def test_cross_task_collision_ignores_own_task():
    index = {"self.yaml": {"not applicable"}}
    assert L.check_cross_task_collision("self.yaml", "not applicable", index) is None


def test_cross_task_collision_excludes_enum_style_token():
    # This repository's closed-enum classification fixtures deliberately
    # ban sibling UPPER_SNAKE_CASE labels -- a correct design, not a bug.
    index = {"other.yaml": {"status: no_compatibility_warning"}}
    assert L.check_cross_task_collision(
        "self.yaml", "Status: NO_COMPATIBILITY_WARNING", index) is None


# ---- check_adversarial_coverage (issue #516, #473 -- discovery mode only) ----

def _write_yaml(path, tags):
    path.write_text(
        "id: t\nname: T\ninputs:\n  prompt: p\ntags:\n" +
        "".join(f"  - {t}\n" for t in tags) + "expected:\n  output_contains: []\n",
        encoding="utf-8")


def test_adversarial_coverage_flags_claim_without_tag(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_yaml(tasks / "t.yaml", ["quality"])
    detail = L.check_adversarial_coverage(
        "some-skill", tasks, "This skill covers 22 adversarial dimensions.")
    assert detail is not None


def test_adversarial_coverage_passes_with_tagged_fixture(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    _write_yaml(tasks / "t.yaml", ["quality", "adversarial"])
    detail = L.check_adversarial_coverage(
        "some-skill", tasks, "This skill covers 22 adversarial dimensions.")
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
        body += "  requires_fresh_dispatch:\n    tool_names: [\"Agent\"]\n    min_dispatches: 1\n"
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
    assert L.check_dispatch_declaration_coverage(
        "evaluating-skill-quality", missing_dir, task_data=task_data) is None


def test_dispatch_declaration_coverage_empty_requires_fresh_dispatch_still_flags(tmp_path):
    # An empty/falsy requires_fresh_dispatch value (e.g. `requires_fresh_dispatch:`
    # with nothing under it) does not count as a real declaration.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "t.yaml").write_text(
        "id: t\nname: T\ninputs:\n  prompt: p\nexpected:\n"
        "  output_contains: []\n  requires_fresh_dispatch:\n",
        encoding="utf-8")
    detail = L.check_dispatch_declaration_coverage("evaluating-skill-quality", tasks)
    assert detail is not None


def test_dispatch_declaration_coverage_bare_truthy_value_still_flags(tmp_path):
    # A fat-fingered `requires_fresh_dispatch: true` is truthy but describes
    # no checkable tool_names/min_dispatches -- must not satisfy coverage.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "t.yaml").write_text(
        "id: t\nname: T\ninputs:\n  prompt: p\nexpected:\n"
        "  output_contains: []\n  requires_fresh_dispatch: true\n",
        encoding="utf-8")
    detail = L.check_dispatch_declaration_coverage("evaluating-skill-quality", tasks)
    assert detail is not None


def test_dispatch_declaration_coverage_zero_min_dispatches_still_flags(tmp_path):
    # requires_fresh_dispatch: {min_dispatches: 0} is a self-contradiction
    # (check_dispatch_trace.py's own `count >= min_dispatches` would report
    # "confirmed" even with zero observed dispatches) -- must not satisfy
    # coverage, matching _is_real_dispatch_declaration's own contract.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "t.yaml").write_text(
        "id: t\nname: T\ninputs:\n  prompt: p\nexpected:\n"
        "  output_contains: []\n  requires_fresh_dispatch:\n"
        "    tool_names: [\"Agent\"]\n    min_dispatches: 0\n",
        encoding="utf-8")
    detail = L.check_dispatch_declaration_coverage("evaluating-skill-quality", tasks)
    assert detail is not None


def test_dispatch_declaration_coverage_non_dict_expected_does_not_crash(tmp_path):
    # A malformed fixture (`expected: "todo"`, a stub left by mistake) must
    # not crash the lint pass with an AttributeError.
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "t.yaml").write_text(
        "id: t\nname: T\ninputs:\n  prompt: p\nexpected: todo\n",
        encoding="utf-8")
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
    # matching score_contract.py's own established bool-exclusion pattern.
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

def _write_skill_and_tasks(root, name, *, with_rubric=False,
                           expected=None):
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(CORPUS, encoding="utf-8")
    if with_rubric:
        (skill_dir / "references").mkdir()
        (skill_dir / "references" / "rubric.md").write_text(CORPUS, encoding="utf-8")
    tasks_dir = root / "evals" / name / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_task(tasks_dir, expected or {"output_contains": ["Blind spot pass"],
                                        "output_not_contains": ["LGTM"]})
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
    _write_skill_and_tasks(tmp_path, "alpha", with_rubric=True,
                           expected={"output_contains": ["blind spot"]})
    _write_skill_and_tasks(tmp_path, "beta",
                           expected={"output_not_contains": ["tenth dimension"]})
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
    rubric, skill = (tmp_path / "skills" / "alpha" / "references" / "rubric.md",
                     tmp_path / "skills" / "alpha" / "SKILL.md")
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
    assert L.check_adversarial_coverage(
        "some-skill", missing_dir, "claims adversarial coverage",
        task_data=task_data) is None
