# Data Generation

Fully synthetic and deterministic. No licensed or proprietary data.

## Stream

```text
N_CHANNELS = 512        # vary: 16, 64, 128, 512
N_WINDOWS  = 2000
SCALE      = 1e-3       # log-return-like magnitude
SEED       = 42
```

Each channel is a zero-mean Gaussian increment series at `SCALE`. A structural break is
installed at the midpoint in one of three modes:

| mode | break | purpose |
|---|---|---|
| `NULL` | none | false-alarm floor |
| `VARIANCE` | variance x1.7 | a second-moment change any method should see |
| `MOMENT_MATCHED` | three-way sign-parity dependency within each group; every mean, variance and covariance preserved | a dependency change that second-moment methods are blind to |

`MOMENT_MATCHED` is the interesting one for cost: it is the case where you would want a
structural method, so it is the case where its cost matters.

## Reproducibility

`code/generate_data.py` writes `stream.npy` (float64, shape `N_WINDOWS x N_CHANNELS`) and
prints a SHA-256. Two runs on the same seed must produce identical digests. Report the
digest with your results.
