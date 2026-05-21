from option_ai_tool.greeks import black_scholes_greeks


def test_call_greeks_are_reasonable():
    greeks = black_scholes_greeks(
        option_type="call",
        underlying_price=100,
        strike=100,
        days_to_expiration=30,
        implied_volatility=0.25,
        risk_free_rate=0.045,
    )
    assert 0.45 < greeks.delta < 0.65
    assert greeks.gamma > 0
    assert greeks.theta < 0
    assert greeks.vega > 0


def test_put_delta_is_negative():
    greeks = black_scholes_greeks(
        option_type="put",
        underlying_price=100,
        strike=100,
        days_to_expiration=30,
        implied_volatility=0.25,
        risk_free_rate=0.045,
    )
    assert -0.65 < greeks.delta < -0.35
    assert greeks.gamma > 0

