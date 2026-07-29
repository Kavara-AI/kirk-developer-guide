# Interpreting Results

Kirk outputs must be interpreted in the context of the input tensor sequence and the operational question.

## Questions to ask

- Does the output change near a known regime boundary?
- How early or late is the response?
- Does it remain elevated after the transition?
- Does it return during recovery?
- Is it sensitive to isolated noise?
- Is the response reproducible?
- Does feature scaling materially change the result?

## Useful evaluation measures

- detection delay
- false-positive rate
- missed-transition rate
- stability within a regime
- separation between regimes
- sensitivity to window size
- sensitivity to feature removal
- reproducibility across random seeds

## Do not overclaim

A visual alignment between an output peak and an event is not enough. Record the event definition, tolerance window and comparison method before inspecting the result where possible.

## Recommended artifacts

Commit:

- raw or generated data
- tensor metadata
- Kirk output as CSV or JSON
- run manifest
- figures
- interpretation notes
