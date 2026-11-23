"""Twelve Data API client (free tier: 800 req/day, 8 req/min)."""

from __future__ import annotations

import os
from typing import Optional
import httpx
import pandas as pd

BASE_URL = "https://api.twelvedata.com"


def _api_key() -> Optional[str]:
    return os.getenv("TWELVE_DATA_KEY")


def is_configured() -> bool:
    key = _api_key()
    return bool(key and not key.startswith("your"))


def _request(endpoint: str, params: dict, timeout: int = 15) -> dict:
    if not is_configured():
        raise RuntimeError("TWELVE_DATA_KEY not configured")
    payload = {**params, "apikey": _api_key()}
    resp = httpx.get(f"{BASE_URL}/{endpoint}", params=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Twelve Data error: {data.get('message', 'unknown')}")
    return data


def get_quote(ticker: str) -> dict:
    return _request("quote", {"symbol": ticker.upper()}) or {}


def get_symbol_info(ticker: str) -> dict:
    data = _request("symbol_search", {"symbol": ticker.upper(), "outputsize": 1})
    items = data.get("data", [])
    return items[0] if items else {}


def get_time_series(ticker: str, interval: str = "1day", outputsize: int = 1260) -> pd.DataFrame:
    data = _request(
        "time_series",
        {
            "symbol": ticker.upper(),
            "interval": interval,
            "outputsize": outputsize,
            "order": "ASC",
        },
    )
    series = data.get("values", [])
    if not series:
        raise RuntimeError(f"Twelve Data: no time series for {ticker}")
    rows = []
    for r in series:
        rows.append(
            {
                "Date": pd.Timestamp(r["datetime"]),
                "Open": float(r.get("open", 0)),
                "High": float(r.get("high", 0)),
                "Low": float(r.get("low", 0)),
                "Close": float(r.get("close", 0)),
                "Volume": int(float(r.get("volume", 0) or 0)),
            }
        )
    return pd.DataFrame(rows).set_index("Date").sort_index()


def get_statistics(ticker: str) -> dict:
    data = _request("statistics", {"symbol": ticker.upper()})
    return data.get("statistics", data.get("values", {})) or {}
