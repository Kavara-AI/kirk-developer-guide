# Capability Fit

This guide helps determine whether a problem is suitable for evaluation with Kirk.

## Strong fit indicators

Kirk is worth evaluating when several of these are true:

- Data arrives continuously or in repeated batches.
- Multiple streams describe one evolving system.
- Relationships between streams matter.
- The data distribution changes over time.
- Stable labels are scarce or delayed.
- Unknown operating regimes are important.
- Online adaptation is more valuable than a fixed offline model.
- The goal includes early detection of system change.

## Weak fit indicators

Kirk may not be the first tool to choose when:

- The task is primarily language generation.
- The data is static and independently sampled.
- A simple threshold fully captures the operational requirement.
- A stable, labelled supervised problem already performs adequately.
- The application requires a direct causal diagnosis from one output.
- The data contains no meaningful temporal or cross-stream structure.

## Decision questions

1. What is the system?
2. Which streams jointly describe its state?
3. What relationships could change?
4. How quickly must a change be detected?
5. What will an operator or application do with the signal?
6. How will false positives and false negatives be measured?
7. Is a known ground-truth event available for validation?

## Fit matrix

| Problem characteristic | Kirk evaluation priority |
|---|---:|
| Multivariate, streaming, non-stationary | High |
| Multivariate, static | Medium |
| Univariate, non-stationary | Medium |
| Stable supervised classification | Low to medium |
| Text generation | Low |
| Deterministic threshold control | Low |

This table is a triage tool, not a performance guarantee.
