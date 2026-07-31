export const meta = {
  name: 'semantic-rationale-load-test-v2',
  description: 'Corrected re-run of the score_semantic_rationale.py load test (issue #625): every case now embeds its own VERIFIED real citation, removing the citation-embedding confound the first run disclosed',
  phases: [
    { title: 'Extract sources' },
    { title: 'Extract & compare candidates' },
    { title: 'Consistency recheck' },
  ],
}

const DECISION_RECORD_SCHEMA = {
  type: 'object',
  properties: {
    rejected_alternative: { type: ['string', 'null'] },
    reason: { type: ['string', 'null'] },
    cited_ref: { type: ['string', 'null'] },
  },
  required: ['rejected_alternative', 'reason', 'cited_ref'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    rejected_alternative_match: { type: 'boolean' },
    reason_match: { type: 'boolean' },
    cited_ref_match: { type: 'boolean' },
    fabrication_detected: { type: 'boolean' },
    explanation: { type: 'string' },
  },
  required: ['rejected_alternative_match', 'reason_match', 'cited_ref_match', 'fabrication_detected', 'explanation'],
}

function extractPrompt(text) {
  return `Extract the decision record described in the text below. "rejected_alternative" is the specific alternative that was considered and NOT chosen (null if none is stated). "reason" is the stated justification for rejecting it (null if none is stated). "cited_ref" is any issue/PR/ADR/doc identifier the text points to as evidence for this decision (null if none is stated). Do not infer content not actually present in the text; use null rather than guessing.\n\nText:\n---\n${text}\n---\n`
}

function comparePrompt(candidateRecord, sourceRecord) {
  return `Two decision records were extracted independently: one from a generated artifact (a code comment), one from the real source it claims to cite. Judge whether the candidate's claims are actually true of the source -- semantic agreement, not string equality (paraphrases count as a match; a candidate claim not supported by the source does not, even if it sounds plausible or is true of some OTHER decision). Set fabrication_detected to true if the candidate asserts something the source does not actually support.\n\nCandidate record:\n${JSON.stringify(candidateRecord, null, 2)}\n\nSource record:\n${JSON.stringify(sourceRecord, null, 2)}\n`
}

function candidateComment(citation, reason) {
  return `# why-not(${citation}): ${reason}`
}

