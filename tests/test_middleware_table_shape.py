"""Integration gate: the middleware inventory's per-section tables pass
the deterministic table-shape checker.

Mirrors test_agent_product_scope_shape.py's own rationale for
check_axis_shape.py: this runs check_middleware_table_shape.py against
the live references/middleware-inventory.md as part of the
repository's enforced pytest run, not only via a manual skill step, so
a column or expected row silently disappearing would fail CI.
"""

from pathlib import Path

import check_middleware_table_shape as cmts

REPO_ROOT = Path(__file__).resolve().parents[1]
MIDDLEWARE_INVENTORY = REPO_ROOT / "skills" / "auditing-agent-product-scope" / "references" / "middleware-inventory.md"


def test_middleware_inventory_passes_table_shape():
    body_text = MIDDLEWARE_INVENTORY.read_text(encoding="utf-8")
    offenses = cmts.check_middleware_table_shape(body_text)
    assert not offenses, "; ".join(offenses)
