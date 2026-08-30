"""Deterministic shape checker for a SKILL.md and its references/ dir.

Single source of truth for the deterministic "shape" lane of the
evaluating-skill-quality skill. It decides only the mechanically
checkable rules; the nine maturity dimensions stay model-judged and are
deliberately NOT implemented here.

Read-only: reads the target skill's files only. No writes, no network,
no mutation. Effects are limited to stdout and the process exit code.
The CLI's ``--allowed-root`` guard rejects targets outside a caller-approved
root and rejects symlinks and special files (FIFOs, sockets, devices)
anywhere in the target skill before reading it. The caller must supply an
immutable/read-only snapshot; this preflight does not claim to defeat a
concurrent filesystem mutation between validation and later reads.

Checks (the canonical list -- the manual fallback is to apply these):
  - SKILL.md itself: readable as UTF-8 text (skill-md-readable). A corrupt
    (non-UTF-8) SKILL.md fails this one check and short-circuits every
    other check below -- there is nothing left to read a description,
    name, or body length out of -- rather than raising out of
    ``check_shape``.
  - description: present/non-empty, no XML tags, <= 1024 chars, and --
    only when actually written as an unquoted YAML plain scalar in the
    source (the form every SKILL.md in this repository currently uses) --
    safe against ": " (colon + whitespace) or a trailing ":" (either reads
    as the start of a new mapping key to a real YAML parser and breaks
    parsing), and against " #" or a leading "#" (reads as a comment marker
    and silently truncates the rest of the value). A description that is
    instead quoted or a block scalar (">"/"|") is exempt from this specific
    check, since those forms are already safe under a real YAML parser
    regardless of content. This checker's own frontmatter parser is
    deliberately lenient and does not reproduce either failure on its own,
    so this is a dedicated check rather than a side effect of parsing.
  - name (only if present): lowercase-hyphenated, <= 64 chars,
    no XML tags, contains no reserved word (anthropic, claude)
  - invocation control (invocation-mode-well-formed): disable-model-invocation
    and user-invocable, each only if present, carry one of Claude Code's
    documented boolean literals (true/false/yes/no/on/off/1/0, any letter
    case); and the two do not together leave the skill invocable by nobody
    (disable-model-invocation truthy AND user-invocable false, which blocks
    the model and hides the skill from the / menu at the same time).
    Neither field present passes -- the documented defaults
    (disable-model-invocation false, user-invocable true) are the normal
    state. Deliberately does NOT judge whether the declared mode matches the
    trigger the skill's own description claims; that semantic question stays
    with the model-judged Invocation-mode fit check in references/rubric.md.
  - SKILL.md body: <= 500 lines
  - metadata sidecar (metadata/gitapex.yaml, under the skill directory):
    present; has no malformed top-level lines (manifest-parsable -- a
    column-0 line that is not blank/comment/document-marker and does not
    match the top-level "key:" pattern, e.g. a stray "- invalid mapping
    entry"); apiVersion is gitapex.io/v1alpha1 and kind is SkillMetadata;
    metadata.name equals the skill directory name; spec.portability is one
    of Portable/Repository-scoped/Mixed; spec.capabilityAssumption is one
    of Broad/Frontier/Adaptive; spec.references, if present, is a non-empty
    list of non-empty scalar strings, each item consistently indented with
    its own list, not an unquoted YAML mapping key such as "path: foo", and
    not an unquoted null/boolean/numeric scalar such as "null"/"true"/"123"
    (a real YAML parser resolves such a plain scalar to that
    type, not a string, so it must fail rather than be silently accepted
    as one; a quoted item, e.g. "\"true\"", is unaffected -- it is a
    deliberate string regardless of its contents)
    (references-well-formed); spec.skillDependencies, if present, is a
    mapping -- itself never real YAML null (a block header with no
    requires/relatedTo key at all under it fails as the wrong type rather
    than being read as "declared, nothing inside": see the
    absent-vs-null-vs-empty paragraph below) -- with only the keys
    requires/relatedTo, each -- if present -- a
    list of non-empty scalar strings with the same per-item shape rules as
    spec.references (including the same null/boolean/numeric-scalar
    rejection), except an empty list is valid here, unlike
    spec.references (skill-dependencies-well-formed); every name listed in
    either list resolves to an existing sibling skill directory
    (skill-dependencies-resolve); and a non-empty
    spec.skillDependencies.requires is incompatible with
    spec.portability: Portable (requires-portability-compatible).
    spec.lifecycle, if present, is a mapping -- likewise never real YAML
    null, per the same rule -- with only the keys
    experimental/deprecated/stable/renamedFrom. experimental
    (reason/trackingIssue required, since optional), deprecated
    (reason/replacement required, since/removeAfter optional), and stable
    (since required, compatibilityGuarantee optional) are each -- if
    present -- a mapping of their own recognized scalar fields (each,
    like spec.lifecycle itself, failing as the wrong type rather than
    passing as an empty mapping when its own header is left blank with
    no field at all under it);
    renamedFrom, if present, is a non-empty scalar string (not a
    sub-block). since/removeAfter, if present, must be real calendar
    dates in strict YYYY-MM-DD shape; trackingIssue, if present, an
    anchored #123 or owner/repo#123 reference; compatibilityGuarantee, if
    present, one of Alpha/Beta/GA (lifecycle-well-formed); and, when
    deprecated.replacement is a non-empty string, it resolves to an
    existing sibling skill directory, the same dangling-reference gate
    spec.skillDependencies uses (lifecycle-deprecated-replacement-resolves).
    experimental and deprecated are independent and optional -- neither
    implies nor excludes the other -- but experimental and stable are
    mutually exclusive: a non-empty spec.lifecycle.experimental cannot
    coexist with a non-empty spec.lifecycle.stable
    (experimental-stable-compatible). renamedFrom is deliberately NOT
    resolved against sibling directories, unlike deprecated.replacement
    -- it names the skill's own former, now-nonexistent directory name
    (a git mv target), backward-pointing on the surviving skill rather
    than a forward-pointing tombstone on a directory that no longer
    exists. No skill's runtime procedure may read or branch on any part
    of spec.lifecycle (the sidecar's behavior-neutrality invariant).
    spec.executionRequirements, if present, is a mapping with only the
    tools, packages, and network keys so far (further categories --
    filesystem/mcp/credentials/browser/externalServices/context -- are
    deferred; until they land, any key other than tools/packages/network
    here is an unknown key, not reserved space);
    tools, if present, is itself a mapping -- like spec.executionRequirements
    itself, never real YAML null -- with only the keys
    read/write/shell, each -- if present -- a list of non-empty scalar
    strings (free-form capability tags; this issue does not define a
    fixed vocabulary), with the same per-item shape rules
    (mapping-like-item, indent-consistency, and null/boolean/numeric-scalar
    detection) spec.skillDependencies.requires/relatedTo items already use
    (execution-requirements-well-formed). An absent executionRequirements
    block, an absent tools block, or an absent read/write/shell key each
    mean "not yet declared"; an explicit empty list (e.g. read: [])
    means "declared, zero tools of that kind needed" -- a deliberate
    statement, not the same as absence.
    network (issue #845), if present, is itself a mapping -- never real
    YAML null, same rule -- with only the keys mode/domains: mode is a
    scalar enum (disabled/allowlist/unrestricted); domains is a list of
    non-empty scalar strings, with the same per-item shape rules as
    tools' own read/write/shell, required non-empty when mode is
    allowlist and required empty-or-absent otherwise. This is the one
    sidecar sub-block mixing a scalar field with a list field in the same
    block -- see EXEC_REQ_NETWORK_SUBKEYS' own comment above for why the
    parser treats that as no different from tools' all-list shape.
    packages, if present, is itself a mapping -- never real YAML null,
    same rule -- but unlike tools/network its own subkeys are not a fixed
    tuple: each is a free-form ecosystem identifier (e.g. "pip", "npm")
    matching EXEC_REQ_PACKAGES_KEY_RE (skill-metadata.schema.json's own
    executionRequirementsPackages.propertyNames pattern), so unknown-
    subkey detection here is a regex mismatch rather than a
    tuple-membership check. Each matching ecosystem key's own value is,
    like tools' read/write/shell, a list of non-empty scalar strings with
    the same per-item shape rules (execution-requirements-well-formed). An
    absent executionRequirements block, an absent packages block, or an
    absent specific-ecosystem key each mean "not yet declared"; an
    explicit empty list (e.g. pip: []) means "declared, zero packages
    needed from that ecosystem" -- a deliberate statement, not the same as
    absence. Whether a declared package is one gitapex permits at all is
    not checked here: that allowlist-membership question is enforced
    entirely outside this portable script, by a repository-owned CI gate
    (.github/scripts/gitapex_gate_dependency_allowlist.py).

    Three-way absent/null/empty-mapping distinction, shared by every gated *mapping*-valued block above
    (spec.skillDependencies, spec.lifecycle and each of its
    experimental/deprecated/stable sub-blocks, spec.executionRequirements,
    spec.executionRequirements.tools, and
    spec.executionRequirements.packages): the key never appearing at all
    means "not declared" (optional, passes); the key appearing with a
    blank value and no child key ever following at the next indent level
    is real YAML null -- a real YAML parser never reads a bare block
    header followed by a dedent as an empty mapping, so this checker
    fails it as the wrong type rather than reading it as "declared,
    nothing inside"; and the key appearing with at least one real child key
    (however that child's own value turns out) is a genuine, non-null
    mapping, checked normally -- there is no way to spell "declared, but
    deliberately an empty mapping" in this parser's supported block-style
    subset (it has no inline flow-mapping "{}" support anywhere), so that
    third state does not exist for these fields the way an explicit empty
    *list* (read: []) does for list-valued fields. This distinction does
    NOT extend to list-valued keys (spec.references;
    spec.skillDependencies.requires/relatedTo;
    spec.executionRequirements.tools.read/write/shell;
    spec.executionRequirements.packages.<ecosystem>) -- a blank list
    header is still read as an empty list, unchanged, matching each
    field's own already-established "explicit empty list is a deliberate
    statement" semantics documented above. Other
    ungated sidecar fields (e.g. spec.evalStatus) are parsed into the spec
    map by _parse_manifest only if written as a single inline scalar; a
    nested/block-shaped field (e.g. evalStatus's documented baseline:/lift:
    children) is dropped entirely, not gated/checked here or anywhere --
    only nested maps and list items under them are skipped by the parser,
    and indented lines are never flagged as malformed regardless of shape.
    spec.externalCitations (issue #1055), if present, is a non-empty list
    of item mappings, each a flat path/role pair (path rooted at evals/ or
    docs/; role one of input-source/output-destination) with no
    unrecognized key (external-citations-well-formed); every declared path
    must literally
    (exact-substring) appear somewhere in SKILL.md or references/*.md,
    catching a stale declaration whose citation no longer exists
    (external-citations-resolve). This is an opt-in supplement to
    GENERIC_ROLE_HEDGE_PHRASES, not a replacement -- see the Portable
    inline-code repo-path citation entry below for how a declared entry
    rescues an inline-code citation.
  - references/ files: exactly one level deep, any extension (a bundled
    JSON schema is as legitimate a dependency file as a Markdown doc).
  - any references/*.md file over 100 lines: contains a table of contents
    (a Markdown heading matching "Table of contents" or "Contents",
    case-insensitive). Junk files (dotfiles, __pycache__, non-UTF-8) under
    references/ are ignored, not flagged; a non-Markdown reference file
    (any extension other than .md) is exempt from this check and the two
    that follow (links-inside-skill, anchor-targets-resolve) -- those are
    Markdown-navigation concepts that do not apply to it -- but still
    counts toward references-flat above.
  - SKILL.md body and every references/*.md file (links-inside-skill):
    every Markdown link target -- inline ([text](path))
    or reference-style ([text][label] resolved via a [label]: path
    definition) -- that is not an absolute URL/scheme (http(s):,
    mailto:, etc.) or a bare in-page fragment (#section) must resolve
    inside the skill's own directory -- a relative link that escapes it
    (e.g. "../../docs/x.md") fails. This
    gives the skill's own "Portable" self-declaration (whose definition
    already requires every instruction to resolve inside the skill's own
    folder) a deterministic backstop. Runs on SKILL.md (bare check name)
    and independently on every references/*.md file (``links-inside-
    skill:{ref.name}``, mirroring anchor-targets-resolve's own per-file
    naming below). A relative target is resolved against the file that
    CONTAINS it (SKILL.md's own directory, or a references/*.md file's
    own references/ directory) -- real relative-link semantics, not
    resolved against the skill root unconditionally, since a
    references/*.md file does not itself sit at the skill root.
  - Markdown anchor-fragment resolution (anchor-targets-resolve): every Markdown link's ``#fragment`` --
    inline or reference-style, same as the check above -- must match a
    real heading anchor GitHub's own renderer would generate for the
    link's target file (the link's own file, when no path is given, or
    the resolved path otherwise). Runs on SKILL.md (bare check name) and
    independently on every references/*.md file (``anchor-targets-
    resolve:{ref.name}``, mirroring toc:{ref.name}'s per-file naming and
    loop, but unconditionally -- not gated on the 100-line TOC threshold,
    since an anchor mismatch is not correlated with file length). Reuses
    this check's own link-gathering rules verbatim (same absolute-URL/
    scheme skip, same reference-style-definition support), plus stripping
    an inline link's optional CommonMark title before reading its
    fragment. A link whose path resolves outside the skill directory is
    silently skipped here -- that is links-inside-skill's own separate
    failure, not duplicated by this check. A target file that cannot be
    read (missing, a directory, binary, non-UTF-8), by contrast, IS
    flagged as broken: there is no real heading it could possibly expose,
    so a dangling `[ghost](references/missing.md#x)`-shaped link is
    exactly the defect class this check exists to catch, not a case to
    tolerate the way the references/ TOC check above tolerates junk files
    it merely iterates past. GitHub's real heading-slug algorithm:
    recognizes both ATX headings (``#`` through ``######``, 0-3 leading
    spaces, an optional trailing closing ``#`` sequence stripped before
    slugging) and Setext headings (a text line immediately underlined by
    a run of ``=`` or ``-``); lowercases the heading text, strips a fixed
    punctuation denylist (ASCII punctuation plus two Unicode punctuation
    blocks) while preserving every Unicode letter/digit plus underscore/
    hyphen/space -- not an ASCII-only allowlist, since GitHub's own
    slugger preserves accented and non-Latin letters -- then each
    surviving space becomes its own literal ``-`` (adjacent stripped
    punctuation is not collapsed first, so e.g. "Trust & authority" ->
    "trust--authority", a real in-repo example). A slug that repeats an
    earlier heading's slug earns the lowest ``-1``, ``-2``, ... suffix not
    already claimed by some OTHER heading's own literal slug (not simply
    a per-base occurrence count, which can under-suffix and collide when
    a document already contains a heading literally named e.g. "Foo-1"),
    counted across every heading in the target document in order -- not
    only the ones actually linked. A heading-shaped line inside a fenced
    code block is never treated as a real heading (the same fence-
    blanking already used for the citation checks below, which also
    normalizes CRLF/CR line endings to bare ``\n`` first).
  - Cross-skill file+heading citation resolution (cross-skill-citation-
    resolves): a prose citation of the shape "`SKILL-NAME`'s
    `references/FILE.md` HEADING TEXT section" (skill name and file path
    each in their own inline-code span, heading text as bare prose ending
    at the literal word "section") in SKILL.md or references/*.md must
    resolve -- the named sibling skill directory exists, the named file
    exists inside that sibling's own references/ directory, and a
    heading matching the cited text exists in that file (reusing the
    same GitHub heading-slug logic anchor-targets-resolve implements
    above). A citation in this shape can never be a real Markdown link
    that anchor-targets-resolve or links-inside-skill would otherwise
    catch, since a cross-skill target cannot legally resolve inside the
    CITING skill's own directory -- this is the dedicated backstop for
    exactly that gap. Runs unconditionally, at every portability level.
  - Mechanism-fit subsection citation completeness (mechanism-fit-
    subsections-cite-sources): every "### " subsection nested
    under a "## Mechanism fit" heading, in SKILL.md or references/*.md,
    must carry either a "[label]"-style citation bracket or the literal
    phrase "this repository's own reasoned extension" -- mechanizing the
    completeness rule such a section's own intro prose already states
    ("the primary source and the reasoning behind each check").
    Generic over any document with such a
    heading, not hardcoded to references/rubric.md's filename; a
    document with no "## Mechanism fit" heading at all trivially passes
    (zero subsections to check). Runs unconditionally, at every
    portability level.
  - Bare issue/PR-number citation (no-bare-issue-citation):
    no bare-prose GitHub issue/PR-number citation (#149 or owner/repo#149)
    in SKILL.md or references/*.md body text. Runs unconditionally on
    every skill regardless of declared portability level -- Portable,
    Mixed, and Repository-scoped alike, unlike the two repo-path checks
    below. A bare #N auto-links relative to whichever repository
    currently hosts the file and silently resolves to the wrong issue
    once the skill is vendored or simply read out of context. This scan
    also covers the metadata sidecar's own spec.references entries and
    lifecycle.experimental/deprecated.reason text -- a bare number there
    loses its meaning once the sidecar travels with its skill directory
    to another repository. A full ``https://github.com/OWNER/REPO/issues/149``-style
    URL contains no bare ``#N`` and so is never flagged by this scan --
    that is the only sanctioned way left to cite an issue from the
    sidecar. Other repo-specific content -- sibling-skill names,
    repo-specific paths/conventions -- remains legitimate
    Mixed/Repository-scoped territory; this rule is narrowly about
    issue/PR numbers. Matches inside inline code (`#149`), fenced code
    blocks, absolute URLs, and Markdown links are excluded from THIS
    bare-prose scan -- those are the established ways this repo's skills
    quote such a token illustratively without it resolving live. Inline
    code is not unconditionally safe, though: for Portable-declared
    content specifically, the separate check below re-inspects
    exactly the inline-code spans this scan skips.
  - Portable self-citation, repo-path half (only when the skill declares
    "Portable", not "Mixed" or "Repository-scoped" -- unlike the
    issue-number scan above, these two checks stay level-gated:
    operational dependence on a repo-specific *path* is the legitimate,
    undisputed core of what Mixed/Repository-scoped is for, and there is
    no URL-equivalent escape hatch for a filesystem path the way there is
    for an issue number). The declaration is read sidecar-primary with a
    body-marker fallback: the sidecar's spec.portability decides whenever
    it is present and usable -- the form every skill in this repository
    uses -- a skill with no sidecar at all (typically one vendored in
    from another repository) falls back to the near-top
    "**Portability: <level>.**" body marker, and a skill whose sidecar
    exists but is unreadable or carries no recognised spec.portability
    runs the scan unconditionally (a false negative in a gate is worse
    than a false positive, and such a skill is already failing
    portability-declared) -- so no Portable-declared skill state ever
    silently skips it. The scan itself: no bare-prose origin-repository
    path citation (evals/... or docs/...) in SKILL.md or references/*.md
    body text, and no bare-prose citation of the calling repository's own
    instruction-file chapter/section ("CLAUDE.md ch.2", "CLAUDE.md
    chapter 3", and "CLAUDE.md section 4" are all covered, matching the
    three phrasings already in real use elsewhere in this repository). A
    repo-relative path breaks the same way a bare issue number does once
    the skill is vendored, and a CLAUDE.md chapter/section citation
    breaks the same way once vendored into a repository with a
    differently-numbered or absent instruction file. Matches inside
    inline code (`evals/...`), fenced code blocks, absolute URLs, and
    Markdown links are excluded -- those are the established ways this
    repo's Portable skills quote such a token illustratively without it
    resolving live. This is the deterministic backstop for the rubric's
    dimension-6 Portable-skill rule; the semantic judgment of whether a
    citation is illustrative context vs. the skill's own bookkeeping
    stays with that model-judged dimension.
  - Portable inline-code repo-path citation without a generic-role hedge
    (issue #1051, narrowing the blind spot the exemption above leaves
    open): treating every inline-code path citation as automatically
    illustrative was itself the original gap -- an inline-code
    `evals/...`/`docs/...` citation reads exactly as authoritative as a
    bare-prose one to a reader who has no way to tell "illustrative
    example" from "this repository's own real file" from the backticks
    alone. This check re-inspects exactly the inline-code spans the
    bare-prose scan above deliberately skips, and fails a match that has
    no phrase from `GENERIC_ROLE_HEDGE_PHRASES` (`the calling repository` /
    `the target repository` -- the narrow, generic-illustrative-placeholder
    half of `HEDGE_PHRASES` only) in its own sentence or the sentence
    immediately before it. An earlier revision of this check accepted the
    *full* `HEDGE_PHRASES` list, including `this repository` / `gitapex`
    (e.g. rubric.md's "This repository has also used ..." and
    scorer-gated-skill-edits/SKILL.md's "This repository has also
    recorded ..."), asymmetrically for `evals/...` while unconditionally
    banning `docs/...` -- a corpus incident (rubric.md's own Execution
    requirements section) showed that this half of the hedge vocabulary
    *discloses* a real, known dependency without *removing* it: the cited
    file still does not travel with a vendored copy either way, so no
    phrase should rescue it. `the calling repository` / `the target
    repository` are categorically different: they mark a citation as a
    generic illustrative path name for *whatever* repository the skill
    lands in, never a citation to *this* origin repository's own real
    file (e.g. establishing-ubiquitous-language's "record resolved terms
    in the calling repository's own glossary doc (e.g. `docs/glossary.md`)"
    -- a placeholder, not this repository's own file), so there is nothing
    to disclose-without-removing in the first place; both `evals/` and
    `docs/` get identical treatment under this narrower list either way.
    Fenced code blocks stay exempt unconditionally, as the module
    docstring above already covers -- this check never runs on blocks,
    only on inline code, since a worked example's illustrative fenced
    output is a different, already-settled case that this check does not
    reopen. A second, independent rescue (issue #1055): a citation whose
    own matched text exactly equals a well-formed spec.externalCitations
    declared path also passes, regardless of any nearby hedge phrase --
    per-citation, not clause-wide, since a declaration is a fact about one
    specific path. This supplements GENERIC_ROLE_HEDGE_PHRASES; it does not
    replace it, and it is deliberately NOT applied to the bare-prose
    (portable-no-repo-path-citation) or issue-number check.
  - Portable inline-code issue/PR-number citation without a hedge (the
    same blind spot as the repo-path check above, but for issue numbers
    instead of paths): the bare-issue-citation scan's inline-code exclusion
    (see its own entry above) let a fictional worked-example citation like
    `` `#42` `` or `` `#142` `` sit in Portable content indefinitely, since
    dimension 6's rubric bans an issue/PR-number citation from Portable
    content even fully hedged inside inline code. This check re-inspects
    exactly the inline-code spans the bare-prose scan above deliberately
    skips, and fails one with no approved hedge phrase
    (ISSUE_CITATION_HEDGE_PHRASES -- see that constant's own comment for the
    full rationale, including why its phrase list is separate from and
    narrower than HEDGE_PHRASES) nearby. Portable-gated, alongside the two
    repo-path checks above, unlike the unconditional bare-prose scan.
  - Portable unhedged sibling-skill fact-claim (portable-no-unhedged-
    skill-fact-claim): a possessive citation of a named
    sibling skill (e.g. `` `scorer-gated-skill-edits`' own
    fixture-authoring guidance already names X for a pure substring
    scorer ``) inside
    Portable-declared content, asserted with "already" in the same
    clause, naming a real sibling skill directory, with no approved hedge
    phrase (HEDGE_PHRASES, the same list the repo-path check above uses)
    nearby. Deliberately narrow (see PORTABLE_SKILL_FACT_CLAIM_RE's own
    comment): a corpus-wide validation scan found that flagging every
    resolving backtick-quoted skill-name citation, without the possessive
    shape and "already" requirements, fires on eleven of this
    repository's own already-shipped skills -- the possessive form alone
    is this repository's single most common, entirely benign way to cite
    a sibling skill's content.
  - Illustrative model identifier (no-illustrative-model-identifier,
    docs/skill-authoring-standards.md rule 1): no real, current Claude model
    identifier (ILLUSTRATIVE_MODEL_ID_RE: "claude-" plus a known
    model-family word -- opus/sonnet/haiku/fable/instant -- plus a
    version-like digit, e.g. "claude-sonnet-5") anywhere in SKILL.md or
    references/*.md body text, including inside a fenced code block or
    inline code span -- unlike every citation check above, this one does
    NOT exempt code, since the rule it enforces is about the identifier
    ever appearing as illustrative content at all, not about it resolving
    live. A placeholder such as "claude-example-model" never matches (no
    recognized family word immediately follows "claude-"), so it stays the
    sanctioned way to write a flagged "bad example" needing a model name.
    One exemption: a match that falls entirely inside an
    ANTHROPIC_DOC_CITATION_RE span -- a real citation URL to Anthropic's own
    docs (platform.claude.com, code.claude.com, claude.com), in this
    repository's own autolink/inline-link/reference-definition citation
    forms -- is not an offender; that is a primary-source citation, not
    illustrative content.
  - Raw angle-bracket placeholder (no-raw-angle-bracket-placeholder,
    docs/skill-authoring-standards.md rule 4): no "<name>"-shaped
    placeholder in SKILL.md or references/*.md bare prose (fenced code
    blocks, inline code spans, absolute URLs, and Markdown links all
    excluded, same as the citation checks above -- placeholder text inside
    any of those renders literally and is safe). A placeholder with a
    matching "</name>" closing tag elsewhere in the same bare prose is
    exempt: that shape is a deliberate open/close tag pair (e.g. this
    repository's own untrusted-input-triage worked example, which quotes a
    fake "<system-reminder>...</system-reminder>" payload as
    adversarial-input content, not a fill-in-the-blank placeholder), not the
    unclosed fill-in-the-blank shape this check exists to catch.
  - Out-of-skill bare-prose scripts/ citation (portable-no-out-of-skill-
    scripts-citation, issue #192, Refs #26 repair 3/#36 repair 3/#20 item
    d; only when the skill declares "Portable", same gate as the two
    repo-path checks above): a bare-prose "scripts/PATH" mention in
    SKILL.md or references/*.md whose path does not resolve to a real file
    under the skill's own directory. Unlike the evals/docs repo-path
    citation above, a "scripts/..." mention routinely DOES legitimately
    resolve inside the citing skill's own directory (every skill's
    SKILL.md names its own bundled script this way), so this is not folded
    into REPO_PATH_CITATION_RE's unconditional-flag-or-hedge treatment --
    it is flagged only when the path does not exist under the skill's own
    directory (a stale root-level or cross-skill reference). This is the
    bare-prose counterpart of links-inside-skill's identical "must resolve
    inside the skill's own directory" rule for a real Markdown link; a
    Markdown-link-shaped "scripts/..." target is already covered there, so
    only the bare-prose form needed a dedicated check.
  - Step-number execution-location contradiction (no-step-location-
    contradiction, issue #192, Refs #93 repair 1): fails when the same
    "step N"/"steps N-M" reference is asserted, in two different sentences
    of the same SKILL.md or references/*.md file, to execute in two
    different locations (a closed vocabulary -- "stays in", "runs
    inside"/"runs in", "executes inside"/"executes in" -- grounded in the
    exact wording of the historical incident this check mechanizes), with
    neither sentence explicitly ceding authority to the other (a nearby
    "authoritative" substring, this repository's own established way of
    marking one location's statement as the authoritative one). Runs
    unconditionally, at every portability level -- a same-file internal
    contradiction about where a step executes is a defect regardless of
    declared portability. Deliberately narrow: this repository's own real
    location-shaped phrasing is otherwise sparse, so a broader vocabulary
    would have no evidence base and a much larger false-positive surface.
  - No voodoo constant (no-voodoo-constant, issue #1045's Acceptance
    Criteria Map item A): every module-level ALL-CAPS-named target
    (``^[A-Z][A-Z0-9_]*$``, the conventional constant-naming heuristic
    that keeps this check from flagging an ordinary variable or a
    regex-compiled pattern like ``NAME_RE = re.compile(...)``, whose RHS
    is a Call, not a literal) of a plain assignment or an annotated
    assignment with a value (``TIMEOUT: int = 30``; a bare annotation with
    no value, ``TIMEOUT: int``, has nothing to scan) in every non-test
    ``*.py`` file anywhere under the skill's own ``scripts/`` directory --
    recursively, so a skill that ships its scripts as a package
    (``scripts/<name>/*.py``) has that subpackage's own constants scanned
    too rather than silently exempted, matching the same recursive scope
    this skill's own sibling ``gitapex_scan_execution_requirements_drift.py``
    already uses for the same question
    (``test_*.py`` files are excluded, by basename at any depth -- test
    fixture literals are not
    "configuration" and would be enormous false-positive noise, e.g. this
    very checker's own ``test_gitapex_check_skill_shape.py``; dotfiles and
    ``__pycache__`` bytecode caches are likewise skipped as junk) whose
    right-hand side is a "simple literal" (a bare ``ast.Constant``; an
    ``ast.Tuple``/``ast.List``/``ast.Set`` of nothing but ``ast.Constant``
    elements; or an ``ast.Dict`` whose every key and value is itself an
    ``ast.Constant``) must carry an adjacent justifying comment: either a
    real ``COMMENT`` token, per Python's own ``tokenize`` module (not a
    naive ``"#" in line`` scan, which false-passes on a ``#`` character
    living inside a string-literal RHS itself, e.g.
    ``PREFIX = "issue #"``, which carries no real comment), on any
    physical line the statement itself spans -- covers both a trailing
    comment on a single-line assignment and one on a multi-line container
    literal's own opening line (``NAME = (  # explanation`` ... ``)``) --
    or a comment-only line immediately above the statement's first line
    (blank lines skipped when walking upward). A chained assignment
    (``FOO = bar = 1``) is evaluated per-target, not gated on every target
    matching the ALL-CAPS heuristic together.
    Deliberately only checks module-level statements (``ast.parse``'s
    top-level ``tree.body``, never recursed into a function or class
    body) -- a constant assigned inside a function is a local, not a
    "voodoo constant" in the configuration sense this check targets.
    Escape hatch, by design: ANY adjacent comment satisfies this check,
    however short -- it flags only a total absence of justification, not
    comment quality (comment quality stays the model-judged dimension-7
    review's job, not this mechanical check's), matching issue #1045's
    own stated residual-risk note that a well-known constant needs a
    one-line-comment escape hatch. A script with a syntax error
    contributes zero offenders for this check (parsed independently per
    file; a malformed script is a different problem this repository's
    other gates already catch). A script that cannot even be read as
    UTF-8 text is reported as an offender instead of silently skipped --
    unlike a syntax error, nothing else is guaranteed to notice an
    unreadable bundled script, so skipping it here would pass vacuously.
    An offender is reported as its path relative to the skill directory
    (``scripts/helperpkg/config.py``, not a bare ``scripts/config.py``),
    so a same-named module in two different subdirectories still points at
    the real file.
    Silently passes with "not declared (optional)" evidence, the same
    absent-optional-content convention used throughout this docstring,
    when the skill has no ``scripts/`` directory at all or it contains no
    qualifying non-test ``.py`` file.
  - Script execution intent stated (script-execution-intent-stated, issue
    #1045's Acceptance Criteria Map item A): every file anywhere under
    the skill's own ``scripts/`` directory (recursively, same scope and
    same junk filter as no-voodoo-constant above; any extension, not just
    ``.py`` -- a referenced ``.sh`` script counts too) that is mentioned
    anywhere in SKILL.md or references/* (via ``_citation_sources``, the
    same source set every prose citation check above scans) as an
    inline-code span of its own exact filename (`` `filename` ``) must
    have at least one such mention whose own enclosing paragraph
    (``_markdown_paragraphs`` -- blank-line-delimited, with internal
    hard-wrapped newlines joined to a single space, so a citation and its
    qualifying phrase still match when a line-wrap falls between them)
    also carries explicit execution-intent phrasing: ``Run `filename` ``
    or ``See `filename` ... for ...`` (case-insensitive -- a natural,
    grammatically lowercase mid-sentence "run"/"see" counts the same as a
    sentence-initial capitalized one; case carries no semantic
    distinction for this check). A script never mentioned this way anywhere is
    silently skipped, not flagged -- an unlinked/unreferenced script is a
    separate dimension-5 progressive-disclosure concern, out of scope for
    this check, per its own "referenced from SKILL.md/references/"
    applicability. Silently passes with "not declared (optional)"
    evidence when the skill has no ``scripts/`` directory at all or it is
    empty.

Usage:
  python3 gitapex_check_skill_shape.py <skill-dir-or-SKILL.md>

Exit code: 0 if every check passes, 1 if any check fails, 2 on bad usage or
when no readable SKILL.md is found.
"""

