# GitHub Issue Forms reference (GitHub runs only)

Read this ONLY when Step 1 detected GitHub. Do not open the GitLab
reference in the same run.

## File layout
- Issue forms: `.github/ISSUE_TEMPLATE/<type>.yml`
- Chooser config: `.github/ISSUE_TEMPLATE/config.yml`
- PR template: `.github/PULL_REQUEST_TEMPLATE.md`
  (or `.github/PULL_REQUEST_TEMPLATE/<name>.md` for multiple)

## Form contract (enforced by validate_templates.py)
Source: SchemaStore github-issue-forms.json (draft-07), verified 2026-07-13.
- Required top-level keys: `name`, `description`, `body` (non-empty list).
- Optional: `title`, `labels`, `assignees`, `projects`, `type`.
- Body element `type` must be one of:
  `markdown`, `input`, `textarea`, `dropdown`, `checkboxes`.
  (The schema also lists `upload`; this skill does not emit it.)
- `markdown` elements require `attributes.value`.
- `input`/`textarea`/`dropdown`/`checkboxes` require `attributes.label`.
- `dropdown`/`checkboxes` additionally require a non-empty
  `attributes.options` list.

## config.yml shape
- `blank_issues_enabled`: boolean (optional).
- `contact_links`: list of `{name, url, about}` (optional).

## Minimal valid form example
    name: Bug report
    description: Report a defect
    labels: [fix]
    body:
      - type: markdown
        attributes:
          value: Thanks for filing. Fill the sections below.
      - type: textarea
        id: what-happened
        attributes:
          label: What happened
        validations:
          required: true

## Self-check
Run: `uv run --with pyyaml python scripts/validate_templates.py <staging_dir> --platform github`
against the staging directory holding the generated files, not the target
repo (which has no templates yet).
