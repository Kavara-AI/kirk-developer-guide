# Benchmark 001 — first run results (4 November 2026)

Kirk on `https://api.kavara.ai` (`release_id: kip-customer`) through kit 0.1.2 (kirk-client 0.1.3+kit3,
kirk-remote 0.1.3+kit4, kavara-preprocess 0.2.1, Uhura render `rms-tanh/1`). Synthetic data only.

**Bottom line.** On this synthetic benchmark Kirk showed **no advantage** over simple baselines, under
either read-out we tried (Observed):

- *As a change detector* (alarms at boundaries), simple baselines found more boundaries (14 of 16 vs 10 of 16).
- *As a regime label* (an unsupervised hidden Markov model on the score, as the Kavara usage guide suggests; that guide is Kavara's guidance on using Kirk outputs and is not published in this repository),
  baselines labelled regimes better (adjusted Rand index 0.42–0.50 vs 0.32), and adding Kirk to the best
  baseline changed little (0.51 vs 0.49).

An earlier version of this page reported that Kirk separated regimes best. **That was an artefact** of the
baselines' heavy-tailed scores; on a common rank scale the baselines separate regimes better (see
"Correction" below). The pre-declared primary configuration failed outright. By the benchmark's own failure
condition ("a simple baseline performs equally well with lower complexity"), Benchmark 001 is
**unsuccessful** for Kirk in this form. What was *not* tested is listed under Limitations.

## What was run

| Item | Value |
|---|---|
| Data | `code/generate_data.py`: 20,000 steps at 100 ms, 10 features, 5 regimes per `data-generation.md`; null control stream (stable throughout) with its own seed. A manifest next to each `.npz` records the seed and the first 6 hex characters of the data's SHA-256; `generate_data.py` prints the full digest. |
| Seeds | Selection seed pair: regimes 1 / null 2. Confirmation seed pairs: 101/201, 102/202, 103/203. |
| Windows | 256 observations, stride 16 → 1,235 windows per stream; warm-up = observations 0–1,999. |
| Constructions | **lag** (16×16: 10 feature rows + 6 zero rows × 16 columns of 16-step changes; the Kavara usage guide's time-series input; pre-declared primary), **corr** (10×10 Pearson), **cov** (10×10 covariance scaled by warm-up sd). All rendered with Uhura. |
| Kirk | `enforce_purity=True`, `random_state=7`, entropy output. **frozen**: learn the warm-up, then score without learning. **online**: keep learning through the stream; score = entropy returned by learn. Learning rates 0.005 (pre-declared primary, from the kit notebook), 0.0005, 0.00005 (Kavara usage guide default). |
| Baselines | per-feature z of window means; Frobenius distance of each construction's matrix from the warm-up mean (`dist_ref`) and from the matrix one full window earlier (`dist_lag`). |
| Detector | `dev_t = s_t − mean(previous 16)`, alarm at the 99.5th percentile of `|dev|`, 16-window refractory, tolerance 768 observations after a boundary. Same for every method. |
| API | 101 + 92 calls (selection) and 6 × 32 (confirmation), all `200`; no rate limiting. |
| Reproducibility | Same seed, same inputs → bitwise-identical entropy (frozen and online). **Demonstrated** (`regimes.run.json`). |

## Results

### Pre-declared primary (lag, online, lr 0.005): failed

**Observed.** 0/4 boundaries with the pre-registered detector, 1/4 with the post-hoc one. Its entropy
oscillates between ~2.3 and ~0.23 on alternate samples during warm-up and then climbs steadily on the null
stream too (≈1.0 → 4.9), so its high raw η² (0.92) is mostly a time trend. The Kavara usage guide lists unstable
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

## Read-out 2: Kirk's output as a regime label (HMM)

`code/regime_labels.py` reuses the stored scores (no new API calls). Fixed before looking at results: each
score series is rank-transformed to a normal scale, then a 5-state Gaussian HMM is fitted (10 restarts,
best likelihood) and its Viterbi path is compared with the true regimes. The **trend control** fits the
same HMM to the null stream's scores and scores it against the regime stream's timing; a method that only
reads time does well there too.

| Method | ARI mean (min–max), 4 seeds | Trend control ARI | Matched accuracy | State switches (truth 4) |
|---|---|---:|---:|---:|
| Kirk named + `baseline_univariate_z` (2-D HMM) | **0.51** (0.45–0.56) | 0.03 | 0.68 | 28 |
| `baseline_cov_dist_ref` | 0.50 (0.45–0.54) | 0.04 | 0.67 | 29 |
| `baseline_univariate_z` | 0.49 (0.43–0.53) | 0.03 | 0.65 | 28 |
| `baseline_lag_dist_lag` | 0.48 (0.44–0.53) | 0.04 | 0.66 | 21 |
| `baseline_lag_dist_ref` | 0.44 (0.34–0.50) | 0.03 | 0.63 | 32 |
| `baseline_cov_dist_lag` | 0.42 (0.36–0.49) | 0.04 | 0.64 | 42 |
| `kirk_cov_lr5e-05_frozen` | 0.32 (0.23–0.43) | 0.01 | 0.51 | 60 |
| `kirk_lag_lr5e-05_frozen` (named) | 0.32 (0.26–0.37) | 0.04 | 0.51 | 55 |
| `kirk_lag_lr5e-05_online` | 0.30 (0.28–0.32) | **0.31** | 0.46 | 896 |
| `baseline_corr_dist_ref` | 0.17 (0.15–0.20) | 0.02 | 0.40 | 149 |

Full table: `regime_labels_table.md`; per-seed detail: `regime_labels.json`.

- **Observed.** Kirk's entropy is a worse regime label than five of the seven baselines. Its labels switch
  state about twice as often as the baselines', so its window-to-window noise is high relative to the
  regime shifts.
- **Observed.** Online Kirk scores well on the trend control (ARI 0.20–0.31 on a stream with no regimes):
  its labels follow elapsed time, not regimes.
- **Observed.** Adding Kirk to the best simple baseline raised ARI by 0.02 on average (0.51 vs 0.49), within
  the seed-to-seed spread. The Kavara usage guide's claim that entropy improves HMM classification on financial
  data is **not reproduced here** on synthetic data.
- On the selection seed alone, the best Kirk configuration reached ARI 0.44 (`lag`, frozen, lr 0.0005),
  still below the best baseline on that seed.

## Correction: regime separation

The first version of this page claimed that Kirk's frozen entropy separated regimes best (trend-controlled
η² 0.63 vs ≤ 0.44). The baselines' scores are heavy-tailed (values up to ~10⁴ in the shock regime), which
inflates their within-regime variance and depresses a raw η². On a common rank scale (the same transform
the HMM uses):

