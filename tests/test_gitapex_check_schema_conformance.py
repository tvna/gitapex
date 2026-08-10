import json
from pathlib import Path

import gitapex_check_schema_conformance as csc
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REAL_SCHEMA_PATH = _REPO_ROOT / "skills/evaluating-skill-quality/references/output-schema.json"


def _dim(i: int, unmeasured: bool = False) -> dict:
    if unmeasured:
        return {"dimensionId": i, "verdict": "unmeasured", "evidence": []}
    return {"dimensionId": i, "verdict": "clear", "evidence": [{"quote": "x", "sourceRef": "y:1"}]}


def _valid_instance() -> dict:
    return {
        "schemaVersion": "1.0.0",
        "reviewMeta": {
            "actor": {"ref": "abc", "provenance": "asserted"},
            "targetRepoRef": "r",
            "skillBuildRef": "sha",
        },
        "shapeCheck": {"checkerRef": "scripts/x.py", "checks": [{"name": "n", "verdict": "PASS"}]},
        "mechanismFit": {
            "wrongMechanism": {"finding": False},
            "cohesion": {"dominantType": "functional"},
            "blindSpotPass": {"gapFound": False},
        },
        "dimensions": [_dim(i) for i in range(1, 10)],
        "verdict": {"token": "WELL-FORMED-AND-MATURE"},
    }


@pytest.fixture
def real_schema() -> dict:
    return json.loads(_REAL_SCHEMA_PATH.read_text(encoding="utf-8"))


# ---- extract_json_block ----------------------------------------------------


def test_extract_json_block_finds_fenced_block():
    text = 'some prose\n```json\n{"a": 1}\n```\nmore prose'
    assert csc.extract_json_block(text) == '{"a": 1}'


def test_extract_json_block_takes_the_last_of_several():
    text = '```json\n{"a": 1}\n```\nprose in between\n```json\n{"a": 2}\n```'
    assert csc.extract_json_block(text) == '{"a": 2}'


def test_extract_json_block_returns_none_when_absent():
    assert csc.extract_json_block("no fenced block here at all") is None


def test_extract_json_block_ignores_non_json_fences():
    text = "```python\nprint(1)\n```\nprose, no json fence"
    assert csc.extract_json_block(text) is None


def test_extract_json_block_none_on_none_input():
    assert csc.extract_json_block(None) is None


# ---- check_schema_conformance -----------------------------------------------


def test_confirmed_on_valid_instance(real_schema):
    text = "Review prose.\n```json\n" + json.dumps(_valid_instance()) + "\n```\n"
    assert csc.check_schema_conformance(text, real_schema) == csc.SCHEMA_CONFIRMED


def test_not_attempted_when_no_block_present(real_schema):
    assert csc.check_schema_conformance("plain prose review, no JSON block", real_schema) == csc.SCHEMA_NOT_ATTEMPTED


def test_not_attempted_on_none_output(real_schema):
    assert csc.check_schema_conformance(None, real_schema) == csc.SCHEMA_NOT_ATTEMPTED


def test_invalid_on_malformed_json(real_schema):
    text = "```json\n{not valid json\n```"
    assert csc.check_schema_conformance(text, real_schema) == csc.SCHEMA_INVALID


def test_invalid_on_schema_violation(real_schema):
    instance = _valid_instance()
    instance["dimensions"] = [_dim(1) for _ in range(9)]  # the degenerate keyword-stuffing case
    text = "```json\n" + json.dumps(instance) + "\n```"
    assert csc.check_schema_conformance(text, real_schema) == csc.SCHEMA_INVALID


def test_invalid_when_json_is_not_an_object(real_schema):
    text = "```json\n[1, 2, 3]\n```"
    assert csc.check_schema_conformance(text, real_schema) == csc.SCHEMA_INVALID


# ---- CLI (main) --------------------------------------------------------------


