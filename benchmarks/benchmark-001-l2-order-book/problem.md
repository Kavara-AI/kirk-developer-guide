# Problem

Electronic order books contain interacting price, depth, trade and cancellation processes.

A meaningful market-state change may first appear as a change in relationships:

- cancellation rate rises while executions remain low
- depth falls while spread widens
- imbalance drifts without an immediate price move
- volatility rises as liquidity deteriorates

A threshold on one feature may miss these combinations or generate false alarms during ordinary variation.

## Operational question

Can a relationship-aware inference engine signal that order-book behaviour has entered a different regime?

## Scope

This benchmark uses synthetic data. It is intended to test the mechanics of the evaluation pipeline before moving to real exchange data.
