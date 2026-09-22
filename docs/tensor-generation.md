# Tensor Generation

**The engine builds the tensor. You supply the observation.**

This is the most common integration mistake, so it is worth stating before anything
else: you do not construct a tensor and send it. You send a snapshot in the shape the
model expects, and the sealed engine renders it.

## The live contract (L2 order book)

`kirk_render_book` takes two arrays and returns the rendered tensor for inspection:

```text
bid_px   10 bid prices, level 1 first
ask_px   10 ask prices, level 1 first
```

The engine renders these into a **20 × 20 complex128** tensor whose rows are
`Bid1..Bid10` and `Ask1..Ask10`.

You can confirm this yourself without spending anything — `kirk_render_book` costs
0 IU and does not invoke the sealed engine:

```json
{"shape": [20, 20], "dtype": "complex128", "non_zero_cells": 50,
 "mid_price": 223.095, "spread_ticks": 1.0}
```

See [`examples/quickstart`](../examples/quickstart/README.md) for a runnable version.

## Decisions that remain yours

The rendering is fixed, but everything upstream of it is your experiment and must be
documented:

1. Sampling interval and snapshot cadence
2. Which book levels you capture, and what you do when fewer than 10 are quoted
3. Timestamp alignment across streams
4. Missing-data policy
5. Warm-up period before the first scored snapshot
6. Metadata attached to each observation

## Avoid leakage

For online evaluation, nothing you derive at time `t` may use observations after `t`.
This applies to any normalisation, scaling or standardisation you perform before
submitting a snapshot — use rolling or pre-defined statistics, never full-sample ones.

## Preserve provenance

Each output should be traceable to:

- source data range
- feature schema version
- observation index
- start and end timestamps
- preprocessing configuration
- **Kirk engine sha** (`kirk_version`, stamped on every response)
- run parameters

The engine sha matters more than the rest: results from different engine builds are not
interchangeable, and a result without its sha cannot be placed in a lineage later.

## Other input shapes

The 10+10 book contract above is what the public MCP surface accepts today. Other
observation shapes exist for other integration paths; contact Kavara rather than
inferring a contract from this page.

## Proposed upload-and-data-fit handoff

**Hypothesis / proposed workflow:** a developer brings a representative sample,
learns its geometry and possible fit, then explores phenomena with Kirk and suitable
comparison methods. This repository does not yet provide that upload service,
an arbitrary-file renderer or an automatic fit classifier. The catalogue supplies
reusable intake content now; execution requires a separately implemented workflow.

The [exploration catalogue](phenomena-catalogue.md) is the recognition layer for that
flow. A developer can say "my data looks like that" without choosing a phenomenon
label or specifying what to do with a discovery. Selecting an industry supplies
examples, not preprocessing instructions or a model choice.

### From recognition to preparation

1. **Describe the source.** Select any relevant domain and source-data profiles,
   or leave them unclassified. Record what observations, entities, coordinates,
   timestamps, channels and units mean. A sample or redacted version must retain
   the structure needed for the intended assessment; anonymization or aggregation
   can change relationships and therefore the findings.
2. **Inspect geometry and quality.** Record dimensions, axis meanings, ordering,
   cadence, coverage, missing and nonfinite values, exact zeros, variability and
   relevant relationships. Distinguish measured facts about the submitted sample
   from user declarations and unknowns about the full dataset. File size and shape
   alone do not establish fit. A small sample cannot establish full-history coverage.
3. **Propose preparation.** Document timestamp alignment, entity mapping, feature
   representation, units, windowing, missingness and any scaling. Explain which
   structure each transformation retains or removes; do not apply a universal
   normalizer or silently replace missing values with zero. Preserve original data
   references and transformation provenance. Online processing must remain causal.
4. **Check the data envelope.** Match the proposed observations to the selected
   model's documented input contract and configuration, including state, warm-up
   and reset requirements. Record the exact contract identity/version and any
   unresolved requirements. Source-data profiles below are not new data envelopes.
   If no applicable contract is established, report that and stop before scoring;
   contact Kavara rather than forcing the data into the L2 book interface.
5. **Explore and compare.** Once admission is established, retain evidence of what
   Kirk and the chosen baselines surface. Separate shared candidates, candidates
   surfaced by only one method, and unresolved cases. Compare the same information
   cutoff and input scope at an explicit review budget, including non-event samples.
   Kirk-only means only relative to the named methods and settings tested, not
   impossible for any other method to find. Choose methods for the actual data and
   discovery question; there is no mandatory detector assigned by industry.

The preflight handoff should identify the source/sample scope, geometry facts and
unknowns, declared domain/profile selections, proposed transformations, model and
contract references, remaining admission questions, and whether scoring has actually
occurred. Keep **source geometry**, **input-contract compatibility** and **discovery
usefulness** separate. A compatible input is not evidence of a useful finding.
An interesting candidate is not a diagnosis, cause or instruction to act.

### Reuse the catalogue in the proposed preprocessing suite

The canonical source is [`catalogues/phenomena.json`](../catalogues/phenomena.json).
Its schema version is local to this content registry; it is not a Kirk API version.

| Field | Purpose in an intake consumer |
| --- | --- |
| `schema_version` | Reject or explicitly migrate unsupported catalogue versions. |
| `claim_status` | Display `Hypothesis` with the examples; do not promote them to measured capabilities. |
| `domains[].id`, `title` | Stable selection identifiers and human-readable domain names. |
| `domains[].example_observations` | Help a developer recognize possible source data. |
| `domains[].data_shapes` | References to relevant source-data profiles; suggestions requiring confirmation. |
| `domains[].phenomena[].id`, `description` | Optional exploration prompts, not required labels or detector outputs. |
| `data_shapes` | Profile titles, intake questions and preparation considerations keyed by stable identifier. |

A consumer can display domain examples, collect confirmed source-data profiles, and
combine their questions without duplication. Support multiple selections, "none of
these" and open-ended exploration. Store the catalogue revision and selected IDs in
the intake record; keep user selections distinct from measured geometry. Do not
execute the `preparation` prose as code, automatically choose a model, or treat a
selection as permission to transfer data or invoke a metered service.

For text, image, audio, graph and unordered sample data, the profiles explicitly ask
about representation. Numerical encoding, arbitrary row order and model compatibility
are separate questions; a table of numbers does not answer all three.

### Maintain one catalogue

Edit the JSON source, then regenerate the developer-facing page:

```bash
python3 scripts/render_phenomena_catalogue.py
python3 scripts/render_phenomena_catalogue.py --check
```

The script uses the Python standard library, validates unique identifiers and profile
references, and checks that the published Markdown matches its source. It reads no
customer files, uploads nothing and calls no engine. Keep existing IDs stable; add
new IDs for new prompts instead of renumbering or reusing old ones. Each entry inherits
the catalogue's `Hypothesis` label. Put measured findings and their evidence in the
benchmark/result records rather than relabeling this inspiration catalogue.
