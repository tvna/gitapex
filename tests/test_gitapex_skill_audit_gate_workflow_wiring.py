"""Drift gate: every `_PROCESS_DISCLOSURE_CHECKS` row must actually be
wired into `.github/workflows/skill-audit-gate.yml`.

Issue #673 (refs #665 repair 1). The registry in
`.github/scripts/gitapex_gate_skill_audit_disclosure.py` makes adding a
process-disclosure check look like a one-row edit -- an earlier revision of
its own comment said exactly that. It is not, and the gap is invisible:
applicability comes from the workflow, not from the table. Add a row and
skip the YAML edit and argparse still registers the flag with
`default=""`, so in real CI the list is empty, `_missing_in_section`
returns `[]`, and the check silently never fires. Every unit test calling
that row's `find_missing_*` wrapper directly still passes, because those
tests supply the item list themselves. CI stays green while the gate is
absent -- the same fail-open class the `deterministic-gate-quality` check
exists to catch, one layer up in the machinery that implements it.

That is what this file gates. It is deliberately a structural check on the
wiring rather than a behavioural one: missing any single edit produces a
different silent failure.

Issue #874 moved the applicability computation out of the workflow's bash
and into `.github/scripts/gitapex_compute_skill_audit_flags.py`, so the
wiring is now three edits -- the module's own output key, the `env:`
entry, and the CLI argument -- plus a fourth plane the same fail-open
reaches: `--check-diff`, the local pre-push wrapper, which fills the same
flags from that module and can drop a check just as silently.

The `.gitapex/ssot.json` registration is checked here too, for the same
reason: `gitapex_scan_ssot_schema.py` verifies every registered script path exists,
but nothing verified the converse for this gate's own helper scripts.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "skill-audit-gate.yml"
SSOT_PATH = REPO_ROOT / ".gitapex" / "ssot.json"

sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))
import gitapex_compute_skill_audit_flags as flags_module  # noqa: E402
import gitapex_gate_skill_audit_disclosure as gate  # noqa: E402


def _job_steps():
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    return workflow["jobs"]["skill-audit-disclosure"]["steps"]


def _step_with(key, needle):
    for step in _job_steps():
        if needle in step.get(key, ""):
            return step
    raise AssertionError(f"no step whose {key} contains {needle!r}")


@pytest.fixture(scope="module")
def diff_step():
    return _step_with("run", "$GITHUB_OUTPUT")


@pytest.fixture(scope="module")
def check_step():
    return _step_with("run", "gitapex_gate_skill_audit_disclosure.py")


@pytest.mark.parametrize("check", gate._PROCESS_DISCLOSURE_CHECKS, ids=lambda c: c.name)
def test_every_registered_check_is_passed_on_the_command_line(check, check_step):
    """Without this, the flag defaults to '' and the check never fires."""
    assert check.cli_flag in check_step["run"], (
        f"{check.name} is registered in _PROCESS_DISCLOSURE_CHECKS but "
        f"{check.cli_flag} is never passed to the gate script, so the check "
        "can never fire in CI"
    )


@pytest.mark.parametrize("check", gate._PROCESS_DISCLOSURE_CHECKS, ids=lambda c: c.name)
def test_every_registered_check_reads_a_step_output_through_env(check, check_step):
    """The value must arrive via `env:` indirection, never interpolated
    straight into the `run:` block (dimensions.md dimension 5)."""
    env = check_step.get("env", {})
    referenced = [name for name, value in env.items() if "steps.diff.outputs" in str(value)]
    assert referenced, "the check step reads no diff-step output at all"
    run = check_step["run"]
    # The flag's argument must be a shell expansion of one of those env
    # vars, not a literal or a `${{ }}` expression.
    flag_index = run.index(check.cli_flag) + len(check.cli_flag)
    argument = run[flag_index : flag_index + 60]
    assert any(f'"${name}"' in argument for name in referenced), (
        f"{check.cli_flag}'s argument is not an env-var expansion: {argument!r}"
    )


@pytest.mark.parametrize("check", gate._PROCESS_DISCLOSURE_CHECKS, ids=lambda c: c.name)
def test_every_registered_check_has_a_published_output_key(check):
    """The diff step must publish an output key for every registered check.

    Issue #874 changed how this can fail, not whether it can. The bash used
    to write the `$GITHUB_OUTPUT` block twice -- once on the early-exit
    (`applicable=false`) path and once on the applicable path -- so this
    test counted both occurrences: a key present on only one of them left
    the check step reading an empty string on the other, a silent skip
    rather than an error. There is now one serializer
    (`SkillAuditFlags.as_output_pairs`), which makes that particular
    divergence unrepresentable; what remains possible is a check whose key
    is never published at all, which is the same silent skip. That is what
    this asserts.
    """
    key = check.cli_flag.lstrip("-")
    assert key in flags_module.OUTPUT_KEYS, (
        f"'{key}' is registered in _PROCESS_DISCLOSURE_CHECKS but "
        "gitapex_compute_skill_audit_flags publishes no such output key, so "
        "the check step would read an empty string and never fire"
    )


def test_the_diff_step_publishes_its_keys_through_the_single_serializer():
    """Guards the test above: it is only a real gate while the workflow gets
    its `$GITHUB_OUTPUT` content from `as_output_pairs`. A step that went
    back to hand-writing keys in bash would satisfy every assertion here
    while re-opening the two-paths divergence."""
    run = _step_with("run", "$GITHUB_OUTPUT")["run"]
    assert "gitapex_compute_skill_audit_flags.py" in run
    assert "--format github-output" in run
    hand_written = [key for key in flags_module.OUTPUT_KEYS if f"{key}=" in run]
    assert not hand_written, f"the diff step hand-writes output keys instead of delegating: {hand_written}"


def test_no_published_output_key_is_consumed_by_nothing():
    """The reverse set difference of the per-check test above.

    `dimensions.md` dimension 20: a correspondence gate asserting only the
    direction its driving spec happened to enumerate first still passes
    while the other direction rots. Here the reverse case is a key left in
    `OUTPUT_KEYS` after the check that read it was removed or renamed --
    the workflow keeps publishing it, the grader reads nothing, and every
    forward assertion stays green.

    All four exclusions are named rather than wildcarded, and each is
    excluded for its own reason -- an unexplained exclusion in a
    reverse-direction drift gate is the exact failure mode it guards
    against. `applicable` gates whether the job's check step runs at all
    and `skill-md-changed` gates the base two-audit check, so neither is a
    process-disclosure check. `description-changed-skills` and
    `needs-eval-coverage-skills` *are* consumed by the grader, but through
    their own hand-declared argparse arguments rather than a
    `_PROCESS_DISCLOSURE_CHECKS` row, because their rules (rejecting a
    WAIVED verdict, requiring a waiver with no PASS/FAIL form) do not fit
    that table's uniform verdict-vocabulary shape. So none of the four has,
    or should have, a row -- and any *fifth* unconsumed key is the drift
    this asserts against.
    """
    consumed = {check.cli_flag.lstrip("-") for check in gate._PROCESS_DISCLOSURE_CHECKS}
    consumed |= {"applicable", "skill-md-changed"}
    consumed |= {"description-changed-skills", "needs-eval-coverage-skills"}
    orphaned = sorted(set(flags_module.OUTPUT_KEYS) - consumed)
    assert not orphaned, (
        f"gitapex_compute_skill_audit_flags publishes these keys that no "
        f"check reads: {orphaned}. Either wire them to a check or stop "
        "publishing them -- a key nothing consumes reads as coverage that "
        "is not there."
    )


def test_as_output_pairs_covers_exactly_the_declared_output_keys():
    """`OUTPUT_KEYS` is the contract the two tests above read; a serializer
    that drifted from it would make both of them assert about a list
    nothing publishes."""
    emitted = [key for key, _ in flags_module.SkillAuditFlags(applicable=False).as_output_pairs()]
    assert tuple(emitted) == flags_module.OUTPUT_KEYS


@pytest.mark.parametrize("check", gate._PROCESS_DISCLOSURE_CHECKS, ids=lambda c: c.name)
def test_every_registered_check_is_filled_by_the_local_check_diff_mode(check):
    """Issue #874's local pre-push wrapper needs the same drift gate as the
    workflow above, for the same reason.

    `--check-diff` fills the grader's list flags from a
    `SkillAuditFlags` field of the same name. A row added to
    `_PROCESS_DISCLOSURE_CHECKS` without a matching field would leave that
    flag at argparse's `default=""` -- the check silently never fires
    locally while every unit test calling its `find_missing_*` wrapper
    directly still passes, which is precisely the fail-open this file
    exists to catch, one plane over.
    """
    assert check.cli_dest in gate._LIST_FLAG_DESTS, (
        f"{check.name} is registered in _PROCESS_DISCLOSURE_CHECKS but "
        f"{check.cli_dest} is not in _LIST_FLAG_DESTS, so --check-diff would "
        "never fill it"
    )
    assert hasattr(flags_module.SkillAuditFlags(applicable=False), check.cli_dest), (
        f"gitapex_compute_skill_audit_flags.SkillAuditFlags publishes no "
        f"'{check.cli_dest}' field, so --check-diff cannot fill {check.name}"
    )


def _imported_module_names(source):
    """Every top-level module name `source` imports, by either spelling.

    `ast.ImportFrom` is handled alongside `ast.Import` deliberately: an
    earlier revision walked only the latter, so wiring in a helper as
    `from gitapex_helper import thing` -- the same import, spelled the
    other way -- silently escaped the registration gate below and left
    that helper outside `deterministic-gate-quality`'s registry scope.
    `node.level` filters relative imports, which cannot name a sibling
    module in this flat, package-less directory.

    Takes source text rather than a path so the spelling coverage can be
    asserted directly, instead of only through whichever forms this
    repository's own files happen to use today.
    """
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            names.add(node.module)
    return names


def _imported_sibling_scripts(relative):
    """The `.github/scripts` siblings `relative` imports."""
    scripts_dir = REPO_ROOT / ".github" / "scripts"
    source = (REPO_ROOT / relative).read_text(encoding="utf-8")
    return {
        f".github/scripts/{name}.py"
        for name in _imported_module_names(source)
        if (scripts_dir / f"{name}.py").is_file()
    }


def _reachable_helper_scripts():
    """Every .github/scripts file this gate's CI half actually executes.

    More than one hop, because issue #874 made it more than one: the
    workflow shells out to `gitapex_compute_skill_audit_flags.py`, which in
    turn *imports* the three helpers the workflow used to invoke directly.
    Scanning only the workflow text would quietly stop covering them the
    moment they moved behind that import, which is the drift this function
    exists to prevent -- an unregistered helper is outside the
    deterministic-gate-quality check's own registry-based scope, so
    changing it would require no disclosure.

    Followed to a fixed point rather than exactly two hops. A helper that
    itself imports a fourth script is just as much part of what this gate
    executes, and a depth-limited walk would stop covering it with no
    failure anywhere -- the same silent-narrowing class as the
    `ImportFrom` gap above. Every hop is derived, never a hardcoded list
    of known helper names: a list goes stale exactly when it matters.
    """
    run = "\n".join(step.get("run", "") for step in _job_steps())
    reachable = set(re.findall(r"\.github/scripts/[A-Za-z0-9_.-]+\.py", run))
    assert reachable, "the workflow invokes no .github/scripts helper at all"

    pending = sorted(reachable)
    while pending:
        discovered = _imported_sibling_scripts(pending.pop()) - reachable
        reachable |= discovered
        pending.extend(sorted(discovered))
    return reachable


def test_helper_scripts_the_workflow_invokes_are_registered_in_ssot():
    """Every .github/scripts helper this gate's CI half executes -- directly
    from the workflow or transitively through the module it calls -- is
    part of this gate's implementation, so the registry must say so."""
    invoked = _reachable_helper_scripts()
    registry = json.loads(SSOT_PATH.read_text(encoding="utf-8"))
    entry = next(g for g in registry["gates"] if g["id"] == "skill-audit-disclosure")
    registered = set(entry["script"])
    missing = sorted(invoked - registered)
    assert not missing, (
        "this gate's CI half executes these scripts but .gitapex/ssot.json's "
        f"skill-audit-disclosure entry does not register them: {missing}"
    )


