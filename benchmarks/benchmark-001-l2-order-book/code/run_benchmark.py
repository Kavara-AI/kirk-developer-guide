"""Benchmark 001: build matrices, run Kirk on api.kavara.ai, compute baselines.

    KAVARA_API_KEY=... python run_benchmark.py --data data/regimes.npz --out results/regimes
    KAVARA_API_KEY=... python run_benchmark.py --data data/null.npz    --out results/null

Writes <out>.scores.npz (one score series per method, aligned to the stride-16 windows) and
<out>.run.json (run manifest: configuration, API call ledger, service release id).

Matrix constructions (one per window, regime label never used):
  lag  : 16 x 16, rows = features, columns = 16-step changes (primary; Ulysses guide time-series input).
  corr : Pearson correlation of the 10 features over the window.
  cov  : covariance of the window-demeaned features, each divided by its warm-up standard
         deviation (warm-up = observations 0..1999 only), so variance changes are kept.
Each matrix is rendered with Uhura (kavara_preprocess.uhura.render, rms-tanh/1) before sending.

Kirk modes:
  frozen : learn on stride-1 windows inside the warm-up (end < 2000), then score every
           stride-16 window without learning.
  online : a fork of the frozen model keeps learning on every stride-16 window in order;
           the score is the entropy returned by learn (active inference, scored while learning).
"""
from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np
import requests

from kavara_preprocess.uhura import identity, out_of_range, render
from kirk_client import KirkModel
from kirk_remote import RemoteBackend

WIN, STRIDE, WARMUP_END = 256, 16, 2000
BASE_URL = "https://api.kavara.ai"
CALLS: list[dict] = []


def windows(n: int, stride: int, end_before: int | None = None) -> np.ndarray:
    starts = np.arange(0, n - WIN + 1, stride)
    if end_before is not None:
        starts = starts[starts + WIN <= end_before]
    return starts


def corr_mats(X: np.ndarray, starts: np.ndarray) -> np.ndarray:
    out = np.empty((len(starts), X.shape[1], X.shape[1]))
    for i, s in enumerate(starts):
        w = X[s:s + WIN]
        w = w - w.mean(0)
        sd = np.sqrt((w ** 2).mean(0)) + 1e-12
        out[i] = (w.T @ w) / WIN / np.outer(sd, sd)
    return out


def cov_mats(X: np.ndarray, starts: np.ndarray, scale: np.ndarray) -> np.ndarray:
    out = np.empty((len(starts), X.shape[1], X.shape[1]))
    for i, s in enumerate(starts):
        w = (X[s:s + WIN] - X[s:s + WIN].mean(0)) / scale
        out[i] = (w.T @ w) / WIN
    return out


BLOCK, SIDE = 16, 16   # lag construction: 16 columns of 16-step changes, rows padded to 16


def block_changes(X: np.ndarray) -> np.ndarray:
    """Per-feature change over each 16-step block (returns-like, directional), per the Ulysses guide.
    Rate/level features use the block's last value minus its first; mid_return_bps uses the block sum."""
    nb = len(X) // BLOCK
    B = X[:nb * BLOCK].reshape(nb, BLOCK, X.shape[1])
    ch = B[:, -1, :] - B[:, 0, :]
    ch[:, 5] = B[:, :, 5].sum(1)
    return ch


