"""Benchmark 001 figure: features, true regimes, Kirk and baseline scores, alarms (post-hoc detector)."""
import json, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sfx = sys.argv[1] if len(sys.argv) > 1 else ""
d = np.load(f"data/regimes{sfx}.npz"); X, f = d["X"], list(d["features"])
R = np.load(f"results/regimes{sfx}.scores.npz"); ends = R["window_end"]
M = json.load(open(f"results/metrics{sfx}.json"))["posthoc_detector_self_calibrated"]
B = [4000, 8000, 12000, 16000]
names = ["stable", "accumulation", "cancel-heavy", "liq. shock", "recovery"]
shade = ["#f2f2f2", "#e3edf7", "#f7ece3", "#f7e3e3", "#e8f3e6"]
series = [("kirk_lag_lr0.005_online", "Kirk lag, online, lr 0.005 (pre-declared primary)"),
          ("kirk_lag_lr5e-05_frozen", "Kirk lag, frozen, lr 0.00005"),
          ("baseline_univariate_z", "Baseline: per-feature z of window mean"),
          ("baseline_lag_dist_lag", "Baseline: change vs. one window earlier")]
series = [(k, l) for k, l in series if k in R.files]
fig, ax = plt.subplots(2 + len(series), 1, figsize=(11, 2.0 * (2 + len(series))), sharex=True)
t = np.arange(len(X))
def regimes(a):
    e = [0] + B + [20000]
    for k in range(5):
        a.axvspan(e[k] * 0.1, e[k + 1] * 0.1, color=shade[k], lw=0)
    for b in B:
        a.axvline(b * 0.1, color="#888", lw=0.8, ls="--")
regimes(ax[0])
for i, c in [(2, "#1f5fa8"), (3, "#c4572a")]:
    ax[0].plot(t * 0.1, X[:, i] / X[:2000, i].mean(), lw=0.4, color=c, label=f[i] + " (rel.)")
ax[0].set_yscale("log"); ax[0].legend(loc="upper left", fontsize=7, frameon=False)
for k in range(5):
    ax[0].text(([0] + B)[k] * 0.1 + 20, ax[0].get_ylim()[1] * 0.6, names[k], fontsize=8)
regimes(ax[1])
for i, c in [(8, "#7a3fa0"), (7, "#2f8f4e"), (4, "#444")]:
    ax[1].plot(t * 0.1, X[:, i] / np.median(X[:2000, i]), lw=0.4, color=c, label=f[i] + " (rel.)")
ax[1].set_yscale("log"); ax[1].legend(loc="upper left", fontsize=7, frameon=False)
for a, (k, lab) in zip(ax[2:], series):
    regimes(a)
    a.plot(ends * 0.1, R[k], lw=0.8, color="#222")
    for e in M[k]["alarm_window_ends"]:
        a.axvline(e * 0.1, color="#d62728", lw=1.2, alpha=0.8)
    m = M[k]
    a.set_title(f"{lab} — boundaries hit {m['boundaries_detected']}/4, false alarms {m['false_alarms_per_1000']}/1k windows, "
                f"trend-controlled η² {m['eta2_minus_null']}", fontsize=8, loc="left")
    if "univariate" in k or "dist" in k:
        a.set_yscale("symlog")
ax[-1].set_xlabel("time (s); red lines = detector alarms (post-hoc self-calibrated detector)")
fig.suptitle(f"Benchmark 001 (synthetic L2 order book), seed set '{sfx or 'original'}' — Kirk via api.kavara.ai", fontsize=10)
fig.tight_layout()
fig.savefig(f"results/benchmark001{sfx}.png", dpi=110)
print(f"results/benchmark001{sfx}.png")
