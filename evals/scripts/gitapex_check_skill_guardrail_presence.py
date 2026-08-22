#!/usr/bin/env python3
"""Deterministic presence check for a skill's own self-referential guardrail corpus.

Issue #364 (refs #261): `evals/battle-testing-a-skill/` and
`evals/evaluating-skill-quality/` already test whether each skill correctly
grades an arbitrary fed-in target -- they hold each skill's own `SKILL.md`
content fixed and vary the target instead. Neither corpus notices an edit
that silently strips one of the two skills' own guardrail clauses (the
CLAUDE.md-exclusion requirement, the byte-exact citation rule, an
input-validation default, and similar) from their own `SKILL.md` or
`references/*.md`, because no fixture reads that text at all.

This script is the "lightweight ... deterministic, scriptable, cheap" half
of issue #364's proposed design: a golden-file presence check, distinct
from (and cheaper than) a behavioral fixture that would feed a skill a
degraded copy of itself and observe whether its own procedure catches the
gap. That behavioral half is deliberately not built here -- see
`skills/battle-testing-a-skill/evals/README.md` and
`skills/evaluating-skill-quality/evals/README.md` for the recorded
trade-off and why, per issue #364's own explicit escape hatch ("if a full
corpus proves not worth the cost relative to the golden-file presence
check alone, that trade-off is recorded here explicitly rather than
silently dropped").

Each covered skill owns a `evals/guardrail-manifest.yaml` inside its own
skill directory (`skills/<skill>/evals/guardrail-manifest.yaml`) --
deliberately not the top-level `evals/<skill>/` directory that already
means "arbitrary-target grading corpus" for that skill (issue #364's own
"Decide where it lives" question). Each manifest entry names one guardrail
clause as an exact anchor string, the file it must still appear in, and the
issue that added it. This script reads every discovered manifest and
confirms every anchor is still present, within a single block, in its
named file -- reusing
`evaluating-skill-quality/references/adversarial-self-audit.md`'s Citation
fidelity rule rather than re-deriving it: a block is a run of lines broken
by a blank line, a fenced-code delimiter, a heading, or the start of a new
list item or table row; matching is whitespace-normalized *within* a
block, never across one, so an anchor tolerates a soft rewrap of the
sentence it quotes but cannot be satisfied by splicing text from two
different paragraphs, list items, or sides of a heading. Unlike that
file's own dual prose/fenced-block rule, a fenced block here is still
whitespace-normalized rather than matched byte-for-byte -- every anchor in
this corpus is prose, so that distinction has no live case to exercise;
disclosed here rather than silently narrowed.

Read-only: reads the discovered manifests and the files they name. No
writes, no network, no mutation. Mirrors `gitapex_check_skill_shape.py`'s
PASS/FAIL-per-line convention and exit-code contract (0 = every checked
anchor present, 1 = at least one missing or the discovery glob matched
nothing at all -- a silent zero-match is a regression in its own right,
not vacuous success, per this repository's own fail-closed-on-empty-match
precedent in `gitapex_gate_evals_scripts_coverage.py`'s "zero files
matched" guard -- 2 = a manifest itself could not be read or does not match
its schema).

Usage:
  uv run --frozen python3 gitapex_check_skill_guardrail_presence.py
  uv run --frozen python3 gitapex_check_skill_guardrail_presence.py --skill-dir skills/battle-testing-a-skill
  uv run --frozen python3 gitapex_check_skill_guardrail_presence.py --manifest path/to/guardrail-manifest.yaml
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_GLOB = "skills/*/evals/guardrail-manifest.yaml"

# Block-boundary lines, per adversarial-self-audit.md's Citation fidelity
# rule: a heading, or the start of a new list item or table row. A blank
# line and a fenced-code delimiter are handled separately in
# _split_into_blocks below, since both need state (blank: just a flush;
# fence: a toggle spanning multiple lines) that a single per-line regex
# cannot express.
_HEADING_RE = re.compile(r"^#{1,6}\s")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s|\d+\.\s)")
_TABLE_ROW_RE = re.compile(r"^\s*\|")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _normalize(text: str) -> str:
    """Collapse whitespace runs (including newlines) to one space and trim.

    Mirrors `evaluating-skill-quality/references/adversarial-self-audit.md`'s
    Citation fidelity prose-block reduction, so an anchor tolerates a soft
    rewrap of the sentence it quotes without tolerating an actual wording
    change -- the same distinction that file draws between a wrap and a
    different value.
    """
    return " ".join(text.split())


def _split_into_blocks(text: str) -> list[str]:
    """Split ``text`` into blocks per adversarial-self-audit.md's Citation
    fidelity rule: a run of lines broken by a blank line, a fenced-code
    delimiter, a heading, or the start of a new list item or table row.

    A multi-line list item's own wrapped continuation lines (indented,
    matching none of the boundary patterns) stay part of the item's block
    -- only a line that itself opens a new heading/list-item/table-row/fence
    starts a fresh one. This is what lets a guardrail anchor span a soft
    wrap within one Procedure step or Stop-boundary bullet while still
    being unable to span into the next one.
    """
    blocks: list[str] = []
    current: list[str] = []
    fence_marker: str | None = None

    def flush() -> None:
        if current:
            blocks.append("\n".join(current))
            current.clear()

    for line in text.split("\n"):
        stripped = line.strip()
        if fence_marker is not None:
            current.append(line)
            if stripped.startswith(fence_marker):
                fence_marker = None
                flush()
            continue
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            flush()
            fence_marker = fence_match.group(1)
            current.append(line)
            continue
        if not stripped:
            flush()
            continue
        if _HEADING_RE.match(line) or _LIST_ITEM_RE.match(line) or _TABLE_ROW_RE.match(line):
            flush()
        current.append(line)
    flush()
    return blocks


class GuardrailEntry(BaseModel):
    """One guardrail clause a manifest requires to keep existing.

    ``file`` is relative to the owning skill directory (e.g. ``"SKILL.md"``
    or ``"references/adversarial-self-audit.md"``); ``anchor`` is the exact
    clause text (whitespace-normalized before matching); ``description``
    names what the clause guards against regressing; ``source`` is the full
    GitHub issue/PR URL that added it -- a bare ``#123`` is rejected the
    same way `gitapex_check_skill_shape.py`'s citation checks reject one
    inside `SKILL.md`/`references/*.md` prose, since this manifest is read
    by the same audience and a bare number resolves only inside the
    repository that minted it.
    """

    model_config = ConfigDict(extra="forbid")

    file: str = Field(min_length=1)
    anchor: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source: str = Field(min_length=1)

    @field_validator("file")
    @classmethod
    def _file_is_relative_and_safe(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"file must be a relative path with no '..' segment, got {value!r}")
        return value

    @field_validator("anchor")
    @classmethod
    def _anchor_is_not_blank(cls, value: str) -> str:
        # A whitespace-only anchor normalizes to "", and "" is a substring
        # of every string -- silently passing against any file, including a
        # missing guardrail. Reject at parse time rather than shipping a
        # manifest entry that can never fail.
        if not _normalize(value):
            raise ValueError("anchor must contain non-whitespace text")
        return value

    @field_validator("source")
    @classmethod
    def _source_is_a_full_github_url(cls, value: str) -> str:
        if not value.startswith("https://github.com/"):
            raise ValueError(f"source must be a full https://github.com/... URL, got {value!r}")
        return value


class GuardrailManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[GuardrailEntry] = Field(min_length=1)


class ManifestError(Exception):
    """A guardrail manifest could not be read or does not match the schema."""


def load_manifest(path: Path) -> GuardrailManifest:
    # A single read_text() call, not an is_file() precondition followed by
    # a separate read: the two are not atomic, so a manifest deleted or
    # made unreadable between them would otherwise raise an uncaught
    # OSError past this function's documented ManifestError contract.
    # FileNotFoundError/IsADirectoryError/PermissionError (all OSError
    # subclasses) are caught here as one failure mode instead.
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ManifestError(f"{path}: not a file") from error
    except OSError as error:
        raise ManifestError(f"{path}: could not read file: {error}") from error
    except UnicodeDecodeError as error:
        raise ManifestError(f"{path}: could not decode as UTF-8: {error}") from error
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as error:
        raise ManifestError(f"{path}: invalid YAML: {error}") from error
    if not isinstance(data, dict):
        raise ManifestError(f"{path}: top level must be a mapping, got {type(data).__name__}")
    try:
        return GuardrailManifest.model_validate(data)
    except ValidationError as error:
        raise ManifestError(f"{path}: does not match the guardrail-manifest schema: {error}") from error


def discover_manifests(repo_root: Path, pattern: str = DEFAULT_MANIFEST_GLOB) -> list[Path]:
    return sorted(repo_root.glob(pattern))


@dataclass(frozen=True)
class EntryResult:
    entry: GuardrailEntry
    ok: bool
    reason: str  # always populated, PASS included, for uniform reporting


def check_entry(skill_dir: Path, entry: GuardrailEntry) -> EntryResult:
    target = skill_dir / entry.file
    # Same TOCTOU fix as load_manifest: one read_text() call, its
    # exceptions caught directly, rather than an is_file() check the
    # actual read can still race past.
    try:
        text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return EntryResult(entry, False, f"{entry.file}: file not found")
    except OSError as error:
        return EntryResult(entry, False, f"{entry.file}: could not read file: {error}")
    except UnicodeDecodeError as error:
        return EntryResult(entry, False, f"{entry.file}: could not decode as UTF-8: {error}")
    normalized_anchor = _normalize(entry.anchor)
    if any(normalized_anchor in _normalize(block) for block in _split_into_blocks(text)):
        return EntryResult(entry, True, f"{entry.file}: anchor present ({entry.description})")
    return EntryResult(entry, False, f"{entry.file}: anchor not found -- {entry.description} (source: {entry.source})")


def check_manifest(manifest_path: Path, manifest: GuardrailManifest) -> list[EntryResult]:
    skill_dir = manifest_path.resolve().parent.parent
    return [check_entry(skill_dir, entry) for entry in manifest.entries]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that every skill-owned guardrail-manifest.yaml's anchor clauses are "
        "still present in the files they cite (issue #364)."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help=f"Repository root to discover manifests under (default: {DEFAULT_MANIFEST_GLOB!r} "
        "relative to this checkout). Ignored when --manifest or --skill-dir is given.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        action="append",
        default=None,
        help="Explicit guardrail-manifest.yaml path to check. Repeatable. Overrides discovery.",
    )
    parser.add_argument(
        "--skill-dir",
        type=Path,
        action="append",
        default=None,
        help="Skill directory whose evals/guardrail-manifest.yaml should be checked. Repeatable. "
        "Overrides discovery; combines with --manifest.",
    )
    args = parser.parse_args(argv)

    manifests: list[Path] = []
    if args.manifest:
        manifests.extend(args.manifest)
    if args.skill_dir:
        manifests.extend(d / "evals" / "guardrail-manifest.yaml" for d in args.skill_dir)

    if not manifests:
        manifests = discover_manifests(args.repo_root)
        if not manifests:
            print(
                f"FAIL: no guardrail-manifest.yaml discovered under "
                f"{args.repo_root / DEFAULT_MANIFEST_GLOB} -- treat an empty match set as a scope "
                "regression, not vacuous success",
                file=sys.stderr,
            )
            return 1

    total = 0
    failures = 0
    for manifest_path in manifests:
        try:
            manifest = load_manifest(manifest_path)
        except ManifestError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2
        skill_name = manifest_path.resolve().parent.parent.name
        for result in check_manifest(manifest_path, manifest):
            total += 1
            status = "PASS" if result.ok else "FAIL"
            print(f"{status}: {skill_name}/{result.reason}")
            if not result.ok:
                failures += 1

    if failures:
        print(
            f"FAIL: {failures}/{total} guardrail anchor(s) missing across {len(manifests)} manifest(s)",
            file=sys.stderr,
        )
        return 1
    print(f"PASS: {total}/{total} guardrail anchor(s) present across {len(manifests)} manifest(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