// Corrected v2: every case below was re-verified this session directly
// against the real committed file (docstring/comment), fixing 3 classes
// of defect the first load test (issue #625, wf_9590fbba-155) disclosed:
//   1. Citation-embedding confound: 6/8 sourceTexts never stated their own
//      citation in prose, so ANY asserted citation registered as a mismatch
//      for the same structural reason regardless of whether it was swapped.
//      Every sourceText below now states its citation explicitly.
//   2. Two digit-transposition-style citation bugs caught by the judge's
//      own real-file verification in v1: lint_fixture_assertions' true
//      citation is #218, not the #518 v1 used; gate_retro_title_convention's
//      true citation is "Issue #520, refs #344", not the bare "#520" v1
//      used.
//   3. Two invented-elaboration reasons v1's own judge flagged as
//      unsupported: gate_retro_title_convention's "would require citations
//      this repository does not actually expect" clause (not in the real
//      docstring) and check_skill_shape's "duplicates gate_provenance_
//      disclosure.py" clause (that script is unrelated -- confirmed by
//      reading it directly; the real docstring states no rationale beyond
//      the rule itself). Both trimmed to only verifiable content.
// Two previously-"fictional placeholder" citations turned out to have real
// citations after a proper re-check (gate_skill_branch_fixture_coverage:
// Issue #49 repair 1, not #540; gate_transfer_check_disclosure: Issue
// #517 refs #487, not #552) -- found via `git log -S`/docstring reads,
// not memory. check_skill_shape_no_illustrative_model_id has no issue
// number in the real repo at all; its real citation is a doc path
// (docs/skill-authoring-standards.md rule 1), kept as such rather than
// inventing a fictional issue number for it.
const CASES = [
  {
    id: 'score_contract_near_check',
    citation: '#312', // REAL -- git log -S "output_contains_near" -> af9ec0b, "(#312)"
    rejectedAlt: 'a pure character-window check for the output_contains_near assertion',
    reason: 'a window-only check lets two occurrences straddle a fully separate, unrelated paragraph and still false-pass as "near"',
    sourceText: 'score_contract.py\'s output_contains_near check (added closing a Codex review finding, issue #312) requires each entry\'s substrings to co-occur within a character window AND have no blank line between their occurrences. A raw character count alone cannot cleanly separate "these two substrings are bound in the same logical unit" from "they merely happen to be within N characters of each other" -- a verbose correct paragraph and a terse adjacent but unrelated one can straddle any fixed window either way. The blank-line check (this repository\'s own paragraph/list-item separator) is what actually carries the distinction in practice; the character window is only a secondary sanity bound.',
  },
  {
    id: 'gate_split_fixture_coverage_check_a',
    citation: 'issue #191, repair 1', // REAL, unchanged from v1
    rejectedAlt: 'applying the full-corpus superset requirement uniformly to every gate-result table, with no exemption for tables scoped to a single named fixture',
    reason: 'without an exemption, every narrow single-fixture recheck dispatch would falsely trip the full-corpus superset requirement, since such a dispatch by construction never claims full-corpus coverage',
    sourceText: 'Check A (issue #191, repair 1) requires a split.md gate-result table\'s Fixture column to be a superset of the file\'s declared selection list -- UNLESS the table is explicitly scoped to a single named fixture via the established "one fresh dispatch per side against \'<fixture>.yaml\'" convention, which by construction never claims full-corpus coverage and is exempt from the superset rule.',
  },
  {
    id: 'run_ablation_bare_mode',
    citation: '#583', // REAL, unchanged from v1, now embedded in sourceText
    rejectedAlt: "staging a .claude/skills/<name>/ directory for the ablation runner's \"without skill\" arm",
    reason: '--bare explicitly disables the very skill-discovery mechanism a staged directory depends on, so the two approaches are mutually exclusive, not a fidelity dial with a middle setting',
    sourceText: 'run_ablation.py (issue #583) uses --bare plus --append-system-prompt-file as its skill toggle mechanism, not a staged .claude/skills/ directory. Claude Code\'s own headless-mode docs confirm --bare "skip[s] auto-discovery of hooks, skills, plugins, MCP servers, auto memory, and CLAUDE.md." Without --bare, invoking claude -p from a checkout of this repository would auto-load the repository\'s own CLAUDE.md and other skills into both arms of the comparison, undermining the whole premise of an ablation run. --bare and skill auto-discovery are therefore not a fidelity dial with a middle setting: --bare explicitly disables the very discovery mechanism a staged .claude/skills/<name>/ directory would depend on.',
  },
  {
    id: 'check_skill_shape_no_illustrative_model_id',
    citation: 'docs/skill-authoring-standards.md rule 1', // REAL doc citation -- no issue number exists for this rule
    rejectedAlt: "allowing a real, current Claude model identifier as illustrative content in a SKILL.md or references/*.md, even inside a worked example deliberately flagged as a \"bad\"/\"before\" sample meant to be fixed",
    reason: 'the rule is about the identifier ever appearing as illustrative content at all, not about whether it resolves live, so a real model ID inside a flagged worked example is exactly what the rule exists to catch, not something to exempt -- the standards doc states this directly and gives no further rationale beyond directing a clearly fictitious placeholder instead',
    sourceText: 'check_skill_shape.py\'s no-illustrative-model-identifier check (docs/skill-authoring-standards.md rule 1) flags a real, current Claude model identifier used as illustrative content in a SKILL.md or references/*.md -- even inside a worked example deliberately flagged as a "bad"/"before" sample meant to be fixed, since the rule is about the identifier ever appearing as illustrative content at all, not about whether it resolves live. The standards doc states this rule directly ("Use a clearly fictitious placeholder instead") with no further stated rationale beyond that.',
  },
  {
    id: 'lint_fixture_assertions_collision_pairs',
    citation: '#218', // REAL -- fixed from v1's #518 (a digit-transposition bug v1's own judge caught)
    rejectedAlt: 'a general English-dictionary substring scan for the short-word-collision check',
    reason: 'a dictionary scan false-flagged this repository\'s own deliberately-truncated stem assertions, like "emporal" for temporal and "hardcod" for hardcode(d), which are not real dictionary words themselves',
    sourceText: 'lint_fixture_assertions.py\'s short-word-collision check (#218) uses a small hand-curated set of known collision pairs, not a general dictionary substring scan. A generic dictionary substring scan was tried first and rejected -- it false-flagged this repository\'s own deliberately-truncated stem assertions (e.g. "emporal" for temporal, "hardcod" for hardcode(d)), which are not real words themselves and so are not the collision this check means to catch.',
  },
  {
    id: 'gate_skill_branch_fixture_coverage_growth_only',
    citation: 'Issue #49, repair 1', // REAL -- fixed from v1's fictional #540 (a real citation exists)
    rejectedAlt: "requiring new fixture coverage on every diff that touches a SKILL.md's Stop-boundary bullets or dispatch branches, regardless of direction",
    reason: 'only a net GROWTH in the Stop-boundary-bullet-plus-dispatch-branch count actually adds untested behavioral surface; a same-or-lower-total content swap (bullets removed, different ones added) still counts as growth for the new bullets\' own keys, so gating on growth alone still catches that case while not demanding fixtures for a pure deletion or reword',
    sourceText: 'gate_skill_branch_fixture_coverage.py (Issue #49, repair 1) counts a SKILL.md\'s Stop-boundary bullets plus named dispatch branches (via Counter subtraction against the before-version) and only fires when that count GROWS in the diff -- delta-scoped, not an absolute-count check. A same-or-lower-total content swap (e.g. 3 bullets removed, 3 different ones added) still shows up as growth, because the new bullets\' keys are entirely absent from the before-version\'s own Counter; a diff that only deletes or rewords an existing bullet, with no new key, does not trigger the gate.',
  },
  {
    id: 'gate_transfer_check_disclosure_structural_no_op',
    citation: 'Issue #517, refs #487', // REAL -- fixed from v1's fictional #552 (a real citation exists)
    rejectedAlt: 'requiring the Transfer-check-disclosure gate to mechanically recognize every split.md heading convention a skill might use for its Kept-edit log',
    reason: 'the gate only mechanically parses the bold **Iteration: line convention under a specific ## Kept-edit log heading; a split.md using plain ## Iteration: H2 headings instead is a structural no-op for this gate by construction, not a violation the gate fails to catch',
    sourceText: 'gate_transfer_check_disclosure.py (Issue #517, refs #487) checks that every newly-added Kept-edit-log **Iteration: entry in a split.md diff discloses a Transfer check line, but it only mechanically fires on files using that specific bold-line convention under a ## Kept-edit log heading. A split.md file that instead uses plain ## Iteration: H2 headings is a structural no-op for this gate -- confirmed by feeding it empty input, which passes trivially, not because the file is somehow exempt from needing disclosure by policy.',
  },
  {
    id: 'gate_retro_title_convention_citation_narrow_scope',
    citation: 'Issue #520, refs #344', // REAL -- fixed from v1's incomplete bare "#520" (real citation includes refs #344 too)
    rejectedAlt: 'requiring a resolvable issue citation for any file asserting something is "this repository\'s own convention," regardless of subject matter',
    reason: 'the gate is deliberately narrowed to only a convention-claim paragraph that also names a title/identity concept (the word "title" or "identity" nearby); a bare "this repo\'s own convention" claim about, say, ASCII formatting or a scoring rubric is a different claim class this gate does not police',
    sourceText: 'gate_retro_title_convention_citation.py (Issue #520, refs #344) flags a "this repo\'s own convention" / "established convention" claim only when it also names a title/identity concept (the word "title" or "identity" in the same paragraph) -- narrowing scope to the paragraph, not the whole file, and deliberately excluding claims like a "gitapex\'s own convention" about ASCII formatting or a scoring rubric, which are a different claim class this gate does not police.',
  },
]

