"""Shared pytest fixtures/helpers for this repository's tests/ suite."""

from __future__ import annotations

import io
import pathlib
import re
import subprocess
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


class _Unsatisfiable(BaseModel):
    """Throwaway model with one required field, used only by
    `make_validation_error` below to manufacture a real pydantic
    `ValidationError` instance."""

    required: int


def make_validation_error() -> ValidationError:
    """A genuine `pydantic.ValidationError` instance, for monkeypatching a
    gate's own `*Args` model class to exercise its `except ValidationError`
    branch in tests. Several `.github/scripts/gitapex_gate_*.py` gates
    (issue #1062, wave 3 of #1040's batch) wrap `argparse`-guaranteed CLI
    input in a pydantic model whose fields can never actually fail
    validation from real CLI input -- their `except ValidationError` branch
    is therefore only reachable by monkeypatching the model class itself to
    raise, not by constructing genuinely invalid input."""
    try:
        _Unsatisfiable()  # type: ignore[call-arg]
    except ValidationError as error:
        return error
    raise AssertionError("expected ValidationError")


class FakeStdin:
    """Just the surface a CLI's `main()` uses: `sys.stdin.buffer.read()`.

    Shared by every test that monkeypatches `sys.stdin` to feed a script
    non-UTF-8 (or otherwise arbitrary) bytes through its
    `sys.stdin.buffer.read().decode("utf-8")` read path, so a future change
    to this mock's surface only needs to land once (same rationale as
    `assert_path_is_gitignored` below).
    """

    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)


# git check-ignore -v prefixes a match with "source:linenum:pattern", then a
# tab and the matched pathname. The pattern (and, in principle, a Windows
# drive-letter source path) can itself contain colons, so a plain split on
# the first ":" can misidentify the source -- anchoring on ":<digits>:" (the
# linenum field, which is always a bare integer) instead finds the correct
# boundary regardless of what precedes or follows it.
_CHECK_IGNORE_SOURCE_RE = re.compile(r"^(.*):\d+:")


