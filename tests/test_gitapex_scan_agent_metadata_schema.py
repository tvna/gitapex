"""Tests for the AgentMetadata sidecar drift scanner
(.github/scripts/gitapex_scan_agent_metadata_schema.py +
.gitapex/agent-metadata.schema.json), issue #2073.

The final test is the gate itself: every real agents/metadata/*.gitapex.yaml
in this repository must validate with no drift -- vacuous today (zero
sidecars exist, per the issue's own Non-goals), but it still proves the
real agents/ tree is discovered. The rest unit-test the schema, the
cross-file checks it cannot express, and main().
"""

from __future__ import annotations

import builtins
import copy
import importlib
import json
import pathlib
import runpy
import sys
from typing import Any

import gitapex_scan_agent_metadata_schema as scanner
import pytest
import yaml

_VALID_INSTANCE: dict[str, Any] = {
    "apiVersion": "gitapex.io/v1alpha1",
    "kind": "AgentMetadata",
    "metadata": {"name": "example-agent"},
    "spec": {
        "executionRequirements": {
            "tools": {
                "read": ["files"],
                "write": ["files"],
                "shell": [],
                "shellDenylist": ["git-push", "gh-cli", "package-install"],
            },
            "lifecycle": {
                "exitConditions": [
                    {
                        "id": "full-verification-suite",
                        "command": "uv run --frozen python3 -m pytest --no-cov -q",
                        "required": True,
                        "onUnsupported": "fail-closed",
                    }
                ]
            },
        }
    },
}


def _instance() -> dict[str, Any]:
    return copy.deepcopy(_VALID_INSTANCE)


def _violations(instance: Any) -> list[str]:
    return scanner.find_schema_violations(instance, scanner.load_schema())


