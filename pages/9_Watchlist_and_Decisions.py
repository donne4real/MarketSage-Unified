"""Page 9: Cross-Asset Watchlist & SQLite Investment Decision Journal."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.ai_research import score_thesis_quality
from ui.components import get_db, render_download_buttons, render_hero, render_sidebar

st.set_page_config(page_title="Watchlist & Decisions | MarketSage", page_icon="📋", layout="wide")
engine = render_sidebar()
db = get_db()

render_hero(
    "📋 Cross-Asset Watchlist & Investment Decision Log",
    "Track Stocks, ETFs, Mutual Funds, and 100-Baggers in one watchlist, and journal your investment theses with objective process grading & outcome tracking.",
)

tab_wl, tab_dec = st.tabs(["Cross-Asset Watchlist", "Investment Decision Journal"])

with tab_wl:
    with st.form("wl_add_form", clear_on_submit=True):
        w1, w2, w3, w4 = st.columns([2, 1, 1, 3])
        tk = w1.text_input("Ticker").strip().upper()
        at = w2.selectbox("Asset Type", ["stock", "etf", "mutual_fund", "bagger"])
        tp = w3.number_input("Target Entry ($)", min_value=0.0, value=0.0, step=5.0)
        notes = w4.text_input("Notes / Catalyst")
        if st.form_submit_button("Add to Watchlist", type="primary") and tk:
            db.add_watchlist(tk, asset_type=at, target_price=tp if tp > 0 else None, notes=notes)
            st.success(f"Added {tk} to Watchlist.")
            st.rerun()

    filt = st.selectbox("Filter Asset Type", ["all", "stock", "etf", "mutual_fund", "bagger"])
    items = db.list_watchlist(asset_type=filt)
    if not items:
        st.info("Your watchlist is empty. Add tickers above or from any screener page.")
    else:
        if st.button("Refresh Watchlist Prices"):
            enriched = []
            for it in items:
                try:
                    info = engine.get_ticker_info(it["ticker"])
                    enriched.append(
                        {
                            "Ticker": it["ticker"],
                            "Type": it["asset_type"],
                            "Name": info.get("name", it.get("name", "")),
                            "Price ($)": round(info.get("price", 0), 2),
                            "Target Entry ($)": it.get("target_price"),
                            "P/E": round(info["pe_ratio"], 1) if info.get("pe_ratio") else None,
                            "Div Yield %": round(info["dividend_yield"] * 100, 2) if info.get("dividend_yield") else None,
                            "Notes": it.get("notes", ""),
                        }
                    )
                except Exception:
                    enriched.append({"Ticker": it["ticker"], "Type": it["asset_type"], "Notes": it.get("notes", "")})
            st.session_state["wl_live_df"] = pd.DataFrame(enriched)

        wdf = st.session_state.get("wl_live_df", pd.DataFrame(items))
        st.dataframe(wdf, use_container_width=True, hide_index=True)

        rm_col1, rm_col2 = st.columns([3, 1])
        rm_pick = rm_col1.selectbox("Remove from Watchlist", [i["ticker"] for i in items])
        if rm_col2.button("Remove", use_container_width=True):
            db.remove_watchlist(rm_pick)
            st.session_state.pop("wl_live_df", None)
            st.rerun()

with tab_dec:
    summary = db.decision_summary()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Decisions", summary["total"])
    m2.metric("Open Positions", summary["open"])
    m3.metric("Avg Return", f"{summary['avg_return_pct']:+.1f}%" if summary["avg_return_pct"] is not None else "—")
    m4.metric("Avg Thesis Quality", f"{summary['avg_thesis_score']}/10" if summary["avg_thesis_score"] is not None else "—")

    with st.expander("➕ Log New Investment Decision", expanded=summary["total"] == 0):
        with st.form("decision_form", clear_on_submit=True):
            d1, d2, d3, d4 = st.columns(4)
            d_tk = d1.text_input("Ticker").strip().upper()
            d_type = d2.selectbox("Asset", ["stock", "etf", "mutual_fund"])
            d_action = d3.selectbox("Decision", ["buy", "watch", "decided_against"])
            d_price = d4.number_input("Price at Decision ($)", min_value=0.0, value=0.0, step=1.0)

            d_thesis = st.text_area("Investment Thesis (Why will this compound over 3–5+ years?)", height=90)
            c5, c6, c7 = st.columns(3)
            d_sell = c5.text_input("Sell / Falsification Criteria (What proves you wrong?)")
            d_stop = c6.text_input("Stop-Loss / Risk Guardrail", placeholder="e.g., -20% or margin < 12%")
            d_pos = c7.number_input("Target Position Size (%)", min_value=0.0, max_value=100.0, value=5.0, step=1.0)

            if st.form_submit_button("Grade & Save Decision", type="primary") and d_tk and d_thesis:
                q = score_thesis_quality(d_tk, d_thesis, d_sell, d_stop, d_pos)
                db.add_decision(
                    ticker=d_tk,
                    asset_type=d_type,
                    decision=d_action,
                    thesis=d_thesis,
                    sell_criteria=d_sell,
                    stop_loss=d_stop,
                    position_pct=d_pos,
                    price_at_decision=d_price if d_price > 0 else None,
                    thesis_quality_score=q["score"],
                )
                st.success(f"Logged decision for {d_tk} — Thesis Process Score: **{q['score']}/10**")
                for fb in q["feedback"]:
                    st.caption(f"• {fb}")
                st.rerun()

    decs = db.list_decisions()
    if decs:
        if st.button("Update Open Decisions with Live Prices"):
            for d in decs:
                if d["status"] == "open":
                    try:
                        p = engine.get_ticker_info(d["ticker"]).get("price")
                        if p:
                            db.update_decision_price(d["id"], float(p))
                    except Exception:
                        pass
            st.rerun()

        ddf = pd.DataFrame(decs)[
            [
                "id",
                "ticker",
                "asset_type",
                "decision",
                "status",
                "price_at_decision",
                "current_price",
                "return_pct",
                "thesis_quality_score",
                "thesis",
                "sell_criteria",
                "created_at",
            ]
        ]
        st.dataframe(ddf, use_container_width=True, hide_index=True)

        u1, u2, u3, u4 = st.columns([2, 2, 2, 1])
        pick_id = u1.selectbox("Update Decision #", [d["id"] for d in decs])
        new_status = u2.selectbox("New Status", ["open", "thesis_intact", "thesis_weakening", "thesis_broken", "sold"])
        rev_note = u3.text_input("Review Note")
        if u4.button("Update", use_container_width=True):
            db.update_decision_status(int(pick_id), new_status, review_notes=rev_note)
            st.rerun()

        render_download_buttons(ddf, {"Decision_Journal": ddf}, "investment_decisions")
