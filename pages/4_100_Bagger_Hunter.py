"""Page 4: 100-Bagger Hunter — 10 Peter Lynch / Chris Mayer Multi-Bagger Criteria."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.data_engine import UNIVERSES
from core.strategies import evaluate_batch
from core.strategies.bagger import BAGGER_STRATEGIES
from ui.components import (
    get_db,
    parse_tickers,
    plot_strategy_scores,
    render_download_buttons,
    render_hero,
    render_sidebar,
)

st.set_page_config(page_title="100-Bagger Hunter | MarketSage", page_icon="🚀", layout="wide")
engine = render_sidebar()
db = get_db()

render_hero(
    "🚀 100-Bagger Hunter — 10 Compounder Criteria",
    "Hunt for long-runway compounders combining small/mid-cap size, hyper-growth, twin-engine PEG valuation, high ROIC, wide gross margins, and founder alignment.",
)

c1, c2 = st.columns([2, 2])
with c1:
    ticker_input = st.text_area(
        "Candidate Tickers",
        value=", ".join(UNIVERSES["100-Bagger Candidates (Small/Mid Growth)"]),
        height=80,
    )
with c2:
    selected_strats = st.multiselect(
        "100-Bagger Criteria",
        list(BAGGER_STRATEGIES.keys()),
        default=list(BAGGER_STRATEGIES.keys()),
    )

if st.button("Scan 100-Bagger Candidates", type="primary"):
    tickers = parse_tickers(ticker_input)
    prog = st.progress(0.0, text="Scanning growth compounders...")
    infos = engine.get_batch_info(tickers, progress_callback=lambda i, t, s: prog.progress(i / max(t, 1), text=f"Scanning {s} ({i}/{t})"))
    prog.empty()
    if infos:
        df, evals = evaluate_batch(infos, asset_class="bagger", selected_strategies=selected_strats)
        st.session_state["bagger_df"] = df
        st.session_state["bagger_evals"] = evals
        db.log_screener_run("100_bagger_hunter", {"tickers": len(tickers)}, len(df))
    else:
        st.error("Unable to fetch candidate data.")

if "bagger_df" in st.session_state:
    df = st.session_state["bagger_df"]
    evals = st.session_state["bagger_evals"]

    st.plotly_chart(plot_strategy_scores(df, "100-Bagger Potential Scores"), use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)

    pick = st.selectbox("Inspect 100-Bagger Breakdown", [e["ticker"] for e in evals])
    chosen = next(e for e in evals if e["ticker"] == pick)
    b_rows = [
        {"Criterion": r.name, "Score": r.score, "Passed": r.passed, "Notes": "; ".join(r.reasons)}
        for r in chosen["details"]
    ]
    st.dataframe(pd.DataFrame(b_rows), use_container_width=True, hide_index=True)

    if st.button(f"+ Add {pick} to Watchlist"):
        db.add_watchlist(pick, asset_type="bagger", name=chosen["name"])
        st.success(f"Added {pick} to Watchlist.")

    render_download_buttons(df, {"100_Bagger_Rankings": df}, "100_bagger_scan")
