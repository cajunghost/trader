from __future__ import annotations

import statistics
from dataclasses import dataclass, asdict
from datetime import UTC, datetime

from .alerts import build_alert_plan
from .config import ScannerConfig
from .greeks import Greeks, black_scholes_greeks
from .market_data import OptionContract, QuoteSnapshot, days_to_expiration, quote_age_minutes


@dataclass(frozen=True)
class Recommendation:
    symbol: str
    strategy: str
    contract: str
    expiration: str
    dte: int
    underlying_price: float
    strike: float
    bid: float
    ask: float
    mid: float
    spread_pct: float
    volume: int
    open_interest: int
    implied_volatility: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    score: float
    rationale: list[str]
    alerts: dict[str, float | int | str]
    data_quality: dict[str, float | int | str | None]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def rank_contracts(
    *,
    quote: QuoteSnapshot,
    contracts: list[OptionContract],
    closes: list[float],
    config: ScannerConfig,
    now: datetime | None = None,
) -> list[Recommendation]:
    now = now or datetime.now(UTC)
    volatility_context = _volatility_context(closes)
    ranked = []

    for contract in contracts:
        recommendation = _score_contract(
            quote=quote,
            contract=contract,
            config=config,
            volatility_context=volatility_context,
            now=now,
        )
        if recommendation:
            ranked.append(recommendation)

    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked


def _score_contract(
    *,
    quote: QuoteSnapshot,
    contract: OptionContract,
    config: ScannerConfig,
    volatility_context: dict[str, float],
    now: datetime,
) -> Recommendation | None:
    dte = days_to_expiration(contract.expiration, now)
    if dte < config.min_dte or dte > config.max_dte:
        return None
    if contract.ask <= 0 or contract.bid < 0 or contract.mid <= 0:
        return None
    if contract.implied_volatility <= 0:
        return None
    if abs(contract.strike - quote.price) / quote.price > 0.35:
        return None
    if contract.open_interest < config.min_open_interest or contract.volume < config.min_volume:
        return None

    spread_pct = contract.spread / contract.mid if contract.mid else 1.0
    if spread_pct > config.max_spread_pct:
        return None

    try:
        greeks = black_scholes_greeks(
            option_type=contract.option_type,
            underlying_price=quote.price,
            strike=contract.strike,
            days_to_expiration=dte,
            implied_volatility=contract.implied_volatility,
            risk_free_rate=config.risk_free_rate,
        )
    except ValueError:
        return None

    abs_delta = abs(greeks.delta)
    if abs_delta < 0.18 or abs_delta > 0.72:
        return None

    score, rationale = _score_components(
        contract=contract,
        greeks=greeks,
        dte=dte,
        spread_pct=spread_pct,
        quote=quote,
        volatility_context=volatility_context,
        config=config,
    )

    alerts = build_alert_plan(
        mid=contract.mid,
        spread=contract.spread,
        theta=greeks.theta,
        abs_delta=abs_delta,
        target_profit_pct=config.target_profit_pct,
        stop_loss_pct=config.stop_loss_pct,
        max_spread_pct=config.max_spread_pct,
    ).to_dict()

    return Recommendation(
        symbol=quote.symbol,
        strategy=f"long_{contract.option_type}",
        contract=contract.contract_symbol,
        expiration=datetime.fromtimestamp(contract.expiration, UTC).date().isoformat(),
        dte=dte,
        underlying_price=round(quote.price, 4),
        strike=contract.strike,
        bid=contract.bid,
        ask=contract.ask,
        mid=round(contract.mid, 4),
        spread_pct=round(spread_pct, 4),
        volume=contract.volume,
        open_interest=contract.open_interest,
        implied_volatility=round(contract.implied_volatility, 4),
        delta=round(greeks.delta, 4),
        gamma=round(greeks.gamma, 6),
        theta=round(greeks.theta, 4),
        vega=round(greeks.vega, 4),
        rho=round(greeks.rho, 4),
        score=round(score, 2),
        rationale=rationale,
        alerts=alerts,
        data_quality={
            "source": "configured real market data provider",
            "quote_age_minutes": None if quote_age_minutes(quote) is None else round(quote_age_minutes(quote), 1),
            "currency": quote.currency,
            "realized_volatility": round(volatility_context.get("realized_vol", 0.0), 4),
        },
    )


def _score_components(
    *,
    contract: OptionContract,
    greeks: Greeks,
    dte: int,
    spread_pct: float,
    quote: QuoteSnapshot,
    volatility_context: dict[str, float],
    config: ScannerConfig,
) -> tuple[float, list[str]]:
    abs_delta = abs(greeks.delta)
    liquidity = min(contract.open_interest / 2000.0, 1.0) * 18 + min(contract.volume / 500.0, 1.0) * 12
    spread_quality = max(0.0, 1.0 - spread_pct / config.max_spread_pct) * 18
    delta_quality = max(0.0, 1.0 - abs(abs_delta - 0.38) / 0.34) * 16
    gamma_theta = min(max((greeks.gamma * quote.price) / max(abs(greeks.theta), 0.01), 0.0), 2.0) * 8
    dte_quality = max(0.0, 1.0 - abs(dte - 35) / 50.0) * 12
    iv_quality = _iv_quality(contract.implied_volatility, volatility_context.get("realized_vol", 0.35)) * 14
    moneyness = _moneyness_quality(contract, quote.price) * 10

    score = liquidity + spread_quality + delta_quality + gamma_theta + dte_quality + iv_quality + moneyness
    rationale = [
        f"liquidity OI={contract.open_interest}, volume={contract.volume}",
        f"spread {spread_pct:.1%} of mid",
        f"delta {greeks.delta:.2f} with gamma/theta balance {gamma_theta:.1f}",
        f"{dte} DTE in configured window",
        f"IV {contract.implied_volatility:.1%} vs realized volatility proxy {volatility_context.get('realized_vol', 0):.1%}",
    ]
    return min(score, 100.0), rationale


def _iv_quality(iv: float, realized_vol: float) -> float:
    if realized_vol <= 0:
        return 0.5
    ratio = iv / realized_vol
    if 0.75 <= ratio <= 1.35:
        return 1.0
    if ratio < 0.75:
        return max(0.4, ratio / 0.75)
    return max(0.0, 1.0 - (ratio - 1.35) / 1.8)


def _moneyness_quality(contract: OptionContract, price: float) -> float:
    distance = abs(contract.strike - price) / price
    return max(0.0, 1.0 - distance / 0.18)


def _volatility_context(closes: list[float]) -> dict[str, float]:
    if len(closes) < 22:
        return {"realized_vol": 0.35, "support": min(closes) if closes else 0.0}
    returns = []
    for previous, current in zip(closes, closes[1:]):
        if previous > 0 and current > 0:
            returns.append((current / previous) - 1.0)
    realized = statistics.stdev(returns[-63:]) * (252 ** 0.5) if len(returns) >= 3 else 0.35
    return {
        "realized_vol": realized,
        "support": min(closes[-20:]),
        "resistance": max(closes[-20:]),
    }
