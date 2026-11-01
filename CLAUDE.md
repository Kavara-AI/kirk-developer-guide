# Working in this repository

This is the **Kirk developer guide** — documentation and benchmarks that help a
developer decide whether Kirk fits a problem, how to represent their data, and
how to evaluate the result reproducibly.

For dataset intake, discovery, runtime connection or a Jev handoff, follow
[the agent guide](docs/agent-guide.md). For repository orientation, read
[START_HERE.md](START_HERE.md).

## Ground rules that matter most here

[CONTRIBUTING.md](CONTRIBUTING.md) is authoritative. Two of its rules do the
most work and are easy to break by accident:

1. **Label every claim** as Demonstrated, Observed, Expected or Hypothesis.
   "Demonstrated" requires committed data and outputs in the repository. An
   evaluation target is **Expected**, not a result.
2. **Do not publish a benchmark claim without its run configuration and output
   artifacts.** A number without the configuration that produced it cannot be
   checked by the reader, which is the whole point of this repository.

Benchmark 001 currently defines an experiment. It does not claim validated
performance, and nothing should describe it as though it does until a real run
and its outputs are committed.

## Running anything against the hosted API

For customer REST calls at `https://api.kavara.ai`, use
[Customer REST API](docs/customer-rest-api.md) and its
[OpenAPI specification](docs/customer-rest-api.openapi.json). The first calls
are readiness, the published limits, and create. Learn and score take the
snapshot from create. `GET /v1/engine`, `GET /v1/models` and `POST /v1/score-book`
are not part of v1. Keep `X-Kavara-Receipt` from a metered success. Paid
workflow activation is separate from these calls.

For the separate MCP surface, calling Kirk needs a credential and costs real
balance on the metered tools.
See [Connect your Claude](docs/connect-your-claude.md) for the connector and for
creating a key in the console. That page lists which of its tools cost 0 IU.

Never commit a credential, and never put one in an example.

## Style

Short sections. Define domain terms on first use. Prefer a concrete example to
an assertion. State limitations and alternative explanations rather than
implying another approach is always inferior. Keep terminology consistent with
the [glossary](docs/glossary.md).

## Agent skills

### Issue tracker

Issues and specs live in Kavara Jira, project EN, not in GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Default mattpocock triage roles; each tracker label equals its role name. See `docs/agents/triage-labels.md`.

### Domain docs

single-context. See `docs/agents/domain.md`.
