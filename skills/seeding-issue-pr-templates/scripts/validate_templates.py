#!/usr/bin/env python3
"""Validate generated Issue/PR templates for a single platform.

Self-check for the seeding-issue-pr-templates skill: before the skill copies
generated template files into the target repo, it runs this on the staging
directory holding them (passed here as <repo_root>) to confirm the output is
structurally valid. A run targets exactly one platform (a repo remote is
GitHub or GitLab, never both), so this checks one platform per invocation.

Usage:
    uv run --with pyyaml python validate_templates.py <repo_root> \\
        [--platform {github,gitlab}]

Exit codes:
    0  all templates valid
    1  validation failures found (each printed, one per line)
    2  usage / environment error (bad dir, ambiguous platform, missing pyyaml)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:  # pyyaml is the one runtime dependency.
    sys.stderr.write(
        "error: pyyaml is required. Run via: "
        "uv run --with pyyaml python validate_templates.py <repo_root>\n"
    )
    raise SystemExit(2)


def detect_platform(repo_root: Path) -> str:
    """Return 'github' or 'gitlab' from the repo layout, else raise ValueError.

    .github/ISSUE_TEMPLATE marks GitHub; .gitlab/issue_templates marks GitLab.
    If both or neither are present, the caller must pass --platform rather
    than guess.
    """
    has_github = (repo_root / ".github" / "ISSUE_TEMPLATE").is_dir()
    has_gitlab = (repo_root / ".gitlab" / "issue_templates").is_dir()
    if has_github and not has_gitlab:
        return "github"
    if has_gitlab and not has_github:
        return "gitlab"
    raise ValueError(
        f"cannot auto-detect platform (github={has_github}, "
        f"gitlab={has_gitlab}); pass --platform"
    )


# GitHub Issue Forms body element types the skill emits, transcribed from the
# SchemaStore github-issue-forms.json schema (see references/github-issue-forms.md).
# The schema also lists 'upload'; the skill never emits it, so it is excluded.
GITHUB_BODY_TYPES = {"markdown", "input", "textarea", "dropdown", "checkboxes"}

# Schema "required" for a form file: these three top-level keys.
GITHUB_REQUIRED_TOP_KEYS = ("name", "description", "body")


def _check_ascii(path: Path, text: str, errors: list[str]) -> None:
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        errors.append(f"{path}: non-ASCII content at byte {exc.start}")


def _read_text(path: Path, errors: list[str]) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"{path}: cannot read file ({exc})")
        return None


def _load_yaml_mapping(path: Path, text: str, errors: list[str]) -> dict | None:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        errors.append(f"{path}: invalid YAML ({exc})")
        return None
    if not isinstance(data, dict):
        errors.append(f"{path}: expected a YAML mapping at top level")
        return None
    return data


def _check_pr_template_github(repo_root: Path) -> list[str]:
    errors: list[str] = []
    candidates = [
        repo_root / ".github" / "PULL_REQUEST_TEMPLATE.md",
        repo_root / "PULL_REQUEST_TEMPLATE.md",
        repo_root / "docs" / "PULL_REQUEST_TEMPLATE.md",
    ]
    found = [p for p in candidates if p.is_file()]
    multi = repo_root / ".github" / "PULL_REQUEST_TEMPLATE"
    if multi.is_dir():
        found += [p for p in sorted(multi.glob("*.md")) if p.is_file()]
    if not found:
        errors.append(f"{repo_root}: no PULL_REQUEST_TEMPLATE.md found")
    for p in found:
        text = _read_text(p, errors)
        if text is None:
            continue
        if not text.strip():
            errors.append(f"{p}: PR template is empty")
        _check_ascii(p, text, errors)
    return errors


def validate_github(repo_root: Path) -> list[str]:
    errors: list[str] = []
    tmpl_dir = repo_root / ".github" / "ISSUE_TEMPLATE"
    forms = [p for p in sorted(tmpl_dir.glob("*.yml")) if p.name != "config.yml"]
    forms += [p for p in sorted(tmpl_dir.glob("*.yaml")) if p.name != "config.yaml"]
    if not forms:
        errors.append(f"{tmpl_dir}: no issue form (.yml) files found")
    for form in forms:
        text = _read_text(form, errors)
        if text is None:
            continue
        _check_ascii(form, text, errors)
        data = _load_yaml_mapping(form, text, errors)
        if data is None:
            continue
        for key in GITHUB_REQUIRED_TOP_KEYS:
            if key not in data or data[key] in (None, ""):
                errors.append(f"{form}: missing required key '{key}'")
        body = data.get("body")
        if not isinstance(body, list) or not body:
            errors.append(f"{form}: 'body' must be a non-empty list")
            continue
        for i, element in enumerate(body):
            if not isinstance(element, dict):
                errors.append(f"{form}: body[{i}] must be a mapping")
                continue
            etype = element.get("type")
            if etype not in GITHUB_BODY_TYPES:
                errors.append(
                    f"{form}: body[{i}] invalid type {etype!r} "
                    f"(allowed: {sorted(GITHUB_BODY_TYPES)})"
                )
                continue
            attrs = element.get("attributes")
            if not isinstance(attrs, dict):
                errors.append(f"{form}: body[{i}] missing 'attributes' mapping")
                continue
            if etype == "markdown":
                if not attrs.get("value"):
                    errors.append(f"{form}: body[{i}] markdown needs attributes.value")
                continue
            if not attrs.get("label"):
                errors.append(f"{form}: body[{i}] {etype} needs attributes.label")
            if etype in ("dropdown", "checkboxes"):
                options = attrs.get("options")
                if not isinstance(options, list) or not options:
                    errors.append(
                        f"{form}: body[{i}] {etype} needs a non-empty attributes.options list"
                    )
    config = tmpl_dir / "config.yml"
    if config.is_file():
        ctext = _read_text(config, errors)
        if ctext is not None:
            _check_ascii(config, ctext, errors)
            cfg = _load_yaml_mapping(config, ctext, errors)
            if isinstance(cfg, dict):
                if "blank_issues_enabled" in cfg and not isinstance(
                    cfg["blank_issues_enabled"], bool
                ):
                    errors.append(f"{config}: 'blank_issues_enabled' must be boolean")
                links = cfg.get("contact_links")
                if links is not None and not isinstance(links, list):
                    errors.append(f"{config}: 'contact_links' must be a list")
                elif isinstance(links, list):
                    for j, link in enumerate(links):
                        if not isinstance(link, dict) or not all(
                            k in link for k in ("name", "url", "about")
                        ):
                            errors.append(
                                f"{config}: contact_links[{j}] needs name/url/about"
                            )
    errors += _check_pr_template_github(repo_root)
    return errors


def validate_gitlab(repo_root: Path) -> list[str]:
    errors: list[str] = []
    for sub in ("issue_templates", "merge_request_templates"):
        d = repo_root / ".gitlab" / sub
        if not d.is_dir():
            errors.append(f"{d}: directory missing")
            continue
        md_files = sorted(d.glob("*.md"))
        if not md_files:
            errors.append(f"{d}: no .md templates found")
        for p in md_files:
            text = _read_text(p, errors)
            if text is None:
                continue
            if not text.strip():
                errors.append(f"{p}: template is empty")
            _check_ascii(p, text, errors)
    return errors


def validate(repo_root: Path, platform: str) -> list[str]:
    if platform == "github":
        return validate_github(repo_root)
    if platform == "gitlab":
        return validate_gitlab(repo_root)
    raise ValueError(f"unknown platform: {platform!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate generated Issue/PR templates for one platform."
    )
    parser.add_argument("repo_root", type=Path)
    parser.add_argument("--platform", choices=("github", "gitlab"))
    args = parser.parse_args(argv)
    if not args.repo_root.is_dir():
        sys.stderr.write(f"error: {args.repo_root} is not a directory\n")
        return 2
    platform = args.platform
    if platform is None:
        try:
            platform = detect_platform(args.repo_root)
        except ValueError as exc:
            sys.stderr.write(f"error: {exc}\n")
            return 2
    errors = validate(args.repo_root, platform)
    if errors:
        for e in errors:
            print(e)
        print(f"FAIL: {len(errors)} problem(s) in {platform} templates")
        return 1
    print(f"OK: {platform} templates valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
