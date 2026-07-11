# Sources

Annotated bibliography for every quantitative input in
[`data/parameters.yaml`](data/parameters.yaml). Each entry gives the figure
used, where it comes from, and the price-level conversion applied (all dollar
inputs are expressed in 2026 dollars; CPI-U index values from
[FRED CPIAUCNS](https://fred.stlouisfed.org/series/CPIAUCNS), target = May 2026
335.123). Accessed June–July 2026.

## Giving total (nominal tranches → 2026 dollars)

- **$26.30B nominal, 2020–2025, inflated tranche-by-tranche to ~$30.2B (2026$).**
  Tranches: Jul 2020 $1.68B and Dec 2020 $4.16B (Scott's Medium letters, widely
  reported); Jun 2021 $2.74B; Mar 2022 $3.86B (gifts since Jun 2021, booked
  conservatively at the 2022 price level); Nov 2022 $1.99B; 2023 ~$2.10B and
  2024 ~$2.07B (Yield Giving year totals as reported by CNBC); 2025 $7.165B and
  the ~$26.3B cumulative:
  [CNBC, 2025-12-13](https://www.cnbc.com/2025/12/13/mackenzie-scott-revealed-her-total-charitable-donations-for-2025.html).
  A $0.535B reconciliation residual (undisclosed/smaller gifts) is booked at
  the 2023 price level. [Yield Giving](https://yieldgiving.com/) itself says
  "over $26B in 2,700+ gifts" — the exact $26.3B comes from the CNBC year-end
  accounting, not the Yield page.
- **Cause-area mix.** [HBS Working Knowledge analysis of Yield Giving
  recipients](https://www.library.hbs.edu/working-knowledge/mackenzie-scotts-15-billion-pledge-what-the-data-says-about-her-epic-giving)
  (largest areas: equity & justice, education, economic security, health;
  average disclosed gift ~$8.4M). Exact allocation percentages in the model are
  author estimates around that qualitative picture — Scott does not publish
  dollars by cause. · [Center for Effective Philanthropy
  (2023)](https://cep.org/wp-content/uploads/2023/11/BigGiftsStudy_Report_Y2_FNL.pdf)
  on the capacity effects of large unrestricted gifts (basis for letting the
  realization factor exceed 1).

## Health — insurance & access (derived cost-per-life)

- **Cost per life saved: $327k–$867k in 2007 dollars → $529k–$1.40M (2026$,
  ×1.616 from CPI-U 207.342 → 335.123).**
  [Sommers, "State Medicaid Expansions and Mortality, Revisited: A Cost-Benefit
  Analysis," *American Journal of Health Economics* 3(3), 2017](https://www.journals.uchicago.edu/doi/10.1162/ajhe_a_00080)
  ([open copy](https://dash.harvard.edu/server/api/core/bitstreams/7312037d-ed01-6bd4-e053-0100007fdf3b/content)),
  p. 30: "a cost per life saved ranging from $327,000 to $867,000 (Appendix
  Table A.4) in 2007 dollars," from Cost = NNT × [$778 × (1+DWL) + $3,156 ×
  DWL], NNT 239–316, OHIE spending effects (Finkelstein et al. 2012, Table V,
  2007 dollars), deadweight loss 15–50%. *(An earlier revision of this repo
  misattributed the range to Sommers, Baicker & Epstein's 2012 NEJM paper —
  that paper established the mortality effect for these expansions; the
  cost-benefit arithmetic is the 2017 single-author reanalysis.)*
- **Mortality-effect corroboration (identification tier).**
  [Miller, Johnson & Wherry, *QJE* 136(3), 2021](https://academic.oup.com/qje/article-abstract/136/3/1783/6124639)
  ([NBER WP 26081](https://www.nber.org/papers/w26081)): ACA Medicaid expansion
  reduced annual mortality 0.132 pp (9.4%) among newly eligible adults.

## Health — community health centers (derived cost-per-life-year)

- **~$54,000 per life-year in 2012 dollars → ~$79k (2026$, ×1.460 from CPI-U
  229.594 → 335.123); model prior $55k–$115k/life-year, converted to $/QALY by
  dividing by the utility-weight draw.**
  [Bailey & Goodman-Bacon, *AER* 105(3), 2015](https://www.aeaweb.org/articles?id=10.1257/aer.20120070)
  ([full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC4436657/)): "a
  cost-per-year-of-life ratio of approximately $54,000"; Medicare comparison
  "$161,373 and $459,000 in 2012 dollars — 3 to 8 times the ratio for CHCs."
  *(An earlier revision multiplied an invented Medicare $/life-year prior by
  the paper's ⅛–⅓ ratio and used the product as $/QALY without converting
  life-years to QALYs; this rebuild uses the paper's direct figure and makes
  the conversion explicit.)*

## Health — mental & behavioral

- **Anchors inflated from 2000s nominal: Gilbody et al. $17k–$39k/QALY and the
  Community Guide's highest $49.5k/QALY, treated as ~2006 dollars → ~$28k–$82k
  (×1.66 from CPI-U 201.6 → 335.123); prior {25k, 140k} with the upper tail
  toward Grochtdreis et al.'s wider healthcare-perspective range (up to ~$153k).**
  [Gilbody et al., *BMC Health Services Research* 10:19](https://link.springer.com/article/10.1186/1472-6963-10-19)
  · [Community Preventive Services Task Force](https://www.thecommunityguide.org/findings/mental-health-and-mental-illness-collaborative-care-management-depressive-disorders.html)
  · [Grochtdreis, Brettschneider, Wegener et al., *PLOS ONE* 10(5):e0123078,
  2015](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0123078).

## Economic security — housing & homelessness

- **Point anchor $62,493/QALY (Housing & Health intervention, HIV-positive
  unstably-housed cohort, study 2004–2008), treated as ~2008 dollars → ~$97k
  (×1.56 from CPI-U 215.303 → 335.123); prior {30k, 220k}.**
  [Holtgrave et al., *AIDS and Behavior* 17(5), 2013](https://link.springer.com/article/10.1007/s10461-012-0204-3).
  [NASEM (2018), *Permanent Supportive Housing*](https://nap.nationalacademies.org/read/25133/chapter/6)
  is cited for the mixed-evidence assessment of PSH health effects only.
  · [Aubry et al., *Lancet Public Health* 5(6), 2020](https://www.thelancet.com/journals/lanpub/article/PIIS2468-2667(20)30055-4/fulltext).

## Economic security — food security

- **Judgmental range conditional on causality; associational anchors.**
  [CBPP, "SNAP Is Linked With Improved Health Outcomes and Lower Health Care
  Costs"](https://www.cbpp.org/research/food-assistance/snap-is-linked-with-improved-health-outcomes-and-lower-health-care-costs)
  · [Penn LDI evidence review](https://ldi.upenn.edu/our-work/research-updates/understanding-the-evidence-snap-and-health/).

## Economic security — cash & financial / workforce (income → health)

- **~Zero detectable causal effect of wealth on adult mortality in a rich
  country** (the reason these archetypes carry high, wide $/QALY priors).
  [Cesarini, Lindqvist, Östling & Wallace, *QJE* 131(2), 2016](https://academic.oup.com/qje/article/131/2/687/2606947).
- **EITC and health (mixed/confounded).**
  [AcademyHealth rapid evidence review (2017)](https://academyhealth.org/sites/default/files/Updated.EITC%20Rapid%20Evidence%20Review%20FINAL.pdf).

## Education → mortality

- **Contested quasi-experimental literature; wide prior.**
  [van Kippersluis, O'Donnell & van Doorslaer, *J. Human Resources* 46(4),
  2011](https://jhr.uwpress.org/content/46/4/695.short) (+1 yr schooling → ~6%
  lower mortality) · [Lleras-Muney, *ReStud* 72(1), 2005](https://academic.oup.com/restud/article-abstract/72/1/189/1581055)
  · [Lager & Torssander, *PNAS* 109(22), 2012](https://www.pnas.org/doi/10.1073/pnas.1105839109)
  · [Clark & Royer, *AER* 103(6), 2013](https://www.aeaweb.org/articles?id=10.1257/aer.103.6.2087) (~null).

## Environment / climate

- **Mortality cost of carbon (projection anchor, not a derivation): ~4,434
  tCO2 per excess death (2020–2100).**
  [Bressler, *Nature Communications* 12, 2021](https://www.nature.com/articles/s41467-021-24487-w).

## Conversions and benchmarks

- **QALE calibration.** Remaining life expectancy ~26y at ~55 for low-income
  adults: [Chetty et al., *JAMA* 315(16), 2016](https://jamanetwork.com/journals/jama/fullarticle/2513561)
  (income–life-expectancy gradient). Utility ~0.78:
  [US EQ-5D-5L population norms (Jiang et al., *Qual Life Res*, 2021)](https://link.springer.com/article/10.1007/s11136-020-02650-y).
  Values are calibration judgments anchored to these sources.
- **VSLY (monetization only): triangular $285k / $611k / $931k, 2026 dollars,
  3% discount.** Central from
  [HHS ASPE Standard Values 2026](https://aspe.hhs.gov/sites/default/files/documents/2d83af5823915d81871334ee08ad03d9/Standard-RIA-Values-2026.pdf);
  low/high are the [2024 Data Point's](https://aspe.hhs.gov/sites/default/files/documents/cd2a1348ea0777b1aa918089e4965b8c/standard-ria-values.pdf)
  $231k/$754k scaled by 611/495 = 1.234 to the 2026 central, preserving
  relative spread at one price level and discount convention.
- **Global-health frontier: $110–$260 per QALY-equivalent (2026$), derived
  from $3,340–$5,500 per under-5 life saved ÷ ~25 discounted QALYs per child
  death** (remaining LE ~65y, 3% discount, half-cycle, utility ~0.87).
  [GiveWell current impact estimates](https://www.givewell.org/impact-estimates)
  (~$5,500/life for nets) · [older AMF/GiveWell summary](https://forum.effectivealtruism.org/posts/HbunzTyFPRwcYihg6/long-lasting-insecticide-treated-nets-usd3-340-per-life)
  (~$3,340/life).

---

_Causal estimates are transported across populations/time; the global
`realization_factor` (author-elicited) is the coarse correction for that and
for philanthropic counterfactuals. Evidence-tier weights, the realization
triangle, and the Dirichlet concentration are author-elicited priors — labeled
as such in the parameter file. See README "Limitations."_
