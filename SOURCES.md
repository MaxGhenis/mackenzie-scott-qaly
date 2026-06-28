# Sources

Annotated bibliography for every quantitative input in
[`data/parameters.yaml`](data/parameters.yaml). Each entry gives the figure used
and where it comes from. Accessed June 2026.

## Giving total and allocation

- **Total giving — $26.3B since 2019, >1,600 orgs ($7.17B in 2025).**
  CNBC, "MacKenzie Scott revealed her total charitable donations for 2025"
  (2025-12-13). https://www.cnbc.com/2025/12/13/mackenzie-scott-revealed-her-total-charitable-donations-for-2025.html
  · Alliance Magazine (2025). https://www.alliancemagazine.org/blog/mackenzie-scott-gave-7-billion-in-2025-nears-bill-gates-total-lifetime-philanthropy/
  · Wikipedia, "MacKenzie Scott" / "Yield Giving."
- **Cause-area mix (top areas: economic security & opportunity, equity &
  justice, education, health; ~$5M average grant; ~90%+ US-focused).**
  Harvard Business School Working Knowledge, "$15 Billion in Five Years: What
  Data Tells Us About MacKenzie Scott's Philanthropy."
  https://www.library.hbs.edu/working-knowledge/mackenzie-scotts-15-billion-pledge-what-the-data-says-about-her-epic-giving
  · Center for Effective Philanthropy, "Emerging Impacts: The Effects of
  MacKenzie Scott's Large, Unrestricted Gifts" (2023) — also the basis for the
  upper end of the realization factor.
  https://cep.org/wp-content/uploads/2023/11/BigGiftsStudy_Report_Y2_FNL.pdf

## Health — insurance & access (derived cost-per-life)

- **Medicaid expansion: ~1 life saved/yr per 239–316 adults covered; $327k–$867k
  per life saved (0.132 pp annual mortality decline, 9.4% reduction).**
  Miller, Johnson & Wherry, "Medicaid and Mortality: New Evidence from Linked
  Survey and Administrative Data," *Quarterly Journal of Economics* 136(3), 2021.
  https://academic.oup.com/qje/article-abstract/136/3/1783/6124639
  · NBER WP 26081: https://www.nber.org/papers/w26081

## Health — community health centers (derived as fraction of Medicare)

- **CHCs cut mortality among adults 50+ by ~2% within a decade, at 1/8 to 1/3
  the cost of the equivalent reduction through Medicare.**
  Bailey & Goodman-Bacon, "The War on Poverty's Experiment in Public Medicine:
  Community Health Centers and the Mortality of Older Americans," *American
  Economic Review* 105(3), 2015.
  https://www.aeaweb.org/articles?id=10.1257/aer.20120070
  · NBER WP 20653: https://www.nber.org/papers/w20653

## Health — mental & behavioral

