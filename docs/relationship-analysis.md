# Relationship Analysis

Relationship analysis examines how variables behave together.

Relevant structures may include:

- correlation and covariance
- lead-lag relationships
- synchronisation
- conditional dependence
- order-book imbalance
- coupling between sensors
- changes in joint variance
- changes in transition dynamics

## Why a square matrix is useful

Each step, Kirk takes one square matrix. You choose the axes. For example:

```text
rows    = recent lags of one stream
columns = the same lags, as a Hankel-style matrix
```

Other constructions that stay square: channels against an equal number of recent
time steps, or channel-by-channel products over a recent interval. A rectangular
panel — many time steps by a different number of features — is source data you
window yourself into one of those matrices. See
[tensor generation](tensor-generation.md).

Row and column meaning, units, scaling and missing-data treatment are part of the experiment and must be documented.

## Caution

A relationship change does not prove causality. It can reflect:

- a genuine system transition
- a sensor fault
- data latency
- resampling artifacts
- a change in market participation
- an external intervention

Interpretation requires domain context.
