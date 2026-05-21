from __future__ import annotations

import argparse
import json

from .scanner import scan_symbols


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan stocks for real-data options opportunities.")
    parser.add_argument("--symbols", nargs="+", required=True, help="Stock symbols to scan, such as AAPL MSFT NVDA")
    parser.add_argument("--max-results", type=int, default=10, help="Recommendations per symbol")
    args = parser.parse_args()

    results = scan_symbols(args.symbols, max_results_per_symbol=args.max_results)
    print(json.dumps([result.to_dict() for result in results], indent=2))


if __name__ == "__main__":
    main()

