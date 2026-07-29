# Data Generation

Generate 20,000 observations at a nominal interval of 100 milliseconds.

## Regime schedule

| Range | Regime |
|---:|---|
| 0–3,999 | Stable |
| 4,000–7,999 | Accumulation |
| 8,000–11,999 | Cancellation-heavy |
| 12,000–15,999 | Liquidity shock |
| 16,000–19,999 | Recovery |

## Design principle

Change joint behaviour, not only individual means.

Examples:

- During accumulation, increase bid depth and imbalance gradually while constraining immediate price movement.
- During cancellation-heavy behaviour, increase cancellation rate and transient displayed depth while keeping trade rate comparatively low.
- During liquidity shock, reduce both sides' depth, widen spread and increase volatility.
- During recovery, return relationships gradually rather than resetting all features instantly.

## Reproducibility

Record:

- random seed
- generator version
- regime schedule
- parameter values
- feature units
- any clipping
- output checksum

Generated data should include a `regime_id` column used only for evaluation, not as an input feature.
