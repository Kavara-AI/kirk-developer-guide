# Tensor Generation

**The engine builds the tensor. You supply the observation.**

This is the most common integration mistake, so it is worth stating before anything
else: you do not construct a tensor and send it. You send a snapshot in the shape the
model expects, and the sealed engine renders it.

## The live contract (L2 order book)

`kirk_render_book` takes two arrays and returns the rendered tensor for inspection:

```text
bid_px   10 bid prices, level 1 first
ask_px   10 ask prices, level 1 first
```

The engine renders these into a **20 × 20 complex128** tensor whose rows are
`Bid1..Bid10` and `Ask1..Ask10`.

You can confirm this yourself without spending anything — `kirk_render_book` costs
0 IU and does not invoke the sealed engine:

```json
{"shape": [20, 20], "dtype": "complex128", "non_zero_cells": 50,
 "mid_price": 223.095, "spread_ticks": 1.0}
```

See [`examples/quickstart`](../examples/quickstart/README.md) for a runnable version.

## Decisions that remain yours

The rendering is fixed, but everything upstream of it is your experiment and must be
documented:

1. Sampling interval and snapshot cadence
2. Which book levels you capture, and what you do when fewer than 10 are quoted
3. Timestamp alignment across streams
4. Missing-data policy
5. Warm-up period before the first scored snapshot
6. Metadata attached to each observation

## Avoid leakage

For online evaluation, nothing you derive at time `t` may use observations after `t`.
This applies to any normalisation, scaling or standardisation you perform before
submitting a snapshot — use rolling or pre-defined statistics, never full-sample ones.

## Preserve provenance

Each output should be traceable to:

- source data range
- feature schema version
- observation index
- start and end timestamps
- preprocessing configuration
- **Kirk engine sha** (`kirk_version`, stamped on every response)
- run parameters

The engine sha matters more than the rest: results from different engine builds are not
interchangeable, and a result without its sha cannot be placed in a lineage later.

## Other input shapes

The 10+10 book contract above is what the public MCP surface accepts today. Other
observation shapes exist for other integration paths; contact Kavara rather than
inferring a contract from this page.
