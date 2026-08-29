# Kirk Benchmarks

Benchmarks show how Kirk behaves on changing systems.

They are not leaderboards. Each benchmark should make one technical question testable and reproducible.

## Benchmark contract

Every benchmark should define:

- the operational problem
- why relationship change matters
- data provenance
- tensor construction
- pre-registered expected behaviour
- baselines
- evaluation measures
- committed outputs
- limitations

## Current benchmarks

| ID | Domain | Status |
|---|---|---|
| 001 | Synthetic L2 order book | Experiment specified |
| 002 | Patient monitoring | Planned |
| 003 | Fusion reactor telemetry | Planned |
| 004 | Industrial IoT | Planned |
| 005 | Cybersecurity telemetry | Planned |
| 006 | Autonomous systems | Planned |
| 007 | Inference cost (energy and time per unit of signal) | Experiment specified |

Start with [Benchmark 001](benchmark-001-l2-order-book/README.md).

[Benchmark 007](benchmark-007-inference-cost/README.md) is the cost counterpart: it is
accuracy-neutral and measures joules and seconds per unit of output signal, with a
runnable CPU reference using TimesFM as the comparison model.
