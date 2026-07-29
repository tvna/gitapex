"""Tests for the Routine scope enforcement gate
(.github/scripts/gate_routine_scope_enforcement.py).

Issue #520 (row 2, refs #348): a Routine-connection doc wiring a
`capabilityAssumption: Broad` skill to a scheduled Routine must cite a
concrete, implemented scoping mechanism, not only a prompt-level
instruction.
"""

from __future__ import annotations

import gate_routine_scope_enforcement as gate


def _write_sidecar(tmp_path, name, capability):
    metadata_dir = tmp_path / "skills" / name / "metadata"
    metadata_dir.mkdir(parents=True)
    (metadata_dir / "gitapex.yaml").write_text(
        "apiVersion: gitapex.io/v1alpha1\n"
        "kind: SkillMetadata\n"
        "metadata:\n"
        f"  name: {name}\n"
        "spec:\n"
        "  portability: Portable\n"
        f"  capabilityAssumption: {capability}\n",
        encoding="utf-8",
    )


_PROMPT_ONLY_DOC = """\
# weekly Routine

Wires `skills/ranking-the-open-queue` to a scheduled Routine.

Read-only scope enforcement: the prompt instructs the model not to write
to any issue or pull request. This is prompt-level hardening only.
"""

_ENV_ID_DOC = """\
# weekly Routine

Wires `skills/ranking-the-open-queue` to a scheduled Routine.

Created with `environment_id: env_abc123`, a dedicated read-only-scoped
environment provisioned for this Routine specifically.
"""

_PERMISSIONS_DOC = """\
# weekly workflow

Wires `skills/ranking-the-open-queue` to a scheduled GitHub Actions workflow.

```yaml
permissions:
  contents: read
  issues: read
  pull-requests: read
```

Plus `claude_args: "--allowedTools mcp__github__list_issues"`.
"""

_PERMISSIONS_WITH_WRITE_DOC = """\
# weekly workflow

Wires `skills/ranking-the-open-queue` to a scheduled workflow.

```yaml
permissions:
  contents: read
  issues: write
```
"""

_DENY_HOOK_DOC = """\
# weekly Routine

Wires `skills/ranking-the-open-queue` to a scheduled Routine, backed by
`hooks/check-bash-safety.sh`, which will deny any write-tool call this
Routine's session attempts.
"""

_READONLY_CREDENTIAL_DOC = """\
# weekly Routine

Wires `skills/ranking-the-open-queue` to a scheduled Routine, authenticated
with a read-only-scoped credential that has no write permission at the API.
"""

_SUPERSEDED_DOC = """\
# weekly Routine

> **Superseded 2026-07-28.** Replaced by the GitHub Actions design.

Wires `skills/ranking-the-open-queue` to a scheduled Routine with only a
prompt-level instruction not to write.
"""

_NON_BROAD_DOC = """\
# some doc

Wires `skills/narrow-skill` to a scheduled Routine, prompt-only enforcement.
"""

_NO_SKILL_REF_DOC = """\
# unrelated doc

Nothing about a Routine or a skill here.
"""

_CAPABILITY_WITH_TRAILING_COMMENT = "spec:\n  capabilityAssumption: Broad  # confirmed 2026-07\n"

_PERMISSIONS_WITH_TRAILING_COMMENT_DOC = """\
# weekly workflow

Wires `skills/ranking-the-open-queue` to a scheduled workflow.

```yaml
permissions:
  contents: read
  issues: write  # reverted after incident
```
"""

_UNRELATED_DENY_AND_HOOK_DOC = """\
# weekly Routine

Wires `skills/ranking-the-open-queue` to a scheduled Routine. Formatting
is enforced by `hooks/pre-commit.sh`.

Reviewers may deny this PR if CI is red.
"""


def test_is_superseded():
    assert gate.is_superseded(_SUPERSEDED_DOC) is True
    assert gate.is_superseded(_PROMPT_ONLY_DOC) is False


def test_referenced_skill_names_dedupes():
    text = "skills/ranking-the-open-queue and skills/ranking-the-open-queue/SKILL.md"
    assert gate.referenced_skill_names(text) == ["ranking-the-open-queue"]


def test_capability_assumption():
    assert gate.capability_assumption("spec:\n  capabilityAssumption: Broad\n") == "Broad"
    assert gate.capability_assumption("spec:\n  portability: Portable\n") is None


def test_capability_assumption_tolerates_trailing_comment():
    assert gate.capability_assumption(_CAPABILITY_WITH_TRAILING_COMMENT) == "Broad"


def test_has_concrete_scoping_citation_env_id():
    assert gate.has_concrete_scoping_citation(_ENV_ID_DOC) is True


def test_has_concrete_scoping_citation_rejects_bare_env_id_mention():
    text = "Pass its `environment_id` when the Routine is finally created."
    assert gate.has_concrete_scoping_citation(text) is False


def test_has_concrete_scoping_citation_permissions_block():
    assert gate.has_concrete_scoping_citation(_PERMISSIONS_DOC) is True