def _make_agents_dir(tmp_path: pathlib.Path, agent_names: tuple[str, ...] = ("example-agent",)) -> pathlib.Path:
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    for name in agent_names:
        (agents_dir / f"{name}.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
    return agents_dir


def _write_sidecar(agents_dir: pathlib.Path, stem: str, instance: Any) -> pathlib.Path:
    metadata_dir = agents_dir / "metadata"
    metadata_dir.mkdir(exist_ok=True)
    path = metadata_dir / f"{stem}{scanner.SIDECAR_SUFFIX}"
    path.write_text(yaml.safe_dump(instance), encoding="utf-8")
    return path


# ---- schema: well-formed envelope (ACM row 1) ----


def test_schema_file_is_a_valid_draft_2020_12_schema() -> None:
    schema = json.loads(scanner.SCHEMA_PATH.read_text(encoding="utf-8"))
    scanner._gitapex_schema_validation.check_schema_or_raise(schema, scanner.SidecarReadError)


def test_valid_instance_has_no_violations() -> None:
    assert _violations(_instance()) == []


def test_issue_2073_example_sidecar_is_accepted() -> None:
    instance = _instance()
    instance["metadata"]["name"] = "branch-plan-task"
    instance["spec"]["executionRequirements"]["tools"] = {
        "read": ["files"],
        "write": ["files"],
        "shellDenylist": ["git-push", "gh-cli", "package-install"],
    }
    assert _violations(instance) == []


def test_skill_metadata_kind_is_rejected() -> None:
    instance = _instance()
    instance["kind"] = "SkillMetadata"
    assert any("kind" in v for v in _violations(instance))


def test_wrong_api_version_is_rejected() -> None:
    instance = _instance()
    instance["apiVersion"] = "gitapex.io/v1"
    assert any("apiVersion" in v for v in _violations(instance))


@pytest.mark.parametrize("key", ["apiVersion", "kind", "metadata", "spec"])
def test_missing_top_level_key_is_rejected(key: str) -> None:
    instance = _instance()
    del instance[key]
    assert _violations(instance)


def test_non_mapping_document_is_rejected() -> None:
    assert _violations(["not", "a", "mapping"])
    assert _violations(None)


@pytest.mark.parametrize(
    ("path", "key"),
    [
        ((), "status"),
        (("metadata",), "labels"),
        (("spec",), "portability"),
        (("spec", "executionRequirements"), "network"),
        (("spec", "executionRequirements", "tools"), "shellAllowlist"),
        (("spec", "executionRequirements", "lifecycle"), "entryConditions"),
    ],
)
def test_unknown_key_fails_closed(path: tuple[str, ...], key: str) -> None:
    instance = _instance()
    target: Any = instance
    for part in path:
        target = target[part]
    target[key] = "x"
    assert _violations(instance)


def test_unknown_key_inside_an_exit_condition_fails_closed() -> None:
    instance = _instance()
    instance["spec"]["executionRequirements"]["lifecycle"]["exitConditions"][0]["timeout"] = 60
    assert _violations(instance)


def test_empty_execution_requirements_is_rejected() -> None:
    instance = _instance()
    instance["spec"]["executionRequirements"] = {}
    assert _violations(instance)


@pytest.mark.parametrize("name", ["Example", "../agents", "example_agent", "", "-example"])
def test_non_kebab_metadata_name_is_rejected(name: str) -> None:
    instance = _instance()
    instance["metadata"]["name"] = name
    assert _violations(instance)


# ---- tools.shellDenylist (ACM row 2) ----


def test_shell_denylist_explicit_empty_list_is_accepted() -> None:
    instance = _instance()
    instance["spec"]["executionRequirements"]["tools"]["shellDenylist"] = []
    assert _violations(instance) == []


@pytest.mark.parametrize(
    "value",
    [
        [""],
        [1],
        [None],
        [["git-push"]],
        "git-push",
        ["git-push", "git-push"],
    ],
)
def test_shell_denylist_rejects_non_list_of_unique_non_empty_strings(value: Any) -> None:
    instance = _instance()
    instance["spec"]["executionRequirements"]["tools"]["shellDenylist"] = value
    assert _violations(instance)


# ---- lifecycle.exitConditions[] (ACM row 3) ----


@pytest.mark.parametrize("value", ["warn", "fail-open", "ignore", "", "FAIL-CLOSED", None])
def test_on_unsupported_other_than_fail_closed_is_rejected(value: Any) -> None:
    instance = _instance()
    instance["spec"]["executionRequirements"]["lifecycle"]["exitConditions"][0]["onUnsupported"] = value
    assert any("onUnsupported" in v for v in _violations(instance))


@pytest.mark.parametrize("field", ["id", "command", "required", "onUnsupported"])
def test_exit_condition_missing_required_field_is_rejected(field: str) -> None:
    instance = _instance()
    del instance["spec"]["executionRequirements"]["lifecycle"]["exitConditions"][0][field]
    assert _violations(instance)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", ""),
        ("id", "Full Suite"),
        ("command", ""),
        ("command", ["uv", "run"]),
        ("required", "true"),
        ("required", 1),
    ],
)
def test_exit_condition_field_with_wrong_shape_is_rejected(field: str, value: Any) -> None:
    instance = _instance()
    instance["spec"]["executionRequirements"]["lifecycle"]["exitConditions"][0][field] = value
    assert _violations(instance)


def test_empty_exit_conditions_list_is_rejected() -> None:
    instance = _instance()
    instance["spec"]["executionRequirements"]["lifecycle"]["exitConditions"] = []
    assert _violations(instance)


def test_duplicate_exit_condition_ids_are_a_finding() -> None:
    instance = _instance()
    conditions = instance["spec"]["executionRequirements"]["lifecycle"]["exitConditions"]
    conditions.append(dict(conditions[0], command="true"))
    assert _violations(instance) == []
    assert scanner.find_duplicate_exit_condition_ids(instance) == [
        "exit-condition-ids-unique: duplicate id 'full-verification-suite'"
    ]


def test_duplicate_exit_condition_ids_tolerates_malformed_shapes() -> None:
    assert scanner.find_duplicate_exit_condition_ids(None) == []
    assert scanner.find_duplicate_exit_condition_ids({"spec": {"executionRequirements": {"lifecycle": []}}}) == []
    assert (
        scanner.find_duplicate_exit_condition_ids(
            {"spec": {"executionRequirements": {"lifecycle": {"exitConditions": ["x", {"id": 1}]}}}}
        )
        == []
    )


