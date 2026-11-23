"""Tests for Multi-Source DataEngine fallback chain, caching & schema normalization."""

from unittest.mock import patch
import pandas as pd

from core.data_engine import DataEngine, normalize_info
from core.database import Database


def test_normalize_yfinance_percentages_and_types():
    raw = {
        "quoteType": "EQUITY",
        "longName": "Example Corp",
        "sector": "Technology",
        "currentPrice": 125.0,
        "debtToEquity": 45.0,  # yfinance returns 45% as 45.0 -> should normalize to 0.45
        "dividendYield": 2.5,  # >0.5 -> normalize to 0.025
        "trailingPE": 18.2,
    }
    norm = normalize_info(raw, "yfinance", "EXMP")
    assert norm["ticker"] == "EXMP"
    assert norm["asset_type"] == "stock"
    assert norm["debt_to_equity"] == 0.45
    assert norm["dividend_yield"] == 0.025
    assert norm["pe_ratio"] == 18.2


def test_fallback_chain_av_fails_then_td_succeeds_and_caches(tmp_path):
    db = Database(tmp_path / "engine.db")
    engine = DataEngine(db=db, source_order="av_first", rate_limit_delay=0.0)

    with (
        patch("core.sources.alpha_vantage.is_configured", return_value=True),
        patch("core.sources.alpha_vantage.get_overview", side_effect=RuntimeError("429 rate limit")),
        patch("core.sources.twelve_data.is_configured", return_value=True),
        patch("core.sources.twelve_data.get_symbol_info", return_value={"symbol": "AAPL", "instrument_name": "Apple Inc."}),
        patch("core.sources.twelve_data.get_quote", return_value={"close": "215.50", "exchange": "NASDAQ"}) as mock_td,
    ):
        first = engine.get_ticker_info("AAPL")
        assert first["source"] == "twelve_data"
        assert first["price"] == 215.50
        assert first["from_cache"] is False
        assert db.get_quota_status()["twelve_data"]["used"] == 1

        # Second call hits SQLite cache without calling network or incrementing quota
        second = engine.get_ticker_info("AAPL")
        assert second["from_cache"] is True
        assert mock_td.call_count == 1
        assert db.get_quota_status()["twelve_data"]["used"] == 1


def test_price_history_caching(tmp_path):
    db = Database(tmp_path / "hist.db")
    engine = DataEngine(db=db, source_order="yf_first", rate_limit_delay=0.0)
    idx = pd.date_range("2026-01-01", periods=10, freq="B")
    sample_df = pd.DataFrame(
        {"Open": 100.0, "High": 102.0, "Low": 99.0, "Close": [100 + i for i in range(10)], "Volume": 1_000_000},
        index=idx,
    )
    sample_df.index.name = "Date"

    with patch.object(engine, "_yf_history", return_value=sample_df) as mock_yf:
        df1 = engine.get_price_history("SPY", period="1y")
        df2 = engine.get_price_history("SPY", period="1y")
        assert len(df1) == 10
        assert len(df2) == 10
        assert mock_yf.call_count == 1
