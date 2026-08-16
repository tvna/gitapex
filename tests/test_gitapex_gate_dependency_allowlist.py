"""Tests for the dependency-allowlist gate
(.github/scripts/gitapex_gate_dependency_allowlist.py).

Issue #1141 (redesign of PR2's -- issue #1118 -> PR #1120 -- now-removed
gitapex_check_skill_shape.py-embedded execution-requirements-packages-
allowlisted check): every skills/*/metadata/gitapex.yaml
spec.executionRequirements.packages declaration must name only a package
in this gate's own hardcoded ALLOWED_PACKAGES. The final test is the gate
itself, run against this repository's real skills/ tree with no fixture
override; the rest unit-test each layer with fixtures built the same way
tests/test_gitapex_scan_skill_metadata_schema.py's own
_make_skill_dir/_write_sidecar pair does (a synthetic skill directory, a
sidecar written via yaml.safe_dump rather than hand-written YAML text).
"""

from __future__ import annotations

import builtins
import importlib
import pathlib
import runpy
import sys
from typing import Any

import gitapex_gate_dependency_allowlist as gate
import pytest
import yaml
from conftest import make_validation_error

# ---- fixture helpers ----


def _instance(packages: Any = None) -> dict[str, Any]:
    """A minimal sidecar instance carrying only what this gate reads:
    spec.executionRequirements.packages. Not a full schema-valid
    SkillMetadata document -- schema shape is
    gitapex_scan_skill_metadata_schema.py's own job, not this gate's."""
    if packages is None:
        return {"spec": {}}
    return {"spec": {"executionRequirements": {"packages": packages}}}


def _make_skill_dir(
    base: pathlib.Path,
    name: str,
    packages: Any = None,
    *,
    no_sidecar: bool = False,
) -> pathlib.Path:
    """A real skill directory fixture: base/name/SKILL.md exists (the same
    "real skill directory" definition discover_skill_dirs uses), with a
    metadata/gitapex.yaml sidecar written via yaml.safe_dump -- mirrors
    tests/test_gitapex_scan_skill_metadata_schema.py's own
    _make_skill_dir/_write_sidecar pair rather than hand-written YAML
    text, which is safer for a nested spec.executionRequirements.packages
    structure. Pass no_sidecar=True to build a skill directory with no
    sidecar file at all."""
    skill_dir = base / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("---\nname: x\n---\nbody\n", encoding="utf-8")
    if not no_sidecar:
        (skill_dir / "metadata").mkdir(parents=True, exist_ok=True)
        (skill_dir / gate.SIDECAR_RELATIVE_PATH).write_text(yaml.safe_dump(_instance(packages)), encoding="utf-8")
    return skill_dir


# ---- find_disallowed_packages ----


def test_allowed_package_passes() -> None:
    instance = _instance({"pip": ["pyyaml"]})
    assert gate.find_disallowed_packages(instance, "some-skill") == []


def test_disallowed_package_fails_and_names_skill_ecosystem_package() -> None:
    instance = _instance({"pip": ["requests"]})
    findings = gate.find_disallowed_packages(instance, "some-skill")
    assert len(findings) == 1
    assert "some-skill" in findings[0]
    assert "pip" in findings[0]
    assert "requests" in findings[0]


def test_packages_key_absent_is_a_no_op() -> None:
    assert gate.find_disallowed_packages(_instance(), "some-skill") == []


def test_packages_empty_mapping_is_a_no_op() -> None:
    assert gate.find_disallowed_packages(_instance({}), "some-skill") == []


def test_packages_empty_ecosystem_list_is_a_no_op() -> None:
    assert gate.find_disallowed_packages(_instance({"pip": []}), "some-skill") == []


def test_packages_non_mapping_value_is_a_no_op_not_a_double_failure() -> None:
    # Regression pin, the important/easy-to-get-wrong case: a malformed
    # sidecar declaring packages as a list (or any other non-mapping)
    # instead of an ecosystem-keyed object is a shape defect
    # gitapex_check_skill_shape.py's own execution-requirements-well-formed
    # check already reports under its own check id -- this gate must
    # silently no-op here, never double-report it as a second failure.
    instance = {"spec": {"executionRequirements": {"packages": ["pyyaml"]}}}
    assert gate.find_disallowed_packages(instance, "some-skill") == []


