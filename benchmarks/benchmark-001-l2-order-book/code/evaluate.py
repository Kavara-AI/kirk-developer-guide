"""Benchmark 001: evaluate every score series with one detector and the metrics in expected-results.md.

    python evaluate.py --results results --data data/regimes.npz

Fixed before looking at the scores:
  * Evaluation windows: stride-16 windows ending at or after observation 2000 (after the warm-up).
  * Detector (identical for every method, causal): dev_t = s_t - mean(s_{t-16..t-1}); alarm when
    |dev_t| > T, then 16 windows (256 obs, one full window) of refractory. T is the 99.5th percentile
    of |dev_t| on the null (no-change) control stream, per method.
  * Event tolerance: an alarm detects boundary b if its window ends in [b, b + 768) observations
    (the window has turned over fully plus 512 observations = 51.2 s). Detection delay = end - b.
  * False alarm: any alarm outside every tolerance zone. Reported per 1,000 evaluation windows,
    on the regime stream and on the null stream.
  * Separation: eta^2 (share of score variance explained by regime) and Cohen's d between adjacent
    regimes, both on windows lying entirely inside one regime.
  * Recovery: (mean score over the last 64 pure recovery windows - stable mean) / stable sd.
Primary Kirk configuration (pre-declared): lag construction, learning rate 0.005, online mode.

POST-HOC additions (added after first looking at results; reported separately, labelled post-hoc):
  * detector "self": T is the 99.5th percentile of |dev_t| on the same stream's own known-stable
    windows ending in [2000, 4000). Reason: independently trained Kirk models produce different score
    scales on the same kind of data, so a threshold from the null stream's model does not transfer.
    The null stream's false-alarm rate is computed the same way on the null stream.
  * eta2_minus_null: eta^2 of (score on regime stream - score on null stream), window by window.
    Reason: online Kirk entropy trends upward on the null stream too, and regimes are in time order,
    so plain eta^2 rewards any trend.
"""
from __future__ import annotations

import argparse
import json

import numpy as np

BOUNDARIES = [4000, 8000, 12000, 16000]
EDGES = [0] + BOUNDARIES + [20000]
NAMES = ["stable", "accumulation", "cancellation_heavy", "liquidity_shock", "recovery"]
LOOKBACK, REFRACTORY, TOL, EVAL_FROM, Q = 16, 16, 768, 2000, 99.5
PRIMARY = "kirk_lag_lr0.005_online"


def devs(s: np.ndarray) -> np.ndarray:
    d = np.full(len(s), np.nan)
    c = np.concatenate([[0.0], np.cumsum(s)])
    for t in range(LOOKBACK, len(s)):
        d[t] = s[t] - (c[t] - c[t - LOOKBACK]) / LOOKBACK
    return d


def alarms(dev: np.ndarray, ends: np.ndarray, T: float) -> list[int]:
    out, last = [], -10 ** 9
    for t in range(len(dev)):
        if ends[t] < EVAL_FROM or np.isnan(dev[t]):
            continue
        if abs(dev[t]) > T and t - last >= REFRACTORY:
            out.append(t)
            last = t
    return out


def eta_sq(s, starts, ends):
    ev = ends >= EVAL_FROM
    reg = np.full(len(s), -1)
    for k in range(5):
        reg[(starts >= EDGES[k]) & (ends < EDGES[k + 1]) & ev] = k
    groups = [s[reg == k] for k in range(5)]
    allp = s[reg >= 0]
    return float(sum(len(g) * (g.mean() - allp.mean()) ** 2 for g in groups) / (((allp - allp.mean()) ** 2).sum() + 1e-300))


