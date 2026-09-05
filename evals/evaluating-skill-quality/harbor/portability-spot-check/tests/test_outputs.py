"""Pytest checks for the portability spot-check trial.

The agent must classify three skill shapes per the rule set in
instruction.md. Expected: A=Portable, B=Mixed-via-bundled-convention,
C=Repository-scoped (sibling fan-out -- the rule working as designed).
"""

import json
from pathlib import Path


def test_outputs():
    """Test that the outputs are correct."""
    verdict = json.loads(Path("/app/verdict.json").read_text())
    assert verdict == {
        "case_a": "Portable",
        "case_b": "Mixed-via-bundled-convention",
        "case_c": "Repository-scoped",
    }
