# Phenomena discovery: from observations to value

Kirk's proposition is continuous discovery of phenomena in customer data, without
requiring customers to name every behaviour or supply phenomenon labels beforehand.
The engineering question is whether a chosen model, representation and state policy
make those behaviours observable and reproducible through the interface being used.

This page defines an evaluation workflow and a commercial proposition. It does not
announce a new API, pricing plan or validated cross-domain capability. Results retain
the evidence labels defined in [Contributing](../CONTRIBUTING.md#claims).

## What counts as a phenomenon?

A phenomenon is an observed behaviour worth investigating: a transition, a persistent
state, a recurring sequence, or a change in relationships among streams. It can remain
unexplained. A score excursion is a candidate observation; a descriptive label and a
causal explanation are separate additions to the evidence.

Discovery should preserve breadth. Investigate individual histories, pairs, groups and
relationships between groups where their representations fit the chosen model's input
contract. A pairwise catalogue does not exhaust collective behaviour. Nor does a list
of the largest scores exhaust the behaviours worth examining.

Possible descriptions include spread compression, divergence, reversal and recurring
co-movement. These are illustrative vocabulary, not a fixed taxonomy or claims of
demonstrated detection. Keep unclassified cases and allow overlapping descriptions.
Record exact-zero intervals and missingness separately until their source meaning is
established; do not silently equate zero with missing data or with an inactive model.

## Two stages: discovery and value

### 1. Discover and document behaviour

Establish whether the data can be represented so Kirk surfaces reproducible phenomena.
Follow the selected model's [input and rendering contract](tensor-generation.md);
arbitrary groupings are research choices, not automatically supported API inputs.
Record ordering, units, sampling, information cutoff, missingness and state policy.

The deliverable is an inspectable phenomena catalogue. Retain the input context and
raw outputs so descriptions, thresholds and episode groupings can be revised without
repeating the engine run. Changing the input representation or model configuration
may still require another run.

Do not make a downstream payoff a prerequisite for recording a phenomenon. For example,
a change in the relationship between two alpha streams can be worth investigating even
before anyone establishes a trading use for it. Equally, an interesting plot does not
establish that Kirk discovered something an existing method would miss.

### 2. Establish the value of a response

Evaluate whether acting on the discoveries improves the customer's stated outcome.
Specify the response, comparison policy, timing and costs before evaluating it on fresh
data where possible. Include the costs of false alarms, missed changes and human review.

Discovery evidence and application evidence answer different questions. A recurring
phenomenon need not be actionable; a useful action does not by itself explain its cause.
Keep exploratory findings distinct from subsequent confirmation.
Unsupervised scoring does not remove selection bias: representation choices, thresholds
and the examples selected for review can still be overfit to a dataset.

## Build an evidence-backed catalogue

Each entry should identify:

- **What and where:** the streams or entities, representation, observed behaviour and
  provisional description, including unresolved alternatives.
- **When:** observation timestamps and information cutoff; for threshold episodes,
  onset, peak and last elevated observation, with boundary-censoring recorded.
- **Measurement:** raw model outputs and any derived scores, including the definition,
  normalization, threshold and eligibility rules used by the consumer.
- **Context:** input histories before and after the selected observation, missingness,
  exact-zero counts, warmup and reset information. Later observations are retrospective
  context and must not influence an earlier detection.
- **Reproducibility:** data reference, model id, engine identity, effective configuration,
  input contract, state history or replay procedure, and analysis version.
- **Recurrence and comparison:** distinct episodes separately from elevated observations;
  eligible non-event windows, selection rules and relevant existing-method results.
- **Interpretation:** what was observed, what remains a hypothesis, and any linked external
  events. Temporal association supplies a lead for investigation, not proof of causation.

Raw evidence can stay in its authorized data environment; the catalogue can reference
it rather than copy it. Save and verify evidence before marking its analysis complete.

Include varied behaviours rather than only impressive peaks. When a baseline requires
finite scores, an unscored initialization period is ineligible, not a non-event. A quiet
score alone does not make a comparison window matched: record relevant differences in
activity, variability and coverage.

## Continuous discovery and drift

Kirk's intended online use updates model state as observations arrive, without requiring
a new labelled training cycle for every phenomenon category. This is distinct from a
claim that no setup, initialization, configuration changes or maintenance are needed.
The chosen API's state and reset behaviour must be explicit.

Test consistency under drift rather than assuming it. Compare the useful behaviours
surfaced, detection timing, review burden and ongoing maintenance effort against the
customer's existing analysis. A specialist detector may recognise a phenomenon once
it is known; discovering it and maintaining detection as conditions change are also
part of the comparison. Alternative methods may adapt online too.

## A shared measurement language

The composition proposition is that independently running Kirk models can expose
measurements with a shared meaning, so their outputs can be compared or used together
under a defined behaviour contract. This is more specific than collecting unrelated
model scores in one dashboard.

**Hypothesis requiring application evidence:** a proposed comparison or composition
preserves the intended meaning across the selected model configurations and inputs.
Record the output definition, units, reference state, cadence and permitted comparison
or combination. Common units alone do not establish equal event probabilities, equal
importance or independence. Separate models combined downstream are not automatically
equivalent to one jointly fitted model.

A consumer's rolling standardized break score is a separate, derived readout. Putting
two streams on dimensionless scales does not establish the model-level comparison
contract or cross-domain equivalence. Preserve the original output alongside any such
transformation and validate the intended use explicitly.

## Measurements for downstream reasoning

Kirk supplies measurements; a reasoning layer investigates their meaning. Give that
layer evidence records with timestamps, context and uncertainty, rather than isolated
numbers. It can examine coincidences, recurrences and links to external events, propose
explanations, and identify evidence that would distinguish those explanations.

An explanation generated downstream remains a hypothesis until supported. A discovery
score is not itself a semantic class, a causal conclusion or an instruction to act.

## The commercial proposition

The service is **discovering and measuring phenomena in customer data**. The phenomena
already exist; the deliverable makes observations inspectable and useful to investigate.

A possible engagement starts with data-fit work and a historical discovery catalogue,
then continues with monitoring and catalogue maintenance. Evaluating or implementing a
customer response is a separate scope. This describes a commercial structure, not an
announced subscription or a change to existing API metering and commercial terms.

Value and billing units are distinct. Raw alert counts are a poor proxy for useful
discovery and can reward noise. Evaluate coverage, evidence quality, repeatability,
review effort and the customer's continued use of the findings.

The claim to earn is: **here are meaningful behaviours your existing analysis was not
surfacing, and a repeatable way to keep discovering them.** Establish it through a fair
comparison. Novelty may concern the behaviour, its discovery in a particular dataset,
or the cost and scale of discovery; none follows merely from producing a catalogue.

## Next steps

- Check [capability fit](capability-fit.md) and the chosen input contract.
- Use [Interpreting Results](interpreting-results.md) to separate exploration from tests.
- Start a reproducible experiment with [Benchmark 001](../benchmarks/benchmark-001-l2-order-book/README.md).