def test_the_import_scan_covers_both_import_spellings():
    """Regression: the scan walked only `import x`, so a helper wired in as
    `from x import y` escaped the registration gate below with nothing
    failing -- the same silent-narrowing class the gate itself exists to
    catch. Relative imports stay excluded: they cannot name a sibling in
    this flat, package-less directory."""
    source = (
        "import gitapex_plain\n"
        "import gitapex_aliased as short\n"
        "from gitapex_fromform import thing\n"
        "from . import gitapex_relative\n"
        "from .gitapex_relative_mod import other\n"
    )
    assert _imported_module_names(source) == {"gitapex_plain", "gitapex_aliased", "gitapex_fromform"}


def test_the_transitive_helper_hop_actually_resolves():
    """Guards `_reachable_helper_scripts`: if the import scan silently found
    nothing, the registration test above would shrink back to the workflow
    text alone and pass vacuously while the three helpers went unregistered."""
    reachable = _reachable_helper_scripts()
    assert ".github/scripts/gitapex_detect_changed_gate_scripts.py" in reachable
    assert ".github/scripts/gitapex_skill_description_diff.py" in reachable
    assert ".github/scripts/gitapex_skill_security_relevance.py" in reachable


def test_gate_detection_helper_is_itself_in_scope_of_the_check_it_computes():
    """gitapex_detect_changed_gate_scripts.py decides whether
    deterministic-gate-quality fires. A change to it that silently narrowed
    the scope would be exactly the fail-open this whole check exists to
    catch, so it must be in its own scope."""
    sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))
    import gitapex_detect_changed_gate_scripts as detect

    registered = detect.registered_gate_paths(REPO_ROOT)
    assert detect.is_gate_path(".github/scripts/gitapex_detect_changed_gate_scripts.py", registered)


