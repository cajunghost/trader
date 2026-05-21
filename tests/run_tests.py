from __future__ import annotations

from tests.test_greeks import test_call_greeks_are_reasonable, test_put_delta_is_negative
from tests.test_database import test_database_saves_recommendation_and_contract_edits
from tests.test_scoring import test_rank_contracts_filters_and_scores_contract
from tests.test_server import test_max_price_filter_sorts_by_ask_then_score


def main() -> None:
    tests = [
        test_call_greeks_are_reasonable,
        test_put_delta_is_negative,
        test_rank_contracts_filters_and_scores_contract,
        test_database_saves_recommendation_and_contract_edits,
        test_max_price_filter_sorts_by_ask_then_score,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} tests passed")


if __name__ == "__main__":
    main()
