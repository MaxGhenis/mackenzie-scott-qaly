"""Command-line entry point.

    uv run msqaly                 # 100k draws, seed 0 — print only (no file writes)
    uv run msqaly --write         # also regenerate results/ + figures + README block
    uv run msqaly --n 500000 --write
    uv run msqaly --no-figure --write

Prints a summary table. Only `--write` mutates committed artifacts, so casual
runs (any --n/--seed) never dirty the repo.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .distributions import implied_median
from .model import driver_sensitivity, load_params, run

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
README = ROOT / "README.md"


def _fmt(x: float) -> str:
    """Human-readable count: 197000 -> '197k', 1.85e6 -> '1.85M'.
    Thresholds account for rounding so 999_999 -> '1.00M', not '1000k'."""
    ax = abs(x)
    if ax >= 999_500:            # rounds to >= 1.0M at the 'k' precision
        return f"{x/1e6:.2f}M"
    if ax >= 1e3:
        return f"{x/1e3:.0f}k"
    return f"{x:.0f}"


def _dollar(x: float) -> str:
    """Human-readable dollars with rounding-safe thresholds."""
    ax = abs(x)
    if ax >= 999_500_000:        # rounds to >= $1.0B
        return f"${x/1e9:.1f}B"
    if ax >= 999_500:            # rounds to >= $1.0M
        return f"${x/1e6:.1f}M"
    if ax >= 1e3:
        return f"${x/1e3:.0f}k"
    return f"${x:.0f}"


def summary_markdown(res, params) -> str:
    s = res.summary()
    tq = s["total_qalys"]
    giving = res.total_giving
    lines = []
    lines.append("# MacKenzie Scott giving — QALY estimate (Monte Carlo)\n")
    lines.append(
        f"_{res.n:,} draws, seed {res.seed}. Total giving "
        f"{_dollar(giving)} ({params['meta']['base_year']} base)._\n"
    )
    lines.append("## Headline\n")
    lines.append(f"- **Median: {_fmt(tq['median'])} QALYs**")
    lines.append(f"- Mean: {_fmt(tq['mean'])} QALYs")
    lines.append(f"- 90% interval: {_fmt(tq['p05'])} – {_fmt(tq['p95'])} QALYs")
    lines.append(
        f"- Blended cost-effectiveness (median of giving ÷ QALYs): "
        f"{_dollar(s['blended_cost_per_qaly_median'])}/QALY"
    )
    lines.append(
        f"- Monetized at VSLY (median): {_dollar(s['value_usd']['median'])} "
        f"→ benefit/cost ratio {s['bc_ratio']['median']:.1f}× "
        f"(90% {s['bc_ratio']['p05']:.1f}–{s['bc_ratio']['p95']:.1f}×)"
    )
    lines.append(
        f"- Global-health frontier (median, handicapped like-for-like with the "
        f"same realization + RCT-grade credibility): "
        f"{_fmt(s['frontier_qalys_median'])} QALYs "
        f"≈ {s['frontier_multiple_median']:.0f}× the estimate above\n"
    )

    tier_short = {
        "randomized": "RCT/lottery",
        "strong_quasi": "strong quasi-exp",
        "moderate_quasi": "quasi-exp (contested)",
        "observational": "observational",
        "projection": "model projection",
        "assumption": "assumption",
    }
    arche = params["archetypes"]
    label_to_share = {a["label"]: a["allocation_share"] for a in arche.values()}
    label_to_tier = {a["label"]: a.get("causal_credibility", "—") for a in arche.values()}

    lines.append("## QALYs by archetype\n")
    lines.append(
        "| Archetype | Median QALYs | Median $/QALY | Evidence | Credibility | Allocation |"
    )
    lines.append("|---|---:|---:|---|---:|---:|")
    ordered = sorted(
        s["per_archetype_mean"].items(), key=lambda kv: kv[1], reverse=True
    )
    for label, _mean_q in ordered:
        med_q = float(np.median(res.per_archetype[label]))
        cpq_med = float(np.median(res.cost_per_qaly[label]))
        cred_med = float(np.median(res.credibility[label]))
        tier = label_to_tier.get(label, "—")
        share = label_to_share.get(label, float("nan"))
        lines.append(
            f"| {label} | {_fmt(med_q)} | {_dollar(cpq_med)} | "
            f"{tier_short.get(tier, tier)} | {cred_med:.2f} | {share*100:.0f}% |"
        )
    lines.append("")
    lines.append(
        "_Each effect is shrunk toward the null in proportion to its "
        "causal-identification credibility (Evidence column): a lottery RCT "
        "(Cesarini) and a difference-in-differences on linked mortality records "
        "(Miller et al. 2021) keep most of their effect; an associational SNAP "
        "correlation or an assumption-only bucket is shrunk hard. Health-access "
        "cost-per-QALY is additionally derived from causal mortality estimates. "
        "See data/parameters.yaml (`identification:` per archetype) and SOURCES.md._\n"
    )

    lines.append("## What drives the uncertainty (Spearman tornado)\n")
    lines.append("| Input | Rank correlation with total QALYs |")
    lines.append("|---|---:|")
    for name, rho in driver_sensitivity(res)[:12]:
        lines.append(f"| {name} | {rho:+.2f} |")
    lines.append(
        "\n_Positive: larger input → more QALYs (allocations, realization). "
        "Negative: larger input → fewer QALYs (a higher $/QALY is less "
        "cost-effective)._\n"
    )
    return "\n".join(lines)


def readme_block(res, params) -> str:
    """Compact headline block injected between the README RESULTS markers.
    All figures (giving total, frontier central) are derived, never hardcoded."""
    s = res.summary()
    tq = s["total_qalys"]
    giving = _dollar(res.total_giving)
    frontier = implied_median(params["conversions"]["frontier_cost_per_daly_usd"])
    return (
        f"**Median ≈ {_fmt(tq['median'])} QALYs** "
        f"(mean {_fmt(tq['mean'])}; 90% interval {_fmt(tq['p05'])}–{_fmt(tq['p95'])}), "
        f"a blended **{_dollar(s['blended_cost_per_qaly_median'])}/QALY**. "
        f"Monetized at VSLY that is **{_dollar(s['value_usd']['median'])}** of health "
        f"value — a **{s['bc_ratio']['median']:.1f}× benefit/cost ratio**. "
        f"The same {giving} at the global-health frontier (~{_dollar(frontier)} per DALY "
        f"averted, treated as ≈1 QALY), handicapped with the same realization and "
        f"evidence discounts, would still "
        f"buy ~{_fmt(s['frontier_qalys_median'])} QALYs — about "
        f"**{s['frontier_multiple_median']:.0f}× more health per dollar**, the "
        f"price of funding a rich country's social fabric rather than the global "
        f"frontier.\n\n"
        f"![Estimated QALYs](results/figure.png)\n\n"
        f"The spread is driven mostly by the global realization factor, the "
        f"causal-credibility weights, and the cost-per-QALY of the largest buckets "
        f"(education, equity & justice):\n\n"
        f"![Sensitivity](results/sensitivity.png)\n\n"
        f"_Full table: [results/summary.md](results/summary.md). Regenerate with "
        f"`uv run msqaly --write`._"
    )


def inject_results(text: str, block: str) -> str | None:
    """Pure marker-replacement (testable without IO). Returns None if the
    RESULTS markers are absent."""
    start, end = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"
    if start not in text or end not in text:
        return None
    pre, post = text.split(start)[0], text.split(end)[1]
    return f"{pre}{start}\n{block}\n{end}{post}"


def update_readme(res, params) -> bool:
    if not README.exists():
        return False
    new = inject_results(README.read_text(), readme_block(res, params))
    if new is None:
        return False
    README.write_text(new)
    return True


def make_figure(res, params, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    s = res.summary()
    teal = "#0F6E56"
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(12, 5.2), gridspec_kw={"width_ratios": [1.15, 1]}
    )

    # Left: distribution of total QALYs (log x)
    tq = res.total_qalys
    logq = np.log10(np.maximum(tq, 1))
    ax1.hist(logq, bins=80, color=teal, alpha=0.85, edgecolor="none")
    med = np.median(tq)
    ax1.axvline(np.log10(med), color="#993C1D", lw=2)
    ax1.text(
        np.log10(med), ax1.get_ylim()[1] * 0.95, f"  median {_fmt(med)}",
        color="#993C1D", va="top", fontsize=11,
    )
    ticks = [4, 4.5, 5, 5.5, 6, 6.5]
    ax1.set_xticks(ticks)
    ax1.set_xticklabels([_fmt(10 ** t) for t in ticks])
    ax1.set_xlabel("Total QALYs (log scale)")
    ax1.set_ylabel("Monte Carlo draws")
    ax1.set_title("Distribution of estimated QALYs", fontsize=12, loc="left")
    for sp in ("top", "right"):
        ax1.spines[sp].set_visible(False)

    # Right: mean QALYs by archetype
    contrib = sorted(s["per_archetype_mean"].items(), key=lambda kv: kv[1])
    labels = [k for k, _ in contrib]
    vals = [v for _, v in contrib]
    ax2.barh(range(len(vals)), vals, color=teal, alpha=0.85)
    ax2.set_yticks(range(len(vals)))
    ax2.set_yticklabels(labels, fontsize=9)
    ax2.set_xlabel("Mean QALYs")
    ax2.set_title("Where the QALYs come from", fontsize=12, loc="left")
    for i, v in enumerate(vals):
        ax2.text(v, i, f" {_fmt(v)}", va="center", fontsize=8, color="#444441")
    for sp in ("top", "right"):
        ax2.spines[sp].set_visible(False)

    fig.suptitle(
        "MacKenzie Scott's lifetime giving — estimated health impact (QALYs)",
        fontsize=13, x=0.01, ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(path, dpi=130)
    plt.close(fig)


def make_sensitivity_figure(res, path: Path, top: int = 12) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = driver_sensitivity(res)[:top][::-1]
    names = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    colors = ["#0F6E56" if v >= 0 else "#993C1D" for v in vals]

    fig, ax = plt.subplots(figsize=(9, 0.5 * len(rows) + 1.2))
    ax.barh(range(len(vals)), vals, color=colors, alpha=0.85)
    ax.axvline(0, color="#888780", lw=0.8)
    ax.set_yticks(range(len(vals)))
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel("Spearman rank correlation with total QALYs")
    ax.set_title(
        "What drives the spread (probabilistic sensitivity)",
        fontsize=12, loc="left",
    )
    ax.set_xlim(-1, 1)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=100_000, help="Monte Carlo draws")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--params", type=str, default=None, help="parameters.yaml path")
    ap.add_argument("--no-figure", action="store_true")
    ap.add_argument(
        "--write", action="store_true",
        help="regenerate committed artifacts (results/, figures, README block). "
             "Without it, the run only prints — so casual/CI runs never dirty git.",
    )
    args = ap.parse_args(argv)

    params = load_params(args.params)
    res = run(params, n=args.n, seed=args.seed)
    md = summary_markdown(res, params)
    print(md)

    if not args.write:
        print("\n(dry run — pass --write to regenerate results/ and the README block)")
        return 0

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "summary.md").write_text(md)
    (RESULTS / "summary.json").write_text(json.dumps(res.summary(), indent=2))
    if not args.no_figure:
        try:
            make_figure(res, params, RESULTS / "figure.png")
            make_sensitivity_figure(res, RESULTS / "sensitivity.png")
        except Exception as exc:  # pragma: no cover - figure is optional
            print(f"(figure skipped: {exc})")
    wrote_readme = update_readme(res, params)
    print(f"\nWrote {RESULTS/'summary.md'}, summary.json"
          + ("" if args.no_figure else ", figure.png, sensitivity.png")
          + (", README block" if wrote_readme else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
