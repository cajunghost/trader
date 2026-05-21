from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Greeks:
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


def _norm_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2 * math.pi)


def _norm_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def black_scholes_greeks(
    *,
    option_type: str,
    underlying_price: float,
    strike: float,
    days_to_expiration: int,
    implied_volatility: float,
    risk_free_rate: float,
) -> Greeks:
    if underlying_price <= 0 or strike <= 0:
        raise ValueError("underlying_price and strike must be positive")
    if days_to_expiration <= 0:
        raise ValueError("days_to_expiration must be positive")
    if implied_volatility <= 0:
        raise ValueError("implied_volatility must be positive")

    t = days_to_expiration / 365.0
    sqrt_t = math.sqrt(t)
    d1 = (
        math.log(underlying_price / strike)
        + (risk_free_rate + 0.5 * implied_volatility**2) * t
    ) / (implied_volatility * sqrt_t)
    d2 = d1 - implied_volatility * sqrt_t

    pdf = _norm_pdf(d1)
    gamma = pdf / (underlying_price * implied_volatility * sqrt_t)
    vega = underlying_price * pdf * sqrt_t / 100.0

    if option_type == "call":
        delta = _norm_cdf(d1)
        theta = (
            -underlying_price * pdf * implied_volatility / (2 * sqrt_t)
            - risk_free_rate * strike * math.exp(-risk_free_rate * t) * _norm_cdf(d2)
        ) / 365.0
        rho = strike * t * math.exp(-risk_free_rate * t) * _norm_cdf(d2) / 100.0
    elif option_type == "put":
        delta = _norm_cdf(d1) - 1.0
        theta = (
            -underlying_price * pdf * implied_volatility / (2 * sqrt_t)
            + risk_free_rate * strike * math.exp(-risk_free_rate * t) * _norm_cdf(-d2)
        ) / 365.0
        rho = -strike * t * math.exp(-risk_free_rate * t) * _norm_cdf(-d2) / 100.0
    else:
        raise ValueError("option_type must be 'call' or 'put'")

    return Greeks(delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho)

