from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class AlertPlan:
    entry_limit: float
    patient_entry: float
    take_profit_price: float
    stop_loss_price: float
    time_exit_dte: int
    theta_exit: float
    spread_exit_pct: float
    delta_floor: float
    delta_ceiling: float

    def to_dict(self) -> dict[str, float | int | str]:
        data = asdict(self)
        data["entry"] = f"Alert when contract ask <= {self.entry_limit:.2f}; stronger entry <= {self.patient_entry:.2f}"
        data["profit"] = f"Consider selling when contract bid >= {self.take_profit_price:.2f}"
        data["loss"] = f"Review/exit if contract bid <= {self.stop_loss_price:.2f}"
        data["time"] = f"Exit or roll with {self.time_exit_dte} DTE remaining"
        data["theta"] = f"Review if theta is below {self.theta_exit:.4f} per day"
        data["spread"] = f"Review if spread exceeds {self.spread_exit_pct:.1%} of mid"
        data["delta"] = f"Review if abs(delta) leaves {self.delta_floor:.2f}-{self.delta_ceiling:.2f}"
        return data


def build_alert_plan(
    *,
    mid: float,
    spread: float,
    theta: float,
    abs_delta: float,
    target_profit_pct: float,
    stop_loss_pct: float,
    max_spread_pct: float,
) -> AlertPlan:
    entry_limit = max(mid - 0.15 * spread, 0.01)
    patient_entry = max(mid - 0.45 * spread, 0.01)
    return AlertPlan(
        entry_limit=round(entry_limit, 2),
        patient_entry=round(patient_entry, 2),
        take_profit_price=round(mid * (1.0 + target_profit_pct), 2),
        stop_loss_price=round(mid * (1.0 - stop_loss_pct), 2),
        time_exit_dte=14,
        theta_exit=round(min(theta * 1.6, -0.01), 4),
        spread_exit_pct=max_spread_pct * 1.35,
        delta_floor=max(round(abs_delta - 0.18, 2), 0.05),
        delta_ceiling=min(round(abs_delta + 0.22, 2), 0.95),
    )

