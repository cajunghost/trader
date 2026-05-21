from dataclasses import dataclass

from option_ai_tool.server import _filter_and_sort_recommendations


@dataclass
class FakeRecommendation:
    ask: float
    score: float


def test_max_price_filter_sorts_by_ask_then_score():
    recommendations = [
        FakeRecommendation(ask=4.0, score=95),
        FakeRecommendation(ask=2.0, score=80),
        FakeRecommendation(ask=2.0, score=90),
        FakeRecommendation(ask=6.0, score=100),
    ]
    filtered = _filter_and_sort_recommendations(recommendations, 4.0)
    assert [(item.ask, item.score) for item in filtered] == [(2.0, 90), (2.0, 80), (4.0, 95)]

