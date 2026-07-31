"""Reconstructs the load test's 24 candidate why-not comments and scores
each with the repository's existing *mechanical* scorer
(``skills/scorer-gated-skill-edits/scripts/score_contract.py``'s
``score()``), to quantify what the prior, pre-#625 evaluation approach
(substring/format presence only) would have said about the same fabricated
candidates the semantic scorer (``score_semantic_rationale.py``) caught.

Run: ``python3 evals/semantic-rationale-load-test/mechanical_baseline.py``
"""

from __future__ import annotations

import importlib.util
import json
import pathlib

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SCORE_CONTRACT_PATH = (
    _REPO_ROOT / "skills/scorer-gated-skill-edits/scripts/score_contract.py"
)

_spec = importlib.util.spec_from_file_location("score_contract", _SCORE_CONTRACT_PATH)
score_contract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score_contract)

# Verbatim from load-test.workflow.js's CASES (citation, reason only --
# sourceText omitted, not needed to reconstruct the candidate comment text).
CASES = [
    {
        "id": "score_contract_near_check",
        "citation": "#421",
        "reason": (
            "a window-only check lets two occurrences straddle a fully "
            'separate, unrelated paragraph and still false-pass as "near"'
        ),
    },
    {
        "id": "gate_split_fixture_coverage_check_a",
        "citation": "issue #191, repair 1",
        "reason": (
            "without an exemption, every narrow single-fixture recheck "
            "dispatch would falsely trip the full-corpus superset "
            "requirement, since such a dispatch by construction never "
            "claims full-corpus coverage -- this would break the "
            "established recheck convention used for narrower rechecks "
            "after a small follow-up fix"
        ),
    },
    {
        "id": "run_ablation_bare_mode",
        "citation": "#583",
        "reason": (
            "--bare explicitly disables the very skill-discovery "
            "mechanism a staged directory depends on, so the two "
            "approaches are mutually exclusive, not a fidelity dial with "
            "a middle setting"
        ),
    },
    {
        "id": "check_skill_shape_no_illustrative_model_id",
        "citation": "#470",
        "reason": (
            "a real current model identifier goes stale the moment that "
            "model is superseded, and duplicates what this repository's "
            "own gate_provenance_disclosure.py is meant to catch"
        ),
    },
    {
        "id": "lint_fixture_assertions_collision_pairs",
        "citation": "#518",
        "reason": (
            "a dictionary scan false-flagged this repository's own "
            'deliberately-truncated stem assertions, like "emporal" for '
            'temporal and "hardcod" for hardcode(d), which are not real '
            "dictionary words themselves"
        ),
    },
    {
        "id": "gate_skill_branch_fixture_coverage_growth_only",
        "citation": "#540",
        "reason": (
            "only a net GROWTH in the Stop-boundary-bullet-plus-dispatch-"
            "branch count actually adds untested behavioral surface; a "
            "deletion or a neutral reword does not, so gating on growth "
            "alone avoids demanding fixtures for changes that removed or "
            "merely re-worded existing, already-covered branches"
        ),
    },
    {
        "id": "gate_transfer_check_disclosure_structural_no_op",
        "citation": "#552",
        "reason": (
            "the gate only mechanically parses the bold **Iteration: "
            "line convention under a specific ## Kept-edit log heading; "
            "a split.md using plain ## Iteration: H2 headings instead is "
            "a structural no-op for this gate by construction, not a "
            "violation the gate fails to catch"
        ),
    },
    {
        "id": "gate_retro_title_convention_citation_narrow_scope",
        "citation": "#520",
        "reason": (
            "the gate is deliberately narrowed to only a convention-claim "
            'paragraph that also names a title/identity concept (the '
            'word "title" or "identity" nearby); a bare "this repo\'s own '
            'convention" claim about, say, ASCII formatting or a scoring '
            "rubric is a different claim class this gate does not "
            "police, and widening it to every convention claim would "
            "require citations this repository does not actually expect "
            "for those other claim classes"
        ),
    },
]


def candidate_comment(citation: str, reason: str) -> str:
    return f"# why-not({citation}): {reason}"


def build_variants() -> list[dict]:
    variants = []
    for i, c in enumerate(CASES):
        nxt = CASES[(i + 1) % len(CASES)]
        variants.append(
            {"caseId": c["id"], "variant": "genuine", "text": candidate_comment(c["citation"], c["reason"])}
        )
        variants.append(
            {"caseId": c["id"], "variant": "wrongReason", "text": candidate_comment(c["citation"], nxt["reason"])}
        )
        variants.append(
            {"caseId": c["id"], "variant": "wrongCitation", "text": candidate_comment(nxt["citation"], c["reason"])}
        )
    return variants


# The "before" baseline: the mechanical, format-only assertion style this
# repo's own SKILL.md says IS a good fit for "a small lint-hook or
# pre-commit check" (the `why-not(#NNN):` prefix, line length) -- i.e.
# exactly score_contract.py's substring-presence style, applied to the ONLY
# thing a substring check can observe: structural shape, never whether the
# claimed reason or citation is actually true of the cited source.
_MECHANICAL_ASSERTIONS = {
    "output_contains": ["why-not(", ":"],
    "output_not_contains": ["TODO", "FIXME"],
}


def main() -> int:
    variants = build_variants()
    by_variant: dict[str, list[float]] = {}
    for v in variants:
        s = score_contract.score(v["text"], _MECHANICAL_ASSERTIONS)
        by_variant.setdefault(v["variant"], []).append(s)

    summary = {
        variant: {
            "n": len(scores),
            "meanScore": sum(scores) / len(scores),
            "allPass": all(s == 1.0 for s in scores),
        }
        for variant, scores in by_variant.items()
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
