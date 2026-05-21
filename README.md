# AI Options Opportunity Scanner

An options decision-support tool that uses real market data for a supplied watchlist, computes option Greeks, ranks candidate contracts, and produces entry/exit alert triggers.

This project does **not** execute trades and does **not** promise returns. It is built to make the data and assumptions visible so you can review each signal before acting.

## What It Uses

- Real quote, options-chain, and price-history data from a configured provider.
- Yahoo Finance public endpoints are available as a no-key fallback.
- Tradier is supported for a production options feed when `TRADIER_TOKEN` is set.
- Black-Scholes Greeks computed from each contract's live/delayed implied volatility, strike, expiration, and underlying price.
- Liquidity, spread, delta, theta, gamma, implied-volatility, and reward/risk filters.
- Rule-based "AI" ranking that is deterministic and auditable. No synthetic market data is generated.

## Quick Start

Use the bundled Codex Python runtime or Python 3.11+.

```powershell
python -m option_ai_tool.cli --symbols AAPL MSFT NVDA --max-results 10
```

Start the mobile web app:

```powershell
python -m option_ai_tool.server --host 127.0.0.1 --port 8080
```

Then open:

```text
http://127.0.0.1:8080/?symbols=AAPL,MSFT,NVDA
```

## Mobile Web App

The web interface includes:

- Ticker scans with editable contract counts.
- Real-data suggested tickers ranked by quote movement, 5-day momentum, and realized volatility.
- Saved recommendations in SQLite.
- Performance marks that refresh the latest option-chain bid/ask/mid.
- Target, stop, estimated cost, and potential return calculations per contract count.

For phone access anywhere, deploy the repo as a Python web service. The included `render.yaml`, `Procfile`, and `Dockerfile` run:

```text
python -m option_ai_tool.server --host 0.0.0.0 --port $PORT
```

Set `TRADER_DB_PATH` to a persistent disk path such as `/var/data/trader.sqlite3`.

## Configuration

Copy `.env.example` to `.env` if you want to change defaults. The app works without API keys because the Yahoo Finance endpoints are public, but they may be delayed, rate-limited, or unavailable.

| Variable | Default | Purpose |
| --- | --- | --- |
| `MARKET_DATA_PROVIDER` | `yahoo` | Use `yahoo` or `tradier`. |
| `TRADIER_TOKEN` | empty | Bearer token for Tradier market data. |
| `TRADIER_BASE_URL` | `https://api.tradier.com/v1` | Tradier live API base URL. |
| `TRADER_DB_PATH` | `trader.sqlite3` | SQLite path for saved scans and performance marks. |
| `SUGGESTION_UNIVERSE` | large-cap watchlist | Comma-separated tickers used for research suggestions. |
| `RISK_FREE_RATE` | `0.045` | Annualized risk-free rate used in Greeks. |
| `MIN_OPEN_INTEREST` | `100` | Minimum contract open interest. |
| `MIN_VOLUME` | `10` | Minimum contract volume. |
| `MAX_SPREAD_PCT` | `0.18` | Maximum bid/ask spread as a fraction of mid. |
| `MIN_DTE` | `7` | Minimum days to expiration. |
| `MAX_DTE` | `75` | Maximum days to expiration. |
| `EXPIRATIONS_TO_SCAN` | `12` | Number of expirations to inspect per symbol. |
| `TARGET_PROFIT_PCT` | `0.45` | Default alert trigger for gains. |
| `STOP_LOSS_PCT` | `0.35` | Default alert trigger for losses. |

Tradier's official docs describe its options expirations endpoint and options chains endpoint, including optional Greeks/IV support via ORATS:

- [Tradier options expirations](https://docs.tradier.com/reference/brokerage-api-markets-get-options-expirations)
- [Tradier options chains](https://docs.tradier.com/reference/brokerage-api-markets-get-options-chains)
- [Tradier market data overview](https://docs.tradier.com/docs/market-data)

## How Recommendations Work

For each symbol, the scanner:

1. Pulls the current quote, available expirations, option chains, and recent daily prices.
2. Discards contracts with missing prices, stale or invalid IV, poor liquidity, excessive spreads, or unsuitable DTE.
3. Rejects internally inconsistent contracts, including strikes far outside a sane moneyness band.
4. Computes Greeks from real chain inputs.
5. Estimates a conservative entry limit near the bid/ask midpoint and a lower "patient entry" based on spread and recent underlying volatility.
6. Scores contracts by liquidity, spread quality, convexity, theta cost, moneyness, probability proxy, and upside trigger distance.
7. Emits alert triggers for entry, profit taking, stop loss, time decay, liquidity deterioration, and Greek drift.

## Example Output

```json
{
  "symbol": "AAPL",
  "strategy": "long_call",
  "contract": "AAPL260619C00200000",
  "entry_limit": 4.12,
  "patient_entry": 3.78,
  "sell_triggers": {
    "take_profit_price": 5.97,
    "stop_loss_price": 2.68,
    "theta_exit": "Exit if theta worsens below -0.08 per day",
    "time_exit": "Exit or roll with 14 DTE remaining"
  }
}
```

## Important Limits

- Options prices from free or delayed endpoints may not match your broker's executable quote.
- "Lowest possible entry" is modeled as a patient limit zone from real bid/ask and volatility context; no tool can know the true future low.
- "Maximum possible ROI" is not knowable in advance. The tool ranks asymmetric payoff opportunities and defines exits so the decision is repeatable.
- Always verify quotes, liquidity, and suitability with your broker before trading.
