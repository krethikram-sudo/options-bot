"""CLI entry point.

Usage:
  python run.py backtest                    # P&L sim with default strategy
  python run.py tune                        # grid search across all tickers
  python run.py tune SNDK                   # grid search for one ticker
  python run.py tune SNDK NVDA              # grid search for a subset
  python run.py historical-alerts           # list alerts that would have fired
  python run.py live                        # live polling + daily reports
  python run.py paper                       # Alpaca paper trading loop
"""
import sys

COMMANDS = {
    "backtest":          ("backtest",          "run", False),
    "tune":              ("tune",              "run", True),
    "spreads":           ("spreads",           "run", True),
    "historical-alerts": ("historical_alerts", "run", False),
    "live":              ("live_alerts",       "run", False),
    "paper":             ("paper_trader",      "run", False),
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    module_name, fn_name, takes_args = COMMANDS[sys.argv[1]]
    module = __import__(module_name)
    fn = getattr(module, fn_name)
    if takes_args:
        extra = sys.argv[2:]
        fn(extra if extra else None)
    else:
        fn()


if __name__ == "__main__":
    main()
