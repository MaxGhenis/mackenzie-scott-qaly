"""Sampling helpers that turn a parameter spec (a dict from parameters.yaml)
into a vector of Monte Carlo draws.

A spec is one of:

    {"dist": "fixed",        "value": x}
    {"dist": "uniform",      "low": a, "high": b}
    {"dist": "loguniform",   "low": a, "high": b}          # a, b > 0
    {"dist": "triangular",   "low": a, "mode": m, "high": b}
    {"dist": "normal",       "mean": m, "sd": s, "min": lo?, "max": hi?}
    {"dist": "lognormal_ci", "low": p05, "high": p95}      # 5th/95th pct, > 0

A bare int/float is treated as a fixed value, so scalars can be written plainly.
"""
from __future__ import annotations

import numpy as np

# 90% of a normal lies within +/- 1.6448536 sd of the mean.
_Z95 = 1.6448536269514722


def sample(spec, n: int, rng: np.random.Generator) -> np.ndarray:
    """Draw `n` samples for a single parameter `spec`."""
    if isinstance(spec, (int, float)):
        return np.full(n, float(spec))
    if not isinstance(spec, dict) or "dist" not in spec:
        raise ValueError(f"Bad parameter spec: {spec!r}")

    kind = spec["dist"]

    if kind == "fixed":
        return np.full(n, float(spec["value"]))

    if kind == "uniform":
        return rng.uniform(spec["low"], spec["high"], n)

    if kind == "loguniform":
        lo, hi = float(spec["low"]), float(spec["high"])
        if lo <= 0 or hi <= 0:
            raise ValueError("loguniform bounds must be positive")
        return np.exp(rng.uniform(np.log(lo), np.log(hi), n))

    if kind == "triangular":
        return rng.triangular(spec["low"], spec["mode"], spec["high"], n)

    if kind == "normal":
        draws = rng.normal(spec["mean"], spec["sd"], n)
        if "min" in spec or "max" in spec:
            draws = np.clip(draws, spec.get("min", -np.inf), spec.get("max", np.inf))
        return draws

    if kind == "lognormal_ci":
        # Interpret {low, high} as the 5th and 95th percentiles of a lognormal.
        lo, hi = float(spec["low"]), float(spec["high"])
        if lo <= 0 or hi <= 0 or hi <= lo:
            raise ValueError("lognormal_ci needs 0 < low < high")
        mu = (np.log(lo) + np.log(hi)) / 2.0
        sigma = (np.log(hi) - np.log(lo)) / (2.0 * _Z95)
        return np.exp(rng.normal(mu, sigma, n))

    raise ValueError(f"Unknown distribution: {kind!r}")


def implied_median(spec) -> float:
    """Best-guess central value of a spec, for quick non-MC reporting."""
    if isinstance(spec, (int, float)):
        return float(spec)
    kind = spec["dist"]
    if kind == "fixed":
        return float(spec["value"])
    if kind == "uniform":
        return (spec["low"] + spec["high"]) / 2.0
    if kind == "loguniform":
        return float(np.sqrt(spec["low"] * spec["high"]))
    if kind == "triangular":
        return float(spec["mode"])
    if kind == "normal":
        return float(spec["mean"])
    if kind == "lognormal_ci":
        return float(np.sqrt(spec["low"] * spec["high"]))
    raise ValueError(f"Unknown distribution: {kind!r}")
