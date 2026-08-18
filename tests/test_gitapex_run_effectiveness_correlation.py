"""Tests for evals/scripts/gitapex_run_effectiveness_correlation.py (issue #1143).

Same stub-executor discipline as test_gitapex_run_ablation.py/
test_gitapex_run_eval_suite.py: a live model run is out of scope for this
environment (no credentials), matching this issue's own Non-goals section.

``test_dry_run_against_real_committed_corpus_produces_correlation_without_error``
is the literal committed evidence for issue #1143's own Acceptance
Criteria Map row 3 proof method ("A dry run against a small subset
produces a correlation value with a CI, not an error") -- it runs the
real, committed ``effectiveness-corpus.json`` against every real skill's
own ``evals/<skill>/eval.yaml``, not a synthetic stand-in, so it is
strictly stronger evidence than a one-off manual dry run and re-verifies
itself on every future change.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import gitapex_run_effectiveness_correlation as m
import pytest
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]

DEMO_SCHEMA_PATH = REPO_ROOT / "evals" / "scripts" / "effectiveness-corpus.schema.json"

DEMO_SKILL_MD = "Demo skill body.\nLine two.\nLine three.\n"

DEMO_EVAL_YAML = """\
name: demo-eval
skill: demo-skill
config:
  trials_per_task: 1
  timeout_seconds: 30
  model: claude-sonnet-5
  executor: copilot-sdk
tasks:
  - "tasks/*.yaml"
"""

DEMO_TASK_YAML = """\
id: demo-task
inputs:
  prompt: Say ok.
expected:
  output_contains: ["ok"]
