from __future__ import annotations

from datetime import UTC, datetime

from .database import TraderDatabase
from .market_data import MarketDataError
from .scanner import MarketDataClient


def mark_recommendation(
    database: TraderDatabase,
    client: MarketDataClient,
    recommendation_id: int,
) -> dict[str, object]:
    recommendation = database.get_recommendation(recommendation_id)
    if not recommendation:
        return {"error": "recommendation not found"}

    try:
        expiration = _expiration_epoch(str(recommendation["expiration"]))
        _, contracts = client.option_chain(str(recommendation["symbol"]), expiration)
        contract = next((item for item in contracts if item.contract_symbol == recommendation["contract"]), None)
        if not contract:
            raise MarketDataError("contract not found in latest option chain")
        current_mid = round(contract.mid, 4)
        entry = float(recommendation["entry_limit"])
        count = int(recommendation["contracts"])
        pnl = (current_mid - entry) * 100 * count
        pnl_pct = ((current_mid / entry) - 1.0) if entry else None
        status = _status(current_mid, recommendation)
        snapshot = database.save_snapshot(
            recommendation_id=recommendation_id,
            current_bid=contract.bid,
            current_ask=contract.ask,
            current_mid=current_mid,
            pnl_dollars=round(pnl, 2),
            pnl_pct=None if pnl_pct is None else round(pnl_pct, 4),
            status=status,
            source="latest option chain mark",
        )
        return {"recommendation": database.get_recommendation(recommendation_id), "snapshot": snapshot}
    except MarketDataError as exc:
        snapshot = database.save_snapshot(
            recommendation_id=recommendation_id,
            current_bid=None,
            current_ask=None,
            current_mid=None,
            pnl_dollars=None,
            pnl_pct=None,
            status=f"mark failed: {exc}",
            source="latest option chain mark",
        )
        return {"recommendation": database.get_recommendation(recommendation_id), "snapshot": snapshot}


def mark_all(database: TraderDatabase, client: MarketDataClient, limit: int = 25) -> list[dict[str, object]]:
    rows = database.list_recommendations(limit=limit)
    return [mark_recommendation(database, client, int(row["id"])) for row in rows]


def _expiration_epoch(value: str) -> int:
    return int(datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC).timestamp())


def _status(current_mid: float, recommendation: dict[str, object]) -> str:
    if current_mid >= float(recommendation["take_profit_price"]):
        return "target reached"
    if current_mid <= float(recommendation["stop_loss_price"]):
        return "stop reached"
    if current_mid <= float(recommendation["patient_entry"]):
        return "patient entry available"
    if current_mid <= float(recommendation["entry_limit"]):
        return "entry available"
    return "active"