# ---- cross-file checks and discovery (find_drift) ----


def test_find_drift_clean_on_valid_sidecar(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path)
    _write_sidecar(agents_dir, "example-agent", _instance())
    assert scanner.find_drift(agents_dir) == []


def test_find_drift_clean_with_no_metadata_dir(tmp_path: pathlib.Path) -> None:
    assert scanner.find_drift(_make_agents_dir(tmp_path)) == []


def test_find_drift_fails_closed_when_agents_dir_is_missing(tmp_path: pathlib.Path) -> None:
    findings = scanner.find_drift(tmp_path / "agents")
    assert len(findings) == 1
    assert findings[0].startswith("agent-definitions-discovered:")


def test_find_drift_fails_closed_when_agents_dir_has_no_definitions(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path, agent_names=())
    _write_sidecar(agents_dir, "example-agent", _instance())
    findings = scanner.find_drift(agents_dir)
    assert findings[0].startswith("agent-definitions-discovered:")


def test_find_drift_reports_name_stem_mismatch(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path, agent_names=("example-agent", "other-agent"))
    _write_sidecar(agents_dir, "other-agent", _instance())
    assert scanner.find_drift(agents_dir) == [
        f"{agents_dir / 'metadata' / 'other-agent.gitapex.yaml'}: "
        "metadata-name-matches-file: 'example-agent' vs file stem 'other-agent'"
    ]


def test_find_drift_reports_missing_agent_definition(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path, agent_names=("other-agent",))
    _write_sidecar(agents_dir, "example-agent", _instance())
    assert scanner.find_drift(agents_dir) == [
        f"{agents_dir / 'metadata' / 'example-agent.gitapex.yaml'}: agent-definition-exists: no agents/example-agent.md"
    ]


def test_find_drift_reports_schema_violation_with_path(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path)
    instance = _instance()
    instance["spec"]["executionRequirements"]["lifecycle"]["exitConditions"][0]["onUnsupported"] = "warn"
    path = _write_sidecar(agents_dir, "example-agent", instance)
    findings = scanner.find_drift(agents_dir)
    assert len(findings) == 1
    assert findings[0].startswith(f"{path}: schema: spec/executionRequirements/lifecycle/exitConditions/0/")


def test_find_drift_reports_duplicate_exit_condition_ids(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path)
    instance = _instance()
    conditions = instance["spec"]["executionRequirements"]["lifecycle"]["exitConditions"]
    conditions.append(dict(conditions[0]))
    _write_sidecar(agents_dir, "example-agent", instance)
    assert any("exit-condition-ids-unique" in f for f in scanner.find_drift(agents_dir))


@pytest.mark.parametrize(
    "filename",
    [
        "example-agent.gitapex.yml",
        "example-agent.yaml",
        "Example-Agent.gitapex.yaml",
        "example_agent.gitapex.yaml",
        ".gitapex.yaml",
        "README.md",
    ],
)
def test_find_drift_rejects_unrecognized_entries_under_metadata_dir(tmp_path: pathlib.Path, filename: str) -> None:
    agents_dir = _make_agents_dir(tmp_path)
    (agents_dir / "metadata").mkdir()
    (agents_dir / "metadata" / filename).write_text(yaml.safe_dump(_instance()), encoding="utf-8")
    findings = scanner.find_drift(agents_dir)
    assert len(findings) == 1
    assert "sidecar-filename:" in findings[0]


def test_find_drift_rejects_a_nested_directory_under_metadata_dir(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path)
    (agents_dir / "metadata" / "nested.gitapex.yaml").mkdir(parents=True)
    findings = scanner.find_drift(agents_dir)
    assert len(findings) == 1
    assert "sidecar-filename:" in findings[0]


