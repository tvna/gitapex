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
confirms every anchor is still present in its named file, byte-for-byte
after whitespace-run normalization (the same reduction
`evaluating-skill-quality/references/adversarial-self-audit.md`'s Citation
fidelity section applies to prose quotations, reused here rather than
re-derived, so a soft rewrap of the guarding sentence does not itself read
as a regression).

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
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_GLOB = "skills/*/evals/guardrail-manifest.yaml"


def _normalize(text: str) -> str:
    """Collapse whitespace runs (including newlines) to one space and trim.

    Mirrors `evaluating-skill-quality/references/adversarial-self-audit.md`'s
    Citation fidelity prose-block reduction, so an anchor tolerates a soft
    rewrap of the sentence it quotes without tolerating an actual wording
    change -- the same distinction that file draws between a wrap and a
    different value.
    """
    return " ".join(text.split())


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
    if not path.is_file():
        raise ManifestError(f"{path}: not a file")
    try:
        raw = path.read_text(encoding="utf-8")
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
    if not target.is_file():
        return EntryResult(entry, False, f"{entry.file}: file not found")
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        return EntryResult(entry, False, f"{entry.file}: could not decode as UTF-8: {error}")
    if _normalize(entry.anchor) in _normalize(text):
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
