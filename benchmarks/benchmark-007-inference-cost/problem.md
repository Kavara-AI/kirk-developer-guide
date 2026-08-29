# Problem

## The setting

You have a live multi-channel stream — order books, sensors, telemetry — and you want a
continuous scalar that tells you when the system's structure has changed. You will run
this every window, forever. Cost is therefore not a footnote; it is the deployment
constraint.

## What is measured

For each approach, on identical synthetic input:

1. **Throughput** — units of output signal per second, at a fixed thread count.
2. **Energy** — joules per unit of output signal, measured at the package via RAPL,
   with an idle baseline subtracted.
3. **Scaling** — how both move as the channel count N and the window W grow.

## What is deliberately NOT measured

- **Detection quality.** That is Benchmark 001. Mixing the two invites the failure where
  a cheap detector looks good because it never fires.
- **Training cost.** Kirk learns online; the foundation model is pretrained. There is no
  common training axis, so none is claimed.
- **GPU.** A CPU-only comparison is the honest floor and the one most developers can
  reproduce. A GPU column is welcome as a separate contribution — but see
  `interpretation.md` on why a GPU number does not transfer across the two systems.

## Why CPU-only for the reference run

The reference run forces the forecasting model onto CPU deliberately:

- it is the configuration every developer can reproduce without accelerator access;
- RAPL package energy is directly attributable, whereas splitting host/device energy on
  an accelerator needs separate instrumentation;
- it establishes the worst case for the forecaster, which must be stated plainly rather
  than buried — see `interpretation.md`.
