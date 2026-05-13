"""Entry signal generation.

Three strategy variants — selected by Strategy.entry_type:
  - mean_reversion : RSI cross out of extreme + MACD confirms reversal
  - trend_following: RSI on the trend side of midline + MACD aligned + persisting
  - macd_cross     : classic MACD line crosses signal line, optional RSI gate

Indicator computation is split out so the tuner computes RSI/MACD once per
ticker and only re-runs the cheap signal logic for each grid combination.
"""
import pandas as pd

import config
from indicators import macd, rsi
from strategy import Strategy


def attach_indicators(bars: pd.DataFrame, s: Strategy | None = None) -> pd.DataFrame:
    if s is None:
        period, fast, slow, sig = config.RSI_PERIOD, config.MACD_FAST, config.MACD_SLOW, config.MACD_SIGNAL
    else:
        period, fast, slow, sig = s.rsi_period, s.macd_fast, s.macd_slow, s.macd_signal
    out = bars.copy()
    out["rsi"] = rsi(out["close"], period)
    macd_df = macd(out["close"], fast, slow, sig)
    return out.join(macd_df)


def _hist_trend(out: pd.DataFrame, n: int) -> tuple[pd.Series, pd.Series]:
    """Histogram strictly rising/falling for the last n bars."""
    rising = pd.Series(True, index=out.index)
    falling = pd.Series(True, index=out.index)
    for k in range(1, n + 1):
        rising &= out["hist"] > out["hist"].shift(k)
        falling &= out["hist"] < out["hist"].shift(k)
    return rising, falling


def _apply_side(out: pd.DataFrame, call: pd.Series, put: pd.Series, s: Strategy) -> pd.DataFrame:
    if s.side == "calls":
        put = pd.Series(False, index=out.index)
    elif s.side == "puts":
        call = pd.Series(False, index=out.index)
    out["call_signal"] = call.fillna(False)
    out["put_signal"] = put.fillna(False)
    return out


def _mean_reversion(out: pd.DataFrame, s: Strategy) -> pd.DataFrame:
    """Buy calls when RSI bounces UP through oversold + MACD turning bullish.
    Puts: RSI breaks DOWN through overbought + MACD turning bearish."""
    rsi_prev = out["rsi"].shift(1)
    cross_up = (rsi_prev <= s.rsi_oversold) & (out["rsi"] > s.rsi_oversold)
    cross_down = (rsi_prev >= s.rsi_overbought) & (out["rsi"] < s.rsi_overbought)
    rising, falling = _hist_trend(out, s.macd_confirm_bars)
    call = cross_up & (out["hist"] > 0) & rising
    put = cross_down & (out["hist"] < 0) & falling
    return _apply_side(out, call, put, s)


def _trend_following(out: pd.DataFrame, s: Strategy) -> pd.DataFrame:
    """Enter on transition INTO trend regime.
    Bullish regime: RSI > rsi_oversold (interpreted as bullish threshold, e.g. 55)
                    AND MACD hist > 0 AND rising.
    Bearish regime: RSI < rsi_overbought (interpreted as bearish threshold)
                    AND MACD hist < 0 AND falling.
    Fires only on the bar the regime newly becomes true (avoids re-firing every bar)."""
    rising, falling = _hist_trend(out, s.macd_confirm_bars)
    bull = (out["rsi"] > s.rsi_oversold) & (out["hist"] > 0) & rising
    bear = (out["rsi"] < s.rsi_overbought) & (out["hist"] < 0) & falling
    bull_prev = bull.shift(1).fillna(False)
    bear_prev = bear.shift(1).fillna(False)
    call = bull & ~bull_prev
    put = bear & ~bear_prev
    return _apply_side(out, call, put, s)


def _macd_cross(out: pd.DataFrame, s: Strategy) -> pd.DataFrame:
    """Classic MACD line crossing signal line. RSI thresholds act as a filter:
    - call only if RSI > rsi_oversold (avoid bullish crosses in deep downtrends)
    - put only if RSI < rsi_overbought (avoid bearish crosses in strong uptrends)"""
    macd_prev = out["macd"].shift(1)
    sig_prev = out["signal"].shift(1)
    bull_cross = (macd_prev <= sig_prev) & (out["macd"] > out["signal"])
    bear_cross = (macd_prev >= sig_prev) & (out["macd"] < out["signal"])
    call = bull_cross & (out["rsi"] > s.rsi_oversold)
    put = bear_cross & (out["rsi"] < s.rsi_overbought)
    return _apply_side(out, call, put, s)


_DISPATCH = {
    "mean_reversion": _mean_reversion,
    "trend_following": _trend_following,
    "macd_cross": _macd_cross,
}


def apply_signal_rules(bars_with_ind: pd.DataFrame, s: Strategy) -> pd.DataFrame:
    fn = _DISPATCH.get(s.entry_type)
    if fn is None:
        raise ValueError(f"Unknown entry_type: {s.entry_type}. Valid: {list(_DISPATCH)}")
    return fn(bars_with_ind.copy(), s)


def compute_signals(bars: pd.DataFrame, s: Strategy | None = None) -> pd.DataFrame:
    s = s or Strategy()
    return apply_signal_rules(attach_indicators(bars, s), s)
