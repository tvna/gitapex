"""Tests for the plugin.json schema-conformance gate
(.github/scripts/gitapex_scan_plugin_manifest_schema.py).

Issue #1028. plugin.json is this repository's plugin-identity
source of truth; this gate checks it validates against the vendored Agent
Plugins Specification v1.0.0 plugin.schema.json
(.gitapex/agent-plugins-plugin.schema.json), that the vendored copy's own
sha256 matches its recorded digest, and (opt-in, --verify-upstream) that
the vendored copy still matches what agentplugins/agent-plugins-spec
publishes at the pinned commit. The final test is the real-repository
check itself.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from unittest import mock

import gitapex_scan_plugin_manifest_schema as scanner
import pytest

_VALID_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "$schema": {"const": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"},
        "name": {"type": "string", "pattern": "^[a-z0-9-]+$"},
    },
    "required": ["$schema", "name"],
    "additionalProperties": False,
}


def _write_json(path: pathlib.Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# schema_conformance_findings
# ---------------------------------------------------------------------------


def test_schema_conformance_findings_empty_for_valid_manifest(tmp_path: pathlib.Path) -> None:
    manifest_path = tmp_path / "plugin.json"
    schema_path = tmp_path / "schema.json"
    _write_json(
        manifest_path, {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json", "name": "gitapex"}
    )
    _write_json(schema_path, _VALID_SCHEMA)
    assert scanner.schema_conformance_findings(manifest_path, schema_path) == []


def test_schema_conformance_findings_reports_violation(tmp_path: pathlib.Path) -> None:
    manifest_path = tmp_path / "plugin.json"
    schema_path = tmp_path / "schema.json"
    _write_json(
        manifest_path, {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json", "name": "Not_Valid!"}
    )
    _write_json(schema_path, _VALID_SCHEMA)
    findings = scanner.schema_conformance_findings(manifest_path, schema_path)
    assert len(findings) == 1
    assert findings[0].startswith("schema-conformance: ")


def test_schema_conformance_findings_missing_manifest_raises(tmp_path: pathlib.Path) -> None:
    schema_path = tmp_path / "schema.json"
    _write_json(schema_path, _VALID_SCHEMA)
    with pytest.raises(scanner.ScanReadError):
        scanner.schema_conformance_findings(tmp_path / "nonexistent.json", schema_path)


def test_schema_conformance_findings_invalid_schema_raises_cleanly(tmp_path: pathlib.Path) -> None:
    """A dict-shaped but semantically-invalid JSON Schema (e.g. a non-string
    "type") passes the isinstance(dict) guard but must still raise
    ScanReadError via check_schema, not let jsonschema's validator
    construction crash with an unhandled TypeError -- a CodeRabbit review
    finding, confirmed live before this fix landed."""
    manifest_path = tmp_path / "plugin.json"
    schema_path = tmp_path / "schema.json"
    _write_json(
        manifest_path, {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json", "name": "gitapex"}
    )
    _write_json(schema_path, {"type": 1})
    with pytest.raises(scanner.ScanReadError, match="is not a valid JSON Schema"):
        scanner.schema_conformance_findings(manifest_path, schema_path)


def test_schema_conformance_findings_non_object_schema_raises_cleanly(tmp_path: pathlib.Path) -> None:
    """A syntactically-valid-JSON-but-non-object vendored schema (e.g. a
    JSON array) must raise ScanReadError, not let jsonschema's own
    internals crash with an unhandled AttributeError -- a live
    evaluating-deterministic-gate-quality review found this defect by
    actually feeding the gate one."""
    manifest_path = tmp_path / "plugin.json"
    schema_path = tmp_path / "schema.json"
    _write_json(
        manifest_path, {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json", "name": "gitapex"}
    )
    _write_json(schema_path, [1, 2, 3])
    with pytest.raises(scanner.ScanReadError, match="must be a JSON object"):
        scanner.schema_conformance_findings(manifest_path, schema_path)


# ---------------------------------------------------------------------------
# pydantic_conformance_findings
# ---------------------------------------------------------------------------


def test_pydantic_conformance_findings_empty_for_valid_manifest(tmp_path: pathlib.Path) -> None:
    manifest_path = tmp_path / "plugin.json"
    _write_json(
        manifest_path,
        {
            "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
            "name": "gitapex",
            "homepage": "https://github.com/tvna/gitapex",
        },
    )
    assert scanner.pydantic_conformance_findings(manifest_path) == []


def test_pydantic_conformance_findings_rejects_a_malformed_url_jsonschema_would_accept(
    tmp_path: pathlib.Path,
) -> None:
    """The one genuine additional-value check this layer adds over
    schema-conformance: the real vendored schema declares "homepage" a
    plain "type": "string" with no format assertion, so a malformed URL
    passes schema_conformance_findings cleanly -- but PluginManifest types
    it AnyUrl, so it must fail here. Uses the real vendored schema (default
    vendored_schema_path) rather than a hand-rolled one, to prove this
    against the actual file schema_conformance_findings validates against,
    not an approximation of it."""
    manifest_path = tmp_path / "plugin.json"
    _write_json(
        manifest_path,
        {
            "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
            "name": "gitapex",
            "homepage": "not a url",
        },
    )
    assert scanner.schema_conformance_findings(manifest_path) == []
    findings = scanner.pydantic_conformance_findings(manifest_path)
    assert len(findings) == 1
    assert findings[0].startswith("pydantic-conformance: homepage")


def test_pydantic_conformance_findings_rejects_unknown_field(tmp_path: pathlib.Path) -> None:
    manifest_path = tmp_path / "plugin.json"
    _write_json(
        manifest_path,
        {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json", "name": "gitapex", "bogus": 1},
    )
    findings = scanner.pydantic_conformance_findings(manifest_path)
    assert len(findings) == 1
    assert findings[0].startswith("pydantic-conformance: bogus")


def test_pydantic_conformance_findings_missing_manifest_raises(tmp_path: pathlib.Path) -> None:
    with pytest.raises(scanner.ScanReadError):
        scanner.pydantic_conformance_findings(tmp_path / "nonexistent.json")


def test_pydantic_conformance_findings_non_object_manifest_raises_cleanly(tmp_path: pathlib.Path) -> None:
    manifest_path = tmp_path / "plugin.json"
    manifest_path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(scanner.ScanReadError, match="must be a JSON object"):
        scanner.pydantic_conformance_findings(manifest_path)


def test_real_repository_plugin_manifest_is_pydantic_valid() -> None:
    assert scanner.pydantic_conformance_findings() == []


# ---------------------------------------------------------------------------
# vendor_digest_drift_findings
# ---------------------------------------------------------------------------


def test_vendor_digest_drift_findings_empty_when_digest_matches(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_bytes(b'{"a": 1}')
    digest = hashlib.sha256(schema_path.read_bytes()).hexdigest()
    monkeypatch.setattr(scanner, "VENDORED_SCHEMA_SHA256", digest)
    assert scanner.vendor_digest_drift_findings(schema_path) == []


def test_vendor_digest_drift_findings_reports_mismatch(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_bytes(b'{"a": 1}')
    monkeypatch.setattr(scanner, "VENDORED_SCHEMA_SHA256", "0" * 64)
    findings = scanner.vendor_digest_drift_findings(schema_path)
    assert len(findings) == 1
    assert findings[0].startswith("vendor-digest-drift: ")


def test_vendor_digest_drift_findings_missing_file_raises(tmp_path: pathlib.Path) -> None:
    with pytest.raises(scanner.ScanReadError):
        scanner.vendor_digest_drift_findings(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# upstream_drift_findings (network mocked)
# ---------------------------------------------------------------------------


def test_upstream_drift_findings_empty_when_bytes_match(tmp_path: pathlib.Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_bytes(b'{"a": 1}')
    response = mock.MagicMock()
    response.read.return_value = b'{"a": 1}'
    response.__enter__.return_value = response
    with mock.patch("gitapex_scan_plugin_manifest_schema.urllib.request.urlopen", return_value=response):
        assert scanner.upstream_drift_findings(schema_path) == []


def test_upstream_drift_findings_reports_mismatch(tmp_path: pathlib.Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_bytes(b'{"a": 1}')
    response = mock.MagicMock()
    response.read.return_value = b'{"a": 2}'
    response.__enter__.return_value = response
    with mock.patch("gitapex_scan_plugin_manifest_schema.urllib.request.urlopen", return_value=response):
        findings = scanner.upstream_drift_findings(schema_path)
    assert len(findings) == 1
    assert findings[0].startswith("upstream-drift: ")


def test_upstream_drift_findings_fetch_failure_is_a_finding(tmp_path: pathlib.Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_bytes(b'{"a": 1}')
    with mock.patch("gitapex_scan_plugin_manifest_schema.urllib.request.urlopen", side_effect=OSError("network down")):
        findings = scanner.upstream_drift_findings(schema_path)
    assert len(findings) == 1
    assert findings[0].startswith("upstream-drift: ")


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def test_main_returns_zero_and_prints_pass_when_clean(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = tmp_path / "plugin.json"
    schema_path = tmp_path / "schema.json"
    _write_json(
        manifest_path, {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json", "name": "gitapex"}
    )
    _write_json(schema_path, _VALID_SCHEMA)
    monkeypatch.setattr(scanner, "PLUGIN_MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(scanner, "VENDORED_SCHEMA_PATH", schema_path)
    monkeypatch.setattr(scanner, "VENDORED_SCHEMA_SHA256", hashlib.sha256(schema_path.read_bytes()).hexdigest())

    assert scanner.main([]) == 0
    assert "No plugin manifest schema drift found." in capsys.readouterr().out


def test_main_returns_one_and_prints_findings_on_violation(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = tmp_path / "plugin.json"
    schema_path = tmp_path / "schema.json"
    _write_json(
        manifest_path, {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json", "name": "Not_Valid!"}
    )
    _write_json(schema_path, _VALID_SCHEMA)
    monkeypatch.setattr(scanner, "PLUGIN_MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(scanner, "VENDORED_SCHEMA_PATH", schema_path)
    monkeypatch.setattr(scanner, "VENDORED_SCHEMA_SHA256", hashlib.sha256(schema_path.read_bytes()).hexdigest())

    assert scanner.main([]) == 1
    out = capsys.readouterr().out
    assert "schema-conformance:" in out


# ---------------------------------------------------------------------------
# Real-repository self-validation (the gate itself)
# ---------------------------------------------------------------------------


def test_real_repository_plugin_manifest_is_schema_valid() -> None:
    assert scanner.main([]) == 0


def test_main_includes_pydantic_conformance_findings(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = tmp_path / "plugin.json"
    schema_path = tmp_path / "schema.json"
    schema_with_homepage = {
        **_VALID_SCHEMA,
        "properties": {**_VALID_SCHEMA["properties"], "homepage": {"type": "string"}},  # type: ignore[dict-item]
    }
    _write_json(
        manifest_path,
        {
            "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
            "name": "gitapex",
            "homepage": "not a url",
        },
    )
    _write_json(schema_path, schema_with_homepage)
    monkeypatch.setattr(scanner, "PLUGIN_MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(scanner, "VENDORED_SCHEMA_PATH", schema_path)
    monkeypatch.setattr(scanner, "VENDORED_SCHEMA_SHA256", hashlib.sha256(schema_path.read_bytes()).hexdigest())

    assert scanner.main([]) == 1
    out = capsys.readouterr().out
    assert "pydantic-conformance:" in out


def test_main_verify_upstream_appends_the_network_findings(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest_path = tmp_path / "plugin.json"
    schema_path = tmp_path / "schema.json"
    _write_json(
        manifest_path, {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json", "name": "gitapex"}
    )
    _write_json(schema_path, _VALID_SCHEMA)
    monkeypatch.setattr(scanner, "PLUGIN_MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(scanner, "VENDORED_SCHEMA_PATH", schema_path)
    monkeypatch.setattr(scanner, "VENDORED_SCHEMA_SHA256", hashlib.sha256(schema_path.read_bytes()).hexdigest())

    response = mock.MagicMock()
    response.read.return_value = b'{"different": true}'
    response.__enter__.return_value = response
    with mock.patch("gitapex_scan_plugin_manifest_schema.urllib.request.urlopen", return_value=response):
        assert scanner.main(["--verify-upstream"]) == 1
    out = capsys.readouterr().out
    assert "upstream-drift:" in out


def test_main_reports_a_scan_read_error_without_a_traceback(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    schema_path = tmp_path / "schema.json"
    _write_json(schema_path, _VALID_SCHEMA)
    monkeypatch.setattr(scanner, "PLUGIN_MANIFEST_PATH", tmp_path / "nonexistent.json")
    monkeypatch.setattr(scanner, "VENDORED_SCHEMA_PATH", schema_path)

    assert scanner.main([]) == 1
    err = capsys.readouterr().err
    assert "FAIL:" in err


def test_upstream_drift_findings_raises_scan_read_error_when_vendored_copy_unreadable(
    tmp_path: pathlib.Path,
) -> None:
    response = mock.MagicMock()
    response.read.return_value = b'{"a": 1}'
    response.__enter__.return_value = response
    with (
        mock.patch("gitapex_scan_plugin_manifest_schema.urllib.request.urlopen", return_value=response),
        pytest.raises(scanner.ScanReadError),
    ):
        scanner.upstream_drift_findings(tmp_path / "nonexistent-vendored-schema.json")
