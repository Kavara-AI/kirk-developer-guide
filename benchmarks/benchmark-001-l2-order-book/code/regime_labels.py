"""Benchmark 001, read-out 2: label regimes from each score series with an unsupervised HMM.

    python regime_labels.py            # uses results/{regimes,null}{,_c1,_c2,_c3}.scores.npz

No API calls: it reuses the stored scores. The Kavara usage guide suggests passing Kirk's entropy to a
hidden Markov model for state classification; this tests that read-out against the same read-out on
the baselines.

Fixed before looking at any result:
  * Evaluation windows: stride-16 windows ending at or after observation 2000. True label = regime at
    the window's last observation (used only for scoring).
  * Transform (every method alike): rank -> standard normal quantile, so scale and heavy tails
    do not decide the result.
  * Model: Gaussian HMM, 5 states (the number of regimes is assumed known), diagonal covariance,
    200 EM iterations, 10 restarts (random_state 0-9), keep the best log-likelihood. Viterbi path.
  * Metrics: adjusted Rand index (ARI, primary), normalised mutual information, accuracy after
    optimal one-to-one matching of states to regimes, and the number of state switches (truth: 4).
  * Trend control: the same HMM on the null stream's scores, scored against the regime stream's
    labels (same timing). A method that only reads time scores well here too; a regime reader
    should not, because the null stream has no regimes.
  * Primary comparison: kirk_lag_lr5e-05_frozen (named before the confirmation seeds) against every
    baseline, on all four seed pairs. Complementarity test: a 2-D HMM on
    [kirk_lag_lr5e-05_frozen, baseline_univariate_z] against baseline_univariate_z alone.
"""
from __future__ import annotations

import json
import warnings

import numpy as np
from hmmlearn.hmm import GaussianHMM
from scipy.optimize import linear_sum_assignment
from scipy.stats import norm, rankdata
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

warnings.filterwarnings("ignore")
EDGES = [0, 4000, 8000, 12000, 16000, 20000]
EVAL_FROM, K, RESTARTS = 2000, 5, 10
SEEDS = ["", "_c1", "_c2", "_c3"]
NAMED = "kirk_lag_lr5e-05_frozen"
COMBO = ("combo_kirk_named+univariate_z", [NAMED, "baseline_univariate_z"])


def gauss(x):
    return norm.ppf((rankdata(x) - 0.5) / len(x))


def fit_hmm(Z):
    best, bl = None, -np.inf
    for rs in range(RESTARTS):
        m = GaussianHMM(n_components=K, covariance_type="diag", n_iter=200, random_state=rs)
        try:
            m.fit(Z)
            ll = m.score(Z)
        except Exception:
            continue  # try next restart
        if np.isfinite(ll) and ll > bl:
            best, bl = m, ll
    if best is None:
        raise RuntimeError("all HMM restarts failed")
    return best.predict(Z)


def matched_acc(y, s):
    C = np.zeros((K, K))
    for a, b in zip(y, s):
        C[a, b] += 1
    r, c = linear_sum_assignment(-C)
    return C[r, c].sum() / len(y)


def score(y, s):
    return {"ari": round(adjusted_rand_score(y, s), 3), "nmi": round(normalized_mutual_info_score(y, s), 3),
            "acc": round(matched_acc(y, s), 3), "switches": int((np.diff(s) != 0).sum())}


def series(R, name, ev):
    keys = COMBO[1] if name == COMBO[0] else [name]
    return np.column_stack([gauss(np.asarray(R[k], float)[ev]) for k in keys])


def main():
    out = {}
    for sfx in SEEDS:
        R = np.load(f"results/regimes{sfx}.scores.npz")
        N = np.load(f"results/null{sfx}.scores.npz")
        ends = R["window_end"]
        ev = ends >= EVAL_FROM
        y = np.searchsorted(EDGES[1:-1], ends[ev], side="right")
        methods = [k for k in R.files if k.startswith(("kirk_", "baseline_")) and not k.endswith("warmup_learn")]
        methods.append(COMBO[0])
        out[sfx or "_sel"] = {m: {"regimes": score(y, fit_hmm(series(R, m, ev))),
                                  "null_trend_control": score(y, fit_hmm(series(N, m, ev)))} for m in methods}
        print("done", sfx or "selection", flush=True)
    with open("results/regime_labels.json", "w") as f:
        json.dump(out, f, indent=2)

    # summary over the methods present on all four seeds
    common = set.intersection(*[set(v) for v in out.values()])
    rows = []
    for m in common:
        a = [out[s][m]["regimes"]["ari"] for s in out]
        c = [out[s][m]["null_trend_control"]["ari"] for s in out]
        acc = [out[s][m]["regimes"]["acc"] for s in out]
        sw = [out[s][m]["regimes"]["switches"] for s in out]
        rows.append((m, np.mean(a), min(a), max(a), np.mean(c), np.mean(acc), np.mean(sw)))
    rows.sort(key=lambda r: -r[1])
    lines = ["| Method | ARI mean (min–max), 4 seeds | Trend control ARI (null stream) | Matched accuracy | State switches (truth 4) |",
             "|---|---|---:|---:|---:|"]
    for m, am, lo, hi, cm, acc, sw in rows:
        lines.append(f"| `{m}` | {am:.2f} ({lo:.2f}–{hi:.2f}) | {cm:.2f} | {acc:.2f} | {sw:.0f} |")
    open("results/regime_labels_table.md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    sel = out["_sel"]
    kirk = sorted(((m, v["regimes"]["ari"], v["null_trend_control"]["ari"]) for m, v in sel.items()
                   if m.startswith("kirk_")), key=lambda r: -r[1])
    print("\nselection seed, all Kirk configurations (ARI, trend-control ARI):")
    for m, a, c in kirk:
        print(f"  {m:32s} {a:5.2f} {c:5.2f}")


if __name__ == "__main__":
    main()
