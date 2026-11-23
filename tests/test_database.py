"""Tests for SQLite persistence layer (cache, quotas, watchlist, holdings, decisions)."""

from core.database import Database


def test_api_cache_set_get_and_clear(tmp_path):
    db = Database(tmp_path / "test.db")
    assert db.get_cached("yfinance", "info", "AAPL") is None

    db.set_cached("yfinance", "info", "aapl", {"price": 210.5}, ttl_hours=24)
    cached = db.get_cached("yfinance", "info", "AAPL")
    assert cached == {"price": 210.5}
    assert db.cache_stats()["total"] == 1

    # Expired entry should return None
    db.set_cached("alpha_vantage", "info", "MSFT", {"price": 400}, ttl_hours=-1)
    assert db.get_cached("alpha_vantage", "info", "MSFT") is None

    cleared = db.clear_cache()
    assert cleared >= 1
    assert db.get_cached("yfinance", "info", "AAPL") is None


def test_api_quota_tracking_and_warning(tmp_path):
    db = Database(tmp_path / "test.db")
    assert db.increment_quota("alpha_vantage", 20) == 20
    status = db.get_quota_status()
    assert status["alpha_vantage"]["used"] == 20
    assert status["alpha_vantage"]["remaining"] == 5
    assert status["alpha_vantage"]["warning"] is True
    assert status["twelve_data"]["warning"] is False


def test_watchlist_and_holdings_crud(tmp_path):
    db = Database(tmp_path / "test.db")
    db.add_watchlist("voo", asset_type="etf", name="Vanguard S&P 500", target_price=480.0, notes="Core")
    db.add_watchlist("aapl", asset_type="stock", name="Apple")
    assert len(db.list_watchlist()) == 2
    assert len(db.list_watchlist("etf")) == 1
    assert db.remove_watchlist("AAPL") is True
    assert len(db.list_watchlist()) == 1

    hid = db.add_holding("VOO", 10.0, 450.0, asset_type="etf", bucket="core", target_weight=60.0)
    assert hid > 0
    rows = db.list_holdings()
    assert len(rows) == 1 and rows[0]["ticker"] == "VOO"
    assert db.delete_holding(hid) is True
    assert db.list_holdings() == []


def test_decision_log_lifecycle(tmp_path):
    db = Database(tmp_path / "test.db")
    did = db.add_decision(
        ticker="MSFT",
        asset_type="stock",
        decision="buy",
        thesis="Durable cloud and enterprise software moat with high ROIC.",
        sell_criteria="Azure growth falls below 10%",
        stop_loss="-25%",
        position_pct=10.0,
        price_at_decision=400.0,
        thesis_quality_score=9,
    )
    ret = db.update_decision_price(did, 460.0)
    assert ret == 15.0

    db.update_decision_status(did, "sold", review_notes="Target reached", sold_price=480.0)
    summary = db.decision_summary()
    assert summary["total"] == 1
    assert summary["sold"] == 1
    assert summary["avg_return_pct"] == 20.0
    assert summary["avg_thesis_score"] == 9.0
