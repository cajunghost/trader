from datetime import UTC, datetime, timedelta

from option_ai_tool.config import ScannerConfig
from option_ai_tool.market_data import OptionContract, QuoteSnapshot
from option_ai_tool.scoring import rank_contracts


def test_rank_contracts_filters_and_scores_contract():
    expiry = int((datetime.now(UTC) + timedelta(days=35)).timestamp())
    quote = QuoteSnapshot("XYZ", 100.0, 99.0, None, "USD")
    contract = OptionContract(
        symbol="XYZ",
        option_type="call",
        contract_symbol="XYZ260619C00100000",
        expiration=expiry,
        strike=100.0,
        bid=4.8,
        ask=5.2,
        last_price=5.0,
        implied_volatility=0.32,
        volume=200,
        open_interest=1000,
        in_the_money=False,
    )
    recs = rank_contracts(
        quote=quote,
        contracts=[contract],
        closes=[95, 96, 98, 97, 99, 100, 101, 100, 99, 100, 102, 101, 100, 99, 101, 102, 103, 102, 101, 100, 101, 102],
        config=ScannerConfig(),
    )
    assert len(recs) == 1
    assert recs[0].contract == "XYZ260619C00100000"
    assert recs[0].alerts["entry_limit"] > 0

