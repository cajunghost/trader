from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .scanner import scan_symbols


INDEX = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Options Scanner</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 0; background: #f7f8fa; color: #17202a; }
    header { padding: 24px; background: #101820; color: white; }
    main { max-width: 1180px; margin: 0 auto; padding: 24px; }
    form { display: flex; gap: 8px; margin-bottom: 20px; }
    input { flex: 1; padding: 10px 12px; font-size: 16px; }
    button { padding: 10px 14px; font-size: 16px; cursor: pointer; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }
    .card { background: white; border: 1px solid #dde2e7; border-radius: 8px; padding: 16px; }
    .score { font-size: 28px; font-weight: 700; }
    .muted { color: #65717f; }
    dl { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 12px; }
    dt { color: #65717f; }
    dd { margin: 0; font-weight: 600; }
    pre { white-space: pre-wrap; background: #f1f3f5; padding: 12px; border-radius: 6px; }
  </style>
</head>
<body>
  <header><h1>AI Options Scanner</h1><p>Real quote/options data, computed Greeks, ranked entries, and sell triggers.</p></header>
  <main>
    <form id="scan-form">
      <input id="symbols" value="{symbols}" aria-label="Symbols">
      <button type="submit">Scan</button>
    </form>
    <div id="results" class="grid"></div>
  </main>
  <script>
    const form = document.getElementById('scan-form');
    const symbols = document.getElementById('symbols');
    const results = document.getElementById('results');
    async function scan() {
      results.innerHTML = '<p>Scanning real market data...</p>';
      const response = await fetch('/api/scan?symbols=' + encodeURIComponent(symbols.value));
      const payload = await response.json();
      results.innerHTML = '';
      for (const item of payload) {
        if (item.errors.length) {
          results.insertAdjacentHTML('beforeend', `<section class="card"><h2>${item.symbol}</h2><pre>${item.errors.join('\\n')}</pre></section>`);
          continue;
        }
        if (!item.recommendations.length) {
          results.insertAdjacentHTML('beforeend', `<section class="card"><h2>${item.symbol}</h2><p class="muted">No qualified contracts under the current real-data filters.</p></section>`);
          continue;
        }
        for (const rec of item.recommendations) {
          results.insertAdjacentHTML('beforeend', `
            <section class="card">
              <div class="muted">${rec.symbol} ${rec.strategy}</div>
              <h2>${rec.contract}</h2>
              <div class="score">${rec.score}</div>
              <dl>
                <dt>Expiration</dt><dd>${rec.expiration} (${rec.dte} DTE)</dd>
                <dt>Strike</dt><dd>${rec.strike}</dd>
                <dt>Bid / Ask</dt><dd>${rec.bid} / ${rec.ask}</dd>
                <dt>Entry</dt><dd>${rec.alerts.entry_limit}</dd>
                <dt>Patient</dt><dd>${rec.alerts.patient_entry}</dd>
                <dt>Take Profit</dt><dd>${rec.alerts.take_profit_price}</dd>
                <dt>Stop</dt><dd>${rec.alerts.stop_loss_price}</dd>
                <dt>Delta</dt><dd>${rec.delta}</dd>
                <dt>Theta</dt><dd>${rec.theta}</dd>
                <dt>Gamma</dt><dd>${rec.gamma}</dd>
                <dt>IV</dt><dd>${(rec.implied_volatility * 100).toFixed(1)}%</dd>
              </dl>
              <pre>${rec.rationale.join('\\n')}</pre>
            </section>
          `);
        }
      }
    }
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      history.replaceState(null, '', '/?symbols=' + encodeURIComponent(symbols.value));
      scan();
    });
    scan();
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        symbols = params.get("symbols", ["AAPL,MSFT,NVDA"])[0]
        if parsed.path == "/api/scan":
            payload = [result.to_dict() for result in scan_symbols(symbols.split(","))]
            self._send_json(payload)
            return
        self._send_html(INDEX.replace("{symbols}", symbols))

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, payload: object) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(200)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AI Options Scanner web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving AI Options Scanner at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
