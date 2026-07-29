# Benchmark 001: L2 Order-Book Regime Detection

## Purpose

Evaluate whether Kirk's outputs respond to deliberately introduced changes in the relationships among synthetic Level 2 order-book features.

This benchmark does not claim validated performance until a Kirk run, manifest and outputs are committed.

## Regimes

1. Stable market
2. Gradual bid-side accumulation
3. Cancellation-heavy spoofing-like behaviour
4. Liquidity shock
5. Recovery

## Features

A candidate ten-feature schema:

1. best bid price
2. best ask price
3. bid depth
4. ask depth
5. spread
6. mid-price return
7. order-book imbalance
8. trade rate
9. cancellation rate
10. rolling volatility

## Tensor shape

Initial configuration:

```text
window length: 256 observations
feature count: 10
stride: 16 observations
```

## Evaluation question

Does the Kirk output change near known regime boundaries while remaining comparatively stable within each regime?

## Read next

- [Problem](problem.md)
- [Data generation](data-generation.md)
- [Tensor generation](tensor-generation.md)
- [Expected results](expected-results.md)
- [Interpretation](interpretation.md)
- [Why compare with an LSTM?](why-not-an-lstm.md)
