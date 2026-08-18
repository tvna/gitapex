"""Tests for evals/scripts/gitapex_compute_waza_advisory_metrics.py (issue
#1144).

Hand-built text fixtures with known counts exercise both counting
functions' exact boundaries; the real-corpus checks at the bottom are the
same "does not just pass a synthetic fixture" discipline
test_gitapex_run_effectiveness_correlation.py's own real-committed-corpus
test already established for this directory -- a regex tuned only against
invented text could still be constant-zero (or otherwise degenerate)
against real ``SKILL.md`` prose, which is exactly the failure mode this
module's own docstring discloses discovering and calibrating against.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import gitapex_compute_waza_advisory_metrics as m
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# skills/drafting-a-pr-to-merge/SKILL.md: confirmed at calibration time to
# contain both a real sentence-initial "Never" hit (three, in fact) and a
# real "## Worked example" heading -- one real file exercising both
# functions, rather than two cherry-picked single-purpose files.
REAL_SKILL_MD_WITH_KNOWN_HITS = REPO_ROOT / "skills" / "drafting-a-pr-to-merge" / "SKILL.md"

# ---------------------------------------------------------------------------
# strip_frontmatter
# ---------------------------------------------------------------------------


def test_strip_frontmatter_removes_well_formed_block() -> None:
    text = "---\nname: demo\ndescription: Never mentioned here.\n---\nBody starts here.\n"
    assert m.strip_frontmatter(text) == "Body starts here.\n"


def test_strip_frontmatter_leaves_frontmatter_prose_out_of_the_body() -> None:
    # The whole point: a description field's own prose must never reach the
    # counting functions below, even if it contains "Never"/"Must"/"Always".
    text = "---\ndescription: Must always never do this.\n---\nAlways do this in the body.\n"
    body = m.strip_frontmatter(text)
    assert "Must always never" not in body
    assert "Always do this" in body


def test_strip_frontmatter_returns_unchanged_when_no_leading_marker() -> None:
    text = "# Just a heading\nNo frontmatter at all.\n"
    assert m.strip_frontmatter(text) == text


def test_strip_frontmatter_returns_unchanged_when_closing_marker_missing() -> None:
    text = "---\nname: demo\nno closing marker here\n"
    assert m.strip_frontmatter(text) == text


def test_strip_frontmatter_returns_unchanged_on_empty_text() -> None:
    assert m.strip_frontmatter("") == ""


def test_strip_frontmatter_strips_crlf_terminated_block() -> None:
    # Regression (code review finding): a CRLF-authored file's first line
    # is "---\r\n", not "---\n" -- rstrip("\n") alone leaves a trailing
    # "\r" that never equals "---", silently failing to strip frontmatter
    # at all and leaking a description field's own prose (which can
    # itself contain "Never"/"Must"/"Always") into the body.
    text = "---\r\ndescription: Never mentioned here.\r\n---\r\nBody starts here.\r\n"
    body = m.strip_frontmatter(text)
    assert "Never mentioned here" not in body
    assert "Body starts here" in body


# ---------------------------------------------------------------------------
# count_constraint_signals
# ---------------------------------------------------------------------------


def test_count_constraint_signals_zero_on_empty_body() -> None:
    assert m.count_constraint_signals("") == 0


def test_count_constraint_signals_zero_when_no_constraint_language() -> None:
    assert m.count_constraint_signals("This is an ordinary paragraph with no constraints.\n") == 0


@pytest.mark.parametrize("word", ["Must", "Never", "Always"])
def test_count_constraint_signals_counts_line_initial_occurrence(word: str) -> None:
    assert m.count_constraint_signals(f"{word} do the thing.\n") == 1


@pytest.mark.parametrize("word", ["Must", "Never", "Always"])
def test_count_constraint_signals_counts_sentence_initial_occurrence(word: str) -> None:
    assert m.count_constraint_signals(f"Do the first thing. {word} do the second thing.\n") == 1


def test_count_constraint_signals_counts_bullet_initial_occurrence() -> None:
    # Regression: this repository's own dominant convention for stating a
    # constraint is a Markdown list item ("- Never do X"), not a
    # free-standing sentence -- 124 of 146 real corpus hits at calibration
    # time (see module docstring's "Bullets dominate" section). The
    # pattern must explicitly allow a "- "/"* " marker between the line
    # start and the constraint word, since `^` alone only matches the
    # dash itself, not the word that follows it.
    body = "- Never do this.\n- Always do that.\n* Must also do this.\n"
    assert m.count_constraint_signals(body) == 3


def test_count_constraint_signals_counts_numbered_list_initial_occurrence() -> None:
    body = "1. Never do this.\n2. Always do that.\n"
    assert m.count_constraint_signals(body) == 2


def test_count_constraint_signals_counts_indented_bullet() -> None:
    # A nested/indented list item ("  - Never...") is still a bullet-
    # initial constraint statement, not mid-sentence prose.
    body = "- Top level.\n  - Never do the nested thing.\n"
    assert m.count_constraint_signals(body) == 1


def test_count_constraint_signals_does_not_match_bare_lowercase() -> None:
    # "always"/"never" mid-sentence, lowercase, is ordinary English prose
    # ("this always happens"), not a constraint statement -- see module
    # docstring's "Why calibrated, not literal" section.
    assert m.count_constraint_signals("This always happens and we never mind.\n") == 0


def test_count_constraint_signals_does_not_match_shouting_case() -> None:
    # Regression: this repository writes constraint language in ordinary
    # sentence case, never shouting case -- a literal MUST/NEVER/ALWAYS
    # match is 0 across the entire real corpus (see module docstring).
    assert m.count_constraint_signals("NEVER do the thing.\n") == 0


def test_count_constraint_signals_does_not_match_mid_sentence_after_comma() -> None:
    # A comma is not a sentence boundary -- only `.`/`!`/`?` followed by
    # whitespace, or a literal line start, count.
    assert m.count_constraint_signals("As a rule, Never do the thing.\n") == 0


def test_count_constraint_signals_counts_multiple_occurrences_non_overlapping() -> None:
    body = "Never do X. Always do Y. Must also do Z.\n"
    assert m.count_constraint_signals(body) == 3


# ---------------------------------------------------------------------------
# count_body_structure_signals
# ---------------------------------------------------------------------------


def test_count_body_structure_signals_zero_when_neither_heading_present() -> None:
    assert m.count_body_structure_signals("## Some other heading\ncontent\n") == 0


@pytest.mark.parametrize(
    "heading",
    ["## Worked example", "## worked example", "## Worked Example", "## Worked examples", "## Example", "## Examples"],
)
def test_count_body_structure_signals_one_for_worked_example_variants(heading: str) -> None:
    assert m.count_body_structure_signals(f"{heading}\ncontent\n") == 1


@pytest.mark.parametrize("heading", ["## Error handling", "## error handling", "## Troubleshooting"])
def test_count_body_structure_signals_one_for_error_handling_variants(heading: str) -> None:
    assert m.count_body_structure_signals(f"{heading}\ncontent\n") == 1


def test_count_body_structure_signals_two_when_both_present() -> None:
    body = "## Worked example\nfoo\n## Troubleshooting\nbar\n"
    assert m.count_body_structure_signals(body) == 2


def test_count_body_structure_signals_requires_heading_marker_not_bare_text() -> None:
    # "Examples" appearing in prose, not as a heading, must not count --
    # only a genuine '##'-or-deeper heading line is a structural signal.
    assert m.count_body_structure_signals("See the examples below for details.\n") == 0


def test_count_body_structure_signals_ignores_level_one_title() -> None:
    # A skill's own top-level title is always a single '#', never counted
    # as a body-structure section heading (real convention confirmed: '#'
    # for the title, '##' for every section including 'Worked example').
    assert m.count_body_structure_signals("# Examples\ncontent\n") == 0


def test_count_body_structure_signals_rejects_hyphenated_compound_word() -> None:
    # Regression (code review finding): a heading merely STARTING with
    # "Example"/"Error handling" is not the same as a genuine worked
    # -example or error-handling section -- a directly-hyphenated compound
    # word ("Example-Based Testing", a real, unrelated testing-methodology
    # term) would otherwise still satisfy a bare `\b` word boundary.
    assert m.count_body_structure_signals("## Example-Based Testing Notes\ncontent\n") == 0
    assert m.count_body_structure_signals("## Error Handling-First Design\ncontent\n") == 0


def test_count_body_structure_signals_still_counts_heading_with_trailing_detail() -> None:
    # The hyphen exclusion above must not overreach: a heading followed by
    # a space, colon, or end of line is still a genuine match.
    assert m.count_body_structure_signals("## Worked example: renaming a variable\ncontent\n") == 1
    assert m.count_body_structure_signals("## Examples of failure modes\ncontent\n") == 1


def test_count_body_structure_signals_does_not_span_an_empty_heading_into_the_next_line() -> None:
    # Regression (code review finding): `\s` also matches a newline, so an
    # earlier `\s+` separator let a heading marker on its OWN line ("##",
    # empty per real CommonMark) span into unrelated text on the next line
    # ("Examples") and still match, even though that text is a separate
    # paragraph, not part of any heading. `[ \t]+` (horizontal whitespace
    # only) must not cross the line boundary.
    assert m.count_body_structure_signals("##\nExamples\n") == 0
    assert m.count_body_structure_signals("## Error\nhandling\n") == 0
    assert m.count_body_structure_signals("##\nWorked\n") == 0


# ---------------------------------------------------------------------------
# Real-corpus sanity checks (not an exact reverse-engineered number, see
# module docstring's "NOT a reverse-engineered copy" section)
# ---------------------------------------------------------------------------


def test_count_constraint_signals_against_real_skill_md_is_positive() -> None:
    text = REAL_SKILL_MD_WITH_KNOWN_HITS.read_text(encoding="utf-8")
    body = m.strip_frontmatter(text)
    assert m.count_constraint_signals(body) > 0


def test_count_body_structure_signals_against_real_skill_md_is_positive() -> None:
    text = REAL_SKILL_MD_WITH_KNOWN_HITS.read_text(encoding="utf-8")
    body = m.strip_frontmatter(text)
    assert m.count_body_structure_signals(body) > 0


def test_metrics_are_non_constant_across_the_real_corpus() -> None:
    # The literal defeat case this module's own docstring discloses
    # discovering: a metric that is constant across every real skill would
    # crash gitapex_compute_rank_correlation.spearman_rho the moment a real
    # correlation run is attempted. This is the committed regression proof
    # that both metrics stay non-constant as the corpus evolves -- not just
    # true at calibration time.
    skill_mds = sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))
    assert len(skill_mds) >= 2
    constraint_counts: set[int] = set()
    body_structure_counts: set[int] = set()
    for path in skill_mds:
        body = m.strip_frontmatter(path.read_text(encoding="utf-8"))
        constraint_counts.add(m.count_constraint_signals(body))
        body_structure_counts.add(m.count_body_structure_signals(body))
    assert len(constraint_counts) > 1, "negative-delta-risk metric is constant across the real corpus"
    assert len(body_structure_counts) > 1, "body-structure metric is constant across the real corpus"


# ---------------------------------------------------------------------------
# main() -- CLI, pydantic-validated args (same shape as this directory's
# other CLIs, e.g. gitapex_compute_rank_correlation.py's own main() tests)
# ---------------------------------------------------------------------------


def test_main_happy_path_exits_zero_and_prints_json(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = m.main(["--skill-md", str(REAL_SKILL_MD_WITH_KNOWN_HITS)])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["skill_md"] == str(REAL_SKILL_MD_WITH_KNOWN_HITS)
    assert payload["negative_delta_risk"] > 0
    assert payload["body_structure"] > 0


def test_main_json_values_match_calling_the_functions_directly(capsys: pytest.CaptureFixture[str]) -> None:
    # Regression: main() must be a thin CLI wrapper, never a second,
    # divergent implementation of the counting logic -- its own JSON
    # output has to match count_constraint_signals/count_body_structure_
    # signals exactly, not just both being positive.
    exit_code = m.main(["--skill-md", str(REAL_SKILL_MD_WITH_KNOWN_HITS)])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)

    text = REAL_SKILL_MD_WITH_KNOWN_HITS.read_text(encoding="utf-8")
    body = m.strip_frontmatter(text)
    assert payload["negative_delta_risk"] == m.count_constraint_signals(body)
    assert payload["body_structure"] == m.count_body_structure_signals(body)


def test_main_missing_skill_md_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "no-such-SKILL.md"
    exit_code = m.main(["--skill-md", str(missing)])
    assert exit_code == 2
    assert "skill file not found" in capsys.readouterr().err


def test_main_non_utf8_skill_md_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_bytes(b"---\nname: demo\n---\n\xff\xfe bad bytes\n")
    exit_code = m.main(["--skill-md", str(skill_md)])
    assert exit_code == 2
    assert "cannot read" in capsys.readouterr().err


def test_direct_invocation_does_not_crash_on_imports() -> None:
    # Regression: this module's own CLI must resolve `import pydantic`
    # (a real third-party dependency) outside pytest's own pythonpath
    # configuration too, the same way gitapex_run_ablation.py's own
    # test_direct_invocation_does_not_crash_on_score_contract_import
    # guards its own bare-`python3`-vs-`uv run` import resolution.
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "evals" / "scripts" / "gitapex_compute_waza_advisory_metrics.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "ModuleNotFoundError" not in result.stderr
    assert "usage:" in result.stdout.lower()