- **Collaborative care for depression: ICER ~$17k–$49.5k/QALY (healthcare
  perspective), adolescents $18,239/QALY; program cost $104–$639/person/yr.**
  The $17k–$49.5k headline range is from the Community Preventive Services Task
  Force (Jacob et al., Community Guide) and Gilbody et al., *BMC Health Services
  Research* 10:19 (https://link.springer.com/article/10.1186/1472-6963-10-19).
  A broader systematic review — Grochtdreis, Brettschneider, Wegener et al.,
  *PLOS ONE* 10(5):e0123078 (2015),
  https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0123078 —
  reports ICERs ranging from dominance up to ~$153k/QALY (healthcare) and
  ~$874k/QALY (societal); the model's `lognormal_ci {15000, 90000}` brackets the
  cost-effective-case range with an upper tail toward that wider evidence.
  Adolescent figure: Wright et al. (2016), PMID 27654449.

## Economic security — housing & homelessness

- **Permanent supportive housing ~$62,493/QALY; frequently cost-saving
  ($6,875–$33,502/person/yr) for high-need chronically homeless.**
  National Academies (NASEM), *Permanent Supportive Housing: Evaluating the
  Evidence for Improving Health Outcomes* (2018).
  https://nap.nationalacademies.org/read/25133/chapter/6
  · Aubry et al., systematic review, *Lancet Public Health* 5(6), 2020.
  https://www.thelancet.com/journals/lanpub/article/PIIS2468-2667(20)30055-4/fulltext

## Economic security — food security

- **SNAP associated with ~$1,400/yr lower health spending and ~4% fewer
  hospitalizations (46% among food-insecure seniors).** (Observational; the
  parameter is downward-adjusted accordingly.)
  Center on Budget and Policy Priorities, "SNAP Is Linked With Improved Health
  Outcomes and Lower Health Care Costs."
  https://www.cbpp.org/research/food-assistance/snap-is-linked-with-improved-health-outcomes-and-lower-health-care-costs
  · Penn LDI, "Understanding the Evidence: SNAP and Health."
  https://ldi.upenn.edu/our-work/research-updates/understanding-the-evidence-snap-and-health/

## Economic security — cash & financial / workforce (income → health)

- **~Zero detectable causal effect of income on adult mortality in a rich
  country** (the reason these archetypes carry a high $/QALY).
  Cesarini, Lindqvist, Östling & Wallace, "Wealth, Health, and Child
  Development: Evidence from Administrative Data on Swedish Lottery Players,"
  *Quarterly Journal of Economics* 131(2), 2016.
- **EITC and health (mixed/positive but confounded).** AcademyHealth rapid
  evidence review (2017).
  https://academyhealth.org/sites/default/files/Updated.EITC%20Rapid%20Evidence%20Review%20FINAL.pdf

## Education → mortality

- **An additional year of schooling lowers adult mortality modestly** (Dutch
  reform ~6% lower probability of death before 89, conditional on survival to
  81; Swedish 1.2M-person quasi-experiment; Lleras-Muney 2005).
  Lager & Torssander, "Causal effect of education on mortality in a
  quasi-experiment on 1.2 million Swedes," *PNAS* 109(22), 2012.
  https://www.pnas.org/doi/10.1073/pnas.1105839109
  · Galama, Lleras-Muney & van Kippersluis, "The Effect of Education on Health
  and Mortality: A Review," NBER WP 24225.
  https://www.nber.org/papers/w24225

## Environment / climate

- **Mortality cost of carbon: ~4,434 tCO2 per excess death (2020–2100);
  mortality-inclusive social cost of carbon $258/t.**
  Bressler, "The mortality cost of carbon," *Nature Communications* 12, 2021.
  https://www.nature.com/articles/s41467-021-24487-w

## Conversions and benchmarks

- **Value of a statistical life-year (VSLY): central $611k at 3% discount
  (2026); 2024 low $231k; 7% discount $1.03M.** Used only to monetize QALYs.
  HHS ASPE, "Standard Values for Regulatory Analysis, 2026."
  https://aspe.hhs.gov/sites/default/files/documents/2d83af5823915d81871334ee08ad03d9/Standard-RIA-Values-2026.pdf
  · Methodology: https://aspe.hhs.gov/reports/updating-vsl-estimates
- **Global-health frontier: ~$78 per DALY averted / ~$3,340 per life saved**
  (insecticide-treated nets) — the counterfactual ceiling.
  GiveWell, Against Malaria Foundation. https://www.givewell.org/charities/amf
  · "Long-lasting insecticide treated nets: $3,340 per life saved, $100 per
  DALY averted," EA Forum.
  https://forum.effectivealtruism.org/posts/HbunzTyFPRwcYihg6/long-lasting-insecticide-treated-nets-usd3-340-per-life

---

_Causal estimates are transported across populations/time; the global
`realization_factor` is a coarse correction for that and for philanthropic
counterfactuals. See README "Limitations."_