def test_main_prints_confirmed_and_exits_zero(tmp_path, capsys):
    output_path = tmp_path / "run.txt"
    output_path.write_text("```json\n" + json.dumps(_valid_instance()) + "\n```", encoding="utf-8")
    rc = csc.main(["--output", str(output_path), "--schema", str(_REAL_SCHEMA_PATH)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "SCHEMA_CONFORMANCE=confirmed"


def test_main_prints_not_attempted_and_exits_zero(tmp_path, capsys):
    output_path = tmp_path / "run.txt"
    output_path.write_text("plain prose, no block", encoding="utf-8")
    rc = csc.main(["--output", str(output_path), "--schema", str(_REAL_SCHEMA_PATH)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "SCHEMA_CONFORMANCE=not_attempted"


def test_main_prints_invalid_and_exits_one(tmp_path, capsys):
    output_path = tmp_path / "run.txt"
    output_path.write_text('```json\n{"nope": true}\n```', encoding="utf-8")
    rc = csc.main(["--output", str(output_path), "--schema", str(_REAL_SCHEMA_PATH)])
    assert rc == 1
    out = capsys.readouterr()
    assert out.out.strip() == "SCHEMA_CONFORMANCE=invalid"
    assert out.err.strip() != ""


def test_main_reads_stdin_when_no_output_flag(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin", type("S", (), {"buffer": type("B", (), {"read": staticmethod(lambda: b"no block")})()})()
    )
    rc = csc.main(["--schema", str(_REAL_SCHEMA_PATH)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "SCHEMA_CONFORMANCE=not_attempted"


def test_main_errors_on_missing_output_file(capsys):
    rc = csc.main(["--output", "/nonexistent/path/does-not-exist.txt", "--schema", str(_REAL_SCHEMA_PATH)])
    assert rc == 2
    assert "output file not found" in capsys.readouterr().err


def test_main_errors_on_missing_schema_file(tmp_path, capsys):
    output_path = tmp_path / "run.txt"
    output_path.write_text("anything", encoding="utf-8")
    rc = csc.main(["--output", str(output_path), "--schema", "/nonexistent/schema.json"])
    assert rc == 2
    assert "schema file not found" in capsys.readouterr().err


def test_main_defaults_to_the_real_repo_schema(tmp_path, capsys):
    output_path = tmp_path / "run.txt"
    output_path.write_text("```json\n" + json.dumps(_valid_instance()) + "\n```", encoding="utf-8")
    rc = csc.main(["--output", str(output_path)])
    assert rc == 0
    assert capsys.readouterr().out.strip() == "SCHEMA_CONFORMANCE=confirmed"


def test_main_undecodable_output_file_fails_closed(tmp_path, capsys):
    output_path = tmp_path / "run.txt"
    output_path.write_bytes(b"\xff\xfe bad")
    rc = csc.main(["--output", str(output_path), "--schema", str(_REAL_SCHEMA_PATH)])
    assert rc == 2
    assert "could not decode output file" in capsys.readouterr().err


def test_main_undecodable_stdin_fails_closed(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin", type("S", (), {"buffer": type("B", (), {"read": staticmethod(lambda: b"\xff\xfe bad")})()})()
    )
    rc = csc.main(["--schema", str(_REAL_SCHEMA_PATH)])
    assert rc == 2
    assert "could not decode standard input" in capsys.readouterr().err


def test_main_undecodable_schema_file_fails_closed(tmp_path, capsys):
    output_path = tmp_path / "run.txt"
    output_path.write_text("anything", encoding="utf-8")
    schema_path = tmp_path / "schema.json"
    schema_path.write_bytes(b"\xff\xfe bad")
    rc = csc.main(["--output", str(output_path), "--schema", str(schema_path)])
    assert rc == 2
    assert "could not read schema file" in capsys.readouterr().err


def test_main_malformed_json_schema_file_fails_closed(tmp_path, capsys):
    output_path = tmp_path / "run.txt"
    output_path.write_text("anything", encoding="utf-8")
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("{not valid json", encoding="utf-8")
    rc = csc.main(["--output", str(output_path), "--schema", str(schema_path)])
    assert rc == 2
    assert "could not read schema file" in capsys.readouterr().err


def test_evaluate_detail_message_for_malformed_json():
    verdict, detail = csc._evaluate(
        "```json\n{not valid\n```", json.loads(_REAL_SCHEMA_PATH.read_text(encoding="utf-8"))
    )
    assert verdict == csc.SCHEMA_INVALID
    assert "not valid JSON" in detail


def test_evaluate_detail_message_for_schema_violation(real_schema):
    instance = _valid_instance()
    instance["dimensions"] = [_dim(1) for _ in range(9)]
    verdict, detail = csc._evaluate("```json\n" + json.dumps(instance) + "\n```", real_schema)
    assert verdict == csc.SCHEMA_INVALID
    assert detail is not None
