"""Semantic (typed-ontology) scorer for rationale artifacts, complementing
score_contract.py's substring scorer (issue #625).

`skills/scorer-gated-skill-edits/scripts/score_contract.py` only checks
literal substring presence/absence (`output_contains`/`output_not_contains`).
It has no way to tell whether a why-not code comment, a commit-log Why, or an
ADR is *semantically* accurate to what it cites -- a comment can contain the
literal string `why-not(#421)` and cite a fabricated or mismatched reason,
and the substring scorer awards full credit regardless. This script adds a
second, complementary evaluation axis: does the artifact's claimed rationale
actually agree with the real source it cites.

Schema design, grounded in primary sources (not invented ad hoc):

- IBIS (Kunz & Rittel, 1970, "Issues as Elements of Information Systems") and
  its extensions -- QOC (MacLean, Young, Bellotti, Moran 1991) and the
  Toulmin argumentation model (Claim/Grounds/Warrant) -- establish that a
  design rationale decomposes into typed parts (a rejected alternative, and
  the claim+grounds for rejecting it), not opaque prose.
- ISO/IEC/IEEE 42010's own conceptual model (verified via a fetched INCOSE
  IW2022 editor presentation and a fetched runds.de reference poster, since
  the standard's own maintainer site returned HTTP 503 on every direct fetch
  attempt) defines a typed `Architecture Rationale` element whose definition
  is, translated, "the explanation, justification or reasoning for the
  architecture decisions made and for architecture alternatives that were
  not selected" -- a direct match for this repo's own why-not-comment
  concept, not an analogy reached for after the fact.
- W3C PROV-O (a real W3C Recommendation, OWL2, machine-readable; verified via
  a direct fetch of https://www.w3.org/TR/prov-o/) grounds the citation/
  traceability part of the schema (`cited_ref`) in a standards-based
  provenance vocabulary (`wasInformedBy`/`wasDerivedFrom`), rather than an
  invented field name.

This script deliberately does NOT constrain the *generation* of the artifact
being judged -- only the *evaluation* step is schema-constrained. Evidence
on constraining generation itself is contested (Tam et al. 2024,
arxiv.org/abs/2408.02442, found format restriction degrades reasoning
performance; a vendor rebuttal disputes the methodology; Geng et al. 2023,
arxiv.org/abs/2305.13971, EMNLP main, found constrained decoding helps only
for tasks whose ground-truth output is itself structured, e.g. extraction).
A why-not comment's underlying content (a decision record) fits that
extraction-task shape, but no fetched source tests this exact question --
this script's own live dispatch (see its test suite and issue #625's
tracked report) is the first real evidence gathered for it, not an assumed
win.

Structured-output mechanism: `claude -p --output-format json --json-schema
<schema>` gives real JSON-Schema-constrained output, verified by directly
fetching https://code.claude.com/docs/en/headless.md this session (not
recalled from training) -- "To get output conforming to a specific schema,
use --output-format json with --json-schema... The response includes...
the structured output in the structured_output field." A live end-to-end
run in *this* environment was attempted and confirmed to fail on
authentication (`claude --bare -p ... ` returns `Authentication error`,
since `ANTHROPIC_API_KEY` is unset and `--bare` mode skips OAuth/keychain
reads per that same page) -- the identical, already-disclosed precondition
`run_ablation.py` (issue #583) carries for its own live path. This script's
shape and interface are therefore built and unit-tested against a stub
executor first, exactly as `run_ablation.py` was.

Closed-book requirement (issue #626): the whole comparison step's validity
depends on the judge reasoning ONLY from the two given JSON records, not
from independently reading the real repository. `--bare` alone does not
guarantee this -- fetched directly this session, `headless.md`/
`cli-reference.md`/`tools-reference.md` all confirm bare mode still grants
Bash and file-read/file-edit tool access by default (it only skips
auto-discovery of hooks/skills/plugins/MCP servers/memory/CLAUDE.md, not
tool registration itself), and a real Workflow-tool load test of this same
comparison logic (`evals/semantic-rationale-load-test/report.md`) caught
judge agents disclosing, in their own returned explanations, that they had
used the GitHub MCP tool and read git history mid-comparison. Both command
builders below therefore also pass `--tools ""` ("restrict which built-in
tools Claude can use... use `""` to disable all", per `cli-reference.md`),
a registration-time removal, not a prompt-level request -- combined with
`--bare` never loading `.mcp.json`, this leaves no tool (built-in or MCP)
registered for either call. This flag combination was confirmed to parse
and reach the auth stage in a live `--bare -p ... --tools ""` invocation in
this environment; the full behavioral proof (a genuine zero-tool-call run
still returning a valid structured_output) remains blocked by the same
missing-`ANTHROPIC_API_KEY` precondition as the rest of this script's live
path -- disclosed here, not claimed as fully verified.

Standard library plus this repository's own `score_contract` module (for
the same fraction-based scoring convention used elsewhere in this corpus).
The `sys.path` bootstrap mirrors `run_ablation.py`'s own, for the same
reason: `pyproject.toml`'s `pythonpath` entry is pytest-only.

Usage::

    python3 evals/scripts/score_semantic_rationale.py \\
        --candidate candidate.txt --source source.txt [--model-cli claude]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

_SCORE_CONTRACT_DIR = (
    Path(__file__).resolve().parents[2]
    / "skills" / "scorer-gated-skill-edits" / "scripts"
)
if str(_SCORE_CONTRACT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCORE_CONTRACT_DIR))

DEFAULT_MODEL_CLI = "claude"
DEFAULT_TIMEOUT_SECONDS = 300

# JSON Schema for the typed decision record extracted from both the
# candidate artifact and its cited source. Field names trace to a specific
# primary source each, not invented independently:
#   rejected_alternative -- IBIS "Position" / QOC "Option" that was NOT taken
#   reason                -- Toulmin Claim+Grounds for rejecting it; also
#                             ISO/IEC/IEEE 42010's Architecture Rationale
#   cited_ref              -- the traceability link (42010 Correspondence /
#                             PROV-O wasInformedBy) -- what real record this
#                             claims to be grounded in
_DECISION_RECORD_SCHEMA = {
    "type": "object",
    "properties": {
        "rejected_alternative": {"type": ["string", "null"]},
        "reason": {"type": ["string", "null"]},
        "cited_ref": {"type": ["string", "null"]},
    },
    "required": ["rejected_alternative", "reason", "cited_ref"],
}

_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "rejected_alternative_match": {"type": "boolean"},
        "reason_match": {"type": "boolean"},
        "cited_ref_match": {"type": "boolean"},
        "fabrication_detected": {"type": "boolean"},
        "explanation": {"type": "string"},
    },
    "required": [
        "rejected_alternative_match",
        "reason_match",
        "cited_ref_match",
        "fabrication_detected",
        "explanation",
    ],
}

_EXTRACTION_PROMPT_TEMPLATE = """\
Extract the decision record described in the text below. `rejected_alternative`
is the specific alternative that was considered and NOT chosen (null if none
is stated). `reason` is the stated justification for rejecting it (null if
none is stated). `cited_ref` is any issue/PR/ADR identifier the text points to
as evidence for this decision (null if none is stated). Do not infer content
that is not actually present in the text; use null rather than guessing.

