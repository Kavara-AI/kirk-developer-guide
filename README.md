# Kirk Developer Guide

Kirk is intended for analysing complex, non-stationary systems in which relationships between data streams may change over time.

The proposition is **continuous discovery of phenomena in your data, without requiring
you to name every behaviour beforehand**. First establish what the chosen model and
data representation reveal; then evaluate whether a response creates value. Read
[Phenomena discovery](docs/phenomena-discovery.md) for the catalogue workflow, the shared
measurement language proposition, and the evidence needed to support each claim.

This repository helps developers answer three practical questions:

1. Is Kirk a plausible fit for this problem?
2. How should the source data be represented?
3. How can Kirk's behaviour be evaluated with reproducible benchmarks?

> Kirk does not merely ask whether one measurement is unusual. The central evaluation question is whether the behaviour of the system has changed.

## Start here

1. Read [Start Here](START_HERE.md).
2. Review the [Capability Fit Guide](docs/capability-fit.md).
3. Run [Benchmark 001](benchmarks/benchmark-001-l2-order-book/README.md).
4. Learn the [tensor-generation workflow](docs/tensor-generation.md).
5. Replace the synthetic benchmark data with data from your own system.

## Repository structure

```text
.
├── README.md
├── START_HERE.md
├── CONTRIBUTING.md
├── docs/
├── benchmarks/
├── examples/
├── decisions/
└── roadmap/
```

## Documentation principles

- **Problem first:** define the system and decision before discussing the engine.
- **Evidence over assertion:** connect material claims to runnable examples.
- **Capability before architecture:** establish fit before explaining internals.
- **Transparent limitations:** distinguish demonstrated behaviour from intended behaviour.
- **Reproducibility:** record data generation, tensor construction, parameters, outputs and interpretation.

## Current status

This repository establishes the documentation and benchmark framework. Benchmark 001 defines a synthetic L2 order-book regime experiment. It does not claim validated performance until an actual Kirk run and its outputs are committed.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing changes.