def test_execution_requirements_non_mapping_is_a_no_op() -> None:
    instance = {"spec": {"executionRequirements": ["oops"]}}
    assert gate.find_disallowed_packages(instance, "some-skill") == []


def test_spec_non_mapping_is_a_no_op() -> None:
    assert gate.find_disallowed_packages({"spec": "oops"}, "some-skill") == []


def test_instance_non_mapping_is_a_no_op() -> None:
    assert gate.find_disallowed_packages(["not", "a", "mapping"], "some-skill") == []


def test_packages_pip_bare_string_does_not_iterate_character_by_character() -> None:
    # Regression pin: packages.pip declared as a bare "pyyaml" string
    # instead of ["pyyaml"] must not iterate character by character --
    # each single-character "p", "y", ... would otherwise surface as a
    # bogus disallowed-package finding.
    instance = _instance({"pip": "pyyaml"})
    assert gate.find_disallowed_packages(instance, "some-skill") == []


def test_non_string_list_item_is_skipped_not_crashed() -> None:
    instance = _instance({"pip": [123, None, "requests"]})
    findings = gate.find_disallowed_packages(instance, "some-skill")
    assert len(findings) == 1
    assert "requests" in findings[0]


def test_pep503_case_variant_of_allowed_name_passes() -> None:
    instance = _instance({"pip": ["PyYAML"]})
    assert gate.find_disallowed_packages(instance, "some-skill") == []


def test_pep503_separator_variant_of_allowed_name_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    # None of the 3 real allowlisted pip names (pyyaml, jsonschema,
    # pydantic) contain an internal separator in their own canonical
    # spelling, so a genuine separator-collapse equivalence (distinct from
    # case-only folding, which test_pep503_case_variant_of_allowed_name_
    # passes above already covers with a real allowed name) needs a name
    # that has one to demonstrate against -- monkeypatches
    # ALLOWED_PACKAGES for this one test only.
    monkeypatch.setattr(gate, "ALLOWED_PACKAGES", {"pip": ("scikit-learn",)})
    instance = _instance({"pip": ["scikit_learn"]})
    assert gate.find_disallowed_packages(instance, "some-skill") == []


def test_pep503_normalize_collapses_separators_and_lowercases() -> None:
    assert gate._pep503_normalize("Scikit_Learn") == "scikit-learn"
    assert gate._pep503_normalize("scikit.learn") == "scikit-learn"
    assert gate._pep503_normalize("scikit-learn") == "scikit-learn"


def test_exact_duplicate_declarations_reported_once() -> None:
    instance = _instance({"pip": ["requests", "requests"]})
    assert len(gate.find_disallowed_packages(instance, "some-skill")) == 1


def test_pep503_equivalent_duplicate_declarations_reported_once() -> None:
    instance = _instance({"pip": ["my-pkg", "my_pkg"]})
    assert len(gate.find_disallowed_packages(instance, "some-skill")) == 1


def test_unknown_ecosystem_allows_nothing() -> None:
    instance = _instance({"npm": ["eslint"]})
    findings = gate.find_disallowed_packages(instance, "some-skill")
    assert len(findings) == 1
    assert "npm" in findings[0]
    assert "eslint" in findings[0]


# ---- load_sidecar ----


