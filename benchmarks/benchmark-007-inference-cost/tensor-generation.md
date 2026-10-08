# Tensor Generation

The two sides consume the same stream, shaped to each model's native contract.

## Kirk path

The source stream is a window of length W by N channels. `stream.npy` stores
that panel as float64. Kirk accepts one square real- or complex-valued matrix
per step. You build it.

With this benchmark's default W = 16 and group size 16, one construction is a
16 × 16 matrix per channel group: one axis is the window's time steps, the
other is the 16 channels in the group. Record which axis is which.
Channel-by-channel products inside the group are another square construction.
The group size is also the width used when `generate_data.py` installs the
`MOMENT_MATCHED` dependency.

This benchmark's reported unit remains **one output scalar per source window**.
If a window produces more than one matrix, record how you reduce those scores
to the one scalar the table counts. A non-square W × N slice is source data
for that construction.

Entries may be real or complex. Record the numeric type you send. This
benchmark's source file is float64. A complex matrix in this benchmark is
complex128. A different precision is a different preparation.

> Hyperparameters are a property of your deployment and are not published here. Use your
> endpoint's defaults, or the public model id exposed by your Kirk surface. Report which
> you used; do not report hyperparameters you were given under agreement.

## Forecasting path (TimesFM)

```text
context_length = 128
horizon        = 1
per window: one forward pass PER CHANNEL, from the trailing 128 values
residual(c, t)  = actual(c, t) - forecast(c, t)
signal(t)       = mean_c |residual(c, t)| / trailing_std(residual(c, ...))
```

Standardisation must be **trailing-only** (rolling std of prior residuals, shifted by one).
Using a full-sample std leaks future information into the signal and inflates the result.

Each side is shaped to its own native contract, so the per-call columns are not
comparable; the per-output-window unit is.
