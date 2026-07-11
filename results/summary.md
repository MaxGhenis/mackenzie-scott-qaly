# MacKenzie Scott giving — QALY estimate (Monte Carlo)

_100,000 draws, seed 0. Total giving $30.3B (2026 base)._

## Headline

- **Median: 71k QALYs**
- Mean: 77k QALYs
- 90% interval: 38k – 139k QALYs
- Blended cost-effectiveness (median of giving ÷ QALYs): $430k/QALY
- Monetized at HHS VQALY (median): $52.3B → benefit/cost ratio 1.7× (90% 0.8–3.7×)
- Global-health frontier (median, handicapped like-for-like with the same realization + RCT-grade credibility): 105.51M QALYs ≈ 1490× the estimate above

## QALYs by archetype

| Archetype | Median QALYs | Median $/QALY | Evidence | Credibility | Allocation |
|---|---:|---:|---|---:|---:|
| Education (HBCUs, comm. college, scholarships) | 13k | $154k | quasi-exp (contested) | 0.45 | 20% |
| Health - insurance & access | 11k | $63k | strong quasi-exp | 0.66 | 5% |
| Health - mental & behavioral | 6k | $61k | RCT/lottery | 0.86 | 2% |
| Economic security - workforce & mobility | 4k | $155k | observational | 0.19 | 14% |
| Economic security - housing & homelessness | 4k | $81k | quasi-exp (contested) | 0.44 | 4% |
| Health - community health centers | 4k | $104k | quasi-exp (contested) | 0.45 | 5% |
| Other / general community | 2k | $109k | observational | 0.19 | 6% |
| Economic security - cash & financial | 2k | $399k | RCT/lottery | 0.86 | 4% |
| Environment / climate | 701 | $223k | model projection | 0.11 | 7% |
| Economic security - food security | 883 | $63k | observational | 0.19 | 2% |
| Equity & justice | 427 | $317k | assumption | 0.04 | 16% |
| Civic / democracy / philanthropy infra | 124 | $708k | assumption | 0.04 | 11% |
| Arts & culture | 14 | $1.4M | assumption | 0.04 | 3% |

_Each effect is shrunk toward the null in proportion to its causal-identification credibility (Evidence column): a lottery RCT (Cesarini) and a difference-in-differences on linked mortality records (Miller et al. 2021) keep most of their effect; an associational SNAP correlation or an assumption-only bucket is shrunk hard. Health-access cost-per-QALY is additionally derived from causal mortality estimates. See data/parameters.yaml (`identification:` per archetype) and SOURCES.md._

## What drives the uncertainty (Spearman tornado)

| Input | Rank correlation with total QALYs |
|---|---:|
| $/QALY · Education (HBCUs, comm. college, scholarships) | -0.47 |
| Realization factor (global) | +0.35 |
| Credibility · Education (HBCUs, comm. college, scholarships) | +0.22 |
| Allocation · Health - mental & behavioral | +0.20 |
| Allocation · Health - insurance & access | +0.20 |
| $/QALY · Economic security - workforce & mobility | -0.18 |
| $/QALY · Health - mental & behavioral | -0.16 |
| Credibility · Economic security - workforce & mobility | +0.16 |
| $/QALY · Health - insurance & access | -0.15 |
| $/QALY · Economic security - housing & homelessness | -0.13 |
| Allocation · Equity & justice | -0.12 |
| $/QALY · Economic security - cash & financial | -0.11 |

_Positive: larger input → more QALYs (allocations, realization). Allocation shares are compositional (they sum to 1), so a share's correlation is relative to the buckets it displaces. Negative: larger input → fewer QALYs (a higher $/QALY is less cost-effective)._
