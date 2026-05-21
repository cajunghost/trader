from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .config import ScannerConfig
from .database import TraderDatabase
from .performance import mark_all, mark_recommendation
from .research import suggest_tickers
from .scanner import _client_from_config, scan_symbols


INDEX = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trader</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #14171f;
      --muted: #657080;
      --line: #dfe5ec;
      --panel: #ffffff;
      --bg: #f5f7fa;
      --accent: #0f766e;
      --accent-dark: #115e59;
      --warn: #9f1239;
      --good: #166534;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      background: #111827;
      color: white;
      padding: 18px 16px 14px;
      position: sticky;
      top: 0;
      z-index: 3;
      border-bottom: 1px solid #243044;
    }
    .topbar {
      align-items: center;
      display: flex;
      gap: 12px;
      justify-content: space-between;
      margin: 0 auto;
      max-width: 1180px;
    }
    h1 { font-size: 22px; margin: 0; }
    h2 { font-size: 18px; margin: 0 0 12px; }
    h3 { font-size: 16px; margin: 0 0 8px; }
    main {
      display: grid;
      gap: 14px;
      margin: 0 auto;
      max-width: 1180px;
      padding: 14px;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }
    form {
      display: grid;
      gap: 10px;
      grid-template-columns: 1fr 120px auto;
    }
    label {
      color: var(--muted);
      display: block;
      font-size: 12px;
      font-weight: 700;
      margin: 0 0 4px;
      text-transform: uppercase;
    }
    input {
      border: 1px solid var(--line);
      border-radius: 7px;
      font-size: 16px;
      min-height: 42px;
      padding: 9px 10px;
      width: 100%;
    }
    button {
      background: var(--accent);
      border: 0;
      border-radius: 7px;
      color: white;
      cursor: pointer;
      font-size: 15px;
      font-weight: 700;
      min-height: 42px;
      padding: 9px 12px;
    }
    button.secondary { background: #344054; }
    button.ghost {
      background: transparent;
      border: 1px solid var(--line);
      color: var(--ink);
    }
    button:disabled { cursor: wait; opacity: 0.65; }
    .layout {
      display: grid;
      gap: 14px;
      grid-template-columns: minmax(0, 1fr) 360px;
    }
    .stack { display: grid; gap: 12px; }
    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .chip {
      align-items: center;
      background: #eef6f4;
      border: 1px solid #b9d8d2;
      border-radius: 999px;
      color: #164e48;
      display: inline-flex;
      gap: 6px;
      min-height: 34px;
      padding: 7px 10px;
    }
    .chip button {
      background: transparent;
      color: inherit;
      min-height: 0;
      padding: 0;
    }
    .grid {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }
    .rec {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
    }
    .headline {
      align-items: start;
      display: flex;
      gap: 10px;
      justify-content: space-between;
    }
    .score {
      background: #ecfdf3;
      border-radius: 6px;
      color: var(--good);
      font-weight: 800;
      padding: 6px 8px;
    }
    .meta {
      color: var(--muted);
      font-size: 13px;
    }
    dl {
      display: grid;
      gap: 7px 10px;
      grid-template-columns: 1fr 1fr;
      margin: 10px 0 0;
    }
    dt { color: var(--muted); font-size: 12px; }
    dd { font-weight: 700; margin: 0; text-align: right; }
    table {
      border-collapse: collapse;
      width: 100%;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      font-size: 14px;
      padding: 9px 8px;
      text-align: left;
      vertical-align: middle;
    }
    th { color: var(--muted); font-size: 12px; text-transform: uppercase; }
    td input { max-width: 84px; min-height: 34px; padding: 6px; }
    .positive { color: var(--good); font-weight: 800; }
    .negative { color: var(--warn); font-weight: 800; }
    .status {
      background: #f2f4f7;
      border-radius: 6px;
      color: #344054;
      display: inline-block;
      font-size: 12px;
      padding: 4px 7px;
    }
    .muted { color: var(--muted); }
    .row-actions { display: flex; gap: 8px; justify-content: flex-end; }
    .toast {
      background: #111827;
      border-radius: 7px;
      bottom: 16px;
      color: white;
      left: 16px;
      max-width: calc(100% - 32px);
      padding: 10px 12px;
      position: fixed;
      transform: translateY(90px);
      transition: transform 160ms ease;
      z-index: 5;
    }
    .toast.show { transform: translateY(0); }
    @media (max-width: 860px) {
      .layout { grid-template-columns: 1fr; }
      form { grid-template-columns: 1fr; }
      header { position: static; }
      .table-wrap { overflow-x: auto; }
      table { min-width: 760px; }
    }
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <h1>Trader</h1>
      <button class="secondary" id="refresh-all" type="button">Refresh Marks</button>
    </div>
  </header>
  <main>
    <section>
      <form id="scan-form">
        <div>
          <label for="symbols">Tickers</label>
          <input id="symbols" autocomplete="off" value="AAPL,MSFT,NVDA">
        </div>
        <div>
          <label for="contracts">Contracts</label>
          <input id="contracts" type="number" min="1" step="1" value="1">
        </div>
        <div>
          <label>&nbsp;</label>
          <button id="scan-button" type="submit">Scan</button>
        </div>
      </form>
    </section>
    <div class="layout">
      <div class="stack">
        <section>
          <div class="headline">
            <h2>Scan Results</h2>
            <span class="meta" id="scan-status"></span>
          </div>
          <div id="results" class="grid"></div>
        </section>
        <section>
          <div class="headline">
            <h2>Performance Database</h2>
            <span class="meta" id="db-status"></span>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Position</th>
                  <th>Contracts</th>
                  <th>Entry</th>
                  <th>Target</th>
                  <th>Stop</th>
                  <th>Mark</th>
                  <th>P/L</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody id="portfolio"></tbody>
            </table>
          </div>
        </section>
      </div>
      <aside class="stack">
        <section>
          <div class="headline">
            <h2>Suggested Tickers</h2>
            <button class="ghost" id="load-suggestions" type="button">Update</button>
          </div>
          <div id="suggestions" class="chips"></div>
        </section>
        <section>
          <h2>Recent Research</h2>
          <div id="research-log" class="stack"></div>
        </section>
      </aside>
    </div>
  </main>
  <div id="toast" class="toast"></div>
  <script>
    const symbolsEl = document.getElementById('symbols');
    const contractsEl = document.getElementById('contracts');
    const resultsEl = document.getElementById('results');
    const portfolioEl = document.getElementById('portfolio');
    const suggestionsEl = document.getElementById('suggestions');
    const researchLogEl = document.getElementById('research-log');
    const scanStatusEl = document.getElementById('scan-status');
    const dbStatusEl = document.getElementById('db-status');
    const scanButton = document.getElementById('scan-button');
    const toastEl = document.getElementById('toast');

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[char]));
    }
    function money(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
      return '$' + Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    function pct(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
      return (Number(value) * 100).toFixed(1) + '%';
    }
    function signed(value) {
      const cls = Number(value) >= 0 ? 'positive' : 'negative';
      return `<span class="${cls}">${money(value)}</span>`;
    }
    function showToast(message) {
      toastEl.textContent = message;
      toastEl.classList.add('show');
      setTimeout(() => toastEl.classList.remove('show'), 2200);
    }
    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { 'Content-Type': 'application/json' },
        ...options
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || 'request failed');
      return payload;
    }
    function renderRecommendation(rec) {
      return `
        <article class="rec">
          <div class="headline">
            <div>
              <h3>${escapeHtml(rec.symbol)} ${escapeHtml(rec.strategy)}</h3>
              <div class="meta">${escapeHtml(rec.contract)}</div>
            </div>
            <span class="score">${escapeHtml(rec.score)}</span>
          </div>
          <dl>
            <dt>Expiration</dt><dd>${escapeHtml(rec.expiration)} (${escapeHtml(rec.dte)} DTE)</dd>
            <dt>Strike</dt><dd>${money(rec.strike)}</dd>
            <dt>Bid / Ask</dt><dd>${money(rec.bid)} / ${money(rec.ask)}</dd>
            <dt>Entry</dt><dd>${money(rec.alerts.entry_limit)}</dd>
            <dt>Patient</dt><dd>${money(rec.alerts.patient_entry)}</dd>
            <dt>Target</dt><dd>${money(rec.alerts.take_profit_price)}</dd>
            <dt>Stop</dt><dd>${money(rec.alerts.stop_loss_price)}</dd>
            <dt>Cost</dt><dd>${money(rec.estimated_cost)}</dd>
            <dt>Target Profit</dt><dd>${money(rec.target_profit)}</dd>
            <dt>Delta</dt><dd>${escapeHtml(rec.delta)}</dd>
            <dt>Theta</dt><dd>${escapeHtml(rec.theta)}</dd>
            <dt>IV</dt><dd>${pct(rec.implied_volatility)}</dd>
          </dl>
        </article>
      `;
    }
    async function scan(event) {
      event?.preventDefault();
      scanButton.disabled = true;
      scanStatusEl.textContent = 'Scanning';
      resultsEl.innerHTML = '';
      try {
        const qs = new URLSearchParams({
          symbols: symbolsEl.value,
          contracts: contractsEl.value || '1',
          save: '1'
        });
        const payload = await api('/api/scan?' + qs.toString());
        const html = [];
        for (const item of payload.results) {
          if (item.errors.length) {
            html.push(`<article class="rec"><h3>${escapeHtml(item.symbol)}</h3><p class="negative">${escapeHtml(item.errors.join('\\n'))}</p></article>`);
            continue;
          }
          if (!item.recommendations.length) {
            html.push(`<article class="rec"><h3>${escapeHtml(item.symbol)}</h3><p class="muted">No qualified contracts under current filters.</p></article>`);
            continue;
          }
          item.recommendations.forEach(rec => html.push(renderRecommendation(rec)));
        }
        resultsEl.innerHTML = html.join('');
        scanStatusEl.textContent = `${payload.saved_count} saved`;
        showToast('Scan saved');
        await loadPortfolio();
      } catch (error) {
        scanStatusEl.textContent = 'Error';
        showToast(error.message);
      } finally {
        scanButton.disabled = false;
      }
    }
    async function loadSuggestions() {
      suggestionsEl.innerHTML = '<span class="meta">Loading</span>';
      researchLogEl.innerHTML = '';
      try {
        const payload = await api('/api/suggestions?limit=10');
        suggestionsEl.innerHTML = payload.suggestions.map(item => `
          <span class="chip">
            <button type="button" data-symbol="${escapeHtml(item.symbol)}">${escapeHtml(item.symbol)}</button>
            <span>${pct(item.change_pct)}</span>
          </span>
        `).join('');
        researchLogEl.innerHTML = payload.suggestions.slice(0, 6).map(item => `
          <article class="rec">
            <div class="headline">
              <h3>${escapeHtml(item.symbol)}</h3>
              <span class="score">${escapeHtml(item.score)}</span>
            </div>
            <dl>
              <dt>Price</dt><dd>${money(item.price)}</dd>
              <dt>Move</dt><dd>${pct(item.change_pct)}</dd>
              <dt>5 Day</dt><dd>${pct(item.momentum_5d)}</dd>
              <dt>Realized Vol</dt><dd>${pct(item.realized_volatility)}</dd>
            </dl>
            <p class="meta">${escapeHtml(item.reasons.join(' | '))}</p>
          </article>
        `).join('');
        suggestionsEl.querySelectorAll('button').forEach(button => {
          button.addEventListener('click', () => {
            symbolsEl.value = button.dataset.symbol;
            scan();
          });
        });
      } catch (error) {
        suggestionsEl.innerHTML = `<span class="negative">${escapeHtml(error.message)}</span>`;
      }
    }
    async function loadPortfolio() {
      const payload = await api('/api/recommendations');
      dbStatusEl.textContent = `${payload.recommendations.length} rows`;
      portfolioEl.innerHTML = payload.recommendations.map(row => `
        <tr>
          <td>
            <strong>${escapeHtml(row.symbol)} ${escapeHtml(row.strategy)}</strong><br>
            <span class="meta">${escapeHtml(row.contract)}</span>
          </td>
          <td><input type="number" min="1" step="1" value="${escapeHtml(row.contracts)}" data-id="${escapeHtml(row.id)}"></td>
          <td>${money(row.entry_limit)}<br><span class="meta">${money(row.estimated_cost)}</span></td>
          <td>${money(row.take_profit_price)}<br><span class="positive">${money(row.target_profit)}</span></td>
          <td>${money(row.stop_loss_price)}<br><span class="negative">${money(row.stop_loss)}</span></td>
          <td>${money(row.current_mid)}</td>
          <td>${row.current_profit === undefined ? '-' : signed(row.current_profit)}</td>
          <td><span class="status">${escapeHtml(row.status || 'saved')}</span></td>
          <td class="row-actions"><button class="ghost" type="button" data-mark="${escapeHtml(row.id)}">Mark</button></td>
        </tr>
      `).join('');
      portfolioEl.querySelectorAll('input').forEach(input => {
        input.addEventListener('change', async () => {
          await api('/api/recommendations/' + input.dataset.id, {
            method: 'POST',
            body: JSON.stringify({ contracts: Number(input.value || 1) })
          });
          await loadPortfolio();
        });
      });
      portfolioEl.querySelectorAll('button[data-mark]').forEach(button => {
        button.addEventListener('click', async () => {
          button.disabled = true;
          await api('/api/recommendations/' + button.dataset.mark + '/mark', { method: 'POST' });
          await loadPortfolio();
        });
      });
    }
    async function refreshAll() {
      const button = document.getElementById('refresh-all');
      button.disabled = true;
      try {
        await api('/api/performance/refresh', { method: 'POST' });
        await loadPortfolio();
        showToast('Marks refreshed');
      } catch (error) {
        showToast(error.message);
      } finally {
        button.disabled = false;
      }
    }
    document.getElementById('scan-form').addEventListener('submit', scan);
    document.getElementById('load-suggestions').addEventListener('click', loadSuggestions);
    document.getElementById('refresh-all').addEventListener('click', refreshAll);
    loadSuggestions();
    loadPortfolio();
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/scan":
                self._send_json(self._scan(params))
            elif parsed.path == "/api/suggestions":
                self._send_json(self._suggestions(params))
            elif parsed.path == "/api/recommendations":
                self._send_json({"recommendations": _database().list_recommendations()})
            elif parsed.path == "/api/research":
                self._send_json({"suggestions": _database().list_suggestions()})
            else:
                self._send_html(INDEX)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/performance/refresh":
                payload = mark_all(_database(), _client(), limit=25)
                self._send_json({"marks": payload})
                return
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) == 3 and parts[:2] == ["api", "recommendations"]:
                body = self._read_json()
                row = _database().update_contracts(int(parts[2]), int(body.get("contracts", 1)))
                if not row:
                    self._send_json({"error": "recommendation not found"}, status=404)
                    return
                self._send_json({"recommendation": row})
                return
            if len(parts) == 4 and parts[:2] == ["api", "recommendations"] and parts[3] == "mark":
                self._send_json(mark_recommendation(_database(), _client(), int(parts[2])))
                return
            self._send_json({"error": "not found"}, status=404)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _scan(self, params: dict[str, list[str]]) -> dict[str, object]:
        symbols = params.get("symbols", ["AAPL,MSFT,NVDA"])[0]
        contracts = max(_int_param(params, "contracts", 1), 1)
        save = params.get("save", ["1"])[0] != "0"
        results = scan_symbols(symbols.replace(",", " ").split(), config=_config(), client=_client(), max_results_per_symbol=8)
        payload = []
        saved_count = 0
        for result in results:
            recommendations = result.recommendations
            saved_rows = _database().save_recommendations(recommendations, contracts=contracts) if save else []
            saved_count += len(saved_rows)
            rendered = []
            for index, rec in enumerate(recommendations):
                item = rec.to_dict()
                item.update(_potential_from_recommendation(item, contracts))
                if index < len(saved_rows):
                    item["database_id"] = saved_rows[index]["id"]
                rendered.append(item)
            payload.append({"symbol": result.symbol, "recommendations": rendered, "errors": result.errors})
        return {"results": payload, "saved_count": saved_count}

    def _suggestions(self, params: dict[str, list[str]]) -> dict[str, object]:
        limit = _int_param(params, "limit", 10)
        suggestions, errors = suggest_tickers(_client(), config=_config(), limit=limit)
        rendered = [suggestion.to_dict() for suggestion in suggestions]
        _database().save_suggestions(rendered)
        return {"suggestions": rendered, "errors": errors}

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _config() -> ScannerConfig:
    return ScannerConfig()


def _database() -> TraderDatabase:
    return TraderDatabase(_config().trader_db_path)


def _client():
    return _client_from_config(_config())


def _int_param(params: dict[str, list[str]], name: str, default: int) -> int:
    try:
        return int(params.get(name, [str(default)])[0])
    except ValueError:
        return default


def _potential_from_recommendation(recommendation: dict[str, object], contracts: int) -> dict[str, float]:
    alerts = recommendation["alerts"]
    entry = float(alerts["entry_limit"])
    target = float(alerts["take_profit_price"])
    stop = float(alerts["stop_loss_price"])
    count = max(int(contracts), 1)
    cost = entry * 100 * count
    return {
        "estimated_cost": round(cost, 2),
        "target_value": round(target * 100 * count, 2),
        "target_profit": round((target - entry) * 100 * count, 2),
        "stop_value": round(stop * 100 * count, 2),
        "stop_loss": round((stop - entry) * 100 * count, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Trader mobile web app.")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8080")))
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving Trader at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
