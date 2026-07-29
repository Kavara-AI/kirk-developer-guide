# Expected Results

These are pre-registered evaluation targets, not reported results.

## Primary expectation

Kirk's output should exhibit a reproducible change near one or more known regime boundaries.

## Secondary expectations

- Lower within-regime variability than cross-regime variability
- A measurable response to gradual accumulation
- A distinct response to cancellation-heavy behaviour
- A strong transition around the liquidity shock
- A recovery pattern as the system returns toward stable behaviour

## Failure conditions

The benchmark should be considered unsuccessful or inconclusive if:

- outputs are unrelated to regime boundaries
- isolated noise creates more response than structural changes
- results disappear under minor scaling changes
- runs are not reproducible
- a simple baseline performs equally well with lower complexity

## Metrics

Define before final analysis:

- event tolerance window
- detection delay
- false alarms per 1,000 windows
- missed boundaries
- within-regime variance
- effect size between regimes
