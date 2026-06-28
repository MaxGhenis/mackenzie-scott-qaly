# MacKenzie Scott giving — QALY cost-effectiveness model

[![CI](https://github.com/MaxGhenis/mackenzie-scott-qaly/actions/workflows/ci.yml/badge.svg)](https://github.com/MaxGhenis/mackenzie-scott-qaly/actions/workflows/ci.yml)

**▶ Interactive version: [maxghenis.com/mackenzie-scott-qaly](https://maxghenis.com/mackenzie-scott-qaly)** — drag the assumptions and watch the model rerun in your browser (a TypeScript port of this package, reading the same `parameters.yaml`).

A GiveWell-style, fully-parameterized Monte Carlo estimate of the health impact
— in quality-adjusted life-years (QALYs) — of MacKenzie Scott's ~**$26.3 billion**
in lifetime philanthropy (2019–2025; Yield Giving reports over $26 billion in
2,700+ gifts).

It replaces hand-waved "$/QALY by sector" guesses with cost-effectiveness ratios
that are, wherever possible, **derived from published causal estimates** (Medicaid
mortality, community health centers, supportive housing, collaborative-care
depression, education→mortality). Each effect is then **shrunk toward the null in
proportion to how credibly it is causally identified** — a lottery RCT is trusted,
an associational correlation is not — and separately discounted for the gap
between a clean study and a marginal philanthropic dollar.

> **What QALYs do and don't capture.** A QALY is a *health* metric. Most of
> Scott's giving targets economic mobility, education, and equity, whose value is
> largely **non-health** (income, opportunity, rights, wellbeing). This model
> therefore *understates* her total social impact — it answers one specific
> question: how much *health* does the money buy? See "Interpretation" below.

## Quick start

```bash
uv sync --extra dev      # Python 3.14 venv + numpy/pyyaml/matplotlib
uv run msqaly            # 100k Monte Carlo draws — prints summary (no file writes)
uv run msqaly --write    # also regenerate results/ + figures + README block
uv run pytest            # test suite
```

`--write` is what regenerates the committed [`results/`](results/) artifacts
(`summary.md`, `summary.json`, `figure.png`, `sensitivity.png`) and the README
block below; a bare `uv run msqaly` only prints, so casual runs never dirty git.

## Method

The model is a transparent pipeline over `n` Monte Carlo draws (vectorized numpy,
seeded → reproducible). All inputs live in
[`data/parameters.yaml`](data/parameters.yaml); every value carries a `source`.

1. **QALYs per death averted.** A discounted (3%/yr), quality-weighted annuity
   over remaining life expectancy, calibrated to the low-income, middle-aged/older
   adults who dominate the causal mortality studies (~26 remaining years, utility
   ~0.78) → ~11–14 QALYs per premature death averted.

2. **Dollar allocation.** Scott does not publish dollars-by-cause, so the split
   across 13 intervention archetypes is drawn from a **Dirichlet** centered on
   the best available qualitative picture (top areas: economic security, equity &
   justice, education, health), with the concentration parameter controlling how
   tightly shares hold to those centers.

3. **Cost-per-QALY per archetype.** Three derivation methods:
   - `cost_per_life` — divide a published cost-per-life-saved by QALYs-per-death.
     Used for **health insurance/access** (Miller, Johnson & Wherry 2021).
   - `cost_per_qaly_derived_chc` — a fraction of the Medicare cost of an equivalent
     mortality reduction. Used for **community health centers** (Bailey &
     Goodman-Bacon 2015).
   - `cost_per_qaly` — drawn directly from the cost-effectiveness literature
     (housing, mental health, food security) or, for indirect buckets, a
     deliberately wide distribution: *anchored to* a causal study where one exists
     (education→mortality; climate mortality-cost-of-carbon) and to an explicit
     *skeptical prior* where none does (equity & justice, civic, arts). Each
     `cost_per_qaly` is the cost-effectiveness **conditional on the effect being
     real** — all causal doubt lives in the credibility axis (step 4), not here,
     so the two never double-count. Concretely, the ranges are the *as-if-causal*
     cost-effectiveness and are deliberately **not** also widened for confounding
     (that is the credibility weight's job). This is an explicit modeling
     assertion — the data alone cannot enforce it — and it biases mildly *down*
     (a real effect is discounted once via credibility) rather than up.

4. **Causal credibility (the evidence-quality axis).** Each archetype is rated by
   the identification design of its evidence — `randomized` (RCT/lottery),
   `strong_quasi`, `moderate_quasi`, `observational`, `projection`, or
   `assumption` — and a credibility weight is drawn from that tier's Beta
   distribution (mean 0.85 → 0.07; weaker designs are also wider). It linearly
   shrinks QALYs/dollar toward the null of *no health effect*. This is what keeps
   an associational SNAP correlation or an assumption-only bucket from counting
   the same as a difference-in-differences on linked mortality records. Note the
   axis is about *trust in the estimate*, not its size: the income→mortality
   lottery RCT is high-credibility precisely because it credibly shows a *small*
   effect.

5. **Realization factor.** One global multiplier (triangular, mode 0.80, range
   0.55–1.10) for the *implementation/attribution* gap — does Scott's marginal
   unrestricted dollar deliver the studied intervention — net of the capacity
   benefits of large unrestricted gifts (CEP 2023). Kept orthogonal to
   credibility, which now carries the "evidence may be overstated" discount.

6. **QALYs** = dollars × share × realization × credibility ÷ cost-per-QALY,
   summed across archetypes.

7. **Monetize & benchmark.** QALYs × VSLY (HHS 2026 central $611k) gives a
   benefit/cost ratio; the same dollars at the global-health frontier
   (loguniform $50–150 **per QALY-equivalent**, central ~$87) are *handicapped
   with the same realization and credibility* so the counterfactual benchmark is
   like-for-like, not a raw ceiling. The parameter note documents the cited
   GiveWell lives-saved/DALY figures and the one-year-of-full-health conversion
   convention.

## Results

See [`results/summary.md`](results/summary.md) (regenerated by `uv run msqaly
--write`). Headline figures are reproduced there rather than hard-coded here, so
the README never drifts from the model. As of the committed run:

<!-- RESULTS:START -->
**Median ≈ 98k QALYs** (mean 105k; 90% interval 54k–180k), a blended **$270k/QALY**. Monetized at VSLY that is **$59.4B** of health value — a **2.3× benefit/cost ratio**. The same $26.3B at the global-health frontier (~$87/QALY-equivalent), handicapped with the same realization and evidence discounts, would still buy ~207.91M QALYs — about **2126× more health per dollar**, the price of funding a rich country's social fabric rather than the global frontier.

![Estimated QALYs](results/figure.png)

The spread is driven mostly by the global realization factor, the causal-credibility weights, and the cost-per-QALY of the largest buckets (education, equity & justice):

![Sensitivity](results/sensitivity.png)

_Full table: [results/summary.md](results/summary.md). Regenerate with `uv run msqaly --write`._
<!-- RESULTS:END -->

## Interpretation

- **The estimate is dominated by the cost-per-QALY *and credibility* assumptions,
  not the dollar total.** Grounding the ratios in causal estimates and then
  weighting by identification quality (rather than a flat US cost-effectiveness
  threshold) is the whole point of this repo.
- **Causal skepticism roughly halves the headline.** Taking evidence quality
  seriously drops the central estimate from trusting every cited effect at face
  value to the lower evidence-weighted estimate. The buckets that survive are
  the ones with the strongest designs
  (collaborative-care RCTs, the Medicaid difference-in-differences); the largest
  *dollar* buckets (equity & justice, education) contribute little health because
  no credible study ties those grants to QALYs — their value is real but largely
  non-health.
- **US ≠ global-health frontier.** Preventing a death costs orders of magnitude
  more in a rich country than via bed nets abroad; the frontier comparison
  quantifies that gap, and is not a criticism of her choices.
- **QALYs ≠ total value.** A WELLBY (wellbeing-year) or consumption-value frame
  would credit the economic-security and education giving far more. This model is
  deliberately scoped to health.

## Limitations

- Allocation shares are an informed prior, not Scott's actual ledger. Swapping in
  a dollar-coded recipient database (Yield Giving) would sharpen step 2.
- Several archetypes (equity & justice, civic, arts) have no clean health pathway;
  their wide distributions reflect genuine ignorance, not measured effect.
- Causal estimates are transported across populations and time; the realization
  factor is a coarse correction.
- Effects are modeled as static cost-per-QALY ratios, not a dynamic life-table
  microsimulation.

## Layout

```
data/parameters.yaml     all inputs, each with a citation
src/msqaly/
  distributions.py       spec -> Monte Carlo samples
  model.py               causal chains + propagation
  cli.py                 run, summarize, plot
tests/test_model.py      integrity, distribution, and end-to-end tests
SOURCES.md               annotated bibliography
results/                 generated outputs (committed)
```

## Sources

Full annotated bibliography in [`SOURCES.md`](SOURCES.md). Not affiliated with,
or endorsed by, MacKenzie Scott, Yield Giving, or GiveWell.