def test_find_drift_fails_closed_when_metadata_path_is_a_file(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path)
    (agents_dir / "metadata").write_text("oops", encoding="utf-8")
    findings = scanner.find_drift(agents_dir)
    assert len(findings) == 1
    assert "sidecar-dir:" in findings[0]


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (b"\xff\xfe not utf-8", "is not valid UTF-8"),
        (b"key: [unterminated", "is not valid YAML"),
        (b"[" * 5000, "is too deeply nested"),
        (b"a: warn\na: fail-closed\n", "duplicate mapping key 'a'"),
    ],
)
def test_find_drift_reports_unreadable_sidecar_as_a_finding(
    tmp_path: pathlib.Path, content: bytes, expected: str
) -> None:
    agents_dir = _make_agents_dir(tmp_path)
    (agents_dir / "metadata").mkdir()
    path = agents_dir / "metadata" / "example-agent.gitapex.yaml"
    path.write_bytes(content)
    findings = scanner.find_drift(agents_dir)
    assert len(findings) == 1
    assert findings[0].startswith(f"{path}: sidecar-read: ")
    assert expected in findings[0]


def test_find_drift_keeps_scanning_after_an_unreadable_sidecar(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path, agent_names=("a-agent", "example-agent"))
    (agents_dir / "metadata").mkdir()
    (agents_dir / "metadata" / "a-agent.gitapex.yaml").write_bytes(b"key: [unterminated")
    instance = _instance()
    instance["kind"] = "SkillMetadata"
    _write_sidecar(agents_dir, "example-agent", instance)
    findings = scanner.find_drift(agents_dir)
    assert any("a-agent.gitapex.yaml: sidecar-read:" in f for f in findings)
    assert any("example-agent.gitapex.yaml: schema: kind:" in f for f in findings)


def test_duplicate_on_unsupported_key_cannot_hide_a_downgrade(tmp_path: pathlib.Path) -> None:
    """Defeat case: PyYAML's default loader keeps the last duplicate key, so
    `onUnsupported: warn` followed by `onUnsupported: fail-closed` would
    validate while a first-wins parser read `warn`."""
    agents_dir = _make_agents_dir(tmp_path)
    text = yaml.safe_dump(_instance()).replace(
        "onUnsupported: fail-closed", "onUnsupported: warn\n        onUnsupported: fail-closed"
    )
    assert yaml.safe_load(text) == _instance()
    (agents_dir / "metadata").mkdir()
    (agents_dir / "metadata" / "example-agent.gitapex.yaml").write_text(text, encoding="utf-8")
    findings = scanner.find_drift(agents_dir)
    assert len(findings) == 1
    assert "duplicate mapping key 'onUnsupported'" in findings[0]


def test_load_sidecar_rejects_duplicate_keys_including_merges(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "example-agent.gitapex.yaml"
    path.write_text("base: &b {x: 1}\nm:\n  <<: *b\n  x: 2\n", encoding="utf-8")
    with pytest.raises(scanner.SidecarReadError, match="duplicate mapping key 'x'"):
        scanner.load_sidecar(path)
    path.write_text("? [1, 2]\n: v\n", encoding="utf-8")
    with pytest.raises(scanner.SidecarReadError, match="is not valid YAML"):
        scanner.load_sidecar(path)


@pytest.mark.parametrize(
    "relative",
    [
        "example-agent.gitapex.yaml",
        "metdata/example-agent.gitapex.yaml",
        "Metadata/example-agent.gitapex.yaml",
        "example-agent/metadata/gitapex.yaml",
        "metadata/nested/example-agent.gitapex.yml",
    ],
)
def test_find_drift_flags_a_misplaced_sidecar(tmp_path: pathlib.Path, relative: str) -> None:
    """Defeat case: discovery reads only agents/metadata/, so a sidecar put
    anywhere else would otherwise never be validated."""
    agents_dir = _make_agents_dir(tmp_path)
    path = agents_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(_instance()), encoding="utf-8")
    findings = scanner.find_drift(agents_dir)
    assert f"{path}: sidecar-location: agent sidecars belong directly under {agents_dir / 'metadata'}" in findings


def test_find_drift_rejects_a_filename_with_a_trailing_newline(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path)
    (agents_dir / "metadata").mkdir()
    (agents_dir / "metadata" / "example-agent.gitapex.yaml\n").write_text(yaml.safe_dump(_instance()), encoding="utf-8")
    findings = scanner.find_drift(agents_dir)
    assert len(findings) == 1
    assert "sidecar-filename:" in findings[0]