def evaluate(s, s0, starts, ends, calib="null"):
    s, s0 = np.asarray(s, float), np.asarray(s0, float)
    ev = ends >= EVAL_FROM
    d, d0 = devs(s), devs(s0)
    if calib == "null":
        T = T0 = float(np.nanpercentile(np.abs(d0[ev]), Q))
    else:  # "self": each stream calibrated on its own known-stable windows before the first boundary
        cal = ev & (ends < BOUNDARIES[0])
        T = float(np.nanpercentile(np.abs(d[cal]), Q))
        T0 = float(np.nanpercentile(np.abs(d0[cal]), Q))
    a = alarms(d, ends, T)
    a0 = alarms(d0, ends, T0)
    det = {}
    hit = set()
    for b in BOUNDARIES:
        m = [t for t in a if b <= ends[t] < b + TOL]
        det[str(b)] = None if not m else round(float(ends[m[0]] - b) * 0.1, 1)  # delay in seconds
        hit.update(m)
    fa = [t for t in a if t not in hit]
    n_ev = int(ev.sum())
    # separation on pure windows
    reg = np.full(len(s), -1)
    for k in range(5):
        reg[(starts >= EDGES[k]) & (ends < EDGES[k + 1]) & ev] = k
    groups = [s[reg == k] for k in range(5)]
    allp = s[reg >= 0]
    eta2 = float(sum(len(g) * (g.mean() - allp.mean()) ** 2 for g in groups) / (((allp - allp.mean()) ** 2).sum() + 1e-300))
    dd = []
    for k in range(4):
        g1, g2 = groups[k], groups[k + 1]
        sp = np.sqrt(((len(g1) - 1) * g1.var(ddof=1) + (len(g2) - 1) * g2.var(ddof=1)) / (len(g1) + len(g2) - 2))
        dd.append(float((g2.mean() - g1.mean()) / (sp + 1e-300)))
    st = groups[0]
    rec = float((groups[4][-64:].mean() - st.mean()) / (st.std(ddof=1) + 1e-300))
    return {"detector": calib, "threshold": T, "eta2_minus_null": round(eta_sq(s - s0, starts, ends), 3),
            "boundaries_detected": sum(v is not None for v in det.values()),
            "delay_s": det, "false_alarms_per_1000": round(1000 * len(fa) / n_ev, 2),
            "null_false_alarms_per_1000": round(1000 * len(a0) / n_ev, 2),
            "eta2": round(eta2, 3), "adjacent_cohens_d": [round(x, 2) for x in dd],
            "min_abs_adjacent_d": round(min(abs(x) for x in dd), 2),
            "recovery_vs_stable_sd": round(rec, 2), "alarm_window_ends": [int(ends[t]) for t in a]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--data", default="data/regimes.npz")
    ap.add_argument("--suffix", default="", help="score files regimes<suffix> / null<suffix>")
    a = ap.parse_args()
    R = np.load(f"{a.results}/regimes{a.suffix}.scores.npz")
    N0 = np.load(f"{a.results}/null{a.suffix}.scores.npz")
    starts, ends = R["window_start"], R["window_end"]
    methods = [k for k in R.files if k.startswith(("kirk_", "baseline_")) and not k.endswith("warmup_learn")]
    res = {c: {m: evaluate(R[m], N0[m], starts, ends, c) for m in methods} for c in ("null", "self")}
    with open(f"{a.results}/metrics{a.suffix}.json", "w") as f:
        json.dump({"primary": PRIMARY, "config": {"lookback": LOOKBACK, "refractory": REFRACTORY,
                   "tolerance_obs": TOL, "eval_from_obs": EVAL_FROM, "threshold_quantile": Q},
                   "preregistered_detector_null_calibrated": res["null"],
                   "posthoc_detector_self_calibrated": res["self"]}, f, indent=2)
    for c, label in (("null", "PRE-REGISTERED detector (threshold from null stream)"),
                     ("self", "POST-HOC detector (threshold from own pre-boundary stable windows)")):
        print("\n" + label)
        rows = sorted(res[c].items(), key=lambda kv: (-kv[1]["boundaries_detected"], kv[1]["false_alarms_per_1000"]))
        print(f"{'method':34s} {'hit':>3s} {'FA/1k':>6s} {'nullFA':>6s} {'eta2':>5s} {'eta2-N':>6s} {'min|d|':>6s} {'recov':>6s}  delays_s")
        for m, r in rows:
            print(f"{m:34s} {r['boundaries_detected']:>3d} {r['false_alarms_per_1000']:>6.2f} "
                  f"{r['null_false_alarms_per_1000']:>6.2f} {r['eta2']:>5.2f} {r['eta2_minus_null']:>6.2f} "
                  f"{r['min_abs_adjacent_d']:>6.2f} {r['recovery_vs_stable_sd']:>6.2f}  {list(r['delay_s'].values())}")


if __name__ == "__main__":
    main()
