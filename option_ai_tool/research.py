from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass

from .config import ScannerConfig
from .market_data import MarketDataError
from .scanner import MarketDataClient


@dataclass(frozen=True)
class TickerSuggestion:
    symbol: str
    price: float
    change_pct: float
    momentum_5d: float
    realized_volatility: float
    score: float
    reasons: list[str]
    source: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def suggest_tickers(
    client: MarketDataClient,
    *,
    config: ScannerConfig | None = None,
    limit: int = 10,
) -> tuple[list[TickerSuggestion], list[str]]:
    config = config or ScannerConfig()
    universe = _universe(config)
    suggestions: list[TickerSuggestion] = []
    errors: list[str] = []

    for symbol in universe:
        try:
            quote = client.quote(symbol)
            closes = client.recent_closes(symbol)
            previous_close = quote.previous_close or (closes[-2] if len(closes) > 1 else None)
            if not previous_close or previous_close <= 0:
                continue
            change_pct = (quote.price / previous_close) - 1.0
            momentum_5d = _momentum_5d(quote.price, closes)
            realized_vol = _realized_volatility(closes)
            score = _research_score(change_pct, momentum_5d, realized_vol)
            reasons = _reasons(change_pct, momentum_5d, realized_vol)
            suggestions.append(
                TickerSuggestion(
                    symbol=symbol,
                    price=round(quote.price, 4),
                    change_pct=round(change_pct, 4),
                    momentum_5d=round(momentum_5d, 4),
                    realized_volatility=round(realized_vol, 4),
                    score=round(score, 2),
                    reasons=reasons,
                    source="real quote and daily price history",
                )
            )
        except MarketDataError as exc:
            errors.append(f"{symbol}: {exc}")

    suggestions.sort(key=lambda item: item.score, reverse=True)
    return suggestions[:limit], errors


def _universe(config: ScannerConfig) -> list[str]:
    symbols = []
    for raw in config.suggestion_universe.split(","):
        symbol = raw.strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def _momentum_5d(price: float, closes: list[float]) -> float:
    if len(closes) < 6 or closes[-6] <= 0:
        return 0.0
    return (price / closes[-6]) - 1.0


def _realized_volatility(closes: list[float]) -> float:
    returns = []
    for previous, current in zip(closes, closes[1:]):
        if previous > 0 and current > 0:
            returns.append((current / previous) - 1.0)
    if len(returns) < 3:
        return 0.0
    return statistics.stdev(returns[-21:]) * (252 ** 0.5)


def _research_score(change_pct: float, momentum_5d: float, realized_volatility: float) -> float:
    intraday = min(abs(change_pct) / 0.04, 1.0) * 34
    trend = min(abs(momentum_5d) / 0.10, 1.0) * 28
    vol = min(realized_volatility / 0.70, 1.0) * 28
    agreement = 10 if change_pct and momentum_5d and (change_pct > 0) == (momentum_5d > 0) else 4
    return intraday + trend + vol + agreement


def _reasons(change_pct: float, momentum_5d: float, realized_volatility: float) -> list[str]:
    direction = "upside" if change_pct >= 0 else "downside"
    trend_direction = "up" if momentum_5d >= 0 else "down"
    return [
        f"{direction} quote move {change_pct:.1%}",
        f"5-day trend {trend_direction} {momentum_5d:.1%}",
        f"realized volatility {realized_volatility:.1%}",
    ]

