"""Strategy and runtime configuration. Tune these to change behavior."""

TICKERS = ["SNDK", "NVDA", "AMD", "AVGO", "MU", "TSM", "MRVL", "ARM", "SMCI"]

# Indicator parameters
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# Entry thresholds
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# Exit rules (fraction of premium paid)
PROFIT_TARGET = 0.25
STOP_LOSS = -0.40
EXIT_MINUTES_BEFORE_CLOSE = 15

# Position sizing
CONTRACTS_PER_SIGNAL = 1
MAX_CONCURRENT_POSITIONS = 3

# Backtest assumptions
BACKTEST_BAR_INTERVAL = "5m"   # yfinance intraday: 1m/2m/5m/15m/30m/60m (60d max for <1h)
BACKTEST_LOOKBACK_DAYS = 59
ASSUMED_IV = 0.50              # used for Black-Scholes pricing if not provided
RISK_FREE_RATE = 0.045
DAYS_TO_EXPIRY = 4             # weekly contracts, mid-week average

# Paper trading loop
POLL_INTERVAL_SECONDS = 60

# Starting paper capital — used to compute lifetime P&L in reports
STARTING_CAPITAL = 100000.0

# Bull put credit spread strategy
# Excluded from the original 9: MU (real put credit ~$0.03 = unworkable),
# ARM (real credit only 7% of width = insufficient cushion). See validate_chains.py.
SPREAD_TICKERS = [t for t in TICKERS if t not in ("MU", "ARM")]

# Calibration: median ratio of (real chain mid credit) / (BS credit at realized vol) was 0.65
# across the 7 viable tickers. Multiplying the IV used in BS pricing by this factor brings
# our backtest credits in line with what the real options market actually pays.
# 1.0 = no calibration (original BS);  0.65 = realistic;  0.55 = conservative fills
SPREAD_IV_HAIRCUT = 0.65

# Profile A* — calibrated bull put spread parameters
# Lowered delta from 0.35 → 0.20 to reduce vega and smooth daily MtM swings.
# Trade-off: less credit per spread but ~50% lower delta sensitivity to underlying drops.
SPREAD_TARGET_DELTA = 0.20      # short put delta target (-0.20, was -0.35)
SPREAD_WIDTH_PCT = 0.05         # long put strike = short - (spot * width_pct)
SPREAD_DTE = 45                  # target days to expiry on entry
SPREAD_PROFIT_TARGET = 0.25     # close when 25% of credit captured
SPREAD_MIN_CREDIT = 0.10        # lowered from 0.20 — 20-delta spreads pay less credit

# Auto-execution risk limits — Conservative profile (post-Week-1 vol-tolerance adjustment)
# Was: $25k risk / qty 2 / 35-delta. New: 30% smaller sizing + lower delta for smoother MtM.
SPREAD_AUTO_SUBMIT = True        # set False to alert-only (no orders)
SPREAD_QTY_PER_TRADE = 2         # number of contracts per spread
SPREAD_MAX_CONCURRENT = 7        # one slot per viable ticker
SPREAD_MAX_TOTAL_RISK = 17500.0  # 25k → 17.5k (30% reduction; smaller spread book)
SPREAD_LIMIT_FILL_FRAC = 0.90    # limit credit = expected_credit * this (helps fills)

# ============================================================
# Multi-strategy roster (Path A): four strategies sharing $100k
# ============================================================

# Strategy 2: Trend-following equities (50-SMA cross)
# Sleeve capital reduced 30% post-Week-1 vol-tolerance adjustment ($30k → $21k)
TREND_AUTO_SUBMIT = True
TREND_TICKERS = TICKERS  # all 9 AI infra names
TREND_SLEEVE_CAPITAL = 21000.0           # $21k allocation for this sleeve
TREND_PER_TICKER = TREND_SLEEVE_CAPITAL / len(TREND_TICKERS)  # ~$2,333 per ticker
TREND_SMA_PERIOD = 50
TREND_STOP_PCT = -0.08                    # 8% stop loss
TREND_STATE_PATH = "logs/trend_positions.jsonl"

# Strategy 3: Rotational momentum (top-3 by 10-day return, monthly rebalance)
# Sleeve capital reduced 30% ($25k → $17.5k)
ROTATION_AUTO_SUBMIT = True
ROTATION_TICKERS = TICKERS                # all 9 AI infra names
ROTATION_SLEEVE_CAPITAL = 17500.0
ROTATION_TOP_N = 3
ROTATION_LOOKBACK_DAYS = 10               # 10-day return for ranking
ROTATION_REBALANCE_DAYS = 30              # rebalance every 30 calendar days
ROTATION_STATE_PATH = "logs/rotation_positions.jsonl"

# Strategy 4: Selective earnings straddles (AVGO + MRVL only — backtest validated)
# Sleeve capital reduced 30% ($15k → $10.5k)
STRADDLE_AUTO_SUBMIT = True
STRADDLE_TICKERS = ["AVGO", "MRVL"]        # only the tickers with proven straddle edge
STRADDLE_SLEEVE_CAPITAL = 10500.0
STRADDLE_QTY_PER_TRADE = 1
STRADDLE_DTE_TARGET = 7                    # weekly options
STRADDLE_DAYS_BEFORE = 1                   # open T-1
STRADDLE_DAYS_AFTER = 1                    # close T+1
STRADDLE_STATE_PATH = "logs/straddle_positions.jsonl"

# Strategy 5: AI full-chain equal-weight basket (validated over 130+ backtests)
# Highest-Sharpe simple strategy from search. Monthly rebalance. Sized for
# realistic -40% drawdown in bear regime (per 6-year backtest).
CHAIN_AUTO_SUBMIT = True
CHAIN_SLEEVE_CAPITAL = 17500.0           # $17.5k post-Week-1 reduction (was $25k = 30% cut)
CHAIN_REBALANCE_DAYS = 30                 # ~monthly
CHAIN_DRIFT_THRESHOLD = 0.15              # only trade if position drifts >15% from target
CHAIN_STATE_PATH = "logs/chain_positions.json"   # single JSON snapshot
# ~50 tickers across the full AI value chain
CHAIN_TICKERS = [
    # core AI infra
    "NVDA", "AMD", "AVGO", "SNDK", "MU", "TSM", "MRVL", "ARM", "SMCI",
    # semi equipment
    "ASML", "AMAT", "LRCX", "KLAC", "TER", "ENTG", "ONTO", "MKSI",
    # foundries (drop GFS, UMC for liquidity)
    "INTC",
    # other silicon
    "QCOM", "TXN", "ADI", "ON", "MCHP", "NXPI", "MPWR",
    # networking + optical
    "ANET", "CSCO", "CIEN", "LITE", "CRDO", "COHR",
    # storage
    "WDC", "STX", "NTAP", "PSTG",
    # servers + power
    "DELL", "HPE", "VRT", "ETN", "GEV", "HUBB", "PWR",
    # hyperscalers
    "AMZN", "MSFT", "GOOGL", "META", "ORCL", "IBM",
]
