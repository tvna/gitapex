"""Integration gate: docs/agent-product-scope.md passes the deterministic
axis-shape checker.

A Codex review on PR #451 found that gitapex_check_axis_shape.py existed but was
invoked only by a manual SKILL.md Step 8 command, with no CI path
actually running it against the live document -- dropping a required
field or introducing an invalid axis could merge whenever an author
skipped that manual step. This test runs the same gitapex_check_axis_shape.py
over the repository's real docs/agent-product-scope.md, so the invariant
is enforced by the test.yml pytest run, not only by an author's memory
(mirrors test_gitapex_repository_skill_shape.py's own rationale for gating
gitapex_check_skill_shape.py the same way).
"""

from pathlib import Path

import gitapex_check_axis_shape as cas

REPO_ROOT = Path(__file__).resolve().parents[1]
SCOPE_MAP = REPO_ROOT / "docs" / "agent-product-scope.md"


def test_agent_product_scope_doc_passes_axis_shape():
    body_text = SCOPE_MAP.read_text(encoding="utf-8")
    offenses = cas.gitapex_check_axis_shape(body_text)
    assert not offenses, "; ".join(offenses)
