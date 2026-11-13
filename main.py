#!/usr/bin/env python3
"""Forecast Polymarket's "Next CEO of NVIDIA?" Yes prices, 4 hours ahead.

Reads one case file per run (MAKEFUN_INPUT_DIR, else /input) and writes one
forecast file per case (MAKEFUN_OUTPUT_DIR, else /output): for every market
and every minute of the next 240, five quantiles of that minute's price.

Method (per market, fitted on the six practice cases; see README.md):
  * Centre: the market's last price, plus a drift that pulls the whole
    distribution back toward the event's probability mass adding up to 1.
    The 24 markets' Yes prices must sum to about 1 (they are mutually
    exclusive outcomes); when their sum at the checkpoint is off 1, the
    excess is traded away over the next hour, distributed across markets
    in proportion to each market's share of the sum.
  * Spread: each market gets its own volatility, an exponentially weighted
    (half-life 2 hours, last 24 hours only) variance of its 1-minute price
    moves, winsorised at +-0.05 so rare huge jumps do not dominate it,
    scaled by 0.3 and floored at 0.0005.  The spread grows like the square
    root of the horizon, with the 5%/95% quantiles widened a further 1.3x
    because the moves are heavy-tailed.
  * No drift from the market's own recent trend: 1-minute moves show no
    usable autocorrelation, and pulling the median toward a trailing mean
    made the practice score worse (old deviations are regime shifts, not
    temporary excursions).

Standard library only, no network, no reads outside the case file, fully
deterministic: the same case always yields the same bytes.
"""

import json
import math
import os

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

# The quantile levels the contest scores, in the order each row lists them.
QUANTILES = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level.
Z = [-1.644854, -0.67449, 0.0, 0.67449, 1.644854]

# --- tuned constants (see README.md for how each was chosen) ---
# Half-life, in minutes, of the exponential weights on past 1-minute moves.
# Iteration 12: 180 -> 120. Price moves cluster (quiet stretches, then
# bursts), so a 2-hour half-life tracks the market's current regime better
# than 3 hours: practice mean 0.313309 -> 0.310420, better on p01/p02/p03,
# near-neutral on p00/p04. Shorter half-lives (60/45) scored lower still
# but only by chasing p03 while p00 worsened steadily, so 120 is kept as
# the coarse, defensible choice rather than the practice optimum.
SIGMA_HALF_LIFE_MIN = 120.0
# 1-minute moves are winsorised to this range before entering the variance.
DIFF_CAP = 0.05
# Only the most recent that many minutes of history feed the volatility.
SIGMA_WINDOW_MIN = 1440
# The raw per-minute volatility overstates the horizon's moves, so scale it.
SIGMA_MULT = 0.3
# No market is ever forecast as perfectly still.
SIGMA_FLOOR = 0.0005
# Extra widening of the outer (5% / 95%) quantiles: heavy-tailed moves.
TAIL_MULT = 1.3
# Fraction of the event's sum-to-one excess removed over the horizon.
SUM_REVERT = 0.8
# What the markets' Yes prices should add up to.
SUM_TARGET = 1.0
# Time constant, in minutes, of the sum reversion.
SUM_TAU_MIN = 60.0


def price6(x):
    """x clamped to [0, 1] and rounded to 6 decimals (0, never -0)."""
    return round(min(1.0, max(0.0, x)), 6) + 0.0


def market_sigma(prices):
    """Per-minute volatility from recent 1-minute moves (winsorised EWMA)."""
    n = len(prices)
    if n < 2:
        return SIGMA_FLOOR
    alpha = 1.0 - 0.5 ** (1.0 / SIGMA_HALF_LIFE_MIN)
    var = 0.0
    start = n - SIGMA_WINDOW_MIN if n > SIGMA_WINDOW_MIN else 1
    for i in range(start, n):
        d = prices[i] - prices[i - 1]
        if d > DIFF_CAP:
            d = DIFF_CAP
        elif d < -DIFF_CAP:
            d = -DIFF_CAP
        var = alpha * d * d + (1.0 - alpha) * var
    sigma = math.sqrt(var) * SIGMA_MULT
    return sigma if sigma > SIGMA_FLOOR else SIGMA_FLOOR


def forecast_market(prices, horizon, drift_total, sqrt_h, revert_h):
    """The horizon rows of five quantiles for one market."""
    x = prices[-1]
    sigma = market_sigma(prices)
    rows = []
    for h in range(horizon):
        med = x + drift_total * revert_h[h]
        spread = sigma * sqrt_h[h]
        row = []
        for j, z in enumerate(Z):
            zz = z * TAIL_MULT if j == 0 or j == 4 else z
            row.append(price6(med + zz * spread))
        for j in range(1, 5):
            if row[j] < row[j - 1]:
                row[j] = row[j - 1]
        rows.append(row)
    return rows


def forecast_case(case):
    horizon = case["horizon_minutes"]
    markets = case["markets"]
    # The event's probability mass at the checkpoint, and each market's
    # share of it: the sum reversion is distributed in proportion to share.
    total = 0.0
    for m in markets:
        total += m["prices"][-1] if m["prices"] else 0.0
    excess = total - SUM_TARGET
    sqrt_h = [math.sqrt(h + 1) for h in range(horizon)]
    revert_h = [1.0 - math.exp(-(h + 1) / SUM_TAU_MIN) for h in range(horizon)]
    forecasts = []
    for m in markets:
        prices = m["prices"]
        if not prices:
            # No history at all: stay at 0.5 with the floor spread.
            prices = [0.5]
        share = prices[-1] / total if total > 0.0 else 0.0
        drift_total = -SUM_REVERT * excess * share
        forecasts.append(
            {"id": m["id"], "q": forecast_market(prices, horizon, drift_total, sqrt_h, revert_h)}
        )
    return forecasts


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    inputs = sorted(f for f in os.listdir(INPUT_DIR) if f.endswith(".in"))
    for name in inputs:
        case_id = name[: -len(".in")]
        with open(os.path.join(INPUT_DIR, name), "r", encoding="utf-8") as f:
            case = json.load(f)
        if len(case["quantiles"]) != len(QUANTILES) or any(
            t != q for t, q in zip(case["quantiles"], QUANTILES)
        ):
            raise ValueError(f"{name} asks for quantiles {case['quantiles']}, not {QUANTILES}")
        forecasts = forecast_case(case)
        out = json.dumps({"forecasts": forecasts}, separators=(",", ":")) + "\n"
        with open(os.path.join(OUTPUT_DIR, case_id + ".out"), "w", encoding="utf-8") as f:
            f.write(out)


if __name__ == "__main__":
    main()
