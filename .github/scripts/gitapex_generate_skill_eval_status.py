#!/usr/bin/env python3
"""Generate docs/skill-eval-status.md from docs/skill-eval-status-narrative.md
plus live-derived per-skill facts.

Issue #928, T14. Before this script, docs/skill-eval-status.md was
hand-maintained: a narrative header (three sections covering issues #106,
#925, #584) followed by an Index table of bare skill-name -> eval-status.md
links, with no derived data at all. One sentence inside that header stated
a countable fact by hand ("All 12 `evals/*/eval.yaml` declare
`trials_per_task: 3`") and drifted stale as suites were added -- nothing
regenerated it, and nothing caught the drift.

This generator derives, for every skill discovered the same way
gitapex_gate_skill_eval_yaml_parity.py does (skills/*/ paired with
evals/*/eval.yaml, never a hardcoded list):

- **Trials**: `config.trials_per_task` from that skill's own `eval.yaml`.
- **Fixtures**: a count of `evals/<skill>/tasks/*.yaml` files.
- **Models observed**: every `claude-<tier>-<version>`-shaped identifier
  found anywhere inside the `models` object of every
  `evals/<skill>/results/*/manifest.json` (deduped, sorted). Deliberately
  a regex extraction over each manifest's own free-text `models` values,
  not a fixed-schema field read: real manifests use inconsistent keys
  ("haiku"/"sonnet"/"opus" tier names in one, "tester_model_requested"/
  "substituted"/"default" in others) and inconsistent prose framing around
  the identifier itself, but every one that actually names a model embeds
  a real `claude-*` identifier substring somewhere in that prose, and a
  manifest that intentionally withholds a model name (a session-identity
  disclosure policy, seen live in one committed manifest) legitimately
  contributes nothing rather than a wrong guess.
- **Has result record**: whether `evals/<skill>/results/` exists at all
  and contains at least one `manifest.json`, i.e. whether any run has ever
  been recorded, independent of which model(s) it used.

**Deliberately not attempted**: `docs/superpowers/plans/2026-08-09-
gitapex-pr-928-lsficy.md`'s own T14 planned-ops text also names "dimension
coverage from gitapex_check_dimension_coverage.py" as a per-skill column.
That tool's own docstring states it is heuristic (citation-based, not
semantic) and, as of this writing, has only actually been run against 2
of the 25 skills discovered here (`evaluating-deterministic-gate-quality`,
`evaluating-skill-quality`) -- the other 23 skills' own eval corpora do
not use either dimension-heading convention that tool recognizes at all,
so running it against them would report spurious "0 dimensions covered"
noise rather than a real fact, not a narrowed-but-real derivation the way
the four columns above are. Left out, disclosed here rather than forced
in to match the plan's own text literally.

Two modes:

- Default (no flags): regenerate and overwrite `docs/skill-eval-status.md`.
- `--check`: regenerate in memory and diff against the committed file;
  exit 1 (printing the first divergent line) on any difference, 0 if
  byte-identical. This is what `tests/test_gitapex_generate_skill_eval_status.py`
  calls, so a hand-edit to the generated file (or a stale committed copy
  after the narrative/derived data changed) fails CI rather than silently
  drifting the way the file this replaces already once did.

ACTIVE (issue #928): enforced solely via the pytest gate in
`tests/test_gitapex_generate_skill_eval_status.py` -- no dedicated CI
workflow step or pre-commit hook, the same established convention as this
migration's other two scanner-shaped gates
(`gitapex_scan_split_schema.py`, `gitapex_gate_skill_eval_yaml_parity.py`).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

import gitapex_gate_skill_eval_yaml_parity as parity
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
EVALS_DIR = REPO_ROOT / "evals"
SKILLS_DIR = REPO_ROOT / "skills"
NARRATIVE_PATH = REPO_ROOT / "docs" / "skill-eval-status-narrative.md"
OUTPUT_PATH = REPO_ROOT / "docs" / "skill-eval-status.md"

_MODEL_IDENTIFIER_RE = re.compile(r"claude-[a-z0-9][a-z0-9.\-]*")


class GenerationError(Exception):
    """A checked-in input this generator depends on (the narrative source or,
    in --check mode, the committed output) could not be read as UTF-8 text
    -- exit 1 with a clear message, never an uncaught traceback."""


def _read_utf8_text(path: pathlib.Path) -> str:
    """Read `path` as UTF-8 text, or raise `GenerationError` naming `path`
    and the failure -- the one read boundary both the narrative-source read
    (in `generate()`) and the --check-mode committed-output read (in
    `main()`) go through, so the two do not carry independently-drifting
    copies of the same OSError/UnicodeDecodeError handling."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise GenerationError(f"{path}: cannot be read: {error}") from error
    except UnicodeDecodeError as error:
        raise GenerationError(f"{path}: is not valid UTF-8: {error}") from error


