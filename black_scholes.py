"""Black-Scholes pricing + delta + strike-finder utilities.

We don't have free historical option chains, so we synthesize prices via BS.
This is approximate — real fills include skew, spread, and time-of-day vol —
but lets the backtester model multi-leg strategies without paid data.
"""
import math

from scipy.optimize import brentq
from scipy.stats import norm


def bs_price(spot: float, strike: float, t_years: float, rate: float, iv: float, kind: str) -> float:
    if t_years <= 0:
        intrinsic = spot - strike if kind == "call" else strike - spot
        return max(intrinsic, 0.0)
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
    d2 = d1 - iv * math.sqrt(t_years)
    if kind == "call":
        return spot * norm.cdf(d1) - strike * math.exp(-rate * t_years) * norm.cdf(d2)
    return strike * math.exp(-rate * t_years) * norm.cdf(-d2) - spot * norm.cdf(-d1)


def bs_delta(spot: float, strike: float, t_years: float, rate: float, iv: float, kind: str) -> float:
    if t_years <= 0:
        if kind == "call":
            return 1.0 if spot > strike else 0.0
        return -1.0 if spot < strike else 0.0
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
    if kind == "call":
        return norm.cdf(d1)
    return norm.cdf(d1) - 1.0


def find_strike_at_delta(
    spot: float, target_abs_delta: float, t_years: float, rate: float, iv: float, kind: str
) -> float:
    """Find strike K such that |delta(K)| ≈ `target_abs_delta`. For OTM credit
    spreads, target_abs_delta is small (e.g. 0.16 = ~16% finish-ITM probability)."""
    target = abs(target_abs_delta) if kind == "call" else -abs(target_abs_delta)

    def fn(strike: float) -> float:
        return bs_delta(spot, strike, t_years, rate, iv, kind) - target

    if kind == "put":
        # OTM puts have strikes below spot; |delta| smaller as strike drops
        lo, hi = max(spot * 0.10, 0.01), spot * 1.5
    else:
        lo, hi = spot * 0.5, spot * 5.0

    try:
        return brentq(fn, lo, hi, xtol=1e-3)
    except ValueError:
        # delta target not bracketable in this range; fall back to spot * heuristic
        return spot * (0.85 if kind == "put" else 1.15)


def atm_strike(spot: float) -> float:
    """Snap to nearest dollar."""
    return round(spot)
