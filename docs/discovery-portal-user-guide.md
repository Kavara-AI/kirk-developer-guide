# Kirk discovery portal: user guide

[Open the Kirk discovery portal](https://kirk-discovery-portal.vercel.app/)

Use the portal to recognise your data, prepare a sample for a data-fit review,
and explore how Kirk evidence could feed a Jev decision workflow. You can begin
without a predefined phenomenon, domain selection or file.

**Observed — portal version checked on 22 September 2026:** the instructions below
cover the [published deployment](https://kirk-discovery-portal-lp11os8f5-kavara.vercel.app/).
The portal provides local preparation and illustrative handoffs. It does not run
Kirk or Jev inference, collect payments, or submit your brief to Kavara.

**Hypothesis — the composition to evaluate:** Kirk discovers and measures
phenomena; Jev evaluates that evidence against defined questions; your application
decides whether to act. Whether this improves a particular workflow requires an
end-to-end evaluation. Read the [discovery thesis](phenomena-discovery.md).

## Start in five minutes

1. Open the portal and choose **Explore your data**.
2. Search for `manufacturing`. Choose **+ Add** on the Manufacturing card if it
   matches your interest. Selection is optional.
3. Choose **Prepare your sample**. Describe your dataset, or write
   “Synthetic equipment telemetry for learning the portal.”
4. Select **Measurements over time**, then choose **Try a synthetic sample**.
5. Inspect the sample summary. In the checked version, the built-in example has
   **6 rows, 5 columns, 1 missing cell and 1 exact zero**. These are local file
   measurements, not Kirk findings.
6. Choose **Review your discovery brief**, then **Download discovery brief**.
   Keep the resulting `kirk-discovery-brief.json` file.

You have prepared an intake for review. You have not selected a model, established
compatibility or run inference.

## Find your way around

The same navigation appears in a sidebar on desktop and across the top on smaller
screens. Move between screens to refine your draft.

| Screen | Use it to | What you get |
| --- | --- | --- |
| **Kirk → Jev** | Explore the proposed evidence-to-decision handoff | An editable illustrative request and a code example |
| **Explore your data** | Search domains, observations and candidate behaviours | Optional domains and exploration prompts for your brief |
| **Prepare a sample** | Describe the source, select data shapes and inspect a small file | Preparation notes and sample statistics |
| **Your discovery brief** | Review and save your preparation | A JSON brief for a data-fit discussion |

Your draft stays in the current page's memory. **Download it before refreshing,
closing the tab or selecting the KAVARA home link.** The current portal has no
saved accounts or facility to re-import a downloaded brief.

## 1. Explore your data

Search the catalogue by domain, observation or behaviour. For example, try
`climate`, `vibration` or `customer`. Data-shape filters help narrow the catalogue;
**Explore all … domains** reveals the remaining cards.

The catalogue contains 32 domains and 256 prompts, drawn from this guide's
[catalogue](phenomena-catalogue.md) at revision `9d2e119`.

- Choose **+ Add** to add a domain to your starting point. Choose **✓ Added** or
  its removal control in the summary to remove it.
- Expand **8 exploration prompts** on a card to read and select individual prompts.
- Select several domains and prompts, or none. Domain and prompt selections are
  independent: removing a domain does not clear prompts selected within it.
- If no result fits, choose **Describe your data** and continue with an open
  exploration.

**Hypothesis:** every catalogue prompt is an idea to investigate, not a validated
Kirk detection or a required label. Selecting a domain does not choose a model,
select preparation profiles or establish an input contract. An **input contract**
specifies the representation and constraints a particular model accepts.

## 2. Describe the source and its structure

In **Prepare a sample**, describe the dataset: what is measured, for which entities,
in which units, over what period. The question or area of interest is optional.

For example:

> Minute-level temperature, vibration and power readings from 40 machines across
> three sites. Maintenance creates gaps; a recorded zero can be a real reading.
> We want to investigate changes in relationships without assuming a fault label.

Select the data shapes that apply. The portal shows preparation guidance and
questions for each selection. These are your declarations, not classifications
inferred from the file.

| Data shape | Context to preserve |
| --- | --- |
| Measurements over time | Timestamps, channels, units, cadence and gaps |
| Timestamped events | Event identity, occurrence and arrival time, entity boundaries |
| Relationships and networks | Node and edge meanings, directions, weights and changing identities |
| Measurements across locations | Coordinates, resolution, coverage and observation times |
| Repeated experiments or operating cycles | Run boundaries, conditions, alignment and reset policy |
| Numerical representations of text, images or audio | Representation method, version and retained relationships |
| Unordered samples or static tables | Sample and batch identities; whether any real ordering exists |

Answer what you know. Leave unresolved questions blank or explicitly say they are
unknown. Do not invent a time axis, replace missing data with zeros or assume one
normalisation works for every dataset.

## 3. Inspect a sample, if useful

Choose **Choose a sample** to inspect a local file. You can also continue without
one, including when the source is sensitive or needs a different representation.

| Requirement | Accepted by the current inspector |
| --- | --- |
| File type | `.csv`, `.tsv`, or `.json` |
| File size | At most 1 MiB (1,048,576 bytes) |
| Data rows | 1–10,000; the CSV/TSV header is separate |
| Columns | 1–128, with non-empty, unique names |
| CSV/TSV structure | Header row, consistent row widths; quoted fields supported |
| JSON structure | An array of flat records; scalar values or null, no nested objects or arrays |

For a minimal file, save this as `example.csv`:

```csv
timestamp,temperature_c,vibration_mm_s
2026-01-01T09:00:00Z,22.1,0.12
2026-01-01T09:01:00Z,22.3,
2026-01-01T09:02:00Z,22.4,0
```

**Observed inspection behaviour:** the portal measures all rows of the supplied
sample. It reports rows, columns, missing cells and exact zeros, plus column-level
numeric counts, non-finite counts and numeric ranges. It does not rewrite values.

- Blank or whitespace-only strings, JSON nulls and absent JSON fields count as
  missing. Text such as the literal string `null` is not automatically missing.
- Exact numeric zeros are counted separately from missing values.
- NaN, Infinity and numbers outside the finite numeric range count separately.
- Numeric-looking strings count as numeric for inspection. An identifier such
  as `001` still needs its meaning confirmed; the count does not redefine it.
- A constant numeric range describes the sample. It does not establish that a
  signal is always constant or that Kirk would be inactive.

If appropriate, select **Time column, if one exists** and **What does row order
mean?** These record your interpretation. The portal does not validate timestamps,
verify cadence, sort rows or establish full-history coverage.

Use **Remove** to clear the sample summary. Choosing another file replaces the
previous sample and clears its time-column and ordering declarations. Parsing a
file successfully is not admission to a Kirk model.

## 4. Review and download the discovery brief

Open **Your discovery brief**. Check the description, domains, shapes, selected
prompts and sample facts. Use **Edit preparation** to make changes.

Choose **Download discovery brief** to save `kirk-discovery-brief.json`. The
versioned JSON includes:

- The source catalogue revision and creation time.
- Your dataset description, optional question, domain and shape selections,
  preparation answers and ordering declarations.
- Selected prompts, still labelled **Hypothesis**.
- Sample filename, column names and statistics, if a sample was inspected.
- Proposed preparation, outstanding unknowns and explicit run/admission status.
- An empty evidence catalogue, because no Kirk run has occurred.

The download **excludes raw rows**, but its names, statistics and written answers
can still contain sensitive information. Review it before sharing through an
authorised channel. Downloading does not send it to Kavara, book an engagement or
agree commercial terms. To arrange a review, use your established Kavara contact
or the [Kavara contact page](https://www.kavara.ai/contact).

The **Your evidence catalogue** panel describes what a future run should retain.
“0 findings · no run yet” is the correct starting state, not an error.

## 5. Explore the Kirk → Jev handoff

Return to **Kirk → Jev** and find **What would you pass to Jev?**

1. Choose **Software operations**, **Industrial equipment** or **Customer behaviour**.
2. Read the illustrative observation and the evidence fields a real handoff needs.
3. Edit **Define a decision question**. The example asks Jev for a
   `needs_review` boolean decision.
4. Choose **Download example request** to save
   `kirk-jev-illustrative-request.json`, or expand **View the AI SDK integration
   pattern** and choose **Copy example**.

**Hypothesis:** these scenarios demonstrate a proposed interface, not measured
Kirk output, a Jev response or a validated integration. The illustrative evidence
explicitly leaves measurements and model/engine identity unset. Editing or
exporting the example makes no model call.

A developer implementing the pattern needs AI SDK 7+, configured AI Gateway
access and actual evidence from an authorised Kirk run. Vercel documents Jev's
`typesafe-ai/jev` evaluation interface in its
[evaluation API guide](https://vercel.com/docs/ai-gateway/modalities/evaluation).
Running copied code elsewhere can make billable calls; this portal does not
provide credentials or execute the code.

A sample-quality report or exploration prompt is not a substitute for discovery
evidence. Retain measurements, timestamps, input context, model and engine identity,
configuration, replay information, comparisons and uncertainty. Then evaluate
Jev's decisions and your application policy separately. A typed decision alone
does not establish a cause or authorise an action.

## Privacy and runtime boundaries

**Observed — current portal:** sample parsing and draft preparation happen in the
browser. These controls do not upload raw rows or draft answers to Kirk, Jev or
Kavara. Normal website requests still reach the hosting service. Exported files
remain wherever your browser saves downloads.

**Hypothesis — production architecture:** discovery would execute in Kirk's
separately secured runtime, with only authorised evidence passed downstream.
The portal neither executes the model nor verifies runtime attestation. A Vercel
website deployment is not an AI Gateway model listing or a confidential-computing
certification.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| No matching domain | Clear the search or filters, or describe your data without a catalogue selection. |
| File too large or too many rows/columns | Export a smaller representative sample and describe omitted coverage. The inspector does not silently truncate. |
| Different row widths or malformed quotes | Check delimiters, escaping and trailing empty fields in the source export. |
| Duplicate or empty column names | Supply distinct, non-empty names before retrying. |
| Nested JSON or unsupported format | Prepare a documented flat representation, or continue with a description only. |
| Draft disappeared after refresh | The draft was held in memory. Refer to your downloaded brief; there is no restore/import control yet. |
| Copy example is unavailable | Select and copy the displayed code manually. |
| Download is not visible | Check the browser's downloads and whether downloads are blocked, then retry. |
| No score, findings, checkout or automatic submission | These features are not enabled in this version. Use the portal to prepare for review. |

## What comes after preparation?

Agree a data-fit review, a supported input contract and a reproducible experiment.
The proposed deliverable is an inspectable catalogue of discoveries. Historical
analysis may lead to ongoing monitoring; the value of any operational response
is a separate evaluation and commercial scope.

Continue with [Capability fit](capability-fit.md),
[Tensor generation](tensor-generation.md),
[Phenomena discovery](phenomena-discovery.md) and
[Interpreting results](interpreting-results.md).
