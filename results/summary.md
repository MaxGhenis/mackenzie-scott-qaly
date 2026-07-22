# MacKenzie Scott giving — QALY estimate (Monte Carlo)

_100,000 draws, seed 0. Total giving $30.3B (2026 base)._

## Headline

- **Median: 202k QALYs**
- Mean: 222k QALYs
- 90% interval: 94k – 419k QALYs
- Blended cost-effectiveness (median of giving ÷ QALYs): $150k/QALY
- Monetized at HHS VQALY (median): $148.8B → benefit/cost ratio 4.9× (90% 2.1–11.0×)
- Global-health frontier (median, handicapped like-for-like with the same realization + RCT-grade credibility): 105.54M QALYs ≈ 521× the estimate above

## QALYs by archetype

| Archetype | Median QALYs | Median $/QALY | Evidence | Credibility | Allocation |
|---|---:|---:|---|---:|---:|
| Global health & development (non-US delivery) | 132k | $5k | strong quasi-exp | 0.66 | 5% |
| Education (HBCUs, comm. college, scholarships) | 12k | $155k | quasi-exp (contested) | 0.45 | 19% |
| Health - insurance & access | 8k | $63k | strong quasi-exp | 0.66 | 4% |
| Health - mental & behavioral | 6k | $61k | RCT/lottery | 0.86 | 2% |
| Economic security - workforce & mobility | 3k | $155k | observational | 0.19 | 13% |
| Economic security - housing & homelessness | 4k | $81k | quasi-exp (contested) | 0.45 | 4% |
| Health - community health centers | 3k | $104k | quasi-exp (contested) | 0.45 | 4% |
| Other / general community | 2k | $110k | observational | 0.19 | 6% |
| Environment / climate | 782 | $225k | model projection | 0.11 | 8% |
| Economic security - cash & financial | 1k | $273k | strong quasi-exp | 0.66 | 3% |
| Economic security - food security | 821 | $63k | observational | 0.19 | 2% |
| Equity & justice | 463 | $315k | assumption | 0.04 | 17% |
| Civic / democracy / philanthropy infra | 122 | $701k | assumption | 0.04 | 11% |
| Arts & culture | 16 | $1.4M | assumption | 0.04 | 3% |

_Each effect is shrunk toward the null in proportion to its causal-identification credibility (Evidence column): a lottery RCT (Cesarini) and a difference-in-differences on linked mortality records (Miller et al. 2021) keep most of their effect; an associational SNAP correlation or an assumption-only bucket is shrunk hard. Health-access cost-per-QALY is additionally derived from causal mortality estimates. See data/parameters.yaml (`identification:` per archetype) and SOURCES.md._

## What drives the uncertainty (Spearman tornado)

| Input | Rank correlation with total QALYs |
|---|---:|
| Allocation · Global health & development (non-US delivery) | +0.83 |
| Realization factor (global) | +0.30 |
| Credibility · Global health & development (non-US delivery) | +0.29 |
| $/QALY · Education (HBCUs, comm. college, scholarships) | -0.15 |
| Allocation · Equity & justice | -0.11 |
| Allocation · Civic / democracy / philanthropy infra | -0.09 |
| Allocation · Economic security - workforce & mobility | -0.08 |
| Allocation · Education (HBCUs, comm. college, scholarships) | -0.07 |
| Credibility · Education (HBCUs, comm. college, scholarships) | +0.07 |
| Allocation · Environment / climate | -0.06 |
| $/QALY · Global health & development (non-US delivery) | -0.06 |
| Credibility · Economic security - workforce & mobility | +0.05 |

_Positive: larger input → more QALYs (allocations, realization). Allocation shares are compositional (they sum to 1), so a share's correlation is relative to the buckets it displaces. Negative: larger input → fewer QALYs (a higher $/QALY is less cost-effective)._
