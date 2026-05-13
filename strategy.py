"""Tunable strategy parameters.

`entry_type` selects the entry rule shape (mean reversion / trend / MACD cross),
and the threshold fields (rsi_oversold, rsi_overbought) are reinterpreted by
each variant. The same Strategy dataclass works for all three so the tuner can
sweep them uniformly.
"""
from dataclasses import dataclass

# valid entry types — must match the dispatch in signals.apply_signal_rules
ENTRY_TYPES = ("mean_reversion", "trend_following", "macd_cross")


@dataclass(frozen=True)
class Strategy:
    entry_type: str = "mean_reversion"

    rsi_period: int = 14
    rsi_oversold: float = 30
    rsi_overbought: float = 70
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # how many consecutive bars the MACD histogram must trend in the entry direction
    macd_confirm_bars: int = 1

    # exit rules (fractions of premium)
    profit_target: float = 0.25
    stop_loss: float = -0.40
    exit_minutes_before_close: int = 15

    # which sides to trade: "calls", "puts", or "both"
    side: str = "both"

    # option pricing assumptions
    iv: float = 0.50
    dte_days: float = 4
    risk_free_rate: float = 0.045

    def label(self) -> str:
        return (
            f"{self.entry_type:<16} "
            f"side={self.side:<5} "
            f"rsi={self.rsi_oversold:.0f}/{self.rsi_overbought:.0f} "
            f"confirm={self.macd_confirm_bars} "
            f"pt={self.profit_target:+.2f} sl={self.stop_loss:+.2f}"
        )
