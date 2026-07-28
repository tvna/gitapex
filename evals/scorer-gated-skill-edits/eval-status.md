# scorer-gated-skill-edits eval status

The committed eval suite (`evals/scorer-gated-skill-edits/`) has no committed
with-skill vs. no-skill score comparison, and only `claude-sonnet-4.6` has
been evaluated -- cross-model behavior is currently unmeasured.

**Issue #149 (unknowns framework):** the Precondition gate section gained a
**Blind spot pass** bullet -- name whether the fixture corpus itself has an
unknown-unknown blind spot before trusting the split -- adapted from
Anthropic's own field guide on working with Claude models (Thariq Shihipar,
"A Field Guide to Fable: Finding Your Unknowns"). Advisory naming addition,
not a new enforced branch, so no new eval fixture was added. Refs #149.

**Issue #175 (judge-mode scoring, deferred from #173 option 1):**
`score_contract.py` gained an opt-in `--judge-verdict {agree,disagree}` flag,
recorded alongside the existing `--compare-to` substring gate output as
`JUDGE_AGREE` / `JUDGE_DISAGREE_REVIEW_REQUIRED`. The flag records the
outcome of the adversarially-verified judge pass Procedure step 3's
conditional branch already requires; it does not call a model itself and
does not change the recorded substring mean or verdict. Design spec:
`docs/superpowers/specs/2026-07-20-judge-mode-scorer-design.md`. Advisory
mechanism documentation on an already-required behavioral branch, not a new
enforced rule, so no new eval fixture was added -- same precedent as #149
above. Refs #175, #173, #174, #167.
