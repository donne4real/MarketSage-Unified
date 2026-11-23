"""Tests for Technicals, Dividends/DCF/DRIP, Backtester, Portfolio Risk & Custom Screener."""

import numpy as np
import pandas as pd

from core.backtester import backtest_portfolio, backtest_single
from core.dividends import dcf_valuation, dividend_safety_assessment, gordon_growth_valuation, project_drip
from core.portfolio import analyze_portfolio_risk, calculate_cvar, calculate_var, compute_rebalance_plan, stress_test_portfolio
from core.screener import PRESET_FILTERS, apply_custom_filters, build_comparison_table
from core.technicals import analyze_technicals, enrich_indicators


def _synthetic_ohlcv(seed: int = 1, drift: float = 0.0008, n: int = 260) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    rets = rng.normal(drift, 0.015, size=n)
    close = 100.0 * np.cumprod(1.0 + rets)
    return pd.DataFrame(
        {
            "Open": close * 0.995,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": rng.integers(500_000, 2_000_000, size=n),
        },
        index=idx,
    )


def test_technicals_pipeline():
    df = _synthetic_ohlcv(seed=7)
    ind = enrich_indicators(df)
    for col in ("SMA_20", "SMA_50", "SMA_200", "RSI_14", "MACD", "BB_Upper", "BB_Lower"):
        assert col in ind.columns
    summary = analyze_technicals("TEST", df)
    assert 0.0 <= summary.rsi_14 <= 100.0
    assert summary.support_1 <= summary.resistance_1
    assert summary.trend_signal in {"Bullish", "Bearish", "Neutral"}


def test_dividends_valuation_and_drip():
    ggm = gordon_growth_valuation(current_price=60.0, annual_dividend=3.0, dividend_growth_rate=0.05, required_return=0.095)
    assert ggm.intrinsic_value == 70.0
    assert ggm.verdict == "Undervalued"

    dcf = dcf_valuation(current_price=100.0, fcf_per_share=8.0, growth_rate_5y=0.10, terminal_growth=0.025, discount_rate=0.10)
    assert dcf.intrinsic_value > 100.0
    assert dcf.verdict == "Undervalued"

    safety = dividend_safety_assessment({"dividend_yield": 0.035, "payout_ratio": 0.45, "free_cash_flow": 1e9, "debt_to_equity": 0.4})
    assert safety["rating"] == "Safe"

    drip = project_drip(10_000, 200, 0.04, 0.06, 0.05, years=10, reinvest=True)
    assert len(drip) == 10
    assert drip.iloc[-1]["Portfolio Value ($)"] > drip.iloc[-1]["Total Contributed ($)"]


def test_backtester_single_and_portfolio():
    df_a = _synthetic_ohlcv(seed=11, drift=0.001)
    df_b = _synthetic_ohlcv(seed=22, drift=0.0005)
    spy = _synthetic_ohlcv(seed=33, drift=0.0006)["Close"]

    for strat in ("buy_and_hold", "sma_crossover", "rsi_mean_reversion"):
        res = backtest_single(df_a["Close"], strategy=strat, initial_capital=10_000.0, benchmark=spy)
        assert res.final_value > 0
        assert "Benchmark" in res.equity_curve.columns

    pres = backtest_portfolio({"AAA": df_a["Close"], "BBB": df_b["Close"]}, weights={"AAA": 60, "BBB": 40}, benchmark=spy)
    assert pres.final_value > 0
    assert pres.max_drawdown_pct <= 0.0


def test_portfolio_risk_stress_and_rebalance():
    df_a = _synthetic_ohlcv(seed=101)
    df_b = _synthetic_ohlcv(seed=202)
    spy = _synthetic_ohlcv(seed=303)["Close"]

    rets = df_a["Close"].pct_change().dropna()
    assert calculate_var(rets, 0.95, "historical") >= 0
    assert calculate_var(rets, 0.95, "parametric") >= 0
    assert calculate_var(rets, 0.95, "monte_carlo") >= 0
    assert calculate_cvar(rets, 0.95) >= calculate_var(rets, 0.95, "historical")

    risk, corr = analyze_portfolio_risk({"AAA": df_a["Close"], "BBB": df_b["Close"]}, {"AAA": 50, "BBB": 50}, market_prices=spy)
    assert corr.shape == (2, 2)
    assert 0 <= risk.diversification_score <= 100

    stress = stress_test_portfolio(50_000.0, risk.beta)
    assert len(stress) == 5

    rebal = compute_rebalance_plan(
        [
            {"ticker": "AAA", "shares": 10, "cost_basis": 100.0, "bucket": "core", "target_weight": 50.0},
            {"ticker": "BBB", "shares": 5, "cost_basis": 100.0, "bucket": "satellite", "target_weight": 50.0},
        ],
        {"AAA": 120.0, "BBB": 100.0},
    )
    assert len(rebal) == 2
    assert "TRIM" in rebal.iloc[0]["Rebalance Action"]
    assert "BUY" in rebal.iloc[1]["Rebalance Action"]


def test_custom_screener_and_comparison():
    infos = [
        {"ticker": "CHEAP", "name": "Cheap Co", "price": 25.0, "pe_ratio": 12.0, "pb_ratio": 1.2, "debt_to_equity": 0.4},
        {"ticker": "PRICY", "name": "Pricy Co", "price": 300.0, "pe_ratio": 45.0, "pb_ratio": 9.0, "debt_to_equity": 1.5},
    ]
    matched = apply_custom_filters(infos, PRESET_FILTERS["Under-$50 Value & Growth"])
    assert [m["ticker"] for m in matched] == ["CHEAP"]

    comp = build_comparison_table(infos)
    assert "CHEAP" in comp.columns and "PRICY" in comp.columns