def test_every_registered_gate_path_is_reachable_by_the_paths_trigger():
    """The scope rule is self-maintaining; the `paths:` trigger is not.

    `gitapex_detect_changed_gate_scripts.py` puts every registered gate in scope
    the moment it is registered, with no edit there -- but if the job never
    starts, that scope is never consulted. Register a gate at a path no
    `paths:` entry matches (a `scripts/x.sh`, a `.github/workflows/*.yaml`
    where the list only had `*.yml`) and a PR touching only that file
    silently skips the whole check, with nothing failing. CLAUDE.md section
    3 requires an invariant's drift gate to ship with it; this is that gate
    for the registry-to-trigger correspondence.
    """
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    # `on:` parses as the boolean True under YAML 1.1.
    trigger = workflow[True] if True in workflow else workflow["on"]
    patterns = trigger["pull_request"]["paths"]

    sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))
    import gitapex_detect_changed_gate_scripts as detect

    scoped = set(detect.registered_gate_paths(REPO_ROOT))
    scoped.add(detect.SSOT_RELATIVE_PATH)
    scoped.add(detect.HOOK_WIRING_PATH)

    unreachable = sorted(p for p in scoped if not _matches_any(p, patterns))
    assert not unreachable, (
        "these paths are in the deterministic-gate-quality scope but no "
        f"`paths:` entry can start the job for them: {unreachable}"
    )