| Method | η², raw (minus null) | η², rank scale |
|---|---:|---:|
| `kirk_lag_lr5e-05_frozen` | 0.63 | 0.63 |
| `baseline_univariate_z` | 0.42 | **0.75** |
| `baseline_lag_dist_lag` | 0.43 | **0.75** |
| `baseline_cov_dist_ref` | 0.15 | 0.73 |
| `baseline_lag_dist_ref` | 0.34 | 0.73 |
| `baseline_corr_dist_ref` | 0.44 | 0.50 |

The η² columns in the tables above are kept as computed; read them with this correction.

## Reading the results against `expected-results.md`

| Expectation | Status |
|---|---|
| Reproducible change near regime boundaries | **Observed, partly.** Frozen lag entropy shifts level at the cancellation, shock and recovery boundaries (see `benchmark001.png`); a step detector catches it inconsistently. |
| Lower within-regime than cross-regime variability | **Observed** for Kirk (η² 0.60–0.65 on every seed), but **lower than four baselines** (0.73–0.75) once all scores are on a rank scale. |
| Response to gradual accumulation | **Not observed** for Kirk or the baselines (2/4 seeds at most; no visible level change). |
| Distinct response to cancellation vs. shock | **Observed** for frozen lag (≈0.66 vs ≈0.69 on the selection seed, against a stable level ≈0.64). |
| Recovery returns toward stable | **Observed** for frozen lag (recovery ends within ~1 sd of stable on 3 of 4 seeds). |
| Failure: a simple baseline performs equally well | **Triggered** for detection, for regime separation and for HMM regime labelling. |
| Failure: results disappear under minor changes | **Partly triggered.** Results depend strongly on learning rate and mode (18 configurations range from 0 to 4 hits). Window and stride sensitivity, feature ablations, noise and missing-data runs were **not done**. |

## Limitations and alternative explanations

- Synthetic data; the regimes also change feature means, which favours the simple baselines.
- Uhura renders each window by its own RMS, which removes overall magnitude. Some regime information (for
  example, volatility level) is therefore hidden from Kirk but visible to the baselines.
- The false-alarm metric counts every alarm inside a volatile regime as false. That penalises baselines whose
  noise rises with volatility; a different alarm policy could change the ranking.
- Only Kirk's entropy output was used. The array, vector and scalar outputs (the Kavara usage guide's
  reconstruction and expected values) were not tried; they may carry more regime information. **Hypothesis.**
- The HMM read-out assumes five states and uses the whole series (offline); a causal, filtered read-out
  was not tested.
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
python code/regime_labels.py   # read-out 2 (needs hmmlearn, scikit-learn)
# confirmation: seeds 101..103 / 201..203 with --lrs 0.00005, then evaluate.py --suffix _c1 (etc.)
```

Run with the kit's virtual environment (plus `matplotlib`). Outputs: `*.scores.npz` (every score series),
`*.run.json` (run manifest and API call ledger), `metrics*.json`, `summary_table.md`, `benchmark001.png`.
