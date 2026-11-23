"""MarketSage Unified — Command Center Landing Page."""

from __future__ import annotations

import streamlit as st

from core.ai_research import detect_red_flags
from core.strategies import STRATEGY_REGISTRIES, evaluate_security
from ui.components import get_db, render_hero, render_sidebar, render_single_ticker_input

st.set_page_config(
    page_title="MarketSage Unified",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

engine = render_sidebar()
db = get_db()

render_hero(
    "📈 MarketSage Unified",
    "One coherent financial intelligence platform uniting Multi-Source Data, 45 Investment Models, Technicals, DCF/DRIP Valuation, Backtesting, Portfolio Risk, SEC EDGAR & AI Research.",
)

# Top-level platform status KPIs
wl = db.list_watchlist()
holdings = db.list_holdings()
dec_summary = db.decision_summary()
cache_stats = db.cache_stats()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Investment Models", f"{sum(len(v) for v in STRATEGY_REGISTRIES.values())}", "4 Asset Classes")
c2.metric("Watchlist Items", len(wl), "Cross-Asset")
c3.metric("Portfolio Holdings", len(holdings), "Tracked in SQLite")
c4.metric("Logged Decisions", dec_summary["total"], f"{dec_summary['open']} open")

st.divider()

# Quick Single-Ticker Lookup right from Command Center
st.subheader("⚡ Quick Security Snapshot")
q_col1, q_col2, q_col3 = st.columns([3, 2, 1])
with q_col1:
    quick_ticker = render_single_ticker_input(
        "home_quick",
        label="Enter Ticker (Stock, ETF, or Mutual Fund)",
        placeholder="e.g. AAPL, VOO, VFIAX",
    )
with q_col2:
    quick_mode = st.selectbox("Evaluation Lens", ["stock", "etf", "mutual_fund", "bagger"])
with q_col3:
    st.markdown("<br>", unsafe_allow_html=True)
    run_quick = st.button("Analyze", type="primary", use_container_width=True)

if run_quick and not quick_ticker:
    st.warning("Enter a ticker symbol first (e.g. AAPL or VOO).")
elif run_quick and quick_ticker:
    with st.spinner(f"Fetching {quick_ticker} via multi-source engine..."):
        try:
            info = engine.get_ticker_info(quick_ticker)
            ev = evaluate_security(info, asset_class=quick_mode)
            flags = detect_red_flags(info)

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Price", f"${info.get('price', 0):,.2f}")
            m2.metric("Composite Score", f"{ev['composite_score']}/100", ev["signal"])
            m3.metric("Strategies Passed", f"{ev['strategies_passed']}/{ev['strategies_total']}")
            pe = info.get("pe_ratio")
            m4.metric("P/E Ratio", f"{pe:.1f}" if pe else "—")
            dy = info.get("dividend_yield")
            m5.metric("Div Yield", f"{dy*100:.2f}%" if dy else "—")

            src_tag = f"Source: `{info.get('source')}` ({'cached' if info.get('from_cache') else 'live'})"
            st.caption(f"**{info.get('name')}** · {info.get('sector')} · {src_tag}")

            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.markdown("**Passed Models:** " + (ev["passed_list"] or "None"))
                if flags:
                    st.warning("**Red Flags:** " + " · ".join(flags))
                else:
                    st.success("No automated financial health red flags triggered.")
            with col_b:
                if st.button(f"+ Add {quick_ticker} to Watchlist", use_container_width=True):
                    db.add_watchlist(quick_ticker, asset_type=quick_mode, name=info.get("name", ""))
                    st.success(f"Added {quick_ticker} to Watchlist.")
        except Exception as exc:
            st.error(f"Could not fetch `{quick_ticker}`: {exc}")

st.divider()

# Module Navigator Overview
st.subheader("🧭 Platform Modules")
g1, g2, g3 = st.columns(3)
with g1:
    st.markdown(
        """
        **1. Stock Screener (15 Models)**  
        10 Classic Guru philosophies + 5 Quant models, Custom Filter Builder (incl. Under-$50), Side-by-Side Comparison & Excel export.

        **2. ETF Analyzer (10 Models)**  
        Cost, scale, dividend, momentum, top holdings & sector weightings.

        **3. Mutual Funds (10 Models)**  
        Expense drag, 3Y/5Y consistency, tax efficiency & fund family quality.
        """
    )
with g2:
    st.markdown(
        """
        **4. 100-Bagger Hunter (10 Models)**  
        Small/mid-cap runway, hyper-growth, PEG twin engine, ROIC & insider alignment.

        **5. Technicals & Backtest**  
        Candlestick + SMA/EMA/Bollinger/RSI/MACD plus Buy & Hold, SMA Crossover, and RSI Mean Reversion backtests vs SPY.

        **6. Dividends & Valuation**  
        Gordon Growth Model, 5-Year FCF DCF Calculator, payout sustainability & DRIP income projector.
        """
    )
with g3:
    st.markdown(
        """
        **7. Portfolio & Risk**  
        SQLite holdings tracker, allocation, VaR/CVaR, Sortino/Beta, correlation heatmap, crash stress tests & rebalancer.

        **8. AI Research & SEC EDGAR**  
        Live 10-K/10-Q retrieval, automated red flags, analyst price targets & multi-LLM synthesis (Claude / Gemini / OpenAI).

        **9. Watchlist & Decision Log**  
        Cross-asset watchlist + SQLite Decision Journal with thesis-quality grading & P&L tracking.
        """
    )
