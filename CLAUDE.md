# Working in this repository

This is the **Kirk developer guide** — documentation and benchmarks that help a
developer decide whether Kirk fits a problem, how to represent their data, and
how to evaluate the result reproducibly.

Read [START_HERE.md](START_HERE.md) first. It sets the reading order.

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

## Running anything against the live engine

Calling Kirk needs a credential and costs real balance on the metered tools.
See [Connect your Claude](docs/connect-your-claude.md) for the connector, or
the [quickstart](examples/quickstart/README.md) for a Python client. Free tools
(`kirk_verify_engine`, `kirk_list_models`, `kirk_render_book`,
`kirk_bulk_howto`, `kirk_billing_*`) cost 0 IU and answer most questions.

Record the `kirk_version` sha with any result you keep. Results from different
engine builds are not interchangeable.

Never commit a credential, and never put one in an example.

## Style

Short sections. Define domain terms on first use. Prefer a concrete example to
an assertion. State limitations and alternative explanations rather than
implying another approach is always inferior. Keep terminology consistent with
the [glossary](docs/glossary.md).
