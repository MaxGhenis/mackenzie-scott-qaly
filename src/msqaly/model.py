"""The cost-effectiveness model.

Pipeline (all vectorized over `n` Monte Carlo draws):

    1. Build a shared `qaly_per_death_averted` from a discounted, quality-
       weighted remaining-life annuity.
    2. Draw a global `realization_factor` (GiveWell-style adjustment).
    3. Draw the dollar allocation across archetypes from a Dirichlet centered
       on the parameter file's `allocation_share` values.
    4. For each archetype, obtain a cost-per-QALY -- either drawn directly or
       DERIVED from a causal estimate (cost-per-life, or a fraction of the
       Medicare cost of an equivalent mortality reduction).
    5. QALYs = dollars * share * realization / cost_per_qaly, summed.
    6. Monetize at VSLY and compare to the global-health frontier.

Everything is plain numpy; no hidden state. Re-running with the same seed
reproduces results exactly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from .distributions import sample

DEFAULT_PARAMS = Path(__file__).resolve().parents[2] / "data" / "parameters.yaml"


def load_params(path: str | Path | None = None) -> dict:
    path = Path(path) if path else DEFAULT_PARAMS
    with open(path) as fh:
        return yaml.safe_load(fh)


def discounted_qale(years: np.ndarray, utility: np.ndarray, rate: float) -> np.ndarray:
    """Present value of `utility` QALYs per year for `years` years, discounted
    annually at `rate`. Closed-form annuity:  u * (1 - (1+r)^-L) / r."""
    years = np.maximum(years, 0.0)
    if rate <= 0:
        return utility * years
    return utility * (1.0 - (1.0 + rate) ** (-years)) / rate


@dataclass
class Results:
    n: int
    seed: int
    total_giving: float
    total_qalys: np.ndarray                       # (n,)
    per_archetype: dict                           # label -> (n,) QALYs
    cost_per_qaly: dict                           # label -> (n,) $/QALY
    credibility: dict                             # label -> (n,) causal-credibility weight
    qaly_per_death: np.ndarray                    # (n,)
    value_usd: np.ndarray                         # (n,) QALYs monetized at VSLY
    bc_ratio: np.ndarray                          # (n,) value / giving
    frontier_qalys: np.ndarray                    # (n,) same $ at global frontier
    blended_cost_per_qaly: np.ndarray             # (n,) giving / total_qalys
    order: list = field(default_factory=list)     # archetype labels, allocation order
    realization: np.ndarray | None = None         # (n,) global realization factor
    shares: np.ndarray | None = None              # (n, k) sampled allocation
    share_labels: list = field(default_factory=list)

    # -- convenience summaries -------------------------------------------------
    @staticmethod
    def _pct(a, q):
        return float(np.percentile(a, q))

    def summary(self) -> dict:
        tq = self.total_qalys
        contrib = {lab: float(np.mean(v)) for lab, v in self.per_archetype.items()}
        return {
            "total_qalys": {
                "mean": float(np.mean(tq)),
                "median": self._pct(tq, 50),
                "p05": self._pct(tq, 5),
                "p95": self._pct(tq, 95),
            },
            "blended_cost_per_qaly_median": self._pct(self.blended_cost_per_qaly, 50),
            "value_usd": {
                "mean": float(np.mean(self.value_usd)),
                "median": self._pct(self.value_usd, 50),
            },
            "bc_ratio": {
                "median": self._pct(self.bc_ratio, 50),
                "p05": self._pct(self.bc_ratio, 5),
                "p95": self._pct(self.bc_ratio, 95),
            },
            "frontier_qalys_median": self._pct(self.frontier_qalys, 50),
            "frontier_multiple_median": self._pct(self.frontier_qalys / tq, 50),
            "per_archetype_mean": contrib,
        }


def run(params: dict, n: int = 100_000, seed: int = 0) -> Results:
    rng = np.random.default_rng(seed)
    giving = float(params["meta"]["total_giving_usd"])
    rate = float(params["meta"]["discount_rate"])
    cpq_floor = float(params["meta"].get("cost_per_qaly_floor_usd", 1.0))

    # 1. QALYs per premature death averted (shared across mortality-based archetypes)
    qd = params["conversions"]["qaly_per_death_averted"]
    L = sample(qd["remaining_life_expectancy"], n, rng)
    u = np.clip(sample(qd["utility_weight"], n, rng), 0.01, 1.0)
    qaly_per_death = discounted_qale(L, u, rate)

    # 2. Global realization factor
    realization = np.clip(sample(params["realization_factor"], n, rng), 0.0, None)

    # 3. Dirichlet allocation centered on the parameter-file shares
    arche = params["archetypes"]
    labels = [a["label"] for a in arche.values()]
    central = np.array([a["allocation_share"] for a in arche.values()], dtype=float)
    central = central / central.sum()
    conc = float(params.get("allocation_concentration", 50))
    shares = rng.dirichlet(central * conc, size=n)        # (n, k)

    # 4-5. Per-archetype cost-per-QALY, causal credibility, and QALYs
    tiers = params.get("evidence_tiers", {})
    per_archetype: dict = {}
    cost_per_qaly: dict = {}
    credibility: dict = {}
    total = np.zeros(n)
    for j, (key, a) in enumerate(arche.items()):
        method = a.get("method", "cost_per_qaly")
        if method == "cost_per_qaly":
            cpq = sample(a["cost_per_qaly_usd"], n, rng)
        elif method == "cost_per_life":
            cpl = sample(a["cost_per_life_usd"], n, rng)
            cpq = cpl / qaly_per_death
        elif method == "cost_per_qaly_derived_chc":
            med = sample(a["medicare_cost_per_lifeyear_usd"], n, rng)
            frac = sample(a["chc_fraction_of_medicare"], n, rng)
            cpq = med * frac
        else:
            raise ValueError(f"Unknown method {method!r} for archetype {key!r}")

        cpq = np.maximum(cpq, cpq_floor)

        # Causal-credibility shrinkage toward the null (zero health effect),
        # weight drawn from the archetype's evidence tier. A higher-credibility
        # design keeps more of the literature effect; a weak/observational one
        # is shrunk hard.
        tier_name = a.get("causal_credibility")
        if tier_name:
            if tier_name not in tiers:
                raise ValueError(f"Archetype {key!r} cites unknown tier {tier_name!r}")
            t = tiers[tier_name]
            cred = sample(
                {"dist": "beta", "mean": t["mean"], "concentration": t["concentration"]},
                n, rng,
            )
        else:
            cred = np.ones(n)
        cred = np.clip(cred, 0.0, 1.0)

        dollars = giving * shares[:, j]
        q = dollars * realization * cred / cpq
        per_archetype[a["label"]] = q
        cost_per_qaly[a["label"]] = cpq
        credibility[a["label"]] = cred
        total += q

    # 6. Monetize and frontier comparison
    vsly = sample(params["conversions"]["vsly_usd"], n, rng)
    value_usd = total * vsly
    bc_ratio = value_usd / giving
    frontier_cpq = sample(params["conversions"]["frontier_cost_per_qaly_usd"], n, rng)
    frontier_qalys = giving / frontier_cpq
    blended = giving / np.maximum(total, 1e-9)

    return Results(
        n=n, seed=seed, total_giving=giving,
        total_qalys=total, per_archetype=per_archetype, cost_per_qaly=cost_per_qaly,
        credibility=credibility, qaly_per_death=qaly_per_death, value_usd=value_usd,
        bc_ratio=bc_ratio, frontier_qalys=frontier_qalys, blended_cost_per_qaly=blended,
        order=labels, realization=realization, shares=shares, share_labels=labels,
    )


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman rank correlation (no scipy dependency)."""
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    rx -= rx.mean()
    ry -= ry.mean()
    denom = np.sqrt((rx @ rx) * (ry @ ry))
    return float(rx @ ry / denom) if denom else 0.0


def driver_sensitivity(res: Results) -> list[tuple[str, float]]:
    """Rank inputs by |Spearman correlation| with total QALYs -- a probabilistic
    (one-way) sensitivity analysis identifying what drives the spread."""
    total = res.total_qalys
    rows: list[tuple[str, float]] = [
        ("Realization factor (global)", _spearman(res.realization, total)),
        ("QALYs per death averted", _spearman(res.qaly_per_death, total)),
    ]
    for j, label in enumerate(res.share_labels):
        rows.append((f"$/QALY · {label}", _spearman(res.cost_per_qaly[label], total)))
        rows.append((f"Credibility · {label}", _spearman(res.credibility[label], total)))
        rows.append((f"Allocation · {label}", _spearman(res.shares[:, j], total)))
    rows.sort(key=lambda t: abs(t[1]), reverse=True)
    return rows
