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

## Customer API access

For a working customer API connection, use **`https://api.kavara.ai`** with an
`X-Kavara-Key` header. Start with the [REST quickstart](docs/customer-rest-api.md)
or the [OpenAPI specification](docs/customer-rest-api.openapi.json).
To get a key, sign in at [kavara.ai/login](https://kavara.ai/login) with Google or GitHub, open **API keys** in the [console](https://kavara.ai/console) and create a key. Keys are self-service and bound to your account.

The REST service supports model listing. It does not require Claude. The separate
hosted MCP surface is described in
[Connect your Claude](docs/connect-your-claude.md).

## Start here

**Using an agent? Start with [Kirk: guide for agents](docs/agent-guide.md).** It
provides an ordered workflow from source data to a discovery brief, runtime
contract checks, reproducible evidence and an optional Jev handoff. The agent can
read the catalogue and prepare the JSON artifact without operating a browser.

1. Find familiar data in [256 exploration prompts across 32 domains](docs/phenomena-catalogue.md).
2. Read [Start Here](START_HERE.md) and the [Capability Fit Guide](docs/capability-fit.md).
3. Choose a matching experiment; [Benchmark 001](benchmarks/benchmark-001-l2-order-book/README.md) is the existing L2 example, not a required format for other data.
4. Learn the [tensor-generation workflow](docs/tensor-generation.md): you build one square matrix per step. The page includes the proposed upload-and-data-fit handoff.
5. Evaluate your own data under that contract. Catalogue examples are hypotheses, not validated capabilities.

## Use the discovery portal

Open the [Kirk discovery portal](https://kirk-discovery-portal.vercel.app/) and follow
the [portal user guide](docs/discovery-portal-user-guide.md) to explore the catalogue,
inspect a sample locally and download a discovery brief. The portal also includes
an illustrative Kirk → Jev handoff; live inference and payments are not enabled.

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

- **Problem first:** define the system and discovery question before discussing Kirk; a downstream decision can follow later.
- **Evidence over assertion:** connect material claims to runnable examples.
- **Capability before architecture:** establish fit before explaining internals.
- **Transparent limitations:** distinguish demonstrated behaviour from intended behaviour.
- **Reproducibility:** record data generation, how each square matrix was built, parameters, outputs and interpretation.

## Current status

This repository establishes the documentation and benchmark framework. Benchmark 001 defines a synthetic L2 order-book regime experiment. It does not claim validated performance until an actual Kirk run and its outputs are committed.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing changes.
