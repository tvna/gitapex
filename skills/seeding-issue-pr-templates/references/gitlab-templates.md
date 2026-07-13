# GitLab description templates reference (GitLab runs only)

Read this ONLY when Step 1 detected GitLab. Do not open the GitHub
reference in the same run.

## File layout
- Issue templates: `.gitlab/issue_templates/<Name>.md`
- MR templates:    `.gitlab/merge_request_templates/<Name>.md`

GitLab templates are plain Markdown description bodies -- there is no form
schema, so validate_templates.py checks placement and non-empty ASCII
content only.

## Conventions
- Filename (without .md) is the visible template name in the UI.
- Selecting a default MR template: set it in project settings (out of scope
  for this skill; note it as a Gate Gap if the repo wants it enforced).
- Use `/label`, `/assign` quick actions inside the body where useful.

## Minimal valid issue template
    ## Problem

    <!-- what and why -->

    ## Acceptance criteria

    - [ ] ...

## Self-check
Run: `uv run --with pyyaml python scripts/validate_templates.py <staging_dir> --platform gitlab`
against the staging directory holding the generated files, not the target
repo (which has no templates yet).
