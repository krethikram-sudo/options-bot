"""Phase 10 — additional unique strategies to bring total unique tests to 100+.

Phases 1-9 tested 92 strategies but ~30 were duplicates (the equal-weight
champion doesn't change when you sweep skip/top-N/weight params). Phase 10
adds genuinely distinct strategies that probe different design choices.
"""
from __future__ import annotations

from research.strategies.engine import Strategy


def phase10_extra() -> list[Strategy]:
    """30 genuinely different strategies to fill out the 100-strategy plan."""
    out: list[Strategy] = []
    sid = 100  # ids beyond original plan

    # ---- 1. Concentrated single-thesis baskets (8) ----
    concentrated = [
        ("ai_lead_trio", ["NVDA", "AVGO", "TSM"]),
        ("ai_pairs_trio", ["AMD", "MRVL", "AVGO"]),
        ("ai_memory", ["MU", "SNDK"]),
        ("ai_lithography", ["ASML", "AMAT", "LRCX", "KLAC"]),
        ("ai_optics", ["LITE", "COHR", "CIEN"]),
        ("ai_power_pure", ["VRT", "GEV", "ETN"]),
        ("nuclear_ai", ["CEG", "VST", "NEE"]),
        ("data_reits", ["DLR", "EQIX", "IRM"]),
    ]
    for name, tickers in concentrated:
        sid += 1
        out.append(Strategy(sid, f"X_basket_{name}", "concentrated_basket",
                            f"Concentrated {name}",
                            {"signal": "equal_weight", "universe": tickers,
                             "rebalance": "monthly"}))

    # ---- 2. Mean reversion with different lookbacks (5) ----
    for lb in [5, 10, 21, 63, 126]:
        sid += 1
        out.append(Strategy(sid, f"X_meanrev_lb{lb}", "xs_meanrev",
                            f"Mean rev lookback={lb} on AI-9",
                            {"signal": "xs_meanrev", "universe": "ai9",
                             "lookback": lb, "top_n": 3, "rebalance": "monthly"}))

    # ---- 3. Lowvol tilt with different windows + universes (4) ----
    for vw in [20, 60, 120]:
        sid += 1
        out.append(Strategy(sid, f"X_lowvol_w{vw}", "lowvol_tilt",
                            f"Low-vol tilt window={vw}",
                            {"signal": "lowvol_tilt", "universe": "ai9",
                             "vol_window": vw, "top_n": 4, "rebalance": "monthly"}))
    sid += 1
    out.append(Strategy(sid, "X_lowvol_full_chain", "lowvol_tilt",
                        "Low-vol on full chain",
                        {"signal": "lowvol_tilt", "universe": "ai_full_chain",
                         "vol_window": 60, "top_n": 7, "rebalance": "monthly"}))

    # ---- 4. Quality+trend with different universes (3) ----
    for uni in ["ai_full_chain", "ai_silicon_only", "ai_software_full"]:
        sid += 1
        out.append(Strategy(sid, f"X_qt_uni_{uni}", "xs_quality_trend",
                            f"Quality+trend on {uni}",
                            {"signal": "xs_quality_trend", "universe": uni,
                             "sharpe_window": 60, "trend_window": 126,
                             "top_n": 5, "rebalance": "monthly"}))

    # ---- 5. Universe-sweep on xs_momentum top_n=3 (5) ----
    for uni in ["semi_equipment", "networking", "servers_power",
                "ai_software", "hyperscalers"]:
        sid += 1
        out.append(Strategy(sid, f"X_xsmom_uni_{uni}", "xs_momentum",
                            f"xs momentum top-3 on {uni}",
                            {"signal": "xs_momentum", "universe": uni,
                             "lookback": 90, "skip": 21, "top_n": 3,
                             "rebalance": "monthly"}))

    # ---- 6. Active equal-weight on benchmark/factor ETFs (3) ----
    for bench in ["benchmarks", "factor_etfs", "broad_diversifier"]:
        sid += 1
        out.append(Strategy(sid, f"X_ew_{bench}", "equal_weight",
                            f"Equal-weight {bench}",
                            {"signal": "equal_weight", "universe": bench,
                             "rebalance": "monthly"}))

    # ---- 7. Vol-targeted with different vol targets (3) ----
    for tv in [0.10, 0.20, 0.30]:
        sid += 1
        out.append(Strategy(sid, f"X_voltgt_{int(tv*100)}", "ts_momentum_voltgt",
                            f"Vol-target {int(tv*100)}%",
                            {"signal": "ts_momentum_voltgt", "universe": "ai9",
                             "lookback": 90, "skip": 21, "target_vol": tv,
                             "rebalance": "weekly"}))

    # ---- 8. Buy-and-hold individual themes (5) ----
    for ticker in ["AVGO", "TSM", "AMD", "PLTR", "VRT"]:
        sid += 1
        out.append(Strategy(sid, f"X_buy_hold_{ticker}", "buy_hold",
                            f"Buy-and-hold {ticker}",
                            {"signal": "buy_hold", "ticker": ticker}))

    # ---- 9. Hyperscaler-only baskets and rotations (3) ----
    sid += 1
    out.append(Strategy(sid, "X_ew_hyperscalers_q", "equal_weight",
                        "Equal-weight hyperscalers quarterly",
                        {"signal": "equal_weight", "universe": "hyperscalers",
                         "rebalance": "quarterly"}))
    sid += 1
    out.append(Strategy(sid, "X_ew_top_4_hyperscalers", "equal_weight",
                        "Top-4 hyperscalers MSFT/GOOGL/META/AMZN",
                        {"signal": "equal_weight",
                         "universe": ["MSFT", "GOOGL", "META", "AMZN"],
                         "rebalance": "monthly"}))
    sid += 1
    out.append(Strategy(sid, "X_xsmom_hyperscalers_top2", "xs_momentum",
                        "xs momentum top-2 across hyperscalers",
                        {"signal": "xs_momentum", "universe": "hyperscalers",
                         "lookback": 126, "skip": 21, "top_n": 2,
                         "rebalance": "monthly"}))

    return out
