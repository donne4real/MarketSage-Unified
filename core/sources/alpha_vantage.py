"""Alpha Vantage API client (free tier: 25 req/day, 5 req/min)."""

from __future__ import annotations

import os
from typing import Optional
import httpx
import pandas as pd

BASE_URL = "https://www.alphavantage.co/query"


def _api_key() -> Optional[str]:
    return os.getenv("ALPHA_VANTAGE_KEY")


def is_configured() -> bool:
    key = _api_key()
    return bool(key and not key.startswith("your"))


def _request(params: dict, timeout: int = 15) -> dict:
    if not is_configured():
        raise RuntimeError("ALPHA_VANTAGE_KEY not configured")
    payload = {**params, "apikey": _api_key()}
    resp = httpx.get(BASE_URL, params=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    for err_key in ("Note", "Information", "Error Message"):
        if err_key in data:
            raise RuntimeError(f"Alpha Vantage ({err_key}): {data[err_key]}")
    return data


def get_overview(ticker: str) -> dict:
    data = _request({"function": "OVERVIEW", "symbol": ticker.upper()})
    if not data or "Symbol" not in data:
        raise RuntimeError(f"Alpha Vantage OVERVIEW empty for {ticker}")
    return data


def get_daily_prices(ticker: str, outputsize: str = "compact") -> pd.DataFrame:
    data = _request(
        {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker.upper(),
            "outputsize": outputsize,
        }
    )
    series = data.get("Time Series (Daily)")
    if not series:
        raise RuntimeError(f"Alpha Vantage: no daily series for {ticker}")
    rows = []
    for dt_str, vals in series.items():
        rows.append(
            {
                "Date": pd.Timestamp(dt_str),
                "Open": float(vals.get("1. open", 0)),
                "High": float(vals.get("2. high", 0)),
                "Low": float(vals.get("3. low", 0)),
                "Close": float(vals.get("5. adjusted close", vals.get("4. close", 0))),
                "Volume": int(float(vals.get("6. volume", vals.get("5. volume", 0)))),
            }
        )
    return pd.DataFrame(rows).set_index("Date").sort_index()


def get_fundamentals(ticker: str) -> dict[str, list[dict]]:
    sym = ticker.upper()
    return {
        "income_statement": _request({"function": "INCOME_STATEMENT", "symbol": sym}).get("quarterlyReports", []),
        "balance_sheet": _request({"function": "BALANCE_SHEET", "symbol": sym}).get("quarterlyReports", []),
        "cash_flow": _request({"function": "CASH_FLOW", "symbol": sym}).get("quarterlyReports", []),
    }


def get_etf_profile(ticker: str) -> dict:
    return _request({"function": "ETF_PROFILE", "symbol": ticker.upper()}) or {}