def assert_path_is_gitignored(path: pathlib.Path, description: str) -> None:
    """Assert ``path`` is ignored by this repository's own tracked
    `.gitignore` (not an ambient exclude source elsewhere on the machine).

    Shared by every `test_gitignore_*.py` drift gate so a future fix to
    the ambient-exclude-source check only needs to land once.
    """
    result = subprocess.run(
        ["git", "check-ignore", "-v", str(path)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"{description} is no longer covered by .gitignore."
    match = _CHECK_IGNORE_SOURCE_RE.match(result.stdout)
    assert match is not None, f"could not parse 'git check-ignore -v' output for {description}: {result.stdout!r}"
    source = match.group(1)
    repo_gitignore = REPO_ROOT / ".gitignore"
    assert pathlib.Path(source).resolve() == repo_gitignore.resolve(), (
        f"{description} is ignored, but by {source!r} instead of this "
        f"repository's own {repo_gitignore} -- an ambient exclude source "
        "(global core.excludesFile, $GIT_DIR/info/exclude) is masking a "
        "possibly-removed repository rule."
    )


def _parse_workflow(workflow_name: str) -> Any:
    """`.github/workflows/<workflow_name>` parsed as YAML."""
    return yaml.safe_load((REPO_ROOT / ".github" / "workflows" / workflow_name).read_text(encoding="utf-8"))


def _workflow_steps(workflow_name: str) -> list[Any]:
    """Every `jobs.*.steps[]` entry of `.github/workflows/<workflow_name>`."""
    return [step for job in _parse_workflow(workflow_name)["jobs"].values() for step in job.get("steps", [])]


def assert_workflow_has_no_trigger_path_filter(workflow_name: str) -> None:
    """Assert `.github/workflows/<workflow_name>`'s trigger carries neither a
    `paths:` nor a `paths-ignore:` filter, in any YAML style.

    Shared by every gate workflow's own no-paths-filter drift test (same
    rationale as `assert_path_is_gitignored` above), so the two things that
    make the check trustworthy only land once. `paths-ignore:` is rejected
    too, not only `paths:`: GitHub's own trigger filter accepts either key to
    the same stuck-Pending effect, so a future edit reaching for the inverse
    form would defeat a `paths:`-only check while recreating the exact
    failure mode these tests exist to catch.

    The trigger keys are read off the parsed YAML rather than matched
    line-by-line against the text between the `on:` and `permissions:`
    markers, which is how this started. That text scan carried two defects,
    the first of them fail-open:

    * a line-prefix scan only ever sees a filter written in block style on a
      line of its own. Rewriting the trigger in flow style --
      `pull_request: {paths: ["hooks/**"]}`, which is the very style
      `plugin-root-brace-notation-gate.yml` already writes its own trigger
      in -- left a real, parser-visible filter passing the check. Verified
      live. A quoted `"paths":` key defeats the prefix scan the same way;
    * isolating the block by splitting on a `permissions:` marker assumed a
      top-level `permissions:` always follows `on:`. That is positional
      rather than structural: it holds in all three callers today and
      silently widens the scanned region to the rest of the file the moment
      one of them reorders.

    Parsing costs one lookup to work around PyYAML's default YAML-1.1
    resolver reading the bare `on` key as boolean `True` rather than the
    string `"on"` -- the well-known GitHub Actions gotcha the text scan
    existed to sidestep, and a far cheaper thing to handle than the
    fail-open above. Comments stop needing to be stripped at all, since the
    parser never offers them: each caller's own pointer comment for this
    very invariant contains the literal substring `` `paths:` `` in prose.
    Each caller's own docstring states why its workflow must stay
    unfiltered.
    """
    parsed = _parse_workflow(workflow_name)
    trigger = parsed[True] if True in parsed else parsed["on"]
    # `on: push` and `on: [push, pull_request]` leave nowhere to hang a
    # filter; only the mapping form does, at either of its two levels.
    blocks = (
        [trigger, *(event for event in trigger.values() if isinstance(event, dict))]
        if isinstance(trigger, dict)
        else []
    )
    filters = sorted(str(key) for block in blocks for key in block if str(key).startswith("paths"))
    assert not filters, f"{workflow_name}'s trigger carries {filters}: {trigger}"


_MERGE_BASE_CALL = 'merge_base=$(git merge-base "$BASE_SHA" "$HEAD_SHA")'


def _strip_shell_comments(script: str) -> str:
    """`script` with its `#` comments removed.

    A `#` opens a comment only at the start of a word and only outside
    quotes. That is POSIX's own rule rather than a simplification of it, and
    the distinction is load-bearing here: one of the real producer lines
    this is run over is `git ls-tree ... | sed -E 's#^skills/##' | sort`,
    whose three `#` characters are all data.
    """
    stripped = []
    for line in script.split("\n"):
        quote = ""
        cut = len(line)
        for index, char in enumerate(line):
            if quote:
                quote = "" if char == quote else quote
            elif char in "\"'":
                quote = char
            elif char == "#" and (index == 0 or line[index - 1].isspace()):
                cut = index
                break
        stripped.append(line[:cut])
    return "\n".join(stripped)


def assert_workflow_feeds_merge_base_to(workflow_name: str, *producer_commands: str) -> None:
    """Assert `.github/workflows/<workflow_name>` both computes `$merge_base`
    from the exact `"$BASE_SHA" "$HEAD_SHA"` pair and feeds it to a line
    running one of `producer_commands` (`"diff"`, `"ls-tree"`).

    Shared by every gate workflow's own merge-base drift test (same rationale
    as `assert_path_is_gitignored` above), so the hardening steps these
    assertions took only land once rather than four times over:

    * the producer line is asserted, not only the `git merge-base` call --
      otherwise a workflow that computes `$merge_base` and then never uses it
      (falling back to `$BASE_SHA` in the producer command) still passes;
    * the exact `"$BASE_SHA" "$HEAD_SHA"` argument pair is required, so a
      swapped or substituted variable no longer matches;
    * both assertions are scoped to the parsed `jobs.*.steps[].run` content
      rather than the whole file as text, so no YAML comment and no
      non-comment YAML value outside a `run:` block (a step `name:`, for
      one) can satisfy them while the real invariant is gone from the
      executable content;
    * the producer line must carry the word `git` followed later by one of
      `producer_commands` as a word, not merely that command as a bare
      substring -- an unrelated executable line (`echo 'diff "$merge_base"'`)
      would otherwise satisfy the check. The two words are matched with `.*`
      between them rather than contiguously, because the real invocations
      read `git -c core.quotePath=false diff ...`, with a flag in between;
    * that `run:` content then has its *shell* comments stripped, which
      scoping to parsed `run:` blocks does not do: a `#` comment written
      inside a step's own script survives parsing as ordinary script text.
      Restating the removed logic in one -- a "this used to read ..." note
      left above the replacement -- satisfied both assertions while the
      executable command diffed `"$BASE_SHA"` directly. Verified live;
    * no producer line may name `"$BASE_SHA"` at all, which is the half of
      "merge-base, not base.sha" that went unasserted while only the
      positive half was checked. This holds independently of how any
      comment is written.

    Both assertions must also be satisfied by one and the same step, not by
    two different ones: `$merge_base` is a plain shell variable, so a
    producer in some later step could never have read it anyway.

    `on:` is deliberately never parsed here -- PyYAML's default YAML-1.1
    resolver reads the bare `on` key as boolean `True`, not the string
    `"on"`, a well-known GitHub Actions YAML gotcha this sidesteps by never
    needing that key. Each caller's own docstring states why its workflow
    must not diff against `base.sha` directly.
    """
    producer_re = re.compile(
        r"\bgit\b.*(" + "|".join(rf"\b{re.escape(command)}\b" for command in producer_commands) + ")"
    )
    scripts = [_strip_shell_comments(step["run"]) for step in _workflow_steps(workflow_name) if "run" in step]
    fed_merge_base = False
    for script in scripts:
        producers = [line for line in script.split("\n") if producer_re.search(line)]
        assert not [line for line in producers if '"$BASE_SHA"' in line], producers
        fed_merge_base = fed_merge_base or (
            _MERGE_BASE_CALL in script and any('"$merge_base"' in line for line in producers)
        )
    assert fed_merge_base, scripts


# The one `ref:` value that makes a checked-out tree *be* the diff's
# post-image, which is what the two line-number-correlating gates need.
_HEAD_SHA_REF = "${{ github.event.pull_request.head.sha }}"


def assert_workflow_checkout_pins_head_sha_with_full_history(workflow_name: str) -> None:
    """Assert every `harden-checkout` step in
    `.github/workflows/<workflow_name>` passes `ref: <head sha>` and
    `fetch-depth: 0`.

    Shared by the two gate workflows that correlate diff-derived line numbers
    against tree content (same rationale as `assert_path_is_gitignored`
    above), so this check cannot silently diverge between them. Each caller's
    own docstring states why its gate needs the pin.

    Scoped to the parsed `jobs.*.steps[].with` mapping rather than checked
    against the whole file as text, for the reason the merge-base assertions
    below were already scoped to parsed `run:` content: both workflows' own
    pointer comment for this very invariant contains the literal substring
    `fetch-depth: '0'` in prose, so a whole-file text check passes off the
    comment alone with the real input deleted -- verified live, and the exact
    defect class this repository had already had to close once.

    Asserted over *every* `harden-checkout` step, not merely one of them: an
    `any()` would let a second, unpinned checkout be added beside the pinned
    one, which is precisely the state that breaks the post-image
    correlation. The non-empty guard is what keeps that `for` from passing
    vacuously if the checkout step is renamed or dropped outright.

    `fetch-depth` is compared as text (`'0'` and `0` both parse to the same
    single input value) because the composite action declares it as an
    action input and interpolates it into `actions/checkout`'s own
    `fetch-depth` -- see `.github/actions/harden-checkout/action.yml`. The
    YAML quoting therefore carries no meaning of its own to assert.
    """
    checkouts = [
        step.get("with") or {} for step in _workflow_steps(workflow_name) if "harden-checkout" in str(step.get("uses"))
    ]
    assert checkouts, f"{workflow_name} has no harden-checkout step"
    for inputs in checkouts:
        assert inputs.get("ref") == _HEAD_SHA_REF, inputs
        assert str(inputs.get("fetch-depth")) == "0", inputs