"""


def _stub_executor_returns_ok(argv: Sequence[str], timeout: int) -> str:
    return "ok"


def _write_demo_skill(
    root: Path, skill: str, *, body: str = DEMO_SKILL_MD, tasks: dict[str, str] | None = None
) -> None:
    skill_md = root / "skills" / skill / "SKILL.md"
    skill_md.parent.mkdir(parents=True, exist_ok=True)
    skill_md.write_text(body, encoding="utf-8")

    eval_dir = root / "evals" / skill
    (eval_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval.yaml").write_text(DEMO_EVAL_YAML, encoding="utf-8")
    for name, text in (tasks or {"a.yaml": DEMO_TASK_YAML}).items():
        (eval_dir / "tasks" / name).write_text(text, encoding="utf-8")


def _write_corpus(root: Path, entries: list[dict[str, Any]]) -> Path:
    corpus_path = root / "corpus.json"
    corpus_path.write_text(
        json.dumps({"methodology_doc": "evals/scripts/effectiveness-corpus-methodology.md", "entries": entries}),
        encoding="utf-8",
    )
    return corpus_path


# ---------------------------------------------------------------------------
# _skip_reason
# ---------------------------------------------------------------------------


def test_skip_reason_redacts_runtime_error_with_embedded_stderr() -> None:
    # Defeat test (issue #1143 adversarial review, CodeRabbit finding): a
    # live model CLI's raw stderr, exactly as subprocess_executor embeds it
    # in its own RuntimeError message, must never survive into the
    # returned reason.
    exc = RuntimeError("model CLI exited 1: ACME_SECRET_TOKEN=sk-live-deadbeef leaked in stderr")
    reason = m._skip_reason(exc)
    assert "ACME_SECRET_TOKEN" not in reason
    assert "sk-live-deadbeef" not in reason
    assert "RuntimeError" in reason


def test_skip_reason_redacts_timeout_expired_with_embedded_prompt() -> None:
    # TimeoutExpired's own str() includes the full argv it ran, which
    # includes the fixture's prompt text (build_command's own -p PROMPT
    # positional) -- must not survive into the returned reason either.
    exc = subprocess.TimeoutExpired(cmd=["claude", "-p", "the fixture's own private prompt text"], timeout=300)
    reason = m._skip_reason(exc)
    assert "private prompt text" not in reason
    assert "TimeoutExpired" in reason


def test_skip_reason_keeps_value_error_verbatim() -> None:
    # ValueError is always this module's or gitapex_run_eval_suite's own
    # deterministic, code-controlled text -- never live external output --
    # so it stays verbatim, genuinely useful for diagnosing which corpus
    # entry or fixture was malformed.
    reason = m._skip_reason(ValueError("skill_md not found: skills/ghost/SKILL.md"))
    assert reason == "skill_md not found: skills/ghost/SKILL.md"


def test_skip_reason_keeps_os_error_verbatim() -> None:
    reason = m._skip_reason(OSError("[Errno 2] No such file or directory: 'x.yaml'"))
    assert "No such file or directory" in reason


# ---------------------------------------------------------------------------
# load_corpus
# ---------------------------------------------------------------------------


def test_load_corpus_happy_path(tmp_path: Path) -> None:
    _write_demo_skill(tmp_path, "demo-a")
    corpus_path = _write_corpus(
        tmp_path,
        [
            {
                "skill": "demo-a",
                "skill_md": "skills/demo-a/SKILL.md",
                "eval_yaml": "evals/demo-a/eval.yaml",
                "split": "selection",
            }
        ],
    )
    corpus = m.load_corpus(corpus_path, DEMO_SCHEMA_PATH)
    assert corpus["entries"][0]["skill"] == "demo-a"


def test_load_corpus_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        m.load_corpus(tmp_path / "missing.json", DEMO_SCHEMA_PATH)


def test_load_corpus_invalid_json_raises(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot read corpus"):
        m.load_corpus(corpus_path, DEMO_SCHEMA_PATH)


def test_load_corpus_schema_violation_raises(tmp_path: Path) -> None:
    # Missing the required 'split' key.
    corpus_path = _write_corpus(
        tmp_path,
        [{"skill": "demo-a", "skill_md": "skills/demo-a/SKILL.md", "eval_yaml": "evals/demo-a/eval.yaml"}],
    )
    with pytest.raises(ValueError, match="failed schema validation"):
        m.load_corpus(corpus_path, DEMO_SCHEMA_PATH)


def test_load_corpus_invalid_schema_file_raises(tmp_path: Path) -> None:
    corpus_path = _write_corpus(
        tmp_path,
        [
            {
                "skill": "demo-a",
                "skill_md": "skills/demo-a/SKILL.md",
                "eval_yaml": "evals/demo-a/eval.yaml",
                "split": "selection",
            }
        ],
    )
    bad_schema_path = tmp_path / "bad-schema.json"
    bad_schema_path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="cannot read schema"):
        m.load_corpus(corpus_path, bad_schema_path)


# ---------------------------------------------------------------------------
# select_entries
# ---------------------------------------------------------------------------


def test_select_entries_filters_by_split() -> None:
    corpus = {"entries": [{"skill": "a", "split": "selection"}, {"skill": "b", "split": "test"}]}
    assert [e["skill"] for e in m.select_entries(corpus, "selection")] == ["a"]
    assert [e["skill"] for e in m.select_entries(corpus, "test")] == ["b"]


def test_select_entries_all_returns_everything() -> None:
    corpus = {"entries": [{"skill": "a", "split": "selection"}, {"skill": "b", "split": "test"}]}
    assert len(m.select_entries(corpus, "all")) == 2


def test_select_entries_empty_match_raises() -> None:
    corpus = {"entries": [{"skill": "a", "split": "selection"}]}
    with pytest.raises(ValueError, match="no corpus entries matched"):
        m.select_entries(corpus, "test")


# ---------------------------------------------------------------------------
# compute_pairs
# ---------------------------------------------------------------------------


def test_compute_pairs_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(m, "REPO_ROOT", tmp_path)
    _write_demo_skill(tmp_path, "demo-a", body="one\ntwo\n")
    entries = [
        {
            "skill": "demo-a",
            "skill_md": "skills/demo-a/SKILL.md",
            "eval_yaml": "evals/demo-a/eval.yaml",
            "split": "selection",
        }
    ]
    pairs, skipped = m.compute_pairs(entries, executor=_stub_executor_returns_ok, model_cli="claude")
    assert skipped == []
    assert len(pairs) == 1
    assert pairs[0].skill == "demo-a"
    # "one\ntwo\n" has no frontmatter, no sentence/bullet-initial Must/Never/Always,
    # and no Worked example/Examples or Error handling/Troubleshooting heading.
    assert pairs[0].x_negative_delta_risk == 0.0
    assert pairs[0].x_body_structure == 0.0
    assert pairs[0].y == 1.0  # stub always returns "ok", matching expected.output_contains: ["ok"]


def test_compute_pairs_skips_missing_skill_md(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(m, "REPO_ROOT", tmp_path)
    entries = [
        {
            "skill": "ghost",
            "skill_md": "skills/ghost/SKILL.md",
            "eval_yaml": "evals/ghost/eval.yaml",
            "split": "selection",
        }
    ]
    pairs, skipped = m.compute_pairs(entries, executor=_stub_executor_returns_ok, model_cli="claude")
    assert pairs == []
    assert len(skipped) == 1
    assert skipped[0].skill == "ghost"
    assert "not found" in skipped[0].reason


def test_compute_pairs_skips_malformed_eval_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(m, "REPO_ROOT", tmp_path)
    skill_md = tmp_path / "skills" / "demo-b" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("body\n", encoding="utf-8")
    eval_yaml = tmp_path / "evals" / "demo-b" / "eval.yaml"
    eval_yaml.parent.mkdir(parents=True)
    eval_yaml.write_text("name: broken\n", encoding="utf-8")  # missing required 'config'/'tasks'

    entries = [
        {
            "skill": "demo-b",
            "skill_md": "skills/demo-b/SKILL.md",
            "eval_yaml": "evals/demo-b/eval.yaml",
            "split": "selection",
        }
    ]
    pairs, skipped = m.compute_pairs(entries, executor=_stub_executor_returns_ok, model_cli="claude")
    assert pairs == []
    assert len(skipped) == 1
    assert skipped[0].skill == "demo-b"


def test_compute_pairs_one_bad_entry_does_not_block_others(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(m, "REPO_ROOT", tmp_path)
    _write_demo_skill(tmp_path, "good-skill", body="a\nb\nc\n")
    entries = [
        {
            "skill": "ghost",
            "skill_md": "skills/ghost/SKILL.md",
            "eval_yaml": "evals/ghost/eval.yaml",
            "split": "selection",
        },
        {
            "skill": "good-skill",
            "skill_md": "skills/good-skill/SKILL.md",
            "eval_yaml": "evals/good-skill/eval.yaml",
            "split": "selection",
        },
    ]
    pairs, skipped = m.compute_pairs(entries, executor=_stub_executor_returns_ok, model_cli="claude")
    assert len(pairs) == 1
    assert pairs[0].skill == "good-skill"
    assert len(skipped) == 1
    assert skipped[0].skill == "ghost"


# ---------------------------------------------------------------------------
# main() -- synthetic corpus
# ---------------------------------------------------------------------------


def test_main_dry_run_happy_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(m, "REPO_ROOT", tmp_path)
    # The stub executor always returns "ok" -- demo-a's task expects "ok"
    # (score 1.0) and demo-b's expects a string the stub never produces
    # (score 0.0), so y actually varies across the two entries. Two
    # identical-scoring entries would make y constant and correlation
    # undefined by construction (spearman_rho correctly rejects that) --
    # not this test's own concern, which is proving the happy path wires
    # end to end when a real correlation *can* be computed. demo-a's and
    # demo-b's SKILL.md bodies are likewise chosen so BOTH x metrics vary
    # across the two entries (demo-a has neither signal; demo-b has one
    # sentence-initial "Never" and one "## Worked example" heading) -- a
    # constant series in either metric would make that metric's own
    # correlation undefined too, and this test's job is proving both
    # succeed end to end.
    _write_demo_skill(tmp_path, "demo-a", body="one\ntwo\nthree\n")
    _write_demo_skill(
        tmp_path,
        "demo-b",
        body="Never skip this step.\n\n## Worked example\n\nSample text.\n",
        tasks={
            "a.yaml": 'id: demo-task\ninputs:\n  prompt: Say ok.\nexpected:\n  output_contains: ["never-produced-by-stub"]\n'
        },
    )
    corpus_path = _write_corpus(
        tmp_path,
        [
            {
                "skill": "demo-a",
                "skill_md": "skills/demo-a/SKILL.md",
                "eval_yaml": "evals/demo-a/eval.yaml",
                "split": "selection",
            },
            {
                "skill": "demo-b",
                "skill_md": "skills/demo-b/SKILL.md",
                "eval_yaml": "evals/demo-b/eval.yaml",
                "split": "selection",
            },
        ],
    )
    exit_code = m.main(
        [
            "--corpus",
            str(corpus_path),
            "--schema",
            str(DEMO_SCHEMA_PATH),
            "--split",
            "selection",
            "--dry-run",
            "--n-resamples",
            "20",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["split"] == "selection"
    assert len(payload["pairs"]) == 2
    assert payload["skipped"] == []
    assert "waza-independent" in payload["x_metric_caveat"]
    assert [c["metric"] for c in payload["correlations"]] == ["negative_delta_risk", "body_structure"]
    assert all(c["n"] == 2 for c in payload["correlations"])


def test_main_missing_corpus_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = m.main(["--corpus", str(tmp_path / "missing.json"), "--schema", str(DEMO_SCHEMA_PATH), "--dry-run"])
    assert exit_code == 2
    assert "not found" in capsys.readouterr().err


def test_main_bad_split_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(m, "REPO_ROOT", tmp_path)
    _write_demo_skill(tmp_path, "demo-a")
    corpus_path = _write_corpus(
        tmp_path,
        [
            {
                "skill": "demo-a",
                "skill_md": "skills/demo-a/SKILL.md",
                "eval_yaml": "evals/demo-a/eval.yaml",
                "split": "selection",
            }
        ],
    )
    exit_code = m.main(
        ["--corpus", str(corpus_path), "--schema", str(DEMO_SCHEMA_PATH), "--split", "nonsense", "--dry-run"]
    )
    assert exit_code == 2
    assert "--split" in capsys.readouterr().err


def test_main_split_matches_nothing_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(m, "REPO_ROOT", tmp_path)
    _write_demo_skill(tmp_path, "demo-a")
    corpus_path = _write_corpus(
        tmp_path,
        [
            {
                "skill": "demo-a",
                "skill_md": "skills/demo-a/SKILL.md",
                "eval_yaml": "evals/demo-a/eval.yaml",
                "split": "selection",
            }
        ],
    )
    exit_code = m.main(
        ["--corpus", str(corpus_path), "--schema", str(DEMO_SCHEMA_PATH), "--split", "test", "--dry-run"]
    )
    assert exit_code == 2
    assert "no corpus entries matched" in capsys.readouterr().err


def test_main_too_few_usable_pairs_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(m, "REPO_ROOT", tmp_path)
    # Only one entry, and it does not exist on disk -- zero usable pairs.
    corpus_path = _write_corpus(
        tmp_path,
        [
            {
                "skill": "ghost",
                "skill_md": "skills/ghost/SKILL.md",
                "eval_yaml": "evals/ghost/eval.yaml",
                "split": "selection",
            }
        ],
    )
    exit_code = m.main(
        ["--corpus", str(corpus_path), "--schema", str(DEMO_SCHEMA_PATH), "--split", "selection", "--dry-run"]
    )
    assert exit_code == 1
    assert "usable pair" in capsys.readouterr().err


def test_main_constant_x_series_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Two skills whose SKILL.md bodies contain neither a sentence/bullet-
    # initial Must/Never/Always nor a Worked example/Examples/Error
    # handling/Troubleshooting heading -- both x metrics are constant
    # (0.0, 0.0) even though the task outcomes (y) differ -- enough usable
    # pairs to attempt a correlation, but negative_delta_risk's own series
    # is constant, so compute_correlation must reject it (correlation is
    # undefined against a constant series) rather than the earlier "too
    # few pairs" guard catching it first. negative_delta_risk is computed
    # (and therefore fails) before body_structure in main(), so this is
    # the one whose own error message actually surfaces here.
    monkeypatch.setattr(m, "REPO_ROOT", tmp_path)
    _write_demo_skill(tmp_path, "demo-a", body="one\ntwo\n")
    _write_demo_skill(
        tmp_path,
        "demo-b",
        body="uno\ndos\n",
        tasks={
            "a.yaml": 'id: demo-task\ninputs:\n  prompt: Say ok.\nexpected:\n  output_contains: ["never-produced-by-stub"]\n'
        },
    )
    corpus_path = _write_corpus(
        tmp_path,
        [
            {
                "skill": "demo-a",
                "skill_md": "skills/demo-a/SKILL.md",
                "eval_yaml": "evals/demo-a/eval.yaml",
                "split": "selection",
            },
            {
                "skill": "demo-b",
                "skill_md": "skills/demo-b/SKILL.md",
                "eval_yaml": "evals/demo-b/eval.yaml",
                "split": "selection",
            },
        ],
    )
    exit_code = m.main(
        ["--corpus", str(corpus_path), "--schema", str(DEMO_SCHEMA_PATH), "--split", "selection", "--dry-run"]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "negative_delta_risk correlation" in err
    assert "constant" in err


def test_main_body_structure_constant_but_negative_delta_risk_varies_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Regression: the two correlations are independent -- a constant
    # body_structure series must be caught even when negative_delta_risk
    # itself varies (proving main() does not stop checking after the
    # first metric happens to succeed).
    monkeypatch.setattr(m, "REPO_ROOT", tmp_path)
    _write_demo_skill(tmp_path, "demo-a", body="one\ntwo\n")
    _write_demo_skill(
        tmp_path,
        "demo-b",
        body="Never skip this step.\n",
        tasks={
            "a.yaml": 'id: demo-task\ninputs:\n  prompt: Say ok.\nexpected:\n  output_contains: ["never-produced-by-stub"]\n'
        },
    )
    corpus_path = _write_corpus(
        tmp_path,
        [
            {
                "skill": "demo-a",
                "skill_md": "skills/demo-a/SKILL.md",
                "eval_yaml": "evals/demo-a/eval.yaml",
                "split": "selection",
            },
            {
                "skill": "demo-b",
                "skill_md": "skills/demo-b/SKILL.md",
                "eval_yaml": "evals/demo-b/eval.yaml",
                "split": "selection",
            },
        ],
    )
    exit_code = m.main(
        ["--corpus", str(corpus_path), "--schema", str(DEMO_SCHEMA_PATH), "--split", "selection", "--dry-run"]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "body_structure correlation" in err
    assert "constant" in err


def test_validation_error_message_native_pydantic_error_not_wrapped() -> None:
    # _split_must_be_known is the only custom field_validator this args
    # model declares; every other field relies on pydantic's own built-in
    # type validation. Constructing the model directly (bypassing argparse,
    # which would normally pre-coerce --confidence to a real float) with a
    # value pydantic's own float parser rejects outright exercises the
    # native-error branch _validation_error_message falls back to when
    # ctx carries no wrapped exception -- distinct from every other error
    # this test module exercises through the CLI, which all route through
    # a custom validator's own raised ValueError. The bad type is
    # deliberate (testing runtime validation of a value static typing
    # would normally rule out), matching this repository's own established
    # `# type: ignore[arg-type]` precedent for the same situation
    # (test_gitapex_run_betterleaks.py's own RunBetterleaksArgs(mode=...) case).
    with pytest.raises(ValidationError) as exc_info:
        m._RunEffectivenessCorrelationArgs(
            corpus=Path("x"),
            schema_path=Path("y"),
            split="selection",
            confidence="not-a-number",  # type: ignore[arg-type]
            n_resamples=10,
            seed=0,
        )
    message = m._validation_error_message(exc_info.value)
    assert "not-a-number" in message or "valid number" in message


# ---------------------------------------------------------------------------
# main() -- the real, committed corpus (issue #1143 ACM row 3 proof)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("split", ["selection", "test", "all"])
def test_dry_run_against_real_committed_corpus_produces_correlation_without_error(
    split: str, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = m.main(["--split", split, "--dry-run", "--n-resamples", "50"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["skipped"] == []  # every one of this repository's real 25 skills is runnable today
    # The exact, known-stable contract (effectiveness-corpus-methodology.md's
    # deterministic 20/80 selection/test split over 25 total skills), not
    # just ">= 2" -- a corpus that quietly shrank to 2 entries would still
    # pass a bare lower-bound check (issue #1143 adversarial review round).
    expected_n = {"selection": 20, "test": 5, "all": 25}[split]
    assert len(payload["pairs"]) == expected_n
    assert [c["metric"] for c in payload["correlations"]] == ["negative_delta_risk", "body_structure"]
    for correlation in payload["correlations"]:
        assert correlation["n"] == expected_n
        assert -1.0 <= correlation["rho"] <= 1.0
        assert correlation["ci_low"] <= correlation["ci_high"]
        assert correlation["power_caveat"]