from __future__ import annotations

import argparse
import os.path
import sys
from pathlib import Path

from shape_checks.bundled_scripts import (
    _comment_line_numbers,
    _no_voodoo_constant_checks,
    _out_of_skill_scripts_checks,
    _script_execution_intent_checks,
)
from shape_checks.citation_checks import (
    _cross_skill_citation_checks,
    _dimension_quote_exemption_checks,
    _illustrative_model_id_checks,
    _issue_citation_checks,
    _mechanism_fit_checks,
    _portable_demonstrative_repository_citation_checks,
    _portable_path_citation_checks,
    _portable_skill_citation_checks,
    _raw_placeholder_checks,
    _step_location_checks,
    _untrusted_authority_crossover_checks,
)
from shape_checks.constants import (
    _INLINE_CITATION_CHECK_SPECS,
    BODY_MAX_LINES,
    CAPABILITY_ASSUMPTIONS,
    DESCRIPTION_MAX_CHARS,
    EXEC_REQ_NETWORK_SUBKEYS,
    EXEC_REQ_PACKAGES_KEY_RE,
    EXEC_REQ_TOOLS_SUBKEYS,
    EXPECTED_API_VERSION,
    EXPECTED_KIND,
    LIFECYCLE_ISSUE_REF_RE,
    LIFECYCLE_SCALAR_KEYS,
    LIFECYCLE_SUBKEYS,
    NAME_MAX_CHARS,
    PORTABILITY_LEVELS,
    REFERENCES_ENTRY_MAX_CHARS,
    REFERENCES_ITEM_SUBKEYS,
    SIDECAR_RELATIVE_PATH,
    SKILL_DEP_LIST_ITEM_RE,
    SKILL_DEPENDENCY_SUBKEYS,
    TOC_MIN_LINES,
    CheckResult,
)
from shape_checks.execution_requirements import _execution_requirements_checks
from shape_checks.field_checks import (
    _invocation_mode_check,
    _owning_skill_dir,
    _references_grammar_check,
    _resolve_skill_md,
    _validate_read_scope,
)
from shape_checks.frontmatter import _parse_frontmatter, _unquote
from shape_checks.lifecycle import _lifecycle_checks, _valid_tracking_issue
from shape_checks.links_portability import (
    SidecarPortability,
    _body_after_frontmatter,
    _broken_anchor_targets,
    _heading_slugs,
    _is_portable,
    _out_of_skill_link_targets,
    _resolves_to_sibling_skill,
    _stale_related_skill_references,
)
from shape_checks.manifest import _is_non_string_plain_scalar, _parse_manifest, spec_of
from shape_checks.orchestrator import (
    _body_length_result,
    _dependency_policy_declared_result,
    _description_field_checks,
    _external_citations_resolve_result,
    _external_citations_well_formed_result,
    _lifecycle_reason_citation_sources,
    _name_field_checks,
    _references_citation_source,
    _references_dir_checks,
    _references_well_formed_result,
    _sidecar_unreadable_results,
    _skill_md_read_result,
)
from shape_checks.skill_dependencies import _skill_dependency_checks

