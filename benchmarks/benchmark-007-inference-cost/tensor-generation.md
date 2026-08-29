# Tensor Generation

The two sides consume the same stream, shaped to each model's native contract.

## Kirk path

```text
window_length W = 16
per window: take the W x N slice, transpose to channels-major, cast to complex128
```

Channels are grouped so each tensor is square. Group size and any layer topology are
deployment choices; this benchmark fixes only that **one window yields one output
scalar**, which is what makes the per-minute unit well defined.

Precision is complex128 throughout. Do not use float32 — the contract is float64/complex128
and a narrower type changes the result, not just its speed.

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