def discover_skill_names(skills_dir: pathlib.Path | None = None, evals_dir: pathlib.Path | None = None) -> list[str]:
    """Every skill in 1:1 parity (see gitapex_gate_skill_eval_yaml_parity.py),
    sorted for deterministic output. Reuses that module's own discovery
    rather than re-globbing, so the two never silently diverge on what
    counts as a real skill.

    `skills_dir`/`evals_dir` default to `None`, resolved to the current
    module-level `SKILLS_DIR`/`EVALS_DIR` inside the body rather than as
    the parameter's own default value -- a default value is bound once at
    function-definition time, so `= SKILLS_DIR` here would freeze in the
    *original* directory forever and silently ignore any later
    reassignment of the module attribute (a test's `monkeypatch.setattr`,
    or any other legitimate override). Every other function in this
    module taking a `*_dir`/`*_path` parameter follows the same pattern
    for the same reason."""
    skills_dir = SKILLS_DIR if skills_dir is None else skills_dir
    evals_dir = EVALS_DIR if evals_dir is None else evals_dir
    names = parity.discover_skill_names(skills_dir) & parity.discover_eval_yaml_skill_names(evals_dir)
    return sorted(names)


def _trials_per_task_of(eval_yaml_path: pathlib.Path) -> int | None:
    """`config.trials_per_task` read directly from an `eval.yaml` path, or
    None if the file is missing/malformed or the key is absent -- reported
    as "?" in the rendered table rather than raising, since a malformed
    eval.yaml is gitapex_scan_skill_metadata_schema.py-adjacent gates' own
    job to catch, not this generator's."""
    try:
        data = yaml.safe_load(eval_yaml_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    config = data.get("config")
    if not isinstance(config, dict):
        return None
    trials = config.get("trials_per_task")
    return trials if isinstance(trials, int) else None


def _trials_per_task_map(evals_dir: pathlib.Path) -> dict[str, int | None]:
    """skill-directory-name -> `config.trials_per_task`, for every
    `evals/*/eval.yaml` under `evals_dir`, each file parsed exactly once.
    `generate()` computes this a single time and threads it through to
    both `substitute_placeholders` and `render_index_table`, which
    previously each parsed the same files independently -- once for the
    `TRIALS_3_COUNT` placeholder, once per skill for the index table."""
    return {path.parent.name: _trials_per_task_of(path) for path in sorted(evals_dir.glob("*/eval.yaml"))}


def load_trials_per_task(
    skill_name: str, evals_dir: pathlib.Path | None = None, trials_map: dict[str, int | None] | None = None
) -> int | None:
    """`config.trials_per_task` from `evals/<skill>/eval.yaml`. See
    `discover_skill_names`'s docstring for why `evals_dir` defaults to
    `None` and is resolved inside the body, not as the parameter default.

    `trials_map`, when given (as `generate()` does), is read instead of
    re-parsing `skill_name`'s own `eval.yaml` a second time this run.
    """
    if trials_map is not None:
        return trials_map.get(skill_name)
    evals_dir = EVALS_DIR if evals_dir is None else evals_dir
    return _trials_per_task_of(evals_dir / skill_name / "eval.yaml")


def count_fixtures(skill_name: str, evals_dir: pathlib.Path | None = None) -> int:
    """Number of `evals/<skill>/tasks/*.yaml` fixture files. See
    `discover_skill_names`'s docstring for why `evals_dir` defaults to
    `None` and is resolved inside the body, not as the parameter default."""
    evals_dir = EVALS_DIR if evals_dir is None else evals_dir
    return len(list((evals_dir / skill_name / "tasks").glob("*.yaml")))


def find_evaluated_models(skill_name: str, evals_dir: pathlib.Path | None = None) -> list[str]:
    """Every distinct `claude-*` model identifier found across every
    `evals/<skill>/results/*/manifest.json`'s own `models` object,
    sorted. Empty list means no result record names a model at all
    (either no result record exists, or every one that does withholds
    the model name). See `discover_skill_names`'s docstring for why
    `evals_dir` defaults to `None` and is resolved inside the body, not as
    the parameter default."""
    evals_dir = EVALS_DIR if evals_dir is None else evals_dir
    results_dir = evals_dir / skill_name / "results"
    if not results_dir.is_dir():
        return []
    identifiers: set[str] = set()
    for manifest_path in sorted(results_dir.glob("*/manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        models = manifest.get("models") if isinstance(manifest, dict) else None
        if not isinstance(models, dict):
            continue
        identifiers.update(_MODEL_IDENTIFIER_RE.findall(json.dumps(models)))
    return sorted(identifiers)


def has_result_record(skill_name: str, evals_dir: pathlib.Path | None = None) -> bool:
    """Whether at least one `evals/<skill>/results/*/manifest.json` exists
    -- a run was recorded at all, independent of whether it names a
    model. See `discover_skill_names`'s docstring for why `evals_dir`
    defaults to `None` and is resolved inside the body, not as the
    parameter default."""
    evals_dir = EVALS_DIR if evals_dir is None else evals_dir
    results_dir = evals_dir / skill_name / "results"
    if not results_dir.is_dir():
        return False
    return any(results_dir.glob("*/manifest.json"))


def render_index_table(
    skill_names: list[str], evals_dir: pathlib.Path | None = None, trials_map: dict[str, int | None] | None = None
) -> str:
    """See `discover_skill_names`'s docstring for why `evals_dir` defaults
    to `None` and is resolved inside the body, not as the parameter
    default. `trials_map`, when given, is passed through to
    `load_trials_per_task` -- see that function's own docstring."""
    evals_dir = EVALS_DIR if evals_dir is None else evals_dir
    lines = [
        "| Skill | Trials | Fixtures | Models observed | Result record | Eval status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name in skill_names:
        trials = load_trials_per_task(name, evals_dir, trials_map)
        trials_cell = str(trials) if trials is not None else "?"
        fixtures_cell = str(count_fixtures(name, evals_dir))
        models = find_evaluated_models(name, evals_dir)
        models_cell = ", ".join(f"`{model}`" for model in models) if models else "none"
        result_cell = "yes" if has_result_record(name, evals_dir) else "no"
        link_cell = f"[evals/{name}/eval-status.md](../evals/{name}/eval-status.md)"
        lines.append(f"| `{name}` | {trials_cell} | {fixtures_cell} | {models_cell} | {result_cell} | {link_cell} |")
    return "\n".join(lines) + "\n"


def substitute_placeholders(
    narrative_text: str, evals_dir: pathlib.Path | None = None, trials_map: dict[str, int | None] | None = None
) -> str:
    """Replace every `{{TOKEN}}` placeholder in the narrative source with
    its live-derived value. Unknown tokens are left as-is rather than
    raising -- a typo in a new placeholder should surface as a visibly
    literal `{{...}}` in the rendered doc during review, not a crash that
    blocks every other regeneration. See `discover_skill_names`'s
    docstring for why `evals_dir` defaults to `None` and is resolved
    inside the body, not as the parameter default.

    `trials_map`, when given, is read instead of re-parsing every
    `evals/*/eval.yaml` a second time this run -- see `_trials_per_task_map`.
    """
    evals_dir = EVALS_DIR if evals_dir is None else evals_dir
    if trials_map is None:
        trials_map = _trials_per_task_map(evals_dir)
    total = len(trials_map)
    trials_3 = sum(1 for trials in trials_map.values() if trials == 3)
    substitutions = {
        "TOTAL_EVAL_YAML_COUNT": str(total),
        "TRIALS_3_COUNT": str(trials_3),
    }
    result = narrative_text
    for token, value in substitutions.items():
        result = result.replace(f"{{{{{token}}}}}", value)
    return result


def generate(
    narrative_path: pathlib.Path | None = None,
    skills_dir: pathlib.Path | None = None,
    evals_dir: pathlib.Path | None = None,
) -> str:
    """The full rendered docs/skill-eval-status.md content: the narrative
    source (HTML-comment banner intact, placeholders substituted) with a
    generated `## Index` table appended. See `discover_skill_names`'s
    docstring for why every path parameter defaults to `None` and is
    resolved inside the body, not as the parameter default."""
    narrative_path = NARRATIVE_PATH if narrative_path is None else narrative_path
    skills_dir = SKILLS_DIR if skills_dir is None else skills_dir
    evals_dir = EVALS_DIR if evals_dir is None else evals_dir
    narrative_text = _read_utf8_text(narrative_path)
    trials_map = _trials_per_task_map(evals_dir)
    rendered_narrative = substitute_placeholders(narrative_text, evals_dir, trials_map)
    skill_names = discover_skill_names(skills_dir, evals_dir)
    table = render_index_table(skill_names, evals_dir, trials_map)
    if not rendered_narrative.endswith("\n"):
        rendered_narrative += "\n"
    return f"{rendered_narrative}\n## Index\n\n{table}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Regenerate in memory and diff against the committed docs/skill-eval-status.md; exit 1 on drift.",
    )
    args = parser.parse_args(argv)

    try:
        rendered = generate()
    except GenerationError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    if args.check:
        try:
            committed = _read_utf8_text(OUTPUT_PATH)
        except GenerationError as error:
            print(f"FAIL: {error}", file=sys.stderr)
            return 1
        if rendered != committed:
            rendered_lines = rendered.splitlines()
            committed_lines = committed.splitlines()
            first_diff = next(
                (
                    index
                    for index in range(max(len(rendered_lines), len(committed_lines)))
                    if (rendered_lines[index] if index < len(rendered_lines) else None)
                    != (committed_lines[index] if index < len(committed_lines) else None)
                ),
                0,
            )
            print(
                f"FAIL: {OUTPUT_PATH} is stale -- a fresh regeneration differs "
                f"starting at line {first_diff + 1}. Re-run without --check to "
                "regenerate, then commit the result.",
                file=sys.stderr,
            )
            return 1
        print(f"PASS: {OUTPUT_PATH} matches a fresh regeneration")
        return 0

    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
