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
