#!/usr/bin/env python3
"""Deterministic synthetic multi-channel stream for Benchmark 007."""
import argparse, hashlib
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--channels", type=int, default=512)
ap.add_argument("--windows", type=int, default=2000)
ap.add_argument("--group-size", type=int, default=16)
ap.add_argument("--scale", type=float, default=1e-3)
ap.add_argument("--mode", choices=["NULL", "VARIANCE", "MOMENT_MATCHED"], default="MOMENT_MATCHED")
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--out", default="stream.npy")
a = ap.parse_args()

rng = np.random.default_rng(a.seed)
half = a.windows // 2
base = rng.normal(scale=a.scale, size=(half, a.channels))

if a.mode == "NULL":
    brk = rng.normal(scale=a.scale, size=(half, a.channels))
elif a.mode == "VARIANCE":
    brk = rng.normal(scale=a.scale, size=(half, a.channels)) * np.sqrt(1.7)
else:  # MOMENT_MATCHED — dependency change with all moments preserved
    brk = rng.normal(scale=a.scale, size=(half, a.channels))
    for g in range(a.channels // a.group_size):
        i, j, k = g * a.group_size, g * a.group_size + 1, g * a.group_size + 2
        brk[:, k] = np.sign(brk[:, i]) * np.sign(brk[:, j]) * np.abs(brk[:, k])

X = np.vstack([base, brk]).astype(np.float64)
np.save(a.out, X)
digest = hashlib.sha256(X.tobytes()).hexdigest()
print(f"wrote {a.out} shape={X.shape} mode={a.mode} seed={a.seed}")
print(f"break_index={half}")
print(f"sha256={digest}")
