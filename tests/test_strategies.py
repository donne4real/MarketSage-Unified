"""Tests covering all 45 investment strategies across Stocks, ETFs, Mutual Funds & 100-Bagger."""

from core.strategies import STRATEGY_REGISTRIES, evaluate_batch, evaluate_security


STRONG_STOCK = {
    "ticker": "QUAL",
    "name": "Quality Compounder Inc.",
    "sector": "Technology",
    "price": 90.0,
    "market_cap": 8_000_000_000,
    "pe_ratio": 14.0,
    "pb_ratio": 1.4,
    "ps_ratio": 1.8,
    "peg_ratio": 0.85,
    "ev_to_ebitda": 10.5,
    "roe": 0.24,
    "roa": 0.14,
    "gross_margin": 0.58,
    "operating_margin": 0.24,
    "profit_margin": 0.18,
    "revenue_growth": 0.26,
    "earnings_growth": 0.28,
    "debt_to_equity": 0.30,
    "current_ratio": 2.4,
    "free_cash_flow": 450_000_000,
    "dividend_yield": 0.035,
    "dividend_rate": 3.15,
    "payout_ratio": 0.42,
    "sma_50": 85.0,
    "sma_200": 78.0,
    "week_52_high": 95.0,
    "week_52_low": 60.0,
    "insider_ownership": 0.14,
    "institutional_ownership": 0.65,
}

STRONG_ETF = {
    "ticker": "VOO",
    "name": "Vanguard S&P 500 Index ETF",
    "category": "Large Blend S&P 500",
    "fund_family": "Vanguard",
    "price": 500.0,
    "expense_ratio": 0.0003,
    "aum": 450_000_000_000,
    "avg_volume": 4_500_000,
    "dividend_yield": 0.016,
    "pe_ratio": 21.0,
    "pb_ratio": 3.5,
    "beta": 1.0,
    "sma_50": 485.0,
    "sma_200": 460.0,
    "ytd_return": 0.14,
    "three_year_return": 0.11,
    "five_year_return": 0.13,
}


def test_total_strategy_count_is_45():
    assert len(STRATEGY_REGISTRIES["stock"]) == 15
    assert len(STRATEGY_REGISTRIES["etf"]) == 10
    assert len(STRATEGY_REGISTRIES["mutual_fund"]) == 10
    assert len(STRATEGY_REGISTRIES["bagger"]) == 10


def test_stock_and_bagger_evaluation():
    ev_stock = evaluate_security(STRONG_STOCK, asset_class="stock")
    assert ev_stock["strategies_total"] == 15
    assert ev_stock["composite_score"] >= 70.0
    assert ev_stock["strategies_passed"] >= 10

    ev_bagger = evaluate_security(STRONG_STOCK, asset_class="bagger")
    assert ev_bagger["strategies_total"] == 10
    assert ev_bagger["composite_score"] >= 80.0


def test_etf_and_mutual_fund_evaluation():
    ev_etf = evaluate_security(STRONG_ETF, asset_class="etf")
    assert ev_etf["strategies_total"] == 10
    assert ev_etf["composite_score"] >= 70.0

    ev_mf = evaluate_security(STRONG_ETF, asset_class="mutual_fund")
    assert ev_mf["strategies_total"] == 10
    assert ev_mf["composite_score"] >= 70.0


def test_evaluate_batch_ranks_higher_score_first():
    weak = {"ticker": "WEAK", "name": "Weak Co", "price": 10.0, "pe_ratio": 80.0, "debt_to_equity": 4.0}
    df, evals = evaluate_batch([weak, STRONG_STOCK], asset_class="stock")
    assert len(df) == 2
    assert df.iloc[0]["Ticker"] == "QUAL"
    assert evals[0]["composite_score"] > evals[1]["composite_score"]
