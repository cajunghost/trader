from __future__ import annotations

import json
import http.cookiejar
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any


class MarketDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class QuoteSnapshot:
    symbol: str
    price: float
    previous_close: float | None
    regular_market_time: int | None
    currency: str | None


@dataclass(frozen=True)
class OptionContract:
    symbol: str
    option_type: str
    contract_symbol: str
    expiration: int
    strike: float
    bid: float
    ask: float
    last_price: float
    implied_volatility: float
    volume: int
    open_interest: int
    in_the_money: bool

    @property
    def mid(self) -> float:
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return self.last_price

    @property
    def spread(self) -> float:
        return max(self.ask - self.bid, 0.0)


class YahooFinanceClient:
    base = "https://query1.finance.yahoo.com"

    def __init__(self, timeout: int = 12) -> None:
        self.timeout = timeout
        self._crumb: str | None = None
        self._cookies = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cookies))

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            params = dict(params or {})
            if path.startswith("/v7/finance/options"):
                params.setdefault("crumb", self._get_crumb())
            query = f"?{urllib.parse.urlencode(params)}" if params else ""
            request = urllib.request.Request(
                f"{self.base}{path}{query}",
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "application/json",
                },
            )
            with self._opener.open(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - network failure details vary
            raise MarketDataError(f"Yahoo Finance request failed for {path}: {exc}") from exc

    def _get_crumb(self) -> str:
        if self._crumb:
            return self._crumb
        seed_request = urllib.request.Request(
            "https://finance.yahoo.com/quote/AAPL/options",
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        )
        self._opener.open(seed_request, timeout=self.timeout).read()
        crumb_request = urllib.request.Request(
            "https://query2.finance.yahoo.com/v1/test/getcrumb",
            headers={"User-Agent": _USER_AGENT, "Accept": "text/plain"},
        )
        with self._opener.open(crumb_request, timeout=self.timeout) as response:
            crumb = response.read().decode("utf-8").strip()
        if not crumb or "<html" in crumb.lower():
            raise MarketDataError("Yahoo Finance did not return a usable crumb token")
        self._crumb = crumb
        return crumb

    def option_expirations(self, symbol: str) -> list[int]:
        result = self._option_result(symbol)
        expirations = result.get("expirationDates") or []
        if not expirations:
            raise MarketDataError(f"No option expirations returned for {symbol}")
        return [int(exp) for exp in expirations]

    def option_chain(self, symbol: str, expiration: int | None = None) -> tuple[QuoteSnapshot, list[OptionContract]]:
        result = self._option_result(symbol, expiration)
        quote = self._quote_from_result(symbol, result)
        options = result.get("options") or []
        contracts: list[OptionContract] = []
        for chain in options:
            contracts.extend(self._contracts(symbol, "call", int(chain["expirationDate"]), chain.get("calls") or []))
            contracts.extend(self._contracts(symbol, "put", int(chain["expirationDate"]), chain.get("puts") or []))
        return quote, contracts

    def quote(self, symbol: str) -> QuoteSnapshot:
        data = self._get_json(
            f"/v8/finance/chart/{urllib.parse.quote(symbol)}",
            {"range": "1d", "interval": "1m"},
        )
        result = (data.get("chart", {}).get("result") or [None])[0]
        if not result:
            raise MarketDataError(f"No quote chart returned for {symbol}")
        meta = result.get("meta") or {}
        timestamps = result.get("timestamp") or []
        price = (
            meta.get("regularMarketPrice")
            or meta.get("postMarketPrice")
            or meta.get("preMarketPrice")
            or meta.get("chartPreviousClose")
            or meta.get("previousClose")
        )
        if price is None:
            raise MarketDataError(f"No quote price returned for {symbol}")
        return QuoteSnapshot(
            symbol=symbol.upper(),
            price=float(price),
            previous_close=_optional_float(meta.get("chartPreviousClose") or meta.get("previousClose")),
            regular_market_time=_optional_int(meta.get("regularMarketTime") or (timestamps[-1] if timestamps else None)),
            currency=meta.get("currency"),
        )

    def recent_closes(self, symbol: str, range_: str = "6mo") -> list[float]:
        data = self._get_json(f"/v8/finance/chart/{urllib.parse.quote(symbol)}", {"range": range_, "interval": "1d"})
        result = (data.get("chart", {}).get("result") or [None])[0]
        if not result:
            raise MarketDataError(f"No chart data returned for {symbol}")
        quote = (result.get("indicators", {}).get("quote") or [{}])[0]
        closes = quote.get("close") or []
        return [float(close) for close in closes if close is not None and float(close) > 0]

    def _option_result(self, symbol: str, expiration: int | None = None) -> dict[str, Any]:
        params = {"date": expiration} if expiration else None
        data = self._get_json(f"/v7/finance/options/{urllib.parse.quote(symbol)}", params)
        error = data.get("optionChain", {}).get("error")
        if error:
            raise MarketDataError(f"Yahoo Finance error for {symbol}: {error}")
        result = (data.get("optionChain", {}).get("result") or [None])[0]
        if not result:
            raise MarketDataError(f"No options data returned for {symbol}")
        return result

    def _quote_from_result(self, symbol: str, result: dict[str, Any]) -> QuoteSnapshot:
        quote = result.get("quote") or {}
        price = quote.get("regularMarketPrice") or quote.get("postMarketPrice") or quote.get("preMarketPrice")
        if price is None:
            raise MarketDataError(f"No real quote price returned for {symbol}")
        return QuoteSnapshot(
            symbol=symbol.upper(),
            price=float(price),
            previous_close=_optional_float(quote.get("regularMarketPreviousClose")),
            regular_market_time=_optional_int(quote.get("regularMarketTime")),
            currency=quote.get("currency"),
        )

    def _contracts(
        self,
        symbol: str,
        option_type: str,
        expiration: int,
        raw_contracts: list[dict[str, Any]],
    ) -> list[OptionContract]:
        contracts = []
        for raw in raw_contracts:
            try:
                contract = OptionContract(
                    symbol=symbol.upper(),
                    option_type=option_type,
                    contract_symbol=str(raw["contractSymbol"]),
                    expiration=expiration,
                    strike=float(raw["strike"]),
                    bid=float(raw.get("bid") or 0),
                    ask=float(raw.get("ask") or 0),
                    last_price=float(raw.get("lastPrice") or 0),
                    implied_volatility=float(raw.get("impliedVolatility") or 0),
                    volume=int(raw.get("volume") or 0),
                    open_interest=int(raw.get("openInterest") or 0),
                    in_the_money=bool(raw.get("inTheMoney")),
                )
            except (KeyError, TypeError, ValueError):
                continue
            contracts.append(contract)
        return contracts


def days_to_expiration(expiration: int, now: datetime | None = None) -> int:
    current = now or datetime.now(UTC)
    expiry = datetime.fromtimestamp(expiration, UTC)
    return max((expiry.date() - current.date()).days, 0)


def quote_age_minutes(quote: QuoteSnapshot) -> float | None:
    if not quote.regular_market_time:
        return None
    return max((time.time() - quote.regular_market_time) / 60.0, 0.0)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


class TradierClient:
    def __init__(self, token: str, base_url: str = "https://api.tradier.com/v1", timeout: int = 12) -> None:
        if not token:
            raise MarketDataError("TRADIER_TOKEN is required when MARKET_DATA_PROVIDER=tradier")
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = f"?{urllib.parse.urlencode(params or {})}" if params else ""
        request = urllib.request.Request(
            f"{self.base_url}{path}{query}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "User-Agent": "option-ai-tool/0.1 real-data scanner",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - network failure details vary
            raise MarketDataError(f"Tradier request failed for {path}: {exc}") from exc

    def option_expirations(self, symbol: str) -> list[int]:
        data = self._get_json(
            "/markets/options/expirations",
            {"symbol": symbol.upper(), "includeAllRoots": "true", "strikes": "false"},
        )
        expirations = data.get("expirations", {}).get("date") or []
        if isinstance(expirations, str):
            expirations = [expirations]
        if not expirations:
            raise MarketDataError(f"No Tradier option expirations returned for {symbol}")
        return [_date_to_epoch(expiration) for expiration in expirations]

    def option_chain(self, symbol: str, expiration: int | None = None) -> tuple[QuoteSnapshot, list[OptionContract]]:
        if expiration is None:
            expiration = self.option_expirations(symbol)[0]
        expiration_date = datetime.fromtimestamp(expiration, UTC).date().isoformat()
        quote = self._quote(symbol)
        data = self._get_json(
            "/markets/options/chains",
            {"symbol": symbol.upper(), "expiration": expiration_date, "greeks": "true"},
        )
        raw_options = data.get("options", {}).get("option") or []
        if isinstance(raw_options, dict):
            raw_options = [raw_options]
        contracts = [contract for raw in raw_options if (contract := self._contract(symbol, expiration, raw))]
        return quote, contracts

    def recent_closes(self, symbol: str, range_: str = "6mo") -> list[float]:
        end = date.today()
        start = end - timedelta(days=190)
        data = self._get_json(
            "/markets/history",
            {"symbol": symbol.upper(), "interval": "daily", "start": start.isoformat(), "end": end.isoformat()},
        )
        days = data.get("history", {}).get("day") or []
        if isinstance(days, dict):
            days = [days]
        closes = [float(day["close"]) for day in days if day.get("close")]
        if not closes:
            raise MarketDataError(f"No Tradier historical closes returned for {symbol}")
        return closes

    def quote(self, symbol: str) -> QuoteSnapshot:
        return self._quote(symbol)

    def _quote(self, symbol: str) -> QuoteSnapshot:
        data = self._get_json("/markets/quotes", {"symbols": symbol.upper()})
        quote = data.get("quotes", {}).get("quote")
        if isinstance(quote, list):
            quote = quote[0] if quote else None
        if not quote:
            raise MarketDataError(f"No Tradier quote returned for {symbol}")
        price = quote.get("last") or quote.get("bid") or quote.get("ask") or quote.get("prevclose")
        if price is None:
            raise MarketDataError(f"No Tradier quote price returned for {symbol}")
        return QuoteSnapshot(
            symbol=symbol.upper(),
            price=float(price),
            previous_close=_optional_float(quote.get("prevclose")),
            regular_market_time=None,
            currency="USD",
        )

    def _contract(self, symbol: str, expiration: int, raw: dict[str, Any]) -> OptionContract | None:
        try:
            greeks = raw.get("greeks") or {}
            iv = greeks.get("mid_iv") or greeks.get("smv_vol") or raw.get("iv") or 0
            iv = float(iv)
            if iv > 3:
                iv = iv / 100.0
            return OptionContract(
                symbol=symbol.upper(),
                option_type=str(raw["option_type"]).lower(),
                contract_symbol=str(raw["symbol"]),
                expiration=expiration,
                strike=float(raw["strike"]),
                bid=float(raw.get("bid") or 0),
                ask=float(raw.get("ask") or 0),
                last_price=float(raw.get("last") or 0),
                implied_volatility=iv,
                volume=int(raw.get("volume") or 0),
                open_interest=int(raw.get("open_interest") or 0),
                in_the_money=bool(raw.get("in_the_money", False)),
            )
        except (KeyError, TypeError, ValueError):
            return None


def _date_to_epoch(value: str) -> int:
    parsed = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    return int(parsed.timestamp())


_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36 "
    "option-ai-tool/0.1"
)
