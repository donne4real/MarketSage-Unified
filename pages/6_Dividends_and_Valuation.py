"""Page 6: Dividends, Gordon Growth, 5-Year FCF DCF Valuation & DRIP Projector."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from core.dividends import (
    dcf_valuation,
    dividend_safety_assessment,
    gordon_growth_valuation,
    project_drip,
)
from ui.components import render_download_buttons, render_hero, render_sidebar, render_single_ticker_input

st.set_page_config(page_title="Dividends & Valuation | MarketSage", page_icon="💰", layout="wide")
engine = render_sidebar()

render_hero(
    "💰 Dividends & Intrinsic Valuation Suite",
    "Calculate fair value via 5-Year Free Cash Flow DCF and Gordon Growth Model, inspect dividend safety, and project long-term DRIP passive income.",
)

tab_val, tab_drip = st.tabs(["Intrinsic Valuation & Dividend Safety", "DRIP Income Compounder"])

with tab_val:
    c1, c2 = st.columns([4, 1])
    with c1:
        ticker = render_single_ticker_input("val_single", label="Stock Ticker", placeholder="e.g. JNJ, PG, KO, MSFT")
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        load_btn = st.button("Fetch Fundamentals", type="primary", use_container_width=True)

    if load_btn and not ticker:
        st.warning("Enter a stock ticker first.")
    elif load_btn and ticker:
        with st.spinner(f"Loading {ticker} valuation inputs..."):
            try:
                st.session_state["val_info"] = engine.get_ticker_info(ticker)
            except Exception as exc:
                st.error(f"Failed to fetch {ticker}: {exc}")

    info = st.session_state.get("val_info")
    if info:
        price = float(info.get("price") or 0.0)
        div_rate = float(info.get("dividend_rate") or 0.0)
        fcf = float(info.get("free_cash_flow") or 0.0)
        shares = float(info.get("shares_outstanding") or 1.0)
        default_fcf_ps = round(fcf / shares, 2) if (fcf and shares > 0) else 5.0

        st.markdown(f"### {info.get('name')} (`{info.get('ticker')}`) — Current Price: **${price:,.2f}**")

        # Dividend safety
        safety = dividend_safety_assessment(info)
        s1, s2, s3 = st.columns(3)
        dy = info.get("dividend_yield") or 0.0
        pr = info.get("payout_ratio")
        s1.metric("Dividend Yield", f"{dy*100:.2f}%", f"${div_rate:.2f}/yr")
        s2.metric("Payout Ratio", f"{pr*100:.0f}%" if pr is not None else "—")
        s3.metric("Safety Score", f"{safety['score']}/100", safety["rating"])
        for n in safety["notes"]:
            st.caption(f"• {n}")

        st.divider()
        col_dcf, col_ggm = st.columns(2)
        with col_dcf:
            st.markdown("#### 5-Year FCF DCF Model")
            fcf_ps = st.number_input("FCF per Share ($)", value=float(default_fcf_ps), step=0.25)
            g5 = st.slider("5-Year Annual FCF Growth (%)", -5.0, 30.0, 8.0, 0.5) / 100.0
            gt = st.slider("Terminal Growth (%)", 1.0, 4.5, 2.5, 0.25) / 100.0
            wacc = st.slider("Discount Rate / WACC (%)", 6.0, 16.0, 9.5, 0.5) / 100.0
            res_dcf = dcf_valuation(price, fcf_ps, g5, gt, wacc)
            st.metric("DCF Intrinsic Value", f"${res_dcf.intrinsic_value:,.2f}", f"{res_dcf.margin_of_safety_pct:+.1f}% ({res_dcf.verdict})")

        with col_ggm:
            st.markdown("#### Gordon Growth Model (DDM)")
            ann_div = st.number_input("Annual Dividend per Share ($)", value=float(div_rate), step=0.10)
            dg = st.slider("Dividend Growth Rate (%)", 0.0, 12.0, 5.0, 0.5) / 100.0
            req_r = st.slider("Required Return (%)", 6.0, 15.0, 9.5, 0.5) / 100.0
            res_ggm = gordon_growth_valuation(price, ann_div, dg, req_r)
            st.metric("GGM Fair Value", f"${res_ggm.intrinsic_value:,.2f}", f"{res_ggm.margin_of_safety_pct:+.1f}% ({res_ggm.verdict})")

with tab_drip:
    d1, d2, d3 = st.columns(3)
    init_inv = d1.number_input("Initial Investment ($)", min_value=0.0, value=10000.0, step=1000.0)
    monthly = d2.number_input("Monthly Contribution ($)", min_value=0.0, value=300.0, step=50.0)
    years = d3.slider("Horizon (Years)", 3, 35, 15)

    d4, d5, d6, d7 = st.columns(4)
    start_y = d4.number_input("Starting Dividend Yield (%)", min_value=0.0, max_value=20.0, value=3.5, step=0.25) / 100.0
    div_g = d5.number_input("Annual Dividend Growth (%)", min_value=0.0, max_value=20.0, value=6.0, step=0.5) / 100.0
    px_g = d6.number_input("Annual Price Growth (%)", min_value=0.0, max_value=20.0, value=5.0, step=0.5) / 100.0
    reinvest = d7.checkbox("Reinvest Dividends (DRIP)", value=True)

    proj = project_drip(init_inv, monthly, start_y, div_g, px_g, years, reinvest)
    final_row = proj.iloc[-1]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(f"Year {years} Portfolio", f"${final_row['Portfolio Value ($)']:,.0f}")
    k2.metric(f"Year {years} Annual Dividend", f"${final_row['Annual Dividend ($)']:,.0f}")
    k3.metric(f"Year {years} Monthly Income", f"${final_row['Monthly Dividend ($)']:,.0f}/mo")
    k4.metric("Yield on Cost", f"{final_row['Yield on Cost (%)']:.1f}%")

    fig = px.area(
        proj,
        x="Year",
        y=["Total Contributed ($)", "Portfolio Value ($)"],
        title="DRIP Portfolio Growth Projection",
        template="plotly_dark",
    )
    fig.update_layout(paper_bgcolor="#0f172a", plot_bgcolor="#1e293b")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(proj, use_container_width=True, hide_index=True)
    render_download_buttons(proj, {"DRIP_Projection": proj}, "drip_projection")
