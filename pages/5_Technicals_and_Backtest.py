"""Page 5: Technical Analysis & Strategy Backtester."""

from __future__ import annotations

import streamlit as st

from core.backtester import backtest_portfolio, backtest_single
from core.technicals import analyze_technicals, enrich_indicators
from ui.components import (
    parse_tickers,
    plot_candlestick_technicals,
    plot_equity_curve,
    render_hero,
    render_sidebar,
    render_single_ticker_input,
)

st.set_page_config(page_title="Technicals & Backtest | MarketSage", page_icon="📉", layout="wide")
engine = render_sidebar()

render_hero(
    "📉 Technical Analysis & Unified Backtester",
    "Inspect SMA/EMA trends, RSI-14, MACD, Bollinger Bands, Support/Resistance, and backtest single-ticker or multi-asset strategies against SPY.",
)

tab_tech, tab_bt = st.tabs(["Technical Indicators", "Strategy & Portfolio Backtester"])

with tab_tech:
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        ticker = render_single_ticker_input("tech_single", label="Ticker", placeholder="e.g. NVDA, AAPL, VOO")
    period = c2.selectbox("History Window", ["6mo", "1y", "2y", "5y"], index=1)
    with c3:
        st.markdown("<br>", unsafe_allow_html=True)
        run_tech = st.button("Load Technicals", type="primary", use_container_width=True)

    if run_tech and not ticker:
        st.warning("Enter a ticker symbol first.")
    elif run_tech and ticker:
        with st.spinner(f"Fetching {ticker} ({period})..."):
            try:
                hist = engine.get_price_history(ticker, period=period)
                ind = enrich_indicators(hist)
                summary = analyze_technicals(ticker, hist)

                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("Price", f"${summary.current_price:,.2f}")
                m2.metric("Trend", summary.trend_signal)
                m3.metric("RSI (14)", f"{summary.rsi_14}", summary.momentum_signal)
                m4.metric("BB Position", f"{summary.bb_position_pct:.0f}%", summary.volatility_signal)
                m5.metric("Support / Res", f"${summary.support_1:.1f} / ${summary.resistance_1:.1f}")
                m6.metric("Risk/Reward", f"{summary.risk_reward_ratio}x", f"Vol {summary.volume_ratio}x")

                st.plotly_chart(plot_candlestick_technicals(ind, ticker), use_container_width=True)
            except Exception as exc:
                st.error(f"Technical analysis failed for {ticker}: {exc}")

with tab_bt:
    mode = st.radio("Backtest Mode", ["Single Security Strategy", "Multi-Asset Equal-Weight Portfolio"], horizontal=True)
    b1, b2, b3 = st.columns([2, 1, 1])
    bt_tickers = b1.text_input(
        "Ticker(s)",
        value="",
        placeholder="e.g. AAPL" if mode.startswith("Single") else "e.g. VOO, QQQ, SCHD, NVDA",
    )
    bt_period = b2.selectbox("Backtest Period", ["1y", "2y", "3y", "5y"], index=2)
    bt_cap = b3.number_input("Initial Capital ($)", min_value=500.0, value=10000.0, step=1000.0)

    strat = "buy_and_hold"
    fast_w, slow_w = 20, 50
    if mode.startswith("Single"):
        s1, s2, s3 = st.columns(3)
        strat = s1.selectbox("Strategy", ["buy_and_hold", "sma_crossover", "rsi_mean_reversion"])
        if strat == "sma_crossover":
            fast_w = s2.number_input("Fast SMA", 5, 100, 20)
            slow_w = s3.number_input("Slow SMA", 20, 250, 50)

    if st.button("Run Backtest", type="primary"):
        syms = parse_tickers(bt_tickers)
        if not syms:
            st.warning("Enter one or more tickers before running a backtest.")
            st.stop()
        with st.spinner("Running backtest & loading SPY benchmark..."):
            try:
                spy_hist = engine.get_price_history("SPY", period=bt_period)
                bench = spy_hist["Close"] if not spy_hist.empty else None

                if mode.startswith("Single"):
                    hist = engine.get_price_history(syms[0], period=bt_period)
                    res = backtest_single(
                        hist["Close"],
                        strategy=strat,
                        initial_capital=bt_cap,
                        benchmark=bench,
                        fast_window=int(fast_w),
                        slow_window=int(slow_w),
                    )
                else:
                    pmap = {}
                    for sym in syms:
                        h = engine.get_price_history(sym, period=bt_period)
                        if not h.empty:
                            pmap[sym] = h["Close"]
                    res = backtest_portfolio(pmap, initial_capital=bt_cap, benchmark=bench)

                r1, r2, r3, r4, r5, r6 = st.columns(6)
                r1.metric("Final Value", f"${res.final_value:,.0f}", f"{res.total_return_pct:+.1f}%")
                r2.metric("CAGR", f"{res.cagr_pct:.1f}%")
                r3.metric("Sharpe", f"{res.sharpe_ratio:.2f}")
                r4.metric("Sortino", f"{res.sortino_ratio:.2f}")
                r5.metric("Max Drawdown", f"{res.max_drawdown_pct:.1f}%")
                r6.metric("Trades", res.num_trades, f"Win {res.win_rate_pct:.0f}%")

                st.plotly_chart(plot_equity_curve(res.equity_curve, res.strategy_name), use_container_width=True)
            except Exception as exc:
                st.error(f"Backtest error: {exc}")
