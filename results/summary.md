# MacKenzie Scott giving — QALY estimate (Monte Carlo)

_100,000 draws, seed 0. Total giving $30.2B (2026 base)._

## Headline

- **Median: 87k QALYs**
- Mean: 94k QALYs
- 90% interval: 49k – 161k QALYs
- Blended cost-effectiveness (median of giving ÷ QALYs): $348k/QALY
- Monetized at VSLY (median): $51.9B → benefit/cost ratio 1.7× (90% 0.8–3.5×)
- Global-health frontier (median, handicapped like-for-like with the same realization + RCT-grade credibility): 122.51M QALYs ≈ 1411× the estimate above

## QALYs by archetype

| Archetype | Median QALYs | Median $/QALY | Evidence | Credibility | Allocation |
|---|---:|---:|---|---:|---:|
| Education (HBCUs, comm. college, scholarships) | 12k | $155k | quasi-exp (contested) | 0.45 | 18% |
| Health - mental & behavioral | 12k | $59k | RCT/lottery | 0.86 | 4% |
| Health - insurance & access | 14k | $63k | strong quasi-exp | 0.66 | 6% |
| Economic security - housing & homelessness | 9k | $81k | quasi-exp (contested) | 0.45 | 8% |
| Economic security - food security | 4k | $63k | observational | 0.19 | 7% |
| Economic security - cash & financial | 4k | $400k | RCT/lottery | 0.86 | 8% |
| Health - community health centers | 4k | $104k | quasi-exp (contested) | 0.45 | 5% |
| Economic security - workforce & mobility | 2k | $155k | observational | 0.19 | 8% |
| Equity & justice | 604 | $317k | assumption | 0.04 | 22% |
| Other / general community | 868 | $109k | observational | 0.19 | 3% |
| Environment / climate | 338 | $224k | model projection | 0.11 | 4% |
| Civic / democracy / philanthropy infra | 39 | $710k | assumption | 0.04 | 4% |
| Arts & culture | 14 | $1.4M | assumption | 0.04 | 3% |

_Each effect is shrunk toward the null in proportion to its causal-identification credibility (Evidence column): a lottery RCT (Cesarini) and a difference-in-differences on linked mortality records (Miller et al. 2021) keep most of their effect; an associational SNAP correlation or an assumption-only bucket is shrunk hard. Health-access cost-per-QALY is additionally derived from causal mortality estimates. See data/parameters.yaml (`identification:` per archetype) and SOURCES.md._

## What drives the uncertainty (Spearman tornado)

| Input | Rank correlation with total QALYs |
|---|---:|
| $/QALY · Education (HBCUs, comm. college, scholarships) | -0.38 |
| Realization factor (global) | +0.38 |
| $/QALY · Health - mental & behavioral | -0.23 |
| Allocation · Health - mental & behavioral | +0.23 |
| $/QALY · Economic security - housing & homelessness | -0.22 |
| $/QALY · Economic security - cash & financial | -0.18 |
| Credibility · Education (HBCUs, comm. college, scholarships) | +0.18 |
| Allocation · Health - insurance & access | +0.17 |
| Allocation · Equity & justice | -0.16 |
| Credibility · Economic security - food security | +0.16 |
| $/QALY · Health - insurance & access | -0.16 |
| $/QALY · Economic security - food security | -0.15 |

_Positive: larger input → more QALYs (allocations, realization). Negative: larger input → fewer QALYs (a higher $/QALY is less cost-effective)._
