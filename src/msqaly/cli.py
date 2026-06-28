"""Command-line entry point.

    uv run msqaly                 # 100k draws, seed 0, writes results/
    uv run msqaly --n 500000      # more draws
    uv run msqaly --no-figure     # skip matplotlib

Prints a summary table and writes results/summary.md plus results/figure.png.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .model import load_params, run

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
README = ROOT / "README.md"


def _fmt(x: float) -> str:
    """Human-readable count: 197000 -> '197k', 1.85e6 -> '1.85M'."""
    ax = abs(x)
    if ax >= 1e6:
        return f"{x/1e6:.2f}M"
    if ax >= 1e3:
        return f"{x/1e3:.0f}k"
    return f"{x:.0f}"


def _dollar(x: float) -> str:
    ax = abs(x)
    if ax >= 1e9:
        return f"${x/1e9:.1f}B"
    if ax >= 1e6:
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
        f"- Blended cost-effectiveness (median): "
        f"{_dollar(s['blended_cost_per_qaly_median'])}/QALY"
    )
    lines.append(
        f"- Monetized at VSLY (median): {_dollar(s['value_usd']['median'])} "
        f"→ benefit/cost ratio {s['bc_ratio']['median']:.1f}× "
        f"(90% {s['bc_ratio']['p05']:.1f}–{s['bc_ratio']['p95']:.1f}×)"
    )
    lines.append(
        f"- Global-health frontier counterfactual (median): "
        f"{_fmt(s['frontier_qalys_median'])} QALYs "
        f"≈ {s['frontier_multiple_median']:.0f}× the estimate above\n"
    )

    lines.append("## QALYs by archetype\n")
    lines.append("| Archetype | Median QALYs | Mean QALYs | Median $/QALY | Allocation |")
    lines.append("|---|---:|---:|---:|---:|")
    arche = params["archetypes"]
    label_to_share = {a["label"]: a["allocation_share"] for a in arche.values()}
    ordered = sorted(
        s["per_archetype_mean"].items(), key=lambda kv: kv[1], reverse=True
    )
    for label, mean_q in ordered:
        med_q = float(np.median(res.per_archetype[label]))
        cpq_med = float(np.median(res.cost_per_qaly[label]))
        share = label_to_share.get(label, float("nan"))
        lines.append(
            f"| {label} | {_fmt(med_q)} | {_fmt(mean_q)} | {_dollar(cpq_med)} | "
            f"{share*100:.0f}% |"
        )
    lines.append("")
    lines.append(
        "_Cost-per-QALY for the two health-access archetypes is derived from "
        "causal mortality estimates (Miller et al. 2021; Bailey & Goodman-Bacon "
        "2015); the rest are drawn from the cited cost-effectiveness literature. "
        "See data/parameters.yaml and SOURCES.md._\n"
    )
    return "\n".join(lines)


def readme_block(res) -> str:
    """Compact headline block injected between the README RESULTS markers."""
    s = res.summary()
    tq = s["total_qalys"]
    return (
        f"**Median ≈ {_fmt(tq['median'])} QALYs** "
        f"(mean {_fmt(tq['mean'])}; 90% interval {_fmt(tq['p05'])}–{_fmt(tq['p95'])}), "
        f"a blended **{_dollar(s['blended_cost_per_qaly_median'])}/QALY**. "
        f"Monetized at VSLY that is **{_dollar(s['value_usd']['median'])}** of health "
        f"value — a **{s['bc_ratio']['median']:.1f}× benefit/cost ratio**. "
        f"The same $26.3B at the global-health frontier (~$80/QALY) would buy "
        f"~{_fmt(s['frontier_qalys_median'])} QALYs — about "
        f"**{s['frontier_multiple_median']:.0f}× more health per dollar**, the "
        f"price of funding a rich country's social fabric rather than the global "
        f"frontier.\n\n"
        f"![Estimated QALYs](results/figure.png)\n\n"
        f"_Full table: [results/summary.md](results/summary.md). Numbers regenerate "
        f"on every `uv run msqaly`._"
    )


def update_readme(res) -> bool:
    if not README.exists():
        return False
    text = README.read_text()
    start, end = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"
    if start not in text or end not in text:
        return False
    pre = text.split(start)[0]
    post = text.split(end)[1]
    README.write_text(f"{pre}{start}\n{readme_block(res)}\n{end}{post}")
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=100_000, help="Monte Carlo draws")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--params", type=str, default=None, help="parameters.yaml path")
    ap.add_argument("--no-figure", action="store_true")
    args = ap.parse_args(argv)

    params = load_params(args.params)
    res = run(params, n=args.n, seed=args.seed)

    RESULTS.mkdir(exist_ok=True)
    md = summary_markdown(res, params)
    (RESULTS / "summary.md").write_text(md)
    (RESULTS / "summary.json").write_text(json.dumps(res.summary(), indent=2))
    if not args.no_figure:
        try:
            make_figure(res, params, RESULTS / "figure.png")
        except Exception as exc:  # pragma: no cover - figure is optional
            print(f"(figure skipped: {exc})")
    update_readme(res)

    print(md)
    print(f"\nWrote {RESULTS/'summary.md'}, summary.json"
          + ("" if args.no_figure else ", figure.png"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