# Names this hub imports only to re-export -- never referenced by
# check_shape()/format_report()/main() below, only by
# skills/evaluating-skill-quality/scripts/test_gitapex_check_skill_shape.py,
# tests/test_gitapex_check_skill_shape_properties.py,
# tests/test_gitapex_skill_metadata_sidecar.py, and
# tests/test_gitapex_repository_skill_shape.py's own historical
# `import gitapex_check_skill_shape as css; css.<name>` access, predating the
# shape_checks/ package split (issue #1330 ACM row 1). Listed explicitly
# (rather than a blanket `from shape_checks.x import *`) so ruff's F401 marks
# each as an intentional public re-export instead of an unused import.
#
# BODY_MAX_LINES/DESCRIPTION_MAX_CHARS/NAME_MAX_CHARS/
# REFERENCES_ENTRY_MAX_CHARS/TOC_MIN_LINES joined this list in issue #1330's
# own row-2 decomposition: check_shape() itself no longer reads them
# directly (each moved into its own shape_checks/orchestrator.py helper),
# but the same four test files still reach in for them by name, so they
# need the same explicit re-export treatment the constants above already
# have -- otherwise ruff's F401 (correctly, from its own static-analysis
# view) reports them as unused and strips them, breaking that attribute
# access.
__all__ = [
    "BODY_MAX_LINES",
    "DESCRIPTION_MAX_CHARS",
    "EXEC_REQ_NETWORK_SUBKEYS",
    "EXEC_REQ_PACKAGES_KEY_RE",
    "EXEC_REQ_TOOLS_SUBKEYS",
    "LIFECYCLE_ISSUE_REF_RE",
    "LIFECYCLE_SCALAR_KEYS",
    "LIFECYCLE_SUBKEYS",
    "NAME_MAX_CHARS",
    "REFERENCES_ENTRY_MAX_CHARS",
    "REFERENCES_ITEM_SUBKEYS",
    "SKILL_DEPENDENCY_SUBKEYS",
    "SKILL_DEP_LIST_ITEM_RE",
    "TOC_MIN_LINES",
    "_INLINE_CITATION_CHECK_SPECS",
    "_comment_line_numbers",
    "_is_non_string_plain_scalar",
    "_resolves_to_sibling_skill",
    "_unquote",
    "_valid_tracking_issue",
    "spec_of",
]


