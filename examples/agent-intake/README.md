# Offline agent intake example

[`discovery-brief.json`](discovery-brief.json) is a complete, synthetic,
description-only preparation artifact. It follows the version 1 export structure
of the [portal deployment checked on 22 September 2026](https://kirk-discovery-portal-lp11os8f5-kavara.vercel.app/).
No file was inspected and no model was called. Its timestamp is an example value.
Its manufacturing selection illustrates navigation, not a validated capability.

Use it with the [agent procedure](../../docs/agent-guide.md). An agent can write
this artifact directly; the portal is optional and currently has no import control
or HTTP endpoint accepting the brief. This is an intake format, not a Kirk API
request, JSON Schema, or inference response.

## Version 1 fields

| Field | Meaning and handling |
| --- | --- |
| `schema_version` | Integer `1` for this brief format. Handle other versions explicitly. The catalogue's separately versioned schema is not an API version either. |
| `created_at` | ISO 8601 creation time. Set it to the actual time for a new brief. |
| `purpose` | Preparation for a data-fit review. |
| `source` | Catalogue repository URL, revision actually read and `catalogue_claim_status: "Hypothesis"`. This example pins `9d2e119`; update for a different source revision. |
| `status` | Explicit preparation-only status. Preserve these values for a brief without contract review or execution. A later run has its own manifest/evidence. |
| `customer_declarations.dataset_description` | Known source description, or null when unknown. Mark synthetic examples explicitly. |
| `customer_declarations.exploration_question` | Optional question or null; open-ended discovery is valid. |
| `customer_declarations.domains` | Zero or more `{id, title}` objects from the source catalogue. |
| `customer_declarations.data_shapes` | Zero or more keys of the catalogue's `data_shapes` object, confirmed against the source structure. |
| `customer_declarations.preparation_answers` | `{profile, question, answer}` for each selected profile's questions; unknown answers are null. |
| `customer_declarations.time_column` | Declared column name or null. This does not validate timestamps. |
| `customer_declarations.row_order` | Portal values: `unknown`, `chronological`, `spatial`, `independent`, or `runs`. These are declarations, not inferred chronology. |
| `optional_exploration_prompts` | Empty is valid. Selected entries contain catalogue `id`, `description`, domain title in `domain`, and `claim_status: "Hypothesis"`. |
| `measured_sample` | Null when not inspected. Otherwise the profile described below, containing measured sample facts only. |
| `proposed_preparation` | `{profile, guidance}` copied from selected catalogue profiles. Guidance is prose to assess, not executable preprocessing. |
| `unknowns` | Unresolved questions; extend with dataset-specific gaps. |
| `evidence_catalogue` | Empty `entries` and reason when no Kirk run occurred. Prompts and file statistics are not findings. |
| `privacy` | Export disclosure. Descriptions, filenames, column names and statistics can contain sensitive data even without raw rows. |

For a measured sample, the portal writes `filename`, `format` (`csv`, `tsv`,
`json`), `rows`, `columns`, `synthetic` and `scope`. Each column has `name`,
`missing`, `zero`, `nonfinite`, `numeric`, `text`, `boolean`, `min` and `max`.
Counts are nonnegative integers. `min`/`max` cover finite numeric values and are
null when none exist. `zero` is a subset of `numeric`; the mutually exclusive
counts `missing + nonfinite + numeric + text + boolean` equal `rows` per column.
Read the [inspection rules](../../docs/discovery-portal-user-guide.md#3-inspect-a-sample-if-useful)
before calculating these values. Record richer analysis separately if it does not
fit this contract; do not put guesses in measured fields.

## Reproduce the description-only walkthrough

From the repository root:

```sh
python3 -m json.tool examples/agent-intake/discovery-brief.json
python3 scripts/render_phenomena_catalogue.py --check
```

Inspect the catalogue's `manufacturing` domain and `time-series` profile. The
example uses their exact identifiers and preparation questions, leaves answers
unknown, and records no measurements or findings. These commands parse the example
and check the source catalogue's generated documentation; they do not establish
runtime compatibility. No dependencies beyond Python's standard library, credentials,
network access or model calls are needed.

**Expected completion:** a valid preparation brief, with model/input contract
unestablished and engine run not performed. To request live equipment analysis,
the next step is an applicable contract and runtime access, not a book-scoring call.