phase('Extract sources')
const sourceRecords = await pipeline(
  CASES,
  c => agent(extractPrompt(c.sourceText), { label: 'source:' + c.id, phase: 'Extract sources', schema: DECISION_RECORD_SCHEMA })
)

const variants = []
for (let i = 0; i < CASES.length; i++) {
  const c = CASES[i]
  const next = CASES[(i + 1) % CASES.length]
  variants.push({ caseId: c.id, variant: 'genuine', sourceIndex: i, citation: c.citation, reason: c.reason })
  variants.push({ caseId: c.id, variant: 'wrongReason', sourceIndex: i, citation: c.citation, reason: next.reason })
  variants.push({ caseId: c.id, variant: 'wrongCitation', sourceIndex: i, citation: next.citation, reason: c.reason })
}

phase('Extract & compare candidates')
const variantResults = await pipeline(
  variants,
  v => agent(
    extractPrompt(candidateComment(v.citation, v.reason)),
    { label: 'candidate:' + v.caseId + ':' + v.variant, phase: 'Extract & compare candidates', schema: DECISION_RECORD_SCHEMA }
  ),
  (candRecord, v) => agent(
    comparePrompt(candRecord, sourceRecords[v.sourceIndex]),
    { label: 'compare:' + v.caseId + ':' + v.variant, phase: 'Extract & compare candidates', schema: VERDICT_SCHEMA }
  ).then(verdict => ({ ...v, candRecord, verdict }))
)