Text:
---
{text}
---
"""

_COMPARISON_PROMPT_TEMPLATE = """\
Two decision records were extracted independently: one from a generated
artifact (a code comment or commit message), one from the real source it
claims to cite. Judge whether the candidate's claims are actually true of
the source -- semantic agreement, not string equality (paraphrases count as
a match; a candidate claim not supported by the source does not, even if it
sounds plausible). Set fabrication_detected to true if the candidate asserts
something the source does not actually support.

Candidate record:
{candidate_record}

Source record:
{source_record}
"""

# (argv, timeout_seconds) -> captured stdout text. Swappable so this
# script's plumbing is unit-testable without a live model CLI or
# credentials -- same shape as run_ablation.py's own Executor type.
Executor = Callable[[Sequence[str], int], str]


def _require_nonblank_str(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def build_extraction_command(model_cli: str, text: str) -> list[str]:
    """Build the argv for one schema-constrained extraction call.

    Includes ``--tools ""`` (issue #626): a registration-time removal of
    all built-in tools, combined with ``--bare`` never loading an MCP
    config, so this call has no tool to invoke at all -- see the module
    docstring's "Closed-book requirement" section for why this is needed
    and what remains unverified about it.
    """
    model_cli = _require_nonblank_str(model_cli, "model_cli")
    prompt = _EXTRACTION_PROMPT_TEMPLATE.format(text=text)
    return [
        model_cli,
        "--bare",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(_DECISION_RECORD_SCHEMA),
        "--tools",
        "",
    ]


def build_comparison_command(
    model_cli: str, candidate_record: dict, source_record: dict
) -> list[str]:
    """Build the argv for the schema-constrained semantic-comparison call.

    Includes ``--tools ""`` (issue #626) for the same closed-book reason as
    ``build_extraction_command`` -- see that function's docstring and this
    module's docstring for the full reasoning.
    """
    model_cli = _require_nonblank_str(model_cli, "model_cli")
    prompt = _COMPARISON_PROMPT_TEMPLATE.format(
        candidate_record=json.dumps(candidate_record, sort_keys=True),
        source_record=json.dumps(source_record, sort_keys=True),
    )
    return [
        model_cli,
        "--bare",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(_VERDICT_SCHEMA),
        "--tools",
        "",
    ]


def subprocess_executor(argv: Sequence[str], timeout: int) -> str:
    """Default executor: run `argv` as a real subprocess and return its
    captured stdout. Same error-handling shape as run_ablation.py's own
    subprocess_executor -- see that module for the reasoning (nonzero exit
    raises rather than silently scoring empty output; invalid UTF-8 in
    output degrades to a replacement character rather than raising)."""
    result = subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"model CLI exited {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout


def _parse_structured_output(raw_stdout: str, *, step: str) -> dict:
    """Parse a `claude -p --output-format json` envelope and return its
    `structured_output` field. Raises ValueError (not the underlying
    json.JSONDecodeError/KeyError) so callers only need to catch one
    exception type, matching this repo's established convention
    (see run_ablation.py's load_task_fixture for the same shape)."""
    try:
        envelope = json.loads(raw_stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{step}: model CLI did not return valid JSON: {exc}") from exc
    if not isinstance(envelope, dict) or "structured_output" not in envelope:
        raise ValueError(
            f"{step}: model CLI response has no 'structured_output' field "
            "-- the schema may have been rejected or the call may have failed"
        )
    return envelope["structured_output"]


@dataclass(frozen=True)
class SemanticVerdict:
    """The extracted records plus the comparison verdict for one
    (candidate, source) pair."""

    candidate_record: dict
    source_record: dict
    rejected_alternative_match: bool
    reason_match: bool
    cited_ref_match: bool
    fabrication_detected: bool
    explanation: str

    @property
    def score(self) -> float:
        """Fraction of the three match fields that are true, mirroring
        score_contract.score's fraction-of-assertions-satisfied convention
        -- NOT reduced further by fabrication_detected, which is reported
        as its own flag rather than folded into one number, since a
        fabrication is a qualitatively different failure than a partial
        mismatch and collapsing it into the same scalar would hide which
        one occurred."""
        matches = [
            self.rejected_alternative_match,
            self.reason_match,
            self.cited_ref_match,
        ]
        return sum(1 for m in matches if m) / len(matches)


def score_semantic_rationale(
    candidate_text: str,
    source_text: str,
    *,
    executor: Executor,
    model_cli: str = DEFAULT_MODEL_CLI,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> SemanticVerdict:
    """Extract typed decision records from `candidate_text` and
    `source_text`, then judge their semantic agreement. Three model calls
    total (two extractions, one comparison), all schema-constrained."""
    candidate_raw = executor(
        build_extraction_command(model_cli, candidate_text), timeout
    )
    candidate_record = _parse_structured_output(candidate_raw, step="candidate extraction")

    source_raw = executor(build_extraction_command(model_cli, source_text), timeout)
    source_record = _parse_structured_output(source_raw, step="source extraction")

    verdict_raw = executor(
        build_comparison_command(model_cli, candidate_record, source_record), timeout
    )
    verdict = _parse_structured_output(verdict_raw, step="comparison")

    return SemanticVerdict(
        candidate_record=candidate_record,
        source_record=source_record,
        rejected_alternative_match=bool(verdict["rejected_alternative_match"]),
        reason_match=bool(verdict["reason_match"]),
        cited_ref_match=bool(verdict["cited_ref_match"]),
        fabrication_detected=bool(verdict["fabrication_detected"]),
        explanation=str(verdict["explanation"]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score a rationale artifact's semantic agreement with "
        "its cited source, via typed extraction + comparison -- "
        "complements score_contract.py's substring scoring."
    )
    parser.add_argument("--candidate", required=True, type=Path, help="Path to the generated artifact text.")
    parser.add_argument("--source", required=True, type=Path, help="Path to the real cited source text.")
    parser.add_argument("--model-cli", default=DEFAULT_MODEL_CLI)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)

    if not args.candidate.is_file():
        print(f"error: candidate file not found: {args.candidate}", file=sys.stderr)
        return 2
    if not args.source.is_file():
        print(f"error: source file not found: {args.source}", file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print(
            f"error: --timeout must be a positive number of seconds, got {args.timeout}",
            file=sys.stderr,
        )
        return 2

    candidate_text = args.candidate.read_text(encoding="utf-8")
    source_text = args.source.read_text(encoding="utf-8")

    try:
        verdict = score_semantic_rationale(
            candidate_text,
            source_text,
            executor=subprocess_executor,
            model_cli=args.model_cli,
            timeout=args.timeout,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "score": verdict.score,
                "fabrication_detected": verdict.fabrication_detected,
                "rejected_alternative_match": verdict.rejected_alternative_match,
                "reason_match": verdict.reason_match,
                "cited_ref_match": verdict.cited_ref_match,
                "explanation": verdict.explanation,
                "candidate_record": verdict.candidate_record,
                "source_record": verdict.source_record,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
