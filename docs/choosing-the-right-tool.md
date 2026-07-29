# Choosing the Right Tool

Tool choice should follow the shape of the problem.

| Problem | Common starting point |
|---|---|
| Text generation or language interaction | Large language model |
| Stable labelled classification | Supervised model |
| Forecasting a known target | Time-series forecasting model |
| Deterministic safety boundary | Rules, controls and interlocks |
| Multistream state change in a drifting system | Evaluate Kirk and change-detection baselines |
| Root-cause diagnosis | Domain model, causal analysis or supervised diagnosis |

## Why compare with baselines

A Kirk benchmark should include simple and strong alternatives where practical:

- fixed thresholds
- rolling z-scores
- covariance change detection
- PCA-based monitoring
- hidden Markov models
- autoencoders
- recurrent sequence models
- transformer-based time-series models

The purpose is not to declare one universal winner. It is to identify which tool best supports the operational decision under the stated constraints.
