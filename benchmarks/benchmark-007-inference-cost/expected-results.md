# Expected Results

These are pre-registered evaluation targets, not reported results.

## Report this table

| | calls / output window | throughput (windows/s) | threads | attributable W | J / output window |
|---|---|---|---|---|---|
| Kirk | | | | | |
| forecaster (TimesFM, CPU) | | | | | |

Plus: idle baseline W, idle drift %, data `sha256`, channel count N, window W, context length.

## Primary expectation

The cost gap should be **driven mainly by calls per output window, not by per-call speed**.
If the per-call figures are close while the per-output-window figures diverge, that is the
expected shape. If instead the gap tracks per-call speed, something in the harness is wrong
— most likely call aggregation is hiding per-call cost, or the forecaster is not actually
producing one scalar per window.

## Secondary expectations

- Forecaster throughput saturates well below the machine's core count; beyond that, more
  threads reduce throughput.
- The gap varies with panel dimension N, and at small N it narrows; report every N you ran
  rather than only the most favourable one.
- Energy ordering matches time ordering at fixed thread count; if they disagree, suspect
  frequency-licence effects (see `interpretation.md`).

## Failure conditions

Consider the run **inconclusive** if any of these hold:

- no idle baseline was captured, or idle drift between brackets exceeds ~2%
- the attributable power delta is below ~3x the idle drift (the signal is inside the noise)
- CUDA was visible during a run reported with package-RAPL energy
- the two sides produced different numbers of output windows
- results are not reproducible from the same seed and `sha256`
- standardisation of the forecaster residual used full-sample statistics (future leakage)

## Explicit non-goals

Detection quality, accuracy, and lead time. A method that is cheaper *and* worse is not
better, and this benchmark cannot tell you which you have. Pair it with Benchmark 001.
