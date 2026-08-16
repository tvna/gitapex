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
    to another repository. A full ``https://github.com/tvna/gitapex/issues/149``-style
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
    ``*.py`` file directly under the skill's own ``scripts/`` directory
    (``test_*.py`` files are excluded -- test fixture literals are not
    "configuration" and would be enormous false-positive noise, e.g. this
    very checker's own ``test_gitapex_check_skill_shape.py``) whose
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
    Silently passes with "not declared (optional)" evidence, the same
    absent-optional-content convention used throughout this docstring,
    when the skill has no ``scripts/`` directory at all or it contains no
    qualifying non-test ``.py`` file.
  - Script execution intent stated (script-execution-intent-stated, issue
    #1045's Acceptance Criteria Map item A): every file directly under
    the skill's own ``scripts/`` directory (any extension, not just
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
import ast
import datetime
import json
import os.path
import re
import sys
import tokenize
from collections.abc import Iterable
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

# The Claude Developer Platform Skills API enforces description <= 1024
# chars and name <= 64 lowercase-hyphen chars (platform.claude.com/docs/
# en/agents-and-tools/agent-skills/best-practices) -- stricter than Claude
# Code's own frontmatter parsing, so this checker uses the platform's
# tighter cap to stay valid on both surfaces.
DESCRIPTION_MAX_CHARS = 1024
NAME_MAX_CHARS = 64  # same Skills API cap family as DESCRIPTION_MAX_CHARS above
# Cap on spec.references' summary field (and spec.lifecycle.experimental/
# deprecated.reason) in metadata/gitapex.yaml -- these free-text fields have
# no length limit otherwise and can grow unbounded by mixing multiple
# distinct events into one string. There is no overflow escape
# valve (e.g. a second file to move detail into): the fix for an
# over-budget entry is to decompose it into one list entry per distinct
# event (see REFERENCES_KIND_VOCAB/REFERENCES_ITEM_SUBKEYS below), each of
# which is short by construction once it stops being fused with its
# siblings.
REFERENCES_ENTRY_MAX_CHARS = 500
# spec.references is a list whose items are themselves mappings -- the one
# field in this sidecar with real nested structure one level *inside* a
# list item, rather than under a scalar key the way spec.skillDependencies/
# spec.lifecycle/spec.executionRequirements all nest. Each item has three
# required scalar fields (kind, anchor, summary) and one optional nested
# mapping (outcome, free-form key/value atoms -- verdict, found, fixed,
# open, ... -- with no closed vocabulary of its own, since real entries use
# too varied a set of outcome facts for a fixed schema to fit).
REFERENCES_ITEM_SUBKEYS = ("kind", "anchor", "summary", "outcome")
REFERENCES_ITEM_REQUIRED_SUBKEYS = ("kind", "anchor", "summary")  # outcome is the one optional subkey
# Exactly 4 spaces -- one level under spec.references' own 2-space key,
# matching every other gated block's own fixed-indent convention.
REFERENCES_ITEM_INDENT = 4
# Closed vocabulary for the "kind" field, derived from the recurring entry
# shapes actually found across every sidecar's spec.references: a
# decision/change record, an audit-round record (a named
# method/dispatch/verdict/finding-count), a deferral to a follow-up issue,
# an external (non-gitapex) corroboration, a portability/worked-example
# caveat, a citation-elision disclosure, or a correction/retraction of an
# earlier entry. Not speculative -- no kind is included that the corpus
# does not already contain an example of.
REFERENCES_KIND_VOCAB = (
    "decision",
    "audit",
    "deferral",
    "corroboration",
    "caveat",
    "elision",
    "correction",
)
# spec.externalCitations (issue #1055): a Portable skill's own opt-in
# declaration that a specific evals/docs/CLAUDE.md-chapter path citation
# names an input source or output destination, not a control dependency --
# see rubric.md's Portability level section for the underlying distinction
# this supplements, not replaces, GENERIC_ROLE_HEDGE_PHRASES for. Each item
# is a flat two-field mapping (no nested "outcome" sub-block, unlike
# spec.references' own items), structurally the simpler of the two list-of-
# mappings fields this sidecar has.
EXTERNAL_CITATION_ITEM_SUBKEYS = ("path", "role")
EXTERNAL_CITATION_ITEM_REQUIRED_SUBKEYS = ("path", "role")  # both subkeys are required; no optional field here
# Exactly 4 spaces, matching REFERENCES_ITEM_INDENT's own convention -- one
# level under spec.externalCitations' own 2-space key.
EXTERNAL_CITATION_ITEM_INDENT = 4
# A repo-external path cited only as an input source (read whatever the
# calling repository has) or an output destination (this skill's own
# result is consumed downstream by X) is not a control dependency -- see
# rubric.md's Portability level section. Closed vocabulary; not
# speculative -- both values are already this repository's own established
# vocabulary from that section's prose.
EXTERNAL_CITATION_ROLES = ("input-source", "output-destination")
# A declared spec.externalCitations path must be rooted at evals/ or docs/,
# the same two prefixes REPO_PATH_CITATION_RE's own evals/docs alternative
# gates -- this mechanism exists to rescue exactly that check's own
# citations, so a path outside both prefixes could never be a real rescue
# target in the first place (code-review finding, issue #1055). Mirrors
# skill-metadata.schema.json's own externalCitationItem.path pattern; kept
# as a separate, hand-duplicated regex here rather than shared, matching
# this module's own established convention for a schema constraint that
# also needs enforcing in this dependency-free parser (see
# EXEC_REQ_NETWORK_SUBKEYS' own comment for the precedent).
EXTERNAL_CITATION_PATH_RE = re.compile(r"^(?:evals|docs)/[A-Za-z0-9._/-]+$")
# "Keep SKILL.md body under 500 lines for optimal performance" (same doc;
# also code.claude.com/docs/en/skills).
BODY_MAX_LINES = 500
# Not an Anthropic-specified number -- this repository's own convention
# for when a reference file earns a table of contents, chosen as a round
# threshold past which skimming a flat file gets slow.
TOC_MIN_LINES = 100
RESERVED_NAME_WORDS = ("anthropic", "claude")  # Anthropic's own reserved skill-name words

# Invocation-control frontmatter. Both fields are Claude Code product
# extensions the Agent Skills standard does not define; both are booleans
# whose accepted literals are documented at code.claude.com/docs/en/skills
# ("Boolean fields accept yes, no, on, off, 1, and 0 in any letter case, in
# addition to true and false"), so the VALUE is lowercased before lookup.
# The KEY is matched case-sensitively and deliberately so: YAML keys are
# case-sensitive and the documented field names are lowercase, so a
# differently-cased "Disable-Model-Invocation" is a different key the
# runtime would not read either -- correctly invisible to this check.
INVOCATION_TRUE_LITERALS = ("true", "yes", "on", "1")
INVOCATION_FALSE_LITERALS = ("false", "no", "off", "0")  # the false half of the same documented vocabulary above
# disable-model-invocation defaults to false (Claude may auto-load);
# user-invocable defaults to true (the skill shows in the / menu). The
# defaults matter here because the pair only fails as a COMBINATION, so an
# absent field still has to resolve to a value.
INVOCATION_FIELD_DEFAULTS = {
    "disable-model-invocation": False,
    "user-invocable": True,
}

# The sidecar is this repository's own metadata convention, not part of the
# Anthropic Agent Skills standard -- hence its own metadata/ subdirectory
# and gitapex-labelled apiVersion. It is never auto-loaded by the skill
# runtime, so it can never change skill behavior.
SIDECAR_RELATIVE_PATH = "metadata/gitapex.yaml"
# Kubernetes-manifest-shaped envelope, borrowed as a convention only; the
# version lets the schema grow without breaking older sidecars.
EXPECTED_API_VERSION = "gitapex.io/v1alpha1"
EXPECTED_KIND = "SkillMetadata"  # the sidecar's fixed manifest kind, alongside EXPECTED_API_VERSION above
PORTABILITY_LEVELS = ("Portable", "Repository-scoped", "Mixed")  # closed vocabulary for spec.portability
CAPABILITY_ASSUMPTIONS = ("Broad", "Frontier", "Adaptive")  # closed vocabulary for spec.capabilityAssumption
DEPENDENCY_POLICY_LEVELS = ("StdlibOnly", "Declared")  # closed vocabulary for spec.dependencyPolicy
# A plain "- <value>" list item, indented 2 or more spaces -- real YAML
# accepts a block sequence indented level with its mapping key (2 spaces,
# same as spec.references' own key) or further indented (4 spaces, this
# repo's convention); requiring one exact width would silently drop an
# otherwise-valid item at a different indent instead of reading it. The
# only list shape this parser understands, and only under spec.references
# specifically.
REFERENCES_LIST_ITEM_RE = re.compile(r"^[ ]{2,}-\s*(.*)$")
# An unquoted item that itself looks like a YAML mapping key ("key: value"
# or a bare "key:"), e.g. "- path: references/rubric.md" -- real YAML
# parses that as a single-key mapping, not a scalar string, and this
# parser has no map-shaped-item support. A quoted string starting with
# this same text (e.g. "\"path: something\"") is a deliberate scalar and
# is excluded by the caller checking for a wrapping quote first.
REFERENCES_MAPPING_LIKE_RE = re.compile(r"^[A-Za-z0-9_.-]+:(\s|$)")
# An unquoted plain scalar that YAML's core schema resolves to something
# OTHER than a string -- null, boolean, or numeric -- rather than the
# string every list-of-scalar-strings field (spec.references,
# spec.skillDependencies.requires/relatedTo,
# spec.executionRequirements.tools.read/write/shell,
# spec.executionRequirements.packages.<ecosystem>) assumes each of its
# items is. Deliberately the common, uncontroversial
# subset -- not YAML 1.1's yes/no/on/off, which are also ordinary English
# words a legitimate capability-tag or reference string could contain --
# rather than a full type resolver. Checked only against an UNQUOTED
# item's raw text; a caller already tests for a wrapping quote first (the
# same way REFERENCES_MAPPING_LIKE_RE above is only checked when
# unquoted), since a quoted item (e.g. "\"true\"") is a deliberate string
# regardless of its contents.
YAML_NON_STRING_SCALAR_RE = re.compile(
    r"^(?:~|[Nn]ull|NULL"
    r"|[Tt]rue|TRUE|[Ff]alse|FALSE"
    r"|[-+]?[0-9]+"
    r"|[-+]?(?:[0-9]+\.[0-9]*|\.[0-9]+)(?:[eE][-+]?[0-9]+)?"
    r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"
)
# A real YAML comment: an unquoted "#" preceded by start-of-string or
# whitespace -- YAML never treats a "#" glued directly onto a preceding
# non-space character as a comment marker (e.g. "true#tag" is the
# literal string "true#tag", not "true" plus a comment). Used only to
# strip a trailing comment before classifying an unquoted list item's own
# scalar type in _is_non_string_plain_scalar below -- the item's stored
# value is unaffected either way, only the type classification is --
# a comment-bearing item such as "true # rationale" would otherwise defeat
# YAML_NON_STRING_SCALAR_RE's own full-string anchor, silently certifying
# a real YAML boolean/null/numeric as a string whenever it carries a
# trailing comment.
_INLINE_COMMENT_RE = re.compile(r"(?:^|\s)#.*$")


def _is_non_string_plain_scalar(raw_text: str) -> bool:
    """Whether an UNQUOTED list item's raw text is a YAML null/boolean/
    numeric scalar rather than a string, comment stripped first the same
    way a real YAML parser would before resolving the item's type.
    Shared by every gated list-of-scalar-strings site (spec.references;
    spec.skillDependencies.requires/relatedTo;
    spec.executionRequirements.tools.read/write/shell;
    spec.executionRequirements.packages.<ecosystem>)."""
    stripped = _INLINE_COMMENT_RE.sub("", raw_text).strip()
    return bool(YAML_NON_STRING_SCALAR_RE.match(stripped))


# spec.skillDependencies's two recognized subkeys, and the shape of their
# lines. Subkeys sit at 4 spaces (one level under skillDependencies' own
# 2-space key). List items accept 4 or more spaces -- real YAML allows a
# block sequence indented level with its own key (4 spaces, same as
# "requires:"/"relatedTo:" themselves) or further indented (this repo's
# convention); requiring one exact width would silently drop an otherwise-
# valid item at a different indent instead of reading it, the same
# accommodation REFERENCES_LIST_ITEM_RE already makes for spec.references.
SKILL_DEPENDENCY_SUBKEYS = ("requires", "relatedTo")
SKILL_DEP_LIST_ITEM_RE = re.compile(r"^[ ]{4,}-\s*(.*)$")

# spec.lifecycle's three recognized sub-blocks -- "experimental" (entry
# side: not yet proven, mirrors Rust's #[unstable(feature, issue)],
# Python's provisional/PendingDeprecationWarning APIs, Go's
# GOEXPERIMENT-gated features, Kubernetes' alpha/beta feature gates),
# "deprecated" (exit side: superseded, mirrors Rust's
# #[deprecated(since, note)], Go's "// Deprecated:" doc comment, Python's
# warnings.deprecated/PEP 702, Kubernetes' API deprecation policy), and
# "stable" (a graduation record, mirrors Rust's
# #[stable(feature, since)]). experimental and deprecated are independent
# -- neither implies nor excludes the other. experimental and stable ARE
# mutually exclusive, though (see EXPERIMENTAL_STABLE_RULE below): "not
# yet graduated" and "already graduated on some date" cannot both be
# true, unlike experimental+deprecated which is merely unusual, not
# contradictory. A skill declaring none of the three is implicitly
# Stable (every skill in this repository today). One nesting level
# deeper than spec.skillDependencies: subkeys sit at 4 spaces (same as
# requires/relatedTo), but each subkey opens ANOTHER nested block of
# scalar fields at 6 spaces, rather than a list.
LIFECYCLE_SUBKEYS = ("experimental", "deprecated", "stable")
LIFECYCLE_FIELDS = {
    "experimental": ("reason", "trackingIssue", "since"),
    "deprecated": ("reason", "replacement", "since", "removeAfter"),
    "stable": ("since", "compatibilityGuarantee"),
}
LIFECYCLE_REQUIRED_FIELDS = {
    "experimental": ("reason", "trackingIssue"),
    "deprecated": ("reason", "replacement"),
    "stable": ("since",),
}
# Kubernetes' alpha/beta/GA API-stability tiers, borrowed as spec.
# lifecycle.stable's optional compatibilityGuarantee enum -- shape-gated
# only; no rule ties a sibling's spec.skillDependencies.requires to this
# value (that would be new cross-skill coupling beyond what was asked).
COMPATIBILITY_GUARANTEE_LEVELS = ("Alpha", "Beta", "GA")
# spec.lifecycle.renamedFrom is different in kind from the three
# sub-blocks above: a plain scalar directly under lifecycle: (like
# metadata.name under metadata:), never opening a nested block. Backward-
# pointing by deliberate choice -- it lives on the *surviving* (new)
# skill's sidecar, naming the old, now-nonexistent directory, because
# `git mv` deletes the old directory itself, leaving nowhere to host a
# forward-pointing renamedTo/tombstone sidecar. Free-form and NOT
# resolved against sibling directories (unlike deprecated.replacement) --
# the whole point is that the old name is expected to no longer exist.
LIFECYCLE_SCALAR_KEYS = ("renamedFrom",)
# Strict calendar-date shape for spec.lifecycle's since/removeAfter
# fields: YYYY-MM-DD only. Real-date validity (rejecting e.g. 2026-02-30)
# is checked separately via datetime.date.fromisoformat in
# _valid_lifecycle_date -- this regex only gates the shape first, so that
# lenient ISO-variant parsing in Python 3.11+ never gets a chance to
# accept an off-shape string.
LIFECYCLE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# A full GitHub issue/PR URL anchoring the whole string: this repository's
# own host only (metadata/gitapex.yaml is maintainer-facing provenance for
# THIS repository, never something a portable skill body depends on), an
# "issues" or "pull" segment, then a digit run. Deliberately a full URL,
# not a bare "#123"/"owner/repo#123" shape: a bare
# issue number means nothing once this sidecar travels with its skill
# directory to another repository (e.g. plugin vendoring); a full URL still
# resolves to the right place wherever it lands. Shape-only -- never
# resolved against a live GitHub API call, since this checker is
# offline/read-only by design.
LIFECYCLE_ISSUE_REF_RE = re.compile(r"^https://github\.com/tvna/gitapex/(?:issues|pull)/\d+$")

# A YAML mapping key at a given indent, however it was written: a bare
# scalar key (any run of characters up to the first unquoted ":" that
# does not start with whitespace, a quote, or "#") or a single/double-
# quoted string key. Shared by every gated block's key-recognition site
# (spec.skillDependencies' requires/relatedTo, spec.lifecycle's
# experimental/deprecated/stable/renamedFrom and their own nested fields).
# Earlier per-field pairs -- a specific-name alternation regex for
# recognized keys, plus a [A-Za-z0-9_-]+ catch-all for unrecognized ones --
# shared one blind spot: a quoted key (`"extra": foo`) or a key containing
# a character outside that narrow class matched NEITHER regex, so it fell
# through both checks into the "stray content, skip silently" branch
# instead of ever reaching unknown-key detection. Matching
# broadly here and leaving "recognized vs. unknown" entirely to the
# caller's own membership check closes that gap: every syntactically
# key-shaped line at this indent is now seen as A key, so an unrecognized
# one can no longer hide behind a narrow character class the way a
# recognized one never had to. Still not a real YAML string lexer, though
# -- it has no escape-sequence support and requires the closing quote to
# be immediately followed by ":" -- so a key using an escaped quote
# (`"ex\"tra": foo`) or whitespace before its colon (`"extra" : foo`) does
# not match this regex either. Each of this regex's three call sites
# handles that residual gap the same way: a line at the gated indent that
# matches neither a list item currently being collected nor this key
# pattern is itself flagged as unknown/malformed, not silently skipped --
# rejecting every unmatched line at that indent, rather than only the
# ones this regex happens to parse, is the actual fail-closed contract.
KEY_LINE_RE_4 = re.compile(r'^[ ]{4}(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'#][^:]*?)):[ \t]*(.*)$')
KEY_LINE_RE_6 = re.compile(r'^[ ]{6}(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'#][^:]*?)):[ \t]*(.*)$')
# One nesting level deeper than KEY_LINE_RE_6: spec.references' own item
# mappings nest an optional "outcome" sub-mapping (8-space indent, one
# level under the item's own 6-space fields) -- the only field in this
# sidecar three levels deep under spec.
KEY_LINE_RE_8 = re.compile(r'^[ ]{8}(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'#][^:]*?)):[ \t]*(.*)$')
# Matches a spec.references list item's own first field, given inline
# right after its "- " marker (e.g. "kind: decision" from
# "- kind: decision") -- same key-shape alternation as KEY_LINE_RE_4/6, but
# with no anchored leading indent, since the "- " prefix itself already
# consumed a variable amount of the line before this text was isolated.
INLINE_KEY_VALUE_RE = re.compile(r'^(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'#][^:]*?)):[ \t]*(.*)$')

# spec.executionRequirements' two recognized subkeys so far: "tools" and
# "network" (issue #845), each at 4-space indent -- same depth as
# spec.skillDependencies' requires/relatedTo and spec.lifecycle's
# experimental/deprecated/stable. Recognized via the same shared
# KEY_LINE_RE_4 matcher those two fields use, not a field-specific regex --
# for consistency across all three gated blocks.
EXEC_REQ_TOOLS_SUBKEYS = ("read", "write", "shell")
# List items accept 6 or more spaces -- the same indent-drift tolerance
# REFERENCES_LIST_ITEM_RE/SKILL_DEP_LIST_ITEM_RE already give their own
# lists (an item at their own subkey's depth, or deeper). Reused verbatim
# by spec.executionRequirements.network's own domains list below --
# domains sits at the identical 6-space depth tools' own read/write/shell
# lists do, so a second, byte-identical regex would add nothing.
EXEC_REQ_TOOLS_LIST_ITEM_RE = re.compile(r"^[ ]{6,}-\s*(.*)$")

# spec.executionRequirements.network's two recognized subkeys (issue #845,
# resolving the mixed scalar-plus-list shape issue #349 deferred): "mode"
# (a scalar enum) and "domains" (a list), in the SAME sub-block -- unlike
# tools, whose read/write/shell are all list-valued. The parser layer below
# does not judge which subkey should hold a scalar vs. a list; each subkey
# is captured exactly as written (an inline value is stored as a raw
# scalar, a blank value opens a list), the same per-subkey mechanism
# tools' own read/write/shell already use -- type validity (mode must be a
# recognized enum string; domains must be a list) is entirely a
# checker-layer question (_execution_requirements_checks), never a
# parser-layer one. This slice hand-duplicates tools' own state machine
# (in_exec_tools/exec_tools/... -> in_exec_network/exec_network/...) rather
# than extracting a shared generic-subblock helper both could call -- the
# existing tools state machine is threaded through this loop via several
# mutually exclusive `nonlocal` flags, and a real extraction touching that
# already-proven path was judged higher regression risk than the size of
# this slice's own scope justifies. A future mixed-shape category (mcp,
# per issue #349's own deferral) can copy this block's shape directly, but
# still cannot literally reuse it as a function without that extraction --
# stated explicitly here per this issue's own disclosure requirement,
# rather than silently claiming a generalization that was not attempted.
EXEC_REQ_NETWORK_SUBKEYS = ("mode", "domains")
EXEC_REQ_NETWORK_MODES = ("disabled", "allowlist", "unrestricted")  # closed vocabulary for network.mode

# spec.executionRequirements' third recognized block sub-key: "packages" --
# the first whose own subkeys are NOT a fixed, closed tuple the way tools'
# read/write/shell (EXEC_REQ_TOOLS_SUBKEYS) and network's mode/domains
# (EXEC_REQ_NETWORK_SUBKEYS) are. A package ecosystem (pip, npm, cargo, ...)
# is an open-ended set by design -- skill-metadata.schema.json's own
# executionRequirementsPackages deliberately declares no closed enum of
# supported ecosystems, via propertyNames rather than a fixed properties
# list -- so unknown-subkey detection here must be a REGEX match against
# that same pattern, not a tuple-membership check: a future ecosystem
# becomes usable with no parser change, matching the schema's own design
# intent. Kept as a separate, hand-duplicated regex here rather than
# imported from the schema (the same precedent EXTERNAL_CITATION_PATH_RE
# already established for a schema constraint that also needs enforcing in
# this dependency-free, no-YAML-library parser).
EXEC_REQ_PACKAGES_KEY_RE = re.compile(r"^[a-z][a-z0-9-]*$")
# Detects a line that LOOKS like an attempted "- <value>" packages list item
# (a "-" as its first non-whitespace character, tabs included) but whose
# leading whitespace fails EXEC_REQ_TOOLS_LIST_ITEM_RE's own strict "6 or
# more literal SPACE characters" requirement -- a tab anywhere in the
# indent, or fewer than 6 spaces. Used only to distinguish that case from a
# packages ecosystem list genuinely ending (a real dedent, or a new sibling
# ecosystem key) while collecting_exec_packages_list is open: without it, a
# line like "\t- some-package" (or "  - some-package", 2 spaces) silently
# finalizes the list as empty -- indistinguishable from the package truly
# never having been declared -- instead of being recorded into
# malformed_execution_requirement_packages_items the way an item
# EXEC_REQ_TOOLS_LIST_ITEM_RE itself rejects (mapping-shaped, wrong type)
# already is. Cannot collide with a legitimate new KEY_LINE_RE_6 sibling
# key: whenever this matches AND the strict item regex already failed, the
# leading whitespace run is provably not "exactly 6 literal spaces" (either
# shorter, or tab-containing), which KEY_LINE_RE_6 requires verbatim -- so
# the two can never both match the same line. Scoped to packages only, per
# this fix's own issue: tools' and network's own sibling list-item blocks
# (collecting_exec_tools_list/collecting_exec_network_list below) share this
# exact latent gap -- no equivalent fail-closed check exists at their own
# list-item level either, only at the surrounding key level -- and are
# deliberately left as-is here rather than silently duplicating the fix
# beyond this issue's own scope.
EXEC_REQ_PACKAGES_MISINDENTED_ITEM_RE = re.compile(r"^[ \t]*-\s*(.*)$")

TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
# A YAML plain (unquoted) scalar cannot safely contain ": " (colon followed
# by whitespace) or end in a bare ":" -- a real YAML parser reads either as
# the start of a new mapping key and either raises ("mapping values are not
# allowed in this context") or misparses the rest of the line. It similarly
# treats " #" (or a leading "#") as a comment marker, silently truncating
# everything after it. This repository's own frontmatter parser
# (_parse_frontmatter, above) is deliberately lenient and reproduces
# neither failure, so this check exists independently of it.
UNSAFE_COLON_RE = re.compile(r":(?:\s|$)")
UNSAFE_COMMENT_RE = re.compile(r"(?:^|\s)#")
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Accept either "Table of contents" or a bare "Contents" heading.
TOC_RE = re.compile(r"^#+\s+(?:table of )?contents\b", re.IGNORECASE | re.MULTILINE)
BLOCK_SCALAR_INDICATORS = (
    ">",
    "|",
    ">-",
    "|-",
    ">+",
    "|+",
)  # YAML block-scalar indicators (folded/literal, chomping variants)
# Markdown inline link syntax: [text](target).
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
# Reference-style link definitions: [label]: target -- the destination a
# [text][label] reference resolves to. Up to 3 leading spaces per
# CommonMark; destination is either <...>-wrapped or a bare non-space run.
REFDEF_RE = re.compile(r"^[ ]{0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)", re.MULTILINE)
# The "Related skills" bullet convention this repo's own skills use to name
# a sibling skill by directory name: "**vs. `name`:**", optionally two
# names separated by " / " (e.g. "**vs. `a` / `b`:**"), followed by
# explanatory prose that commonly repeats or adds further skill-name
# backticks of its own (e.g. "... produces the PR `other-skill` would then
# take over."). Matches the whole bullet -- header through its own
# explanatory text -- up to the next bullet marker, a blank line, or end of
# string, so BACKTICK_SKILL_NAME_RE can pull every backtick-quoted name out
# of the full bullet, not just its header. Deliberately narrower than "any
# backtick-quoted kebab-case token in the body" -- that broader scan has a
# high false-positive rate (CI-gate names, shape-checker check IDs, subagent
# names, executor names, filenames, and sibling/external-project skill names
# all appear in backticks elsewhere in skill prose without being a
# same-repo skill-directory reference); this bullet is the one
# consistently-used, low-ambiguity convention for one skill naming another,
# and that convention covers its own body prose just as much as its header.
RELATED_SKILL_BULLET_RE = re.compile(r"\*\*vs\.\s+.+?:\*\*.*?(?=\n[ \t]*-\s|\n[ \t]*\n|\Z)", re.DOTALL)
BACKTICK_SKILL_NAME_RE = re.compile(r"`([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)`")
# An absolute-URL scheme (http:, https:, mailto:, ftp:, ...) -- anything
# matching this is external, not a same-repo relative path.
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")

# Portable self-citation scans (see the module docstring). A skill counts as
# Portable only when its portability marker says "Portable" without the
# "Mixed" / "Repository-scoped" qualifiers -- those levels legitimately cite
# repo-specific paths, so the two repo-path checks below do not apply to
# them. The bare-issue-citation check is different: it runs unconditionally
# on every skill regardless of this classification.
# The near-top body marker, kept only as the fallback declaration form for a
# skill vendored in from another repository that has no sidecar. Skills in
# this repository declare portability in metadata/gitapex.yaml instead.
PORTABILITY_RE = re.compile(r"\bportability\s*:", re.IGNORECASE)
PORTABILITY_MAX_BODY_LINE = 6  # the fallback body marker must appear "near the top", not anywhere in the body
PORTABLE_LEVEL_RE = re.compile(r"\bportable\b", re.IGNORECASE)
NON_PORTABLE_LEVEL_RE = re.compile(r"\b(?:mixed|repository-scoped|repo-scoped)\b", re.IGNORECASE)
# A GitHub issue/PR-number citation: an optional "owner/repo" prefix, then
# "#" and a digit run. The trailing (?![\d-]) rejects an in-page anchor slug
# like "#1-discovery" (a digit run followed by "-word"); a real citation ends
# at the digits.
ISSUE_CITATION_RE = re.compile(r"(?:[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*)?#\d+(?![\d-])")
# An origin-repository path citation rooted at this repo's own top-level
# tooling dirs. Kept deliberately narrow (evals/ and docs/) -- the two roots
# the historical incidents used -- rather than every path shape, so the scan
# stays a low-false-positive backstop, not a general path linter. The second
# alternative (issue #192, Refs #26 repair 1) catches a bare citation of the
# *calling repository's own instruction-file* chapter/section -- the same
# self-containment defect as an evals/docs path citation (a consumer repo
# vendoring this skill has no such chapter, or a different one), just a
# different citation shape. Three real phrasings are already in use
# elsewhere in this repository ("CLAUDE.md ch.2", "CLAUDE.md chapter 3",
# "CLAUDE.md section 4") -- all three are covered rather than guessing at
# just the one issue #26 happened to quote. The CLAUDE.md alternative is
# scoped case-insensitive via an inline ``(?i:...)`` group (a review
# finding: "CLAUDE.md Chapter 2" or "claude.md section 4" otherwise
# evaded both checks this constant feeds) -- scoped rather than a
# pattern-wide ``re.IGNORECASE``, so the evals/docs alternative, whose
# real targets are always lowercase POSIX paths, keeps its existing
# case-sensitive behavior unchanged.
#
# evals/, docs/, and CLAUDE.md-chapter citations get identical treatment,
# as of issue #1051 -- a corpus incident (rubric.md's own Execution
# requirements section) showed that the *disclosing* half of the old hedge
# vocabulary ("this repository" / "gitapex") lets a hedge phrase disclose a
# repo-path dependency without removing it: the cited file still does not
# travel with a vendored copy of the skill, hedged or not. Earlier
# revisions of this check gave evals/ that same full hedge escape in
# inline-code form while unconditionally banning docs/ -- an asymmetric,
# enumerated exception table that itself reproduced the same class of gap
# (a future third top-level dir would need its own manual entry in that
# table to get the strict treatment). Both prefixes now get identical
# treatment in both the bare-prose form (unconditional, as always -- no
# hedge phrase has ever rescued a bare-prose match) and the inline-code
# form (rescued only by GENERIC_ROLE_HEDGE_PHRASES, the narrow half of the
# old vocabulary that marks a citation as a generic illustrative
# placeholder rather than a real reference to this repository's own file
# -- see that constant's own comment for the full rationale). This mirrors
# the same resolve-inside-the-skill-directory-or-fail rule
# SCRIPTS_PATH_BARE_RE below already applies to scripts/ citations (the
# one prefix that legitimately CAN resolve inside the citing skill's own
# directory, so it gets a resolution check instead of a pattern ban).
REPO_PATH_CITATION_RE = re.compile(
    r"(?:evals|docs)/[A-Za-z0-9._/-]+"
    r"|(?i:CLAUDE\.md\s+(?:ch\.|chapter|section)\s*\d+)"
)
# A bare-prose "scripts/PATH" mention (issue #192, Refs #26 repair 3/#36
# repair 3/#20 item d). Deliberately NOT folded into REPO_PATH_CITATION_RE's
# alternation above: unlike evals/ or docs/, a "scripts/..." path routinely
# DOES legitimately resolve inside the citing skill's own directory (every
# skill's SKILL.md refers to its own bundled script this way -- confirmed
# by a corpus-wide check before adding this pattern), so this citation kind
# needs its own directory-resolution check
# (_out_of_skill_scripts_offenders), not the evals/docs family's
# unconditional-flag-or-hedge treatment. Only the bare-prose form is
# checked here: the Markdown-link form of the identical "must resolve
# inside the skill's own directory" rule is already covered by
# links-inside-skill/_out_of_skill_link_targets above. The leading ``\b``
# (a review finding) keeps this from matching inside an unrelated word
# that merely ends in "scripts" (e.g. "manuscripts/genX.py",
# "postscripts/cleanup.sh") -- unlike REPO_PATH_CITATION_RE's evals/docs
# alternative, which only gates presence and is harmless without one,
# this pattern drives an existence check, so a mid-word false match would
# produce a wrong verdict rather than a merely-imprecise offender string.
SCRIPTS_PATH_BARE_RE = re.compile(r"\bscripts/[A-Za-z0-9._/-]+")
# A real, versioned Claude model identifier: "claude-" plus a known
# model-family word (opus/sonnet/haiku/fable/instant) plus a version-like
# digit, e.g. "claude-sonnet-5", "claude-opus-4.7",
# "claude-haiku-4-5-20251001". Deliberately narrower than
# outward-artifact-preflight/scripts/gitapex_scan_provenance.py's bare
# "claude-[a-z0-9.-]+" match (a different check, scanning outgoing artifact
# text for undisclosed disclosure -- a different false-positive budget):
# requiring a family word immediately after "claude-" excludes this
# repository's own legitimate non-model tokens already in skills/ content
# today, e.g. "claude-code", "claude-plugin", or a descriptive title like
# "claude-fable-finding-your-unknowns" (starts with a family word but has no
# version digit after it) -- none of these name an actual model. A
# placeholder like "claude-example-model" never matches either, since
# "example" is not a recognized family word.
ILLUSTRATIVE_MODEL_ID_RE = re.compile(
    r"\bclaude-(?:opus|sonnet|haiku|fable|instant)-?[0-9][a-z0-9.\-]*\b", re.IGNORECASE
)
# A citation to Anthropic's own documentation, in the exact forms this
# repository's own reference lists use: a GFM autolink
# ("<https://platform.claude.com/...>"), an inline link target, with or
# without CommonMark's optional title
# ("[text](https://code.claude.com/... \"Title\")"), or a reference-style
# link definition ("[label]: https://claude.com/..."). A real, current model
# identifier appearing only inside one of these -- e.g. a doc URL whose own
# slug names the model the page documents -- is a primary-source citation,
# not "illustrative content" in rule 1's sense (a worked example or sample
# value a reader might copy-paste); rule 1's own found-via incident (a
# worked example's flagged "bad" sample) never involved a citation URL.
# Narrowly scoped to the three Anthropic-owned domains this rubric's own
# Stop boundaries already name as primary sources (platform.claude.com,
# code.claude.com) plus claude.com (the blog domain [steering]/[fable]/
# [modeleffort] already cite), so this exemption cannot become a general
# escape hatch for illustrative content wrapped in an arbitrary URL.
ANTHROPIC_DOC_CITATION_RE = re.compile(
    r"<https://(?:platform\.claude\.com|code\.claude\.com|claude\.com)/"
    r"[^\s>]*>"
    r"|\]\(https://(?:platform\.claude\.com|code\.claude\.com|claude\.com)/"
    r"[^)\s]*(?:\s+\"[^\"]*\"|\s+'[^']*')?\)"
    r"|^[ ]{0,3}\[[^\]]+\]:\s*<?https://"
    r"(?:platform\.claude\.com|code\.claude\.com|claude\.com)/[^\s>]*>?",
    re.MULTILINE,
)
# An opening angle-bracket placeholder token in raw prose: "<" then a single
# word of letters/digits/underscore/hyphen (no "/" or ":"), then ">". The
# no-"/"-or-":" restriction means a GFM autolink ("<https://example.com>")
# can never match -- that syntax is already a real, safe Markdown form, not
# the defect this check exists to catch.
RAW_PLACEHOLDER_OPEN_RE = re.compile(r"<([A-Za-z][A-Za-z0-9_-]*)>")
# A run of Markdown "already illustrative / already external" syntax whose
# contents must not be scanned: a fenced code block (``` ... ```), an inline
# code span (`...`), an absolute URL, an inline link ([text](target)), a
# reference-style link ([text][label]), or a reference definition
# ([label]: target). Stripping these leaves only bare prose.
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
# A Markdown inline code span: a run of 1-3 backticks, non-greedy content,
# then a closing run of the SAME length (\1) -- CommonMark's own rule, used
# e.g. when the span's content itself needs to contain a literal backtick
# (` ``a`b`` `). A span using two backticks each side (` ``#42`` `) must be
# read as one citation, not two adjacent empty single-backtick spans --
# otherwise its content is never inspected by either citation check below,
# a silent evasion route, not just a cosmetic gap. Capped at 3 backticks
# (this file already reserves
# exactly 3 for FENCE_RE's own fenced-block markers, handled separately
# per-line by ``_blank_fenced_blocks`` before this regex ever runs on that
# line) rather than an unbounded ``+``, since this checker is deliberately a
# practical approximation of CommonMark, not a full parser.
INLINE_CODE_RE = re.compile(r"(`{1,3})(?!`)(.+?)(?<!`)\1(?!`)")
BARE_URL_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s>)\]]+")
MD_INLINE_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
MD_REF_LINK_RE = re.compile(r"\[[^\]]*\]\[[^\]]*\]")
MD_REF_DEF_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s.*$")

# Approved hedge phrases for the inline-code repo-path citation check (see
# the module docstring's repo-path citation entry above). Matched case-insensitively as a
# plain substring, not a word-boundary regex, so a longer phrase already in
# use (e.g. "this repository's own", "this repository has also") is covered
# by the shorter "this repository" entry without a separate one per variant.
# "this repository" / "gitapex" mark a citation as a deliberate, known-real
# reference to this repository's own file; "the calling repository" / "the
# target repository" mark the opposite -- a generic illustrative path name
# for whatever repository the skill lands in or reviews. Both directions are
# already this repository's own established phrasing (rubric.md, worked-
# example-explaining-the-work.md, establishing-ubiquitous-language), not
# invented for this check.
HEDGE_PHRASES = (
    "this repository",
    "the calling repository",
    "the target repository",
    "gitapex",
)

# The generic-placeholder half of HEDGE_PHRASES only (issue #1051's own
# refinement): "the calling repository" / "the target repository" mark a
# citation as a generic illustrative path name for WHATEVER repository the
# skill lands in or reviews -- not a citation to this origin repository's
# own real file at all, so there is no vendoring-breaks-it dependency to
# disclose in the first place. "this repository" / "gitapex" mark the
# opposite: a deliberate, known-real reference to this repository's own
# file -- exactly the #220 failure shape (a hedge phrase that *discloses* a
# real dependency without *removing* it) issue #1051 closed by making the
# repo-path check unconditional. Only the generic-placeholder half still
# rescues a match here; the real-reference half never did and still does
# not. See the module docstring's repo-path citation entry and rubric.md's
# Portability level section (the control-dependency vs. input-source vs.
# output-destination distinction) for the underlying rationale.
GENERIC_ROLE_HEDGE_PHRASES = (
    "the calling repository",
    "the target repository",
)

# Approved hedge phrases for the inline-code issue/PR-number citation check
# (see the module docstring's issue-number citation entry above). Deliberately a separate,
# narrower list from HEDGE_PHRASES: that list marks a repo-*path* citation as
# a deliberate reference to a real (or explicitly generic) repository; this
# one marks an issue-*number* citation as a rule/syntax illustration rather
# than worked-example bookkeeping -- different questions, so a shared phrase
# list would blur both.
# Deliberately full multi-word phrases, not bare words, matching HEDGE_PHRASES'
# own convention: a bare word such as "anchored" or "citation" is not enough --
# an ordinary sentence like "See the citation in PR `#144` for prior art" or
# "the review is anchored to PR `#88`" contains either bare word while citing
# a real, banned issue number, the exact defect this check exists to catch.
# Full phrases collapse that false-negative surface close to zero without
# adding new mechanism.
# "must be an anchored" is this repository's own established way of
# introducing a trackingIssue field's *shape* (`trackingIssue` must be an
# anchored `#123` or `owner/repo#123` reference) rather than citing a
# specific issue as content -- see evaluating-skill-quality's own SKILL.md
# and rubric.md trackingIssue documentation, verbatim in both.
# "issue/pr-number citation" (matched case-insensitively, like every other
# entry here) catches this skill's own, distinct self-referential case: this
# very shape check's rule stated in prose (e.g. "A bare GitHub issue/PR-
# number citation (#149, owner/repo#149) is barred ..."), the same way the
# module docstring above states it, just duplicated for the model reader.
# Both of the above are this repository's own already-established phrasing,
# not invented for this check.
#
# "hex color" / "css color" are different in kind from the two phrases
# above: a pre-emptive escape hatch for a known, unresolved limitation
# rather than a hedge drawn from existing in-repo prose --
# ISSUE_CITATION_RE (`#\d+`) cannot syntactically distinguish a real issue
# number from a decimal-digit-only CSS hex color (`#123456`, `#123`,
# `#000000` are all valid CSS, all also valid GitHub issue-number shapes).
# This repository has no web-design skill yet, but a future
# one documenting a literal color value would hit this false positive with
# no natural way to phrase around it otherwise. Naming the color's own
# nature ("the hex color `#123456`", "this CSS color") is how such a skill
# would phrase it anyway, so the escape hatch costs no awkward wording.
# Reserved in advance of that skill landing, not drawn from existing
# content the way the two phrases above are. Does not replace the deeper,
# still-open fix of context-aware classification instead of
# a hedge word.
ISSUE_CITATION_HEDGE_PHRASES = (
    "must be an anchored",
    "issue/pr-number citation",
    "hex color",
    "css color",
)

# A possessive citation of a named sibling skill -- e.g.
# "`scorer-gated-skill-edits`' own fixture-authoring guidance already
# names X for a pure substring scorer". Matches either
# "`name`'s" (a name not already ending in "s") or the bare-apostrophe
# English possessive "`name`'" (a name that already ends in "s", e.g.
# "scorer-gated-skill-edits'"). ``clause`` captures the text up to the
# next sentence/clause boundary (an approximation, same tolerance this
# file's own _SENTENCE_SPLIT_RE-based tokenizer elsewhere accepts, not a
# full parser) for the caller to search for "already" and an approved
# hedge phrase.
#
# Deliberately narrower than "any backtick-quoted resolving skill name" --
# an unscoped "any resolving citation, no hedge" rule fires on eleven of
# this repository's own already-shipped skills -- the possessive-citation
# shape alone ("`NAME`'s own X") is this repository's single most common,
# entirely benign way to cite a sibling skill's content, used dozens of
# times across nearly every skill. Requiring "already" in the same clause
# reduces that same corpus-wide scan to zero real false positives (three
# residual hits were all inside Repository-scoped/Mixed skills this
# check's own Portable gate already excludes). This narrowness is a
# deliberate, evidence-grounded trade-off, not an oversight: it will not
# catch a differently-worded unhedged fact-claim that never uses the word
# "already".
#
# A trailing ``\b`` word-boundary assertion (the usual way this file marks
# "end of token" elsewhere) does NOT work after the bare-apostrophe form:
# at the position right after a lone ``'`` with no ``s`` following, both
# the apostrophe itself and the whitespace after it are non-word
# characters, so no word/non-word transition exists there for ``\b`` to
# match, and the bare-apostrophe form (a name already ending in "s", e.g.
# "scorer-gated-skill-edits'") would never match at all. A negative
# lookahead for a word character is used instead (matches whitespace,
# punctuation, or end of string, but never a further letter/digit
# continuing the possessive itself) rather than ``(?=\s)`` (requires
# whitespace specifically): a citation immediately followed by
# punctuation before further prose (e.g. "`name`', already noted, ...")
# has a comma, not whitespace, right after the possessive, and
# ``(?=\s)`` would silently never match that either.
PORTABLE_SKILL_FACT_CLAIM_RE = re.compile(
    r"`([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)`'s?(?![A-Za-z0-9])"
    r"(?P<clause>[^.;\n]{0,120})"
)

# Issue #192 (Refs #93 repair 1): a "step N" / "steps N-M" reference,
# case-insensitive (this repo's own SKILL.md files use both "Step 1" and
# "step 5"). Deliberately does not attempt to parse "and"/comma-joined
# multi-step lists (e.g. "Steps 1-2 and 5-7") into every individual number
# they name -- a lower-precision, whole-match extraction is enough for the
# same-number-two-locations contradiction this check exists to catch, and
# a false negative here (an uncaught multi-step list) is far cheaper than
# a hand-rolled list grammar earning its own false positives.
# The \u2013 in the character class below is an EN DASH, written as an escape
# rather than as a literal. The character is load-bearing -- SKILL.md prose
# writes both "Steps 1-2" and "Steps 1\u20132" -- and an escape says so, where a
# literal en dash is visually indistinguishable from the hyphen beside it.
STEP_NUM_RE = re.compile(r"\bsteps?\s+(\d+)(?:\s*[-\u2013]\s*\d+)?\b", re.IGNORECASE)
# A closed, narrow vocabulary of execution-location assertions, grounded in
# the exact wording of the historical incident this check mechanizes
# (issue #93: SKILL.md's Procedure intro said step 6 "stays in the main
# thread" while its Subagent dispatch section required step 6 to "execute
# inside" the dispatch -- an internal contradiction with no location
# explicitly ceding authority to the other). Deliberately not a general
# "location" or "environment" prose linter -- this repo's own real-world
# location-shaped phrasing is otherwise sparse (a corpus-wide check while
# designing this rule found only two hits total, both hedged/unrelated),
# so a broader vocabulary would have no evidence base and a much larger
# false-positive surface. Captures up to 3 further whitespace-separated
# tokens after the verb phrase (deliberately short, not the rest of the
# sentence) so the offender text names WHERE ("the main thread", "the ...
# dispatch") without also absorbing unrelated trailing prose that would
# make two mentions of the exact same location read as "distinct" purely
# because of what was said afterward in one sentence but not the other.
STEP_LOCATION_ASSERTION_RE = re.compile(
    r"\b(?:stays?\s+in|runs?\s+(?:inside|in)|executes?\s+(?:inside|in))"
    r"\b(?:\s+\S+){0,3}",
    re.IGNORECASE,
)
# This repo's own established way (issue #93's own fix commit) of marking
# that one location's statement is authoritative and a second, differently
# located mention of the same step is not a real contradiction -- e.g. "see
# the Subagent dispatch section for the authoritative statement." Matched
# as a case-insensitive substring, the same convention HEDGE_PHRASES and
# ISSUE_CITATION_HEDGE_PHRASES already use.
STEP_LOCATION_CEDING_PHRASE = "authoritative"


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    rule: str
    evidence: str


@dataclass(frozen=True)
class FrontmatterParse:
    """Result of ``_parse_frontmatter``: the parsed top-level scalar fields,
    plus which of them were written as an unquoted YAML plain scalar rather
    than quoted or a block scalar (``>``/``|``).

    Only a plain scalar is at risk of the ": "/trailing ":"/" #" hazard
    ``_yaml_plain_scalar_safety_check`` exists to catch -- a quoted or
    block-scalar value is already safe under a real YAML parser regardless
    of what characters it contains, so a caller needs to know which form a
    field actually used, not just its already-unquoted/already-joined
    value in ``fields``.
    """

    fields: dict[str, str]
    plain_fields: frozenset[str]


def _parse_frontmatter(text: str) -> FrontmatterParse:
    """Extract top-level 'key: value' pairs from a leading --- block.

    Handles the scalar forms real SKILL.md files use: plain, single/double
    quoted, and YAML block scalars (folded '>' and literal '|', whose
    indented continuation lines are joined). Strips a leading UTF-8 BOM and
    requires a closing '---'; without one the frontmatter is treated as
    malformed (returns an empty result), rather than reading body lines as
    fields. No external YAML dependency.
    """
    text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        return FrontmatterParse(fields={}, plain_fields=frozenset())
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return FrontmatterParse(fields={}, plain_fields=frozenset())
    fields: dict[str, str] = {}
    plain_fields: set[str] = set()
    i = 1
    while i < end:
        m = re.match(r"([A-Za-z0-9_-]+):\s*(.*)$", lines[i])
        if not m:
            i += 1
            continue
        key, value = m.group(1), m.group(2).strip()
        if value in BLOCK_SCALAR_INDICATORS:
            block: list[str] = []
            i += 1
            while i < end and (lines[i].strip() == "" or lines[i][:1] in (" ", "\t")):
                block.append(lines[i].strip())
                i += 1
            joiner = "\n" if value[0] == "|" else " "
            fields[key] = joiner.join(block).strip()
            continue
        is_quoted = len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'"
        fields[key] = _unquote(value)
        if not is_quoted:
            plain_fields.add(key)
        i += 1
    return FrontmatterParse(fields=fields, plain_fields=frozenset(plain_fields))


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        if value[0] == '"':
            # A double-quoted YAML scalar's escaping is a superset-safe
            # match for JSON string escaping (this repository's own
            # sidecar-generation method deliberately relies on that: see
            # the design plan's Task 1, which builds these values with
            # json.dumps). Decoding via the stdlib json module handles
            # every escape a generator might emit (\", \\, \n, \uXXXX, ...).
            # Fall back to a naive strip on decode failure (e.g. a stray
            # unescaped literal quote) rather than raising -- this parser
            # never raises on malformed sidecar content.
            try:
                decoded = json.loads(value)
            except ValueError:
                decoded = None
            if isinstance(decoded, str):
                return decoded
        return value[1:-1]
    return value


def _strip_bare_comment(value: str) -> str:
    """Return ``value`` unchanged, unless it is an UNQUOTED value that
    starts with ``#`` -- real YAML never allows an unquoted scalar to
    start with ``#`` (that always opens a comment, making the actual
    value null/absent), so such a ``value`` must read as empty here too.

    This parser otherwise deliberately does not strip inline comments
    (see ``_parse_manifest``'s docstring: trailing ``# comment`` text
    after a real value is read as part of that value, "safe" because it
    fails closed against the expected enum/literal). That reasoning does
    NOT hold when the field's own valid shape can itself start with
    ``#`` -- e.g. ``spec.lifecycle.experimental.trackingIssue: #123``
    (unquoted) is real YAML for "trackingIssue is null", not the literal
    string ``"#123"``, yet ``"#123"`` is exactly this field's valid
    shape, so the old fails-closed argument fails open here instead.
    Used only by the three ``spec.lifecycle`` value-extraction sites
    (block-open decision, leaf fields, ``renamedFrom``) -- not applied
    to every other sidecar scalar, since none of their valid shapes start
    with ``#`` the way an issue reference does, and rewriting the whole
    parser's comment handling is a larger, separate change than this
    field's specific collision.
    """
    return "" if value.startswith("#") else value


def _match_key_line(pattern: re.Pattern[str], line: str) -> tuple[str, str] | None:
    """Match ``line`` against ``pattern`` (``KEY_LINE_RE_4`` or
    ``KEY_LINE_RE_6``). Returns ``(key, value)`` with the key already
    unquoted (a quoted key's own quote characters are never part of the
    key name) and the value right-stripped, or ``None`` if ``line`` is not
    a key-shaped line at that indent. The one shared recognition site
    every gated block's key handling uses -- callers decide
    "recognized vs. unknown" themselves via membership in their own set of
    valid names; this function only decides "is this syntactically a key
    at all," so an unrecognized key can never again bypass detection by
    virtue of being quoted or containing a character a narrower per-field
    regex did not anticipate.
    """
    m = pattern.match(line)
    if not m:
        return None
    key = m.group(1) if m.group(1) is not None else (m.group(2) if m.group(2) is not None else m.group(3))
    return key, m.group(4).strip()


@dataclass(frozen=True)
class ManifestParse:
    """Result of ``_parse_manifest``: the parsed top-level mapping plus any
    malformed top-level lines found alongside it.

    ``malformed_lines`` holds each offending line (trimmed), in file order --
    empty when the sidecar's top-level structure is clean. See
    ``_parse_manifest`` for the exact malformed-line rule.

    ``malformed_reference_items`` holds each spec.references list item's
    own opening line (trimmed) that could not be read as a well-formed
    item mapping -- an indent inconsistent with the rest of its own list,
    an opening line not shaped like "<key>: <value>" at all (e.g. the
    plain-scalar or pipe-delimited-string shapes this field used before),
    an opening key outside REFERENCES_ITEM_SUBKEYS, or an otherwise
    well-opened item missing one of REFERENCES_ITEM_REQUIRED_SUBKEYS
    (``kind``/``anchor``/``summary``) by the time it closes. Empty when
    every item in every spec.references list parsed cleanly. Unlike
    ``malformed_lines``, these are indented lines; they would otherwise be
    silently skipped by this parser's own "indented lines are never
    malformed" rule, which is why they need this separate, explicit
    channel rather than reusing ``malformed_lines``.

    ``unknown_reference_item_keys`` holds each key found inside an
    otherwise-well-opened spec.references item that is not one of
    REFERENCES_ITEM_SUBKEYS (trimmed line, e.g. "notes: foo") -- the
    item's other recognized fields still parse normally; only the stray
    key itself is flagged, the same asymmetry
    ``unknown_lifecycle_fields``/``unknown_skill_dependency_keys`` already
    use for their own sibling fields.

    ``malformed_skill_dependency_items`` and ``unknown_skill_dependency_keys``
    are spec.skillDependencies' equivalents: the former holds each
    requires/relatedTo list item that is mapping-shaped or inconsistently
    indented (same rule as ``malformed_reference_items``, one nesting level
    deeper); the latter holds each key found directly under
    spec.skillDependencies that is not ``requires`` or ``relatedTo``
    (trimmed line, e.g. "extra: foo"). Both empty when the field is absent
    or parsed cleanly.

    ``unknown_lifecycle_keys`` and ``unknown_lifecycle_fields`` are
    spec.lifecycle's equivalents, one nesting level deeper again:
    ``unknown_lifecycle_keys`` holds each key found directly under
    spec.lifecycle that is not ``experimental``, ``deprecated``,
    ``stable``, or ``renamedFrom`` (trimmed line); ``unknown_lifecycle_fields``
    holds each key found inside any of the three block sub-keys
    (``experimental``/``deprecated``/``stable``) that is not one of its
    own recognized fields (e.g. "extra: foo" under experimental). Both
    empty when the field is absent or parsed cleanly. There is no
    malformed-item channel for spec.lifecycle the way
    spec.references/spec.skillDependencies have one for list items --
    every leaf under spec.lifecycle is a plain scalar, so a wrong-type
    value is simply stored as the raw string by the field parser and
    fails the downstream well-formed check on shape, with nothing that
    needs a separate parse-time detection channel.

    ``unknown_execution_requirement_keys``, ``unknown_execution_requirement_tools_keys``,
    and ``malformed_execution_requirement_tools_items`` are
    spec.executionRequirements' equivalents: the first holds each key found directly under
    spec.executionRequirements that is not ``tools``, ``packages``, or
    ``network`` (only three recognized keys exist so far -- further
    categories are deferred to sibling child issues, and any other key
    here is unknown, not reserved space); the second holds each key found
    directly under ``tools`` that is not ``read``, ``write``, or
    ``shell``; the third holds each
    read/write/shell list item that is mapping-shaped or inconsistently
    indented, the same rule ``malformed_reference_items``/
    ``malformed_skill_dependency_items`` use one nesting level shallower.
    All three empty when the field is absent or parsed cleanly.

    ``unknown_execution_requirement_network_keys`` and
    ``malformed_execution_requirement_network_items`` are ``network``'s own
    equivalents to ``unknown_execution_requirement_tools_keys``/
    ``malformed_execution_requirement_tools_items``: the first holds each
    key found directly under ``network`` that is not ``mode`` or
    ``domains``; the second holds each ``domains`` list item that is
    mapping-shaped or inconsistently indented. Both empty when the field
    is absent or parsed cleanly.

    ``unknown_execution_requirement_packages_keys`` and
    ``malformed_execution_requirement_packages_items`` are ``packages``'s
    own equivalents, differing from ``tools``'/``network``'s in HOW both
    are populated: since ``packages``' own subkeys are free-form
    ecosystem identifiers rather than a fixed tuple (see
    EXEC_REQ_PACKAGES_KEY_RE), the first holds each key found directly
    under ``packages`` that does NOT match EXEC_REQ_PACKAGES_KEY_RE's own
    pattern (a regex mismatch, not a tuple-membership miss); the second
    holds each per-ecosystem list item that is mapping-shaped or
    inconsistently indented, the same rule every other malformed-item
    channel above uses, PLUS one packages-only addition
    (EXEC_REQ_PACKAGES_MISINDENTED_ITEM_RE, see its own comment): a line
    that looks like an attempted "- <value>" item (a "-" as its first
    non-whitespace character) but whose leading whitespace fails the
    strict list-item regex's own "6 or more literal spaces" requirement
    -- a tab, or fewer than 6 spaces -- is ALSO recorded here rather than
    silently finalizing the list as empty, indistinguishable from the
    package never having been declared at all. tools'/network's own
    sibling list-item blocks do not have this addition; see
    EXEC_REQ_PACKAGES_MISINDENTED_ITEM_RE's own comment for why that gap
    is deliberately left as-is there. Both empty when the field is absent
    or parsed cleanly.

    ``malformed_external_citation_items`` and
    ``unknown_external_citation_item_keys`` are spec.externalCitations'
    equivalents to ``malformed_reference_items``/
    ``unknown_reference_item_keys`` (issue #1055): the former holds each
    externalCitations list item's own opening line (trimmed) that could
    not be read as a well-formed item mapping (bad indent, not "<key>:
    <value>" shaped, an opening key outside EXTERNAL_CITATION_ITEM_SUBKEYS,
    or missing ``path``/``role`` by the time it closes); the latter holds
    each key found inside an otherwise-well-opened item that is not
    ``path``/``role``. Both empty when the field is absent or parsed
    cleanly.
    """

    root: dict[str, object]
    malformed_lines: list[str]
    malformed_reference_items: list[str]
    unknown_reference_item_keys: list[str]
    malformed_skill_dependency_items: list[str]
    unknown_skill_dependency_keys: list[str]
    unknown_lifecycle_keys: list[str]
    unknown_lifecycle_fields: list[str]
    unknown_execution_requirement_keys: list[str]
    unknown_execution_requirement_tools_keys: list[str]
    malformed_execution_requirement_tools_items: list[str]
    unknown_execution_requirement_packages_keys: list[str]
    malformed_execution_requirement_packages_items: list[str]
    unknown_execution_requirement_network_keys: list[str]
    malformed_execution_requirement_network_items: list[str]
    malformed_external_citation_items: list[str]
    unknown_external_citation_item_keys: list[str]


def _parse_manifest(text: str) -> ManifestParse:
    """Parse the YAML subset the metadata sidecar is specified to use.

    Reads top-level 'key: value' scalars and exactly-two-space-indented
    scalars under a top-level map (metadata:, spec:). Two exceptions:

    - spec.references (and only that key, and only directly under spec) is
      read as a list whose items are themselves mappings -- one
      maintainer-facing provenance event each (see the design spec's
      Sub-project C and its issue #488 follow-up). Each item opens with a
      "- <key>: <value>" line (its first field given inline right after
      the dash) at exactly 4-space indent, with further recognized fields
      as "<key>: <value>" continuation lines at exactly 6-space indent --
      one level deeper, matching every other gated block's own indent-
      doubling convention. Recognized keys: ``kind`` (required, a closed
      vocabulary -- REFERENCES_KIND_VOCAB), ``anchor`` (required, the
      provenance source), ``summary`` (required, free prose), and
      ``outcome`` (optional, itself an empty-value key opening a further
      nested mapping of free-form key/value atoms at 8-space indent --
      KEY_LINE_RE_8 -- with no closed vocabulary of its own). A key inside
      an item other than these four is collected into
      ``ManifestParse.unknown_reference_item_keys`` instead of being
      silently skipped, the same reasoning
      ``unknown_skill_dependency_keys`` documents below; an item whose own
      opening line is not "<key>: <value>" shaped at all, opens with an
      unrecognized key, is indented inconsistently with the rest of its
      own list, or is missing one of the three required keys by the time
      it closes is collected (its opening line, trimmed) into
      ``ManifestParse.malformed_reference_items`` and excluded from the
      parsed list entirely, rather than kept as a partial or garbled item.
    - spec.skillDependencies (and only that key, and only directly under
      spec) is read as a mapping with exactly two recognized subkeys,
      ``requires`` and ``relatedTo`` (see the design spec's Sub-project D).
      Each subkey, at exactly 4-space indent, is either an inline empty
      list (``requires: []``) or an empty value opening a block list of
      "- <value>" items at 4 or more spaces indent -- the same depth as
      the subkey's own line, or deeper, with the same per-item shape rules
      (mapping-like-item and indent-consistency detection) and the same
      indent-drift tolerance as spec.references' items. A key inside
      spec.skillDependencies other than ``requires``/``relatedTo`` is
      collected into ``ManifestParse.unknown_skill_dependency_keys``
      instead of being silently skipped, since an unrecognized key here is
      a real shape defect the checker is expected to catch, not reserved
      space. Every gated block's key recognition (this one, spec.lifecycle's
      below, and any future one) shares one key-line matcher,
      ``_match_key_line`` over ``KEY_LINE_RE_4``/``KEY_LINE_RE_6`` --
      it recognizes a bare OR quoted YAML key as A key regardless of its
      characters, leaving "recognized vs. unknown" entirely to the
      caller's own membership check. A narrower, name-specific regex used
      to do both jobs at once (matching only the recognized names, with a
      separate ``[A-Za-z0-9_-]+`` catch-all for everything else); a quoted
      key (``"extra": foo``) or a key containing a character outside that
      narrow class matched neither regex and fell through both into the
      "stray content, skip silently" branch instead of ever reaching
      unknown-key detection (issue #356).
    - spec.lifecycle (and only that key, and only directly under spec) is
      read as a mapping with exactly three recognized block sub-keys --
      ``experimental``, ``deprecated``, ``stable`` -- plus one recognized
      plain scalar key, ``renamedFrom``. Each block sub-key, at exactly
      4-space indent, is an empty value opening a nested block of scalar
      fields at exactly 6-space indent (``reason``/``trackingIssue``/
      ``since`` for ``experimental``; ``reason``/``replacement``/
      ``since``/``removeAfter`` for ``deprecated``; ``since``/
      ``compatibilityGuarantee`` for ``stable``). ``renamedFrom``, also
      at 4-space indent, takes an inline scalar value directly instead of
      opening a block -- structurally like ``metadata.name`` under
      ``metadata:``, not like the other three. One nesting level deeper
      than spec.skillDependencies, but with scalar leaves instead of a
      list -- there is no list-item shape inside spec.lifecycle at all. A
      key directly under spec.lifecycle other than one of these four is
      collected into ``ManifestParse.unknown_lifecycle_keys``; a key
      inside any of the three block sub-keys that is not one of its own
      recognized fields is collected into
      ``ManifestParse.unknown_lifecycle_fields`` -- both instead of being
      silently skipped, for the same reason
      ``unknown_skill_dependency_keys`` exists. A block sub-key header
      written as an inline scalar instead of opening a block (e.g.
      ``experimental: true``) is stored as that raw scalar under its own
      key, exactly as spec.skillDependencies' non-list scalar fallback
      works, so the checker layer reports it as the wrong type rather
      than silently dropping it -- and symmetrically, ``renamedFrom``
      given a block instead of a scalar (e.g. nested children under
      ``renamedFrom:``) is detected one line later (see
      ``lifecycle_scalar_pending`` in the parsing loop below) and stored
      as an empty mapping, so it fails the same way in reverse.
    - spec.executionRequirements (and only that key, and only directly
      under spec) is read as a mapping with exactly one recognized
      block sub-key so far, ``tools`` (issue #349, #307 Workstream W1
      first slice -- further categories are deferred to sibling child
      issues). ``tools``, at exactly 4-space indent, is an empty value
      opening a nested block of list-of-scalars fields at exactly
      6-space indent: ``read``/``write``/``shell``, each either an
      inline empty list (``read: []``) or an empty value opening a
      block list of "- <value>" items at 6 or more spaces indent -- the
      same per-item shape rules and indent-drift tolerance
      spec.skillDependencies' requires/relatedTo already use, one
      nesting level deeper. A key directly under
      spec.executionRequirements other than ``tools`` is collected into
      ``ManifestParse.unknown_execution_requirement_keys``; a key inside
      ``tools`` other than ``read``/``write``/``shell`` is collected into
      ``ManifestParse.unknown_execution_requirement_tools_keys`` -- both
      instead of being silently skipped, for the same reason
      ``unknown_skill_dependency_keys`` exists. A malformed (mapping-shaped
      or inconsistently indented) list item under any of the three tools
      subkeys is collected into
      ``ManifestParse.malformed_execution_requirement_tools_items``.
    - spec.executionRequirements' second recognized block sub-key (issue
      #845): ``network``, structurally parallel to ``tools`` above -- also
      an empty value opening a nested block at 6-space indent, also
      finalizing to real YAML null when its own header sees zero child
      key lines. Its own two subkeys, ``mode``/``domains``, are each
      captured the identical way tools' own read/write/shell are: an
      inline non-blank value is stored as a raw scalar (``mode``'s normal,
      valid case: ``mode: disabled``); a blank value opens a list of
      "- <value>" items at 6-or-more-space indent, reusing
      ``EXEC_REQ_TOOLS_LIST_ITEM_RE`` verbatim (``domains``'s normal, valid
      case). The parser draws no distinction between the two subkeys --
      whether a stored value is the "right" shape for its own key (mode as
      a scalar, domains as a list) is left entirely to
      ``_execution_requirements_checks``, exactly as it already is for
      tools' own three list-only subkeys. A key inside ``network`` other
      than ``mode``/``domains`` is collected into
      ``ManifestParse.unknown_execution_requirement_network_keys``; a
      malformed ``domains`` list item is collected into
      ``ManifestParse.malformed_execution_requirement_network_items``.
    - spec.executionRequirements' third recognized block sub-key:
      ``packages``, also an empty value opening a nested block at 6-space
      indent, also finalizing to real YAML null when its own header sees
      zero child key lines -- but unlike ``tools``' fixed
      read/write/shell and ``network``'s fixed mode/domains, ``packages``'
      own subkeys are free-form ecosystem identifiers (``pip``, ``npm``,
      ...) matching ``EXEC_REQ_PACKAGES_KEY_RE``, not a closed tuple,
      mirroring skill-metadata.schema.json's own
      executionRequirementsPackages.propertyNames pattern (no closed enum
      of supported ecosystems, so a future ecosystem needs no parser
      change to become recognized). Each ecosystem key matching that
      pattern is captured the same way tools' own read/write/shell are:
      an inline non-blank value is stored as a raw scalar (the wrong
      shape for a package list, caught downstream by
      ``_execution_requirements_checks``); a blank value opens a list of
      "- <value>" items at 6-or-more-space indent, reusing
      ``EXEC_REQ_TOOLS_LIST_ITEM_RE`` verbatim (the same depth-reuse
      ``domains`` above already established -- an ecosystem key sits at
      the identical 6-space depth tools' own read/write/shell and
      network's mode/domains do). A key under ``packages`` NOT matching
      ``EXEC_REQ_PACKAGES_KEY_RE`` is collected into
      ``ManifestParse.unknown_execution_requirement_packages_keys``
      instead of being silently skipped; a malformed per-ecosystem list
      item is collected into
      ``ManifestParse.malformed_execution_requirement_packages_items``.

    Every other nested map or list (e.g. spec.evalStatus) is still
    deliberately skipped, exactly as before: skipping keeps this
    stdlib-only with no YAML dependency. Inline '# comment' text after a
    value on the same line is not stripped -- it is read as part of the
    value, which is safe (fails closed against the expected enum/literal)
    but is not a supported way to annotate a sidecar field. Exception:
    every gated-block-opening site (the top-level ``nested`` dispatch for
    spec.references/skillDependencies/lifecycle/executionRequirements;
    spec.skillDependencies' own requires/relatedTo; spec.lifecycle's
    experimental/deprecated/stable and their own value-extraction sites;
    spec.executionRequirements' own tools; and tools' own
    read/write/shell) strips a value that is NOTHING BUT a comment
    (starts with ``#`` unquoted) down to empty via
    ``_strip_bare_comment`` before deciding whether that value is blank,
    since real YAML never allows an unquoted scalar to start with ``#``
    (it always opens a comment there) -- the general "fails closed"
    reasoning above does not hold when a blank-vs-not decision gates
    whether a whole nested block opens at all: a code-review finding
    caught that ``executionRequirements:  # not yet fully specified``
    (and the equivalent for every other gated block/list-opening key)
    read the comment as a literal, wrong-type scalar value instead of a
    blank one, silently discarding everything nested underneath it
    before this fix. Applies one level deeper too, for the same reason:
    ``experimental.trackingIssue``'s ``#123``/``owner/repo#123`` shape
    means an unquoted ``trackingIssue: #123`` must read as absent, not as
    the literal string ``"#123"`` a quoted value would give.

    A top-level (column-0) line that is not blank, not a '#' comment, not a
    YAML document marker ('---' or '...'), and does not match the top-level
    'key:' pattern is malformed -- e.g. a stray '- invalid mapping entry'
    that real PyYAML would reject with a ParserError. Every such line is
    collected (trimmed) into the returned ``ManifestParse.malformed_lines``,
    so a caller can fail the sidecar even though this permissive parser
    itself does not raise. Indented lines are NEVER considered malformed
    this same way -- every indented line belongs to nested/list structures
    this parser deliberately does not interpret, and flagging them would
    defeat that reserved-field design. spec.references and
    spec.skillDependencies list items are the exceptions with their own
    malformed channels, though the two fields' own item shapes differ
    (references' own items are mappings; skillDependencies.requires/
    relatedTo's are still plain scalar strings): a spec.references item
    not shaped like "<key>: <value>" at all, indented inconsistently with
    the rest of its own list, opening with an unrecognized key, or missing
    a required field by the time it closes is collected (its opening
    line, trimmed) into ``ManifestParse.malformed_reference_items`` (see
    this field's own fuller description above); a
    spec.skillDependencies.requires/relatedTo item shaped like an
    unquoted YAML mapping key ("path: foo", real YAML would read that as
    a nested mapping, not the scalar string this list still expects), one
    indented inconsistently with the rest of its own list, or an unquoted
    null/boolean/numeric scalar (issue #356: real YAML resolves e.g.
    "true"/"123"/"null" to that type, not a string) is collected the same
    way into ``ManifestParse.malformed_skill_dependency_items`` -- both
    instead of being silently accepted as a garbled or wrongly-typed
    value.

    Every gated *mapping*-valued block (spec.skillDependencies,
    spec.lifecycle and its experimental/deprecated/stable sub-blocks,
    spec.executionRequirements, spec.executionRequirements.tools,
    spec.executionRequirements.network) stores
    ``None`` -- real YAML null -- rather than ``{}`` when its own block
    header was seen with zero child key lines ever following it at the
    next indent level (issue #356, ACM row 2): a bare block header
    immediately followed by a dedent is null under any real YAML parser,
    never an empty-but-present mapping, so this parser must not silently
    promote that shape to ``{}`` the way an earlier version of it did. A
    block that does see at least one child key line (however that
    child's own value turns out) still stores a real, non-null ``dict``.
    This null/non-null distinction is orthogonal to whether the key
    appears in its parent dict at all -- a key that never appears means
    "not declared" (the pre-existing, unaffected "absent" state); only a
    key that DOES appear, with nothing under it, newly resolves to
    ``None`` instead of ``{}``. List-valued keys under these same blocks
    (requires/relatedTo, tools.read/write/shell, network.domains) are NOT
    affected by this change -- a blank list header still parses to ``[]``, per each
    field's own pre-existing "explicit empty list" semantics.
    """
    text = text.lstrip("\ufeff")  # strip a leading UTF-8 BOM, as _parse_frontmatter does
    root: dict[str, object] = {}
    current: dict[str, object] | None = None
    collecting_refs: list[dict[str, object]] | None = None
    # The spec.references item mapping currently being read (between its
    # own "- <key>: <value>" opening line and either the next item, a
    # dedent, or end of file); None between items. current_ref_item_valid
    # goes False the moment the item's own opening line or any of its
    # fields turns out malformed, so the item is excluded at finalization
    # even though its now-known-garbage lines are still consumed here
    # (not left to desync the references list's own end-of-block
    # detection). current_ref_open_line is the item's own opening line
    # (trimmed), kept only for evidence messages.
    current_ref_item: dict[str, object] | None = None
    current_ref_item_valid = True
    current_ref_open_line = ""
    # Non-None while inside that item's own optional "outcome:" nested
    # mapping (one level deeper still -- see KEY_LINE_RE_8).
    current_ref_outcome: dict[str, object] | None = None
    malformed: list[str] = []
    malformed_refs: list[str] = []
    unknown_ref_item_keys: list[str] = []
    # spec.externalCitations' own state, structurally parallel to
    # spec.references' above but simpler -- each item is a flat two-field
    # mapping (path/role) with no nested "outcome" sub-block.
    collecting_ext_citations: list[dict[str, object]] | None = None
    current_ext_citation_item: dict[str, object] | None = None
    current_ext_citation_item_valid = True
    current_ext_citation_open_line = ""
    malformed_ext_citations: list[str] = []
    unknown_ext_citation_item_keys: list[str] = []
    in_skill_deps = False
    skill_deps: dict[str, object] = {}
    # Whether spec.skillDependencies has seen at least one real child line
    # (a recognized or unknown key) since it was opened -- distinguishes a
    # block header left with nothing under it (real YAML null) from one
    # that genuinely has content, however malformed.
    # Mirrored by lifecycle_has_content/lifecycle_subkey_has_content/
    # exec_req_has_content/exec_tools_has_content below, one per gated
    # mapping block.
    skill_deps_has_content = False
    collecting_dep_list: list[str] | None = None
    collecting_dep_key: str | None = None
    dep_list_indent: int | None = None
    malformed_deps: list[str] = []
    unknown_dep_keys: list[str] = []
    in_lifecycle = False
    lifecycle: dict[str, object] = {}
    lifecycle_has_content = False
    lifecycle_subkey: str | None = None
    lifecycle_field_buffer: dict[str, object] = {}
    lifecycle_subkey_has_content = False
    unknown_lifecycle_keys: list[str] = []
    unknown_lifecycle_fields: list[str] = []
    # Set when a scalar-only lifecycle key (currently only renamedFrom) is
    # seen with a blank/comment-only value -- deferred one line, since that
    # shape is ambiguous until the next line is known: it is either a
    # legitimately absent declaration (next line dedents or is a sibling),
    # or the start of a wrongly block-shaped value (next line is more
    # deeply indented than spec.lifecycle's own 4-space level). See the
    # "if lifecycle_scalar_pending is not None:" handling below.
    lifecycle_scalar_pending: str | None = None
    in_execution_requirements = False
    execution_requirements: dict[str, object] = {}
    exec_req_has_content = False
    in_exec_tools = False
    exec_tools: dict[str, object] = {}
    exec_tools_has_content = False
    collecting_exec_tools_list: list[str] | None = None
    collecting_exec_tools_key: str | None = None
    exec_tools_list_indent: int | None = None
    malformed_exec_tools_items: list[str] = []
    unknown_exec_req_keys: list[str] = []
    unknown_exec_tools_keys: list[str] = []
    # packages' own state, structurally parallel to exec_tools' above (see
    # EXEC_REQ_NETWORK_SUBKEYS' own comment for why this is a hand-
    # duplicated analog rather than a shared helper -- a third parallel
    # block here rather than an extraction, same precedent, same
    # regression-risk-vs-scope tradeoff). Unlike exec_tools/exec_network,
    # unknown_exec_packages_keys is populated by a REGEX mismatch
    # (EXEC_REQ_PACKAGES_KEY_RE), not a tuple-membership miss -- see the
    # parsing loop below.
    in_exec_packages = False
    exec_packages: dict[str, object] = {}
    exec_packages_has_content = False
    collecting_exec_packages_list: list[str] | None = None
    collecting_exec_packages_key: str | None = None
    exec_packages_list_indent: int | None = None
    malformed_exec_packages_items: list[str] = []
    unknown_exec_packages_keys: list[str] = []
    # network's own state, structurally parallel to exec_tools' above (see
    # EXEC_REQ_NETWORK_SUBKEYS' own comment for why this is a hand-
    # duplicated analog rather than a shared helper).
    in_exec_network = False
    exec_network: dict[str, object] = {}
    exec_network_has_content = False
    collecting_exec_network_list: list[str] | None = None
    collecting_exec_network_key: str | None = None
    exec_network_list_indent: int | None = None
    malformed_exec_network_items: list[str] = []
    unknown_exec_network_keys: list[str] = []

    def _finalize_ref_outcome() -> None:
        nonlocal current_ref_outcome
        if current_ref_outcome is not None and current_ref_item is not None:
            current_ref_item["outcome"] = current_ref_outcome if current_ref_outcome else None
        current_ref_outcome = None

    def _finalize_current_ref_item() -> None:
        nonlocal current_ref_item, current_ref_item_valid, current_ref_open_line
        _finalize_ref_outcome()
        if current_ref_item is not None:
            missing = [k for k in REFERENCES_ITEM_REQUIRED_SUBKEYS if k not in current_ref_item]
            if current_ref_item_valid and missing:
                joined = ", ".join(missing)
                malformed_refs.append(f"{current_ref_open_line} (missing required field(s): {joined})")
            elif current_ref_item_valid and collecting_refs is not None:
                collecting_refs.append(current_ref_item)
        current_ref_item = None
        current_ref_item_valid = True
        current_ref_open_line = ""

    def _finalize_refs() -> None:
        nonlocal collecting_refs
        _finalize_current_ref_item()
        if collecting_refs is not None and current is not None:
            current["references"] = collecting_refs
        collecting_refs = None

    def _finalize_current_ext_citation_item() -> None:
        nonlocal current_ext_citation_item, current_ext_citation_item_valid, current_ext_citation_open_line
        if current_ext_citation_item is not None:
            missing = [k for k in EXTERNAL_CITATION_ITEM_REQUIRED_SUBKEYS if k not in current_ext_citation_item]
            if current_ext_citation_item_valid and missing:
                joined = ", ".join(missing)
                malformed_ext_citations.append(
                    f"{current_ext_citation_open_line} (missing required field(s): {joined})"
                )
            elif current_ext_citation_item_valid and collecting_ext_citations is not None:
                collecting_ext_citations.append(current_ext_citation_item)
        current_ext_citation_item = None
        current_ext_citation_item_valid = True
        current_ext_citation_open_line = ""

    def _finalize_ext_citations() -> None:
        nonlocal collecting_ext_citations
        _finalize_current_ext_citation_item()
        if collecting_ext_citations is not None and current is not None:
            current["externalCitations"] = collecting_ext_citations
        collecting_ext_citations = None

    def _finalize_dep_list() -> None:
        nonlocal collecting_dep_list, collecting_dep_key, dep_list_indent
        if collecting_dep_list is not None and collecting_dep_key is not None:
            skill_deps[collecting_dep_key] = collecting_dep_list
        collecting_dep_list = None
        collecting_dep_key = None
        dep_list_indent = None

    def _finalize_skill_deps() -> None:
        nonlocal in_skill_deps, skill_deps, skill_deps_has_content
        _finalize_dep_list()
        if in_skill_deps and current is not None:
            # A block header with zero real children ever seen is real
            # YAML null, not an empty-but-present mapping.
            current["skillDependencies"] = skill_deps if skill_deps_has_content else None
        in_skill_deps = False
        skill_deps = {}
        skill_deps_has_content = False

    def _finalize_lifecycle_subkey() -> None:
        nonlocal lifecycle_subkey, lifecycle_field_buffer, lifecycle_subkey_has_content
        if lifecycle_subkey is not None:
            lifecycle[lifecycle_subkey] = lifecycle_field_buffer if lifecycle_subkey_has_content else None
        lifecycle_subkey = None
        lifecycle_field_buffer = {}
        lifecycle_subkey_has_content = False

    def _finalize_lifecycle() -> None:
        nonlocal in_lifecycle, lifecycle, lifecycle_has_content
        _finalize_lifecycle_subkey()
        if in_lifecycle and current is not None:
            current["lifecycle"] = lifecycle if lifecycle_has_content else None
        in_lifecycle = False
        lifecycle = {}
        lifecycle_has_content = False

    def _finalize_exec_tools_list() -> None:
        nonlocal collecting_exec_tools_list, collecting_exec_tools_key, exec_tools_list_indent
        if collecting_exec_tools_list is not None and collecting_exec_tools_key is not None:
            exec_tools[collecting_exec_tools_key] = collecting_exec_tools_list
        collecting_exec_tools_list = None
        collecting_exec_tools_key = None
        exec_tools_list_indent = None

    def _finalize_exec_tools() -> None:
        nonlocal in_exec_tools, exec_tools, exec_tools_has_content
        _finalize_exec_tools_list()
        if in_exec_tools:
            execution_requirements["tools"] = exec_tools if exec_tools_has_content else None
        in_exec_tools = False
        exec_tools = {}
        exec_tools_has_content = False

    def _finalize_exec_packages_list() -> None:
        nonlocal collecting_exec_packages_list, collecting_exec_packages_key, exec_packages_list_indent
        if collecting_exec_packages_list is not None and collecting_exec_packages_key is not None:
            exec_packages[collecting_exec_packages_key] = collecting_exec_packages_list
        collecting_exec_packages_list = None
        collecting_exec_packages_key = None
        exec_packages_list_indent = None

    def _finalize_exec_packages() -> None:
        nonlocal in_exec_packages, exec_packages, exec_packages_has_content
        _finalize_exec_packages_list()
        if in_exec_packages:
            execution_requirements["packages"] = exec_packages if exec_packages_has_content else None
        in_exec_packages = False
        exec_packages = {}
        exec_packages_has_content = False

    def _finalize_exec_network_list() -> None:
        nonlocal collecting_exec_network_list, collecting_exec_network_key, exec_network_list_indent
        if collecting_exec_network_list is not None and collecting_exec_network_key is not None:
            exec_network[collecting_exec_network_key] = collecting_exec_network_list
        collecting_exec_network_list = None
        collecting_exec_network_key = None
        exec_network_list_indent = None

    def _finalize_exec_network() -> None:
        nonlocal in_exec_network, exec_network, exec_network_has_content
        _finalize_exec_network_list()
        if in_exec_network:
            execution_requirements["network"] = exec_network if exec_network_has_content else None
        in_exec_network = False
        exec_network = {}
        exec_network_has_content = False

    def _finalize_execution_requirements() -> None:
        nonlocal in_execution_requirements, execution_requirements, exec_req_has_content
        _finalize_exec_tools()
        _finalize_exec_packages()
        _finalize_exec_network()
        if in_execution_requirements and current is not None:
            current["executionRequirements"] = execution_requirements if exec_req_has_content else None
        in_execution_requirements = False
        execution_requirements = {}
        exec_req_has_content = False

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if collecting_refs is not None:
            item = REFERENCES_LIST_ITEM_RE.match(line)
            if item:
                # A new "- <key>: <value>" item marker always closes
                # whatever item (and its own outcome sub-block, if open)
                # came before it.
                _finalize_current_ref_item()
                item_indent = len(line) - len(line.lstrip(" "))
                raw_text = item.group(1).strip()
                opened = _match_key_line(INLINE_KEY_VALUE_RE, raw_text)
                current_ref_open_line = line.strip()
                if item_indent != REFERENCES_ITEM_INDENT or opened is None or opened[0] not in REFERENCES_ITEM_SUBKEYS:
                    # Wrong indent (exactly 4 spaces required -- one level
                    # under spec.references' own 2-space key, matching
                    # every other gated block's own fixed-indent
                    # convention, not the old bare-scalar-list design's
                    # "2 or more spaces" tolerance), not a "key: value"
                    # shape at all (the old pipe-string/bare-scalar shape
                    # this field used before, or other garbage), or an
                    # unrecognized first
                    # key -- flag the whole item rather than silently
                    # misreading it. Still track it as "an item is open"
                    # so its own (now-known-garbage) continuation lines
                    # are consumed here instead of desyncing this block's
                    # own end-of-list detection.
                    malformed_refs.append(line.strip())
                    current_ref_item = {}
                    current_ref_item_valid = False
                else:
                    key, value = opened
                    current_ref_item = {}
                    current_ref_item_valid = True
                    if value:
                        current_ref_item[key] = _unquote(value)
                continue
            if current_ref_outcome is not None:
                matched = _match_key_line(KEY_LINE_RE_8, line)
                if matched:
                    key, value = matched
                    if value:
                        current_ref_outcome[key] = _unquote(value)
                    continue
                indent = len(line) - len(line.lstrip(" "))
                if line[:1] in (" ", "\t") and indent >= 8:
                    # Same fail-closed reasoning as every other gated
                    # block's own equivalent branch: an unmatched line at
                    # outcome's own indent invalidates the item rather
                    # than being silently tolerated or misread.
                    current_ref_item_valid = False
                    continue
                # Not more deeply indented: outcome's own block ends here.
                # Finalize it and fall through to re-check this same line
                # against the item's own 6-space fields below.
                _finalize_ref_outcome()
            if current_ref_item is not None:
                matched = _match_key_line(KEY_LINE_RE_6, line)
                if matched:
                    key, value = matched
                    value = _strip_bare_comment(value)
                    if key not in REFERENCES_ITEM_SUBKEYS:
                        unknown_ref_item_keys.append(line.strip())
                    elif key == "outcome" and not value:
                        current_ref_outcome = {}
                    elif value:
                        current_ref_item[key] = _unquote(value)
                    continue
                indent = len(line) - len(line.lstrip(" "))
                if line[:1] in (" ", "\t") and indent >= 6:
                    # Same fail-closed reasoning as every other gated
                    # block's own equivalent branch.
                    current_ref_item_valid = False
                    unknown_ref_item_keys.append(line.strip())
                    continue
            # Neither a new item marker nor a continuation of the current
            # one: the references list ends here (there is no legitimate
            # content under spec.references besides its own items).
            # Finalize it and fall through to process this line normally
            # below.
            _finalize_refs()
        if collecting_ext_citations is not None:
            item = REFERENCES_LIST_ITEM_RE.match(line)
            if item:
                # A new "- <key>: <value>" item marker always closes
                # whatever item came before it -- same rule as
                # spec.references' own items above.
                _finalize_current_ext_citation_item()
                item_indent = len(line) - len(line.lstrip(" "))
                raw_text = item.group(1).strip()
                opened = _match_key_line(INLINE_KEY_VALUE_RE, raw_text)
                current_ext_citation_open_line = line.strip()
                if (
                    item_indent != EXTERNAL_CITATION_ITEM_INDENT
                    or opened is None
                    or opened[0] not in EXTERNAL_CITATION_ITEM_SUBKEYS
                ):
                    malformed_ext_citations.append(line.strip())
                    current_ext_citation_item = {}
                    current_ext_citation_item_valid = False
                else:
                    key, value = opened
                    current_ext_citation_item = {}
                    current_ext_citation_item_valid = True
                    if value:
                        current_ext_citation_item[key] = _unquote(value)
                continue
            if current_ext_citation_item is not None:
                matched = _match_key_line(KEY_LINE_RE_6, line)
                if matched:
                    key, value = matched
                    value = _strip_bare_comment(value)
                    if key not in EXTERNAL_CITATION_ITEM_SUBKEYS:
                        unknown_ext_citation_item_keys.append(line.strip())
                    elif value:
                        current_ext_citation_item[key] = _unquote(value)
                    continue
                indent = len(line) - len(line.lstrip(" "))
                if line[:1] in (" ", "\t") and indent >= 6:
                    # Same fail-closed reasoning as spec.references' own
                    # equivalent branch.
                    current_ext_citation_item_valid = False
                    unknown_ext_citation_item_keys.append(line.strip())
                    continue
            # Neither a new item marker nor a continuation of the current
            # one: the externalCitations list ends here. Finalize it and
            # fall through to process this line normally below.
            _finalize_ext_citations()
        if collecting_dep_list is not None:
            item = SKILL_DEP_LIST_ITEM_RE.match(line)
            if item:
                item_indent = len(line) - len(line.lstrip(" "))
                if dep_list_indent is None:
                    dep_list_indent = item_indent
                if item_indent != dep_list_indent:
                    malformed_deps.append(line.strip())
                    continue
                raw_text = item.group(1).strip()
                is_quoted = len(raw_text) >= 2 and raw_text[0] == raw_text[-1] and raw_text[0] in "\"'"
                if (not is_quoted and REFERENCES_MAPPING_LIKE_RE.match(raw_text)) or (
                    not is_quoted and _is_non_string_plain_scalar(raw_text)
                ):
                    malformed_deps.append(line.strip())
                else:
                    collecting_dep_list.append(_unquote(raw_text))
                continue
            # Not a list item: this requires/relatedTo list ends here.
            _finalize_dep_list()
        if in_skill_deps:
            matched = _match_key_line(KEY_LINE_RE_4, line)
            if matched:
                skill_deps_has_content = True
                key, value = matched
                # A value that is NOTHING BUT a comment (e.g. "requires:
                # # comment") must read as blank/absent, not as the
                # literal comment text -- otherwise it neither opens the
                # list nor equals "[]" and is instead stored as a raw,
                # wrong-type scalar.
                value = _strip_bare_comment(value)
                if key not in SKILL_DEPENDENCY_SUBKEYS:
                    unknown_dep_keys.append(line.strip())
                elif value == "[]":
                    skill_deps[key] = []
                elif not value:
                    collecting_dep_list = []
                    collecting_dep_key = key
                    dep_list_indent = None
                else:
                    # Not an empty list and not "[]" -- this narrow parser
                    # has no flow-sequence support; store the raw scalar so
                    # the shape gate can fail it as the wrong type rather
                    # than silently dropping it.
                    skill_deps[key] = value
                continue
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent >= 4:
                # An indented line reaching here is neither an active list
                # item nor a key line KEY_LINE_RE_4 recognizes -- including
                # a key using YAML quoting/escaping that regex cannot
                # parse (an escaped quote, or whitespace between a closing
                # quote and its colon). spec.skillDependencies has no
                # legitimate reserved nested structure beyond its own two
                # list-valued keys, so flag it as unknown rather than
                # silently tolerating it: rejecting every unmatched line at
                # this indent, not just the ones a regex happens to parse,
                # is the actual fail-closed contract.
                skill_deps_has_content = True
                unknown_dep_keys.append(line.strip())
                continue
            # Dedented below the block's own indent: skillDependencies ends
            # here. Finalize it and fall through to process this line
            # normally below.
            _finalize_skill_deps()
        if lifecycle_subkey is not None:
            matched = _match_key_line(KEY_LINE_RE_6, line)
            if matched:
                lifecycle_subkey_has_content = True
                key, value = matched
                value = _strip_bare_comment(value)
                if key in LIFECYCLE_FIELDS.get(lifecycle_subkey, ()):
                    if value:
                        lifecycle_field_buffer[key] = _unquote(value)
                else:
                    unknown_lifecycle_fields.append(line.strip())
                continue
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent >= 6:
                # Same fail-closed reasoning as spec.skillDependencies'
                # equivalent branch above -- an unmatched line at this
                # indent (including one KEY_LINE_RE_6 cannot parse due to
                # quoting/escaping) is flagged, not silently tolerated.
                lifecycle_subkey_has_content = True
                unknown_lifecycle_fields.append(line.strip())
                continue
            # Dedented below the sub-block's own indent: this
            # experimental/deprecated block ends here. Finalize it and
            # fall through to process this line normally below (it may be
            # the other sub-block's header, or a dedent out of lifecycle
            # entirely).
            _finalize_lifecycle_subkey()
        if lifecycle_scalar_pending is not None:
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent > 4:
                # A block followed a scalar-only key (e.g. renamedFrom
                # given nested children instead of a plain value) -- the
                # wrong type, not the documented plain scalar. Store a
                # non-string sentinel so the checker layer reports it as
                # such; deeper sibling lines of this same mistaken block
                # are then silently absorbed by the existing "stray
                # content" fallback below (their own internal shape does
                # not matter -- the type error is already captured).
                lifecycle[lifecycle_scalar_pending] = {}
                lifecycle_scalar_pending = None
                continue
            # Not more deeply indented: the key really was declared blank
            # (or comment-only) with nothing following -- matches this
            # parser's "blank scalar assignment means not declared"
            # convention. Fall through to process the current line
            # normally below.
            lifecycle_scalar_pending = None
        if in_lifecycle:
            matched = _match_key_line(KEY_LINE_RE_4, line)
            if matched:
                lifecycle_has_content = True
                key, value = matched
                value = _strip_bare_comment(value)
                if key in LIFECYCLE_SUBKEYS:
                    if value:
                        # Not opening a block -- a bare scalar written where a
                        # mapping is expected (e.g. "experimental: true").
                        # Store the raw scalar under the subkey itself so the
                        # checker layer reports it as the wrong type, exactly
                        # as spec.skillDependencies' non-list scalar fallback
                        # works.
                        lifecycle[key] = value
                    else:
                        lifecycle_subkey = key
                        lifecycle_field_buffer = {}
                elif key in LIFECYCLE_SCALAR_KEYS:
                    if value:
                        lifecycle[key] = _unquote(value)
                    else:
                        # Blank (or comment-only) value: ambiguous until the
                        # next line is seen -- see the
                        # "lifecycle_scalar_pending is not None" handling above.
                        lifecycle_scalar_pending = key
                else:
                    unknown_lifecycle_keys.append(line.strip())
                continue
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent >= 4:
                # Same fail-closed reasoning as spec.skillDependencies'
                # equivalent branch above.
                lifecycle_has_content = True
                unknown_lifecycle_keys.append(line.strip())
                continue
            # Dedented below spec.lifecycle's own indent: the block ends
            # here. Finalize it and fall through to process this line
            # normally below.
            _finalize_lifecycle()
        if collecting_exec_tools_list is not None:
            item = EXEC_REQ_TOOLS_LIST_ITEM_RE.match(line)
            if item:
                item_indent = len(line) - len(line.lstrip(" "))
                if exec_tools_list_indent is None:
                    exec_tools_list_indent = item_indent
                if item_indent != exec_tools_list_indent:
                    # Same list, different indent than its own first item --
                    # real YAML would reject this outright.
                    malformed_exec_tools_items.append(line.strip())
                    continue
                raw_text = item.group(1).strip()
                is_quoted = len(raw_text) >= 2 and raw_text[0] == raw_text[-1] and raw_text[0] in "\"'"
                if (not is_quoted and REFERENCES_MAPPING_LIKE_RE.match(raw_text)) or (
                    not is_quoted and _is_non_string_plain_scalar(raw_text)
                ):
                    malformed_exec_tools_items.append(line.strip())
                else:
                    collecting_exec_tools_list.append(_unquote(raw_text))
                continue
            # Not a list item: this read/write/shell list ends here.
            _finalize_exec_tools_list()
        if in_exec_tools:
            matched = _match_key_line(KEY_LINE_RE_6, line)
            if matched:
                exec_tools_has_content = True
                key, value = matched
                # Same comment-only-value fix as spec.skillDependencies'
                # equivalent branch above (e.g. "read:  # comment").
                value = _strip_bare_comment(value)
                if key not in EXEC_REQ_TOOLS_SUBKEYS:
                    unknown_exec_tools_keys.append(line.strip())
                elif value == "[]":
                    exec_tools[key] = []
                elif not value:
                    collecting_exec_tools_list = []
                    collecting_exec_tools_key = key
                    exec_tools_list_indent = None
                else:
                    # Not an empty list and not "[]" -- no flow-sequence
                    # support; store the raw scalar so the shape gate can
                    # fail it as the wrong type rather than silently
                    # dropping it, exactly as spec.skillDependencies does.
                    exec_tools[key] = value
                continue
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent >= 6:
                # Same fail-closed reasoning as spec.skillDependencies'/
                # spec.lifecycle's equivalent branches -- an unmatched
                # line at this indent is flagged, not silently tolerated.
                exec_tools_has_content = True
                unknown_exec_tools_keys.append(line.strip())
                continue
            # Dedented below tools' own indent: the block ends here.
            # Finalize it and fall through to process this line normally
            # below.
            _finalize_exec_tools()
        if collecting_exec_packages_list is not None:
            item = EXEC_REQ_TOOLS_LIST_ITEM_RE.match(line)
            if item:
                item_indent = len(line) - len(line.lstrip(" "))
                if exec_packages_list_indent is None:
                    exec_packages_list_indent = item_indent
                if item_indent != exec_packages_list_indent:
                    # Same list, different indent than its own first item --
                    # real YAML would reject this outright.
                    malformed_exec_packages_items.append(line.strip())
                    continue
                raw_text = item.group(1).strip()
                is_quoted = len(raw_text) >= 2 and raw_text[0] == raw_text[-1] and raw_text[0] in "\"'"
                if not is_quoted:
                    # A trailing "# comment" on an otherwise-valid item
                    # (e.g. "- requests  # transitively needed") must not
                    # become part of the stored package name. Real YAML's
                    # own comment rule -- an unquoted "#" preceded by
                    # start-of-string or whitespace -- is exactly what
                    # _INLINE_COMMENT_RE already encodes for
                    # _is_non_string_plain_scalar's own type-classification
                    # use below; that stripped copy was never fed back into
                    # the STORED value before this fix, so a trailing
                    # comment silently became part of the parsed package
                    # name and then failed the allowlist check with
                    # nothing pointing at the comment as the actual
                    # problem. Gated on is_quoted the same way
                    # REFERENCES_MAPPING_LIKE_RE/_is_non_string_plain_scalar
                    # below already are -- a quoted item's own "#" is never
                    # a real comment marker, so stripping must not touch
                    # it. Scoped to packages only, per this fix's own
                    # issue: tools'/network's own sibling item-storage
                    # sites below share this same "stored value keeps a
                    # trailing comment" gap and are deliberately left as-is
                    # here.
                    raw_text = _INLINE_COMMENT_RE.sub("", raw_text).strip()
                if (not is_quoted and REFERENCES_MAPPING_LIKE_RE.match(raw_text)) or (
                    not is_quoted and _is_non_string_plain_scalar(raw_text)
                ):
                    malformed_exec_packages_items.append(line.strip())
                else:
                    collecting_exec_packages_list.append(_unquote(raw_text))
                continue
            if (
                line[:1] in (" ", "\t")
                and line.strip() not in ("---", "...")
                and EXEC_REQ_PACKAGES_MISINDENTED_ITEM_RE.match(line)
            ):
                # Looks like an attempted list item that the strict regex
                # above rejected on indentation alone (a tab, or fewer
                # than 6 spaces) -- see
                # EXEC_REQ_PACKAGES_MISINDENTED_ITEM_RE's own comment. A
                # real YAML parser (and a human reading the file) would
                # still see a declared package here, so this must fail
                # loudly as a malformed item like any other malformed
                # packages entry, rather than silently finalizing the list
                # as empty -- indistinguishable from the package never
                # having been declared at all.
                #
                # The line[:1] guard (found live by an independent
                # adversarial review) is required because
                # EXEC_REQ_PACKAGES_MISINDENTED_ITEM_RE's own leading
                # "[ \t]*" is zero-or-more, deliberately looser than
                # EXEC_REQ_TOOLS_LIST_ITEM_RE's own "{6,}" -- exactly the
                # width this branch needs to catch an under-indented item
                # (the bug the comment above already describes), but that
                # same width also matches a column-0 "---"/"..." YAML
                # document marker (both start with "-") and a bare
                # column-0 "- stray" line, neither of which is an
                # attempted list item at all. Excluding both here lets
                # them fall through to their own correct handling instead
                # (the document-marker skip below, or the generic
                # top-level malformed-line catch-all) rather than being
                # misreported as a malformed *packages* item and spuriously
                # failing a sidecar whose packages list is actually
                # well-formed. A real, indented-but-under-6-spaces item
                # (the tab/two-space regression fixtures this branch
                # already has) always starts with a space or tab, so this
                # guard does not narrow the original fix's own coverage.
                malformed_exec_packages_items.append(line.strip())
                continue
            # Not a list item: this per-ecosystem package-name list ends here.
            _finalize_exec_packages_list()
        if in_exec_packages:
            matched = _match_key_line(KEY_LINE_RE_6, line)
            if matched:
                exec_packages_has_content = True
                key, value = matched
                # Same comment-only-value fix as tools'/network's own
                # equivalent branches above (e.g. "pip:  # comment").
                value = _strip_bare_comment(value)
                # REGEX match, not tuple membership -- packages' own
                # subkeys are free-form ecosystem identifiers
                # (EXEC_REQ_PACKAGES_KEY_RE), unlike tools'/network's own
                # fixed EXEC_REQ_TOOLS_SUBKEYS/EXEC_REQ_NETWORK_SUBKEYS
                # tuples (see EXEC_REQ_PACKAGES_KEY_RE's own comment).
                # fullmatch(), not match(): Python's trailing "$" (unlike
                # JSON Schema's own ECMA-262 "$", which EXEC_REQ_PACKAGES_KEY_RE
                # is hand-duplicated from -- see its own comment) also
                # matches immediately before a trailing "\n", which
                # match() would silently accept. key can never actually
                # carry a "\n" here (every line is rstrip()-ped before
                # this point in the parsing loop), so this is defense in
                # depth against unintended reuse of this pattern with
                # unstripped input, not a reachable bug today. Deliberately
                # NOT rewritten to "\Z" in the regex source itself: that
                # would desync EXEC_REQ_PACKAGES_KEY_RE.pattern from
                # skill-metadata.schema.json's own propertyNames.pattern,
                # which test_execution_requirement_packages_key_pattern_matches_schema
                # asserts stay byte-identical -- and "\Z" is not a valid
                # ECMA-262 escape, so mirroring it into the JSON Schema
                # file would break every real downstream JSON-Schema
                # validator that consumes it. fullmatch() gets the same
                # exact-end semantics without touching the shared pattern
                # text.
                if not EXEC_REQ_PACKAGES_KEY_RE.fullmatch(key):
                    unknown_exec_packages_keys.append(line.strip())
                elif value == "[]":
                    exec_packages[key] = []
                elif not value:
                    collecting_exec_packages_list = []
                    collecting_exec_packages_key = key
                    exec_packages_list_indent = None
                else:
                    # Not an empty list and not "[]" -- no flow-sequence
                    # support; store the raw scalar so the shape gate can
                    # fail it as the wrong type rather than silently
                    # dropping it, exactly as tools'/network's own
                    # equivalent branches do.
                    exec_packages[key] = value
                continue
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent >= 6:
                # Same fail-closed reasoning as tools'/network's own
                # equivalent branches -- an unmatched line at this indent
                # is flagged, not silently tolerated.
                exec_packages_has_content = True
                unknown_exec_packages_keys.append(line.strip())
                continue
            # Dedented below packages' own indent: the block ends here.
            # Finalize it and fall through to process this line normally
            # below.
            _finalize_exec_packages()
        if collecting_exec_network_list is not None:
            item = EXEC_REQ_TOOLS_LIST_ITEM_RE.match(line)
            if item:
                item_indent = len(line) - len(line.lstrip(" "))
                if exec_network_list_indent is None:
                    exec_network_list_indent = item_indent
                if item_indent != exec_network_list_indent:
                    # Same list, different indent than its own first item --
                    # real YAML would reject this outright.
                    malformed_exec_network_items.append(line.strip())
                    continue
                raw_text = item.group(1).strip()
                is_quoted = len(raw_text) >= 2 and raw_text[0] == raw_text[-1] and raw_text[0] in "\"'"
                if (not is_quoted and REFERENCES_MAPPING_LIKE_RE.match(raw_text)) or (
                    not is_quoted and _is_non_string_plain_scalar(raw_text)
                ):
                    malformed_exec_network_items.append(line.strip())
                else:
                    collecting_exec_network_list.append(_unquote(raw_text))
                continue
            # Not a list item: this domains list ends here.
            _finalize_exec_network_list()
        if in_exec_network:
            matched = _match_key_line(KEY_LINE_RE_6, line)
            if matched:
                exec_network_has_content = True
                key, value = matched
                # Same comment-only-value fix as tools' equivalent branch
                # above (e.g. "domains:  # comment").
                value = _strip_bare_comment(value)
                if key not in EXEC_REQ_NETWORK_SUBKEYS:
                    unknown_exec_network_keys.append(line.strip())
                elif value == "[]":
                    exec_network[key] = []
                elif not value:
                    # Blank value: opens a list for "domains" (its normal,
                    # valid case) or, for "mode", wrongly opens a list
                    # where a scalar is expected -- the parser stores
                    # either the same way and leaves that judgment to
                    # _execution_requirements_checks, per this block's own
                    # module-docstring note above.
                    collecting_exec_network_list = []
                    collecting_exec_network_key = key
                    exec_network_list_indent = None
                else:
                    # Not an empty list and not "[]" -- store the raw
                    # scalar. This is "mode"'s own normal, valid case
                    # (e.g. "mode: disabled"); for "domains", an inline
                    # scalar here is the wrong type, caught downstream the
                    # same way tools' own list-only subkeys already are.
                    exec_network[key] = value
                continue
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent >= 6:
                # Same fail-closed reasoning as tools'/spec.skillDependencies'/
                # spec.lifecycle's equivalent branches.
                exec_network_has_content = True
                unknown_exec_network_keys.append(line.strip())
                continue
            # Dedented below network's own indent: the block ends here.
            # Finalize it and fall through to process this line normally
            # below.
            _finalize_exec_network()
        if in_execution_requirements:
            matched = _match_key_line(KEY_LINE_RE_4, line)
            if matched:
                exec_req_has_content = True
                key, value = matched
                # Same comment-only-value fix as spec.skillDependencies'
                # equivalent branch above (e.g. "tools:  # comment").
                value = _strip_bare_comment(value)
                if key not in ("tools", "packages", "network"):
                    unknown_exec_req_keys.append(line.strip())
                elif value:
                    # Not opening a block -- a bare scalar written where a
                    # mapping is expected (e.g. "tools: true"). Store the
                    # raw scalar so the checker layer reports it as the
                    # wrong type rather than silently dropping it.
                    execution_requirements[key] = value
                elif key == "tools":
                    in_exec_tools = True
                    exec_tools = {}
                elif key == "packages":
                    in_exec_packages = True
                    exec_packages = {}
                else:
                    in_exec_network = True
                    exec_network = {}
                continue
            indent = len(line) - len(line.lstrip(" "))
            if line[:1] in (" ", "\t") and indent >= 4:
                # Same fail-closed reasoning as spec.skillDependencies'/
                # spec.lifecycle's equivalent branches.
                exec_req_has_content = True
                unknown_exec_req_keys.append(line.strip())
                continue
            # Dedented below spec.executionRequirements' own indent: the
            # block ends here. Finalize it and fall through to process
            # this line normally below.
            _finalize_execution_requirements()
        if line[:1] in (" ", "\t"):
            # Indented: nested/list content this parser does not interpret,
            # except spec.references and spec.skillDependencies (handled
            # above once each starts). Exactly two spaces: a four-space
            # line (a child of a nested map) has a space where this
            # expects a key character, so it will not match and is
            # skipped -- never malformed either way.
            nested = re.match(r"[ ]{2}([A-Za-z0-9_-]+):\s*(.*)$", line)
            if nested and current is not None:
                key, value = nested.group(1), nested.group(2).strip()
                # A value that is NOTHING BUT a comment (e.g.
                # "executionRequirements:  # not yet fully specified")
                # must read as blank, the same way a real YAML parser
                # reads it -- otherwise `not value` is False, none of
                # these four gated blocks ever opens, and the entire
                # nested block underneath is discarded as a raw,
                # wrong-type scalar string instead.
                value = _strip_bare_comment(value)
                # current is root["spec"] by identity exactly while inside
                # the spec: block, so this is "are we directly under spec"
                # without tracking a separate current-top-key variable.
                if key == "references" and current is root.get("spec") and not value:
                    collecting_refs = []
                elif key == "externalCitations" and current is root.get("spec") and not value:
                    collecting_ext_citations = []
                elif key == "skillDependencies" and current is root.get("spec") and not value:
                    in_skill_deps = True
                    skill_deps = {}
                elif key == "lifecycle" and current is root.get("spec") and not value:
                    in_lifecycle = True
                    lifecycle = {}
                elif key == "executionRequirements" and current is root.get("spec") and not value:
                    in_execution_requirements = True
                    execution_requirements = {}
                elif key == "dependencyPolicy" and current is root.get("spec") and not value:
                    # dependencyPolicy is a closed-vocabulary scalar, not a
                    # block key like the four above -- but it still needs its
                    # own explicit branch: dependency-policy-declared is the
                    # first check in this file to treat "spec.get(key) is
                    # None" as "absent, therefore fine" for an *optional*
                    # field (contrast with the reserved, silently-ignored
                    # spec.evalStatus, see
                    # test_manifest_parser_still_ignores_eval_status).
                    # Falling through here would leave a bare
                    # "dependencyPolicy:" (or one followed by list/mapping
                    # content this parser does not interpret at this key's
                    # own indent) completely unregistered, indistinguishable
                    # from the key never having been written at all --
                    # dependency-policy-declared would then silently PASS a
                    # present-and-malformed declaration as if it were
                    # absent. Registering it as an empty string keeps it
                    # distinct from real absence while still failing the
                    # DEPENDENCY_POLICY_LEVELS membership check (empty
                    # string is not StdlibOnly/Declared).
                    current[key] = ""
                elif value:
                    current[key] = _unquote(value)
            continue
        if line.strip() in ("---", "..."):
            continue
        top = re.match(r"([A-Za-z0-9_-]+):\s*(.*)$", line)
        if top:
            key, value = top.group(1), top.group(2).strip()
            if value:
                root[key] = _unquote(value)
                current = None
            else:
                child: dict[str, object] = {}
                root[key] = child
                current = child
            continue
        malformed.append(line.strip())
    _finalize_refs()
    _finalize_ext_citations()
    _finalize_skill_deps()
    _finalize_lifecycle()
    _finalize_execution_requirements()
    return ManifestParse(
        root=root,
        malformed_lines=malformed,
        malformed_reference_items=malformed_refs,
        unknown_reference_item_keys=unknown_ref_item_keys,
        malformed_skill_dependency_items=malformed_deps,
        unknown_skill_dependency_keys=unknown_dep_keys,
        unknown_lifecycle_keys=unknown_lifecycle_keys,
        unknown_lifecycle_fields=unknown_lifecycle_fields,
        unknown_execution_requirement_keys=unknown_exec_req_keys,
        unknown_execution_requirement_tools_keys=unknown_exec_tools_keys,
        malformed_execution_requirement_tools_items=malformed_exec_tools_items,
        unknown_execution_requirement_packages_keys=unknown_exec_packages_keys,
        malformed_execution_requirement_packages_items=malformed_exec_packages_items,
        unknown_execution_requirement_network_keys=unknown_exec_network_keys,
        malformed_execution_requirement_network_items=malformed_exec_network_items,
        malformed_external_citation_items=malformed_ext_citations,
        unknown_external_citation_item_keys=unknown_ext_citation_item_keys,
    )


def spec_of(parsed: ManifestParse) -> dict[str, object] | None:
    """Return ``parsed.root["spec"]`` if present and a mapping, else None.

    A malformed sidecar can write ``spec:`` as a scalar or list rather than
    a mapping; every consumer that only cares about "does this sidecar have
    a real spec mapping" needs the same isinstance guard around
    ``root.get("spec")``; sharing this guard avoids the pattern regressing
    independently at each call site. Callers outside this module (e.g.
    tests/test_gitapex_skill_metadata_sidecar.py) should use this instead of
    inlining ``parsed.root.get("spec")`` themselves.
    """
    spec = parsed.root.get("spec")
    return spec if isinstance(spec, dict) else None


def _body_after_frontmatter(text: str) -> list[str]:
    """Lines after the closing frontmatter '---'. If there is no
    frontmatter, the whole text is the body."""
    text = text.lstrip("\ufeff")  # strip a leading UTF-8 BOM, as _parse_frontmatter does
    lines = text.splitlines()
    if not text.startswith("---"):
        return lines
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return lines
    return lines[end + 1 :]


def _is_ignorable(p: Path) -> bool:
    """Junk that must not affect the references/ checks: dotfiles (e.g. a
    macOS .DS_Store) and Python bytecode caches."""
    return p.name.startswith(".") or "__pycache__" in p.parts


def _raw_link_targets(body_text: str) -> list[str]:
    """Return every raw Markdown link target string in ``body_text`` --
    both inline ([text](target)) and reference-style ([text][label]
    resolved via a [label]: target definition elsewhere in the body) --
    unprocessed (no stripping, ``<...>``-unwrapping, or scheme filtering
    yet).

    Shared by ``_out_of_skill_link_targets`` and ``_broken_anchor_targets``:
    this exact gathering step (the two regex sources) is identical between
    them, but their per-target cleanup afterward is not (the latter also
    strips an inline link's optional CommonMark title before its fragment
    is read), so only this common prefix is factored out rather than the
    whole per-target loop.
    """
    raw_targets = [m.group(1) for m in LINK_RE.finditer(body_text)]
    raw_targets += [m.group(1) for m in REFDEF_RE.finditer(body_text)]
    return raw_targets


def _escapes_skill_dir(normalized: str, skill_norm: str) -> bool:
    """Whether a lexically-normalized path ``normalized`` falls outside
    ``skill_norm`` (the skill directory's own normalized path).

    Shared by ``_out_of_skill_link_targets`` (which flags an escaping
    SKILL.md link as broken) and ``_resolve_anchor_link_file`` (which
    instead treats an escaping path as out of that check's own scope) --
    the same boundary test, applied by two callers that each respond to
    it differently.
    """
    return normalized != skill_norm and not normalized.startswith(skill_norm + os.sep)


def _out_of_skill_link_targets(body_text: str, skill_dir: Path, source_dir: Path | None = None) -> list[str]:
    """Return each Markdown link target in ``body_text`` that resolves
    outside ``skill_dir``.

    Covers both inline links ([text](target)) and reference-style links
    ([text][label] resolved via a [label]: target definition elsewhere in
    the body) -- a reference-style target is exactly as capable of
    escaping the skill directory as an inline one. Skips absolute-URL/
    scheme targets (http:, https:, mailto:, ...) and bare in-page
    fragments (#section) -- neither is a same-repo relative path.
    Resolution is purely lexical (os.path.normpath), not a real
    filesystem lookup, since the target need not exist for this check.

    ``source_dir`` (default: ``skill_dir`` itself) is the directory a
    relative target is resolved AGAINST -- real relative-link semantics,
    the file-relative rule ``_resolve_anchor_link_file`` already
    established for the anchor-fragment check. For SKILL.md,
    which sits at the skill root, "relative to the containing file" and
    "relative to the skill root" coincide, so the default keeps that call
    site unchanged. A references/*.md file does NOT sit at the skill
    root, though: a relative target written there (e.g. "other.md" meaning
    "references/other.md") must resolve against references/, not the
    skill root, or a same-directory link would be misclassified as
    escaping. The escape-BOUNDARY test itself stays ``skill_dir``
    regardless of ``source_dir`` -- escaping the skill directory is the
    failure this check exists to catch, not escaping references/ alone.
    """
    skill_norm = os.path.normpath(str(skill_dir))
    source_norm = os.path.normpath(str(source_dir if source_dir is not None else skill_dir))
    offenders = []
    for raw in _raw_link_targets(body_text):
        target = raw.strip()
        if len(target) >= 2 and target[0] == "<" and target[-1] == ">":
            target = target[1:-1].strip()
        if SCHEME_RE.match(target):
            continue
        path_part = target.split("#", 1)[0].split("?", 1)[0].strip()
        if not path_part:
            continue  # fragment-only or query-only link
        if Path(path_part).is_absolute():
            normalized = os.path.normpath(path_part)
        else:
            normalized = os.path.normpath(Path(source_norm) / path_part)
        if _escapes_skill_dir(normalized, skill_norm):
            offenders.append(target)
    return offenders


# A Markdown ATX heading line: 0-3 leading spaces (CommonMark's own
# indent tolerance, matching REFDEF_RE's identical "[ ]{0,3}" convention
# elsewhere in this file), 1-6 '#', a space/tab, the heading text, then an
# optional CommonMark closing sequence (one or more trailing '#'
# characters, itself preceded by at least one space/tab) and any trailing
# whitespace. The closing sequence must be stripped in the regex itself,
# not left for ANCHOR_SLUG_STRIP_RE to clean up afterward: a trailing
# space before the closing '#'s would otherwise survive stripping and
# become a spurious trailing '-' in the slug ("heading-" instead of
# "heading"). Applied only to fence-blanked text
# (see _heading_slugs) so a heading-shaped line inside a fenced code
# example is never read as a real heading.
HEADING_RE = re.compile(r"^[ ]{0,3}#{1,6}[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$", re.MULTILINE)
# A Markdown Setext heading: a non-blank text line (0-3 leading spaces,
# CommonMark's tolerance again), immediately followed (no blank line
# between) by an underline of only '=' characters (renders an H1) or only
# '-' characters (renders an H2), itself 0-3-space-indented with optional
# trailing whitespace. The negative lookahead excludes a text line that is
# itself already a valid ATX heading (1-6 '#' then a space/tab, or '#'s
# alone at end of line) -- CommonMark gives ATX-heading parsing priority
# for that line, so it can never simultaneously serve as a Setext
# underline's own text line; without this exclusion, an ATX heading
# immediately followed by a "---" divider (a common section-break
# convention, distinct from a Setext underline) would be misread as a
# Setext H2 whose "text" is the whole "## Heading" line, hashes included.
SETEXT_HEADING_RE = re.compile(r"^[ ]{0,3}(?!#{1,6}(?:[ \t]|$))(\S.*?)[ \t]*\n[ ]{0,3}(?:=+|-+)[ \t]*$", re.MULTILINE)
# GitHub's own heading-to-anchor slug punctuation strip set -- a denylist
# of specific ASCII punctuation plus two Unicode "General Punctuation"/
# "Supplemental Punctuation" blocks, matching the real github-slugger
# algorithm's own regex, NOT an ASCII allowlist. This denylist form
# preserves Unicode letters/digits (and underscore/hyphen/space) while
# stripping the same fixed punctuation set GitHub's own slugger strips --
# an ASCII-only allowlist would incorrectly also delete non-ASCII Unicode
# letters (e.g. turning "## Café Notes" into "caf-notes" instead of
# GitHub's real "café-notes").
ANCHOR_SLUG_STRIP_RE = re.compile(r"[\u2000-\u206F\u2E00-\u2E7F\\'!\"#$%&()*+,./:;<=>?@\[\]^`{|}~]")


def _github_slug(heading: str, occurrences: dict[str, int]) -> str:
    """Return the GitHub-rendered anchor slug for one ``heading``'s text,
    given ``occurrences`` (a same-document-wide table of every slug string
    already assigned, mapped to a running per-base counter -- mutated in
    place by this call, and threaded across every heading in the target
    document, in order, not reset per link, since GitHub's own dedup
    counts every rendered heading, not only the ones some other document
    happens to link to).

    Lowercase, strip via ANCHOR_SLUG_STRIP_RE, then each surviving space
    becomes its own literal '-' -- adjacent punctuation removed by the
    strip step is NOT collapsed first, so "Trust & authority" becomes
    "trust  authority" (two spaces where '&' was deleted) and then
    "trust--authority", a real slug already in this repository's own
    executing-a-branch-plan TOC-validated data.

    A slug that repeats an earlier heading's slug earns a '-1', '-2', ...
    suffix -- but the candidate suffix must itself be checked against
    every slug already assigned, not just counted against its own base:
    for headings "Foo", "Foo-1", "Foo" in that order, the naive "count how
    many times 'foo' was seen" approach would slug the third heading
    "foo-1" again, colliding with the second heading's own real slug
    "foo-1". This loop instead keeps incrementing the
    base's own counter and re-probing until it lands on a slug string not
    already in ``occurrences`` -- exactly the real github-slugger
    algorithm's own occurrence-tracking approach -- so the third "Foo"
    above correctly slugs to "foo-2", skipping over the already-taken
    "foo-1".
    """
    slug = ANCHOR_SLUG_STRIP_RE.sub("", heading.lower()).replace(" ", "-")
    original = slug
    while slug in occurrences:
        occurrences[original] = occurrences.get(original, 0) + 1
        slug = f"{original}-{occurrences[original]}"
    occurrences[slug] = 0
    return slug


def _heading_slugs(text: str) -> frozenset[str]:
    """Return every GitHub-rendered anchor slug ``text`` (a Markdown
    document body) would expose, in heading order, deduplicated exactly
    as GitHub's own renderer does (see ``_github_slug``).

    Fenced code blocks are blanked first via ``_blank_fenced_blocks`` (the
    same helper the citation checks already share) so an illustrative
    heading-shaped line inside a worked example is never treated as a
    real heading; that same helper also normalizes CRLF/CR line endings
    to bare '\\n' via its own ``str.splitlines()`` + ``"\\n".join`` pass,
    so a Windows-checked-out file with trailing '\\r' characters cannot
    leak into a captured heading's text either.

    ATX (HEADING_RE) and Setext (SETEXT_HEADING_RE) matches are gathered
    together and sorted by position before slugging, since GitHub's own
    per-document dedup counter must see every heading in true document
    order regardless of which of the two forms produced it.
    """
    defenced = _blank_fenced_blocks(text)
    matches = [(m.start(), m.group(1)) for m in HEADING_RE.finditer(defenced)]
    matches += [(m.start(), m.group(1)) for m in SETEXT_HEADING_RE.finditer(defenced)]
    matches.sort(key=lambda pair: pair[0])
    occurrences: dict[str, int] = {}
    return frozenset(_github_slug(heading, occurrences) for _pos, heading in matches)


# A cross-skill "file+heading" citation: this repository's own
# established convention for naming a specific sibling skill's reference
# file and heading in prose (e.g. "`evaluating-skill-quality`'s
# `references/adversarial-self-audit.md` Isolation verification section").
# Both the skill
# name and the file path sit in their OWN inline-code span (unlike the
# bare-prose citation checks below, this one is never inline-code-stripped
# first -- the regex depends on the backticks being present), while the
# heading text itself is bare prose ending at the literal word "section".
# Skill-name char class matches BACKTICK_SKILL_NAME_RE's own kebab-case
# shape (same convention _stale_related_skill_references already reads a
# sibling skill name against). A plain ASCII apostrophe before "s",
# matching this repository's own established prose (this repository's own
# skill content uses only plain ASCII apostrophes). The
# heading-text group is deliberately narrow (letters/digits/space/
# apostrophe/slash/hyphen, non-greedy) so it stops at the literal " section"
# boundary rather than running on into the next sentence.
#
# "s?" (not a bare "s") plus a following-character guard, not a plain
# "\s+": a sibling skill directory name that itself already ends in "s"
# (e.g. "scorer-gated-skill-edits") is correctly cited with the bare
# English possessive apostrophe and no trailing "s" -- the same "\b does
# not work here" pitfall PORTABLE_SKILL_FACT_CLAIM_RE's own comment
# documents. Without the same fix, a cross-skill citation naming such a
# sibling in the grammatically-correct bare-apostrophe form would never
# match at all, never flagged as dangling even if broken. The
# following-character guard is a negative lookahead for
# a word character, not a literal "\s+": a possessive immediately followed
# by punctuation before further prose (e.g. a comma) still needs to match.
CROSS_SKILL_CITATION_RE = re.compile(
    r"`([a-z0-9](?:[a-z0-9-]*[a-z0-9])?)`'s?(?![A-Za-z0-9])\s*"
    r"`references/([A-Za-z0-9._-]+\.md)`\s+"
    r"([A-Za-z0-9][A-Za-z0-9 '/-]*?)\s+[Ss]ection\b"
)

# Mechanism-fit subsection completeness: every ATX heading in a
# document, this time captured WITH its own '#'-run (unlike HEADING_RE,
# which only needs a heading's text for anchor-slug purposes and is
# level-agnostic) -- the Mechanism-fit check below needs to tell a level-2
# "## Mechanism fit" heading apart from a level-3 "### " subsection nested
# under it, so it cannot reuse HEADING_RE's own single-capture-group shape.
MECHANISM_FIT_HEADING_RE = re.compile(r"^[ ]{0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$", re.MULTILINE)
# A "[label]"-style citation bracket -- this repository's own established
# reference-style-link-label convention (e.g. "[sd]", "[ab]",
# "[modeleffort]"), the same shape a Mechanism-fit subsection already uses
# today wherever it cites a primary source. Presence-only: this check does
# not verify the label resolves to a real "[label]: url" definition
# elsewhere in the document (a distinct, narrower question this check
# does not attempt), only that a subsection carries SOME citation-shaped marker
# rather than none.
MECHANISM_FIT_CITATION_RE = re.compile(r"\[[a-z0-9][a-z0-9-]*\]")
# The literal disclosure phrase this repository's own rubric.md already
# uses (verbatim, twice) to mark a Mechanism-fit claim as its own reasoned
# extension rather than an Anthropic-sourced one.
MECHANISM_FIT_REASONED_EXTENSION_PHRASE = "this repository's own reasoned extension"


# An optional Markdown link *title* trailing an inline link's destination
# (CommonMark: destination, one or more spaces, then "title", 'title', or
# (title)). LINK_RE's own capture group is the entire parenthesized
# content -- destination and title together -- so a titled inline link
# like [text](#heading "Jump there") would otherwise leave the title text
# stuck onto the fragment once split on '#'. Reference-style definitions
# (REFDEF_RE) already exclude the title naturally, since their own
# capture group is a bare non-whitespace run; applying this to a
# REFDEF_RE-sourced target is harmless (no whitespace+quoted-suffix shape
# to strip from an untitled destination).
LINK_TITLE_RE = re.compile(r"""[ \t]+(?:"[^"]*"|'[^']*'|\([^()]*\))[ \t]*$""")


def _resolve_anchor_link_file(raw_path: str, source_dir: Path, skill_norm: str) -> Path | None:
    """Resolve a Markdown link's path portion to the file it actually
    points at, for the purpose of validating its ``#fragment`` -- real
    relative-link semantics, resolved against ``source_dir`` (the
    directory of the file that CONTAINS the link), not against the skill
    root the way ``_out_of_skill_link_targets`` resolves paths.

    That existing helper's skill-root-relative resolution is only ever
    exercised against SKILL.md, which happens to sit at the skill root --
    so "relative to the containing file" and "relative to the skill root"
    coincide there and the difference was never actually observable. This
    check also runs per references/*.md file, which does not sit at the
    skill root, so the two resolution rules would diverge for a
    cross-reference link written there; this function uses the real,
    file-relative rule so it stays correct in both places.

    Returns ``None`` when the resolved path falls outside the skill
    directory -- deliberately out of scope for this check: an escaping
    path is a distinct defect class links-inside-skill (for SKILL.md)
    already owns separately, not one this anchor check duplicates or
    re-flags.
    """
    if Path(raw_path).is_absolute():
        resolved = os.path.normpath(raw_path)
    else:
        resolved = os.path.normpath(Path(source_dir) / raw_path)
    if _escapes_skill_dir(resolved, skill_norm):
        return None
    return Path(resolved)


def _cached_target_heading_slugs(path: Path, cache: dict[Path, frozenset[str] | None]) -> frozenset[str] | None:
    """Return ``path``'s heading-slug set (see ``_heading_slugs``), reading
    and parsing the file at most once per ``check_shape`` run -- ``cache``
    is shared across the SKILL.md check and every references/*.md check in
    one call, since more than one link can point at the same target file.

    Returns ``None`` (a cached miss) when ``path`` cannot be read as UTF-8
    text (missing, a directory, binary, or non-UTF-8) -- the caller treats
    that as "this fragment can never resolve" (a broken-anchor failure),
    not a skip: unlike the references/ TOC check's own tolerance for
    unreadable junk (which exists so a stray binary file sitting in
    references/ cannot abort the whole run), a link that names a target
    file which does not exist -- or cannot be read as one -- has no
    possible real heading to match, so silently passing it would leave
    exactly the kind of dead link (`[ghost](references/missing.md#x)`)
    this check exists to catch undetected.
    """
    if path in cache:
        return cache[path]
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        cache[path] = None
        return None
    body = "\n".join(_body_after_frontmatter(text))
    slugs = _heading_slugs(body)
    cache[path] = slugs
    return slugs


def _broken_anchor_targets(
    body_text: str, source_path: Path, skill_dir: Path, cache: dict[Path, frozenset[str] | None]
) -> list[str]:
    """Return each Markdown link target in ``body_text`` (the body of
    ``source_path``) whose ``#fragment`` does not match any real
    GitHub-rendered heading anchor in its target file.

    Shares ``_out_of_skill_link_targets``'s own link-gathering step
    (``_raw_link_targets``) and its ``<...>``-unwrap/SCHEME_RE
    absolute-URL skip, but inspects the fragment instead of validating
    the path. An inline link's optional CommonMark title
    (``[text](#heading "Jump there")``) is stripped via LINK_TITLE_RE
    before the fragment is read -- LINK_RE's own capture group is the
    entire parenthesized destination-plus-title, so without this step a
    titled link's title text would stay stuck onto the fragment
    (`heading "Jump there"`), which could never match any real anchor and
    would false-positive-fail a link GitHub renders and resolves
    correctly. A target with no ``#`` or an empty fragment (path-only, or
    a bare trailing ``#``) has nothing to check and is skipped. A bare
    fragment (``#section``, no path) resolves against ``source_path``
    itself; otherwise the path portion resolves via
    ``_resolve_anchor_link_file`` -- a path that escapes the skill
    directory is silently skipped (see that function's own docstring for
    why: it is links-inside-skill's own separate, already-owned failure).
    A target file that cannot be read as one, by contrast, IS flagged
    here (see ``_cached_target_heading_slugs``'s own docstring): there is
    no real heading it could possibly expose, so every fragment link into
    it is broken.
    """
    skill_norm = os.path.normpath(str(skill_dir))
    source_dir = source_path.parent
    offenders = []
    for raw in _raw_link_targets(body_text):
        target = raw.strip()
        title_match = LINK_TITLE_RE.search(target)
        if title_match:
            target = target[: title_match.start()].rstrip()
        if len(target) >= 2 and target[0] == "<" and target[-1] == ">":
            target = target[1:-1].strip()
        if SCHEME_RE.match(target):
            continue
        path_part, _sep, fragment = target.partition("#")
        path_part = path_part.split("?", 1)[0].strip()
        fragment = fragment.strip()
        if not fragment:
            continue  # path-only, query-only, or bare trailing '#'
        if path_part:
            resolved = _resolve_anchor_link_file(path_part, source_dir, skill_norm)
            if resolved is None:
                continue  # escapes the skill dir -- a different check's concern
        else:
            resolved = source_path
        slugs = _cached_target_heading_slugs(resolved, cache)
        if slugs is None or fragment not in slugs:
            offenders.append(target)
    return _dedup(offenders)


def _is_bare_skill_name(entry: str) -> bool:
    """Whether ``entry`` is shaped like a real skill directory name -- a
    bare path component (no separator, not ".", not "..") -- rather than a
    path that could escape the skills root when joined with "/".
    ``(skill_dir.parent / entry).is_dir()`` does not itself guard against
    pathlib's absolute-operand-replaces-the-left-side behavior
    (``Path("/repo/skills") / "/etc" == Path("/etc")``) or a "../"
    traversal segment, so an entry that is not a bare name must never be
    treated as potentially resolving. Mirrors
    ``.github/scripts/gitapex_scan_skill_metadata_schema.py``'s own
    ``_is_bare_skill_name``; kept as an independent copy rather than a
    shared import because this file is stdlib-only by design (see the
    module docstring) and that module is not (issue #757)."""
    return entry not in ("", ".", "..") and "/" not in entry and "\\" not in entry


def _resolves_to_sibling_skill(name: str, siblings_dir: Path) -> bool:
    """Whether ``name`` names an existing sibling skill directory: a bare
    name (see ``_is_bare_skill_name``) whose ``siblings_dir / name`` also
    contains a real ``SKILL.md`` -- not merely ``.is_dir()``. Without the
    ``SKILL.md`` check, any non-skill directory under ``siblings_dir`` (a
    docs folder, a work-in-progress directory with no ``SKILL.md`` yet, a
    stray build artifact) would incorrectly read as a resolved reference.
    Shared by this file's four dangling-reference resolve checks
    (related-skill-references-resolve, portable-no-unhedged-skill-fact-claim,
    skill-dependencies-resolve, lifecycle-deprecated-replacement-resolves)
    so the one safety-critical "does this reference resolve" predicate has
    exactly one implementation in this file, not four copies that could
    silently diverge. Backports the identical gap fixed in
    ``gitapex_scan_skill_metadata_schema.py``'s own
    ``_resolves_to_sibling_skill`` (issue #757)."""
    return _is_bare_skill_name(name) and (siblings_dir / name / "SKILL.md").is_file()


def _stale_related_skill_references(body_text: str, skill_dir: Path) -> list[str]:
    """Return each skill name referenced anywhere inside a "**vs. `name`:**"
    Related-skills bullet (its header AND its own explanatory prose) in
    ``body_text`` that does not resolve to an existing sibling skill
    directory.

    A rename that updates every skill's own Steps/Output but misses one
    sibling's "vs. `old-name`:" cross-reference leaves prose that reads
    fine in isolation but names a directory that no longer exists -- this
    is a purely static, single-tree-state check (no git history needed):
    every currently-committed bullet's name must resolve right now.
    """
    offenders: list[str] = []
    for bullet_match in RELATED_SKILL_BULLET_RE.finditer(body_text):
        for name in BACKTICK_SKILL_NAME_RE.findall(bullet_match.group(0)):
            if not _resolves_to_sibling_skill(name, skill_dir.parent):
                offenders.append(name)
    return offenders


@dataclass(frozen=True)
class SidecarPortability:
    """Three-state summary of the sidecar's portability declaration.

    Derived once, in ``check_shape``, from the single sidecar read+parse
    performed there -- this module never reads the sidecar a second time to
    answer the portability question. Handed to ``_is_portable``, which
    dispatches on ``state`` instead of touching the filesystem itself.

    - "absent": no ``metadata/gitapex.yaml`` under the skill directory. The
      vendored-from-elsewhere case: ``_is_portable`` falls back to the
      near-top body marker.
    - "usable": the sidecar was read and parsed, and its
      ``spec.portability`` is one of ``PORTABILITY_LEVELS``. ``level``
      carries that value; ``_is_portable`` returns ``level == "Portable"``.
    - "unusable": the sidecar exists but could not be read/parsed (bad
      encoding, OS error), or its ``spec.portability`` is missing or not a
      recognised level. ``_is_portable`` returns True unconditionally in
      this state -- see its docstring for why.
    """

    state: str
    level: str | None = None


def _is_portable(body: list[str], sidecar: SidecarPortability) -> bool:
    """Whether the skill declares itself Portable (not Mixed/Repository-scoped).

    Dispatches on ``sidecar`` (a ``SidecarPortability`` derived once in
    ``check_shape`` from its single sidecar read -- this function never
    reads the sidecar itself):

    1. ``sidecar.state == "usable"``: the sidecar alone decides --
       "Portable" -> True, "Mixed" / "Repository-scoped" -> False. This is
       the declaration form every skill in this repository uses, since the
       enum moved out of the SKILL.md body and into the sidecar.
    2. ``sidecar.state == "absent"``: no sidecar file at all -- fall back to
       the near-top body marker (``**Portability: Portable.**``). A skill
       vendored in from another repository carries that marker and no
       sidecar, and must still get the path-citation scan rather than
       silently skipping it.
    3. ``sidecar.state == "unusable"``: the sidecar exists but is
       unreadable, or its ``spec.portability`` is missing/unrecognised.
       Returns True -- run the scan -- WITHOUT consulting the body marker.
       This is deliberate: when a sidecar is present it is authoritative,
       and this repo's own rule is that a false negative in a gate (a
       silently skipped scan) is worse than a false positive (extra
       citation findings). A skill in this state is already failing
       ``portability-declared``, so the extra findings land on an
       already-red skill rather than a silently-skipped one.

    "Mixed" and "Repository-scoped" skills legitimately cite repo-specific
    paths, so the two Portable-only repo-path citation checks
    (``_portable_path_citation_checks``) do not apply to them. The
    bare-issue-citation check (``_issue_citation_checks``) is different: it
    runs unconditionally on every skill regardless of what this function
    returns -- this function's return value never gates it.

    In the fallback (absent) path the level word may wrap onto the line
    after the ``Portability:`` marker (e.g. ``**Portability:**`` then
    ``Portable. ...``). Reading only the marker line would then classify a
    Portable skill as non-Portable and silently skip the path-citation scan
    -- a false negative in the gate, worse than a false positive -- so when
    the marker line carries no level word, the immediately following line
    is folded in before deciding.
    """
    if sidecar.state == "usable":
        return sidecar.level == "Portable"
    if sidecar.state == "unusable":
        return True
    window = body[:PORTABILITY_MAX_BODY_LINE]
    for i, line in enumerate(window):
        if PORTABILITY_RE.search(line):
            decl = line
            if not (PORTABLE_LEVEL_RE.search(line) or NON_PORTABLE_LEVEL_RE.search(line)):
                decl = " ".join(window[i : i + 2])  # level wrapped to next line
            return bool(PORTABLE_LEVEL_RE.search(decl)) and not NON_PORTABLE_LEVEL_RE.search(decl)
    return False


def _blank_fenced_blocks(body_text: str) -> str:
    """Return ``body_text`` with every fenced code block's lines (the
    fence markers themselves included) replaced by empty lines, preserving
    line count and every other line verbatim.

    Shared by ``_strip_illustrative_spans`` (which goes on to also strip
    inline code, URLs, and links) and ``_inline_citation_offenders``
    (which deliberately keeps inline code intact, since it inspects
    exactly those spans) -- both need fenced blocks excluded the same way,
    since a fenced code block is "already illustrative" regardless of
    which citation shape is being scanned for.
    """
    out: list[str] = []
    in_fence = False
    for line in body_text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


# Sentence-ending punctuation followed by whitespace. A deliberately simple
# tokenizer (not a full sentence-boundary detector): it can over-split on an
# abbreviation like "e.g." mid-sentence, but ``_inline_citation_offenders``
# checks both the current AND the immediately preceding sentence for a
# hedge, so an over-split still finds a hedge that landed just before the
# split point -- the failure mode is graceful, not silent. Semicolons are
# handled separately, by ``_split_at_bridging_semicolon`` below, rather than
# folded into this regex -- see that function's docstring for why a blanket
# semicolon split is wrong.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
# A blank line (a run of whitespace-only lines) separating paragraphs, and a
# run of whitespace collapsed to one space -- both precompiled, matching
# this file's own convention, since ``_inline_citation_offenders`` applies
# them to every paragraph of every source file for every citation spec.
_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_illustrative_spans(defenced_text: str) -> str:
    """Return ``defenced_text`` (already fence-blanked via
    ``_blank_fenced_blocks``) with every span that quotes a token
    illustratively or externally removed, leaving only bare prose.

    Per line, strips inline code spans, absolute URLs, Markdown
    inline/reference links, and reference definitions. These are exactly
    the forms in which this repo's Portable skills already write an issue
    number or repo path without it resolving live (an inline-code
    ``#149``, a full URL, a ``[PR #2][pr2]`` worked-example link), so what
    remains is a citation sitting unguarded in running prose.
    """
    out: list[str] = []
    for line in defenced_text.splitlines():
        if MD_REF_DEF_RE.match(line):
            out.append("")
            continue
        stripped = INLINE_CODE_RE.sub(" ", line)
        stripped = BARE_URL_RE.sub(" ", stripped)
        stripped = MD_INLINE_LINK_RE.sub(" ", stripped)
        stripped = MD_REF_LINK_RE.sub(" ", stripped)
        out.append(stripped)
    return "\n".join(out)


def _split_at_bridging_semicolon(sentence: str, citation_res: tuple[re.Pattern[str], ...]) -> list[str]:
    """Split ``sentence`` at its first semicolon into two clauses, but ONLY
    when an inline-code citation (matching any of ``citation_res``, across
    every spec, not just one) appears on BOTH sides of it -- otherwise
    return ``[sentence]`` unsplit.

    A semicolon is structurally ambiguous in real prose: it can join two
    independent clauses ("Use the hex color `#123456`; see PR `#42` for
    the implementation history."), which must split so the second, unrelated
    citation does
    not inherit the first's hedge; or it can sit inside a single
    parenthetical aside about ONE citation ("`docs/adr/NNNN-*.md` (line
    24; gitapex's own state on this path is covered under Portability
    level above), uses forward slashes." -- real, pre-existing content in
    this repository's own worked-example-explaining-the-work.md), which
    must NOT split, or the hedge phrase that lands after the semicolon
    loses the citation it was actually describing. Splitting at every
    semicolon would incorrectly split a single parenthetical aside about
    one citation; never splitting would let a hedge after the semicolon
    absorb an unrelated citation before it. Requiring a
    citation on both sides is the narrowest rule that keeps both correct.
    Only the FIRST semicolon is considered -- multiple semicolons in one
    sentence are rare enough in this repository's own prose that handling
    only the common case matches this checker's own established "simple,
    not a full parser" tolerance elsewhere in this module.
    """
    semi = sentence.find(";")
    if semi == -1:
        return [sentence]
    before, after = sentence[: semi + 1], sentence[semi + 1 :]

    def _has_citation(text: str) -> bool:
        return any(cre.search(m.group(2)) for m in INLINE_CODE_RE.finditer(text) for cre in citation_res)

    if _has_citation(before) and _has_citation(after):
        return [before, after]
    return [sentence]


def _inline_citation_offenders(
    defenced_text: str,
    specs: tuple[tuple[re.Pattern[str], tuple[str, ...], frozenset[str]], ...],
) -> list[list[str]]:
    """Return, for each ``(citation_re, hedge_phrases, declared_paths)``
    triple in ``specs``, the list of inline-code citations matching that
    ``citation_re`` in
    ``defenced_text`` (already fence-blanked via ``_blank_fenced_blocks``)
    that have no phrase from that spec's ``hedge_phrases`` in their own
    sentence (or bridging-semicolon-split clause, see
    ``_split_at_bridging_semicolon``) or the one immediately before it (see
    the module docstring's repo-path and issue-number citation entries for
    the rationale, and the clause-splitting note below). The returned list
    is ordered the same as ``specs``. Shared by the evals/docs/CLAUDE.md-
    chapter repo-path check (``REPO_PATH_CITATION_RE``/
    ``GENERIC_ROLE_HEDGE_PHRASES`` -- see that constant's own comment for
    why only the generic-placeholder half of ``HEDGE_PHRASES`` rescues a
    match here) and the issue-number check
    (``ISSUE_CITATION_RE``/``ISSUE_CITATION_HEDGE_PHRASES``) -- the citation
    shape and hedge vocabulary differ per spec, but the paragraph/sentence
    tokenization and the inline-code-span search below are identical, so
    both specs are evaluated in one pass over the same tokens rather than
    one pass per spec.

    Bounded to a paragraph first (a run of contiguous non-blank lines),
    then to a sentence within it via ``_SENTENCE_SPLIT_RE``, each further
    split at a bridging semicolon (see ``_split_at_bridging_semicolon`` --
    across every spec's citation shape at once, since clause boundaries
    are shared infrastructure, not per-spec) -- not paragraph-wide, so a
    hedge written for one citation cannot silently exempt an unrelated
    citation many sentences later in the same (possibly long, multi-topic)
    paragraph. Whitespace inside a paragraph is normalized to single
    spaces first, since Markdown line-wraps a hedge phrase across lines
    exactly as often as it wraps any other prose (e.g. "the calling\\n
    repository's own").

    Every inline-code span in the clause -- not just the citation being
    checked -- is blanked out of that clause's hedge search text, so a
    citation cannot self-satisfy the requirement merely because its own
    text happens to contain a hedge word (e.g. a path literally named with
    "gitapex" in it). A hedge is the author's own prose explaining a
    citation; text inside any backtick span is never that, regardless of
    which citation it is or whether it happens to match a citation shape
    at all.

    Two or more citations WITHIN one clause deliberately still share that
    whole clause's hedge search -- this file's own real content relies on
    one leading hedge introducing a list of several different citations
    (e.g. "in this repository's own bookkeeping ...:
    `evals/.../split.md`'s Kept-edit log and `docs/skill-eval-status.md`."),
    which a stricter per-citation windowing design would incorrectly break.
    The "clause immediately before"
    fallback is instead the layer doing the real work for the reported
    exploit shape: it is used ONLY when that previous clause has no
    citation of its own for this spec -- the established, tested pattern
    is a pure hedge clause ("This repository has also recorded background
    context here.") followed by a citation clause, never two back-to-back
    clauses that each cite something. Without this restriction, a hedge
    that correctly justifies one clause's own citation (e.g. "Use the hex
    color `#123456` for the button.") would leak into a completely
    unrelated citation in the very next clause (e.g. "See PR `#42` for the
    implementation history.") purely because they are clause-adjacent.

    A narrower residual is accepted, not solved, by this design: two
    DIFFERENT citations within the same clause, comma- or
    apposition-joined (no bridging semicolon), where only one is
    genuinely hedged (e.g. "See `#123456`, a hex color reference,
    followed by the real bug `#42`.") still share the clause-wide hedge
    and both pass. Distinguishing that shape from the legitimate "one
    hedge, a list of several citations" shape above would require more
    than a punctuation-based tokenizer can resolve; this checker is a
    deliberately simple, practical approximation (see the module's own
    established tolerance for this tokenizer's "e.g." over-split,
    elsewhere in this file), not a full parser.

    Fenced code blocks are already excluded by the caller via
    ``_blank_fenced_blocks`` -- a citation inside a fenced illustrative
    example never reaches this check, matching the module docstring's
    "fenced code blocks stay exempt unconditionally" note. Each spec's
    result list is order-preserving and deduplicated, matching
    ``_portable_citation_offenders``.

    ``declared_paths`` (issue #1055) supplements ``hedge_phrases`` for a
    spec that carries one: a citation whose own matched text exactly
    equals a member of ``declared_paths`` is rescued even when its clause
    carries no hedge phrase at all, per-citation rather than clause-wide --
    a ``spec.externalCitations`` declaration is a fact about one specific
    path, unlike a hedge phrase, which is prose covering everything in its
    own clause. Empty for the issue-number spec, which this proposal does
    not touch.
    """
    citation_res = tuple(citation_re for citation_re, _hedge_phrases, _declared_paths in specs)
    offenders_per_spec: list[list[str]] = [[] for _ in specs]
    for para in _PARAGRAPH_SPLIT_RE.split(defenced_text):
        if not para.strip():
            continue
        normalized = _WHITESPACE_RE.sub(" ", para)
        clauses: list[str] = []
        for sentence in _SENTENCE_SPLIT_RE.split(normalized):
            clauses.extend(_split_at_bridging_semicolon(sentence, citation_res))
        # Precomputed once per paragraph (not just-in-time per clause) so
        # the "previous clause has no citation of its own" check below can
        # look at any earlier clause's code spans without re-scanning.
        all_code_spans = [list(INLINE_CODE_RE.finditer(c)) for c in clauses]
        for i, clause in enumerate(clauses):
            code_spans = all_code_spans[i]
            if not code_spans:
                continue
            prev_lower = clauses[i - 1].lower() if i > 0 else ""
            clause_lower = clause.lower()
            blanked = list(clause_lower)
            for cs in code_spans:
                for pos in range(cs.start(), cs.end()):
                    blanked[pos] = " "
            blanked_lower = "".join(blanked)
            for spec_idx, (citation_re, hedge_phrases, declared_paths) in enumerate(specs):
                spec_matches = [(cs, list(citation_re.finditer(cs.group(2)))) for cs in code_spans]
                spec_matches = [(cs, ms) for cs, ms in spec_matches if ms]
                if not spec_matches:
                    continue
                prev_has_own_citation = i > 0 and any(citation_re.search(cs.group(2)) for cs in all_code_spans[i - 1])
                candidate_prev = "" if prev_has_own_citation else prev_lower
                hedged = any(phrase in blanked_lower or phrase in candidate_prev for phrase in hedge_phrases)
                if hedged:
                    continue
                for cs, matches in spec_matches:
                    # A span is rescued only when EVERY citation match it
                    # carries is declared -- per-citation, not clause-wide
                    # (issue #1055): a span packing one declared and one
                    # undeclared citation (e.g. `` `docs/a.md docs/b.md` ``)
                    # must still surface the undeclared one, so a single
                    # ``.search()`` (first match only) is not enough here.
                    all_declared = bool(declared_paths) and all(m.group(0) in declared_paths for m in matches)
                    if not all_declared:
                        offenders_per_spec[spec_idx].append(cs.group(0))
    return [_dedup(offenders) for offenders in offenders_per_spec]


def _portable_citation_offenders(defenced_text: str) -> tuple[list[str], list[str]]:
    """Return (issue-number, repo-path) bare-prose citations in
    ``defenced_text`` (already fence-blanked via ``_blank_fenced_blocks``).

    Applies the illustrative-span strip first, so only citations left
    unguarded in running prose are reported. Order-preserving and
    deduplicated so the evidence string is stable and terse.
    """
    prose = _strip_illustrative_spans(defenced_text)
    issues = _dedup(m.group(0) for m in ISSUE_CITATION_RE.finditer(prose))
    paths = _dedup(m.group(0) for m in REPO_PATH_CITATION_RE.finditer(prose))
    return issues, paths


def _dedup(items: Iterable[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        seen.setdefault(item, None)
    return list(seen)


def _no_xml_check(field: str, value: str) -> CheckResult:
    has_tag = bool(TAG_RE.search(value))
    return CheckResult(
        f"{field}-no-xml", not has_tag, f"{field} has no XML tags", "tag found" if has_tag else "no tags"
    )


def _length_check(field: str, value: str, limit: int) -> CheckResult:
    return CheckResult(f"{field}-length", len(value) <= limit, f"{field} <= {limit} chars", f"{len(value)} chars")


def _yaml_plain_scalar_safety_check(field: str, value: str, is_plain_scalar: bool) -> CheckResult:
    rule = (
        f"{field} (an unquoted YAML plain scalar) has no ': ', trailing "
        "':', or ' #'/leading '#' that would break or silently "
        "truncate under a real YAML parser"
    )
    if not is_plain_scalar:
        # A quoted or block-scalar (>/|) value is already safe under a real
        # YAML parser regardless of what characters it contains -- the
        # hazard this check exists for is specific to the unquoted plain
        # scalar form (the one every SKILL.md in this repository currently
        # uses), so a quoted/block-scalar field is exempt rather than
        # scanned against already-unquoted/already-joined text that no
        # longer reflects how it was actually written.
        return CheckResult(f"{field}-yaml-safe", True, rule, "safe (quoted or block scalar in source)")
    colon_hit = UNSAFE_COLON_RE.search(value)
    comment_hit = UNSAFE_COMMENT_RE.search(value)
    # Report whichever hazard occurs first in the string -- a real YAML
    # parser stops at the first one it hits, so that is also the one a
    # maintainer needs to see in order to fix the value.
    if colon_hit and (comment_hit is None or colon_hit.start() <= comment_hit.start()):
        ok, evidence = False, f"unquoted ': ' or trailing ':' at char {colon_hit.start()}"
    elif comment_hit:
        ok, evidence = False, f"unquoted ' #' or leading '#' at char {comment_hit.start()}"
    else:
        ok, evidence = True, "safe"
    return CheckResult(f"{field}-yaml-safe", ok, rule, evidence)


def _resolve_skill_md(target: Path) -> Path:
    return target / "SKILL.md" if target.is_dir() else target


def _validate_read_scope(target: Path, allowed_root: Path) -> None:
    """Reject an escaped or symlinked CLI target before reading any content."""
    # PTH100 waived on all three abspath calls in this file: Path.resolve()
    # follows symlinks, os.path.abspath does not. This function depends on
    # that difference -- it absolutizes without resolving so the loop below
    # can still see each symlinked component and reject it. Rewriting to
    # resolve() would collapse the very links this check exists to catch.
    root = Path(os.path.abspath(allowed_root))  # noqa: PTH100
    if not root.is_dir():
        raise ValueError(f"allowed root is not a directory: {allowed_root}")

    candidate = _resolve_skill_md(Path(os.path.abspath(target)))  # noqa: PTH100
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"target is outside allowed root: {target}") from exc

    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"symlink is not allowed in target path: {current}")

    root_real = root.resolve(strict=True)
    candidate_real = candidate.resolve(strict=True)
    try:
        candidate_real.relative_to(root_real)
    except ValueError as exc:
        raise ValueError(f"resolved target is outside allowed root: {target}") from exc

    skill_dir = candidate.parent
    for directory, dirnames, filenames in os.walk(skill_dir, followlinks=False):
        for name in dirnames:
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError(f"symlink is not allowed in target skill: {path}")
        for name in filenames:
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError(f"symlink is not allowed in target skill: {path}")
            if not path.is_file():
                raise ValueError(f"special file is not allowed in target skill: {path}")


def _references_grammar_check(references: object) -> CheckResult:
    """spec.references entries must each have a ``kind`` drawn from
    REFERENCES_KIND_VOCAB -- the one thing about an already-well-shaped
    item (see ``references-well-formed``, which already guarantees
    ``kind``/``anchor``/``summary`` are all non-empty strings and
    ``outcome``, if present, is itself a mapping) that is a semantic
    enum-membership question rather than a parse-time shape question, the
    same division of labor ``portability-declared``/
    ``capability-assumption-declared`` already use relative to
    ``manifest-envelope``. Runs independently of references-well-formed (a
    malformed-shape entry can also carry an unrecognized ``kind``, and a
    reader benefits from seeing both findings rather than only the first
    one that happens to fail); when the field isn't a usable list of item
    mappings at all, that precondition failure is already reported by
    references-well-formed, so this reports "nothing to check" instead of
    a redundant or misleading second failure.

    Deliberately does not validate the anchor field's own internal shape
    (a GitHub URL, an external URL, a `method:<skill>` token, or a
    repo-relative path are all legitimate depending on the entry's kind) --
    the existing no-bare-issue-citation scan already enforces the one rule
    that actually matters for an anchor (no bare `#N`/`owner/repo#N`
    citation anywhere in the entry), so a second, narrower anchor-shape
    regex here would just be unenforced ornamentation.
    """
    rule = f"spec.references, if present, has each entry's kind field one of {REFERENCES_KIND_VOCAB}"
    if references is None:
        return CheckResult("references-grammar", True, rule, "not declared (optional)")
    if not (
        isinstance(references, list)
        and references
        and all(isinstance(r, dict) and isinstance(r.get("kind"), str) for r in references)
    ):
        return CheckResult(
            "references-grammar", True, rule, "nothing to check (already reported by references-well-formed)"
        )
    offenders = [r["kind"] for r in references if r["kind"] not in REFERENCES_KIND_VOCAB]
    count = len(offenders)
    return CheckResult(
        "references-grammar",
        not offenders,
        rule,
        "all entries match"
        if not offenders
        else f"{count} entr{'y' if count == 1 else 'ies'} with an unrecognized kind: {offenders[0]!r}",
    )


def _invocation_mode_check(fields: dict[str, str]) -> CheckResult:
    """The two invocation-control frontmatter fields must each carry a
    documented boolean literal, and must not together leave the skill
    invocable by nobody.

    Deliberately narrow. Whether the declared mode *matches the trigger the
    skill's own description and procedure claim* -- a manual-only skill
    promising to fire automatically on some event -- is the semantic
    question, and it stays with the model-judged Invocation-mode fit check
    in references/rubric.md; a script cannot read a trigger sentence's
    intent. What a script CAN decide is exactly two things:

    - a value outside Claude Code's documented boolean literal set, where
      the runtime's own behavior (rejected, or silently read as one branch)
      is Unknown per the runtime-compatibility baseline, so the author's
      intent is unknowable from the file alone; and
    - ``disable-model-invocation`` truthy together with
      ``user-invocable`` false, which removes both invocation paths the
      product documents and leaves a skill nothing can start. That
      combination is never a deliberate state -- unlike either field alone,
      each of which is a documented, useful choice.

    Absent fields pass: the documented defaults (auto-loadable, and visible
    in the / menu) are the normal, overwhelmingly common state.

    Known false positive, disclosed rather than worked around: a value
    carrying a trailing inline YAML comment (``true  # manual only``)
    fails, because ``_parse_frontmatter`` deliberately does not strip
    inline comments and reads the whole remainder as the value. This is
    the same fail-closed-against-an-expected-literal tradeoff
    ``_parse_manifest``'s own docstring already states for the sidecar's
    enum fields, applied here to a frontmatter field for the first time --
    a loud failure naming the exact offending raw value, never a silent
    pass.
    """
    rule = (
        "disable-model-invocation/user-invocable, if present, each carry a "
        "documented boolean literal, and do not together disable both "
        "invocation paths"
    )
    declared = {k: v for k, v in fields.items() if k in INVOCATION_FIELD_DEFAULTS}
    if not declared:
        return CheckResult("invocation-mode-well-formed", True, rule, "not declared (optional)")
    resolved: dict[str, bool] = dict(INVOCATION_FIELD_DEFAULTS)
    malformed: list[str] = []
    for key, raw in declared.items():
        literal = raw.strip().lower()
        if literal in INVOCATION_TRUE_LITERALS:
            resolved[key] = True
        elif literal in INVOCATION_FALSE_LITERALS:
            resolved[key] = False
        else:
            malformed.append(f"{key}: {raw!r}")
    if malformed:
        return CheckResult(
            "invocation-mode-well-formed",
            False,
            rule,
            f"value outside {INVOCATION_TRUE_LITERALS + INVOCATION_FALSE_LITERALS} "
            f"(case-insensitive): {', '.join(malformed)}",
        )
    if resolved["disable-model-invocation"] and not resolved["user-invocable"]:
        return CheckResult(
            "invocation-mode-well-formed",
            False,
            rule,
            "invocable by nobody: disable-model-invocation blocks the model "
            "and user-invocable: false hides it from the / menu",
        )
    return CheckResult(
        "invocation-mode-well-formed",
        True,
        rule,
        "declared: " + ", ".join(f"{k}={str(resolved[k]).lower()}" for k in sorted(declared)),
    )


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
    try:
        text = skill_md.read_text(encoding="utf-8")
    except FileNotFoundError:
        # A SKILL.md that does not exist at all is a different, pre-existing
        # contract this fix does not change: main() already pre-checks
        # ``skill_md.is_file()`` before ever calling check_shape() and
        # returns exit 2 for that case (see test_directory_without_skill_md_
        # returns_2), the same "missing" vs. "present but corrupt" split the
        # sidecar's own is_file() check below draws. Re-raising here (rather
        # than folding "missing" into the "present but unreadable" evidence
        # below) keeps that split intact for any other direct caller too.
        raise
    except (OSError, UnicodeDecodeError) as exc:
        return [
            CheckResult(
                "skill-md-readable", False, "SKILL.md is readable as UTF-8 text", f"unreadable: {type(exc).__name__}"
            )
        ]
    # Always emitted (pass or fail), matching every other check in this
    # module -- not only on the failure path above -- so a caller scanning
    # results for this name never has to treat its absence as a third,
    # ambiguous state.
    results.append(CheckResult("skill-md-readable", True, "SKILL.md is readable as UTF-8 text", "present"))
    frontmatter = _parse_frontmatter(text)
    fields = frontmatter.fields

    description = fields.get("description", "")
    if not description:
        results.append(
            CheckResult("description-present", False, "description present and non-empty", "missing or empty")
        )
    else:
        results.append(CheckResult("description-present", True, "description present and non-empty", "present"))
        results.append(_no_xml_check("description", description))
        results.append(_length_check("description", description, DESCRIPTION_MAX_CHARS))
        results.append(
            _yaml_plain_scalar_safety_check("description", description, "description" in frontmatter.plain_fields)
        )

    name = fields.get("name")
    if name:
        results.append(
            CheckResult("name-pattern", bool(NAME_RE.match(name)), "name is lowercase-hyphenated", repr(name))
        )
        results.append(_length_check("name", name, NAME_MAX_CHARS))
        results.append(_no_xml_check("name", name))
        lname = name.lower()
        reserved_hit = any(word in lname for word in RESERVED_NAME_WORDS)
        results.append(
            CheckResult(
                "name-not-reserved",
                not reserved_hit,
                f"name contains no reserved word {RESERVED_NAME_WORDS}",
                repr(name),
            )
        )

    results.append(_invocation_mode_check(fields))

    body_lines = len(text.splitlines())
    results.append(
        CheckResult(
            "body-length",
            body_lines <= BODY_MAX_LINES,
            f"SKILL.md body <= {BODY_MAX_LINES} lines",
            f"{body_lines} lines",
        )
    )

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
            results.append(
                CheckResult(
                    "manifest-parsable", False, f"{SIDECAR_RELATIVE_PATH} has no malformed top-level lines", evidence
                )
            )
            results.append(
                CheckResult(
                    "manifest-envelope",
                    False,
                    f"apiVersion is {EXPECTED_API_VERSION} and kind is {EXPECTED_KIND}",
                    evidence,
                )
            )
            results.append(
                CheckResult(
                    "metadata-name-matches-dir", False, "metadata.name equals the skill directory name", evidence
                )
            )
            results.append(
                CheckResult("portability-declared", False, f"spec.portability is one of {PORTABILITY_LEVELS}", evidence)
            )
            results.append(
                CheckResult(
                    "capability-assumption-declared",
                    False,
                    f"spec.capabilityAssumption is one of {CAPABILITY_ASSUMPTIONS}",
                    evidence,
                )
            )
            results.append(
                CheckResult(
                    "dependency-policy-declared",
                    False,
                    f"spec.dependencyPolicy, if present, is one of {DEPENDENCY_POLICY_LEVELS}",
                    evidence,
                )
            )
            results.append(
                CheckResult(
                    "references-well-formed",
                    False,
                    "spec.references, if present, is a non-empty list of non-empty strings",
                    evidence,
                )
            )
            results.append(
                CheckResult(
                    "references-grammar",
                    False,
                    'spec.references, if present, has each entry shaped "<kind> | <anchor> | <summary>[ | <outcome>]"',
                    evidence,
                )
            )
            results.append(
                CheckResult(
                    "external-citations-well-formed",
                    False,
                    "spec.externalCitations, if present, is a non-empty list of "
                    "item mappings, each with path/role (role one of "
                    f"{EXTERNAL_CITATION_ROLES}) and no unrecognized key",
                    evidence,
                )
            )
            results.append(
                CheckResult(
                    "external-citations-resolve",
                    False,
                    "every spec.externalCitations path literally appears somewhere "
                    "in SKILL.md or references/*.md (no stale declaration)",
                    evidence,
                )
            )
            results.append(
                CheckResult(
                    "skill-dependencies-well-formed",
                    False,
                    "spec.skillDependencies, if present, is a mapping with only "
                    "requires/relatedTo keys, each -- if present -- a list of "
                    "non-empty strings",
                    evidence,
                )
            )
            results.append(
                CheckResult(
                    "skill-dependencies-resolve",
                    False,
                    "every name in spec.skillDependencies.requires/relatedTo "
                    "resolves to an existing sibling skill directory",
                    evidence,
                )
            )
            results.append(
                CheckResult(
                    "requires-portability-compatible",
                    False,
                    "a non-empty spec.skillDependencies.requires is incompatible with spec.portability: Portable",
                    evidence,
                )
            )
            results.append(
                CheckResult(
                    "lifecycle-well-formed",
                    False,
                    "spec.lifecycle, if present, is a mapping with only "
                    "experimental/deprecated/stable/renamedFrom keys, each "
                    "block sub-key (experimental/deprecated/stable) -- if "
                    "present -- a mapping of its own recognized scalar fields "
                    "with required fields non-empty and since/removeAfter, if "
                    "present, real YYYY-MM-DD dates, and renamedFrom, if "
                    "present, a non-empty scalar string",
                    evidence,
                )
            )
            results.append(
                CheckResult(
                    "lifecycle-deprecated-replacement-resolves",
                    False,
                    "spec.lifecycle.deprecated.replacement, if a non-empty "
                    "string, resolves to an existing sibling skill directory",
                    evidence,
                )
            )
            results.append(
                CheckResult(
                    "experimental-stable-compatible",
                    False,
                    "spec.lifecycle.experimental and spec.lifecycle.stable "
                    "cannot both be present -- a skill cannot be both "
                    "not-yet-graduated and already graduated",
                    evidence,
                )
            )
            results.append(
                CheckResult(
                    "execution-requirements-well-formed",
                    False,
                    "spec.executionRequirements, if present, is a mapping with "
                    "only the tools/packages/network keys; tools, if present, "
                    "is a mapping with only read/write/shell keys, each -- if "
                    "present -- a list of non-empty strings; packages, if "
                    "present, is a mapping keyed by free-form ecosystem "
                    "identifiers, each value -- if present -- a list of "
                    "non-empty strings; network, if present, is a mapping "
                    "with only mode (a disabled/allowlist/unrestricted enum) "
                    "and domains (a list of non-empty strings, non-empty "
                    "only when mode is allowlist)",
                    evidence,
                )
            )
            # Deliberately not the body-marker fallback: a present-but-broken
            # sidecar is authoritative-and-failing, not absent. Running the
            # scan (rather than skipping it) lands extra findings on a skill
            # that is already failing portability-declared -- a false
            # negative in the gate is worse than a false positive.
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
            # Same waiver: the name compared here must be the symlink's own
            # basename, not the real directory it points to (see the
            # metadata-name-matches-dir test for a symlinked skill dir).
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
            dependency_policy_declared_rule = f"spec.dependencyPolicy, if present, is one of {DEPENDENCY_POLICY_LEVELS}"
            dependency_policy = spec.get("dependencyPolicy")
            if not spec_is_mapping:
                # Same precondition failure portability-declared/
                # capability-assumption-declared already report above --
                # "not declared (optional)" would misreport a non-mapping
                # spec as the ordinary optional-and-absent case, mirroring
                # references-well-formed's own guard below.
                results.append(
                    CheckResult(
                        "dependency-policy-declared",
                        False,
                        dependency_policy_declared_rule,
                        f"spec is not a mapping: {spec_raw!r}",
                    )
                )
            elif dependency_policy is None:
                results.append(
                    CheckResult(
                        "dependency-policy-declared",
                        True,
                        dependency_policy_declared_rule,
                        "not declared (optional, treated as StdlibOnly-equivalent)",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        "dependency-policy-declared",
                        dependency_policy in DEPENDENCY_POLICY_LEVELS,
                        dependency_policy_declared_rule,
                        repr(dependency_policy),
                    )
                )
            references = spec.get("references")
            references_well_formed_rule = (
                "spec.references, if present, is a non-empty list of "
                "item mappings, each with kind/anchor/summary (and no "
                f"unrecognized key), summary <= {REFERENCES_ENTRY_MAX_CHARS} "
                "chars"
            )
            is_ref_item = lambda r: (  # noqa: E731 -- local, single use
                isinstance(r, dict)
                and isinstance(r.get("kind"), str)
                and isinstance(r.get("anchor"), str)
                and isinstance(r.get("summary"), str)
            )
            if not spec_is_mapping:
                # spec itself failed to parse as a mapping (e.g. "spec:
                # some-scalar"), the same precondition failure
                # portability-declared/capability-assumption-declared
                # already report above -- "not declared" would misreport
                # this as the ordinary optional-and-absent case.
                results.append(
                    CheckResult(
                        "references-well-formed",
                        False,
                        references_well_formed_rule,
                        f"spec is not a mapping: {spec_raw!r}",
                    )
                )
            elif malformed_reference_items:
                # An item whose own opening line was unrecognizable, whose
                # first key was unrecognized, whose indent didn't match the
                # rest of its own list, or that was missing a required
                # field by the time it closed was already flagged by the
                # parser -- fail loudly instead of reporting on whatever
                # partial item it was excluded in favor of, even if the
                # rest of the list otherwise looks clean.
                count = len(malformed_reference_items)
                results.append(
                    CheckResult(
                        "references-well-formed",
                        False,
                        references_well_formed_rule,
                        f"{count} malformed entr{'y' if count == 1 else 'ies'}: {malformed_reference_items[0]!r}",
                    )
                )
            elif unknown_reference_item_keys:
                count = len(unknown_reference_item_keys)
                results.append(
                    CheckResult(
                        "references-well-formed",
                        False,
                        references_well_formed_rule,
                        f"{count} unknown key{'' if count == 1 else 's'}: {unknown_reference_item_keys[0]!r}",
                    )
                )
            elif references is None:
                results.append(
                    CheckResult("references-well-formed", True, references_well_formed_rule, "not declared (optional)")
                )
            elif not (isinstance(references, list) and references and all(is_ref_item(r) for r in references)):
                ref_evidence = "empty list" if references == [] else f"not a list of item mappings: {references!r}"
                results.append(CheckResult("references-well-formed", False, references_well_formed_rule, ref_evidence))
            else:
                oversized = [r for r in references if len(r["summary"]) > REFERENCES_ENTRY_MAX_CHARS]
                if oversized:
                    results.append(
                        CheckResult(
                            "references-well-formed",
                            False,
                            references_well_formed_rule,
                            f"{len(oversized)} entr{'y' if len(oversized) == 1 else 'ies'} "
                            f"over {REFERENCES_ENTRY_MAX_CHARS} chars: "
                            f"{len(oversized[0]['summary'])} chars, kind="
                            f"{oversized[0].get('kind')!r}",
                        )
                    )
                else:
                    ref_count = len(references)
                    ref_noun = "entry" if ref_count == 1 else "entries"
                    results.append(
                        CheckResult(
                            "references-well-formed", True, references_well_formed_rule, f"{ref_count} {ref_noun}"
                        )
                    )
            results.append(_references_grammar_check(references))
            if isinstance(references, list) and references:
                ref_texts = []
                for r in references:
                    if not isinstance(r, dict):
                        continue
                    ref_texts.append(str(r.get("anchor", "")))
                    ref_texts.append(str(r.get("summary", "")))
                    outcome = r.get("outcome")
                    if isinstance(outcome, dict):
                        ref_texts.extend(str(v) for v in outcome.values())
                sidecar_citation_sources.append(("metadata/gitapex.yaml:spec.references", "\n".join(ref_texts)))
            external_citations = spec.get("externalCitations")
            external_citations_well_formed_rule = (
                "spec.externalCitations, if present, is a non-empty list of "
                "item mappings, each with a path rooted at evals/ or docs/ "
                "and a role one of "
                f"{EXTERNAL_CITATION_ROLES}, and no unrecognized key"
            )
            is_ext_citation_item = lambda c: (  # noqa: E731 -- local, single use
                isinstance(c, dict)
                and isinstance(c.get("path"), str)
                and bool(EXTERNAL_CITATION_PATH_RE.match(c["path"]))
                and c.get("role") in EXTERNAL_CITATION_ROLES
            )
            if not spec_is_mapping:
                results.append(
                    CheckResult(
                        "external-citations-well-formed",
                        False,
                        external_citations_well_formed_rule,
                        f"spec is not a mapping: {spec_raw!r}",
                    )
                )
            elif malformed_external_citation_items:
                count = len(malformed_external_citation_items)
                results.append(
                    CheckResult(
                        "external-citations-well-formed",
                        False,
                        external_citations_well_formed_rule,
                        f"{count} malformed entr{'y' if count == 1 else 'ies'}: {malformed_external_citation_items[0]!r}",
                    )
                )
            elif unknown_external_citation_item_keys:
                count = len(unknown_external_citation_item_keys)
                results.append(
                    CheckResult(
                        "external-citations-well-formed",
                        False,
                        external_citations_well_formed_rule,
                        f"{count} unknown key{'' if count == 1 else 's'}: {unknown_external_citation_item_keys[0]!r}",
                    )
                )
            elif external_citations is None:
                results.append(
                    CheckResult(
                        "external-citations-well-formed",
                        True,
                        external_citations_well_formed_rule,
                        "not declared (optional)",
                    )
                )
            elif not (
                isinstance(external_citations, list)
                and external_citations
                and all(is_ext_citation_item(c) for c in external_citations)
            ):
                ext_evidence = (
                    "empty list"
                    if external_citations == []
                    else f"not a list of item mappings with a valid evals/docs path and role: {external_citations!r}"
                )
                results.append(
                    CheckResult(
                        "external-citations-well-formed", False, external_citations_well_formed_rule, ext_evidence
                    )
                )
            else:
                ext_count = len(external_citations)
                ext_noun = "entry" if ext_count == 1 else "entries"
                results.append(
                    CheckResult(
                        "external-citations-well-formed",
                        True,
                        external_citations_well_formed_rule,
                        f"{ext_count} {ext_noun}",
                    )
                )
                # Only a genuinely well-formed list feeds external-citations-
                # resolve/the inline-citation rescue further down -- a
                # malformed or absent declaration has nothing valid to
                # resolve against, matching how a malformed spec.references
                # never reaches sidecar_citation_sources above.
                external_citations_declared = external_citations
            lifecycle_raw = spec.get("lifecycle") if spec_is_mapping else None
            lifecycle_dict = lifecycle_raw if isinstance(lifecycle_raw, dict) else {}
            for lifecycle_key in ("experimental", "deprecated"):
                lifecycle_block = lifecycle_dict.get(lifecycle_key)
                if isinstance(lifecycle_block, dict):
                    reason_text = lifecycle_block.get("reason")
                    if isinstance(reason_text, str) and reason_text:
                        sidecar_citation_sources.append(
                            (f"metadata/gitapex.yaml:spec.lifecycle.{lifecycle_key}.reason", reason_text)
                        )
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

    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        nested = sorted(
            str(p.relative_to(refs_dir))
            for p in refs_dir.rglob("*")
            if p.is_file() and p.parent != refs_dir and not _is_ignorable(p)
        )
        results.append(
            CheckResult(
                "references-flat",
                not nested,
                "references/ files are one level deep",
                "nested: " + ", ".join(nested) if nested else "flat",
            )
        )
        for ref in sorted(refs_dir.iterdir()):
            if not ref.is_file() or _is_ignorable(ref):
                continue
            if ref.suffix.lower() != ".md":
                # A non-Markdown dependency file (e.g. a bundled JSON
                # schema) still gets references-flat and the junk filter
                # above, but TOC/link/anchor are Markdown-navigation
                # concepts that do not apply to it -- skip rather than
                # fail it against a heading convention it was never
                # written to have.
                continue
            try:
                ref_text = ref.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue  # skip binary/unreadable junk, don't abort the run
            n = len(ref_text.splitlines())
            if n > TOC_MIN_LINES:
                has_toc = bool(TOC_RE.search(ref_text))
                results.append(
                    CheckResult(
                        f"toc:{ref.name}",
                        has_toc,
                        f"reference over {TOC_MIN_LINES} lines has a TOC",
                        f"{n} lines, " + ("TOC found" if has_toc else "no TOC"),
                    )
                )
            ref_body = "\n".join(_body_after_frontmatter(ref_text))
            ref_offenders = _out_of_skill_link_targets(ref_body, skill_dir, source_dir=ref.parent)
            results.append(
                CheckResult(
                    f"links-inside-skill:{ref.name}",
                    not ref_offenders,
                    "Markdown link targets resolve inside the skill's own directory",
                    "all inside" if not ref_offenders else "outside: " + ", ".join(ref_offenders),
                )
            )
            anchor_slug_cache.setdefault(ref, _heading_slugs(ref_body))
            ref_broken_anchors = _broken_anchor_targets(ref_body, ref, skill_dir, anchor_slug_cache)
            results.append(
                CheckResult(
                    f"anchor-targets-resolve:{ref.name}",
                    not ref_broken_anchors,
                    "Markdown link #fragments resolve to a real heading anchor in their target file",
                    "all resolve" if not ref_broken_anchors else "broken: " + ", ".join(ref_broken_anchors),
                )
            )

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
        if not external_citations_declared:
            results.append(
                CheckResult(
                    "external-citations-resolve",
                    True,
                    "every spec.externalCitations path literally appears somewhere "
                    "in SKILL.md or references/*.md (no stale declaration)",
                    "not declared (optional)",
                )
            )
        else:
            stale_external_citations = _external_citation_declaration_offenders(
                external_citations_declared, skill_md, skill_dir, body
            )
            results.append(
                CheckResult(
                    "external-citations-resolve",
                    not stale_external_citations,
                    "every spec.externalCitations path literally appears somewhere "
                    "in SKILL.md or references/*.md (no stale declaration)",
                    "all resolve" if not stale_external_citations else "stale: " + ", ".join(stale_external_citations),
                )
            )

    results.extend(_issue_citation_checks(skill_md, skill_dir, body, extra_sources=sidecar_citation_sources))
    results.extend(_cross_skill_citation_checks(skill_md, skill_dir, body, anchor_slug_cache))
    results.extend(_mechanism_fit_checks(skill_md, skill_dir, body))
    results.extend(_illustrative_model_id_checks(skill_md, skill_dir, body))
    results.extend(_raw_placeholder_checks(skill_md, skill_dir, body))
    results.extend(_step_location_checks(skill_md, skill_dir, body))
    results.extend(_no_voodoo_constant_checks(skill_md, skill_dir, body))
    results.extend(_script_execution_intent_checks(skill_md, skill_dir, body))
    if _is_portable(body, sidecar_portability):
        declared_citation_paths = frozenset(
            c["path"] for c in external_citations_declared if isinstance(c.get("path"), str)
        )
        results.extend(_portable_path_citation_checks(skill_md, skill_dir, body, declared_citation_paths))
        results.extend(_portable_skill_citation_checks(skill_md, skill_dir, body))
        results.extend(_out_of_skill_scripts_checks(skill_md, skill_dir, body))

    return results


def _external_citation_declaration_offenders(
    external_citations: list[dict[str, object]], skill_md: Path, skill_dir: Path, body: list[str]
) -> list[str]:
    """Return each ``spec.externalCitations`` declared ``path`` (issue
    #1055) with no literal, exact match against a real citation-shaped
    token anywhere in SKILL.md or references/*.md -- a stale declaration
    naming a citation this skill no longer actually carries. Matches
    ``_citation_sources``' own raw, unfenced text (a declared path
    legitimately citing an illustrative fenced example is still a real
    citation this check should find), the same exact-literal matching Q3
    of issue #1055's design decision settled on -- deliberately not a
    regex or line-anchored match, mirroring how a declaration is expected
    to quote its own citation's exact text.

    Matched against ``REPO_PATH_CITATION_RE``'s own extracted tokens, not
    a raw substring test over the whole haystack: a plain ``path in
    haystack`` check would let a declaration for ``docs/a.md`` falsely
    "resolve" against a real, different citation like ``docs/a.mdx`` --
    ``docs/a.md`` is a literal prefix of it -- since the character class
    ``REPO_PATH_CITATION_RE`` accepts (including ``.``) makes prefix
    overlap between two distinct real citations possible. Anchoring to
    the regex's own extracted tokens keeps "exact literal match" exact.

    A trailing ``".,;:)"`` is stripped from each extracted token before
    the match, the same established fix (a prior review finding) already
    applied to ``SCRIPTS_PATH_BARE_RE``'s own bare-prose matches below:
    sentence-final punctuation immediately after a real extension (e.g.
    "documented in docs/a.md.") is captured by this regex's own character
    class -- which must include "." for real extensions -- and would
    otherwise make a genuine, correctly declared citation report as stale
    purely because of how its sentence ends; no real path ends in one of
    these characters, so stripping them is never lossy.
    """
    haystack = "\n".join(source_text for _label, source_text in _citation_sources(skill_md, skill_dir, body))
    cited_tokens = frozenset(m.group(0).rstrip(".,;:)") for m in REPO_PATH_CITATION_RE.finditer(haystack))
    offenders = []
    for entry in external_citations:
        path = entry.get("path")
        if isinstance(path, str) and path and path not in cited_tokens:
            offenders.append(path)
    return offenders


def _citation_sources(skill_md: Path, skill_dir: Path, body: list[str]) -> list[tuple[str, str]]:
    """Return (label, body-text) for SKILL.md and every references/ file,
    Markdown or not -- the shared source set every prose citation/
    placeholder/mechanism-fit check built on this function scans.
    Deliberately NOT limited to references/*.md: a bundled non-Markdown
    dependency file (e.g. a JSON schema) still carries author-written
    English in its own description strings, and exempting it by extension
    would let a bare issue citation, an illustrative model identifier, an
    unhedged repo-path citation, or a raw placeholder hide from every one
    of these checks just by living in a `.json`/`.yaml`/`.txt` file instead
    of a `.md` one -- a real bypass a corpus-wide adversarial pass found
    when this exemption was first tried (issue #834 follow-up). The
    Markdown-syntax-specific checks (TOC-heading presence,
    links-inside-skill, anchor-targets-resolve) stay .md-only, in the
    separate references/ loop below this function -- those really are
    Markdown conventions a non-Markdown file has no notion of; the prose
    checks built on this function are not.
    """
    sources: list[tuple[str, str]] = [(skill_md.name, "\n".join(body))]
    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        for ref in sorted(refs_dir.iterdir()):
            if not ref.is_file() or _is_ignorable(ref):
                continue
            try:
                ref_text = ref.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            sources.append((f"references/{ref.name}", "\n".join(_body_after_frontmatter(ref_text))))
    return sources


def _issue_citation_checks(
    skill_md: Path, skill_dir: Path, body: list[str], extra_sources: list[tuple[str, str]] | None = None
) -> list[CheckResult]:
    """The bare GitHub issue/PR-number citation scan over SKILL.md body,
    references/*.md, and (unlike every other check built on
    ``_citation_sources``) the metadata/gitapex.yaml sidecar's own
    spec.references entries and lifecycle.experimental/deprecated.reason
    text, passed in via ``extra_sources``. A bare number in the sidecar
    loses its meaning the moment the sidecar travels with its skill
    directory to another repository, so this scan covers the sidecar's
    own free text too. A full
    ``https://github.com/...`` URL contains no bare ``#N`` and so is never
    flagged here -- that is what makes a full URL the only way left to cite
    an issue from the sidecar, with no separate format regex needed. Runs
    unconditionally on every skill regardless of declared portability level
    -- unlike ``_portable_path_citation_checks`` below, the caller does not
    gate this one on ``_is_portable``.

    ``extra_sources`` (the sidecar text) is scanned with the bare
    ``ISSUE_CITATION_RE`` regex directly, NOT through
    ``_portable_citation_offenders``/``_strip_illustrative_spans`` the way
    SKILL.md/references/*.md are: that
    stripping exempts an inline-code span (`` `#149` ``) as an
    "already illustrative, does not resolve live" citation form -- true in
    rendered Markdown, where backticks make GitHub's auto-linker leave the
    text alone, but meaningless inside a YAML string scalar, where a
    backtick is just a literal character. Applying that exemption to the
    sidecar would let a provenance entry write "fixed in `` `gitapex#25` ``"
    and pass unflagged, defeating the full-URL-only rule this check exists
    to enforce there.
    """
    issue_hits: list[str] = []
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        defenced = _blank_fenced_blocks(source_text)
        issues, _paths = _portable_citation_offenders(defenced)
        issue_hits += [f"{label}:{c}" for c in issues]
    for label, source_text in extra_sources or ():
        issue_hits += [f"{label}:{c}" for c in _dedup(m.group(0) for m in ISSUE_CITATION_RE.finditer(source_text))]

    return [
        CheckResult(
            "no-bare-issue-citation",
            not issue_hits,
            "No bare-prose GitHub issue/PR-number citation, at any portability level",
            "none" if not issue_hits else "found: " + ", ".join(issue_hits),
        ),
    ]


def _cross_skill_citation_checks(
    skill_md: Path, skill_dir: Path, body: list[str], slug_cache: dict[Path, frozenset[str] | None]
) -> list[CheckResult]:
    """Every cross-skill "file+heading" citation
    (CROSS_SKILL_CITATION_RE) in SKILL.md or references/*.md must resolve --
    the sibling skill directory exists (a cheaper version of this,
    directory-only, is already covered by ``related-skill-references-resolve``
    and ``skill-dependencies-resolve``), the named file exists inside that
    sibling's own references/ directory, and a heading matching the cited
    text actually exists in that file -- reusing ``_github_slug``/
    ``_heading_slugs`` verbatim, the same GitHub heading-slug logic
    ``anchor-targets-resolve`` already implements for real Markdown links.
    Unlike a real Markdown link, a citation in this prose shape can never be
    a same-repo relative link (a cross-skill target cannot legally resolve
    inside the CITING skill's own directory, per ``links-inside-skill``), so
    neither ``links-inside-skill`` nor ``anchor-targets-resolve`` ever sees
    it -- this is the dedicated backstop for exactly that gap. Runs
    unconditionally, at every portability level, the same as
    ``no-bare-issue-citation`` above: a dangling cross-skill citation is a
    defect regardless of declared portability.

    Each cited heading is slugged with its OWN fresh, empty occurrence
    table (not the target file's real per-document dedup table) -- a prose
    citation names a heading's TEXT, and this checker has no way to know
    which same-slug occurrence (1st, 2nd, ...) the author meant, so it
    accepts a match against the base (first-occurrence) slug only.

    ``slug_cache`` is ``check_shape``'s own ``anchor_slug_cache`` -- the
    SAME ``Path``-keyed cache ``anchor-targets-resolve`` already shares
    across SKILL.md and every references/*.md file -- reused here (via
    ``_cached_target_heading_slugs``) rather than this function keeping an
    independent ``(skill_name, filename)``-keyed cache of its own: two
    caches with the identical read-once/frontmatter-strip/heading-slugs/
    None-on-error contract would have to be kept in sync by hand, and a
    sibling skill's own SKILL.md or references/*.md file cited here might
    already be a cached anchor target from this same run's earlier checks.
    """
    offenders: list[str] = []
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        defenced = _blank_fenced_blocks(source_text)
        for m in CROSS_SKILL_CITATION_RE.finditer(defenced):
            skill_name, filename, heading_text = m.group(1), m.group(2), m.group(3)
            citation = m.group(0)
            sibling_dir = skill_dir.parent / skill_name
            if not sibling_dir.is_dir():
                offenders.append(f"{label}:{citation} (no such sibling skill)")
                continue
            target = sibling_dir / "references" / filename
            slugs = _cached_target_heading_slugs(target, slug_cache)
            if slugs is None:
                offenders.append(f"{label}:{citation} (file not found)")
                continue
            if _github_slug(heading_text, {}) not in slugs:
                offenders.append(f"{label}:{citation} (heading not found)")
    offenders = _dedup(offenders)
    return [
        CheckResult(
            "cross-skill-citation-resolves",
            not offenders,
            'Every "SKILL-NAME\'s `references/FILE.md` HEADING section" '
            "cross-skill citation resolves to a real sibling skill, file, "
            "and heading",
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


def _mechanism_fit_citation_offenders(body_text: str) -> list[str]:
    """Return each '### ' subsection heading text nested under
    a '## Mechanism fit' heading in ``body_text`` that carries neither a
    '[label]'-style citation (MECHANISM_FIT_CITATION_RE) nor the literal
    phrase "this repository's own reasoned extension" --
    mechanizing the completeness rule references/rubric.md's own
    Mechanism-fit section intro already states in prose ("the primary
    source and the reasoning behind each check").

    Generic over ANY document, not hardcoded to rubric.md's filename -- a
    document with no '## Mechanism fit' heading at all contributes zero
    offenders (the same "not applicable, trivially passes" shape the
    references-flat/TOC checks already use for a precondition that does not
    apply to every skill). Only a level-2 '## Mechanism fit' heading is
    recognized (case-insensitive on its text, exact heading level); its own
    section span runs from immediately after it to the next heading at
    level <= 2 (or end of document), and only '### ' (level-3) headings
    inside that span count as its subsections -- a deeper '#### ' heading
    nested under a level-3 subsection is part of that subsection's own
    content, not a sibling subsection needing its own citation.
    """
    defenced = _blank_fenced_blocks(body_text)
    headings = [(m.start(), len(m.group(1)), m.group(2)) for m in MECHANISM_FIT_HEADING_RE.finditer(defenced)]
    offenders: list[str] = []
    for i, (_start, level, text) in enumerate(headings):
        if level != 2 or text.strip().lower() != "mechanism fit":
            continue
        section_end = next((s for s, lv, _t in headings[i + 1 :] if lv <= 2), len(defenced))
        subsections = [(s, t) for s, lv, t in headings[i + 1 :] if s < section_end and lv == 3]
        for j, (sub_start, sub_text) in enumerate(subsections):
            sub_end = subsections[j + 1][0] if j + 1 < len(subsections) else section_end
            content = defenced[sub_start:sub_end]
            has_citation = bool(MECHANISM_FIT_CITATION_RE.search(content))
            has_phrase = MECHANISM_FIT_REASONED_EXTENSION_PHRASE in content.lower()
            if not (has_citation or has_phrase):
                offenders.append(sub_text.strip())
    return offenders


def _mechanism_fit_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """The check_shape() entry point for _mechanism_fit_citation_offenders,
    scanning SKILL.md and every references/*.md file the same way every
    other _citation_sources-based check does. Runs unconditionally, at
    every portability level -- a missing citation is a completeness defect,
    not a portability one.
    """
    offenders: list[str] = []
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        for heading in _mechanism_fit_citation_offenders(source_text):
            offenders.append(f"{label}:{heading}")
    offenders = _dedup(offenders)
    return [
        CheckResult(
            "mechanism-fit-subsections-cite-sources",
            not offenders,
            "Every '### ' subsection under a '## Mechanism fit' heading "
            "carries a '[label]'-style citation or the literal phrase "
            '"this repository\'s own reasoned extension"',
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


def _illustrative_model_id_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """docs/skill-authoring-standards.md rule 1: no real, current Claude
    model identifier as illustrative content in SKILL.md or references/*.md,
    even inside a fenced "bad example" that is itself flagged and fixed.
    Unlike every citation check in this module, this deliberately does NOT
    strip fenced code blocks or inline code spans first: rule 1 is about the
    identifier ever appearing as illustrative content at all, not about it
    resolving live, so a real model ID inside a worked example is exactly
    what this check exists to catch, not something to exempt.

    One narrow exemption: a match that falls entirely inside an
    ANTHROPIC_DOC_CITATION_RE span (a real citation URL to Anthropic's own
    docs, not illustrative content) does not count as an offender -- see
    that constant's own docstring for why.
    """
    offenders: list[str] = []
    for label, text in _citation_sources(skill_md, skill_dir, body):
        citation_spans = [m.span() for m in ANTHROPIC_DOC_CITATION_RE.finditer(text)]
        for m in ILLUSTRATIVE_MODEL_ID_RE.finditer(text):
            if any(start <= m.start() and m.end() <= end for start, end in citation_spans):
                continue
            offenders.append(f"{label}:{m.group(0)}")
    offenders = _dedup(offenders)
    return [
        CheckResult(
            "no-illustrative-model-identifier",
            not offenders,
            "No real, current Claude model identifier as illustrative "
            "content (docs/skill-authoring-standards.md rule 1)",
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


def _raw_placeholder_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """docs/skill-authoring-standards.md rule 4: no angle-bracket
    placeholder ("<NAME>") in raw prose -- outside a code span or fenced
    code block -- in SKILL.md or references/*.md. GitHub's Markdown/HTML
    rendering drops an unescaped "<NAME>" silently, corrupting the
    surrounding text.

    A placeholder whose matching closing tag ("</name>", same name,
    case-insensitive) also appears in the same bare prose is exempt: that
    open/close pairing marks a genuine HTML-shaped tag being quoted as
    content, not an unclosed fill-in-the-blank placeholder -- e.g. this
    repository's own untrusted-input-triage worked example, which
    deliberately quotes a fake "<system-reminder>...</system-reminder>"
    payload as adversarial-input content.
    """
    offenders: list[str] = []
    for label, text in _citation_sources(skill_md, skill_dir, body):
        bare = _strip_illustrative_spans(_blank_fenced_blocks(text))
        lowered = bare.lower()
        for match in RAW_PLACEHOLDER_OPEN_RE.finditer(bare):
            if f"</{match.group(1).lower()}>" in lowered:
                continue
            offenders.append(f"{label}:{match.group(0)}")
    offenders = _dedup(offenders)
    return [
        CheckResult(
            "no-raw-angle-bracket-placeholder",
            not offenders,
            "No angle-bracket placeholder in raw prose (docs/skill-authoring-standards.md rule 4)",
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


def _step_location_offenders(body_text: str) -> list[str]:
    """Issue #192 (Refs #93 repair 1): fail when the same numbered step
    (STEP_NUM_RE) is asserted to execute in two different locations
    (STEP_LOCATION_ASSERTION_RE) within ``body_text``, with neither
    mention explicitly ceding authority to the other
    (STEP_LOCATION_CEDING_PHRASE) -- the exact defect shape issue #93's
    own incident found (SKILL.md's Procedure intro said step 6 "stays in
    the main thread" while its Subagent dispatch section required step 6
    to "execute inside" the dispatch, with nothing reconciling the two).

    Scans sentence-by-sentence (``_SENTENCE_SPLIT_RE``, this file's own
    sentence tokenizer, shared with the skill-fact-claim hedge-proximity
    check) rather than the whole document at once: a step number and a
    location assertion are only read as related when they co-occur in the
    SAME sentence -- two unrelated sentences that separately happen to
    mention some step number and some location phrase, with no shared
    clause connecting them, are not the contradiction this check exists to
    catch. Two mentions of the SAME step number with the SAME location
    phrase are not a contradiction either (restating one fact twice is not
    a conflict) -- only genuinely distinct location phrases for one step
    number count. A sentence naming more than one step number, or
    asserting more than one location phrase, is skipped entirely (a
    review finding: pairing the sentence's FIRST step-number match with
    its FIRST location match via independent ``.search()`` calls can
    misattribute one step's location claim to a different step number
    named in the same sentence) rather than guessed at -- unambiguous
    single-step-number, single-location-phrase sentences are the only
    shape this check reads, matching this check's own deliberately narrow
    scope.

    Illustrative spans (inline code, Markdown links, absolute URLs -- see
    ``_strip_illustrative_spans``) are stripped before scanning, the same
    as every other bare-prose check in this file (a review finding: an
    inline-code-quoted illustration of issue #93's own incident -- this
    repository's own established way of documenting a "bad example," see
    e.g. rubric.md's citation checks -- would otherwise trip this check as
    a real contradiction).

    A ceding phrase only resolves the SPECIFIC pair of distinct location
    phrases where at least one side's own sentence carries it, not every
    contradiction recorded for that step number (a review finding: one
    ceding sentence would otherwise silently drop an unrelated, genuinely
    unreconciled third location for the same step).
    """
    bare = _strip_illustrative_spans(_blank_fenced_blocks(body_text))
    by_step: dict[str, list[tuple[str, bool]]] = {}
    for sentence in _SENTENCE_SPLIT_RE.split(bare):
        step_matches = list(STEP_NUM_RE.finditer(sentence))
        location_matches = list(STEP_LOCATION_ASSERTION_RE.finditer(sentence))
        if len(step_matches) != 1 or len(location_matches) != 1:
            continue
        step_num = step_matches[0].group(1)
        has_ceding = STEP_LOCATION_CEDING_PHRASE in sentence.lower()
        phrase = " ".join(location_matches[0].group(0).split()).rstrip(".,;:")
        by_step.setdefault(step_num, []).append((phrase, has_ceding))

    offenders: list[str] = []
    for step_num in sorted(by_step, key=int):
        phrase_ceding: dict[str, bool] = {}
        for phrase, ceding in by_step[step_num]:
            phrase_ceding[phrase] = phrase_ceding.get(phrase, False) or ceding
        distinct_phrases = list(phrase_ceding)
        if len(distinct_phrases) < 2:
            continue
        unresolved = [
            (a, b)
            for i, a in enumerate(distinct_phrases)
            for b in distinct_phrases[i + 1 :]
            if not (phrase_ceding[a] or phrase_ceding[b])
        ]
        if not unresolved:
            continue
        offenders.append(f"step {step_num}: " + "; ".join(f"{a!r} vs. {b!r}" for a, b in unresolved))
    return offenders


def _step_location_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """The check_shape() entry point for _step_location_offenders, scanning
    SKILL.md and every references/*.md file the same way every other
    _citation_sources-based check does -- each file checked independently,
    never merging step numbers across files (a references/*.md file's own
    local "step 3" is unrelated to SKILL.md's own step 3). Runs
    unconditionally, at every portability level -- a same-file internal
    contradiction about where a step executes is a completeness/consistency
    defect, not a portability one, the same reasoning
    mechanism-fit-subsections-cite-sources above already uses.
    """
    offenders: list[str] = []
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        for offender in _step_location_offenders(source_text):
            offenders.append(f"{label}:{offender}")
    offenders = _dedup(offenders)
    return [
        CheckResult(
            "no-step-location-contradiction",
            not offenders,
            "No 'step N'/'steps N-M' reference is asserted to execute in "
            "two different locations without one explicitly ceding "
            f"authority (a nearby {STEP_LOCATION_CEDING_PHRASE!r})",
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


# (check-name, citation_re, hedge_phrases, human-readable citation-kind
# label) for each Portable-only inline-code citation check. Table-driven so
# a third citation kind is "add a row", not "copy the block a third time" --
# ``_portable_path_citation_checks`` below builds one ``CheckResult`` per
# row from a single loop instead of a hand-duplicated block per kind. The
# repo-path row uses ``GENERIC_ROLE_HEDGE_PHRASES`` (issue #1051), the
# narrow "the calling repository"/"the target repository" half of
# ``HEDGE_PHRASES`` only -- see that constant's own comment for why: those
# two phrases mark a citation as a generic illustrative path name for
# whatever repository the skill lands in, never a citation to THIS origin
# repository's own real file, so there is nothing to vendor-break in the
# first place. The other half of ``HEDGE_PHRASES`` ("this repository" /
# "gitapex") never rescued a match here even before issue #1051 -- it marks
# the opposite, a deliberate real-file reference, which is exactly the #220
# failure shape (a hedge discloses a real dependency without removing it).
# The issue-number row keeps its own, separate hedge-phrase list unchanged
# -- issue #1051 only revisits the repo-path row's escape, not the
# issue-number citation rule this table also drives.
_INLINE_CITATION_CHECK_SPECS = (
    ("portable-no-inline-path-citation", REPO_PATH_CITATION_RE, GENERIC_ROLE_HEDGE_PHRASES, "origin-repository path"),
    ("portable-no-unhedged-inline-issue-citation", ISSUE_CITATION_RE, ISSUE_CITATION_HEDGE_PHRASES, "issue/PR-number"),
)


def _portable_path_citation_checks(
    skill_md: Path, skill_dir: Path, body: list[str], declared_citation_paths: frozenset[str] = frozenset()
) -> list[CheckResult]:
    """The Portable-only repo-path and inline-code-issue-number self-citation
    checks over SKILL.md body and references/*.md. Each source contributes
    its offenders labelled by file, so a failure points at the exact file to
    fix. Only called when ``_is_portable`` is true (see ``check_shape``) --
    unlike the bare-prose issue-number scan in ``_issue_citation_checks``,
    every check here stays level-gated (see the module docstring's
    bare-issue-citation entry for why the bare-prose scan is different,
    and the issue-number citation entry for why the inline-code
    issue-number check joins the two repo-path checks here rather than
    the unconditional one).

    ``declared_citation_paths`` (issue #1055) is the skill's own
    well-formed ``spec.externalCitations`` path set -- passed through to
    ``portable-no-inline-path-citation`` only (via ``_inline_citation_offenders``'s
    ``declared_paths``), supplementing ``GENERIC_ROLE_HEDGE_PHRASES`` rather
    than replacing it, per this issue's own design decision. Deliberately
    NOT applied to ``portable-no-repo-path-citation`` (the bare-prose form)
    or the issue-number spec -- both stay out of scope, per the issue's own
    Non-goals.
    """
    path_hits: list[str] = []
    inline_hits_per_spec: list[list[str]] = [[] for _ in _INLINE_CITATION_CHECK_SPECS]
    inline_specs = tuple(
        (
            citation_re,
            hedge_phrases,
            declared_citation_paths if name == "portable-no-inline-path-citation" else frozenset(),
        )
        for name, citation_re, hedge_phrases, _label in _INLINE_CITATION_CHECK_SPECS
    )
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        # Fence-blanked once and shared -- the bare-prose scan and the
        # inline-code scan (itself now one pass covering every spec in
        # _INLINE_CITATION_CHECK_SPECS) both need fenced code excluded the
        # same way, and source_text can be a multi-hundred-line references/
        # file.
        defenced = _blank_fenced_blocks(source_text)
        _issues, paths = _portable_citation_offenders(defenced)
        path_hits += [f"{label}:{c}" for c in paths]
        offenders_per_spec = _inline_citation_offenders(defenced, inline_specs)
        for spec_idx, offenders in enumerate(offenders_per_spec):
            inline_hits_per_spec[spec_idx] += [f"{label}:{c}" for c in offenders]

    results = [
        CheckResult(
            "portable-no-repo-path-citation",
            not path_hits,
            "Portable content has no bare-prose origin-repository path citation",
            "none" if not path_hits else "found: " + ", ".join(path_hits),
        ),
    ]
    # inline_hits_per_spec is built as one list per spec, so strict=True can
    # only fire if that construction changes out from under this loop.
    for (check_name, _citation_re, hedge_phrases, kind_label), hits in zip(
        _INLINE_CITATION_CHECK_SPECS, inline_hits_per_spec, strict=True
    ):
        rule = (
            f"Portable content has no inline-code {kind_label} citation "
            f"without an approved hedge phrase {hedge_phrases} in its own "
            "sentence or the sentence immediately before it"
        )
        results.append(
            CheckResult(
                check_name,
                not hits,
                rule,
                "none" if not hits else "found: " + ", ".join(hits),
            )
        )
    return results


def _portable_skill_fact_claim_offenders(defenced_text: str, skill_dir: Path) -> list[str]:
    """Return each possessive sibling-skill citation
    (PORTABLE_SKILL_FACT_CLAIM_RE) in ``defenced_text`` that names a real
    sibling skill directory, asserts its claim with "already" in the same
    clause, and has no approved hedge phrase (HEDGE_PHRASES -- the same
    list ``portable-no-repo-path-citation`` uses; the underlying meaning is
    the same regardless of whether the citation is a path, an issue
    number, or a skill name: a disclosed, deliberate same-repo dependency)
    in that clause or the sentence immediately before it, within the same
    paragraph.

    See PORTABLE_SKILL_FACT_CLAIM_RE's own comment for why all three
    conditions (possessive shape, "already" nearby, real sibling) are
    required together -- each one alone was corpus-validated to produce
    false positives against this repository's own shipped skills.

    The hedge lookback is bounded to the sentence immediately before the
    citation's own clause, within the current paragraph (via
    `_PARAGRAPH_SPLIT_RE` + `_SENTENCE_SPLIT_RE`, the same hedge-proximity
    boundary `_inline_citation_offenders` uses: "own sentence or the
    sentence immediately before it"), not a fixed character count and not
    the whole paragraph: a fixed character count would let an unrelated
    hedge word in a prior, unconnected sentence satisfy an unhedged
    citation, and a whole-paragraph lookback would let a hedge two-or-more
    sentences back leak in (see `test_hedge_in_unrelated_earlier_sentence_
    does_not_count`). Inline-code spans are blanked out of the search text
    first, matching ``_inline_citation_offenders``'s own rule ("a citation
    cannot self-satisfy the requirement merely because its own text
    happens to contain a hedge word") -- otherwise an unrelated
    inline-code token elsewhere in the paragraph (e.g. a
    `` `docs/gitapex-notes.md` `` path) could satisfy the hedge search
    purely because "gitapex" is one of HEDGE_PHRASES, with no bearing on
    this citation at all.
    """
    offenders: list[str] = []
    para_breaks = [m.end() for m in _PARAGRAPH_SPLIT_RE.finditer(defenced_text)]
    for m in PORTABLE_SKILL_FACT_CLAIM_RE.finditer(defenced_text):
        name = m.group(1)
        clause = m.group("clause")
        if "already" not in clause.lower():
            continue
        if not _resolves_to_sibling_skill(name, skill_dir.parent):
            continue
        para_start = 0
        for brk in para_breaks:
            if brk > m.start():
                break
            para_start = brk
        para_lookback = defenced_text[para_start : m.start()]
        prior_sentences = [s for s in _SENTENCE_SPLIT_RE.split(para_lookback) if s.strip()]
        lookback = prior_sentences[-1] if prior_sentences else ""
        haystack = INLINE_CODE_RE.sub(" ", lookback + clause).lower()
        if any(phrase in haystack for phrase in HEDGE_PHRASES):
            continue
        offenders.append(m.group(0).strip())
    return offenders


def _portable_skill_citation_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """The check_shape() entry point for
    _portable_skill_fact_claim_offenders, scanning SKILL.md and every
    references/*.md file the same way every other _citation_sources-based
    check does. Only called when ``_is_portable`` is true (see
    ``check_shape``), matching ``_portable_path_citation_checks``'s own
    Portable-only gate: a Mixed/Repository-scoped skill legitimately
    depends on a named sibling's real behavior.
    """
    hits: list[str] = []
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        defenced = _blank_fenced_blocks(source_text)
        for offender in _portable_skill_fact_claim_offenders(defenced, skill_dir):
            hits.append(f"{label}:{offender}")
    hits = _dedup(hits)
    return [
        CheckResult(
            "portable-no-unhedged-skill-fact-claim",
            not hits,
            "Portable content has no unhedged declarative fact-claim "
            "about a named sibling skill's own behavior "
            f"(no approved hedge phrase {HEDGE_PHRASES} nearby)",
            "none" if not hits else "found: " + ", ".join(hits),
        ),
    ]


def _out_of_skill_scripts_offenders(skill_dir: Path, source_text: str) -> list[str]:
    """Issue #192 (Refs #26 repair 3, #36 repair 3, #20 item d): return
    each bare-prose "scripts/PATH" mention (SCRIPTS_PATH_BARE_RE) in
    ``source_text`` whose path does NOT resolve to a real file under
    ``skill_dir`` -- the same "must resolve inside the skill's own
    directory" rule links-inside-skill/_out_of_skill_link_targets already
    applies to a real Markdown link, applied here to the bare-prose form
    that rule does not see (a Markdown link's target is only path-checked
    when written as "[text](scripts/foo.py)" -- a bare "run
    `scripts/foo.py`"-shaped mention has no link syntax to check at all).

    A "scripts/PATH" mention that DOES resolve inside the skill's own
    directory is a common, legitimate self-reference (every skill's
    SKILL.md routinely names its own bundled script this way) and is not
    flagged -- unlike REPO_PATH_CITATION_RE's evals/docs prefixes, which
    never legitimately resolve inside a skill directory and so are
    unconditionally flagged, "scripts/..." needs this resolution check
    rather than an unconditional flag or a hedge-phrase-proximity check
    (confirmed by a corpus-wide simulation before adding this check: every
    real bare-prose "scripts/..." mention in this repository's own
    Portable skills today is a same-skill self-reference).

    Resolution reuses ``_escapes_skill_dir`` (a review finding: a plain
    ``(skill_dir / path).is_file()`` check, with no lexical boundary
    check first, would treat a "scripts/../../other-skill/scripts/x.py"-
    shaped citation that plainly escapes the citing skill's own directory
    as a legitimate self-reference whenever the traversed-to file happens
    to exist -- the same boundary test links-inside-skill's own
    ``_out_of_skill_link_targets`` already applies to a real Markdown
    link, applied here too). A trailing ".,;:)" is stripped from the raw
    regex match before resolution (another review finding: sentence-final
    punctuation immediately after a real extension, e.g. "run
    scripts/check_foo.py.", is captured by SCRIPTS_PATH_BARE_RE's own
    character class -- which must include "." for real extensions -- and
    would otherwise make a genuine self-reference fail the existence
    check purely because of how the sentence ends); no real path ends in
    one of these characters, so stripping them is never lossy.
    """
    bare = _strip_illustrative_spans(_blank_fenced_blocks(source_text))
    skill_norm = os.path.normpath(str(skill_dir))
    offenders: list[str] = []
    for match in SCRIPTS_PATH_BARE_RE.finditer(bare):
        path = match.group(0).rstrip(".,;:)")
        normalized = os.path.normpath(Path(skill_norm) / path)
        if _escapes_skill_dir(normalized, skill_norm) or not Path(normalized).is_file():
            offenders.append(path)
    return offenders


def _out_of_skill_scripts_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """The check_shape() entry point for _out_of_skill_scripts_offenders,
    scanning SKILL.md and every references/*.md file the same way every
    other _citation_sources-based check does. Only called when
    ``_is_portable`` is true (see ``check_shape``), matching
    ``_portable_path_citation_checks``'s own Portable-only gate: a
    Mixed/Repository-scoped skill legitimately depends on a repo-specific
    scripts/ path.
    """
    offenders: list[str] = []
    for label, source_text in _citation_sources(skill_md, skill_dir, body):
        for offender in _out_of_skill_scripts_offenders(skill_dir, source_text):
            offenders.append(f"{label}:{offender}")
    offenders = _dedup(offenders)
    return [
        CheckResult(
            "portable-no-out-of-skill-scripts-citation",
            not offenders,
            "Portable content has no bare-prose 'scripts/...' path citation outside the skill's own directory",
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


# Conventional constant-naming heuristic (no-voodoo-constant, issue #1045
# ACM item A): a bare-uppercase-leading identifier of only letters, digits,
# and underscores. This is the scoping filter that keeps the check from
# flagging an ordinary lowercase/mixed-case variable, or a regex-compiled
# module "constant" like ``NAME_RE = re.compile(...)`` -- that RHS is a
# Call, not a literal, and so is excluded by ``_is_simple_literal_node``
# below regardless of the name matching this pattern.
_ALL_CAPS_CONST_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _is_simple_literal_node(node: ast.expr) -> bool:
    """Whether ``node`` (an assignment's RHS value) is a "simple literal"
    for the no-voodoo-constant check: a bare ``ast.Constant``, an
    ``ast.Tuple``/``ast.List``/``ast.Set`` whose every element is itself an
    ``ast.Constant`` (covers e.g. this file's own
    ``EXEC_REQ_NETWORK_MODES = ("disabled", "allowlist", "unrestricted")``-
    shaped constants), or an ``ast.Dict`` whose every key and value is
    itself an ``ast.Constant`` (a literal-keys-and-values config mapping is
    exactly the "voodoo constant" shape this check exists to catch; a
    ``None`` key -- the AST's own shape for a ``**spread`` entry -- fails
    the ``ast.Constant`` check and so is correctly excluded). Deliberately
    excludes any RHS containing a Call, a Name reference, or a nested
    container -- those are outside this check's narrow "bare data literal
    with no adjacent justification" scope.
    """
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(isinstance(elt, ast.Constant) for elt in node.elts)
    if isinstance(node, ast.Dict):
        return all(isinstance(k, ast.Constant) for k in node.keys) and all(
            isinstance(v, ast.Constant) for v in node.values
        )
    return False


def _bundled_python_scripts(skill_dir: Path) -> list[Path]:
    """Every non-test ``*.py`` file directly under the skill's own
    ``scripts/`` directory, sorted for deterministic offender ordering.
    Returns an empty list when ``scripts/`` does not exist -- the shared
    "not declared (optional)" precondition both new bundled-script checks
    use. ``test_*.py`` files are excluded: test fixture literals are not
    "configuration" and would be enormous false-positive noise (e.g. this
    very checker's own 6000+-line ``test_gitapex_check_skill_shape.py``).
    """
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return []
    return [
        p for p in sorted(scripts_dir.iterdir()) if p.is_file() and p.suffix == ".py" and not p.name.startswith("test_")
    ]


def _assignment_target_names(node: ast.stmt) -> tuple[list[str], ast.expr | None]:
    """Return (bare-Name target names, RHS value) for a module-level
    ``ast.Assign`` or ``ast.AnnAssign`` statement, uniformly -- an
    ``ast.AnnAssign`` (``TIMEOUT: int = 30``) carries a single ``target``,
    not a ``targets`` list, and its own ``value`` is ``None`` for a
    bare annotation with no assignment (``TIMEOUT: int``, nothing to
    scan). Any other statement type, or an ``ast.AnnAssign`` with no
    value, returns ``([], None)``.

    Each target is evaluated independently by the caller rather than
    requiring every target in a chained assignment (``FOO = bar = 1``) to
    match the ALL-CAPS heuristic together -- a tuple-unpacking, attribute,
    or subscript target is simply excluded from the returned name list
    (not a reason to discard the whole statement), since those are not
    simple named constants either.
    """
    if isinstance(node, ast.Assign):
        return [t.id for t in node.targets if isinstance(t, ast.Name)], node.value
    if isinstance(node, ast.AnnAssign) and node.value is not None and isinstance(node.target, ast.Name):
        return [node.target.id], node.value
    return [], None


def _comment_line_numbers(source: str) -> set[int]:
    """Physical (1-indexed) line numbers carrying a real ``COMMENT`` token,
    per Python's own tokenizer -- correctly distinguishes an actual
    comment from a ``#`` character living inside a string literal (the
    tokenizer never emits a ``COMMENT`` token for one), unlike a naive
    ``"#" in line`` text scan. Returns an empty set on any tokenizer error
    -- callers already treat a file that fails ``ast.parse`` as
    contributing zero offenders, so a source that also fails to tokenize
    (unlikely once it has already parsed, but not impossible for exotic
    encodings) degrades to "no comments found" rather than raising.
    """
    comment_lines: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                comment_lines.add(tok.start[0])
    except (tokenize.TokenError, IndentationError, SyntaxError, UnicodeDecodeError):
        return set()
    return comment_lines


def _has_adjacent_comment(node: ast.stmt, lines: list[str], comment_lines: set[int]) -> bool:
    """Whether ``node`` (an ``ast.Assign``/``ast.AnnAssign`` statement) has
    an adjacent justifying comment: (a) a real ``COMMENT`` token (per
    ``comment_lines``, tokenizer-derived -- never a ``#`` living inside a
    string-literal RHS, e.g. ``PREFIX = "issue #"``) exists on ANY
    physical line the statement itself spans (``node.lineno`` through
    ``node.end_lineno`` inclusive) -- covers both a trailing comment on a
    single-line assignment and a trailing comment on a multi-line
    container literal's own opening line (e.g.
    ``NAME = (  # explanation`` ... ``)``), which a strict
    "only the very last line" check would miss; or (b) the nearest
    non-blank source line above the statement's first line is itself a
    comment-only line.
    """
    end_lineno = node.end_lineno or node.lineno
    if any(lineno in comment_lines for lineno in range(node.lineno, end_lineno + 1)):
        return True
    prev_idx = node.lineno - 2
    while prev_idx >= 0:
        prev_line = lines[prev_idx].strip()
        if not prev_line:
            prev_idx -= 1
            continue
        return prev_line.startswith("#")
    return False


def _voodoo_constant_offenders(scripts: list[Path]) -> list[str]:
    """Return ``scripts/FILE.py:LINE:NAME`` for each module-level,
    ALL-CAPS-named, simple-literal assignment or annotated assignment in
    ``scripts`` with no adjacent justifying comment -- see the module
    docstring's no-voodoo-constant entry for the full rule and its
    deliberate escape hatch (any adjacent comment, however short,
    satisfies this check).

    Only ``tree.body`` (module-level statements) is walked, never
    recursed into a function or class body -- a constant assigned inside a
    function is a local, not a "voodoo constant" in the configuration
    sense this check targets. A file that fails to parse (``SyntaxError``)
    contributes zero offenders -- a malformed script is a different
    problem, not this check's (this repository's other gates, e.g. a
    full pytest run, already catch it). A file that cannot even be read
    as UTF-8 text (``UnicodeDecodeError``/``OSError``) is different:
    unlike a syntax error, nothing else in this repository's own gates
    is guaranteed to notice a bundled script that is simply unreadable,
    so silently skipping it here would let the check pass vacuously for
    a script nobody actually scanned -- reported as an offender instead,
    matching this file's own ``skill-md-readable`` check's fail-loud
    precedent for the same failure mode on ``SKILL.md`` itself.
    """
    offenders: list[str] = []
    for script in scripts:
        try:
            source = script.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            offenders.append(f"scripts/{script.name}:0:unreadable ({type(exc).__name__})")
            continue
        try:
            tree = ast.parse(source, filename=str(script))
        except SyntaxError:
            continue
        lines = source.splitlines()
        comment_lines = _comment_line_numbers(source)
        relpath = f"scripts/{script.name}"
        for node in tree.body:
            names, value = _assignment_target_names(node)
            if not names or value is None or not _is_simple_literal_node(value):
                continue
            if _has_adjacent_comment(node, lines, comment_lines):
                continue
            for name in names:
                if _ALL_CAPS_CONST_NAME_RE.match(name):
                    offenders.append(f"{relpath}:{node.lineno}:{name}")
    return offenders


def _no_voodoo_constant_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """The check_shape() entry point for _voodoo_constant_offenders,
    issue #1045's Acceptance Criteria Map item A. Runs unconditionally, at
    every portability level -- unlike the Portable-gated checks above, an
    uncommented configuration constant is a defect regardless of a skill's
    declared portability.
    """
    rule = "every bundled script's module-level ALL-CAPS constant assignment has an adjacent justifying comment (no voodoo constants)"
    scripts = _bundled_python_scripts(skill_dir)
    if not scripts:
        return [CheckResult("no-voodoo-constant", True, rule, "not declared (optional)")]
    offenders = sorted(_voodoo_constant_offenders(scripts))
    return [
        CheckResult(
            "no-voodoo-constant",
            not offenders,
            rule,
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


def _bundled_scripts(skill_dir: Path) -> list[Path]:
    """Every file (any extension) directly under the skill's own
    ``scripts/`` directory, sorted for deterministic offender ordering --
    the script-execution-intent-stated check's own scope, wider than
    ``_bundled_python_scripts`` above since a referenced ``.sh`` script
    counts too. Returns an empty list when ``scripts/`` does not exist.
    """
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return []
    return [p for p in sorted(scripts_dir.iterdir()) if p.is_file()]


def _markdown_paragraphs(source_text: str) -> list[str]:
    """Blank-line-delimited paragraphs from ``source_text``, each with its
    own internal hard-wrapped newlines joined to a single space -- the
    same unit Markdown itself treats a hard-wrapped sentence as. A
    citation and its qualifying execution-intent phrase can legitimately
    fall on different physical source lines purely because of where a
    line-wrap happens to land (this repository's own Markdown is
    hard-wrapped around 80 columns); paragraph-level matching recognizes
    them as adjacent regardless, where a strict same-physical-line match
    would not.
    """
    paragraphs: list[str] = []
    current: list[str] = []
    for line in source_text.split("\n"):
        if line.strip() == "":
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def _script_execution_intent_offenders(
    skill_md: Path, skill_dir: Path, body: list[str], scripts: list[Path]
) -> list[str]:
    """Return ``label:filename`` for each bundled script in ``scripts``
    that IS mentioned somewhere in ``_citation_sources`` as an inline-code
    span of its own exact filename (`` `filename` ``) but carries no such
    mention whose own enclosing paragraph (``_markdown_paragraphs`` --
    blank-line-delimited, hard-wrapped newlines joined) also states
    explicit execution intent (``Run `filename` `` or
    ``See `filename` ... for ...``) -- see the module docstring's
    script-execution-intent-stated entry for the full rule.

    A script never mentioned this way anywhere is skipped entirely, not an
    offender -- an unlinked/unreferenced script is a separate
    dimension-5 progressive-disclosure concern, out of scope for this
    check. The result is deduplicated by filename -- a script mentioned in
    multiple files with no qualifying phrase in any of them is reported
    once, labelled by the first source it was found unqualified in.
    """
    sources = _citation_sources(skill_md, skill_dir, body)
    offenders: list[str] = []
    seen: set[str] = set()
    for script in scripts:
        filename = script.name
        token = f"`{filename}`"
        # Case-insensitive: "run"/"see" mid-sentence ("...also run `x.py`
        # to...") is natural, grammatically-required lowercase prose, not
        # a defect -- only the capitalized, sentence-initial imperative
        # form the rubric's own illustrative example happens to use. Case
        # carries no semantic distinction for "does this state execution
        # intent," so gating on it would only pressure authors toward
        # awkward, sentence-initial-only phrasing to satisfy the check.
        run_re = re.compile(r"\bRun\s+`" + re.escape(filename) + r"`", re.IGNORECASE)
        see_re = re.compile(r"\bSee\s+`" + re.escape(filename) + r"`[^\n]*\bfor\b", re.IGNORECASE)
        mentioned = False
        satisfied = False
        first_offending_label: str | None = None
        for label, source_text in sources:
            if token not in source_text:
                continue
            for para in _markdown_paragraphs(source_text):
                if token not in para:
                    continue
                mentioned = True
                if run_re.search(para) or see_re.search(para):
                    satisfied = True
                    break
                if first_offending_label is None:
                    first_offending_label = label
            if satisfied:
                break
        if mentioned and not satisfied and filename not in seen:
            offenders.append(f"{first_offending_label}:{filename}")
            seen.add(filename)
    return offenders


def _script_execution_intent_checks(skill_md: Path, skill_dir: Path, body: list[str]) -> list[CheckResult]:
    """The check_shape() entry point for _script_execution_intent_offenders,
    issue #1045's Acceptance Criteria Map item A. Runs unconditionally, at
    every portability level -- like _no_voodoo_constant_checks above, this
    is about a skill's own bundled scripts, orthogonal to the portability
    axis.
    """
    rule = "a bundled script referenced from SKILL.md/references/ states explicit execution intent ('Run `X`' or 'See `X` for ...')"
    scripts = _bundled_scripts(skill_dir)
    if not scripts:
        return [CheckResult("script-execution-intent-stated", True, rule, "not declared (optional)")]
    offenders = _script_execution_intent_offenders(skill_md, skill_dir, body, scripts)
    return [
        CheckResult(
            "script-execution-intent-stated",
            not offenders,
            rule,
            "none" if not offenders else "found: " + ", ".join(offenders),
        ),
    ]


def _valid_skill_dependency_list(value: object) -> bool:
    """Whether ``value`` is a valid requires/relatedTo list: a list of
    non-empty strings. Unlike spec.references, an empty list is valid here
    -- most skills' spec.skillDependencies.requires is expected to be
    empty (see the design spec's Sub-project D rationale)."""
    return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)


def _skill_dependency_checks(
    spec_is_mapping: bool,
    spec_raw: object,
    spec: dict[str, object],
    malformed_items: list[str],
    unknown_keys: list[str],
    skill_dir: Path,
    portability: object,
) -> list[CheckResult]:
    """The three spec.skillDependencies checks (Sub-project D):
    ``skill-dependencies-well-formed`` (shape), ``skill-dependencies-resolve``
    (every named sibling exists -- the dangling-reference gate), and
    ``requires-portability-compatible`` (a non-empty ``requires`` cannot
    coexist with ``spec.portability: Portable`` -- a portable skill cannot
    hard-depend on a sibling that does not travel with it).

    Mirrors the spec.references cascade in ``check_shape``: shape is
    checked first, since a badly-shaped field has nothing sensible to
    resolve or contradict against -- in every early-return branch below,
    ``skill-dependencies-resolve`` and ``requires-portability-compatible``
    report "nothing to check" rather than silently passing on data that was
    never actually a list.
    """
    well_formed_rule = (
        "spec.skillDependencies, if present, is a mapping "
        "with only requires/relatedTo keys, each -- if "
        "present -- a list of non-empty strings"
    )
    resolve_rule = (
        "every name in spec.skillDependencies.requires/relatedTo resolves to an existing sibling skill directory"
    )
    contradiction_rule = "a non-empty spec.skillDependencies.requires is incompatible with spec.portability: Portable"

    if not spec_is_mapping:
        evidence = f"spec is not a mapping: {spec_raw!r}"
        return [
            CheckResult("skill-dependencies-well-formed", False, well_formed_rule, evidence),
            CheckResult("skill-dependencies-resolve", True, resolve_rule, "nothing to check (spec is not a mapping)"),
            CheckResult(
                "requires-portability-compatible", True, contradiction_rule, "nothing to check (spec is not a mapping)"
            ),
        ]

    if "skillDependencies" not in spec:
        return [
            CheckResult("skill-dependencies-well-formed", True, well_formed_rule, "not declared (optional)"),
            CheckResult("skill-dependencies-resolve", True, resolve_rule, "not declared (optional)"),
            CheckResult("requires-portability-compatible", True, contradiction_rule, "not declared (optional)"),
        ]

    deps = spec.get("skillDependencies")
    # deps is None here means the key was present with a blank (YAML null)
    # value, not absent -- distinct from the "not in spec" case above.
    # isinstance(None, dict) is already False, so the
    # existing "not a mapping" branch below fails it correctly without
    # further special-casing.
    if not isinstance(deps, dict):
        evidence = f"not a mapping: {deps!r}"
        return [
            CheckResult("skill-dependencies-well-formed", False, well_formed_rule, evidence),
            CheckResult("skill-dependencies-resolve", True, resolve_rule, "nothing to check (not a mapping)"),
            CheckResult(
                "requires-portability-compatible", True, contradiction_rule, "nothing to check (not a mapping)"
            ),
        ]

    results: list[CheckResult] = []
    problems: list[str] = []
    if unknown_keys:
        count = len(unknown_keys)
        problems.append(f"{count} unknown key{'' if count == 1 else 's'}: {unknown_keys[0]!r}")
    if malformed_items:
        count = len(malformed_items)
        problems.append(f"{count} malformed entr{'y' if count == 1 else 'ies'}: {malformed_items[0]!r}")
    for key in SKILL_DEPENDENCY_SUBKEYS:
        if key in deps and not _valid_skill_dependency_list(deps[key]):
            problems.append(f"{key} is not a list of non-empty strings: {deps[key]!r}")

    if problems:
        results.append(CheckResult("skill-dependencies-well-formed", False, well_formed_rule, "; ".join(problems)))
    else:
        declared = [k for k in SKILL_DEPENDENCY_SUBKEYS if k in deps]
        evidence = f"{', '.join(declared)} declared" if declared else "no keys declared"
        results.append(CheckResult("skill-dependencies-well-formed", True, well_formed_rule, evidence))

    requires = deps.get("requires")
    requires = requires if _valid_skill_dependency_list(requires) else []
    related = deps.get("relatedTo")
    related = related if _valid_skill_dependency_list(related) else []
    named = list(dict.fromkeys(requires + related))
    dangling = [n for n in named if not _resolves_to_sibling_skill(n, skill_dir.parent)]
    results.append(
        CheckResult(
            "skill-dependencies-resolve",
            not dangling,
            resolve_rule,
            "all resolve" if not dangling else "dangling: " + ", ".join(dangling),
        )
    )

    contradiction = bool(requires) and portability == "Portable"
    results.append(
        CheckResult(
            "requires-portability-compatible",
            not contradiction,
            contradiction_rule,
            "ok" if not contradiction else f"non-empty requires with portability={portability!r}",
        )
    )

    return results


def _valid_lifecycle_date(value: object) -> bool:
    """Whether ``value`` is a real calendar date in strict YYYY-MM-DD
    shape, for spec.lifecycle's since/removeAfter fields.

    Regex first (rejects any non-dashed or wrong-width shape outright),
    then ``datetime.date.fromisoformat`` (rejects a shape-valid but
    non-existent date, e.g. "2026-13-45" or "2026-02-30", that a
    regex-only check would silently accept). Gating the regex first also
    blocks ``fromisoformat``'s lenient Python 3.11+ ISO-variant parsing
    from accepting an off-shape string that happens to still be valid
    ISO 8601.
    """
    if not (isinstance(value, str) and LIFECYCLE_DATE_RE.match(value)):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _valid_tracking_issue(value: object) -> bool:
    """Shape-only check for spec.lifecycle.experimental.trackingIssue: a
    full ``https://github.com/tvna/gitapex/issues/123`` (or ``/pull/123``)
    URL. Never resolved against a live GitHub API call -- this checker is
    offline/read-only by design.
    """
    return isinstance(value, str) and bool(LIFECYCLE_ISSUE_REF_RE.match(value))


def _lifecycle_checks(
    spec_is_mapping: bool,
    spec_raw: object,
    spec: dict[str, object],
    unknown_keys: list[str],
    unknown_fields: list[str],
    skill_dir: Path,
) -> list[CheckResult]:
    """The three spec.lifecycle checks: ``lifecycle-well-formed`` (shape),
    ``lifecycle-deprecated-replacement-resolves`` (the dangling-reference
    gate for ``deprecated.replacement``, mirroring
    ``skill-dependencies-resolve``), and
    ``experimental-stable-compatible`` (the one cross-field rule: a skill
    cannot be simultaneously "not yet graduated" and "already graduated on
    some date").

    ``experimental``, ``deprecated``, and ``stable`` are independent,
    optional sub-blocks; ``renamedFrom`` is a plain scalar directly under
    ``spec.lifecycle``, never a sub-block. ``experimental`` and
    ``deprecated`` do not exclude each other (an experimental skill can
    legitimately be superseded by a different experiment) -- but
    ``experimental`` and ``stable`` are a real logical contradiction, so
    unlike the ``deprecated`` pairing, that combination is gated. Mirrors
    the ``_skill_dependency_checks`` cascade: shape is checked first,
    since a badly-shaped field has nothing sensible to resolve or
    contradict against -- every early-return branch below reports both
    ``lifecycle-deprecated-replacement-resolves`` and
    ``experimental-stable-compatible`` as "nothing to check" rather than
    silently passing on data that was never actually a mapping.
    """
    well_formed_rule = (
        "spec.lifecycle, if present, is a mapping with only "
        "experimental/deprecated/stable/renamedFrom keys. experimental "
        "(reason/trackingIssue required, since optional), deprecated "
        "(reason/replacement required, since/removeAfter optional), and "
        "stable (since required, compatibilityGuarantee optional) are "
        "each -- if present -- a mapping of their own recognized scalar "
        "fields; renamedFrom, if present, is a non-empty scalar string. "
        "since/removeAfter, if present, must be real YYYY-MM-DD dates; "
        "reason, if present, is <= "
        f"{REFERENCES_ENTRY_MAX_CHARS} chars; trackingIssue, if present, a "
        "full https://github.com/tvna/gitapex/issues/<N> (or /pull/<N>) "
        "URL; compatibilityGuarantee, if present, one of "
        f"{COMPATIBILITY_GUARANTEE_LEVELS}"
    )
    resolve_rule = (
        "spec.lifecycle.deprecated.replacement, if a non-empty string, resolves to an existing sibling skill directory"
    )
    contradiction_rule = (
        "spec.lifecycle.experimental and spec.lifecycle.stable cannot "
        "both be present -- a skill cannot be both not-yet-graduated and "
        "already graduated"
    )

    if not spec_is_mapping:
        evidence = f"spec is not a mapping: {spec_raw!r}"
        return [
            CheckResult("lifecycle-well-formed", False, well_formed_rule, evidence),
            CheckResult(
                "lifecycle-deprecated-replacement-resolves",
                True,
                resolve_rule,
                "nothing to check (spec is not a mapping)",
            ),
            CheckResult(
                "experimental-stable-compatible", True, contradiction_rule, "nothing to check (spec is not a mapping)"
            ),
        ]

    if "lifecycle" not in spec:
        return [
            CheckResult("lifecycle-well-formed", True, well_formed_rule, "not declared (optional)"),
            CheckResult("lifecycle-deprecated-replacement-resolves", True, resolve_rule, "not declared (optional)"),
            CheckResult("experimental-stable-compatible", True, contradiction_rule, "not declared (optional)"),
        ]

    lifecycle = spec.get("lifecycle")
    # lifecycle is None here means present-but-blank (YAML null), distinct
    # from absent above -- isinstance(None, dict) is already
    # False, so the existing "not a mapping" branch below fails it.
    if not isinstance(lifecycle, dict):
        evidence = f"not a mapping: {lifecycle!r}"
        return [
            CheckResult("lifecycle-well-formed", False, well_formed_rule, evidence),
            CheckResult(
                "lifecycle-deprecated-replacement-resolves", True, resolve_rule, "nothing to check (not a mapping)"
            ),
            CheckResult("experimental-stable-compatible", True, contradiction_rule, "nothing to check (not a mapping)"),
        ]

    problems: list[str] = []
    if unknown_keys:
        count = len(unknown_keys)
        problems.append(f"{count} unknown key{'' if count == 1 else 's'}: {unknown_keys[0]!r}")
    if unknown_fields:
        count = len(unknown_fields)
        problems.append(f"{count} unknown field{'' if count == 1 else 's'}: {unknown_fields[0]!r}")

    sub_blocks: dict[str, dict[str, object]] = {}
    for key in LIFECYCLE_SUBKEYS:
        if key not in lifecycle:
            continue
        block = lifecycle[key]
        if not isinstance(block, dict):
            problems.append(f"{key} is not a mapping: {block!r}")
            continue
        sub_blocks[key] = block
        for field in LIFECYCLE_REQUIRED_FIELDS[key]:
            val = block.get(field)
            if not (isinstance(val, str) and val.strip()):
                problems.append(f"{key}.{field} is missing or not a non-empty string: {val!r}")
        for field in ("since", "removeAfter"):
            if field in block and not _valid_lifecycle_date(block[field]):
                problems.append(f"{key}.{field} is not a YYYY-MM-DD date: {block[field]!r}")
        reason_val = block.get("reason")
        if isinstance(reason_val, str) and len(reason_val) > REFERENCES_ENTRY_MAX_CHARS:
            problems.append(
                f"{key}.reason is {len(reason_val)} chars, over the {REFERENCES_ENTRY_MAX_CHARS}-char limit"
            )
        if key == "experimental" and "trackingIssue" in block and not _valid_tracking_issue(block["trackingIssue"]):
            problems.append(
                f"experimental.trackingIssue is not a full "
                f"https://github.com/tvna/gitapex/issues/<N> (or /pull/<N>) "
                f"URL: {block['trackingIssue']!r}"
            )
        if (
            key == "stable"
            and "compatibilityGuarantee" in block
            and block["compatibilityGuarantee"] not in COMPATIBILITY_GUARANTEE_LEVELS
        ):
            problems.append(
                f"stable.compatibilityGuarantee is not one of "
                f"{COMPATIBILITY_GUARANTEE_LEVELS}: "
                f"{block['compatibilityGuarantee']!r}"
            )

    if "renamedFrom" in lifecycle:
        renamed_from = lifecycle["renamedFrom"]
        if not (isinstance(renamed_from, str) and renamed_from.strip()):
            problems.append(f"renamedFrom is not a non-empty string: {renamed_from!r}")

    if problems:
        results = [CheckResult("lifecycle-well-formed", False, well_formed_rule, "; ".join(problems))]
    else:
        declared = [k for k in LIFECYCLE_SUBKEYS if k in sub_blocks]
        if "renamedFrom" in lifecycle:
            declared.append("renamedFrom")
        evidence = f"{', '.join(declared)} declared" if declared else "no keys declared"
        results = [CheckResult("lifecycle-well-formed", True, well_formed_rule, evidence)]

    deprecated = sub_blocks.get("deprecated")
    replacement = deprecated.get("replacement") if deprecated else None
    if isinstance(replacement, str) and replacement.strip():
        exists = _resolves_to_sibling_skill(replacement, skill_dir.parent)
        results.append(
            CheckResult(
                "lifecycle-deprecated-replacement-resolves",
                exists,
                resolve_rule,
                "resolves" if exists else f"dangling: {replacement!r}",
            )
        )
    else:
        results.append(
            CheckResult(
                "lifecycle-deprecated-replacement-resolves",
                True,
                resolve_rule,
                "nothing to check (replacement missing or invalid)",
            )
        )

    contradiction = "experimental" in sub_blocks and "stable" in sub_blocks
    results.append(
        CheckResult(
            "experimental-stable-compatible",
            not contradiction,
            contradiction_rule,
            "ok" if not contradiction else "both experimental and stable are present",
        )
    )
    return results


def _valid_execution_requirements_tools_list(value: object) -> bool:
    """Whether ``value`` is a valid tools.read/write/shell list: a list of
    non-empty strings. Mirrors ``_valid_skill_dependency_list`` -- an empty
    list is valid here too, since it is a deliberate "zero tools of this
    kind needed" statement, distinct from the subkey being absent
    entirely."""
    return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)


def _execution_requirements_checks(
    spec_is_mapping: bool,
    spec_raw: object,
    spec: dict[str, object],
    unknown_keys: list[str],
    unknown_tools_keys: list[str],
    malformed_tools_items: list[str],
    unknown_packages_keys: list[str],
    malformed_packages_items: list[str],
    unknown_network_keys: list[str],
    malformed_network_items: list[str],
) -> list[CheckResult]:
    """The one spec.executionRequirements check landed so far:
    ``execution-requirements-well-formed``.

    Mirrors ``_skill_dependency_checks``'s early-return ladder (spec not a
    mapping / not declared / not a mapping) before real validation, and its
    problem-accumulation-then-single-CheckResult pattern. Unlike
    spec.skillDependencies or spec.lifecycle, this field has only three
    recognized top-level subkeys so far, ``tools``, ``packages``, and
    ``network`` (issue #845; #1115's own ADR follow-up added ``packages``)
    -- the remaining categories (filesystem, mcp, credentials, browser,
    externalServices, context) are deferred; any key here other than
    ``tools``/``packages``/``network`` fails closed via ``unknown_keys``
    rather than being silently accepted as reserved space. There is no
    dangling-reference or cross-field check the way
    spec.skillDependencies/spec.lifecycle have one each -- tools'
    read/write/shell entries are free-form capability tags, not names that
    resolve against sibling skill directories, and no rule ties this field
    to portability/capabilityAssumption/lifecycle. network.mode/domains
    DO carry one cross-field rule of their own (domains non-empty iff mode
    is allowlist), checked below the same way requires-portability-
    compatible is checked elsewhere in this file, just folded into this
    same well-formed check rather than earning its own separate
    CheckResult -- tools has no analogous cross-subkey rule to justify the
    same split. packages' own allowlist-membership resolution (whether a
    declared package name is one gitapex permits at all) is not part of
    this check: it is enforced entirely outside this portable script, by
    a repository-owned CI gate
    (``.github/scripts/gitapex_gate_dependency_allowlist.py``) that never
    produces a CheckResult here. This function validates only packages'
    own internal SHAPE, the same as tools and network.
    """
    well_formed_rule = (
        "spec.executionRequirements, if present, is a "
        "mapping with only the tools/packages/network keys; "
        "tools, if present, is a mapping with only "
        "read/write/shell keys, each -- if present -- a list "
        "of non-empty strings; packages, if present, is a "
        "mapping keyed by free-form ecosystem identifiers "
        "(matching ^[a-z][a-z0-9-]*$), each value -- if "
        "present -- a list of non-empty strings; network, if "
        "present, is a mapping with only mode (a "
        "disabled/allowlist/unrestricted enum, required when "
        "network is declared) and domains (a list of "
        "non-empty strings, non-empty iff mode is allowlist)"
    )

    if not spec_is_mapping:
        return [
            CheckResult(
                "execution-requirements-well-formed", False, well_formed_rule, f"spec is not a mapping: {spec_raw!r}"
            )
        ]

    if "executionRequirements" not in spec:
        return [CheckResult("execution-requirements-well-formed", True, well_formed_rule, "not declared (optional)")]

    execution_requirements = spec.get("executionRequirements")
    # None here means present-but-blank (YAML null), distinct from absent
    # above -- isinstance(None, dict) is already False, so
    # the existing "not a mapping" branch below fails it correctly.
    if not isinstance(execution_requirements, dict):
        return [
            CheckResult(
                "execution-requirements-well-formed",
                False,
                well_formed_rule,
                f"not a mapping: {execution_requirements!r}",
            )
        ]

    problems: list[str] = []
    if unknown_keys:
        count = len(unknown_keys)
        problems.append(f"{count} unknown key{'' if count == 1 else 's'}: {unknown_keys[0]!r}")

    tools_present = "tools" in execution_requirements
    tools = execution_requirements.get("tools")
    # tools_present with tools is None means present-but-blank (YAML
    # null), distinct from tools being absent entirely -- both must fail
    # closed here rather than silently passing as an empty mapping.
    if tools_present and not isinstance(tools, dict):
        problems.append(f"tools is not a mapping: {tools!r}")
    elif isinstance(tools, dict):
        if unknown_tools_keys:
            count = len(unknown_tools_keys)
            problems.append(f"{count} unknown tools key{'' if count == 1 else 's'}: {unknown_tools_keys[0]!r}")
        if malformed_tools_items:
            count = len(malformed_tools_items)
            problems.append(f"{count} malformed tools entr{'y' if count == 1 else 'ies'}: {malformed_tools_items[0]!r}")
        for key in EXEC_REQ_TOOLS_SUBKEYS:
            if key in tools and not _valid_execution_requirements_tools_list(tools[key]):
                problems.append(f"tools.{key} is not a list of non-empty strings: {tools[key]!r}")

    packages_present = "packages" in execution_requirements
    packages = execution_requirements.get("packages")
    # Same present-but-null-vs-absent distinction tools' own branch above
    # already draws.
    if packages_present and not isinstance(packages, dict):
        problems.append(f"packages is not a mapping: {packages!r}")
    elif isinstance(packages, dict):
        if unknown_packages_keys:
            count = len(unknown_packages_keys)
            problems.append(f"{count} unknown packages key{'' if count == 1 else 's'}: {unknown_packages_keys[0]!r}")
        if malformed_packages_items:
            count = len(malformed_packages_items)
            problems.append(
                f"{count} malformed packages entr{'y' if count == 1 else 'ies'}: {malformed_packages_items[0]!r}"
            )
        # packages' own subkeys are free-form ecosystem identifiers, not a
        # fixed tuple like EXEC_REQ_TOOLS_SUBKEYS -- iterate the parsed
        # mapping's own keys (already guaranteed to match
        # EXEC_REQ_PACKAGES_KEY_RE by the parser; a non-matching key never
        # reaches this dict at all, landing in unknown_packages_keys
        # instead, per _parse_manifest) rather than a fixed vocabulary, so
        # only each key's own VALUE shape remains to check here.
        for key in packages:
            if not _valid_execution_requirements_tools_list(packages[key]):
                problems.append(f"packages.{key} is not a list of non-empty strings: {packages[key]!r}")
        # KNOWN, DISCLOSED GAP (not fixed here): $defs.packageList in
        # skill-metadata.schema.json declares "uniqueItems": true, but
        # this checker does not enforce it -- a package name repeated
        # twice under the same ecosystem (e.g. "pip: [pyyaml, pyyaml]")
        # currently still passes execution-requirements-well-formed.
        # Fail-open only in the sense of "does not additionally flag a
        # redundant duplicate as its own defect"; it is not an
        # allowlist-bypass gap (the CI gate that resolves allowlist
        # membership dedupes by normalized name before checking, so a
        # duplicate cannot inflate or hide an offender there). Left
        # unimplemented rather than folded into
        # _valid_execution_requirements_tools_list, which tools.read/
        # write/shell and network.domains also share -- enforcing
        # uniqueItems there too is a broader, separate change this
        # finding did not ask for and risks failing existing skills that
        # currently rely on tolerated duplicates in those other lists.

    network_present = "network" in execution_requirements
    network = execution_requirements.get("network")
    # Same present-but-null-vs-absent distinction tools' own branch above
    # already draws.
    if network_present and not isinstance(network, dict):
        problems.append(f"network is not a mapping: {network!r}")
    elif isinstance(network, dict):
        if unknown_network_keys:
            count = len(unknown_network_keys)
            problems.append(f"{count} unknown network key{'' if count == 1 else 's'}: {unknown_network_keys[0]!r}")
        if malformed_network_items:
            count = len(malformed_network_items)
            problems.append(
                f"{count} malformed network entr{'y' if count == 1 else 'ies'}: {malformed_network_items[0]!r}"
            )
        mode_present = "mode" in network
        mode = network.get("mode")
        if not mode_present:
            problems.append("network.mode is required when network is declared")
        elif not (isinstance(mode, str) and mode in EXEC_REQ_NETWORK_MODES):
            problems.append(f"network.mode is not one of {EXEC_REQ_NETWORK_MODES}: {mode!r}")
        domains_present = "domains" in network
        domains = network.get("domains")
        # Reuses _valid_execution_requirements_tools_list: the same "list
        # of non-empty strings" shape tools.read/write/shell already
        # validate, generic despite its tools-scoped name.
        if domains_present and not _valid_execution_requirements_tools_list(domains):
            problems.append(f"network.domains is not a list of non-empty strings: {domains!r}")
        elif mode == "allowlist" and not (isinstance(domains, list) and domains):
            problems.append("network.domains must be a non-empty list when network.mode is allowlist")
        elif mode in ("disabled", "unrestricted") and isinstance(domains, list) and domains:
            problems.append(f"network.domains must be empty when network.mode is {mode!r}")

    if problems:
        return [CheckResult("execution-requirements-well-formed", False, well_formed_rule, "; ".join(problems))]

    declared = [f"tools.{k}" for k in EXEC_REQ_TOOLS_SUBKEYS if k in tools] if isinstance(tools, dict) else []
    # packages has no fixed subkey tuple to iterate (see the loop above) --
    # walk the parsed mapping's own keys instead, in file order (Python
    # dict iteration order is insertion order, which here is parse order).
    declared += [f"packages.{k}" for k in packages] if isinstance(packages, dict) else []
    declared += [f"network.{k}" for k in EXEC_REQ_NETWORK_SUBKEYS if k in network] if isinstance(network, dict) else []
    evidence = ", ".join(declared) + " declared" if declared else "no keys declared"
    return [CheckResult("execution-requirements-well-formed", True, well_formed_rule, evidence)]


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
    parser = argparse.ArgumentParser(description="Check a SKILL.md's deterministic shape (read-only).")
    parser.add_argument(
        "--allowed-root",
        help="Caller-approved directory that must contain the target; "
        "also rejects symlinks in the target skill. The caller must keep "
        "the snapshot immutable while the check runs.",
    )
    parser.add_argument("target", help="Path to a skill directory or a SKILL.md file.")
    args = parser.parse_args(argv)
    target = Path(args.target)
    allowed_root = Path(args.allowed_root) if args.allowed_root else None
    if allowed_root is not None:
        try:
            _validate_read_scope(target, allowed_root)
        except (OSError, ValueError) as exc:
            print(f"error: unsafe target path: {exc}", file=sys.stderr)
            return 2
    skill_md = _resolve_skill_md(target)
    if not skill_md.is_file():
        print(f"error: no SKILL.md found at: {target}", file=sys.stderr)
        return 2
    try:
        results = check_shape(target)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: could not read skill files: {exc}", file=sys.stderr)
        return 2
    print(format_report(results))
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
