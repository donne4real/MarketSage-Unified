"""Page 1: Stock Screener — 15 Guru & Quant Models, Custom Filters, Comparison & Export."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.data_engine import UNIVERSES
from core.screener import PRESET_FILTERS, FilterRule, apply_custom_filters, build_comparison_table
from core.strategies import evaluate_batch
from core.strategies.stocks import STOCK_STRATEGIES
from ui.components import (
    get_db,
    parse_tickers,
    plot_strategy_scores,
    render_download_buttons,
    render_hero,
    render_sidebar,
)

st.set_page_config(page_title="Stock Screener | MarketSage", page_icon="📊", layout="wide")
engine = render_sidebar()
db = get_db()

render_hero(
    "📊 Stock Screener — 15 Guru & Quant Models",
    "Screen equities across Benjamin Graham, Warren Buffett, Peter Lynch, Magic Formula, CAN SLIM, Piotroski F-Score, Altman Z-Score, Momentum & Custom Filters.",
)

tab_screen, tab_custom, tab_compare = st.tabs(["Multi-Model Screener", "Custom Metric Filter", "Side-by-Side Comparison"])

with tab_screen:
    c1, c2 = st.columns([2, 2])
    with c1:
        preset_u = st.selectbox(
            "Starter Universe",
            ["US Blue-Chip & Tech Leaders", "Dividend Aristocrats", "Under-$50 Value & Growth", "Custom"],
        )
        default_tickers = ", ".join(UNIVERSES.get(preset_u, ["AAPL", "MSFT", "GOOGL", "JNJ", "KO"]))
        ticker_input = st.text_area("Tickers (comma-separated)", value=default_tickers, height=80)
    with c2:
        selected_strats = st.multiselect(
            "Strategies to Apply",
            list(STOCK_STRATEGIES.keys()),
            default=list(STOCK_STRATEGIES.keys())[:10],
        )

    if st.button("Run Stock Screen", type="primary"):
        tickers = parse_tickers(ticker_input)
        prog = st.progress(0.0, text="Fetching stock fundamentals...")

        def _cb(i: int, tot: int, sym: str):
            prog.progress(i / max(tot, 1), text=f"Fetching {sym} ({i}/{tot})...")

        infos = engine.get_batch_info(tickers, progress_callback=_cb)
        prog.empty()

        if not infos:
            st.error("No stock data returned. Check tickers or API limits.")
        else:
            df, evals = evaluate_batch(infos, asset_class="stock", selected_strategies=selected_strats)
            st.session_state["stock_screen_df"] = df
            st.session_state["stock_screen_evals"] = evals
            st.session_state["stock_screen_infos"] = infos
            db.log_screener_run("stock_multi_model", {"tickers": len(tickers), "strategies": len(selected_strats)}, len(df))

    if "stock_screen_df" in st.session_state:
        df = st.session_state["stock_screen_df"]
        evals = st.session_state["stock_screen_evals"]

        k1, k2, k3 = st.columns(3)
        k1.metric("Stocks Analyzed", len(df))
        k2.metric("Avg Composite Score", f"{df['Composite Score'].mean():.1f}")
        k3.metric("Top Ranked", f"{df.iloc[0]['Ticker']} ({df.iloc[0]['Composite Score']})")

        st.plotly_chart(plot_strategy_scores(df, "Stock Composite Rankings"), use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Build detail sheet for export & inspection
        detail_rows = []
        for ev in evals:
            for r in ev["details"]:
                detail_rows.append(
                    {
                        "Ticker": ev["ticker"],
                        "Strategy": r.name,
                        "Score": r.score,
                        "Passed": r.passed,
                        "Signal": r.signal,
                        "Reasons": "; ".join(r.reasons),
                    }
                )
        detail_df = pd.DataFrame(detail_rows)

        with st.expander("Inspect Strategy Breakdown by Stock"):
            pick = st.selectbox("Select Stock", [e["ticker"] for e in evals])
            sub = detail_df[detail_df["Ticker"] == pick]
            st.dataframe(sub, use_container_width=True, hide_index=True)
            if st.button(f"+ Add {pick} to Watchlist"):
                row_info = next(e["raw_info"] for e in evals if e["ticker"] == pick)
                db.add_watchlist(pick, asset_type="stock", name=row_info.get("name", ""))
                st.success(f"Saved {pick} to Watchlist.")

        render_download_buttons(df, {"Summary": df, "Strategy_Details": detail_df}, "stock_screener")

with tab_custom:
    st.markdown("Filter your fetched stock set (or load a preset like **Under-$50 Value & Growth**).")
    infos = st.session_state.get("stock_screen_infos", [])
    preset_name = st.selectbox("Filter Preset", ["Custom Rules"] + list(PRESET_FILTERS.keys()))
    f1, f2, f3, f4 = st.columns(4)
    max_price = f1.number_input("Max Price ($)", min_value=0.0, value=50.0 if "Under-$50" in preset_name else 10000.0)
    max_pe = f2.number_input("Max P/E", min_value=0.0, value=25.0)
    min_roe = f3.number_input("Min ROE (%)", min_value=-100.0, value=0.0)
    max_dte = f4.number_input("Max Debt/Equity", min_value=0.0, value=2.5)

    if not infos:
        st.info("Run the Multi-Model Screener first to load stock data for custom filtering.")
    else:
        rules = PRESET_FILTERS[preset_name] if preset_name in PRESET_FILTERS else [
            FilterRule("price", "<=", max_price),
            FilterRule("pe_ratio", "<=", max_pe),
            FilterRule("roe", ">=", min_roe / 100.0),
            FilterRule("debt_to_equity", "<=", max_dte),
        ]
        matched = apply_custom_filters(infos, rules)
        st.success(f"Matched **{len(matched)}** of {len(infos)} securities.")
        if matched:
            mdf, _ = evaluate_batch(matched, asset_class="stock")
            st.dataframe(mdf, use_container_width=True, hide_index=True)

with tab_compare:
    comp_tickers = st.text_input("Tickers to Compare Side-by-Side", value="AAPL, MSFT, GOOGL, NVDA")
    if st.button("Compare Tickers"):
        syms = parse_tickers(comp_tickers)
        comp_infos = engine.get_batch_info(syms)
        if comp_infos:
            st.dataframe(build_comparison_table(comp_infos), use_container_width=True, hide_index=True)
        else:
            st.warning("Unable to load comparison metrics.")
