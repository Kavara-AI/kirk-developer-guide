# Tensor Generation

## Input schema

Use the ordered feature list defined in the benchmark README.

## Initial preprocessing

- align all observations to the common 100 ms grid
- derive spread, returns, imbalance and rolling volatility
- avoid future leakage in rolling calculations
- apply rolling or pre-fitted scaling
- preserve the regime label outside the input tensor

## Model input

Kirk accepts one square matrix per time step. Build it from the aligned feature
window. The numbers below describe that source window.

```text
source_window_length = 256
stride = 16
features = 10
```

Example constructions, each recorded with row and column meaning:

- a 10 × 10 channel-by-channel summary over the source window
- a square matrix of side 16 or 32, built from selected lags or from channels
  against an equal number of recent steps

Each matrix should have metadata:

```json
{
  "tensor_id": 0,
  "start_index": 0,
  "end_index": 255,
  "start_timestamp": "...",
  "end_timestamp": "...",
  "feature_schema_version": "1.0",
  "construction": "10x10 channel-by-channel summary over the source window"
}
```

## Sensitivity runs

Repeat with:

- window lengths: 64, 128, 256, 512
- strides: 1, 8, 16, 32
- feature ablations
- altered noise levels
- missing-data injection