def test_has_concrete_scoping_citation_rejects_permissions_block_with_write():
    assert gate.has_concrete_scoping_citation(_PERMISSIONS_WITH_WRITE_DOC) is False


def test_has_concrete_scoping_citation_rejects_permissions_block_with_write_trailing_comment():
    # A write-granting line with a trailing comment must not silently drop
    # out of the "all values are read" check.
    assert gate.has_concrete_scoping_citation(_PERMISSIONS_WITH_TRAILING_COMMENT_DOC) is False


def test_has_concrete_scoping_citation_deny_hook():
    assert gate.has_concrete_scoping_citation(_DENY_HOOK_DOC) is True


def test_has_concrete_scoping_citation_rejects_unrelated_deny_and_hook_mentions():
    # A hook path in one paragraph and an unrelated "deny" in another must
    # not combine into a false "named deny hook" citation.
    assert gate.has_concrete_scoping_citation(_UNRELATED_DENY_AND_HOOK_DOC) is False


def test_has_concrete_scoping_citation_readonly_credential():
    assert gate.has_concrete_scoping_citation(_READONLY_CREDENTIAL_DOC) is True


def test_has_concrete_scoping_citation_rejects_prompt_only():
    assert gate.has_concrete_scoping_citation(_PROMPT_ONLY_DOC) is False


def test_broad_skills_without_scoping_flags_prompt_only(tmp_path):
    _write_sidecar(tmp_path, "ranking-the-open-queue", "Broad")
    offenders = gate.broad_skills_without_scoping(_PROMPT_ONLY_DOC, tmp_path / "skills")
    assert offenders == ["ranking-the-open-queue"]


def test_broad_skills_without_scoping_passes_env_id(tmp_path):
    _write_sidecar(tmp_path, "ranking-the-open-queue", "Broad")
    assert gate.broad_skills_without_scoping(_ENV_ID_DOC, tmp_path / "skills") == []


def test_broad_skills_without_scoping_passes_permissions_block(tmp_path):
    _write_sidecar(tmp_path, "ranking-the-open-queue", "Broad")
    assert gate.broad_skills_without_scoping(_PERMISSIONS_DOC, tmp_path / "skills") == []


def test_broad_skills_without_scoping_skips_superseded(tmp_path):
    _write_sidecar(tmp_path, "ranking-the-open-queue", "Broad")
    assert gate.broad_skills_without_scoping(_SUPERSEDED_DOC, tmp_path / "skills") == []


def test_broad_skills_without_scoping_passes_non_broad_skill(tmp_path):
    _write_sidecar(tmp_path, "narrow-skill", "Narrow")
    assert gate.broad_skills_without_scoping(_NON_BROAD_DOC, tmp_path / "skills") == []


def test_broad_skills_without_scoping_no_skill_reference(tmp_path):
    assert gate.broad_skills_without_scoping(_NO_SKILL_REF_DOC, tmp_path / "skills") == []


def test_broad_skills_without_scoping_missing_sidecar_flagged(tmp_path):
    # Referenced skill has no sidecar under skills_root -- fail loud rather
    # than silently treat an unknown capabilityAssumption as "not Broad"
    # (a missing/renamed/typo'd sidecar must not silently defeat the gate).
    offenders = gate.broad_skills_without_scoping(_PROMPT_ONLY_DOC, tmp_path / "skills")
    assert len(offenders) == 1
    assert "unverifiable" in offenders[0]


def test_main_fails_on_prompt_only_doc(tmp_path, capsys):
    _write_sidecar(tmp_path, "ranking-the-open-queue", "Broad")
    doc = tmp_path / "routine-doc.md"
    doc.write_text(_PROMPT_ONLY_DOC, encoding="utf-8")
    exit_code = gate.main(["--skills-root", str(tmp_path / "skills"), str(doc)])
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().err


def test_main_passes_on_env_id_doc(tmp_path, capsys):
    _write_sidecar(tmp_path, "ranking-the-open-queue", "Broad")
    doc = tmp_path / "routine-doc.md"
    doc.write_text(_ENV_ID_DOC, encoding="utf-8")
    exit_code = gate.main(["--skills-root", str(tmp_path / "skills"), str(doc)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_missing_file_errors(tmp_path, capsys):
    exit_code = gate.main(["--skills-root", str(tmp_path / "skills"), str(tmp_path / "missing.md")])
    assert exit_code == 1
    assert "error" in capsys.readouterr().err


def test_real_repo_routine_docs_pass():
    """Live-document regression check: both real ranking-the-open-queue
    Routine-connection docs in this repository must pass -- the superseded
    Cloud-Routine doc (skipped via its own banner) and the shipped GitHub
    Actions doc (passes via its permissions:/--allowedTools citation)."""
    exit_code = gate.main(
        [
            "--skills-root",
            "skills",
            "docs/superpowers/specs/2026-07-25-ranking-the-open-queue-weekly-routine.md",
            "docs/superpowers/specs/2026-07-28-ranking-the-open-queue-github-actions-routine.md",
        ]
    )
    assert exit_code == 0
