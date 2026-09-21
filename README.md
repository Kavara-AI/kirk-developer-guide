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

> The discovery question is what structure, recurrence, persistence or relationship
> is observable in the data. Deciding what to do with it is a separate question.

## Start here

1. Find familiar data in [256 exploration prompts across 32 domains](docs/phenomena-catalogue.md).
2. Read [Start Here](START_HERE.md) and the [Capability Fit Guide](docs/capability-fit.md).
3. Run [Benchmark 001](benchmarks/benchmark-001-l2-order-book/README.md).
4. Learn the [tensor-generation workflow](docs/tensor-generation.md), including the proposed upload-and-data-fit handoff.
5. Evaluate your own data under a matching input contract. Catalogue examples are hypotheses, not validated capabilities.

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

- **Problem first:** define the system and discovery question before discussing the engine; a downstream decision can follow later.
- **Evidence over assertion:** connect material claims to runnable examples.
- **Capability before architecture:** establish fit before explaining internals.
- **Transparent limitations:** distinguish demonstrated behaviour from intended behaviour.
- **Reproducibility:** record data generation, tensor construction, parameters, outputs and interpretation.

## Current status

This repository establishes the documentation and benchmark framework. Benchmark 001 defines a synthetic L2 order-book regime experiment. It does not claim validated performance until an actual Kirk run and its outputs are committed.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing changes.
