# Non-Stationary Data

A process is non-stationary when its statistical behaviour changes over time.

Changes may affect:

- mean
- variance
- frequency content
- correlation
- event rate
- dependence structure
- missing-data pattern
- latency
- noise

## Why fixed models can struggle

A model trained on one regime may degrade when the system enters another. This does not make fixed models useless; it means their assumptions and retraining strategy must be explicit.

## Types of change

- **Abrupt change:** a sudden transition.
- **Gradual drift:** a slow movement away from prior behaviour.
- **Recurring regime:** a previously observed state returns.
- **Novel regime:** a new pattern appears.
- **Contextual change:** behaviour is normal only under a particular operating condition.

## Benchmark design

A useful non-stationary benchmark should record the exact change points used to generate or label the data. Detection delay can then be measured relative to those boundaries.
