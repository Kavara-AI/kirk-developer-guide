# What is Kirk?

Kirk is an inference engine intended for complex, non-stationary systems.

For this guide, that means systems with:

- several interacting variables
- continuous or repeated observations
- behaviour that changes over time
- incomplete labels
- operational regimes that may not be known in advance

Kirk should be evaluated on its ability to characterise changes in joint system behaviour. It is not enough to show that one feature crossed a threshold.

## A useful mental model

Traditional point-anomaly logic asks:

> Is this measurement unusual relative to its history?

A relationship-aware system asks:

> Is the way these measurements move together different from before?

The second question can reveal a state change even when every individual value remains within a familiar range.

## What Kirk does not provide by itself

A system-change signal is not automatically a diagnosis.

A production application may still require:

- domain rules
- causal analysis
- physics-based models
- operator review
- supervised classifiers
- control logic
- safety interlocks

Kirk's output should be treated as evidence about system behaviour, not as an unrestricted authority to actuate a safety-critical system.

## Next steps

- Check [capability fit](capability-fit.md).
- Review [limitations](limitations.md).
- Run [Benchmark 001](../benchmarks/benchmark-001-l2-order-book/README.md).
