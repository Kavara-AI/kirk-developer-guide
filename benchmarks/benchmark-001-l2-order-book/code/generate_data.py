"""Benchmark 001: synthetic L2 order-book stream with five regimes.

    python generate_data.py --out data/regimes.npz --seed 1
    python generate_data.py --out data/null.npz --seed 2 --null     # control: stable throughout

20,000 observations at 100 ms. Regimes change joint behaviour, not only means
(see data-generation.md). The regime label is stored for evaluation only.
"""
from __future__ import annotations

import argparse
import hashlib
import json

import numpy as np

GENERATOR_VERSION = "b001-gen/1"
N = 20_000
DT = 0.1
BOUNDARIES = [4000, 8000, 12000, 16000]
REGIMES = ["stable", "accumulation", "cancellation_heavy", "liquidity_shock", "recovery"]
FEATURES = ["best_bid", "best_ask", "bid_depth", "ask_depth", "spread", "mid_return_bps",
            "imbalance", "trade_rate", "cancel_rate", "rolling_vol_bps"]
VOL_WINDOW = 50  # observations in the causal rolling volatility

# Per-regime parameters. "Accumulation" ramps from stable to these values across the regime;
# "recovery" ramps from liquidity_shock back to stable. The others switch at the boundary.
P = {
    "stable": dict(bid_mu=1000.0, ask_mu=1000.0, common_w=0.5, idio_sd=0.15, bid_drift=0.0,
                   spread_base=0.02, spread_gamma=0.5, sigma_bps=0.6, beta_imb=0.6,
                   trade_base=20.0, trade_vol_w=0.8, cancel_base=40.0, cancel_trade_w=0.8,
                   spoof_on=0.0, spoof_size=0.0, vol_ar_sd=0.05),
    "accumulation": dict(bid_mu=1900.0, ask_mu=950.0, common_w=0.5, idio_sd=0.12, bid_drift=0.0,
                         spread_base=0.02, spread_gamma=0.5, sigma_bps=0.35, beta_imb=0.0,
                         trade_base=18.0, trade_vol_w=0.8, cancel_base=35.0, cancel_trade_w=0.8,
                         spoof_on=0.0, spoof_size=0.0, vol_ar_sd=0.05),
    "cancellation_heavy": dict(bid_mu=1000.0, ask_mu=1000.0, common_w=0.5, idio_sd=0.15, bid_drift=0.0,
                               spread_base=0.02, spread_gamma=0.5, sigma_bps=0.6, beta_imb=0.6,
                               trade_base=9.0, trade_vol_w=0.8, cancel_base=150.0, cancel_trade_w=0.0,
                               spoof_on=0.08, spoof_size=1.2, vol_ar_sd=0.05),
    "liquidity_shock": dict(bid_mu=300.0, ask_mu=280.0, common_w=1.2, idio_sd=0.1, bid_drift=0.0,
                            spread_base=0.08, spread_gamma=1.5, sigma_bps=2.0, beta_imb=0.6,
                            trade_base=45.0, trade_vol_w=1.8, cancel_base=60.0, cancel_trade_w=0.8,
                            spoof_on=0.0, spoof_size=0.0, vol_ar_sd=0.12),
}
P["recovery"] = P["stable"]  # end point of the recovery ramp


def params_at(t: int, null: bool) -> dict:
    if null:
        return P["stable"]
    r = int(np.searchsorted(BOUNDARIES, t, side="right"))
    name = REGIMES[r]
    if name == "accumulation":
        a = (t - 4000) / 4000.0
        return {k: (1 - a) * P["stable"][k] + a * P["accumulation"][k] for k in P["stable"]}
    if name == "recovery":
        a = (t - 16000) / 4000.0
        return {k: (1 - a) * P["liquidity_shock"][k] + a * P["stable"][k] for k in P["stable"]}
    return P[name]


