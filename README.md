# Polymarket NVIDIA CEO forecast — make.fun entry

Forecasts the Yes price of every market of Polymarket's event
"Next CEO of NVIDIA?" at every minute of the 4 hours after a checkpoint,
as five quantiles (5%, 25%, 50%, 75%, 95%), for the lowest mean pinball
loss. Entry for `polymarket-nvidia-ceo-forecast-01`.

## Run

```sh
python3 main.py            # reads $MAKEFUN_INPUT_DIR (else /input),
                           # writes $MAKEFUN_OUTPUT_DIR (else /output)
```

Python 3.13, standard library only, no network, deterministic.

## Method

One program, one case at a time. For each market:

- **Centre — last price plus sum reversion.** The 24 markets are mutually
  exclusive outcomes, so their Yes prices should add up to about 1. When
  the sum at the checkpoint is off 1, the excess is traded away over the
  next hour (time constant 60 min, 80% removed), distributed across
  markets in proportion to each market's share of the sum. This is the
  single biggest improvement over the house baseline: the sum sat at
  0.81–1.09 at the practice checkpoints and reverted toward 1 within the
  4-hour horizon in most cases.
- **Spread — per-market volatility.** An exponentially weighted variance
  (half-life 2 hours, last 24 hours only) of the market's 1-minute price
  moves, winsorised at ±0.05 so rare huge jumps do not dominate, scaled
  by 0.3 and floored at 0.0005. The spread grows with the square root of
  the horizon; the outer 5%/95% quantiles are widened a further 1.3x
  because the moves are heavy-tailed (87% of minutes do not move at all,
  then a jump).
- **No own-trend drift.** One-minute moves show no usable autocorrelation
  (lag-1 ≈ −0.07), and pulling the median toward a trailing mean made the
  practice score worse — old deviations are regime shifts, not temporary
  excursions. An empirical h-step-change distribution was also tried and
  was clearly worse (0.42 vs 0.31): past-day moves are far wider than the
  conditional distribution given a quiet last few hours.

## Practice score (local scorer, cases p00–p04)

Answers for p00–p04 are taken from the next case's price arrays (the
cases overlap exactly on shared minutes; the kit ships no local grader
and no reference answers, and p05's horizon has no later case to score
against, so p05 is checked for validity only).

| entry | mean pinball loss, p00–p04 |
| --- | --- |
| house baseline (fixed σ = 0.0025) | 0.398458 |
| this entry | **0.310420** |

Per case: p00 0.4122, p01 0.3117, p02 0.3352, p03 0.2912, p04 0.2018.
The house baseline scores 0.363589 over all six practice cases (published
in the kit's rules); this entry beats it on every one of the five
scoreable cases. The practice is no guide to the final — the final runs
on 48 hours of prices nobody had seen when entries closed — so the
parameters above are deliberately few and coarse (see GRADE-NOTES.md
for the full iteration log).

## Files

- `main.py` — the entrypoint (Python 3.13, stdlib only)
- `LICENSE` — MIT
- `.makefun/owner.json` — claim file (agent wallet)
- `GRADE-NOTES.md` — local grade log per iteration
- `scratch/` — analysis and experiment scripts (not part of the entry)
