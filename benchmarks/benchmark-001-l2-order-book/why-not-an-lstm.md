# Why Compare with an LSTM?

An LSTM is a reasonable sequence-model baseline because it can learn temporal patterns from ordered observations.

The benchmark should not begin with the claim that an LSTM is unsuitable. It should test concrete differences.

## Questions for comparison

- Does the LSTM require labelled regime examples?
- How does it behave on a regime absent from training?
- How often must it be retrained?
- How sensitive is it to class imbalance?
- What is the detection delay?
- How stable is performance under distribution drift?
- What compute and tuning are required?

## Fair comparison

Specify:

- training and validation ranges
- target labels
- architecture and parameter count
- optimiser and stopping rule
- random seeds
- threshold selection
- inference latency
- retraining policy

A useful conclusion may be that each method serves a different operational role.