def _matches_any(path, patterns):
    """GitHub Actions path-filter semantics: `*` does not cross `/`, `**`
    does. Implemented here rather than with fnmatch, whose `*` crosses `/`
    and would make this test pass on patterns GitHub would not match."""
    for pattern in patterns:
        regex = ""
        i = 0
        while i < len(pattern):
            if pattern.startswith("**", i):
                regex += ".*"
                i += 2
            elif pattern[i] == "*":
                regex += "[^/]*"
                i += 1
            elif pattern[i] == "?":
                regex += "[^/]"
                i += 1
            else:
                regex += re.escape(pattern[i])
                i += 1
        if re.fullmatch(regex, path):
            return True
    return False


def test_the_paths_matcher_itself_behaves_like_github():
    """Guards the helper above: a matcher whose `*` crossed `/` would make
    the reachability assertion vacuous."""
    assert _matches_any("hooks/a.sh", ["hooks/**"])
    assert _matches_any("hooks/sub/a.sh", ["hooks/**"])
    assert _matches_any(".github/workflows/lint.yml", [".github/workflows/*.yml"])
    assert not _matches_any(".github/workflows/sub/lint.yml", [".github/workflows/*.yml"])
    assert not _matches_any(".github/workflows/lint.yaml", [".github/workflows/*.yml"])
    assert not _matches_any("scripts/x.sh", ["hooks/**", ".github/scripts/*.py"])
