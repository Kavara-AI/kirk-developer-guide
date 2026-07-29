# Contributing

Contributions should make Kirk easier to evaluate, reproduce or apply.

## Ground rules

1. Separate observed results from hypotheses.
2. Do not publish benchmark claims without the run configuration and output artifacts.
3. Explain tensor shape, feature order, windowing and normalisation.
4. Prefer small, reviewable pull requests.
5. Keep terminology consistent with the [glossary](docs/glossary.md).

## Adding a benchmark

A benchmark should include:

- `README.md`
- `problem.md`
- `data-generation.md` or a dataset reference
- `tensor-generation.md`
- `expected-results.md`
- `interpretation.md`
- raw or reproducibly generated data
- machine-readable Kirk output
- figures derived from that output

Use [Benchmark 001](benchmarks/benchmark-001-l2-order-book/README.md) as the template.

## Claims

Use one of these labels:

- **Demonstrated:** supported by committed data and outputs.
- **Observed:** seen in a specific run but not yet broadly validated.
- **Expected:** a pre-registered evaluation target.
- **Hypothesis:** a proposed behaviour requiring testing.

## Style

- Use short sections.
- Define domain-specific terms.
- Prefer concrete examples.
- Avoid blanket statements that another model class is always inferior.
- State limitations and alternative explanations.

## Pull-request checklist

- [ ] Links resolve.
- [ ] Commands are reproducible.
- [ ] Claims are correctly labelled.
- [ ] Figures can be regenerated.
- [ ] No secrets or proprietary data are included.