phase('Consistency recheck')
const recheckTargets = [variantResults[1], variantResults[10], variantResults[19]].filter(Boolean)
const rechecks = await parallel(
  recheckTargets.map(v => () =>
    agent(
      comparePrompt(v.candRecord, sourceRecords[v.sourceIndex]),
      { label: 'recheck:' + v.caseId + ':' + v.variant, phase: 'Consistency recheck', schema: VERDICT_SCHEMA }
    ).then(verdict2 => ({ caseId: v.caseId, variant: v.variant, firstVerdict: v.verdict, secondVerdict: verdict2 }))
  )
)

function scoreOf(verdict) {
  const flags = [verdict.rejected_alternative_match, verdict.reason_match, verdict.cited_ref_match]
  return flags.filter(Boolean).length / flags.length
}

const byVariant = { genuine: [], wrongReason: [], wrongCitation: [] }
for (const r of variantResults) {
  if (!r) continue
  byVariant[r.variant].push({ caseId: r.caseId, score: scoreOf(r.verdict), fabrication_detected: r.verdict.fabrication_detected, explanation: r.verdict.explanation })
}

function summarize(list) {
  const meanScore = list.reduce((s, x) => s + x.score, 0) / list.length
  const fabricationRate = list.filter(x => x.fabrication_detected).length / list.length
  return { n: list.length, meanScore, fabricationRate }
}

const summary = {
  genuine: summarize(byVariant.genuine),
  wrongReason: summarize(byVariant.wrongReason),
  wrongCitation: summarize(byVariant.wrongCitation),
}

const falsePositives = byVariant.genuine.filter(x => x.fabrication_detected)
const falseNegatives = [...byVariant.wrongReason, ...byVariant.wrongCitation].filter(x => !x.fabrication_detected)

return {
  summary,
  falsePositives,
  falseNegatives,
  consistency: rechecks,
  allResults: variantResults.map(r => r && ({ caseId: r.caseId, variant: r.variant, verdict: r.verdict, score: scoreOf(r.verdict) })),
}
