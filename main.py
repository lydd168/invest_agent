"""CLI entry point for the Buffett multi-agent research pipeline."""

from __future__ import annotations

import argparse
from typing import List, Optional

from graph.orchestrator import run_pipeline
from pathlib import Path

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    # python-dotenv not installed or other non-fatal issue; proceed without .env autoload
    pass


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Buffett-style multi-agent equity research CLI",
    )
    parser.add_argument(
        "--sector",
        type=str,
        default=None,
        help="Optional sector focus when screening (e.g. Technology)",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Optional keyword query for the screener",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="Comma-separated tickers to force into the pipeline (e.g. AAPL,MSFT)",
    )
    parser.add_argument(
        "--news-window",
        type=int,
        default=14,
        help="Lookback window in days for the news agent",
    )
    parser.add_argument(
        "--max-news",
        type=int,
        default=30,
        help="Maximum number of news items to ingest per ticker",
    )
    parser.add_argument(
        "--reports-dir",
        type=str,
        default=None,
        help="Optional override for the reports output directory",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help="Optional cap on number of user-provided tickers to consider",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    tickers = None
    if args.tickers:
        tickers = [ticker.strip().upper() for ticker in args.tickers.split(",") if ticker.strip()]

    result_path = run_pipeline(
        {
            "sector": args.sector,
            "query": args.query,
            "tickers": tickers,
            "news_window_days": args.news_window,
            "max_news": args.max_news,
            "reports_dir": args.reports_dir,
            "max_candidates": args.max_candidates,
        }
    )

    print(f"Report generated at {result_path}")


if __name__ == "__main__":
    main()
