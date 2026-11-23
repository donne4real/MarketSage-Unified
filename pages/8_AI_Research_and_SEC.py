"""Page 8: AI Research Assistant, SEC EDGAR 10-K Filings & Analyst Consensus."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.ai_research import detect_provider, detect_red_flags, generate_research_brief
from ui.components import get_db, render_hero, render_sidebar, render_single_ticker_input

st.set_page_config(page_title="AI Research & SEC | MarketSage", page_icon="🤖", layout="wide")
engine = render_sidebar()
db = get_db()

render_hero(
    "🤖 AI Research Assistant & SEC EDGAR Filings",
    "Combine live SEC 10-K/10-Q retrieval, automated red-flag checks, Wall Street analyst price targets, and multi-provider LLM synthesis (Claude / Gemini / OpenAI).",
)

c1, c2, c3 = st.columns([3, 1, 1])
with c1:
    ticker = render_single_ticker_input("ai_single", label="Security Ticker", placeholder="e.g. MSFT, AAPL, VOO")
fetch_10k = c2.checkbox("Include Latest SEC 10-K Text", value=True)
force_ai = c3.checkbox("Bypass AI Cache", value=False)

st.caption(f"Detected AI provider: **`{detect_provider()}`** (works offline with deterministic quant brief if no API key is set in `.env`).")

if st.button("Run Deep Research", type="primary"):
    if not ticker:
        st.warning("Enter a ticker symbol first.")
        st.stop()
    with st.spinner(f"Gathering fundamentals, analyst ratings, SEC filings & research brief for {ticker}..."):
        try:
            info = engine.get_ticker_info(ticker)
            ratings = engine.get_analyst_ratings(ticker)
            filings = engine.get_sec_filings(ticker)
            ten_k_doc = engine.get_latest_10k(ticker) if fetch_10k else None
            flags = detect_red_flags(info)

            cached_ai = None if force_ai else db.get_ai_cache(ticker, info.get("asset_type", "stock"))
            if cached_ai:
                brief = cached_ai["data"]
            else:
                brief = generate_research_brief(info, ten_k_excerpt=ten_k_doc["text"] if ten_k_doc else None)
                db.set_ai_cache(ticker, info.get("asset_type", "stock"), brief.get("provider", "offline"), brief)

            st.session_state["research_payload"] = {
                "info": info,
                "ratings": ratings,
                "filings": filings,
                "ten_k_doc": ten_k_doc,
                "flags": flags,
                "brief": brief,
            }
        except Exception as exc:
            st.error(f"Research run failed for {ticker}: {exc}")

payload = st.session_state.get("research_payload")
if payload:
    info = payload["info"]
    ratings = payload["ratings"]
    brief = payload["brief"]
    flags = payload["flags"]
    filings = payload["filings"]

    st.subheader(f"{info.get('name')} ({info.get('ticker')})")

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Current Price", f"${info.get('price', 0):,.2f}")
    a2.metric("Analyst Consensus", ratings.get("consensus", "N/A"), f"{ratings.get('num_analysts', 0)} analysts")
    tm = ratings.get("target_mean")
    up = ratings.get("upside_pct")
    a3.metric("Mean Target", f"${tm:,.2f}" if tm else "—", f"{up:+.1f}%" if up is not None else "")
    a4.metric("Brief Engine", brief.get("provider", "offline").upper())

    if flags:
        st.warning("**Automated Red Flags:**\n" + "\n".join(f"- {f}" for f in flags))
    else:
        st.success("No automated financial health red flags detected.")

    st.info("*AI/Research output is for educational synthesis only — not financial advice.*")

    b1, b2 = st.columns([3, 2])
    with b1:
        st.markdown("#### Business & Thesis Overview")
        st.write(brief.get("business_summary", ""))
        st.markdown("#### Valuation Context")
        st.write(brief.get("valuation_read", ""))
        st.markdown("#### SEC 10-K / Filing Takeaway")
        st.write(brief.get("filing_note", ""))
    with b2:
        st.markdown("#### Key Strengths")
        for s in brief.get("key_strengths", []):
            st.markdown(f"- ✅ {s}")
        st.markdown("#### Bear Case & Risks")
        for r in brief.get("bear_case", []):
            st.markdown(f"- ⚠️ {r}")
        st.markdown("#### Thesis Reflection Prompts")
        for q in brief.get("thesis_prompts", []):
            st.markdown(f"- ❓ {q}")

    st.divider()
    st.markdown("#### 📄 Recent SEC EDGAR Filings")
    if filings:
        fdf = pd.DataFrame(filings)[["form", "filing_date", "accession", "url"]]
        st.dataframe(fdf, use_container_width=True, hide_index=True)
    else:
        st.caption("No SEC EDGAR filings returned for this ticker (ETFs/foreign tickers may not map to a US CIK).")
