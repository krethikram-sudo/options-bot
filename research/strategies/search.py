"""Iterative search through 100 strategies.

The plan progresses in phases:

  Phase 1 (1-15)   : Baselines — one of each major family
  Phase 2 (16-30)  : Vary lookback on top-3 baseline families
  Phase 3 (31-45)  : Vary top-N on best family
  Phase 4 (46-55)  : Vary rebalance frequency
  Phase 5 (56-65)  : Vary universe
  Phase 6 (66-75)  : Add filters/overlays
  Phase 7 (76-85)  : Weight schemes (equal vs vol)
  Phase 8 (86-95)  : Hybrid signals
  Phase 9 (96-100) : Refinements on absolute champion

Each phase examines history of prior results and picks parameters informed by
what worked. Champion (highest Sharpe) is tracked and reported.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from tabulate import tabulate

from research.strategies.engine import Strategy, run_strategy
from research.strategies.framework import BacktestResult

OUT_DIR = Path(__file__).resolve().parent
RESULTS_CSV = OUT_DIR / "iter_results.csv"
LOG_PATH = OUT_DIR / "iter_log.jsonl"
CHAMPIONS_PATH = OUT_DIR / "champions.json"


# ---- 100-strategy plan ----

def _phase1_baselines() -> list[Strategy]:
    """1-15: one strategy per family at default params."""
    return [
        Strategy(1, "B01_buy_hold_spy", "buy_hold", "Passive market baseline",
                 {"signal": "buy_hold", "ticker": "SPY"}),
        Strategy(2, "B02_buy_hold_qqq", "buy_hold", "Passive Nasdaq baseline",
                 {"signal": "buy_hold", "ticker": "QQQ"}),
        Strategy(3, "B03_buy_hold_nvda", "buy_hold", "Single-name AI champion",
                 {"signal": "buy_hold", "ticker": "NVDA"}),
        Strategy(4, "B04_ew_ai9", "equal_weight", "Equal-weight AI infra basket",
                 {"signal": "equal_weight", "universe": "ai9", "rebalance": "monthly"}),
        Strategy(5, "B05_ew_full_chain", "equal_weight", "Equal-weight full AI value chain",
                 {"signal": "equal_weight", "universe": "ai_full_chain", "rebalance": "monthly"}),
        Strategy(6, "B06_xs_mom_ai9", "xs_momentum", "12-1 momentum within AI-9",
                 {"signal": "xs_momentum", "universe": "ai9", "lookback": 252, "skip": 21,
                  "top_n": 3, "rebalance": "monthly"}),
        Strategy(7, "B07_xs_mom_universe", "xs_momentum", "12-1 momentum across full chain",
                 {"signal": "xs_momentum", "universe": "ai_full_chain", "lookback": 252,
                  "skip": 21, "top_n": 5, "rebalance": "monthly"}),
        Strategy(8, "B08_quality_trend", "xs_quality_trend", "Quality (Sharpe) + 6mo trend composite",
                 {"signal": "xs_quality_trend", "universe": "ai9", "sharpe_window": 60,
                  "trend_window": 126, "top_n": 4, "rebalance": "monthly"}),
        Strategy(9, "B09_lowvol_tilt", "lowvol_tilt", "Low-vol tilt within AI-9",
                 {"signal": "lowvol_tilt", "universe": "ai9", "vol_window": 60,
                  "top_n": 4, "rebalance": "monthly"}),
        Strategy(10, "B10_xs_meanrev", "xs_meanrev", "Buy worst-performing recently",
                 {"signal": "xs_meanrev", "universe": "ai9", "lookback": 21,
                  "top_n": 3, "rebalance": "monthly"}),
        Strategy(11, "B11_ts_voltgt", "ts_momentum_voltgt", "Vol-targeted single-name trend",
                 {"signal": "ts_momentum_voltgt", "universe": "ai9", "lookback": 252,
                  "skip": 21, "target_vol": 0.15, "rebalance": "weekly"}),
        Strategy(12, "B12_dual_momentum", "dual_momentum", "Asset-class rotation eq/bond/gold",
                 {"signal": "dual_momentum", "lookback": 126, "rebalance": "monthly"}),
        Strategy(13, "B13_ew_power_infra", "equal_weight", "Power infra basket",
                 {"signal": "equal_weight", "universe": ["VRT", "GEV", "CEG", "ETN", "HUBB"],
                  "rebalance": "monthly"}),
        Strategy(14, "B14_ew_networking", "equal_weight", "Networking-optical basket",
                 {"signal": "equal_weight", "universe": ["ANET", "LITE", "CRDO", "COHR", "CIEN"],
                  "rebalance": "monthly"}),
        Strategy(15, "B15_ew_wfe", "equal_weight", "Wafer fab equipment basket",
                 {"signal": "equal_weight", "universe": ["ASML", "AMAT", "KLAC", "LRCX", "TER"],
                  "rebalance": "monthly"}),
    ]


def _phase2_lookback_sweep(history: list["IterationResult"]) -> list[Strategy]:
    """16-30: vary lookback on top-3 momentum-family baselines."""
    out = []
    sid = 16
    for lb in [60, 90, 126, 200, 300]:
        out.append(Strategy(sid, f"P2_xs_mom_ai9_lb{lb}", "xs_momentum",
                            f"Vary lookback={lb} on AI-9 xs momentum",
                            {"signal": "xs_momentum", "universe": "ai9", "lookback": lb,
                             "skip": 21, "top_n": 3, "rebalance": "monthly"}))
        sid += 1
    for lb in [60, 90, 126, 200, 300]:
        out.append(Strategy(sid, f"P2_xs_mom_uni_lb{lb}", "xs_momentum",
                            f"Vary lookback={lb} on full-chain momentum",
                            {"signal": "xs_momentum", "universe": "ai_full_chain", "lookback": lb,
                             "skip": 21, "top_n": 5, "rebalance": "monthly"}))
        sid += 1
    for lb in [60, 90, 126, 200, 300]:
        out.append(Strategy(sid, f"P2_ts_voltgt_lb{lb}", "ts_momentum_voltgt",
                            f"Vary lookback={lb} on TS vol-target trend",
                            {"signal": "ts_momentum_voltgt", "universe": "ai9", "lookback": lb,
                             "skip": 21, "target_vol": 0.15, "rebalance": "weekly"}))
        sid += 1
    return out


def _phase3_top_n(history: list["IterationResult"], champion: "IterationResult") -> list[Strategy]:
    """31-45: vary top_n on best 3 families seen so far."""
    out = []
    sid = 31
    # Use champion's family as primary target
    fams_tried = {}
    for r in history:
        fams_tried.setdefault(r.config.get("signal"), []).append(r)
    fam_avg_sharpe = {f: np.mean([h.metrics.get("sharpe", 0) for h in hs]) for f, hs in fams_tried.items()}
    top_fams = sorted(fam_avg_sharpe.items(), key=lambda x: x[1], reverse=True)[:3]

    for fam, _ in top_fams:
        # Only top-N parameterizable signals
        if fam not in ("xs_momentum", "xs_quality_trend", "lowvol_tilt", "xs_meanrev"):
            continue
        # find best lookback for that family from history
        best_h = max((h for h in fams_tried[fam] if h.metrics.get("n_days", 0) > 100),
                     key=lambda h: h.metrics.get("sharpe", -99), default=None)
        if best_h is None:
            continue
        base_cfg = dict(best_h.config)
        for n in [1, 2, 3, 5, 7]:
            cfg = dict(base_cfg)
            cfg["top_n"] = n
            out.append(Strategy(sid, f"P3_{fam}_topN{n}", fam,
                                f"Top-N={n} on best {fam} setup", cfg))
            sid += 1
    return out[:15]


def _phase4_rebalance(champion: "IterationResult") -> list[Strategy]:
    """46-55: vary rebalance frequency on champion."""
    out = []
    sid = 46
    base_cfg = dict(champion.config)
    for freq in ["daily", "weekly", "biweekly", "monthly", "quarterly"]:
        cfg = dict(base_cfg)
        cfg["rebalance"] = freq
        out.append(Strategy(sid, f"P4_champ_{freq}", "rebalance_sweep",
                            f"Rebalance={freq} on champion", cfg))
        sid += 1
    base2 = dict(base_cfg)
    base2["rebalance"] = "weekly"
    for skip in [0, 5, 10, 21, 42]:
        cfg = dict(base2)
        cfg["skip"] = skip
        out.append(Strategy(sid, f"P4_champ_skip{skip}", "skip_sweep",
                            f"Skip={skip} on champion", cfg))
        sid += 1
    return out


def _phase5_universe(champion: "IterationResult") -> list[Strategy]:
    """56-65: vary universe on champion."""
    out = []
    sid = 56
    base_cfg = dict(champion.config)
    for uni in ["ai9", "ai_silicon_only", "ai_full_chain", "ai_infra_plus_power",
                "semi_equipment", "networking", "hyperscalers", "ai_software",
                "sector_etfs", "factor_etfs"]:
        cfg = dict(base_cfg)
        cfg["universe"] = uni
        out.append(Strategy(sid, f"P5_champ_uni_{uni}", "universe_sweep",
                            f"Universe={uni} on champion", cfg))
        sid += 1
    return out


def _phase6_filters(champion: "IterationResult") -> list[Strategy]:
    """66-75: add filters/overlays on champion."""
    out = []
    sid = 66
    base_cfg = dict(champion.config)
    variants = [
        ("vix_gate", {"vix_gate": True}),
        ("sma_gate_200", {"sma_gate": True, "sma_window": 200}),
        ("sma_gate_100", {"sma_gate": True, "sma_window": 100}),
        ("vix_and_sma", {"vix_gate": True, "sma_gate": True, "sma_window": 200}),
        ("cost_2bps", {"cost_bps": 2}),
        ("cost_10bps", {"cost_bps": 10}),
        ("cost_20bps", {"cost_bps": 20}),
        ("cost_50bps", {"cost_bps": 50}),
        ("vix_gate_30", {"vix_gate": True, "vix_lookback": 30}),
        ("vix_gate_120", {"vix_gate": True, "vix_lookback": 120}),
    ]
    for label, override in variants:
        cfg = dict(base_cfg)
        cfg.update(override)
        out.append(Strategy(sid, f"P6_champ_{label}", "filter_sweep",
                            f"{label} on champion", cfg))
        sid += 1
    return out


def _phase7_weight_method(champion: "IterationResult") -> list[Strategy]:
    """76-85: weight method on champion + tweaks."""
    out = []
    sid = 76
    base_cfg = dict(champion.config)
    for method in ["equal", "vol"]:
        for n in [3, 5, 7, 10]:
            cfg = dict(base_cfg)
            cfg["weight_method"] = method
            cfg["top_n"] = n
            out.append(Strategy(sid, f"P7_champ_{method}_n{n}", "weight_sweep",
                                f"Weight={method} top_n={n}", cfg))
            sid += 1
            if sid > 85:
                break
        if sid > 85:
            break
    return out[:10]


def _phase8_hybrid(champion: "IterationResult", history: list["IterationResult"]) -> list[Strategy]:
    """86-95: try alternate signal types + dual_momentum variants."""
    out = []
    sid = 86
    # dual momentum variants
    sleeve_options = [
        {"equity": "QQQ", "bonds": "TLT"},
        {"equity": "QQQ", "bonds": "TLT", "gold": "GLD"},
        {"equity": "SPY", "bonds": "IEF", "gold": "GLD"},
        {"equity": "SMH", "bonds": "TLT", "gold": "GLD"},
        {"equity": "MTUM", "bonds": "TLT", "gold": "GLD"},
    ]
    for sl in sleeve_options:
        out.append(Strategy(sid, f"P8_dual_mom_{'_'.join(sl.values())}", "dual_momentum",
                            f"Dual momentum {sl}",
                            {"signal": "dual_momentum", "sleeves": sl, "lookback": 126,
                             "rebalance": "monthly"}))
        sid += 1
    # combine quality+trend with different windows
    for sw, tw in [(30, 63), (60, 126), (90, 252), (120, 200), (60, 60)]:
        out.append(Strategy(sid, f"P8_qt_sw{sw}_tw{tw}", "xs_quality_trend",
                            f"Quality+trend {sw}/{tw} windows",
                            {"signal": "xs_quality_trend", "universe": "ai9",
                             "sharpe_window": sw, "trend_window": tw,
                             "top_n": 4, "rebalance": "monthly"}))
        sid += 1
    return out


def _phase9_refine(champion: "IterationResult") -> list[Strategy]:
    """96-100: refinements around the champion."""
    out = []
    sid = 96
    base_cfg = dict(champion.config)
    refinements = [
        ("ref_topn_2", {"top_n": 2}),
        ("ref_topn_4", {"top_n": 4}),
        ("ref_skip_5", {"skip": 5}),
        ("ref_lookback_180", {"lookback": 180}),
        ("ref_combo", {"sma_gate": True, "vix_gate": True, "top_n": 3}),
    ]
    for label, override in refinements:
        cfg = dict(base_cfg)
        cfg.update(override)
        out.append(Strategy(sid, f"P9_{label}", "refinement", label, cfg))
        sid += 1
    return out


# ---- iteration loop ----

@dataclass
class IterationResult:
    iteration: int
    name: str
    family: str
    rationale: str
    config: dict
    metrics: dict
    duration_sec: float
    notes: str = ""


def _diagnose(prev_best: float, this_sharpe: float, this_metrics: dict) -> str:
    if this_sharpe > prev_best:
        return f"NEW CHAMPION (+{(this_sharpe - prev_best):.2f} Sharpe)"
    delta = this_sharpe - prev_best
    if this_metrics.get("n_days", 0) < 100:
        return f"weak: too little data ({this_metrics.get('n_days', 0)} days)"
    if this_metrics.get("max_dd", 0) < -0.4:
        return f"weak: deep drawdown {this_metrics['max_dd']*100:.0f}%"
    if abs(delta) < 0.05:
        return f"comparable to champion ({delta:+.2f} Sharpe)"
    return f"underperforms champion ({delta:+.2f} Sharpe)"


def run_search(target_iterations: int = 100) -> list[IterationResult]:
    history: list[IterationResult] = []
    champion: IterationResult | None = None

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.unlink(missing_ok=True)

    def execute(strat: Strategy):
        nonlocal champion
        if len(history) >= target_iterations:
            return False
        t0 = time.time()
        try:
            r = run_strategy(strat)
        except Exception as e:
            print(f"  [{strat.id:>3}] {strat.name}: ERROR {e}")
            return True
        elapsed = time.time() - t0
        m = r.metrics or {}
        prev_best = champion.metrics.get("sharpe", -99) if champion else -99
        sharpe = m.get("sharpe", 0)
        notes = _diagnose(prev_best, sharpe, m)
        result = IterationResult(
            iteration=len(history) + 1, name=strat.name, family=strat.family,
            rationale=strat.rationale, config=dict(strat.config),
            metrics=m, duration_sec=elapsed, notes=notes,
        )
        history.append(result)
        if (sharpe > prev_best and m.get("n_days", 0) >= 100 and m.get("max_dd", 0) > -0.5):
            champion = result
            marker = " ★"
        else:
            marker = ""
        print(f"  [{result.iteration:>3}] {strat.name:<32} "
              f"CAGR={m.get('cagr', 0)*100:>+6.1f}%  "
              f"Sharpe={sharpe:>+5.2f}  "
              f"DD={m.get('max_dd', 0)*100:>+6.1f}%  "
              f"({elapsed:>4.1f}s) {notes}{marker}")
        with LOG_PATH.open("a") as f:
            f.write(json.dumps(asdict(result), default=str) + "\n")
        return True

    # ---- Phase 1: baselines ----
    print("\n=== PHASE 1: BASELINES (1-15) ===")
    for s in _phase1_baselines():
        if not execute(s): break

    # ---- Phase 2: lookback sweep ----
    print("\n=== PHASE 2: LOOKBACK SWEEP (16-30) ===")
    for s in _phase2_lookback_sweep(history):
        if not execute(s): break

    # ---- Phase 3: top-N sweep on top families ----
    print("\n=== PHASE 3: TOP-N SWEEP (31-45) ===")
    for s in _phase3_top_n(history, champion):
        if not execute(s): break

    # ---- Phase 4: rebalance frequency ----
    if champion:
        print("\n=== PHASE 4: REBALANCE/SKIP (46-55) ===")
        for s in _phase4_rebalance(champion):
            if not execute(s): break

    # ---- Phase 5: universe variations ----
    if champion:
        print("\n=== PHASE 5: UNIVERSE VARIATIONS (56-65) ===")
        for s in _phase5_universe(champion):
            if not execute(s): break

    # ---- Phase 6: filters/overlays ----
    if champion:
        print("\n=== PHASE 6: FILTERS/OVERLAYS (66-75) ===")
        for s in _phase6_filters(champion):
            if not execute(s): break

    # ---- Phase 7: weight method ----
    if champion:
        print("\n=== PHASE 7: WEIGHT METHODS (76-85) ===")
        for s in _phase7_weight_method(champion):
            if not execute(s): break

    # ---- Phase 8: hybrid ----
    print("\n=== PHASE 8: HYBRID/ALTERNATE SIGNALS (86-95) ===")
    for s in _phase8_hybrid(champion, history):
        if not execute(s): break

    # ---- Phase 9: refinements ----
    if champion:
        print("\n=== PHASE 9: CHAMPION REFINEMENTS (96-100) ===")
        for s in _phase9_refine(champion):
            if not execute(s): break

    # ---- Phase 10: extra unique strategies to fill 100+ ----
    print("\n=== PHASE 10: EXTRA UNIQUE STRATEGIES (101-130) ===")
    from research.strategies.phase10 import phase10_extra
    for s in phase10_extra():
        execute(s)  # always run, no early-stop
    return history


def write_summary(history: list[IterationResult]) -> None:
    rows = []
    for r in history:
        m = r.metrics
        rows.append({
            "iter": r.iteration, "strategy": r.name, "family": r.family,
            "cagr_pct": round(m.get("cagr", 0) * 100, 2),
            "sharpe": round(m.get("sharpe", 0), 2),
            "sortino": round(m.get("sortino", 0), 2),
            "max_dd_pct": round(m.get("max_dd", 0) * 100, 2),
            "vol_pct": round(m.get("vol", 0) * 100, 2),
            "calmar": round(m.get("calmar", 0), 2),
            "n_days": m.get("n_days", 0),
            "n_trades": 0,  # filled later if we track
            "notes": r.notes,
        })
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS_CSV, index=False)
    print(f"\nResults → {RESULTS_CSV}")

    print("\n=== TOP 20 BY SHARPE ===")
    top = df.sort_values("sharpe", ascending=False).head(20)
    print(tabulate(top[["iter", "strategy", "cagr_pct", "sharpe", "max_dd_pct", "vol_pct"]],
                   headers="keys", tablefmt="simple", showindex=False))


if __name__ == "__main__":
    h = run_search(target_iterations=140)  # phases 1-9 ≈ 95, phase 10 adds ~37 more
    write_summary(h)
