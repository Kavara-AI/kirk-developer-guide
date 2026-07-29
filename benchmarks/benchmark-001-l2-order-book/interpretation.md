# Interpretation

Plot the following on a shared time axis:

1. selected order-book features
2. true synthetic regime
3. Kirk output
4. baseline outputs
5. detected change points

## Interpretation questions

- Which regime boundaries produced a response?
- Did the response lead, coincide with or lag the boundary?
- Was gradual accumulation visible?
- Did cancellation-heavy behaviour differ from the liquidity shock?
- Did recovery return toward the original state?
- Which feature ablations removed the response?

## Alternative explanations

A response may be caused by:

- scaling discontinuity
- derived-feature leakage
- abrupt generator artifacts
- window overlap
- one dominant feature
- numerical instability

Run controls before attributing the result to relationship-aware inference.
