from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from .scoring import Recommendation


class TraderDatabase:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        if self.path.parent and str(self.path.parent) != ".":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    contract TEXT NOT NULL,
                    expiration TEXT NOT NULL,
                    dte INTEGER NOT NULL,
                    underlying_price REAL NOT NULL,
                    strike REAL NOT NULL,
                    bid REAL NOT NULL,
                    ask REAL NOT NULL,
                    mid REAL NOT NULL,
                    spread_pct REAL NOT NULL,
                    volume INTEGER NOT NULL,
                    open_interest INTEGER NOT NULL,
                    implied_volatility REAL NOT NULL,
                    delta REAL NOT NULL,
                    gamma REAL NOT NULL,
                    theta REAL NOT NULL,
                    vega REAL NOT NULL,
                    rho REAL NOT NULL,
                    score REAL NOT NULL,
                    entry_limit REAL NOT NULL,
                    patient_entry REAL NOT NULL,
                    take_profit_price REAL NOT NULL,
                    stop_loss_price REAL NOT NULL,
                    contracts INTEGER NOT NULL DEFAULT 1,
                    rationale_json TEXT NOT NULL,
                    alerts_json TEXT NOT NULL,
                    data_quality_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS performance_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recommendation_id INTEGER NOT NULL,
                    checked_at TEXT NOT NULL,
                    current_bid REAL,
                    current_ask REAL,
                    current_mid REAL,
                    pnl_dollars REAL,
                    pnl_pct REAL,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL,
                    FOREIGN KEY (recommendation_id) REFERENCES recommendations(id)
                );

                CREATE TABLE IF NOT EXISTS research_suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    change_pct REAL NOT NULL,
                    momentum_5d REAL NOT NULL,
                    realized_volatility REAL NOT NULL,
                    score REAL NOT NULL,
                    reasons_json TEXT NOT NULL,
                    source TEXT NOT NULL
                );
                """
            )

    def save_recommendations(self, recommendations: list[Recommendation], contracts: int = 1) -> list[dict[str, Any]]:
        saved = []
        now = _now()
        with self.connect() as connection:
            for rec in recommendations:
                entry = float(rec.alerts["entry_limit"])
                patient = float(rec.alerts["patient_entry"])
                take_profit = float(rec.alerts["take_profit_price"])
                stop_loss = float(rec.alerts["stop_loss_price"])
                cursor = connection.execute(
                    """
                    INSERT INTO recommendations (
                        created_at, symbol, strategy, contract, expiration, dte, underlying_price,
                        strike, bid, ask, mid, spread_pct, volume, open_interest, implied_volatility,
                        delta, gamma, theta, vega, rho, score, entry_limit, patient_entry,
                        take_profit_price, stop_loss_price, contracts, rationale_json, alerts_json,
                        data_quality_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now,
                        rec.symbol,
                        rec.strategy,
                        rec.contract,
                        rec.expiration,
                        rec.dte,
                        rec.underlying_price,
                        rec.strike,
                        rec.bid,
                        rec.ask,
                        rec.mid,
                        rec.spread_pct,
                        rec.volume,
                        rec.open_interest,
                        rec.implied_volatility,
                        rec.delta,
                        rec.gamma,
                        rec.theta,
                        rec.vega,
                        rec.rho,
                        rec.score,
                        entry,
                        patient,
                        take_profit,
                        stop_loss,
                        max(int(contracts), 1),
                        json.dumps(rec.rationale),
                        json.dumps(rec.alerts),
                        json.dumps(rec.data_quality),
                    ),
                )
                saved.append(self._row_to_dict(connection.execute("SELECT * FROM recommendations WHERE id = ?", (cursor.lastrowid,)).fetchone()))
        return saved

    def list_recommendations(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT r.*, p.checked_at, p.current_bid, p.current_ask, p.current_mid,
                       p.pnl_dollars, p.pnl_pct, p.status, p.source AS snapshot_source
                FROM recommendations r
                LEFT JOIN performance_snapshots p
                  ON p.id = (
                      SELECT id FROM performance_snapshots
                      WHERE recommendation_id = r.id
                      ORDER BY checked_at DESC
                      LIMIT 1
                  )
                ORDER BY r.created_at DESC, r.score DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_recommendation(self, recommendation_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM recommendations WHERE id = ?", (recommendation_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def update_contracts(self, recommendation_id: int, contracts: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE recommendations SET contracts = ? WHERE id = ?",
                (max(int(contracts), 1), recommendation_id),
            )
            row = connection.execute("SELECT * FROM recommendations WHERE id = ?", (recommendation_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def save_snapshot(
        self,
        *,
        recommendation_id: int,
        current_bid: float | None,
        current_ask: float | None,
        current_mid: float | None,
        pnl_dollars: float | None,
        pnl_pct: float | None,
        status: str,
        source: str,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO performance_snapshots (
                    recommendation_id, checked_at, current_bid, current_ask, current_mid,
                    pnl_dollars, pnl_pct, status, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (recommendation_id, _now(), current_bid, current_ask, current_mid, pnl_dollars, pnl_pct, status, source),
            )
            row = connection.execute("SELECT * FROM performance_snapshots WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)

    def save_suggestions(self, suggestions: list[dict[str, Any]]) -> None:
        now = _now()
        with self.connect() as connection:
            for suggestion in suggestions:
                connection.execute(
                    """
                    INSERT INTO research_suggestions (
                        created_at, symbol, price, change_pct, momentum_5d,
                        realized_volatility, score, reasons_json, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now,
                        suggestion["symbol"],
                        suggestion["price"],
                        suggestion["change_pct"],
                        suggestion["momentum_5d"],
                        suggestion["realized_volatility"],
                        suggestion["score"],
                        json.dumps(suggestion["reasons"]),
                        suggestion["source"],
                    ),
                )

    def list_suggestions(self, limit: int = 30) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM research_suggestions ORDER BY created_at DESC, score DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for key in ("rationale_json", "alerts_json", "data_quality_json", "reasons_json"):
            if key in data and data[key]:
                data[key.removesuffix("_json")] = json.loads(data[key])
                del data[key]
        data.update(_potential(data))
        return data


def _potential(row: dict[str, Any]) -> dict[str, float]:
    contracts = max(int(row.get("contracts") or 1), 1)
    entry = float(row.get("entry_limit") or 0)
    take_profit = float(row.get("take_profit_price") or 0)
    stop_loss = float(row.get("stop_loss_price") or 0)
    current_mid = row.get("current_mid")
    cost = entry * 100 * contracts
    target_value = take_profit * 100 * contracts
    stop_value = stop_loss * 100 * contracts
    data = {
        "estimated_cost": round(cost, 2),
        "target_value": round(target_value, 2),
        "target_profit": round(target_value - cost, 2),
        "stop_value": round(stop_value, 2),
        "stop_loss": round(stop_value - cost, 2),
    }
    if current_mid is not None:
        current_value = float(current_mid) * 100 * contracts
        data["current_value"] = round(current_value, 2)
        data["current_profit"] = round(current_value - cost, 2)
    return data


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")