def check_shape(target: Path) -> list[CheckResult]:
    skill_md = _resolve_skill_md(target)
    skill_dir = skill_md.parent
    results: list[CheckResult] = []
    # Populated below, only when the sidecar parses with spec.references
    # and/or spec.lifecycle.experimental/deprecated.reason present -- fed
    # into _issue_citation_checks so the bare-issue-citation ban covers the
    # sidecar's own free text too, not just SKILL.md/
    # references/*.md.
    sidecar_citation_sources: list[tuple[str, str]] = []

    # A corrupt (non-UTF-8) SKILL.md must not raise out of check_shape --
    # the same contract already established for the sidecar read below
    # (see its own try/except a few lines down). Unlike
    # the sidecar, SKILL.md's text feeds nearly every other check in this
    # function (frontmatter, body-length, and every citation/model-id/
    # placeholder/link scan further down), so there is no bounded,
    # independent subset of checks left to run once it can't be read --
    # report the one failure and stop, rather than a raised exception
    # that would abort any direct caller (not just main(), which already
    # guards its own check_shape() call) with a bare traceback.
    text, skill_md_result = _skill_md_read_result(skill_md)
    if text is None:
        return [skill_md_result]
    results.append(skill_md_result)
    frontmatter = _parse_frontmatter(text)
    fields = frontmatter.fields

    results.extend(_description_field_checks(fields, frontmatter))
    results.extend(_name_field_checks(fields))
    results.append(_invocation_mode_check(fields))
    results.append(_body_length_result(text))

    sidecar = skill_dir / SIDECAR_RELATIVE_PATH
    # Every well-formed spec.externalCitations item (path/role), populated
    # below only when the sidecar parses cleanly -- fed into
    # external-citations-resolve and the inline-path-citation rescue
    # further down, both of which run after ``body`` exists, unlike
    # every other sidecar-derived check above (issue #1055). Stays []
    # whenever the sidecar is absent, unreadable, or the field itself is
    # malformed/empty, matching every other declared-list default here.
    external_citations_declared: list[dict[str, object]] = []
    # True only when the sidecar exists but could not be read/parsed at
    # all (manifest is None below) -- the one case where
    # external-citations-well-formed/-resolve were already emitted as
    # FAILed above, so the unconditional block near the end of this
    # function must not append a second, silently-overwriting result.
    # Deliberately NOT sidecar_portability.state != "unusable": that state
    # also covers a *parsed* manifest with an invalid spec.portability
    # (see below), where external-citations-well-formed already ran
    # normally and external-citations-resolve must still run too
    # (code-review finding, issue #1055 follow-up: the broader state-based
    # guard silently skipped external-citations-resolve for that second,
    # unrelated case).
    external_citations_sidecar_unreadable = False
    # Cached once, not re-derived at the external-citations-resolve guard
    # below: a second sidecar.is_file() call there could observe a
    # different result if the sidecar were created or removed between the
    # two checks, silently desyncing metadata-file-present from
    # external-citations-resolve within the same check_shape() run
    # (CodeRabbit review, issue #1064's own PR).
    sidecar_present = sidecar.is_file()
    if not sidecar_present:
        results.append(CheckResult("metadata-file-present", False, f"{SIDECAR_RELATIVE_PATH} exists", "missing"))
        sidecar_portability = SidecarPortability(state="absent")
    else:
        results.append(CheckResult("metadata-file-present", True, f"{SIDECAR_RELATIVE_PATH} exists", "present"))
        # Single read+parse site for the sidecar in this module (see the
        # SidecarPortability docstring): a corrupt (non-UTF-8) or otherwise
        # unreadable sidecar must not raise out of check_shape -- it is a
        # shape defect, reported as FAILed checks, not a usage error.
        try:
            parsed = _parse_manifest(sidecar.read_text(encoding="utf-8"))
            manifest: dict[str, object] | None = parsed.root
            malformed_lines = parsed.malformed_lines
            malformed_reference_items = parsed.malformed_reference_items
            unknown_reference_item_keys = parsed.unknown_reference_item_keys
            malformed_skill_dependency_items = parsed.malformed_skill_dependency_items
            unknown_skill_dependency_keys = parsed.unknown_skill_dependency_keys
            unknown_lifecycle_keys = parsed.unknown_lifecycle_keys
            unknown_lifecycle_fields = parsed.unknown_lifecycle_fields
            unknown_execution_requirement_keys = parsed.unknown_execution_requirement_keys
            unknown_execution_requirement_tools_keys = parsed.unknown_execution_requirement_tools_keys
            malformed_execution_requirement_tools_items = parsed.malformed_execution_requirement_tools_items
            unknown_execution_requirement_packages_keys = parsed.unknown_execution_requirement_packages_keys
            malformed_execution_requirement_packages_items = parsed.malformed_execution_requirement_packages_items
            unknown_execution_requirement_network_keys = parsed.unknown_execution_requirement_network_keys
            malformed_execution_requirement_network_items = parsed.malformed_execution_requirement_network_items
            malformed_external_citation_items = parsed.malformed_external_citation_items
            unknown_external_citation_item_keys = parsed.unknown_external_citation_item_keys
            read_error: str | None = None
        except (OSError, UnicodeDecodeError) as exc:
            manifest = None
            malformed_lines = []
            malformed_reference_items = []
            unknown_reference_item_keys = []
            malformed_skill_dependency_items = []
            unknown_skill_dependency_keys = []
            unknown_lifecycle_keys = []
            unknown_lifecycle_fields = []
            unknown_execution_requirement_keys = []
            unknown_execution_requirement_tools_keys = []
            malformed_execution_requirement_tools_items = []
            unknown_execution_requirement_packages_keys = []
            malformed_execution_requirement_packages_items = []
            unknown_execution_requirement_network_keys = []
            malformed_external_citation_items = []
            unknown_external_citation_item_keys = []
            malformed_execution_requirement_network_items = []
            read_error = type(exc).__name__

        if manifest is None:
            external_citations_sidecar_unreadable = True
            evidence = f"unreadable: {read_error}"
            # Deliberately not the body-marker fallback: a present-but-broken
            # sidecar is authoritative-and-failing, not absent. Running the
            # scan (rather than skipping it) lands extra findings on a skill
            # that is already failing portability-declared -- a false
            # negative in the gate is worse than a false positive.
            results.extend(_sidecar_unreadable_results(evidence))
            sidecar_portability = SidecarPortability(state="unusable")
        else:
            if malformed_lines:
                count = len(malformed_lines)
                plural = "" if count == 1 else "s"
                manifest_parsable_evidence = f"{count} malformed line{plural}: {malformed_lines[0]!r}"
            else:
                manifest_parsable_evidence = "no malformed lines"
            results.append(
                CheckResult(
                    "manifest-parsable",
                    not malformed_lines,
                    f"{SIDECAR_RELATIVE_PATH} has no malformed top-level lines",
                    manifest_parsable_evidence,
                )
            )
            api = manifest.get("apiVersion")
            kind_value = manifest.get("kind")
            envelope_ok = api == EXPECTED_API_VERSION and kind_value == EXPECTED_KIND
            results.append(
                CheckResult(
                    "manifest-envelope",
                    envelope_ok,
                    f"apiVersion is {EXPECTED_API_VERSION} and kind is {EXPECTED_KIND}",
                    f"apiVersion={api!r}, kind={kind_value!r}",
                )
            )
            meta = manifest.get("metadata")
            meta_name = meta.get("name") if isinstance(meta, dict) else None
            # Same PTH100 waiver shape_checks/field_checks.py's own
            # _validate_read_scope documents: the name compared here must
            # be the symlink's own basename, not the real directory it
            # points to (see the metadata-name-matches-dir test for a
            # symlinked skill dir).
            resolved_dir_name = Path(os.path.abspath(skill_dir)).name  # noqa: PTH100
            results.append(
                CheckResult(
                    "metadata-name-matches-dir",
                    meta_name == resolved_dir_name,
                    "metadata.name equals the skill directory name",
                    f"{meta_name!r} vs directory {resolved_dir_name!r}",
                )
            )
            spec_raw = manifest.get("spec")
            spec_is_mapping = isinstance(spec_raw, dict)
            spec = spec_raw if spec_is_mapping else {}
            portability = spec.get("portability")
            results.append(
                CheckResult(
                    "portability-declared",
                    portability in PORTABILITY_LEVELS,
                    f"spec.portability is one of {PORTABILITY_LEVELS}",
                    repr(portability),
                )
            )
            capability = spec.get("capabilityAssumption")
            results.append(
                CheckResult(
                    "capability-assumption-declared",
                    capability in CAPABILITY_ASSUMPTIONS,
                    f"spec.capabilityAssumption is one of {CAPABILITY_ASSUMPTIONS}",
                    repr(capability),
                )
            )
            results.append(_dependency_policy_declared_result(spec_is_mapping, spec_raw, spec))

            references = spec.get("references")
            results.append(
                _references_well_formed_result(
                    spec_is_mapping, spec_raw, malformed_reference_items, unknown_reference_item_keys, references
                )
            )
            results.append(_references_grammar_check(references))
            reference_source = _references_citation_source(references)
            if reference_source is not None:
                sidecar_citation_sources.append(reference_source)
            external_citations = spec.get("externalCitations")
            ext_well_formed_result, external_citations_declared = _external_citations_well_formed_result(
                spec_is_mapping,
                spec_raw,
                malformed_external_citation_items,
                unknown_external_citation_item_keys,
                external_citations,
            )
            results.append(ext_well_formed_result)
            lifecycle_raw = spec.get("lifecycle") if spec_is_mapping else None
            lifecycle_dict = lifecycle_raw if isinstance(lifecycle_raw, dict) else {}
            sidecar_citation_sources.extend(_lifecycle_reason_citation_sources(lifecycle_dict))
            results.extend(
                _skill_dependency_checks(
                    spec_is_mapping,
                    spec_raw,
                    spec,
                    malformed_skill_dependency_items,
                    unknown_skill_dependency_keys,
                    skill_dir,
                    portability,
                )
            )
            results.extend(
                _lifecycle_checks(
                    spec_is_mapping, spec_raw, spec, unknown_lifecycle_keys, unknown_lifecycle_fields, skill_dir
                )
            )
            results.extend(
                _execution_requirements_checks(
                    spec_is_mapping,
                    spec_raw,
                    spec,
                    unknown_execution_requirement_keys,
                    unknown_execution_requirement_tools_keys,
                    malformed_execution_requirement_tools_items,
                    unknown_execution_requirement_packages_keys,
                    malformed_execution_requirement_packages_items,
                    unknown_execution_requirement_network_keys,
                    malformed_execution_requirement_network_items,
                )
            )
            if portability in PORTABILITY_LEVELS:
                sidecar_portability = SidecarPortability(state="usable", level=portability)
            else:
                sidecar_portability = SidecarPortability(state="unusable")

    body = _body_after_frontmatter(text)

    offenders = _out_of_skill_link_targets("\n".join(body), skill_dir)
    results.append(
        CheckResult(
            "links-inside-skill",
            not offenders,
            "Markdown link targets resolve inside the skill's own directory",
            "all inside" if not offenders else "outside: " + ", ".join(offenders),
        )
    )

    # Shared across the SKILL.md anchor check below and every
    # references/*.md anchor check in the loop that follows -- more than
    # one link (in either file) can point at the same target file, and
    # each target's heading-slug set only needs computing once per run.
    # Pre-seeded with SKILL.md's own already-read/parsed body (below) and,
    # in the loop, each reference file's own already-read body -- without
    # this, a same-file bare-fragment link (or a cross-link back into
    # SKILL.md from a references/*.md file) would otherwise cost a second,
    # redundant read()+frontmatter-strip of a file this function already
    # has the text of in hand.
    anchor_slug_cache: dict[Path, frozenset[str] | None] = {
        skill_md: _heading_slugs("\n".join(body)),
    }
    broken_anchors = _broken_anchor_targets("\n".join(body), skill_md, skill_dir, anchor_slug_cache)
    results.append(
        CheckResult(
            "anchor-targets-resolve",
            not broken_anchors,
            "Markdown link #fragments resolve to a real heading anchor in their target file",
            "all resolve" if not broken_anchors else "broken: " + ", ".join(broken_anchors),
        )
    )

    stale_refs = _stale_related_skill_references("\n".join(body), skill_dir)
    results.append(
        CheckResult(
            "related-skill-references-resolve",
            not stale_refs,
            "every '**vs. `name`:**' Related-skills bullet name resolves to an existing sibling skill directory",
            "all resolve" if not stale_refs else "dangling: " + ", ".join(stale_refs),
        )
    )

    results.extend(_references_dir_checks(skill_dir, anchor_slug_cache))

    # A "manifest is None" (unreadable sidecar) already emitted a failed
    # external-citations-resolve above, alongside every sibling
    # sidecar-derived check -- skip here so this unconditional block does
    # not silently overwrite that FAIL with a "not declared (optional)"
    # PASS (code-review finding, issue #1055: _by_name's dict comprehension
    # keeps only the LAST same-named CheckResult, so appending twice is not
    # merely redundant, it is a real gate bypass). Guarded on the precise
    # external_citations_sidecar_unreadable flag, NOT
    # sidecar_portability.state != "unusable" -- that state also fires for
    # a parsed manifest with an invalid spec.portability, a second,
    # unrelated case where this block must still run (a follow-up
    # code-review finding on the first fix: the broader state-based guard
    # silently skipped external-citations-resolve there too).
    #
    # Also requires sidecar_present (the cached sidecar.is_file() result
    # from above, not a second live call): when the sidecar is absent
    # entirely, every sibling sidecar-derived check (references-well-formed,
    # skill-dependencies-well-formed, ...) is omitted outright -- only
    # metadata-file-present: False is emitted. Without this guard,
    # external-citations-resolve broke that convention by firing here as a
    # false "not declared (optional)" PASS even with no sidecar at all
    # (issue #1064).
    if not external_citations_sidecar_unreadable and sidecar_present:
        results.append(_external_citations_resolve_result(external_citations_declared, skill_md, skill_dir, body))

    results.extend(_issue_citation_checks(skill_md, skill_dir, body, extra_sources=sidecar_citation_sources))
    results.extend(_cross_skill_citation_checks(skill_md, skill_dir, body, anchor_slug_cache))
    results.extend(_mechanism_fit_checks(skill_md, skill_dir, body))
    results.extend(_illustrative_model_id_checks(skill_md, skill_dir, body))
    results.extend(_raw_placeholder_checks(skill_md, skill_dir, body))
    results.extend(_step_location_checks(skill_md, skill_dir, body))
    # function-body-test-coverage: WAIVED: this diff's own new
    # test_untrusted_authority_crossover_* tests already call
    # css.check_shape(d) directly (skills/evaluating-skill-quality/scripts/
    # test_gitapex_check_skill_shape.py), but that gate's own
    # _test_relative_paths() unconditionally resolves to top-level
    # tests/test_{stem}.py and has no fallback for this repository's
    # pre-existing co-located test convention (a source file's own
    # sibling test_*.py, e.g. this exact file/test pair) -- a gate-side
    # gap, confirmed by tests/test_gitapex_check_skill_shape.py not
    # existing at all, not a real coverage hole in this line.
    results.extend(_untrusted_authority_crossover_checks(skill_md, skill_dir, body))
    results.extend(_dimension_quote_exemption_checks(skill_md, skill_dir, body))
    results.extend(_no_voodoo_constant_checks(skill_md, skill_dir, body))
    results.extend(_script_execution_intent_checks(skill_md, skill_dir, body))
    if _is_portable(body, sidecar_portability):
        declared_citation_paths = frozenset(
            c["path"] for c in external_citations_declared if isinstance(c.get("path"), str)
        )
        results.extend(_portable_path_citation_checks(skill_md, skill_dir, body, declared_citation_paths))
        results.extend(_portable_skill_citation_checks(skill_md, skill_dir, body))
        results.extend(_portable_demonstrative_repository_citation_checks(skill_md, skill_dir, body))
        results.extend(_out_of_skill_scripts_checks(skill_md, skill_dir, body))

    return results


