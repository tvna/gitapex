"""Tests for the consolidated local pre-push gate runner (issue #876).

Two layers, kept apart on purpose:

- **Fixture-registry tests** build their own tiny ``ssot.json`` pointing at
  purpose-built pass/fail scripts, so the runner's own aggregation,
  discovery, error handling and exit-code logic are exercised in under a
  second with no dependence on this repository's real 18 wired gates. Issue
  #876's first acceptance criterion asks for an integration test running
  the consolidated command "with one deliberately-broken instance of each
  wired check, asserting all are reported in one run" --
  ``test_every_broken_gate_is_reported_in_one_run`` is that test, built on a
  fixture registry rather than by breaking the real gates, since the wired
  set is registry-driven and the real gates carry their own separate suites.

- **Real-registry tests** assert the live ``.gitapex/ssot.json`` still
  yields a usable wired set and that every wired gate's argv points at a
  file that exists. They deliberately do *not* run the real gates: that is
  what the runner itself is for, and running mypy inside pytest would add
  minutes to every suite.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

import _gitapex_argv_safety
import gitapex_gate_local_preflight
import gitapex_scan_ssot_schema
import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# A real, registered gate script. The bypass fixtures name it on purpose:
# keeping the gate's own script in the argv is what makes the existence and
# identity-drift checks report clean, so the argv-safety guard is the only
# layer left to catch the payload.
_REAL_GATE_SCRIPT = ".github/scripts/gitapex_gate_hidden_characters.py"


def _gate(
    gate_id: str,
    *,
    planes: list[str],
    local_invocation: list[str] | None = None,
    local_stdin: list[str] | None = None,
) -> dict[str, object]:
    """One minimally-shaped gates[] entry. Only the fields the runner itself
    reads are populated -- the full schema is gitapex_scan_ssot_schema.py's
    own subject, not this runner's."""
    gate: dict[str, object] = {"id": gate_id, "planes": planes}
    if local_invocation is not None:
        gate["local_invocation"] = local_invocation
    if local_stdin is not None:
        gate["local_stdin"] = local_stdin
    return gate


def _write_ssot(tmp_path: pathlib.Path, gates: list[dict[str, object]]) -> pathlib.Path:
    path = tmp_path / "ssot.json"
    path.write_text(json.dumps({"gates": gates}), encoding="utf-8")
    return path


def _write_script(tmp_path: pathlib.Path, name: str, body: str) -> pathlib.Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# load_local_checks: discovery
# --------------------------------------------------------------------------


def test_only_local_plane_gates_are_selected(tmp_path: pathlib.Path) -> None:
    ssot = _write_ssot(
        tmp_path,
        [
            _gate("ci-only", planes=["ci"]),
            _gate("hook-only", planes=["pretooluse"]),
            _gate("wired", planes=["ci", "local"], local_invocation=["true"]),
        ],
    )
    assert [check.gate_id for check in gitapex_gate_local_preflight.load_local_checks(ssot)] == ["wired"]


def test_checks_are_sorted_by_gate_id(tmp_path: pathlib.Path) -> None:
    ssot = _write_ssot(
        tmp_path,
        [
            _gate("zulu", planes=["local"], local_invocation=["true"]),
            _gate("alpha", planes=["local"], local_invocation=["true"]),
        ],
    )
    assert [check.gate_id for check in gitapex_gate_local_preflight.load_local_checks(ssot)] == ["alpha", "zulu"]


def test_local_stdin_is_carried_through(tmp_path: pathlib.Path) -> None:
    ssot = _write_ssot(
        tmp_path,
        [_gate("fed", planes=["local"], local_invocation=["cat"], local_stdin=["echo", "hi"])],
    )
    (check,) = gitapex_gate_local_preflight.load_local_checks(ssot)
    assert check.argv == ("cat",)
    assert check.stdin_argv == ("echo", "hi")


def test_missing_local_stdin_stays_none(tmp_path: pathlib.Path) -> None:
    ssot = _write_ssot(tmp_path, [_gate("plain", planes=["local"], local_invocation=["true"])])
    (check,) = gitapex_gate_local_preflight.load_local_checks(ssot)
    assert check.stdin_argv is None


# --------------------------------------------------------------------------
# load_local_checks: every registry shape that must raise rather than
# silently produce a short (falsely-clean) wired set
# --------------------------------------------------------------------------


def test_unreadable_registry_raises(tmp_path: pathlib.Path) -> None:
    with pytest.raises(gitapex_gate_local_preflight.PreflightRegistryError, match="cannot be read as UTF-8"):
        gitapex_gate_local_preflight.load_local_checks(tmp_path / "does-not-exist.json")


