# This repository's ADR placement convention

The significance criteria and template structure in
[../SKILL.md](../SKILL.md) and [adr-template.md](adr-template.md) are
general and portable. This file holds the one repository-specific
detail: where an approved ADR actually gets written.

## Placement

Place the approved ADR at `docs/adr/NNNN-title.md`, where `NNNN` is the
next sequential number under `docs/adr/` (four digits, zero-padded) and
`title` is a short, hyphenated slug of the ADR's own title.

## Adapting to a different repository

A calling repository that vendors this skill and uses a different ADR
location or numbering convention should replace this file's content
with its own -- the rest of the skill (Steps 1-10, 12; the significance
checklist and template in `adr-template.md`) applies unchanged.
