# MacKenzie Scott giving — QALY estimate (Monte Carlo)

_500,000 draws, seed 0. Total giving $26.3B (2026 base)._

## Headline

- **Median: 106k QALYs**
- Mean: 113k QALYs
- 90% interval: 59k – 192k QALYs
- Blended cost-effectiveness (median): $248k/QALY
- Monetized at VSLY (median): $64.6B → benefit/cost ratio 2.5× (90% 1.1–5.0×)
- Global-health frontier counterfactual (median): 304.05M QALYs ≈ 2863× the estimate above

## QALYs by archetype

| Archetype | Median QALYs | Median $/QALY | Evidence | Credibility | Allocation |
|---|---:|---:|---|---:|---:|
| Health - mental & behavioral | 17k | $37k | RCT/lottery | 0.86 | 4% |
| Health - insurance & access | 19k | $39k | strong quasi-exp | 0.66 | 6% |
| Economic security - housing & homelessness | 12k | $55k | quasi-exp (contested) | 0.45 | 8% |
| Education (HBCUs, comm. college, scholarships) | 10k | $155k | quasi-exp (contested) | 0.45 | 18% |
| Health - community health centers | 10k | $38k | quasi-exp (contested) | 0.45 | 5% |
| Economic security - food security | 4k | $63k | observational | 0.19 | 7% |
| Economic security - cash & financial | 3k | $400k | RCT/lottery | 0.86 | 8% |
| Economic security - workforce & mobility | 2k | $155k | observational | 0.19 | 8% |
| Equity & justice | 515 | $316k | assumption | 0.04 | 22% |
| Other / general community | 762 | $110k | observational | 0.19 | 3% |
| Environment / climate | 294 | $224k | model projection | 0.11 | 4% |
| Civic / democracy / philanthropy infra | 34 | $707k | assumption | 0.04 | 4% |
| Arts & culture | 12 | $1.4M | assumption | 0.04 | 3% |

_Each effect is shrunk toward the null in proportion to its causal-identification credibility (Evidence column): a lottery RCT (Cesarini) and a difference-in-differences on linked mortality records (Miller et al. 2021) keep most of their effect; an associational SNAP correlation or an assumption-only bucket is shrunk hard. Health-access cost-per-QALY is additionally derived from causal mortality estimates. See data/parameters.yaml (`identification:` per archetype) and SOURCES.md._

## What drives the uncertainty (Spearman tornado)

| Input | Rank correlation with total QALYs |
|---|---:|
| Realization factor (global) | +0.38 |
| $/QALY · Education (HBCUs, comm. college, scholarships) | -0.29 |
| $/QALY · Health - mental & behavioral | -0.29 |
| Allocation · Health - mental & behavioral | +0.28 |
| $/QALY · Economic security - housing & homelessness | -0.25 |
| Allocation · Health - insurance & access | +0.22 |
| $/QALY · Health - insurance & access | -0.18 |
| Allocation · Equity & justice | -0.17 |
| Credibility · Economic security - housing & homelessness | +0.15 |
| $/QALY · Health - community health centers | -0.15 |
| Credibility · Education (HBCUs, comm. college, scholarships) | +0.14 |
| $/QALY · Economic security - cash & financial | -0.13 |

_Positive: larger input → more QALYs (allocations, realization). Negative: larger input → fewer QALYs (a higher $/QALY is less cost-effective)._
