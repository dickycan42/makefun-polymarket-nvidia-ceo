# Local grade log — polymarket-nvidia-ceo-forecast-01

Scorer: my own local scorer (`scratch/score.py`). The kit ships no local
grader and no reference answers, so answers for p00–p04 are taken from
the *next* case's price arrays (cases are 4 h apart, horizon 240 min;
consecutive cases overlap exactly on shared minutes — 0 mismatches over
~170k shared points). p05's horizon (to 2026-11-13T06:00Z) has no later
case, so p05 is validity-checked only. All losses below are mean pinball
loss in percentage points over cases p00–p04.

House baseline (published in RULES.txt, all 6 practice cases): 0.363589.
House baseline re-scored locally on p00–p04 (sanity check of my scorer):
0.398458 — per case 0.5361 / 0.3804 / 0.4084 / 0.3686 / 0.2988.

## Iterations (mean loss p00–p04)

| # | change | mean | note |
| --- | --- | --- | --- |
| 0 | house baseline, σ = 0.0025 fixed, no drift | 0.398458 | reference |
| 1 | per-market EWMA σ (HL 360, cap 0.05, ×1.0) | 0.427722 | raw EWMA σ far too wide |
| 2 | σ grid: HL 180, cap 0.05, ×0.4, floor 0.0005 | 0.330312 | short half-life wins; σ must be scaled down a lot |
| 3 | + median reversion to trailing mean (R 0.25–0.8) | worse | old deviations are regime shifts, not excursions |
| 4 | + jump reversion (last-60m move, capped) | 0.329661 | +0.0007, noise-level |
| 5 | + tail widening 5%/95% ×1.1–1.3; σ exponent 0.5 best | 0.328569 | sqrt(h) growth confirmed; saturation hurts |
| 6 | empirical h-step-change quantiles (window 24 h) | 0.420305 | far too wide — past-day moves overstate the conditional distribution |
| 7 | logit-space forecast | 0.330384 | no better than price space |
| 8 | EWMA of \|d\| instead of d² | 0.332671 | no better |
| 9 | + sum reversion (S → 1.0, share-weighted, srev 0.8, τ 60 m) | **0.315395** | big win, concentrated in p00/p02 where \|S−1\| was large |
| 10 | retune σ/tail on top of sum reversion: ×0.3, tail 1.3 | **0.313309** | final config |
| 11 | + jump reversion on final config | 0.312352 | +0.001, flips p03 worse — dropped as noise |

## Final config (in main.py)

- σ: EWMA variance of 1-min moves, half-life 180 min, last 24 h, winsorised
  ±0.05, ×0.3, floor 0.0005.
- Spread: σ·√h, outer quantiles ×1.3.
- Drift: sum reversion only — 80% of (Σ prices − 1.0) removed with τ = 60 min,
  distributed by market share. No own-trend drift, no trailing-mean pull.
- Per-case losses: p00 0.4111, p01 0.3149, p02 0.3366, p03 0.3027,
  p04 0.2013. Median error 0.57–1.25, 90% coverage 0.90–0.94 (baseline:
  0.87–0.98, over-covering).
- Beats the house baseline on every scoreable practice case
  (−21% mean loss). Practice is no guide to the final, so parameters
  are deliberately few and coarse.

## Verification (2026-11-13, before hand-off)

- Two full runs over all 6 practice cases: byte-identical outputs.
- All 6 outputs valid: exactly one `forecasts` key, every case market
  once, 240 rows × 5 numbers, each in [0, 1], non-decreasing per row,
  ≤ 1 MiB (192–255 KB).
- Single-case run (one `.in` in /input, as the grader does): 0.10 s.
  Full 6-case run: ~0.36 s. Limit is 8 s per case.
- Python 3.12.3 locally (grader uses 3.13); stdlib only, no network,
  no reads outside the case file.
