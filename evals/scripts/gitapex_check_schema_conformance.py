"""Check whether a captured evaluating-skill-quality run's output carries a
structured verdict conforming to references/output-schema.json (issue #1002).

`docs/superpowers/specs/2026-08-10-evaluating-skill-quality-output-schema-design.md`
Decision 3 names the construct-validity gap this closes:
`gitapex_score_contract.py`'s substring scorer confirms expected keywords
appear, not that the full nine-dimension walk actually ran. This checker
mirrors `gitapex_check_dispatch_trace.py`'s own role for a different gap
(issue #584): it inspects a run's own captured output for a specific,
independently-verifiable structural fact, and hands the caller a verdict to
record via `gitapex_score_contract.py --schema-conformance-verdict` --
never blending anything into the substring score itself.

Three verdicts, chosen deliberately as three states, not a boolean:

- ``SCHEMA_CONFIRMED`` -- the output carries a fenced ```json block that
  validates against the schema.
- ``SCHEMA_INVALID`` -- the output carries a fenced ```json block that is
  either not valid JSON or fails schema validation (a real defect: the
  reviewer attempted structured output and got it wrong). A ```json fence
  opened but never closed (a truncated capture) counts as this case too --
  it is an attempt that failed, not an absence of one.
- ``SCHEMA_NOT_ATTEMPTED`` -- no fenced ```json block is present at all,
  which is a legitimate outcome during the design doc's own disclosed
  opt-in adoption window (existing fixtures were never asked to produce
  one) and is distinct from an attempt that failed.

When more than one fenced ```json block is present, the *last* one is
checked -- the design doc's own Sequencing step 3 has `SKILL.md`'s
Procedure step 6 "close with" the structured block, so the last fenced
json block in the output is the one that carries the verdict; any earlier
json fence is prose the review quoted along the way (e.g. a cited
`rubric.md` worked example), not the output contract. Fence delimiters are
matched only at the start of a line (never as a bare substring), so a
quoted string value that happens to contain literal backticks, or a
defensively widened fence around quoted content, cannot be mistaken for
the real opener or closer -- see `_iter_json_fences`'s own docstring.

Standard library plus ``jsonschema`` (already a project dependency, used
the same way `_gitapex_schema_validation.py` and its own callers already
use it), matching this repository's other `evals/scripts/*.py` tooling.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_PATH = REPO_ROOT / "skills/evaluating-skill-quality/references/output-schema.json"

SCHEMA_CONFIRMED = "SCHEMA_CONFIRMED"
SCHEMA_INVALID = "SCHEMA_INVALID"
SCHEMA_NOT_ATTEMPTED = "SCHEMA_NOT_ATTEMPTED"

_FENCE_OPEN_RE = re.compile(r"^```json[ \t]*\r?\n", re.IGNORECASE | re.MULTILINE)
_FENCE_CLOSE_RE = re.compile(r"^```[ \t]*\r?$", re.MULTILINE)


def _iter_json_fences(text: str) -> Iterator[tuple[str, str | None, int]]:
    """Yield ``(status, block, start)`` for every ```json fence found in
    ``text``, in order. ``status`` is ``"found"`` (``block`` is the fenced
    inner text) or ``"truncated"`` (an opening fence with no matching close;
    ``block`` is ``None``) -- a truncated fence always ends the scan, since
    there is no reliable close position to resume searching from.

    Both delimiters are anchored to the start of a line (``re.MULTILINE``
    ``^``/``$``), not matched as a bare substring. This matters against two
    adversarial shapes an earlier, unanchored version of this regex missed:
    a JSON string value that happens to contain a literal ```` ``` ```` --
    JSON's grammar forbids a raw, unescaped newline inside a string, so such
    a sequence can never legally sit alone on its own line, and anchoring
    to line-start excludes it; and a widened fence (four or more backticks,
    the documented defense in adversarial-self-audit.md's own quoting rule)
    -- ```` ````json ```` does not match a literal 3-backtick open anchored
    at line-start, so a defensively-widened fence around quoted content is
    never mistaken for the real output contract's opener or closer."""
    pos = 0
    while True:
        open_match = _FENCE_OPEN_RE.search(text, pos)
        if open_match is None:
            return
        close_match = _FENCE_CLOSE_RE.search(text, open_match.end())
        if close_match is None:
            yield "truncated", None, open_match.start()
            return
        yield "found", text[open_match.end() : close_match.start()].strip(), open_match.start()
        pos = close_match.end()


def _locate_last_json_fence(text: str) -> tuple[str, str | None]:
    """Return ``(status, block)`` for the *last* ```json fence in ``text``:
    ``("absent", None)`` when no opening fence exists at all, ``("truncated",
    None)`` when the last opening fence has no matching close, or
    ``("found", block)`` otherwise."""
    result: tuple[str, str | None] = ("absent", None)
    for status, block, _ in _iter_json_fences(text):
        result = (status, block)
    return result


def extract_json_block(text: str | None) -> str | None:
    """Return the last *complete* fenced ```json ... ``` block's inner text
    from ``text``, or ``None`` when no complete block exists -- that covers
    both no opening fence at all and a truncated one (an opening fence with
    no matching close). Callers that must tell those two cases apart use
    ``_evaluate``, which reports a truncated fence as ``SCHEMA_INVALID``
    (an attempt that failed) rather than ``SCHEMA_NOT_ATTEMPTED``. A
    ``None`` ``text`` is treated the same as an absent block, matching how
    `gitapex_score_contract.py`'s own ``score()`` treats a ``None`` output
    as empty rather than raising."""
    if text is None:
        return None
    status, block = _locate_last_json_fence(text)
    return block if status == "found" else None


def _evaluate(output_text: str | None, schema: dict[str, Any]) -> tuple[str, str | None]:
    """Single-pass core: return ``(verdict, detail)``, where ``detail`` is a
    human-readable reason for a ``SCHEMA_INVALID`` verdict and ``None``
    otherwise. Both ``check_schema_conformance`` and ``main`` delegate here
    so the JSON-decode and schema-validation work happens exactly once --
    an earlier revision re-derived it a second time in ``main`` to build the
    detail message, which left the "re-validation finds no error" branch
    unreachable in practice (the first pass already established one exists)
    and therefore untestable."""
    if output_text is None:
        return SCHEMA_NOT_ATTEMPTED, None
    status, block = _locate_last_json_fence(output_text)
    if status == "absent":
        return SCHEMA_NOT_ATTEMPTED, None
    if status == "truncated":
        return SCHEMA_INVALID, "opening ```json fence has no matching closing ``` fence (truncated output)"
    try:
        # status not in {"absent", "truncated"} means "found", which
        # _iter_json_fences only ever yields paired with a str block.
        instance = json.loads(cast(str, block))
    except json.JSONDecodeError as exc:
        return SCHEMA_INVALID, f"fenced json block is not valid JSON: {exc}"
    validator = jsonschema.Draft202012Validator(schema)
    error = next(validator.iter_errors(instance), None)
    if error is not None:
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        return SCHEMA_INVALID, f"{error.message} (at {location})"
    return SCHEMA_CONFIRMED, None


def check_schema_conformance(output_text: str | None, schema: dict[str, Any]) -> str:
    """Return one of ``SCHEMA_CONFIRMED``/``SCHEMA_INVALID``/``SCHEMA_NOT_ATTEMPTED``
    for ``output_text`` against ``schema``. Never raises on malformed input --
    a run that attempted structured output and got it wrong is
    ``SCHEMA_INVALID``, not a crash."""
    return _evaluate(output_text, schema)[0]


_VERDICT_TO_FLAG = {
    SCHEMA_CONFIRMED: "confirmed",
    SCHEMA_INVALID: "invalid",
    SCHEMA_NOT_ATTEMPTED: "not_attempted",
}


def main(argv: list[str] | None = None) -> int:
    """CLI: print ``SCHEMA_CONFORMANCE=<confirmed|invalid|not_attempted>`` for
    a captured run's output against a schema file. Exit 0 for
    ``confirmed``/``not_attempted`` (both are legitimate outcomes during the
    disclosed opt-in adoption window), exit 1 for ``invalid`` (the run
    attempted structured output and it failed validation -- a real defect
    worth a caller's attention), exit 2 on a usage error (missing file)."""
    parser = argparse.ArgumentParser(
        description="Check a captured evaluating-skill-quality run's output for a "
        "structured verdict conforming to references/output-schema.json."
    )
    parser.add_argument(
        "--output",
        help="Path to the run's captured output text; reads standard input when omitted.",
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help="Path to the JSON Schema file (defaults to "
        "skills/evaluating-skill-quality/references/output-schema.json).",
    )
    args = parser.parse_args(argv)

    if args.output:
        try:
            output_text = Path(args.output).read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"error: output file not found: {args.output}", file=sys.stderr)
            return 2
        except UnicodeDecodeError as exc:
            print(f"error: could not decode output file {args.output}: {exc}", file=sys.stderr)
            return 2
    else:
        try:
            output_text = sys.stdin.buffer.read().decode("utf-8")
        except UnicodeDecodeError as exc:
            print(f"error: could not decode standard input: {exc}", file=sys.stderr)
            return 2

    try:
        schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: schema file not found: {args.schema}", file=sys.stderr)
        return 2
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"error: could not read schema file {args.schema}: {exc}", file=sys.stderr)
        return 2

    verdict, detail = _evaluate(output_text, schema)
    print(f"SCHEMA_CONFORMANCE={_VERDICT_TO_FLAG[verdict]}")
    if verdict == SCHEMA_INVALID:
        print(f"detail: {detail}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