def lag_mats(X: np.ndarray, starts: np.ndarray, scale: np.ndarray) -> np.ndarray:
    """16 x 16: rows = 10 features (+6 zero rows), columns = the window's 16 block changes, oldest first,
    each feature divided by its warm-up block-change sd. Only defined for starts on a block boundary."""
    ch = block_changes(X) / scale
    out = np.zeros((len(starts), SIDE, SIDE))
    for i, s in enumerate(starts):
        b = s // BLOCK
        out[i, :X.shape[1], :] = ch[b:b + WIN // BLOCK].T
    return out


def lag_scale(X: np.ndarray) -> np.ndarray:
    return block_changes(X[:WARMUP_END]).std(0) + 1e-12


def warmup_scale(X: np.ndarray) -> np.ndarray:
    # per-feature sd of window-demeaned values, from warm-up windows only (causal)
    st = windows(len(X), STRIDE, WARMUP_END)
    dev = np.concatenate([X[s:s + WIN] - X[s:s + WIN].mean(0) for s in st])
    return dev.std(0) + 1e-12


def to_kirk(m: np.ndarray) -> np.ndarray:
    r = render(m.astype(np.complex128))          # complex input, zero imaginary part
    assert out_of_range(r.samples) is None
    return r.samples.astype(np.complex64)


# ---------- baselines (no API) ----------

def b_univariate(X: np.ndarray, starts: np.ndarray) -> np.ndarray:
    """max over features of |z| of the window mean, z against warm-up window means (prices as returns)."""
    Y = X.copy()
    Y[1:, :2] = np.diff(X[:, :2], axis=0)        # price levels -> first differences
    Y[0, :2] = 0
    means = np.array([Y[s:s + WIN].mean(0) for s in starts])
    ref = np.array([Y[s:s + WIN].mean(0) for s in windows(len(X), STRIDE, WARMUP_END)])
    return np.max(np.abs((means - ref.mean(0)) / (ref.std(0) + 1e-12)), axis=1)


def b_dist_ref(M: np.ndarray, Mref: np.ndarray) -> np.ndarray:
    """Frobenius distance of each matrix from the mean warm-up matrix."""
    return np.linalg.norm(M - Mref.mean(0), axis=(1, 2))


def b_dist_lag(M: np.ndarray, lag: int = WIN // STRIDE) -> np.ndarray:
    """Frobenius distance from the matrix one full window earlier (non-overlapping); 0 for the first windows."""
    d = np.zeros(len(M))
    d[lag:] = np.linalg.norm(M[lag:] - M[:-lag], axis=(1, 2))
    return d


# ---------- Kirk ----------

def _record(resp, *a, **k):
    err = ""
    if "json" in resp.headers.get("Content-Type", ""):
        try:
            b = resp.json()
            err = str(b.get("error", "")) if isinstance(b, dict) else ""
        except ValueError:
            pass
    CALLS.append({"method": resp.request.method, "route": resp.request.path_url.split("?")[0],
                  "status": resp.status_code, "error": err})


def backend() -> RemoteBackend:
    s = requests.Session()
    s.headers["X-Kirk-Render"] = identity()
    s.hooks["response"].append(_record)
    return RemoteBackend(url=BASE_URL, api_key=os.environ["KAVARA_API_KEY"], key_header="X-Kavara-Key",
                         route_prefix="/v1/kirk-api", session=s, rate_limit_budget=60.0)


def kirk_run(train: np.ndarray, series: np.ndarray, seed: int, be: RemoteBackend, lr: float) -> dict:
    v = train.shape[-1]
    model = KirkModel(visible_nodes=v, enforce_purity=True, learning_rate=lr, random_state=seed,
                      batch_size=500, backend=be)
    warm = model.learn(train, outputs="entropy").entropy
    frozen = model.score(series, outputs="entropy").entropy
    online_model = model.fork()
    online = online_model.learn(series, outputs="entropy").entropy
    return {"warmup_learn": np.asarray(warm), "frozen": np.asarray(frozen), "online": np.asarray(online)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--lrs", type=float, nargs="+", default=[0.005, 0.0005, 0.00005],
                    help="first value is the pre-declared primary; the rest are sensitivity runs")
    ap.add_argument("--repeat", action="store_true", help="rerun corr/frozen to check reproducibility")
    a = ap.parse_args()

    d = np.load(a.data)
    X = d["X"]
    st = windows(len(X), STRIDE)
    st_warm = windows(len(X), 1, WARMUP_END)
    scale = warmup_scale(X)
    mats = {"lag": (lag_mats(X, windows(len(X), BLOCK, WARMUP_END), lag_scale(X)), lag_mats(X, st, lag_scale(X))),
            "corr": (corr_mats(X, st_warm), corr_mats(X, st)),
            "cov": (cov_mats(X, st_warm, scale), cov_mats(X, st, scale))}

    scores = {"window_start": st, "window_end": st + WIN - 1,
              "baseline_univariate_z": b_univariate(X, st)}
    for name, (Mw, M) in mats.items():
        scores[f"baseline_{name}_dist_ref"] = b_dist_ref(M, Mw)
        scores[f"baseline_{name}_dist_lag"] = b_dist_lag(M)

    be = backend()
    health = be._session.get(BASE_URL + "/v1/kirk-api/health", timeout=30).json()
    contract = be.contract()
    t0 = time.time()
    for name, (Mw, M) in mats.items():
        for lr in a.lrs:
            out = kirk_run(to_kirk(Mw), to_kirk(M), a.seed, be, lr)
            tag = f"kirk_{name}_lr{lr:g}"
            scores[f"{tag}_frozen"] = out["frozen"]
            scores[f"{tag}_online"] = out["online"]
            scores[f"{tag}_warmup_learn"] = out["warmup_learn"]
            print(tag, "done", round(time.time() - t0, 1), "s,", len(CALLS), "calls", flush=True)
    repro = None
    if a.repeat:
        lr0 = a.lrs[0]
        again = kirk_run(to_kirk(mats["lag"][0]), to_kirk(mats["lag"][1]), a.seed, backend(), lr0)
        tag = f"kirk_lag_lr{lr0:g}"
        repro = {"construction": "lag", "learning_rate": lr0,
                 "frozen_max_abs_diff": float(np.max(np.abs(again["frozen"] - scores[f"{tag}_frozen"]))),
                 "online_max_abs_diff": float(np.max(np.abs(again["online"] - scores[f"{tag}_online"])))}
        print("reproducibility:", repro)

    np.savez(a.out + ".scores.npz", **scores)
    run = {"data": a.data, "data_manifest": a.data.replace(".npz", ".manifest.json"),
           "window": WIN, "stride": STRIDE, "warmup_end": WARMUP_END,
           "n_windows": int(len(st)), "n_warmup_windows": int(len(st_warm)),
           "constructions": {"lag": "16x16: 10 feature rows (+6 zero rows) x 16 block changes of 16 steps (primary, Ulysses guide)",
                             "corr": "10x10 Pearson correlation over the window",
                             "cov": "10x10 covariance of window-demeaned features / warm-up sd"}, "renderer": identity(), "render_recipe": "rms-tanh/1",
           "kirk": {"visible_nodes": {"lag": 16, "corr": 10, "cov": 10}, "learning_rates": a.lrs,
                    "primary_learning_rate": a.lrs[0], "enforce_purity": True,
                    "random_state": a.seed, "outputs": "entropy", "modes": ["frozen", "online"]},
           "service_release_id": health.get("release_id"), "contract_release_id": contract.get("release_id"),
           "api_calls": len(CALLS), "non_200": [c for c in CALLS if c["status"] != 200],
           "reproducibility": repro, "elapsed_s": round(time.time() - t0, 1)}
    with open(a.out + ".run.json", "w") as f:
        json.dump(run, f, indent=2)
    print(json.dumps({k: run[k] for k in ("n_windows", "n_warmup_windows", "service_release_id",
                                          "api_calls", "non_200", "elapsed_s")}))


if __name__ == "__main__":
    main()
