#!/usr/bin/env python3
"""
Fetch live AI company stock data via yfinance (Yahoo Finance).

Companies list sourced from:
  https://companiesmarketcap.com/artificial-intelligence/largest-ai-companies-by-marketcap/

ETF pulse: BOTZ · AIQ · ARKQ · ROBO
"""

import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
MARKETS_FILE = os.path.join(DATA_DIR, "markets.json")
CACHE_TTL_MINUTES = 15

# Top 10 AI companies by market cap — companiesmarketcap.com/artificial-intelligence
AI_COMPANIES = [
    {"ticker": "NVDA",  "name": "NVIDIA",   "rank": 1},
    {"ticker": "MSFT",  "name": "Microsoft","rank": 2},
    {"ticker": "AAPL",  "name": "Apple",    "rank": 3},
    {"ticker": "GOOGL", "name": "Alphabet", "rank": 4},
    {"ticker": "AMZN",  "name": "Amazon",   "rank": 5},
    {"ticker": "META",  "name": "Meta",     "rank": 6},
    {"ticker": "TSM",   "name": "TSMC",     "rank": 7},
    {"ticker": "AVGO",  "name": "Broadcom", "rank": 8},
    {"ticker": "ORCL",  "name": "Oracle",   "rank": 9},
    {"ticker": "PLTR",  "name": "Palantir", "rank": 10},
]

AI_ETFS = [
    {"ticker": "BOTZ", "name": "Global X Robotics & AI"},
    {"ticker": "AIQ",  "name": "Global X AI & Big Data"},
    {"ticker": "ARKQ", "name": "ARK Autonomous Tech"},
    {"ticker": "ROBO", "name": "Robo Global Robotics"},
]


def fmt_cap(value) -> str:
    if not value:
        return "N/A"
    v = float(value)
    if v >= 1e12:
        return f"${v / 1e12:.2f}T"
    if v >= 1e9:
        return f"${v / 1e9:.1f}B"
    return f"${v / 1e6:.0f}M"


def fetch_markets() -> dict:
    import yfinance as yf

    all_tickers = [c["ticker"] for c in AI_COMPANIES] + [e["ticker"] for e in AI_ETFS]
    raw = yf.download(
        tickers=all_tickers,
        period="2d",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    # Also grab fast_info for market cap and current price
    ticker_objects = {t: yf.Ticker(t) for t in all_tickers}

    def get_info(ticker):
        try:
            fi = ticker_objects[ticker].fast_info
            return {
                "price": round(float(fi.last_price or 0), 2),
                "prev_close": round(float(fi.previous_close or 0), 2),
                "market_cap": fi.market_cap,
                "week52_high": round(float(fi.year_high or 0), 2),
                "week52_low": round(float(fi.year_low or 0), 2),
                "currency": getattr(fi, "currency", "USD"),
            }
        except Exception:
            return {"price": 0, "prev_close": 0, "market_cap": 0,
                    "week52_high": 0, "week52_low": 0, "currency": "USD"}

    stocks = []
    for company in AI_COMPANIES:
        t = company["ticker"]
        info = get_info(t)
        price = info["price"]
        prev = info["prev_close"] or price
        change = round(price - prev, 2)
        change_pct = round((change / prev * 100) if prev else 0, 2)
        stocks.append({
            "ticker": t,
            "name": company["name"],
            "rank": company["rank"],
            "price": price,
            "change": change,
            "change_pct": change_pct,
            "market_cap": fmt_cap(info["market_cap"]),
            "market_cap_raw": info["market_cap"] or 0,
            "week52_high": info["week52_high"],
            "week52_low": info["week52_low"],
            "currency": info["currency"],
        })

    etfs = []
    for etf in AI_ETFS:
        t = etf["ticker"]
        info = get_info(t)
        price = info["price"]
        prev = info["prev_close"] or price
        change_pct = round(((price - prev) / prev * 100) if prev else 0, 2)
        etfs.append({
            "ticker": t,
            "name": etf["name"],
            "price": price,
            "change_pct": change_pct,
            "change": round(price - prev, 2),
        })

    result = {
        "last_updated": datetime.now().isoformat(),
        "stocks": stocks,
        "etfs": etfs,
        "source_companies": "companiesmarketcap.com/artificial-intelligence",
        "source_prices": "Yahoo Finance",
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MARKETS_FILE, "w") as f:
        json.dump(result, f, indent=2)

    return result


def load_markets() -> dict:
    if os.path.exists(MARKETS_FILE):
        try:
            with open(MARKETS_FILE) as f:
                data = json.load(f)
            last = datetime.fromisoformat(data.get("last_updated", "2020-01-01"))
            if (datetime.now() - last).total_seconds() / 60 < CACHE_TTL_MINUTES:
                return data
        except Exception:
            pass
    return fetch_markets()


if __name__ == "__main__":
    data = fetch_markets()
    print(f"Fetched {len(data['stocks'])} stocks, {len(data['etfs'])} ETFs\n")
    for s in data["stocks"]:
        arrow = "▲" if s["change_pct"] >= 0 else "▼"
        print(f"  {s['rank']:2}. {s['name']:12} ({s['ticker']:5}) "
              f"${s['price']:>10,.2f}  {arrow}{abs(s['change_pct']):.2f}%  {s['market_cap']}")
    print()
    for e in data["etfs"]:
        arrow = "▲" if e["change_pct"] >= 0 else "▼"
        print(f"  {e['ticker']:5}  ${e['price']:.2f}  {arrow}{abs(e['change_pct']):.2f}%")