def test_non_utf8_registry_raises(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "ssot.json"
    path.write_bytes(b"\xff\xfe not utf-8")
    with pytest.raises(gitapex_gate_local_preflight.PreflightRegistryError, match="cannot be read as UTF-8"):
        gitapex_gate_local_preflight.load_local_checks(path)


def test_unparseable_registry_raises(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "ssot.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(gitapex_gate_local_preflight.PreflightRegistryError, match="cannot be parsed as JSON"):
        gitapex_gate_local_preflight.load_local_checks(path)


@pytest.mark.parametrize("document", ["[]", '"a string"', "{}", '{"gates": 1}'])
def test_registry_without_a_gates_array_raises(tmp_path: pathlib.Path, document: str) -> None:
    path = tmp_path / "ssot.json"
    path.write_text(document, encoding="utf-8")
    with pytest.raises(gitapex_gate_local_preflight.PreflightRegistryError, match="no 'gates' array"):
        gitapex_gate_local_preflight.load_local_checks(path)


def test_non_object_gate_entry_raises(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "ssot.json"
    path.write_text(json.dumps({"gates": [1]}), encoding="utf-8")
    with pytest.raises(gitapex_gate_local_preflight.PreflightRegistryError, match="non-object entry"):
        gitapex_gate_local_preflight.load_local_checks(path)


def test_gate_without_planes_is_skipped_not_raised(tmp_path: pathlib.Path) -> None:
    """A malformed `planes` is gitapex_scan_ssot_schema.py's finding to
    report, not a reason for this runner to refuse to run at all -- it just
    cannot be a local-plane gate."""
    path = tmp_path / "ssot.json"
    path.write_text(json.dumps({"gates": [{"id": "x"}, {"id": "y", "planes": "ci"}]}), encoding="utf-8")
    assert gitapex_gate_local_preflight.load_local_checks(path) == []


@pytest.mark.parametrize("gate_id", [None, "", 3])
def test_local_gate_without_a_usable_id_raises(tmp_path: pathlib.Path, gate_id: object) -> None:
    path = tmp_path / "ssot.json"
    path.write_text(
        json.dumps({"gates": [{"id": gate_id, "planes": ["local"], "local_invocation": ["true"]}]}),
        encoding="utf-8",
    )
    with pytest.raises(gitapex_gate_local_preflight.PreflightRegistryError, match="no usable 'id'"):
        gitapex_gate_local_preflight.load_local_checks(path)


@pytest.mark.parametrize("invocation", [None, [], "true", {}])
def test_bad_local_invocation_shape_raises(tmp_path: pathlib.Path, invocation: object) -> None:
    path = tmp_path / "ssot.json"
    path.write_text(
        json.dumps({"gates": [{"id": "x", "planes": ["local"], "local_invocation": invocation}]}),
        encoding="utf-8",
    )
    with pytest.raises(gitapex_gate_local_preflight.PreflightRegistryError, match="must be a non-empty array"):
        gitapex_gate_local_preflight.load_local_checks(path)


@pytest.mark.parametrize("element", [1, "", None])
def test_non_string_argv_element_raises(tmp_path: pathlib.Path, element: object) -> None:
    path = tmp_path / "ssot.json"
    path.write_text(
        json.dumps({"gates": [{"id": "x", "planes": ["local"], "local_invocation": ["true", element]}]}),
        encoding="utf-8",
    )
    with pytest.raises(gitapex_gate_local_preflight.PreflightRegistryError, match="only non-empty strings"):
        gitapex_gate_local_preflight.load_local_checks(path)


def test_bad_local_stdin_shape_raises(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "ssot.json"
    path.write_text(
        json.dumps({"gates": [{"id": "x", "planes": ["local"], "local_invocation": ["true"], "local_stdin": []}]}),
        encoding="utf-8",
    )
    with pytest.raises(
        gitapex_gate_local_preflight.PreflightRegistryError, match="local_stdin must be a non-empty array"
    ):
        gitapex_gate_local_preflight.load_local_checks(path)


# --------------------------------------------------------------------------
# load_local_checks: the pre-execution argv guard
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["sh", "-c", "echo pwned"],
        ["/bin/bash", "payload.sh"],
        ["env", "python3", "x.py"],
        ["uv", "run", "python3", "-c", "print('pwned')"],
    ],
)
def test_an_unsafe_argv_refuses_the_whole_run(tmp_path: pathlib.Path, argv: list[str]) -> None:
    """The guard must fire during discovery, not as one gate's failure: an
    argv this shape means the registry is untrustworthy, not that a single
    check is broken."""
    ssot = _write_ssot(tmp_path, [_gate("x", planes=["local"], local_invocation=argv)])
    with pytest.raises(gitapex_gate_local_preflight.PreflightRegistryError, match="refusing to run"):
        gitapex_gate_local_preflight.load_local_checks(ssot)


def test_an_unsafe_local_stdin_refuses_the_whole_run(tmp_path: pathlib.Path) -> None:
    ssot = _write_ssot(
        tmp_path,
        [_gate("x", planes=["local"], local_invocation=["true"], local_stdin=["sh", "-c", "echo x"])],
    )
    with pytest.raises(gitapex_gate_local_preflight.PreflightRegistryError, match="local_stdin"):
        gitapex_gate_local_preflight.load_local_checks(ssot)


@pytest.mark.slow
def test_an_unsafe_argv_runs_nothing_at_all(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The defect this closes, reconstructed: `ssot-schema-drift` carries the
    same predicates but is itself a wired gate, and not the first one in
    gate-id order, so a payload on an earlier-sorting gate executed *before*
    the guard evaluated it -- and the run still reported exit 0, because that scanner reads its
    own module-level SSOT_PATH rather than the registry the runner was given.
    Here the earlier-sorting gate writes a marker file; the guard must stop
    the run before it ever exists."""
    marker = tmp_path / "PWNED.txt"
    ssot = _write_ssot(
        tmp_path,
        [
            _gate("aaa-first", planes=["local"], local_invocation=["sh", "-c", f"touch {marker}"]),
            _gate("zzz-guard", planes=["local"], local_invocation=["true"]),
        ],
    )
    exit_code = gitapex_gate_local_preflight.main(["--ssot-path", str(ssot), "--repo-root", str(tmp_path)])
    assert exit_code == 1
    assert not marker.exists(), "the payload ran despite the pre-execution guard"
    assert "refusing to run" in capsys.readouterr().err


def test_the_guard_reuses_the_scanner_predicates_rather_than_re_deriving_them() -> None:
    """Two copies of this judgment would drift, and the copy in the weaker
    position would be the one that silently stopped matching. Both the
    runner and gitapex_scan_ssot_schema.py must resolve to the same module."""
    assert gitapex_gate_local_preflight._gitapex_argv_safety is gitapex_scan_ssot_schema._gitapex_argv_safety


def test_an_ordinary_pinned_invocation_is_not_refused(tmp_path: pathlib.Path) -> None:
    """The real registry's own shapes must survive the guard: a `uv run`
    pin, and git's `-c` config flag which is spelled like an inline-code
    flag but precedes no interpreter."""
    ssot = _write_ssot(
        tmp_path,
        [
            _gate(
                "real",
                planes=["local"],
                local_invocation=["uv", "run", "--frozen", "python3", ".github/scripts/x.py"],
                local_stdin=["git", "-c", "core.quotePath=false", "diff", "--merge-base", "origin/main", "HEAD"],
            )
        ],
    )
    assert [check.gate_id for check in gitapex_gate_local_preflight.load_local_checks(ssot)] == ["real"]


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        ((), 0),
        (("uv", "run", "--frozen", "python3", ".github/scripts/x.py"), 0),
        (("git", "-c", "core.quotePath=false", "diff"), 0),
        # Issue #904 finding 2, the mirror-image false positive: a `-c` that
        # belongs to the *gate script*, not to the interpreter, comes after
        # the interpreter's script argument and must still run. Refusing it
        # would abort every push, since the runner refuses the whole run.
        (("uv", "run", "--frozen", "python3", "script.py", "-c", "conf.json"), 0),
        # Real CPython options whose own letters overlap another
        # interpreter's inline-code flag. Matching a short flag inside a
        # combined cluster is what catches `-Bcprint(1)` below, so these
        # pin the other side of that rule.
        (("python3", "-Wignore::DeprecationWarning", "x.py"), 0),
        (("python3", "-Xfrozen_modules=off", "x.py"), 0),
        (("sh", "-c", "x"), 1),
        (("python3", "-c", "x"), 1),
        # Issue #904 finding 1, the three spellings an exact-token match
        # misses. Each was run before being asserted: CPython executes the
        # payload in all three.
        (("python3", "-cprint(1)"), 1),
        (("python3", "-Bcprint(1)"), 1),
        (("python3", "-X", "utf8", "-cprint(1)"), 1),
        # Same shape on the other interpreters, also run first: `perl`,
        # `ruby` and `php` all accept the concatenated form.
        (("perl", "-eprint('x')"), 1),
        (("perl", "-le", "print 'x'"), 1),
        (("ruby", "-eputs(1)"), 1),
        (("php", "-recho 1;"), 1),
        # `node` rejects the concatenated form and needs the flag as its own
        # token; `-p`/`--eval` were absent from the flag set entirely.
        (("node", "-p", "1"), 1),
        (("node", "--eval=1"), 1),
        # CPython has no `-e`, and adding one to its flag set would
        # false-flag every `-Wignore::...` above. The shell violation still
        # refuses this argv on its own.
        (("sh", "-c", "python3", "-e", "x"), 1),
        (("sh", "-c", "python3", "-cx"), 2),
        # A versioned interpreter binary is the same interpreter. Found by
        # re-reading the module adversarially for #904, not by the issue:
        # the old membership set listed `python`/`python3` literally, so
        # this was unguarded in the spelled-out form too.
        (("uv", "run", "--frozen", "python3.12", "-c", "x"), 1),
        (("uv", "run", "--frozen", "python3.12", "-cprint(1)"), 1),
        (("php8.2", "-recho 1;"), 1),
        # CodeRabbit's review of PR #910: CPython's free-threaded build and
        # a Windows `.exe` are the same interpreter under other names, and
        # both were unguarded in the spelled-out form too.
        (("python3.13t", "-cprint(1)"), 1),
        (("python3.13t.exe", "-cprint(1)"), 1),
        (("python3.exe", "-c", "print(1)"), 1),
        (("PYTHON3", "-c", "print(1)"), 1),
        # ... and the normalization must not invent interpreters that are
        # not there: `pytest3` strips to `pytest`, then the free-threaded
        # `t` rule would try `pytes`, and neither is an interpreter.
        (("uv", "run", "--frozen", "pytest3", "-c", "x"), 0),
        # Same review, second finding: an option *value* can carry a dot,
        # so a dot-or-slash script heuristic ended the span early and never
        # reached the payload. Both of these print when run.
        (("python3", "-X", "pycache_prefix=cache.dir", "-cprint(99)", "script.py"), 1),
        (("python3", "-W", "ignore::Dep:mypkg.mod", "-cprint(98)", "script.py"), 1),
        # Second review round: requiring a *script extension* on the
        # span-ending token narrowed that hole instead of closing it -- an
        # option value can end in `.py` just as easily. All three print when
        # run, and all three reported clean before the span was re-anchored
        # to position (a value is the token after an option) rather than to
        # the value's own shape.
        (("python3", "-W", "ignore:x.py", "-cprint(99)", "script.py"), 1),
        (("python3", "-X", "pycache_prefix=cache.py", "-cprint(99)", "script.py"), 1),
        (("python3", "-W", "x.py", "-cprint(99)", "script.py"), 1),
        (("node", "--require", "./pre.js", "-e", "payload"), 1),
        # The span must still end on a real script argument, in either
        # spelling of the path, and after an option/value pair.
        (("uv", "run", "--frozen", "python3", ".github/scripts/x.py", "-c", "conf.json"), 0),
        (("uv", "run", "--frozen", "python3", "-X", "utf8", "script.py", "-c", "conf.json"), 0),
        (("Rscript", "analysis.R", "-e", "conf"), 0),
        # A bare `-` makes the interpreter read its *program* from stdin,
        # which the runner wires to the gate's own `local_stdin` producer.
        # `echo "print('OWNED')" | python3 - /some/arg` prints OWNED.
        (("uv", "run", "--frozen", "python3", "-", ".github/scripts/x.py"), 1),
        # ... and so does naming no script at all.
        (("uv", "run", "--frozen", "python3"), 1),
        # ... but a `-` belonging to the gate script, past the span, does not.
        (("uv", "run", "--frozen", "python3", ".github/scripts/x.py", "-"), 0),
        # A later token merely *named* after an interpreter is an option
        # value, not an invocation with no script.
        (("uv", "run", "--frozen", "python3", ".github/scripts/x.py", "--interpreter", "node"), 0),
        # `pypy3` normalizes to `pypy`, which needed its own entry.
        (("pypy3", "-c", "print(1)"), 1),
    ],
)
def test_find_argv_safety_violations_directly(argv: tuple[str, ...], expected: int) -> None:
    """The shared predicate's own contract, including the empty-argv case
    that neither caller can reach (both reject an empty argv earlier as a
    shape violation) but which must still not raise."""
    assert len(_gitapex_argv_safety.find_argv_safety_violations(argv)) == expected


def test_a_concatenated_inline_code_flag_is_refused_by_every_layer(tmp_path: pathlib.Path) -> None:
    """Issue #904 finding 1, reproduced end to end rather than only at the
    predicate. The registry entry below passed all three layers on merged
    `main`: the guard returned no violation, `ssot-schema-drift` reported no
    drift, and the runner accepted it -- because the gate's own real script
    path is still present, so the existence and identity-drift checks see
    nothing wrong. The payload then ran on every `git push`."""
    argv = [
        "uv",
        "run",
        "--frozen",
        "python3",
        "-cprint('OWNED')",
        ".github/scripts/gitapex_gate_hidden_characters.py",
    ]
    assert _gitapex_argv_safety.find_argv_safety_violations(argv)

    # Against the real registry with that one field swapped, exactly as the
    # issue reproduced it -- a hand-built instance would not prove the
    # existence and identity-drift checks still see nothing wrong.
    instance = json.loads((REPO_ROOT / ".gitapex" / "ssot.json").read_text(encoding="utf-8"))
    for gate in instance["gates"]:
        if gate["id"] == "hidden-characters":
            gate["local_invocation"] = argv
    registry = gitapex_scan_ssot_schema._parse_registry(instance)
    assert registry is not None
    assert gitapex_scan_ssot_schema.find_local_invocation_drift(registry) == []
    assert gitapex_scan_ssot_schema.find_local_invocation_identity_drift(registry) == []
    assert gitapex_scan_ssot_schema.find_local_shell_argv(registry)

    ssot = _write_ssot(tmp_path, [_gate("hidden-characters", planes=["local"], local_invocation=argv)])
    with pytest.raises(gitapex_gate_local_preflight.PreflightRegistryError, match="refusing to run"):
        gitapex_gate_local_preflight.load_local_checks(ssot)


@pytest.mark.parametrize(
    "argv",
    [
        ["uv", "run", "--frozen", "python3", "-X", "pycache_prefix=cache.dir", "-cprint('OWNED')", "x.py"],
        ["uv", "run", "--frozen", "python3", "-W", "ignore::Dep:mypkg.mod", "-cprint('OWNED')", "x.py"],
        ["uv", "run", "--frozen", "python3.13t", "-cprint('OWNED')", "x.py"],
        # Second review round: the same class with a value that ends in a
        # script extension, which the extension-based span could not tell
        # from the script itself.
        ["uv", "run", "--frozen", "python3", "-W", "ignore:x.py", "-cprint('OWNED')", _REAL_GATE_SCRIPT],
        ["uv", "run", "--frozen", "python3", "-X", "pycache_prefix=cache.py", "-cprint('OWNED')", _REAL_GATE_SCRIPT],
        # ... and the stdin-program path, which needs no inline flag at all:
        # with a `local_stdin` producer wired in, this executes whatever the
        # producer emits.
        ["uv", "run", "--frozen", "python3", "-", _REAL_GATE_SCRIPT],
    ],
)
def test_a_payload_behind_a_dotted_option_value_is_refused_at_the_runner(
    tmp_path: pathlib.Path, argv: list[str]
) -> None:
    """CodeRabbit's review of PR #910 and the second review round after it,
    end to end rather than at the predicate alone. Each argv was run before
    being asserted: CPython consumes the value as an option value and still
    executes the payload, `python3.13t` is a real free-threaded binary name,
    and `echo "print('OWNED')" | python3 - /some/arg` prints OWNED."""
    ssot = _write_ssot(tmp_path, [_gate("payload", planes=["local"], local_invocation=argv)])
    with pytest.raises(gitapex_gate_local_preflight.PreflightRegistryError, match="refusing to run"):
        gitapex_gate_local_preflight.load_local_checks(ssot)


def test_a_gate_scripts_own_short_option_still_runs(tmp_path: pathlib.Path) -> None:
    """Issue #904 finding 2 at the runner: the check is anchored to the
    interpreter's own option span, so a `-c` the gate script itself takes
    does not refuse all wired gates and every push with them."""
    ssot = _write_ssot(
        tmp_path,
        [
            _gate(
                "takes-a-short-option",
                planes=["local"],
                local_invocation=["uv", "run", "--frozen", "python3", "script.py", "-c", "conf.json"],
            )
        ],
    )
    assert [check.gate_id for check in gitapex_gate_local_preflight.load_local_checks(ssot)] == ["takes-a-short-option"]


def test_the_live_registry_passes_its_own_guard() -> None:
    """Every wired gate in the real .gitapex/ssot.json must survive the
    guard -- otherwise the pre-push hook refuses every push."""
    assert gitapex_gate_local_preflight.load_local_checks()


# --------------------------------------------------------------------------
# run_check: one gate's verdict, including every not-a-real-exit-code path
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_passing_gate_is_a_pass(tmp_path: pathlib.Path) -> None:
    script = _write_script(tmp_path, "ok.py", "print('all good')\n")
    check = gitapex_gate_local_preflight.LocalCheck("ok", (sys.executable, str(script)))
    result = gitapex_gate_local_preflight.run_check(check, tmp_path)
    assert result.passed is True
    assert result.returncode == 0
    assert result.status == "PASS"
    assert "all good" in result.output


@pytest.mark.slow
def test_failing_gate_carries_its_own_output(tmp_path: pathlib.Path) -> None:
    script = _write_script(tmp_path, "bad.py", "import sys\nprint('boom', file=sys.stderr)\nsys.exit(3)\n")
    check = gitapex_gate_local_preflight.LocalCheck("bad", (sys.executable, str(script)))
    result = gitapex_gate_local_preflight.run_check(check, tmp_path)
    assert result.passed is False
    assert result.returncode == 3
    assert "boom" in result.output


def test_missing_executable_is_a_failure_not_a_skip(tmp_path: pathlib.Path) -> None:
    check = gitapex_gate_local_preflight.LocalCheck("gone", ("gitapex-no-such-binary-876",))
    result = gitapex_gate_local_preflight.run_check(check, tmp_path)
    assert result.passed is False
    assert result.returncode is None
    assert "failed to run" in result.output


def test_timeout_is_a_failure_naming_the_ceiling(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="slow", timeout=7)

    monkeypatch.setattr(gitapex_gate_local_preflight.subprocess, "run", fake_run)
    check = gitapex_gate_local_preflight.LocalCheck("slow", ("true",))
    result = gitapex_gate_local_preflight.run_check(check, tmp_path, timeout=7)
    assert result.passed is False
    assert result.returncode is None
    assert "timed out after 7s" in result.output


@pytest.mark.slow
def test_local_stdin_producer_feeds_the_gate(tmp_path: pathlib.Path) -> None:
    script = _write_script(
        tmp_path,
        "reads.py",
        "import sys\ndata = sys.stdin.read()\nsys.exit(0 if 'PAYLOAD' in data else 1)\n",
    )
    check = gitapex_gate_local_preflight.LocalCheck(
        "fed", (sys.executable, str(script)), (sys.executable, "-c", "print('PAYLOAD')")
    )
    assert gitapex_gate_local_preflight.run_check(check, tmp_path).passed is True


@pytest.mark.slow
def test_failing_local_stdin_producer_fails_the_gate(tmp_path: pathlib.Path) -> None:
    """A producer that exits non-zero must never let the gate run against a
    truncated or empty payload -- an empty diff is exactly the input a
    diff-scoped gate reports clean on."""
    check = gitapex_gate_local_preflight.LocalCheck(
        "fed",
        ("true",),
        (sys.executable, "-c", "import sys; print('nope', file=sys.stderr); sys.exit(2)"),
    )
    result = gitapex_gate_local_preflight.run_check(check, tmp_path)
    assert result.passed is False
    assert result.returncode is None
    assert "local_stdin producer" in result.output
    assert "nope" in result.output


@pytest.mark.slow
def test_non_utf8_gate_output_does_not_abort_the_run(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression: `text=True` decodes strictly, and the resulting
    UnicodeDecodeError is a ValueError -- caught by neither OSError nor
    SubprocessError. It escaped run_check entirely and aborted the whole
    aggregate pass with a traceback, so every later gate went unrun *and*
    unreported and no verdict was printed at all. The one live producer runs
    `git diff` under `core.quotePath=false`, which deliberately disables
    git's escaping of non-ASCII path bytes, so this is reachable."""
    emitter = _write_script(
        tmp_path, "emit.py", "import sys\nsys.stdout.buffer.write(b'bad \\xff\\xfe\\n')\nsys.exit(1)\n"
    )
    passing = _write_script(tmp_path, "ok.py", "print('ok')\n")
    ssot = _write_ssot(
        tmp_path,
        [
            _gate("aaa-bad-bytes", planes=["local"], local_invocation=[sys.executable, str(emitter)]),
            _gate("zzz-still-runs", planes=["local"], local_invocation=[sys.executable, str(passing)]),
        ],
    )
    exit_code = gitapex_gate_local_preflight.main(["--ssot-path", str(ssot), "--repo-root", str(tmp_path)])
    report = capsys.readouterr().out
    assert exit_code == 1
    assert "FAIL  aaa-bad-bytes" in report
    assert "PASS  zzz-still-runs" in report, "a decode failure in one gate must not lose the rest of the run"


@pytest.mark.slow
def test_non_utf8_local_stdin_producer_output_does_not_abort_the_run(tmp_path: pathlib.Path) -> None:
    """The same decode path, one layer up: the producer's own stdout."""
    emitter = _write_script(tmp_path, "emit.py", "import sys\nsys.stdout.buffer.write(b'\\xff\\xfe')\n")
    check = gitapex_gate_local_preflight.LocalCheck("fed", ("true",), (sys.executable, str(emitter)))
    result = gitapex_gate_local_preflight.run_check(check, tmp_path)
    assert result.passed is True, "a replacement-decoded producer payload is still a usable payload"


@pytest.mark.slow
def test_a_gate_without_a_producer_gets_no_inherited_stdin(tmp_path: pathlib.Path) -> None:
    """Without an explicit DEVNULL a gate with no local_stdin inherits this
    process's stdin, so a stdin-reading gate blocks until the per-gate
    timeout -- a half-hour silent hang on a contributor's pre-push at the
    production default, reported afterwards as a timeout that looks like a
    hung gate rather than a missing local_stdin declaration."""
    reader = _write_script(tmp_path, "reads.py", "import sys\nsys.exit(0 if sys.stdin.read() == '' else 1)\n")
    check = gitapex_gate_local_preflight.LocalCheck("reader", (sys.executable, str(reader)))
    result = gitapex_gate_local_preflight.run_check(check, tmp_path, timeout=20)
    assert result.passed is True
    assert result.returncode == 0


def test_unrunnable_local_stdin_producer_fails_the_gate(tmp_path: pathlib.Path) -> None:
    check = gitapex_gate_local_preflight.LocalCheck("fed", ("true",), ("gitapex-no-such-binary-876",))
    result = gitapex_gate_local_preflight.run_check(check, tmp_path)
    assert result.passed is False
    assert "local_stdin producer failed to run" in result.output


# --------------------------------------------------------------------------
# run_checks / format_report: the aggregate verdict
# --------------------------------------------------------------------------


def test_run_checks_runs_every_gate_even_after_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[str] = []

    def fake_run_check(
        check: gitapex_gate_local_preflight.LocalCheck, *_a: object, **_k: object
    ) -> gitapex_gate_local_preflight.CheckResult:
        ran.append(check.gate_id)
        return gitapex_gate_local_preflight.CheckResult(check.gate_id, check.gate_id != "b", 0, "")

    monkeypatch.setattr(gitapex_gate_local_preflight, "run_check", fake_run_check)
    checks = [gitapex_gate_local_preflight.LocalCheck(name, ("true",)) for name in ("a", "b", "c")]
    results = gitapex_gate_local_preflight.run_checks(checks, REPO_ROOT)
    assert ran == ["a", "b", "c"]
    assert [result.passed for result in results] == [True, False, True]


def test_run_checks_streams_progress_when_asked(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        gitapex_gate_local_preflight,
        "run_check",
        lambda check, *_a, **_k: gitapex_gate_local_preflight.CheckResult(check.gate_id, True, 0, ""),
    )
    checks = [gitapex_gate_local_preflight.LocalCheck(name, ("true",)) for name in ("a", "b")]
    gitapex_gate_local_preflight.run_checks(checks, REPO_ROOT, progress=sys.stderr)
    assert capsys.readouterr().err.splitlines() == ["[1/2] a ... PASS", "[2/2] b ... PASS"]


def test_report_lists_every_gate_and_summarises_a_clean_run() -> None:
    results = [
        gitapex_gate_local_preflight.CheckResult("a", True, 0, "fine"),
        gitapex_gate_local_preflight.CheckResult("b", True, 0, "fine"),
    ]
    report = gitapex_gate_local_preflight.format_report(results)
    assert "PASS  a" in report
    assert "PASS  b" in report
    assert "all 2 wired gate(s) passed." in report
    # A passing gate's own banner is deliberately dropped from the report.
    assert "fine" not in report


def test_report_names_every_failure_and_includes_its_output() -> None:
    results = [
        gitapex_gate_local_preflight.CheckResult("a", False, 1, "first problem"),
        gitapex_gate_local_preflight.CheckResult("b", True, 0, ""),
        gitapex_gate_local_preflight.CheckResult("c", False, None, "never started"),
    ]
    report = gitapex_gate_local_preflight.format_report(results)
    assert "--- a (exit 1) ---" in report
    assert "first problem" in report
    assert "--- c (did not complete) ---" in report
    assert "never started" in report
    assert "2 of 3 gate(s) FAILED: a, c" in report


def test_report_renders_a_failure_with_no_output_at_all() -> None:
    results = [gitapex_gate_local_preflight.CheckResult("a", False, 1, "")]
    assert "(no output)" in gitapex_gate_local_preflight.format_report(results)


# --------------------------------------------------------------------------
# main(): the consolidated command's own contract
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_every_broken_gate_is_reported_in_one_run(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Issue #876's first acceptance criterion: one deliberately-broken
    instance of each wired shape (a plain gate, a second plain gate, a
    stdin-fed gate, and one whose command does not exist at all), asserting
    every one of them is reported in a single run rather than the run
    stopping at the first red."""
    failing = _write_script(tmp_path, "fails.py", "import sys\nprint('broke')\nsys.exit(1)\n")
    reads = _write_script(tmp_path, "reads.py", "import sys\nsys.stdin.read()\nsys.exit(1)\n")
    passing = _write_script(tmp_path, "ok.py", "print('ok')\n")
    # A real script file, not `python3 -c '...'`: the pre-execution argv
    # guard refuses inline interpreter code, so a fixture using it would be
    # rejected during discovery rather than exercising the aggregation this
    # test is about.
    producer = _write_script(tmp_path, "producer.py", "print('diff')\n")
    ssot = _write_ssot(
        tmp_path,
        [
            _gate("broken-one", planes=["ci", "local"], local_invocation=[sys.executable, str(failing)]),
            _gate("broken-two", planes=["local"], local_invocation=[sys.executable, str(failing)]),
            _gate(
                "broken-stdin",
                planes=["local"],
                local_invocation=[sys.executable, str(reads)],
                local_stdin=[sys.executable, str(producer)],
            ),
            _gate("broken-missing", planes=["local"], local_invocation=["gitapex-no-such-binary-876"]),
            _gate("healthy", planes=["local"], local_invocation=[sys.executable, str(passing)]),
            _gate("not-local", planes=["ci"]),
        ],
    )

    exit_code = gitapex_gate_local_preflight.main(["--ssot-path", str(ssot), "--repo-root", str(tmp_path)])
    report = capsys.readouterr().out

    assert exit_code == 1
    for gate_id in ("broken-one", "broken-two", "broken-stdin", "broken-missing"):
        assert f"FAIL  {gate_id}" in report, f"{gate_id} was not reported in the single run"
    assert "PASS  healthy" in report
    assert "not-local" not in report
    assert "4 of 5 gate(s) FAILED" in report


@pytest.mark.slow
def test_exit_code_is_zero_when_every_wired_gate_passes(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    passing = _write_script(tmp_path, "ok.py", "print('ok')\n")
    ssot = _write_ssot(
        tmp_path,
        [
            _gate("a", planes=["local"], local_invocation=[sys.executable, str(passing)]),
            _gate("b", planes=["local"], local_invocation=[sys.executable, str(passing)]),
        ],
    )
    assert gitapex_gate_local_preflight.main(["--ssot-path", str(ssot), "--repo-root", str(tmp_path)]) == 0
    assert "all 2 wired gate(s) passed." in capsys.readouterr().out


def test_list_prints_the_wired_set_without_running_anything(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ssot = _write_ssot(
        tmp_path,
        [
            _gate("plain", planes=["local"], local_invocation=["echo", "one"]),
            _gate("fed", planes=["local"], local_invocation=["cat"], local_stdin=["echo", "two"]),
        ],
    )
    assert gitapex_gate_local_preflight.main(["--ssot-path", str(ssot), "--list"]) == 0
    out = capsys.readouterr().out
    assert "plain: echo one" in out
    assert "fed: cat" in out
    assert "fed: stdin < echo two" in out


def test_an_empty_wired_set_is_an_error_not_a_clean_run(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reporting "nothing to check" as exit 0 would turn a registry that lost
    its local plane into a green pre-push verdict."""
    ssot = _write_ssot(tmp_path, [_gate("ci-only", planes=["ci"])])
    assert gitapex_gate_local_preflight.main(["--ssot-path", str(ssot)]) == 1
    assert "carries the 'local' plane" in capsys.readouterr().err


def test_an_empty_wired_set_is_an_error_under_list_too(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--list is the command a contributor reaches for to inspect the wiring
    after a suspicious edit, so it must not be the one path that answers
    "the local plane is gone" with silence and exit 0."""
    ssot = _write_ssot(tmp_path, [_gate("ci-only", planes=["ci"])])
    assert gitapex_gate_local_preflight.main(["--ssot-path", str(ssot), "--list"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "carries the 'local' plane" in captured.err


def test_unreadable_registry_exits_one_with_a_message(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert gitapex_gate_local_preflight.main(["--ssot-path", str(tmp_path / "nope.json")]) == 1
    assert "error:" in capsys.readouterr().err


# --------------------------------------------------------------------------
# The real registry
# --------------------------------------------------------------------------


def test_real_registry_yields_a_non_empty_wired_set() -> None:
    checks = gitapex_gate_local_preflight.load_local_checks()
    assert checks, ".gitapex/ssot.json no longer wires any gate into the local preflight."


def test_every_wired_gate_argv_points_at_a_real_file() -> None:
    """The runner-side twin of gitapex_scan_ssot_schema.py's own
    find_local_invocation_drift: a renamed or deleted gate script must be
    caught here, not as an exit-127 "failure" on every contributor's
    machine. It reuses that scanner's own _looks_like_repo_path rather than
    re-deriving which argv tokens are paths -- two copies of that judgment
    would drift, and the copy in the weaker position would be the one that
    silently stopped matching."""
    missing = [
        f"{check.gate_id}: {token}"
        for check in gitapex_gate_local_preflight.load_local_checks()
        for token in (*check.argv, *(check.stdin_argv or ()))
        if gitapex_scan_ssot_schema._looks_like_repo_path(token) and not (REPO_ROOT / token).is_file()
    ]
    assert missing == [], f"local_invocation/local_stdin reference missing files: {missing}"


def test_every_wired_gate_is_registered_with_the_local_plane() -> None:
    """The wired set is exactly the registry's local-plane set -- this module
    contributes no gate names of its own, which is the property issue #876's
    third criterion asks for."""
    registry = json.loads((REPO_ROOT / ".gitapex" / "ssot.json").read_text(encoding="utf-8"))
    expected = sorted(gate["id"] for gate in registry["gates"] if "local" in gate["planes"])
    assert [check.gate_id for check in gitapex_gate_local_preflight.load_local_checks()] == expected


def test_the_preflight_is_wired_as_a_pre_push_hook() -> None:
    """The runner is only enforcement if something actually invokes it.
    Before this wiring existed its sole trigger was a contributor typing the
    command, which an isolated gate-quality audit reported as the headline
    finding against it (realized in no enforcement domain). This asserts the
    `pre-push` wiring keeps existing, so deleting the hook -- or quietly
    moving it to another stage, where it would grade a staged index it was
    never designed for -- fails here rather than silently returning the
    repository to a state where a green local run means nothing."""
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = [hook for repo in config["repos"] for hook in repo["hooks"]]
    matching = [hook for hook in hooks if "gitapex_gate_local_preflight.py" in hook["entry"]]
    assert len(matching) == 1, f"expected exactly one hook invoking the preflight, found {len(matching)}"
    hook = matching[0]
    assert hook["stages"] == ["pre-push"], f"preflight must stay a pre-push hook, got {hook.get('stages')}"
    # always_run + pass_filenames: false -- the preflight grades the whole
    # repository, so a push whose file list happens not to match any filter
    # must not skip it, and it takes no filenames.
    assert hook["always_run"] is True
    assert hook["pass_filenames"] is False


def test_the_default_stage_keeps_a_new_hook_off_the_push_path() -> None:
    """Issue #890 set `default_stages: [pre-commit]` so the ruff/mypy hooks,
    which declare no `stages` of their own, do not start running on every
    push once a pre-push shim exists. The preflight already covers ruff and
    mypy at pre-push through the registry's `python-lint`/`mypy-type-check`
    entries, so losing this key would run both twice per push.

    Issue #876 originally used `default_install_hook_types` here to make a
    bare `prek install` write both shims; that was dropped when this branch
    merged #890, which names both shims explicitly at every install site and
    verifies each one resolves afterwards. See the config's own comment."""
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    assert config.get("default_stages") == ["pre-commit"]


def test_only_deliberately_named_hooks_reach_the_push_path() -> None:
    """A hook reaches pre-push only by naming that stage explicitly. This
    pins the set, so a hook silently acquiring `stages: [pre-push]` -- or
    the preflight silently losing it -- fails here rather than changing what
    every contributor's push runs."""
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = [hook for repo in config["repos"] for hook in repo["hooks"]]
    pre_push = sorted(hook["id"] for hook in hooks if "pre-push" in hook.get("stages", []))
    assert pre_push == ["betterleaks-history", "local-preflight"], f"the pre-push hook set changed: {pre_push}"


def test_every_unwired_gate_records_why() -> None:
    """The drift-test branch of issue #876's third criterion: a gate with no
    working-tree form must say so in prose, so the 22 exclusions stay
    readable as decisions rather than as coverage silently lost. The schema
    enforces the same invariant; this asserts it against the live registry
    so a schema regression cannot pass unnoticed."""
    registry = json.loads((REPO_ROOT / ".gitapex" / "ssot.json").read_text(encoding="utf-8"))
    undocumented = [
        gate["id"]
        for gate in registry["gates"]
        if "local" not in gate["planes"] and not gate.get("local_exclusion", "").strip()
    ]
    assert undocumented == [], f"gates with neither a local invocation nor a recorded exclusion: {undocumented}"


# Every file that states a wired- or excluded-gate count in prose. Issue
# #904 finding 3: all six drifted to 16/21 while the registry moved to
# 17/22, and one of those figures was load-bearing rather than cosmetic.
# The scope is named here rather than repository-wide on purpose -- the
# `docs/` plans, `evals/` records and merged retrospectives are dated
# snapshots that are supposed to keep saying what was true when written.
# The residual is therefore real and disclosed: a count in a file outside
# this tuple is not covered.
# Every file scanned for a contradicting count.
_COUNT_SCANNED_PATHS = (
    "CONTRIBUTING.md",
    ".pre-commit-config.yaml",
    ".github/scripts/_gitapex_argv_safety.py",
    ".github/scripts/gitapex_gate_local_preflight.py",
    ".github/scripts/gitapex_scan_ssot_schema.py",
    "tests/test_gitapex_gate_local_preflight.py",
)

# The subset that must state at least one count, so the fail-closed check
# is per file rather than aggregate. An aggregate `assert claims` was the
# first version and a review caught it: two of the scanned files legitimately
# state no count any more (their ordinals were replaced by the property they
# rest on), so one surviving count anywhere satisfied it and a reword of
# CONTRIBUTING.md could have dropped that file from coverage unnoticed.
# The two property-stating files stay in the scanned tuple above -- they
# state no count today, and this pins that a reintroduced *wrong* one is
# still caught -- but they are deliberately absent here.
_COUNT_ASSERTING_PATHS = (
    "CONTRIBUTING.md",
    ".pre-commit-config.yaml",
    ".github/scripts/gitapex_gate_local_preflight.py",
    "tests/test_gitapex_gate_local_preflight.py",
)

# Digits immediately qualifying "wired" / "excluded" / "exclusions".
#
# Two deliberate exclusions. A numeral spelled out as an English word is
# not matched by this regex -- `_SPELLED_OUT_COUNT_RE` below bans the
# phrasing outright instead, which is cheaper to keep correct than an
# English-to-integer mapping. Every scanned file was reworded off that
# phrasing, `gitapex_scan_ssot_schema.py` included, where a review found a
# pair of them still present after the first pass.
# And `N wired gate(s)` is skipped by the lookahead: that is the runner's
# own summary line, a count it computes at runtime, asserted here against a
# two-gate fixture registry. Pinning it to the live registry would be
# wrong, not merely noisy.
_COUNT_CLAIM_RE = re.compile(r"(\d+)\s+(wired|excluded|exclusions)\b(?!\s+gate\(s\))")
_SPELLED_OUT_COUNT_RE = re.compile(
    r"\b(?:thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\s+"
    r"(?:wired|excluded|exclusions|gates|broken)",
    re.IGNORECASE,
)


def test_no_prose_count_contradicts_the_registry() -> None:
    """Issue #904's third acceptance criterion. Each count is checked
    against the live registry rather than against a constant restated here,
    so wiring gate 18 in fails on the prose that still says 17.

    Fail-closed **per file**, following
    `gitapex_gate_evals_scripts_coverage.py`'s own rule: a file in
    `_COUNT_ASSERTING_PATHS` that matches no count at all means the phrasing
    moved and this test silently stopped checking that file, which is
    indistinguishable from passing it."""
    registry = json.loads((REPO_ROOT / ".gitapex" / "ssot.json").read_text(encoding="utf-8"))
    planes = [gate["planes"] for gate in registry["gates"]]
    expected = {
        "wired": sum(1 for plane_list in planes if "local" in plane_list),
        "excluded": sum(1 for plane_list in planes if "local" not in plane_list),
    }
    expected["exclusions"] = expected["excluded"]

    silent: list[str] = []
    wrong: list[str] = []
    for relative_path in _COUNT_SCANNED_PATHS:
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        claims = _COUNT_CLAIM_RE.findall(text)
        if not claims and relative_path in _COUNT_ASSERTING_PATHS:
            silent.append(relative_path)
        wrong.extend(
            f"{relative_path}: says {stated} {noun}, registry has {expected[noun]}"
            for stated, noun in claims
            if int(stated) != expected[noun]
        )
        # A spelled-out count is invisible to the digit regex, so it would
        # drift silently. Rewrite it as a digit or as the property.
        wrong.extend(f"{relative_path}: spelled-out count {phrase!r}" for phrase in _SPELLED_OUT_COUNT_RE.findall(text))

    assert silent == [], f"files stating no wired/excluded count at all; the phrasing moved: {silent}"
    assert wrong == [], "prose counts contradicting .gitapex/ssot.json: " + "; ".join(wrong)
