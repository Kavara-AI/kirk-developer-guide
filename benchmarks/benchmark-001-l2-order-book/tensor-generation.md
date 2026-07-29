# Tensor Generation

## Input schema

Use the ordered feature list defined in the benchmark README.

## Initial preprocessing

- align all observations to the common 100 ms grid
- derive spread, returns, imbalance and rolling volatility
- avoid future leakage in rolling calculations
- apply rolling or pre-fitted scaling
- preserve the regime label outside the input tensor

## Windowing

```text
window_length = 256
stride = 16
tensor_shape = 256 × 10
```

Each tensor should have metadata:

```json
{
  "tensor_id": 0,
  "start_index": 0,
  "end_index": 255,
  "start_timestamp": "...",
  "end_timestamp": "...",
  "feature_schema_version": "1.0"
}
```

## Sensitivity runs

Repeat with:

- window lengths: 64, 128, 256, 512
- strides: 1, 8, 16, 32
- feature ablations
- altered noise levels
- missing-data injection