def format_report(results: list[CheckResult]) -> str:
    width = max((len(r.name) for r in results), default=5)
    lines = [f"{'CHECK'.ljust(width)}  RESULT  EVIDENCE (rule)"]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"{r.name.ljust(width)}  {status}    {r.evidence}  ({r.rule})")
    passed = sum(1 for r in results if r.passed)
    lines.append(f"\n{passed}/{len(results)} checks passed")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check one or more SKILL.md's deterministic shape (read-only).")
    parser.add_argument(
        "--allowed-root",
        help="Caller-approved directory that must contain every target; "
        "also rejects symlinks in the target skill. The caller must keep "
        "the snapshot immutable while the check runs.",
    )
    parser.add_argument(
        "target",
        nargs="+",
        help="One or more paths to a skill directory or a SKILL.md file. A "
        "path under a skill's metadata/ or references/ directory (issue "
        "#1387: what a pre-commit hook's changed-file argv actually "
        "supplies) is normalized to its owning skill directory.",
    )
    args = parser.parse_args(argv)
    allowed_root = Path(args.allowed_root) if args.allowed_root else None

    # Normalize each raw target to its owning skill directory and dedupe --
    # a commit touching both skills/foo/SKILL.md and
    # skills/foo/references/bar.md must grade skills/foo once, not twice.
    # Order preserved (first occurrence wins); sources kept per group so the
    # printed report can attribute back to every raw path that mapped there.
    sources_by_owner: dict[Path, list[str]] = {}
    for raw in args.target:
        owner = _owning_skill_dir(Path(raw))
        sources_by_owner.setdefault(owner, []).append(raw)

    guard_error = False
    check_error = False
    for target, sources in sources_by_owner.items():
        if allowed_root is not None:
            try:
                _validate_read_scope(target, allowed_root)
            except (OSError, ValueError) as exc:
                print(f"error: unsafe target path: {exc}", file=sys.stderr)
                guard_error = True
                continue
        skill_md = _resolve_skill_md(target)
        if not skill_md.is_file():
            print(f"error: no SKILL.md found at: {target}", file=sys.stderr)
            guard_error = True
            continue
        try:
            results = check_shape(target)
        except (OSError, UnicodeDecodeError) as exc:
            print(f"error: could not read skill files: {exc}", file=sys.stderr)
            guard_error = True
            continue
        # len(sources) == 1, not sources == [str(target)] (adversarial
        # review finding): the raw source's literal spelling almost always
        # differs from the normalized target (e.g. a "SKILL.md"-suffixed
        # or "references/..."-prefixed argv), so the stricter equality
        # would attach "(touched: ...)" to nearly every single-target run.
        header = str(target) if len(sources) == 1 else f"{target} (touched: {', '.join(sources)})"
        print(f"{header}:")
        print(format_report(results))
        if not all(r.passed for r in results):
            check_error = True

    if guard_error:
        return 2
    return 1 if check_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
