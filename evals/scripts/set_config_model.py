#!/usr/bin/env python3
"""Override the ``config.model`` of a waza ``eval.yaml`` in place.

waza 0.38.0 selects the model from an ``eval.yaml`` field (``config.model``)
and exposes no ``--model`` flag on ``waza run`` -- verified against the waza
CLI reference (``waza run [skill] [-v] [-o <file>]``). A cross-model matrix
therefore cannot be driven from the command line; each model tier needs the
suite's ``config.model`` rewritten before the run.

This tool is that rewrite, kept deliberately narrow so the matrix workflow
stays deterministic (CLAUDE.md section 3): given one committed ``eval.yaml``
and one model id, it replaces the ``model:`` line *inside the ``config:``
block* and leaves everything else -- comments, key order, the grader-level
``model:`` of an ``llm`` grader if one is ever added -- byte-for-byte intact.
It edits in place because the matrix runs it on an ephemeral CI checkout, not
on a committed tree; the committed suites stay pinned to their default model.

Fail-loud contract (CLAUDE.md section 4): if the ``config:`` block or its
``model:`` line is missing, or if ``config`` carries more than one ``model:``
line, it raises rather than guessing or silently no-op'ing -- a suite that
does not get its model overridden would otherwise run the wrong tier and be
silently mislabelled in the matrix results.

Usage::

    python3 evals/scripts/set_config_model.py <eval.yaml> <model-id>

Run standalone (exit 1 on any violation) or via the pytest gate in
``tests/test_set_config_model.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path


def set_config_model(text: str, model: str) -> str:
    """Return ``text`` with the ``config.model`` line rewritten to ``model``.

    ``text`` is the full ``eval.yaml`` source. The ``config:`` block is the run
    of lines from a top-level ``config:`` key up to (but not including) the next
    top-level key -- a top-level key being one with no leading whitespace. The
    single ``model:`` line within that run is replaced, its original
    indentation preserved. Any ``model:`` outside the ``config:`` block (for
    example a grader's) is left untouched.
    """
    if not model or model != model.strip():
        raise ValueError(f"model id must be non-empty and unpadded, got {model!r}")

    lines = text.splitlines(keepends=True)

    config_start = None
    for i, line in enumerate(lines):
        if line.rstrip("\n") == "config:" or line.startswith("config:"):
            config_start = i
            break
    if config_start is None:
        raise ValueError("no top-level 'config:' block found in eval.yaml")

    # The block runs until the next line that starts a new top-level key
    # (non-space, non-comment first character).
    config_end = len(lines)
    for i in range(config_start + 1, len(lines)):
        stripped = lines[i]
        if stripped.strip() == "" or stripped.lstrip().startswith("#"):
            continue
        if not stripped[:1].isspace():
            config_end = i
            break

    model_line_idxs = [
        i
        for i in range(config_start + 1, config_end)
        if lines[i].lstrip().startswith("model:")
    ]
    if len(model_line_idxs) == 0:
        raise ValueError("no 'model:' line inside the 'config:' block")
    if len(model_line_idxs) > 1:
        raise ValueError(
            f"expected exactly one 'model:' line in 'config:', found {len(model_line_idxs)}"
        )

    idx = model_line_idxs[0]
    original = lines[idx]
    indent = original[: len(original) - len(original.lstrip())]
    newline = "\n" if original.endswith("\n") else ""
    lines[idx] = f"{indent}model: {model}{newline}"
    return "".join(lines)


def override_file(path: Path, model: str) -> None:
    """Rewrite ``path`` in place, setting ``config.model`` to ``model``."""
    text = path.read_text(encoding="utf-8")
    path.write_text(set_config_model(text, model), encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "usage: set_config_model.py <eval.yaml> <model-id>",
            file=sys.stderr,
        )
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"error: not a file: {path}", file=sys.stderr)
        return 1
    try:
        override_file(path, argv[2])
    except ValueError as exc:
        print(f"error: {path}: {exc}", file=sys.stderr)
        return 1
    print(f"{path}: config.model -> {argv[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
