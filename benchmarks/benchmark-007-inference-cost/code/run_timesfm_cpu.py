#!/usr/bin/env python3
"""TimesFM forced onto CPU — throughput per unit of output signal.

Forcing CPU is deliberate and is asserted, not assumed: a silent fallback to an
accelerator would make the energy figure meaningless, since RAPL package counters do
not see device power.

Install (CPU-only wheel):
    pip install timesfm
    pip install torch --index-url https://download.pytorch.org/whl/cpu
"""
import argparse, os, time
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--stream", default="stream.npy")
ap.add_argument("--context", type=int, default=128)
ap.add_argument("--threads", type=int, default=32)
ap.add_argument("--channels", type=int, default=0, help="0 = all in the stream")
ap.add_argument("--windows", type=int, default=64, help="output windows to time")
ap.add_argument("--batch", type=int, default=512)
a = ap.parse_args()

# Must be set before torch imports its threading runtime.
os.environ.setdefault("OMP_NUM_THREADS", str(a.threads))
os.environ.setdefault("MKL_NUM_THREADS", str(a.threads))
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")     # hard CPU lock

import torch, timesfm

assert not torch.cuda.is_available(), (
    "CUDA is visible; this benchmark measures CPU. Unset CUDA_VISIBLE_DEVICES only if "
    "you intend a GPU run, and then do NOT report package-RAPL energy."
)
torch.set_num_threads(a.threads)
print(f"device=cpu threads={torch.get_num_threads()} torch={torch.__version__}")

X = np.load(a.stream)
N = a.channels or X.shape[1]
X = X[:, :N]
print(f"stream {X.shape} -> using {N} channels")

model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
    "google/timesfm-2.5-200m-pytorch", torch_compile=False)
model.compile(timesfm.ForecastConfig(max_context=a.context, max_horizon=1,
                                     normalize_inputs=True, per_core_batch_size=64))

starts = list(range(a.context, a.context + a.windows))
inputs = [X[t - a.context : t, c].astype(np.float32) for t in starts for c in range(N)]
model.forecast(horizon=1, inputs=inputs[: min(64, len(inputs))])   # warm

t0 = time.perf_counter()
preds = []
for i in range(0, len(inputs), a.batch):
    pt, _ = model.forecast(horizon=1, inputs=inputs[i : i + a.batch])
    preds.append(np.asarray(pt).reshape(-1))
dt = time.perf_counter() - t0

n_fc = len(inputs)
print(f"forecasts={n_fc}  windows={a.windows}  channels={N}")
print(f"elapsed={dt:.2f}s  {n_fc/dt:.1f} forecasts/s  {a.windows/dt:.2f} signal-windows/s")
print(f"calls_per_output_window={N}")
