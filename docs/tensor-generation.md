# Tensor Generation

**You build one square matrix per step.**

Each step, Kirk takes one square matrix of real or complex values. Typical sizes
are 16 × 16 and 32 × 32. Non-square input is not accepted.

You decide what the rows and columns represent, and you do any windowing
yourself. Window length and stride are choices in that construction. Three
examples:

- **Recent lags of one stream.** A Hankel-style lag matrix: recent lags of a
  single series, arranged so the matrix is square.
- **Channels against recent time.** One axis is streams, the other is the most
  recent time steps, with the window chosen so both axes have the same length.
- **Channel-by-channel products.** Over a recent interval, products — or another
  pairwise summary you record — between streams. The result is square because
  both axes are the same set of streams.

A rectangular panel of source observations, such as 256 time steps by 10
channels, is material you may draw from when you build these matrices. Record
the rule, including units.

## One matrix per time step

Send one matrix per time step, in time order. Kirk learns on every step, so
ordering, chain length, and splitting a sequence across calls change the
results. Choose a warm-up period and record how many steps you treat as warm-up
before comparing outputs.

## Scale causally, and keep gaps visible

For online evaluation, nothing derived at time `t` may use observations after
`t`. Scale with rolling or pre-defined statistics. Do not silently replace gaps
with zero. Record what each row and column means, the units, and the
missing-data rule.

## Outputs per step

Learn and score in the [customer contract](customer-rest-api.md) return an
archive. The members depend on `outputs`:

- `entropy`: float32, shape `(n,)`
- `feature_arr`: complex64, shape `(n, V, V)`
- `feature_vec`: complex64, shape `(n, 2V)`
- `feature_scalar`: complex64, shape `(n,)`

`outputs=all` returns all four. `outputs=entropy` returns `entropy` only.
`outputs=features` returns the three feature members. Learn also returns the
next `snapshot`. Keep those field names.

## Suitable data

A strong fit is several streams that describe one evolving system, arriving
continuously, where relationships between streams matter and the distribution
drifts. Static, independently sampled data is a weak fit. The longer triage is
in [capability fit](capability-fit.md).

## Customer calls

Submit the square matrices through the [customer REST contract](customer-rest-api.md).
`POST /v1/kirk-api/create` takes JSON `hyperparameters` (at least
`visible_nodes`) and returns a snapshot. `POST /v1/kirk-api/learn` and
`POST /v1/kirk-api/score` take that snapshot plus `samples`, `n` squares of
`V` × `V`, with every real and imaginary part in [-1, 1].

Earlier preview routes are not part of the v1 customer API and are not supported.
Do not reshape unrelated columns into a price book to fit a retired call.
Read [Customer REST API](customer-rest-api.md) for the methods, headers and
response members. Where a surface has no documented way to submit the matrices
you built, contact Kavara.

## Decisions that remain yours

The matrix you send is your experiment and must be documented:

1. What the rows and columns represent
2. Window length and stride, through the construction above
3. Sampling interval and how often you emit a matrix
4. Timestamp alignment across streams
5. Missing-data policy
6. Causal scaling
7. Warm-up length
8. Metadata attached to each matrix

## Avoid leakage

The scaling rule above is the leakage rule. Full-sample normalisation,
standardisation or other statistics computed over later observations are not
valid for an online run. Use rolling or pre-defined statistics only.

## Preserve provenance

Each output should be traceable to:

- source data range
- row and column meaning, with units
- feature schema version
- observation index
- start and end timestamps
- preprocessing configuration, including window, stride and missing-data rule
- the `X-Kavara-Receipt` value on a metered success (`rcpt_` and 32 hex characters)
- run parameters, including chain length and warm-up

Keep the receipt with the snapshot it belongs to. A result without that receipt
cannot be matched to the call that produced it.

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
3. **Propose preparation.** Document timestamp alignment, entity mapping, how each
   square matrix is built, what its rows and columns mean, units, windowing,
   stride, missingness and any scaling. Explain which structure each
   transformation retains or removes; do not apply a universal normalizer or
   silently replace missing values with zero. Preserve original data references
   and transformation provenance. Online processing must remain causal.
4. **Check the data envelope.** Match the proposed matrices to the selected
   model's documented input contract and configuration, including state, warm-up
   and reset requirements. For Kirk, that contract is one square matrix per
   time step, sent in order. Record the exact contract identity/version and any
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
customer files, uploads nothing and calls no hosted API. Keep existing IDs stable; add
new IDs for new prompts instead of renumbering or reusing old ones. Each entry inherits
the catalogue's `Hypothesis` label. Put measured findings and their evidence in the
benchmark/result records rather than relabeling this inspiration catalogue.
