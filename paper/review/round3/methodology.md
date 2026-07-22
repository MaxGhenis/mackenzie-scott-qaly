# Methodology referee report — round 3

| Round-2 item | Status | Verification against fresh text |
|---:|---|---|
| 1 | ACCEPTABLE DEFERRAL | The archetype-level uncertainty ledger and one-factor-off runs remain absent, but the manuscript still states that the two-multiplier partition is imperfect and identifies the mixed-evidence overlap (§3 and §7). That is an adequately prominent limitation for an SSRN working paper. |
| 2 | ACCEPTABLE DEFERRAL | There is still no concentration sweep or propagation of gift-pipeline uncertainty. The concentration (60), judgment-prior meaning, illustrative global-health interval, and excluded uncertainties remain explicit (§3 and §7), so the deferral is transparent. |
| 3 | ACCEPTABLE DEFERRAL | Robust/clustered inference, validation, influence analysis, and propagation of imputation uncertainty remain deferred. The fresh text retains the selected-sample flow, repeated-gift and pooling caveats, median fallbacks, and the “descriptive and conditional”/“not a validated prediction rule” qualification (§2.2). |
| 4 | NOT RESOLVED | The caption and body correctly define a **near**-RCT-only to **near**-face-value scenario path, but the introduction still says “counting only randomized evidence,” the plotted tick labels omit “near,” and §7 still calls the sweep an “honest bound” even though the caption says “not a bound” (rendered lines 51–52, 600–610, 711–717). Make all three labels match the exact scenario definition. |
| 5 | PARTIALLY RESOLVED | The paper accurately reports a fixed 3% analysis under source-specific conventions. The repository's general discount-rate control still rescales mortality conversions, VQALY, and the frontier but not direct cost-per-QALY anchors; it therefore remains a partial conversion sensitivity and should be labeled as such. This artifact-level issue does not invalidate the paper's 3% default result. |
| 6 | RESOLVED | §4.2 now says the frontier shares each realization draw and receives RCT-grade credibility, matching the independent frontier credibility draw in the model. The generated summary uses the same accurate distinction. |
| 7 | NOT RESOLVED (artifact) | The manuscript's Table 1 remains correct. `results/summary.md` still presents nonadditive archetype medians while sorting rows by mean contribution, without saying so. Add a note that medians do not add and rows are ordered by mean QALYs; this is not a manuscript-blocking issue. |
| 10 | ACCEPTABLE DEFERRAL | The interval remains correctly labeled a probabilistic-sensitivity range and the omitted uncertainty sources remain listed. No convergence calculation, compact dependence specification, or demonstrated Monte Carlo-error estimate has been added; “a few hundred QALYs” is still asserted rather than shown. For a working paper, the fixed seed, 100,000 draws, and explicit limitation make this a reasonable deferral, though reporting the calculation would improve the final version. |
| Round-2 new finding 1 | RESOLVED | §7 now describes a partial accounting that omits non-health benefits and possible harms and explicitly says it is “not a floor on total wellbeing,” consistent with the introduction (rendered lines 711–717). |

## New findings

1. **SEVERITY: MINOR**  
   **LOCATION:** `paper/review/rendered.txt` lines 142–146 and 724–725; `paper/index.qmd` lines 136 and 311.  
   **Problem:** The revised data section now correctly says Europe & Central Asia plus Canada are not classified by income here and that the bucket's true high-income share is unidentified. The limitations section still calls the combined roughly one-fifth “unattributable and high-income-region dollars,” contradicting that correction.  
   **Fix:** Replace that phrase with “unattributable and Europe & Central Asia plus Canada dollars,” or “unattributable and potentially high-income-region dollars.”

The brief regression pass found no other new methodological problem.

RECOMMENDATION: Minor revisions
