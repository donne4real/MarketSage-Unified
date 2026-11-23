"""Page 3: Mutual Fund Analyzer — 10 Evaluation Models & Fee Comparison."""

from __future__ import annotations

import streamlit as st

from core.screener import build_comparison_table
from core.strategies import evaluate_batch
from core.strategies.mutual_funds import MUTUAL_FUND_STRATEGIES
from ui.components import (
    get_db,
    plot_strategy_scores,
    render_download_buttons,
    render_hero,
    render_sidebar,
    render_ticker_selector,
)

st.set_page_config(page_title="Mutual Funds | MarketSage", page_icon="🏦", layout="wide")
engine = render_sidebar()
db = get_db()

render_hero(
    "🏦 Mutual Fund Analyzer — 10 Scoring Models",
    "Screen mutual funds for low fee drag, 3Y/5Y compounding consistency, tax efficiency, income generation, and fund family strength.",
)

tickers = render_ticker_selector(
    "mf_screen",
    asset_class="mutual_fund",
    placeholder="Type Mutual Fund tickers (e.g. VFIAX, FXAIX, VTSAX, SWPPX) or open 'Load Market Universe' above...",
)
selected_strats = st.multiselect(
    "Mutual Fund Models",
    list(MUTUAL_FUND_STRATEGIES.keys()),
    default=list(MUTUAL_FUND_STRATEGIES.keys()),
)

if st.button("Analyze Mutual Funds", type="primary"):
    if not tickers:
        st.warning("Enter at least one Mutual Fund ticker or load a list above first.")
    else:
        prog = st.progress(0.0, text="Fetching mutual fund profiles...")
        infos = engine.get_batch_info(tickers, progress_callback=lambda i, t, s: prog.progress(i / max(t, 1), text=f"Fetching {s} ({i}/{t})"))
        prog.empty()
        if infos:
            df, _ = evaluate_batch(infos, asset_class="mutual_fund", selected_strategies=selected_strats)
            st.session_state["mf_df"] = df
            st.session_state["mf_infos"] = infos
            db.log_screener_run("mutual_fund_analyzer", {"tickers": len(tickers)}, len(df))
        else:
            st.error("Unable to fetch mutual fund metrics.")

if "mf_df" in st.session_state:
    df = st.session_state["mf_df"]
    infos = st.session_state["mf_infos"]

    st.plotly_chart(plot_strategy_scores(df, "Mutual Fund Composite Rankings"), use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

    with st.expander("Side-by-Side Mutual Fund Comparison"):
        st.dataframe(build_comparison_table(infos), use_container_width=True, hide_index=True)

    pick = st.selectbox("Save Fund to Watchlist", [i["ticker"] for i in infos])
    if st.button(f"+ Add {pick} to Watchlist"):
        item = next(i for i in infos if i["ticker"] == pick)
        db.add_watchlist(pick, asset_type="mutual_fund", name=item.get("name", ""))
        st.success(f"Added {pick} to Watchlist.")

    render_download_buttons(df, {"Mutual_Fund_Rankings": df}, "mutual_fund_analysis")
