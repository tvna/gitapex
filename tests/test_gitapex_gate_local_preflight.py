"""Tests for the consolidated local pre-push gate runner (issue #876).

Two layers, kept apart on purpose:

- **Fixture-registry tests** build their own tiny ``ssot.json`` pointing at
  purpose-built pass/fail scripts, so the runner's own aggregation,
  discovery, error handling and exit-code logic are exercised in under a
  second with no dependence on this repository's real 16 wired gates. Issue
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
import subprocess
import sys

import gitapex_gate_local_preflight
import gitapex_scan_ssot_schema
import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


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
    ssot = _write_ssot(
        tmp_path,
        [
            _gate("broken-one", planes=["ci", "local"], local_invocation=[sys.executable, str(failing)]),
            _gate("broken-two", planes=["local"], local_invocation=[sys.executable, str(failing)]),
            _gate(
                "broken-stdin",
                planes=["local"],
                local_invocation=[sys.executable, str(reads)],
                local_stdin=[sys.executable, "-c", "print('diff')"],
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


def test_prek_install_wires_the_pre_push_shim_without_a_flag() -> None:
    """`default_install_hook_types` is what makes a bare `prek install`
    write .git/hooks/pre-push, not just pre-commit. Without it the hook
    above would sit in the config doing nothing on every existing clone --
    the same "configured but never installed" gap that left
    .git/hooks/pre-commit a .sample file before issue #725."""
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    assert "pre-push" in config.get("default_install_hook_types", [])


def test_the_pre_commit_stage_hooks_do_not_also_run_at_pre_push() -> None:
    """ruff/mypy are the fast pre-commit pass; the preflight already covers
    both again at pre-push through the registry's `python-lint` and
    `mypy-type-check` entries. Leaving their `stages` unset would make
    pre-commit's own default (every stage) run mypy twice on every push."""
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = [hook for repo in config["repos"] for hook in repo["hooks"]]
    for hook in hooks:
        if "gitapex_gate_local_preflight.py" in hook["entry"]:
            continue
        assert hook.get("stages") == ["pre-commit"], (
            f"hook {hook['id']!r} would also run at pre-push, duplicating the preflight's own coverage"
        )


def test_every_unwired_gate_records_why() -> None:
    """The drift-test branch of issue #876's third criterion: a gate with no
    working-tree form must say so in prose, so the 21 exclusions stay
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