def generate(seed: int, null: bool = False) -> dict:
    rng = np.random.default_rng(seed)
    X = np.zeros((N, len(FEATURES)))
    regime = np.zeros(N, dtype=np.int8)
    D = 0.0          # common liquidity factor, AR(1)
    eb = ea = 0.0    # side-specific depth noise, AR(1)
    v = 0.0          # volatility latent, AR(1)
    tl = 0.0         # trade-intensity noise, AR(1)
    spoof = 0        # spoofing burst state (0/1), Markov
    spoof_side = 1
    pending_cancel = 0.0
    mid = 100.0
    imb_prev = 0.0
    rets = np.zeros(N)
    for t in range(N):
        p = params_at(t, null)
        regime[t] = 0 if null else int(np.searchsorted(BOUNDARIES, t, side="right"))
        D = 0.98 * D + 0.2 * rng.standard_normal()
        eb = 0.95 * eb + p["idio_sd"] * rng.standard_normal()
        ea = 0.95 * ea + p["idio_sd"] * rng.standard_normal()
        v = 0.99 * v + p["vol_ar_sd"] * rng.standard_normal()
        tl = 0.9 * tl + 0.15 * rng.standard_normal()
        # spoofing: transient displayed depth on one side, cancelled a few steps later
        if spoof == 0 and rng.random() < p["spoof_on"]:
            spoof, spoof_side = 1, (1 if rng.random() < 0.5 else -1)
        elif spoof == 1 and rng.random() < 0.3:
            spoof = 0
            pending_cancel += p["spoof_size"]
        bid = p["bid_mu"] * np.exp(p["common_w"] * D + eb + (p["spoof_size"] * spoof if spoof_side > 0 else 0))
        ask = p["ask_mu"] * np.exp(p["common_w"] * D + ea + (p["spoof_size"] * spoof if spoof_side < 0 else 0))
        imb = (bid - ask) / (bid + ask)
        sigma = p["sigma_bps"] * np.exp(v)
        r_bps = p["beta_imb"] * imb_prev * sigma + sigma * rng.standard_normal()
        mid *= 1 + r_bps * 1e-4
        depth_ratio = 2000.0 / (bid + ask)
        spread = p["spread_base"] * depth_ratio ** p["spread_gamma"] * np.exp(0.1 * rng.standard_normal())
        spread = max(0.01, round(spread / 0.01) * 0.01)  # tick size 0.01
        trade = p["trade_base"] * np.exp(p["trade_vol_w"] * v + tl)
        cancel = p["cancel_base"] * np.exp(p["cancel_trade_w"] * (np.log(trade / p["trade_base"]))
                                           + 0.2 * rng.standard_normal() + pending_cancel)
        pending_cancel *= 0.5
        rets[t] = r_bps
        lo = max(0, t - VOL_WINDOW + 1)
        vol = float(np.std(rets[lo:t + 1])) if t > 0 else 0.0
        X[t] = [mid - spread / 2, mid + spread / 2, bid, ask, spread, r_bps, imb, trade, cancel, vol]
        imb_prev = imb
    return {"X": X, "regime": regime}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--null", action="store_true", help="stable regime throughout (control stream)")
    a = ap.parse_args()
    d = generate(a.seed, a.null)
    np.savez(a.out, X=d["X"], regime=d["regime"], features=np.array(FEATURES))
    digest = hashlib.sha256(d["X"].tobytes() + d["regime"].tobytes()).hexdigest()
    manifest = {"generator_version": GENERATOR_VERSION, "seed": a.seed, "null_control": a.null,
                "n": N, "interval_s": DT, "boundaries": [] if a.null else BOUNDARIES,
                "regimes": ["stable"] if a.null else REGIMES, "features": FEATURES,
                "feature_units": {"best_bid": "price", "best_ask": "price", "bid_depth": "shares",
                                  "ask_depth": "shares", "spread": "price (tick 0.01)",
                                  "mid_return_bps": "basis points per step", "imbalance": "ratio [-1,1]",
                                  "trade_rate": "events/s (continuous intensity)",
                                  "cancel_rate": "events/s (continuous intensity)",
                                  "rolling_vol_bps": "std of returns over 50 steps, causal"},
                "parameters": P, "clipping": "spread floored at one tick (0.01)",
                "sha256_X_regime": digest}
    with open(a.out.replace(".npz", ".manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(a.out, digest)


if __name__ == "__main__":
    main()
