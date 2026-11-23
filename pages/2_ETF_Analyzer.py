"""Page 2: ETF Analyzer — 10 ETF Models, Holdings & Sector Breakdown, Comparison & Export."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from core.screener import build_comparison_table
from core.strategies import evaluate_batch
from core.strategies.etfs import ETF_STRATEGIES
from ui.components import (
    get_db,
    plot_strategy_scores,
    render_download_buttons,
    render_hero,
    render_sidebar,
    render_ticker_selector,
)

st.set_page_config(page_title="ETF Analyzer | MarketSage", page_icon="📈", layout="wide")
engine = render_sidebar()
db = get_db()

render_hero(
    "📈 ETF Analyzer — 10 Scoring Models & Holdings X-Ray",
    "Evaluate Exchange-Traded Funds on cost efficiency, scale, income, momentum, diversification, and inspect underlying top holdings & sector allocations.",
)

tickers = render_ticker_selector(
    "etf_screen",
    asset_class="etf",
    placeholder="Type ETF tickers (e.g. VOO, QQQ, SCHD, VXUS) or open 'Load Market Universe' above to browse all US ETFs, Watchlist, or CSV...",
)
selected_strats = st.multiselect(
    "ETF Strategies",
    list(ETF_STRATEGIES.keys()),
    default=list(ETF_STRATEGIES.keys()),
)

if st.button("Analyze ETFs", type="primary"):
    if not tickers:
        st.warning("Enter at least one ETF ticker or load a universe above first.")
    else:
        prog = st.progress(0.0, text="Fetching ETF profiles...")
        infos = engine.get_batch_info(tickers, progress_callback=lambda i, t, s: prog.progress(i / max(t, 1), text=f"Fetching {s} ({i}/{t})"))
        prog.empty()
        if infos:
            df, evals = evaluate_batch(infos, asset_class="etf", selected_strategies=selected_strats)
            st.session_state["etf_df"] = df
            st.session_state["etf_infos"] = infos
            db.log_screener_run("etf_analyzer", {"tickers": len(tickers)}, len(df))
        else:
            st.error("Could not fetch ETF data.")

if "etf_df" in st.session_state:
    df = st.session_state["etf_df"]
    infos = st.session_state["etf_infos"]

    st.plotly_chart(plot_strategy_scores(df, "ETF Composite Rankings"), use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)
    render_download_buttons(df, {"ETF_Rankings": df, "Comparison": build_comparison_table(infos)}, "etf_analysis")

    st.divider()
    st.subheader("🔍 ETF Holdings & Sector X-Ray")
    pick = st.selectbox("Inspect ETF Holdings", [i["ticker"] for i in infos])
    col_btn1, col_btn2 = st.columns([1, 1])
    if col_btn1.button("Load Holdings & Sector Weights", use_container_width=True):
        hdata = engine.get_etf_holdings(pick)
        hc1, hc2 = st.columns(2)
        with hc1:
            st.markdown(f"**Top Holdings — {pick}**")
            if hdata["top_holdings"]:
                hdf = pd.DataFrame(hdata["top_holdings"])
                st.dataframe(hdf, use_container_width=True, hide_index=True)
            else:
                st.info("Top holdings not reported for this ETF by current data source.")
        with hc2:
            st.markdown(f"**Sector Allocation — {pick}**")
            if hdata["sector_breakdown"]:
                sdf = pd.DataFrame(hdata["sector_breakdown"])
                fig = px.pie(sdf, names="sector", values="weight", template="plotly_dark", hole=0.4)
                fig.update_layout(paper_bgcolor="#0f172a")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sector weights not reported for this ETF.")
    if col_btn2.button(f"+ Add {pick} to Watchlist", use_container_width=True):
        item = next(i for i in infos if i["ticker"] == pick)
        db.add_watchlist(pick, asset_type="etf", name=item.get("name", ""))
        st.success(f"Added {pick} to Watchlist.")
