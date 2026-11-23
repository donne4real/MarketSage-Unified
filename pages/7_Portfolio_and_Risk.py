"""Page 7: Portfolio Builder, Holdings Manager, Risk Management (VaR/CVaR/Sortino) & Stress Tests."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from core.portfolio import analyze_portfolio_risk, compute_rebalance_plan, stress_test_portfolio
from ui.components import (
    get_db,
    plot_correlation_heatmap,
    render_download_buttons,
    render_hero,
    render_sidebar,
)

st.set_page_config(page_title="Portfolio & Risk | MarketSage", page_icon="🛡️", layout="wide")
engine = render_sidebar()
db = get_db()

render_hero(
    "🛡️ Portfolio Builder & Risk Management",
    "Manage core & satellite holdings in SQLite, track unrealized P&L and rebalancing actions, and run VaR/CVaR, Sortino, Correlation & Crash Stress Tests.",
)

with st.expander("➕ Add Holding to Portfolio", expanded=not bool(db.list_holdings())):
    with st.form("add_holding_form", clear_on_submit=True):
        h1, h2, h3, h4, h5, h6 = st.columns(6)
        tk = h1.text_input("Ticker", value="", placeholder="e.g. VOO").strip().upper()
        shares = h2.number_input("Shares", min_value=0.0001, value=10.0, step=1.0)
        cost = h3.number_input("Avg Cost ($)", min_value=0.01, value=450.0, step=5.0)
        atype = h4.selectbox("Asset", ["etf", "stock", "mutual_fund"])
        bucket = h5.selectbox("Bucket", ["core", "satellite"])
        target_w = h6.number_input("Target Wt (%)", min_value=0.0, max_value=100.0, value=25.0, step=5.0)
        submitted = st.form_submit_button("Save Holding", type="primary")
        if submitted and tk:
            db.add_holding(tk, shares, cost, asset_type=atype, bucket=bucket, target_weight=target_w)
            st.success(f"Added {shares} shares of {tk}.")
            st.rerun()

holdings = db.list_holdings()
if not holdings:
    st.info("Add at least one holding above to run live portfolio & risk analytics.")
    st.stop()

# Delete control
del_col1, del_col2 = st.columns([3, 1])
with del_col1:
    del_opts = {f"#{h['id']} — {h['ticker']} ({h['shares']} sh @ ${h['cost_basis']})": h["id"] for h in holdings}
    pick_del = st.selectbox("Manage Stored Holdings", list(del_opts.keys()))
with del_col2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Delete Selected", use_container_width=True):
        db.delete_holding(del_opts[pick_del])
        st.rerun()

if st.button("Refresh Live Valuation & Risk Analytics", type="primary"):
    tickers = list(dict.fromkeys(h["ticker"] for h in holdings))
    prices: dict[str, float] = {}
    price_map = {}
    with st.spinner("Fetching live prices, 2Y histories & SPY benchmark..."):
        for sym in tickers:
            try:
                hist = engine.get_price_history(sym, period="2y")
                if not hist.empty:
                    price_map[sym] = hist["Close"]
                    prices[sym] = float(hist["Close"].iloc[-1])
            except Exception:
                pass
        try:
            spy_close = engine.get_price_history("SPY", period="2y")["Close"]
        except Exception:
            spy_close = None

        rebal_df = compute_rebalance_plan(holdings, prices)
        st.session_state["port_rebal_df"] = rebal_df
        total_val = float(rebal_df["Market Value ($)"].sum())

        weights = {}
        for _, r in rebal_df.iterrows():
            weights[r["Ticker"]] = weights.get(r["Ticker"], 0.0) + float(r["Current Wt (%)"])

        if price_map:
            risk, corr = analyze_portfolio_risk(price_map, weights, market_prices=spy_close)
            st.session_state["port_risk"] = risk
            st.session_state["port_corr"] = corr
            st.session_state["port_stress"] = stress_test_portfolio(total_val, risk.beta)

if "port_rebal_df" in st.session_state:
    rebal_df = st.session_state["port_rebal_df"]
    total_val = float(rebal_df["Market Value ($)"].sum())
    total_pnl = float(rebal_df["Unrealized P&L ($)"].sum())

    k1, k2, k3 = st.columns(3)
    k1.metric("Total Portfolio Value", f"${total_val:,.2f}")
    k2.metric("Total Unrealized P&L", f"${total_pnl:+,.2f}")
    core_val = float(rebal_df[rebal_df["Bucket"] == "core"]["Market Value ($)"].sum())
    k3.metric("Core Allocation", f"{(core_val/max(total_val,1))*100:.1f}%", "vs Satellite")

    st.dataframe(rebal_df, use_container_width=True, hide_index=True)

    c_pie, c_corr = st.columns(2)
    with c_pie:
        fig_pie = px.pie(rebal_df, names="Ticker", values="Market Value ($)", title="Portfolio Allocation", template="plotly_dark", hole=0.45)
        fig_pie.update_layout(paper_bgcolor="#0f172a")
        st.plotly_chart(fig_pie, use_container_width=True)
    with c_corr:
        if "port_corr" in st.session_state:
            st.plotly_chart(plot_correlation_heatmap(st.session_state["port_corr"]), use_container_width=True)

    if "port_risk" in st.session_state:
        risk = st.session_state["port_risk"]
        st.subheader("📐 Risk Diagnostics")
        r1, r2, r3, r4, r5 = st.columns(5)
        r1.metric("Ann. Return / Vol", f"{risk.expected_annual_return_pct:.1f}%", f"Vol {risk.annual_volatility_pct:.1f}%")
        r2.metric("Sharpe / Sortino", f"{risk.sharpe_ratio:.2f}", f"Sortino {risk.sortino_ratio:.2f}")
        r3.metric("Portfolio Beta", f"{risk.beta:.2f}", "vs SPY")
        r4.metric("Daily VaR 95% / CVaR", f"-{risk.var_95_daily_pct:.2f}%", f"CVaR -{risk.cvar_95_daily_pct:.2f}%")
        r5.metric("Max DD / Diversif.", f"{risk.max_drawdown_pct:.1f}%", f"Score {risk.diversification_score}/100")

        st.subheader("🌪️ Market Crash Stress Tests")
        stress_df = st.session_state["port_stress"]
        st.dataframe(stress_df, use_container_width=True, hide_index=True)
        render_download_buttons(
            rebal_df,
            {"Holdings_Rebalance": rebal_df, "Stress_Tests": stress_df},
            "portfolio_risk_report",
        )