def test_load_sidecar_reads_valid_yaml(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gitapex.yaml"
    instance = _instance({"pip": ["pyyaml"]})
    path.write_text(yaml.safe_dump(instance), encoding="utf-8")
    assert gate.load_sidecar(path) == instance


def test_load_sidecar_raises_on_invalid_yaml(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gitapex.yaml"
    path.write_text("key: [unterminated", encoding="utf-8")
    with pytest.raises(gate.SidecarReadError):
        gate.load_sidecar(path)


def test_load_sidecar_raises_on_non_utf8(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gitapex.yaml"
    path.write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(gate.SidecarReadError):
        gate.load_sidecar(path)


def test_load_sidecar_raises_on_pathologically_deep_nesting(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "gitapex.yaml"
    path.write_text("key: " + "[" * 3000 + "]" * 3000, encoding="utf-8")
    with pytest.raises(gate.SidecarReadError):
        gate.load_sidecar(path)


def test_load_sidecar_raises_on_os_error(tmp_path: pathlib.Path) -> None:
    # A directory where a file is expected raises IsADirectoryError (a
    # real OSError subclass) on read_text() -- more portable than a
    # permission-bit test, which a root-run sandbox commonly ignores.
    path = tmp_path / "gitapex.yaml"
    path.mkdir()
    with pytest.raises(gate.SidecarReadError):
        gate.load_sidecar(path)


# ---- discover_skill_dirs ----


def test_discover_skill_dirs_finds_only_dirs_with_skill_md(tmp_path: pathlib.Path) -> None:
    (tmp_path / "has-skill").mkdir()
    (tmp_path / "has-skill" / "SKILL.md").write_text("x", encoding="utf-8")
    (tmp_path / "no-skill").mkdir()
    dirs = gate.discover_skill_dirs(tmp_path)
    assert [d.name for d in dirs] == ["has-skill"]


def test_discover_skill_dirs_empty_when_skills_dir_missing(tmp_path: pathlib.Path) -> None:
    assert gate.discover_skill_dirs(tmp_path / "does-not-exist") == []


# ---- find_violations (end-to-end) ----


def test_find_violations_clean_tree_is_empty(tmp_path: pathlib.Path) -> None:
    skills_dir = tmp_path / "skills"
    _make_skill_dir(skills_dir, "clean-skill", {"pip": ["pyyaml"]})
    assert gate.find_violations(skills_dir, min_expected_skill_dirs=1) == []


def test_find_violations_missing_sidecar_is_a_no_op(tmp_path: pathlib.Path) -> None:
    skills_dir = tmp_path / "skills"
    _make_skill_dir(skills_dir, "no-sidecar-skill", no_sidecar=True)
    assert gate.find_violations(skills_dir, min_expected_skill_dirs=1) == []


def test_find_violations_unreadable_sidecar_fails_closed(tmp_path: pathlib.Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_dir = _make_skill_dir(skills_dir, "broken-skill")
    (skill_dir / gate.SIDECAR_RELATIVE_PATH).write_text("key: [unterminated", encoding="utf-8")
    findings = gate.find_violations(skills_dir, min_expected_skill_dirs=1)
    assert len(findings) == 1
    assert "broken-skill" in findings[0]


def test_find_violations_only_names_the_offending_skill(tmp_path: pathlib.Path) -> None:
    skills_dir = tmp_path / "skills"
    _make_skill_dir(skills_dir, "clean-skill", {"pip": ["pyyaml"]})
    _make_skill_dir(skills_dir, "offending-skill", {"pip": ["requests"]})
    findings = gate.find_violations(skills_dir, min_expected_skill_dirs=2)
    assert len(findings) == 1
    assert "offending-skill" in findings[0]
    assert "clean-skill" not in findings[0]


def test_find_violations_floor_fires_when_too_few_skill_dirs_found(tmp_path: pathlib.Path) -> None:
    (tmp_path / "skills").mkdir()
    findings = gate.find_violations(tmp_path / "skills")
    assert any("skill-discovery-floor" in f for f in findings)


# ---- GateDependencyAllowlistArgs ----


def test_args_defaults_skills_root_to_skills() -> None:
    assert gate.GateDependencyAllowlistArgs().skills_root == "skills"


def test_args_accepts_a_custom_skills_root() -> None:
    assert gate.GateDependencyAllowlistArgs(skills_root="/tmp/skills").skills_root == "/tmp/skills"


# ---- main() ----


def test_main_prints_pass_and_returns_0_when_clean(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "find_violations", lambda skills_dir: [])
    assert gate.main([]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_prints_fail_and_returns_1_with_findings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "find_violations", lambda skills_dir: ["fake: finding"])
    assert gate.main([]) == 1
    assert "fake: finding" in capsys.readouterr().err


def test_main_threads_skills_root_flag_into_find_violations(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, pathlib.Path] = {}

    def _fake_find_violations(skills_dir: pathlib.Path) -> list[str]:
        captured["skills_dir"] = skills_dir
        return []

    monkeypatch.setattr(gate, "find_violations", _fake_find_violations)
    gate.main(["--skills-root", "/some/custom/skills-root"])
    assert captured["skills_dir"] == pathlib.Path("/some/custom/skills-root")


def test_main_exits_two_when_args_fail_validation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise make_validation_error()

    monkeypatch.setattr(gate, "GateDependencyAllowlistArgs", _raise)
    assert gate.main([]) == 2
    assert "invalid CLI arguments" in capsys.readouterr().err


# ---- missing/broken PyYAML dependency (guarded import) ----
#
# All four cases are simulated the same way, via builtins.__import__
# patching, rather than mixing in the sys.modules["yaml"] = None trick
# some sibling gates' own tests use for the plain-missing case: patching
# __import__ can also raise a *different* ModuleNotFoundError (error.name
# == "yaml.tokens", not "yaml") to simulate a broken/partial install,
# which a single sys.modules entry cannot represent.


def test_missing_pyyaml_exits_with_clear_message_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A surface without the dev dependency group installed must see a
    clear, actionable message, not a raw traceback. Runs the script fresh
    via runpy.run_path(..., run_name="__main__") -- the guard's
    SystemExit(2) only fires under __name__ == "__main__" (see the
    regression test below for why), and run_path is the standard-library
    way to execute a file as if it were __main__ in-process."""
    real_import = builtins.__import__

    def _fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "yaml":
            raise ModuleNotFoundError("No module named 'yaml'", name="yaml")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    script_path = str(pathlib.Path(gate.__file__))

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(script_path, run_name="__main__")

    assert exc_info.value.code == 2
    stderr = capsys.readouterr().err
    assert "PyYAML" in stderr
    assert "uv sync --group dev" in stderr


def test_missing_pyyaml_on_plain_import_propagates_cleanly_not_systemexit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Converting a missing PyYAML into SystemExit(2) unconditionally --
    including when this module is merely *imported* rather than run as a
    script -- would break pytest's own collection machinery: a bare
    SystemExit raised during collection is not a plain Exception, so
    pytest's collection handler cannot catch it cleanly. Asserts a plain
    import with PyYAML missing lets ModuleNotFoundError itself propagate
    instead. Evicts the cached module first to force a fresh top-level
    exec, since reusing the already-imported `gate` object would skip the
    guard entirely and let this test pass vacuously."""
    module_name = "gitapex_gate_dependency_allowlist"
    real_import = builtins.__import__

    def _fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "yaml":
            raise ModuleNotFoundError("No module named 'yaml'", name="yaml")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    monkeypatch.delitem(sys.modules, module_name, raising=False)

    with pytest.raises(ModuleNotFoundError) as exc_info:
        importlib.import_module(module_name)

    assert exc_info.value.name == "yaml"


def test_broken_yaml_installation_error_propagates_unmodified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ModuleNotFoundError raised from INSIDE an already-found but
    broken/partial PyYAML install (one of its own internal submodules
    missing) carries error.name == "yaml.<submodule>", not "yaml". This
    guard's own remediation ("install the dev dependency group") would not
    fix a corrupted install, so misreporting it as a plain missing-PyYAML
    case would send a reader chasing the wrong problem -- asserts the
    ORIGINAL ModuleNotFoundError propagates uncaught, not converted to
    this guard's SystemExit(2)."""
    module_name = "gitapex_gate_dependency_allowlist"
    real_import = builtins.__import__

    def _fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "yaml":
            raise ModuleNotFoundError("No module named 'yaml.tokens'", name="yaml.tokens")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    monkeypatch.delitem(sys.modules, module_name, raising=False)

    with pytest.raises(ModuleNotFoundError) as exc_info:
        importlib.import_module(module_name)

    assert exc_info.value.name == "yaml.tokens"


def test_broken_yaml_installation_in_script_mode_propagates_unmodified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Isolates the intersection the two tests above each only cover from
    one side: a broken/partial install (error.name == "yaml.tokens", not
    "yaml") encountered via the CLI entry point itself (__name__ ==
    "__main__", via runpy.run_path the same way the script-mode test above
    does) -- proving the error.name check still correctly re-raises rather
    than being masked by the __name__ check alone."""
    script_path = str(pathlib.Path(gate.__file__))
    real_import = builtins.__import__

    def _fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "yaml":
            raise ModuleNotFoundError("No module named 'yaml.tokens'", name="yaml.tokens")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    with pytest.raises(ModuleNotFoundError) as exc_info:
        runpy.run_path(script_path, run_name="__main__")

    assert exc_info.value.name == "yaml.tokens"


# ---- the real gate ----


def test_real_repository_skills_have_no_dependency_allowlist_violations() -> None:
    assert gate.find_violations() == []