def test_find_drift_rejects_a_symlinked_sidecar(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path)
    target = tmp_path / "elsewhere.yaml"
    target.write_text(yaml.safe_dump(_instance()), encoding="utf-8")
    (agents_dir / "metadata").mkdir()
    (agents_dir / "metadata" / "example-agent.gitapex.yaml").symlink_to(target)
    findings = scanner.find_drift(agents_dir)
    assert len(findings) == 1
    assert "sidecar-filename:" in findings[0]


def test_find_drift_rejects_a_symlinked_metadata_dir(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path)
    real = tmp_path / "real-metadata"
    real.mkdir()
    (agents_dir / "metadata").symlink_to(real, target_is_directory=True)
    findings = scanner.find_drift(agents_dir)
    assert len(findings) == 1
    assert "sidecar-dir:" in findings[0]


def test_find_drift_rejects_a_dangling_metadata_symlink(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path)
    (agents_dir / "metadata").symlink_to(tmp_path / "missing", target_is_directory=True)
    findings = scanner.find_drift(agents_dir)
    assert len(findings) == 1
    assert "sidecar-dir:" in findings[0]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("lifecycle", "exitConditions", 0, "id"), "full-verification-suite\n"),
        (("lifecycle", "exitConditions", 0, "command"), "   "),
        (("tools", "shellDenylist"), ["  "]),
        (("tools",), {}),
    ],
)
def test_schema_rejects_newline_whitespace_and_empty_shapes(path: tuple[Any, ...], value: Any) -> None:
    """Defeat cases: `$` in a Python regex also matches before a trailing
    newline, and minLength alone accepts a whitespace-only string."""
    instance = _instance()
    target: Any = instance["spec"]["executionRequirements"]
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    assert _violations(instance)


def test_metadata_name_with_trailing_newline_is_rejected() -> None:
    instance = _instance()
    instance["metadata"]["name"] = "example-agent\n"
    assert _violations(instance)


def test_load_sidecar_parses_a_valid_file(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path)
    path = _write_sidecar(agents_dir, "example-agent", _instance())
    assert scanner.load_sidecar(path) == _instance()


def test_load_sidecar_raises_on_unreadable_path(tmp_path: pathlib.Path) -> None:
    with pytest.raises(scanner.SidecarReadError, match="cannot be read"):
        scanner.load_sidecar(tmp_path / "missing.gitapex.yaml")


