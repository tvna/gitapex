"""Tests for check_middleware_table_shape.py.

Fixtures are synthesized in-memory (no repository file is read) so the
test is self-contained and travels with the skill on vendoring. Not
wired into the root pyproject.toml testpaths -- this skill's checklist
item is meant to stand alone (same approach as
git-hosting-surface-audit/scripts/test_scan_unpinned_actions.py); run
directly with:
    python3 -m pytest skills/auditing-agent-product-scope/scripts/
"""

import check_middleware_table_shape as cmts

_COMPLETE_DOC = """\
## Nix toolchain (`flake.nix`)

| Tool | Class | Why needed | Scope of responsibility | Supply-chain coverage |
|---|---|---|---|---|
| `uv` | A | manages deps | dev group only | Dependabot `nix` |
| `gh` | A | repo interaction | write blocked by a hook | Dependabot `nix` |
| `actionlint` | A | lints workflows | wired into lint.yml | Dependabot `nix` |
| `python312` | A | runtime | base interpreter | Dependabot `nix` |
| `bun` | A | JS/TS runtime | provisioned only | Dependabot `nix` |
| `lychee` | A | link checker | provisioned only | Dependabot `nix` |
| `waza` | B | eval CLI | see waza section | excluded |
| `apm` | B | regenerates docs | see apm section | excluded |
| `rtk` | B | token-reducing proxy | provisioned only | excluded |
| `betterleaks` | B | secrets scanner | provisioned only | excluded |

## apm

| Dependency | Why needed | Scope of responsibility | Pinned in |
|---|---|---|---|
| `apm` (the tool itself) | regenerates docs | tool's own version | apm.lock.yaml |
| `obra/superpowers` | a plugin assumed installed | pinned commit | apm.lock.yaml |
| `tvna/clairvoyance` | a plugin assumed installed | pinned commit | apm.lock.yaml |

## Python dev tooling

| Package | Why needed | Scope of responsibility |
|---|---|---|
| `pytest` | test runner | runs the suites |
| `pytest-cov` | coverage | reports coverage |
| `pyyaml` | YAML parsing | used by checker scripts |
| `prek` | pre-commit runner | no config file wired up |

## GitHub MCP server

| Attribute | Detail |
|---|---|
| Why needed | sole hard dependency for several skills |
| Scope of responsibility | not tied to a specific hook |
| Coverage / alternative | no GitLab MCP server exists |

## Supply-chain coverage summary

| Ecosystem | Bumps | Covers Class B binaries? |
|---|---|---|
| `nix` | nixpkgs input | No |
| `github-actions` | SHA-pinned actions | N/A |
| `uv` | dev tools | No |
"""


def test_complete_doc_passes():
    assert cmts.check_middleware_table_shape(_COMPLETE_DOC) == []


def test_missing_section_heading_flagged():
    text = _COMPLETE_DOC.replace("## apm\n", "## renamed-by-mistake\n")
    offenses = cmts.check_middleware_table_shape(text)
    assert any(o.startswith("apm:") and "no '## apm'" in o for o in offenses)


def test_section_with_no_table_flagged():
    text = _COMPLETE_DOC.replace(
        "| `pytest` | test runner | runs the suites |\n"
        "| `pytest-cov` | coverage | reports coverage |\n"
        "| `pyyaml` | YAML parsing | used by checker scripts |\n"
        "| `prek` | pre-commit runner | no config file wired up |\n",
        "Just some prose, no table here.\n",
    )
    # Dropping every data row still leaves the header + separator, which
    # is a real (if empty) table -- to genuinely remove the table we
    # also need to drop the header/separator lines themselves.
    text = text.replace(
        "| Package | Why needed | Scope of responsibility |\n|---|---|---|\n",
        "",
    )
    offenses = cmts.check_middleware_table_shape(text)
    assert any(
        o.startswith("Python dev tooling:") and "none found" in o for o in offenses
    )


def test_missing_column_flagged():
    text = _COMPLETE_DOC.replace(
        "| Tool | Class | Why needed | Scope of responsibility | Supply-chain coverage |",
        "| Tool | Class | Scope of responsibility | Supply-chain coverage |",
    ).replace(
        "|---|---|---|---|---|\n| `uv` | A | manages deps | dev group only | Dependabot `nix` |",
        "|---|---|---|---|\n| `uv` | A | dev group only | Dependabot `nix` |",
    )
    offenses = cmts.check_middleware_table_shape(text)
    assert any(
        o.startswith("Nix toolchain (`flake.nix`):") and "Why needed" in o
        for o in offenses
    )


def test_missing_row_flagged():
    text = _COMPLETE_DOC.replace(
        "| `betterleaks` | B | secrets scanner | provisioned only | excluded |\n", ""
    )
    offenses = cmts.check_middleware_table_shape(text)
    assert any(
        o.startswith("Nix toolchain (`flake.nix`):") and "betterleaks" in o
        for o in offenses
    )


def test_second_table_missing_row_does_not_flag_first_table():
    text = _COMPLETE_DOC.replace(
        "| `tvna/clairvoyance` | a plugin assumed installed | pinned commit | apm.lock.yaml |\n",
        "",
    )
    offenses = cmts.check_middleware_table_shape(text)
    assert len(offenses) == 1
    assert offenses[0].startswith("apm:")
    assert "clairvoyance" in offenses[0]


def test_multiple_offenses_all_reported():
    text = _COMPLETE_DOC.replace(
        "| `rtk` | B | token-reducing proxy | provisioned only | excluded |\n", ""
    ).replace("## GitHub MCP server", "## Renamed Section")
    offenses = cmts.check_middleware_table_shape(text)
    assert any("rtk" in o for o in offenses)
    assert any("GitHub MCP server" in o and "no '##" in o for o in offenses)
    assert len(offenses) == 2


def test_cli_pass(tmp_path, capsys):
    doc = tmp_path / "inventory.md"
    doc.write_text(_COMPLETE_DOC)
    exit_code = cmts.main([str(doc)])
    assert exit_code == 0
    assert "PASS" in capsys.readouterr().out


def test_cli_fail(tmp_path, capsys):
    doc = tmp_path / "inventory.md"
    doc.write_text("# No expected sections here\n")
    exit_code = cmts.main([str(doc)])
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().err


def test_cli_missing_file(capsys):
    exit_code = cmts.main(["/nonexistent/path/inventory.md"])
    assert exit_code == 1
    assert "error" in capsys.readouterr().err


def test_lone_pipe_line_at_end_of_section_is_not_a_table():
    text = "## apm\n\n| just one line, no separator follows |\n"
    assert cmts._first_table(text.split("## apm\n\n", 1)[1]) is None


def test_pipe_line_not_followed_by_pipe_line_is_not_a_table():
    text = "| Dependency | Why needed |\nno pipe on this line\n"
    assert cmts._first_table(text) is None


def test_pipe_line_followed_by_non_separator_pipe_line_is_not_a_table():
    # The second line looks like a table row (has pipes), but its cells
    # are not '---'-shaped, so it cannot be a header/separator pair.
    text = "| Dependency | Why needed |\n| apm | regenerates docs |\n"
    assert cmts._first_table(text) is None
