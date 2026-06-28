# MacKenzie Scott giving — QALY estimate (Monte Carlo)

_100,000 draws, seed 0. Total giving $26.3B (2026 base)._

## Headline

- **Median: 106k QALYs**
- Mean: 114k QALYs
- 90% interval: 60k – 191k QALYs
- Blended cost-effectiveness (median of giving ÷ QALYs): $248k/QALY
- Monetized at VSLY (median): $64.6B → benefit/cost ratio 2.5× (90% 1.1–5.0×)
- Global-health frontier counterfactual (median): 207.91M QALYs ≈ 1955× the estimate above

## QALYs by archetype

| Archetype | Median QALYs | Median $/QALY | Evidence | Credibility | Allocation |
|---|---:|---:|---|---:|---:|
| Health - mental & behavioral | 17k | $37k | RCT/lottery | 0.86 | 4% |
| Health - insurance & access | 19k | $39k | strong quasi-exp | 0.66 | 6% |
| Economic security - housing & homelessness | 12k | $55k | quasi-exp (contested) | 0.45 | 8% |
| Education (HBCUs, comm. college, scholarships) | 10k | $154k | quasi-exp (contested) | 0.45 | 18% |
| Health - community health centers | 10k | $38k | quasi-exp (contested) | 0.45 | 5% |
| Economic security - food security | 4k | $63k | observational | 0.19 | 7% |
| Economic security - cash & financial | 3k | $402k | RCT/lottery | 0.86 | 8% |
| Economic security - workforce & mobility | 2k | $155k | observational | 0.19 | 8% |
| Equity & justice | 521 | $317k | assumption | 0.04 | 22% |
| Other / general community | 759 | $109k | observational | 0.19 | 3% |
| Environment / climate | 297 | $222k | model projection | 0.11 | 4% |
| Civic / democracy / philanthropy infra | 35 | $705k | assumption | 0.04 | 4% |
| Arts & culture | 12 | $1.4M | assumption | 0.04 | 3% |

_Each effect is shrunk toward the null in proportion to its causal-identification credibility (Evidence column): a lottery RCT (Cesarini) and a difference-in-differences on linked mortality records (Miller et al. 2021) keep most of their effect; an associational SNAP correlation or an assumption-only bucket is shrunk hard. Health-access cost-per-QALY is additionally derived from causal mortality estimates. See data/parameters.yaml (`identification:` per archetype) and SOURCES.md._

## What drives the uncertainty (Spearman tornado)

| Input | Rank correlation with total QALYs |
|---|---:|
| Realization factor (global) | +0.39 |
| $/QALY · Education (HBCUs, comm. college, scholarships) | -0.29 |
| $/QALY · Health - mental & behavioral | -0.28 |
| Allocation · Health - mental & behavioral | +0.27 |
| $/QALY · Economic security - housing & homelessness | -0.25 |
| Allocation · Health - insurance & access | +0.22 |
| $/QALY · Health - insurance & access | -0.18 |
| Allocation · Equity & justice | -0.18 |
| Credibility · Economic security - housing & homelessness | +0.16 |
| $/QALY · Health - community health centers | -0.15 |
| Credibility · Education (HBCUs, comm. college, scholarships) | +0.13 |
| $/QALY · Economic security - cash & financial | -0.13 |

_Positive: larger input → more QALYs (allocations, realization). Negative: larger input → fewer QALYs (a higher $/QALY is less cost-effective)._
