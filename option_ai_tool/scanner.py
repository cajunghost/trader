from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .config import ScannerConfig
from .market_data import (
    MarketDataAppClient,
    MarketDataError,
    OptionContract,
    QuoteSnapshot,
    ResilientMarketDataClient,
    TradierClient,
    YahooFinanceClient,
)
from .scoring import Recommendation, rank_contracts


class MarketDataClient(Protocol):
    def option_expirations(self, symbol: str) -> list[int]:
        ...

    def option_chain(self, symbol: str, expiration: int | None = None) -> tuple[QuoteSnapshot, list[OptionContract]]:
        ...

    def recent_closes(self, symbol: str, range_: str = "6mo") -> list[float]:
        ...

    def quote(self, symbol: str) -> QuoteSnapshot:
        ...


@dataclass(frozen=True)
class ScanResult:
    symbol: str
    recommendations: list[Recommendation]
    errors: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "recommendations": [item.to_dict() for item in self.recommendations],
            "errors": self.errors,
        }


def scan_symbols(
    symbols: list[str],
    *,
    config: ScannerConfig | None = None,
    client: MarketDataClient | None = None,
    max_results_per_symbol: int = 10,
) -> list[ScanResult]:
    config = config or ScannerConfig()
    client = client or _client_from_config(config)
    results: list[ScanResult] = []

    for raw_symbol in symbols:
        symbol = raw_symbol.strip().upper()
        if not symbol:
            continue
        errors = []
        recommendations: list[Recommendation] = []
        try:
            expirations = client.option_expirations(symbol)[: config.expirations_to_scan]
            all_contracts = []
            quote = None
            for expiration in expirations:
                quote, contracts = client.option_chain(symbol, expiration)
                all_contracts.extend(contracts)
            closes = client.recent_closes(symbol)
            if quote is None:
                raise MarketDataError(f"No quote returned for {symbol}")
            recommendations = rank_contracts(
                quote=quote,
                contracts=all_contracts,
                closes=closes,
                config=config,
            )[:max_results_per_symbol]
        except MarketDataError as exc:
            errors.append(str(exc))
        results.append(ScanResult(symbol=symbol, recommendations=recommendations, errors=errors))

    return results


def _client_from_config(config: ScannerConfig) -> MarketDataClient:
    provider = config.market_data_provider.strip().lower()
    if provider == "tradier":
        return TradierClient(token=config.tradier_token or "", base_url=config.tradier_base_url)
    if provider == "yahoo":
        return ResilientMarketDataClient(
            primary=YahooFinanceClient(),
            fallback=MarketDataAppClient(token=config.marketdata_token),
        )
    raise MarketDataError(f"Unsupported MARKET_DATA_PROVIDER: {config.market_data_provider}")
