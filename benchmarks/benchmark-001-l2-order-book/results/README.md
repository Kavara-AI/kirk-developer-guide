# Benchmark 001 — first run results (4 November 2026)

Kirk on `https://api.kavara.ai` (`release_id: kip-customer`) through kit 0.1.2 (kirk-client 0.1.3+kit3,
kirk-remote 0.1.3+kit4, kavara-preprocess 0.2.1, Uhura render `rms-tanh/1`). Synthetic data only.

**Bottom line.** Kirk's frozen-model entropy was the best *regime-state indicator* we measured: it moved
between distinct levels per regime more cleanly than any baseline, on all four seeds (Observed). It was
**not** a better *boundary detector*: with one shared step-change detector, simple baselines found more
boundaries (Observed). The pre-declared primary configuration failed outright. By the benchmark's own
failure condition ("a simple baseline performs equally well with lower complexity"), Benchmark 001 is
**inconclusive** for Kirk.

## What was run

| Item | Value |
|---|---|
| Data | `code/generate_data.py`: 20,000 steps at 100 ms, 10 features, 5 regimes per `data-generation.md`; null control stream (stable throughout) with its own seed. Manifests with SHA-256 next to each `.npz`. |
| Seeds | Selection seed pair: regimes 1 / null 2. Confirmation seed pairs: 101/201, 102/202, 103/203. |
| Windows | 256 observations, stride 16 → 1,235 windows per stream; warm-up = observations 0–1,999. |
| Constructions | **lag** (16×16: 10 feature rows + 6 zero rows × 16 columns of 16-step changes; the Ulysses guide's time-series input; pre-declared primary), **corr** (10×10 Pearson), **cov** (10×10 covariance scaled by warm-up sd). All rendered with Uhura. |
| Kirk | `enforce_purity=True`, `random_state=7`, entropy output. **frozen**: learn the warm-up, then score without learning. **online**: keep learning through the stream; score = entropy returned by learn. Learning rates 0.005 (pre-declared primary, from the kit notebook), 0.0005, 0.00005 (Ulysses guide default). |
| Baselines | per-feature z of window means; Frobenius distance of each construction's matrix from the warm-up mean (`dist_ref`) and from the matrix one full window earlier (`dist_lag`). |
| Detector | `dev_t = s_t − mean(previous 16)`, alarm at the 99.5th percentile of `|dev|`, 16-window refractory, tolerance 768 observations after a boundary. Same for every method. |
| API | 101 + 92 calls (selection) and 6 × 32 (confirmation), all `200`; no rate limiting. |
| Reproducibility | Same seed, same inputs → bitwise-identical entropy (frozen and online). **Demonstrated** (`regimes.run.json`). |

## Results

### Pre-declared primary (lag, online, lr 0.005): failed

**Observed.** 0/4 boundaries with the pre-registered detector, 1/4 with the post-hoc one. Its entropy
oscillates between ~2.3 and ~0.23 on alternate samples during warm-up and then climbs steadily on the null
stream too (≈1.0 → 4.9), so its high raw η² (0.92) is mostly a time trend. The Ulysses guide lists unstable
or runaway outputs as a sign the learning rate is too high; 0.005 is 100× its default.

### Deviation from the pre-registration (post-hoc, disclosed)

1. **Detector calibration.** The pre-registered threshold came from the null stream. Independently trained
   Kirk models give different score scales on the same kind of data (frozen `cov`: ≈0.49 vs ≈1.00), so a
   threshold does not transfer between models. The post-hoc detector calibrates each stream on its own
   known-stable windows (ending 2,000–3,999). Both sets of numbers are in `metrics*.json`.
2. **Trend control.** η² of (regime-stream score − null-stream score) is added, because regimes are in
   time order and any trend inflates plain η².
3. **Configuration selection.** `kirk_lag_lr5e-05_frozen` was chosen *after* seeing 18 Kirk configurations
   on the selection seed (where it hit 4/4). It was then fixed and rerun on three fresh seed pairs.

### Named configuration vs. baselines, all four seeds (post-hoc detector)

| Method | Boundaries hit (of 16) | Hit the gradual onset | False alarms /1k | Null false alarms /1k | Trend-controlled η² (mean, range) |
|---|---:|---:|---:|---:|---|
| `kirk_lag_lr5e-05_frozen` | 10 | 2/4 | 13.6 | 7.3 | **0.63** (0.60–0.68) |
| `baseline_univariate_z` | **14** | 2/4 | 29.6 | 12.0 | 0.42 (0.28–0.59) |
| `baseline_lag_dist_lag` | **14** | 2/4 | 34.0 | 5.8 | 0.43 (0.28–0.57) |
| `baseline_lag_dist_ref` | **14** | 2/4 | 33.1 | 8.4 | 0.34 (0.20–0.44) |
| `baseline_cov_dist_lag` | 13 | 1/4 | 31.6 | 8.0 | 0.23 (0.12–0.33) |
| `baseline_cov_dist_ref` | 13 | 1/4 | 32.0 | 9.3 | 0.15 (0.07–0.23) |
| `baseline_corr_dist_ref` | 8 | 1/4 | 9.3 | 6.0 | 0.44 (0.35–0.51) |
| `baseline_corr_dist_lag` | 5 | 0/4 | 5.6 | 7.1 | 0.07 (0.01–0.12) |

On the three confirmation seeds alone, the Kirk configuration hit 6/12 boundaries (2, 1, 3).

## Reading the results against `expected-results.md`

| Expectation | Status |
|---|---|
| Reproducible change near regime boundaries | **Observed, partly.** Frozen lag entropy shifts level at the cancellation, shock and recovery boundaries (see `benchmark001.png`); a step detector catches it inconsistently. |
| Lower within-regime than cross-regime variability | **Observed.** Trend-controlled η² 0.60–0.68 on every seed, the highest of any method. |
| Response to gradual accumulation | **Not observed** for Kirk or the baselines (2/4 seeds at most; no visible level change). |
| Distinct response to cancellation vs. shock | **Observed** for frozen lag (≈0.66 vs ≈0.69 on the selection seed, against a stable level ≈0.64). |
| Recovery returns toward stable | **Observed** for frozen lag (recovery ends within ~1 sd of stable on 3 of 4 seeds). |
| Failure: a simple baseline performs equally well | **Triggered for detection.** Not triggered for regime separation. |
| Failure: results disappear under minor changes | **Partly triggered.** Results depend strongly on learning rate and mode (18 configurations range from 0 to 4 hits). Window and stride sensitivity, feature ablations, noise and missing-data runs were **not done**. |

## Limitations and alternative explanations

- Synthetic data; the regimes also change feature means, which favours the simple baselines.
- Uhura renders each window by its own RMS, which removes overall magnitude. Some regime information (for
  example, volatility level) is therefore hidden from Kirk but visible to the baselines.
- The false-alarm metric counts every alarm inside a volatile regime as false. That penalises baselines whose
  noise rises with volatility; a different alarm policy could change the ranking.
- One detector suits step changes. Kirk's frozen output behaves like a level indicator, so a level or
  regime-classification read-out (an HMM, as the Ulysses guide suggests) may suit it better. **Hypothesis.**
- Cooling rate, tau and initialisation range were left at kit defaults; there was no hyperparameter search
  beyond three learning rates.
- No LSTM or other learned baseline.

## Reproduce

```bash
python code/generate_data.py --out data/regimes.npz --seed 1
python code/generate_data.py --out data/null.npz --seed 2 --null
python code/run_benchmark.py --data data/regimes.npz --out results/regimes --repeat   # needs KAVARA_API_KEY
python code/run_benchmark.py --data data/null.npz --out results/null
python code/evaluate.py && python code/plot.py
# confirmation: seeds 101..103 / 201..203 with --lrs 0.00005, then evaluate.py --suffix _c1 (etc.)
```

Run with the kit's virtual environment (plus `matplotlib`). Outputs: `*.scores.npz` (every score series),
`*.run.json` (run manifest and API call ledger), `metrics*.json`, `summary_table.md`, `benchmark001.png`.
