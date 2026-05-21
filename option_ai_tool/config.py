from __future__ import annotations

import os
from dataclasses import dataclass


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class ScannerConfig:
    market_data_provider: str = os.getenv("MARKET_DATA_PROVIDER", "yahoo")
    tradier_token: str | None = os.getenv("TRADIER_TOKEN")
    tradier_base_url: str = os.getenv("TRADIER_BASE_URL", "https://api.tradier.com/v1")
    trader_db_path: str = os.getenv("TRADER_DB_PATH", "trader.sqlite3")
    suggestion_universe: str = os.getenv(
        "SUGGESTION_UNIVERSE",
        "AAPL,MSFT,NVDA,AMZN,META,GOOGL,TSLA,AMD,AVGO,SPY,QQQ,IWM,NFLX,PLTR,COIN,SMCI,CRM,UBER,JPM,XOM",
    )
    risk_free_rate: float = _float("RISK_FREE_RATE", 0.045)
    min_open_interest: int = _int("MIN_OPEN_INTEREST", 100)
    min_volume: int = _int("MIN_VOLUME", 10)
    max_spread_pct: float = _float("MAX_SPREAD_PCT", 0.18)
    min_dte: int = _int("MIN_DTE", 7)
    max_dte: int = _int("MAX_DTE", 75)
    target_profit_pct: float = _float("TARGET_PROFIT_PCT", 0.45)
    stop_loss_pct: float = _float("STOP_LOSS_PCT", 0.35)
    expirations_to_scan: int = _int("EXPIRATIONS_TO_SCAN", 12)
