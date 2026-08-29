# Running the Benchmark

## 0. Prerequisites

```bash
python -m pip install numpy timesfm
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only wheel
perf stat -a -e power/energy-pkg/ -- sleep 1      # must print Joules, else see below
```

If `perf` cannot read the event: `sudo sysctl -w kernel.perf_event_paranoid=0`.
`/sys/class/powercap/.../energy_uj` is root-only on most modern kernels, which is why this
benchmark reads RAPL through `perf` rather than sysfs.

## 1. Generate the stream

```bash
python code/generate_data.py --channels 512 --windows 2000 --mode MOMENT_MATCHED --seed 42
```

Record the printed `sha256`. Two runs on the same seed must match.

## 2. TimesFM, forced onto CPU

```bash
python code/run_timesfm_cpu.py --threads 32 --channels 512 --windows 64
```

The script sets `CUDA_VISIBLE_DEVICES=""` and **asserts** `torch.cuda.is_available()` is
false. This is not belt-and-braces: package RAPL counters do not see accelerator power, so
a silent GPU fallback would produce a real-looking energy number that is simply wrong.

**Thread count matters more than you expect.** Measure the scaling curve before choosing
a number to report:

```bash
for T in 1 2 4 8 16 32 64; do
  python code/run_timesfm_cpu.py --threads $T --channels 64 --windows 32 | tail -2
done
```

On the reference machine throughput **saturated at or below 32 threads and got worse at
64**. Report the curve, not a single point — a single point invites the reader to assume
it scales.

## 3. Energy

```bash
IDLE_SECS=40 code/measure_energy.sh \
  python code/run_timesfm_cpu.py --threads 32 --channels 512 --windows 64
```

Prints idle W, workload W, attributable W and J, and an idle re-check so you can bound
baseline drift. Divide the attributable joules by the run's output-window count.

**Size the run so model load is amortised.** `perf` brackets the whole process, including
the one-off checkpoint load. On a short run that load can dominate the energy figure — a
16-window run on the reference machine spent most of its wall clock loading. Use enough
windows that the steady-state loop is at least ~10x the load time (30-60 s of loop is a
good target), or measure the load separately and subtract it.

## 4. Kirk side

Kirk's cost per output scalar depends on the deployment path:

| path | what you can measure | what you cannot |
|---|---|---|
| **In-process / sealed engine on your own host** | engine throughput **and** RAPL energy | — |
| **Hosted MCP surface** (`kirk_score_book_batch`) | end-to-end throughput | engine energy — the number is network round-trip, not compute |

Use the in-process path for the energy column. If you only have the hosted surface,
report throughput and **leave the energy cell empty** rather than filling it with a
round-trip figure; a network-bound number in an energy column is worse than no number.

Hyperparameters and topology are deployment properties and are not published in this
repo — use your endpoint's defaults and state which build you ran.

## 5. Report

Fill in `expected-results.md`'s table, and always include:

- idle baseline W and the drift between the two idle brackets
- thread count and the scaling curve
- the data `sha256`
- calls per output window for each side