def test_load_sidecar_raises_on_memory_error(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "example-agent.gitapex.yaml"
    path.write_text("key: value\n", encoding="utf-8")

    def _exhaust(_text: str) -> Any:
        raise MemoryError("alias expansion")

    monkeypatch.setattr(scanner.yaml, "load", lambda _text, Loader: _exhaust(_text))
    with pytest.raises(scanner.SidecarReadError, match="exhausted memory while parsing"):
        scanner.load_sidecar(path)


def test_find_schema_violations_names_the_failing_location() -> None:
    instance = _instance()
    instance["spec"]["executionRequirements"]["tools"]["shellDenylist"] = [""]
    assert scanner.find_schema_violations(_instance(), scanner.load_schema()) == []
    violations = scanner.find_schema_violations(instance, scanner.load_schema())
    assert violations
    assert violations[0].startswith("schema: spec/executionRequirements/tools/shellDenylist/0:")


def test_find_name_mismatch_direct() -> None:
    assert scanner.find_name_mismatch(_instance(), "example-agent") == []
    assert scanner.find_name_mismatch(_instance(), "other-agent") == [
        "metadata-name-matches-file: 'example-agent' vs file stem 'other-agent'"
    ]
    assert scanner.find_name_mismatch(None, "example-agent") == []
    assert scanner.find_name_mismatch({"metadata": "x"}, "example-agent") == []
    assert scanner.find_name_mismatch({"metadata": {"name": 1}}, "example-agent") == []


def test_find_drift_reports_empty_sidecar_as_schema_violation(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path)
    (agents_dir / "metadata").mkdir()
    (agents_dir / "metadata" / "example-agent.gitapex.yaml").write_text("", encoding="utf-8")
    findings = scanner.find_drift(agents_dir)
    assert findings
    assert all("schema:" in f for f in findings)


def test_load_schema_raises_on_non_object_schema(tmp_path: pathlib.Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("[]", encoding="utf-8")
    with pytest.raises(scanner.SidecarReadError, match="must be a JSON object"):
        scanner.load_schema(schema_path)


def test_load_schema_raises_on_invalid_schema(tmp_path: pathlib.Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text('{"type": 1}', encoding="utf-8")
    with pytest.raises(scanner.SidecarReadError, match="is not a valid JSON Schema"):
        scanner.load_schema(schema_path)


# ---- main() ----


def test_main_returns_1_on_drift(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(scanner, "find_drift", lambda: ["fake: finding"])
    assert scanner.main() == 1
    assert "fake: finding" in capsys.readouterr().out


def test_main_returns_1_on_read_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def _raise() -> list[str]:
        raise scanner.SidecarReadError("boom")

    monkeypatch.setattr(scanner, "find_drift", _raise)
    assert scanner.main() == 1
    assert "boom" in capsys.readouterr().err


def test_main_returns_0_on_the_real_repository(capsys: pytest.CaptureFixture[str]) -> None:
    assert scanner.main() == 0
    assert "No agent metadata schema drift found." in capsys.readouterr().out


# ---- missing PyYAML dependency (same guard as gitapex_scan_skill_metadata_schema.py) ----


def test_missing_pyyaml_in_script_mode_exits_2_with_clear_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(sys.modules, "yaml", None)
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(pathlib.Path(scanner.__file__)), run_name="__main__")
    assert exc_info.value.code == 2
    stderr = capsys.readouterr().err
    assert "PyYAML" in stderr
    assert "uv sync --group dev" in stderr


def test_missing_pyyaml_on_plain_import_propagates_not_systemexit(monkeypatch: pytest.MonkeyPatch) -> None:
    module_name = "gitapex_scan_agent_metadata_schema"
    monkeypatch.setitem(sys.modules, "yaml", None)
    monkeypatch.delitem(sys.modules, module_name, raising=False)
    with pytest.raises(ModuleNotFoundError) as exc_info:
        importlib.import_module(module_name)
    assert exc_info.value.name == "yaml"


def test_broken_yaml_installation_in_script_mode_propagates_unmodified(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def _fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "yaml":
            raise ModuleNotFoundError("No module named 'yaml.tokens'", name="yaml.tokens")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    with pytest.raises(ModuleNotFoundError) as exc_info:
        runpy.run_path(str(pathlib.Path(scanner.__file__)), run_name="__main__")
    assert exc_info.value.name == "yaml.tokens"


# ---- the gate itself ----


def test_real_repository_agent_sidecars_have_no_schema_drift() -> None:
    assert scanner.find_drift() == []


def test_find_misplaced_sidecars_direct(tmp_path: pathlib.Path) -> None:
    agents_dir = _make_agents_dir(tmp_path)
    metadata_dir = agents_dir / "metadata"
    metadata_dir.mkdir()
    (metadata_dir / "example-agent.gitapex.yaml").write_text("x: 1\n", encoding="utf-8")
    (agents_dir / "notes.yaml").write_text("x: 1\n", encoding="utf-8")
    assert scanner.find_misplaced_sidecars(agents_dir, metadata_dir) == []
    stray = agents_dir / "gitapex.yml"
    stray.write_text("x: 1\n", encoding="utf-8")
    assert scanner.find_misplaced_sidecars(agents_dir, metadata_dir) == [
        f"{stray}: sidecar-location: agent sidecars belong directly under {metadata_dir}"
    ]


def test_construct_unique_mapping_direct() -> None:
    assert yaml.load("a: 1\nb: 2\n", Loader=scanner._UniqueKeyLoader) == {"a": 1, "b": 2}  # noqa: S506
    loader = scanner._UniqueKeyLoader("a: 1\na: 2\n")
    try:
        node = loader.get_single_node()
        assert isinstance(node, yaml.MappingNode)
        with pytest.raises(yaml.constructor.ConstructorError, match="duplicate mapping key 'a'"):
            scanner._construct_unique_mapping(loader, node)
    finally:
        loader.dispose()
