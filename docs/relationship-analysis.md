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

## Why a 2D representation is useful

A two-dimensional tensor can represent a time window by features:

```text
rows    = observations through time
columns = ordered features or streams
```

For example, a `256 × 10` tensor contains 256 consecutive observations for 10 features.

The feature order, units, normalisation and missing-data treatment are part of the experiment and must be documented.

## Caution

A relationship change does not prove causality. It can reflect:

- a genuine system transition
- a sensor fault
- data latency
- resampling artifacts
- a change in market participation
- an external intervention

Interpretation requires domain context.
