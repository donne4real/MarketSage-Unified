"""Reusable Streamlit sidebar, session engine, KPI styling, and Plotly visualizers."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core.ai_research import detect_provider
from core.data_engine import UNIVERSES as CURATED_UNIVERSES, DataEngine
from core.database import Database
from core.exporter import export_csv_bytes, export_excel_bytes
from core.universes import UniverseProvider, parse_uploaded_tickers


CUSTOM_CSS = """
<style>
.ms-hero {
    background: linear-gradient(135deg, #1e3a8a 0%, #4c1d95 100%);
    padding: 1.4rem 1.8rem;
    border-radius: 12px;
    margin-bottom: 1.2rem;
    border: 1px solid #334155;
}
.ms-hero h1 { margin: 0; font-size: 1.9rem; color: #f8fafc; }
.ms-hero p { margin: 0.35rem 0 0; color: #cbd5e1; font-size: 0.98rem; }
.ms-badge {
    display: inline-block;
    padding: 0.18rem 0.55rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-right: 0.35rem;
    background: #1e293b;
    border: 1px solid #334155;
    color: #93c5fd;
}
</style>
"""


@st.cache_resource
def get_db() -> Database:
    return Database()


def get_engine() -> DataEngine:
    order = st.session_state.get("source_order", "yf_first")
    delay = float(st.session_state.get("rate_limit_delay", 0.4))
    return DataEngine(db=get_db(), source_order=order, rate_limit_delay=delay)


def inject_theme() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_hero(title: str, subtitle: str) -> None:
    inject_theme()
    st.markdown(
        f'<div class="ms-hero"><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def render_sidebar() -> DataEngine:
    """Render shared sidebar with Source Priority, Live API Quota Monitor & Cache controls."""
    db = get_db()
    with st.sidebar:
        st.markdown("### MarketSage Unified")
        st.caption("US & Global Equities · ETFs · Mutual Funds · Valuation · Risk · AI")

        order_map = {
            "yfinance → Alpha Vantage → Twelve Data": "yf_first",
            "Alpha Vantage → Twelve Data → yfinance": "av_first",
            "Twelve Data → Alpha Vantage → yfinance": "td_first",
        }
        chosen = st.selectbox(
            "Data Source Priority",
            list(order_map.keys()),
            index=0,
            key="source_order_label",
        )
        st.session_state["source_order"] = order_map[chosen]
        st.session_state["rate_limit_delay"] = st.slider(
            "Batch Rate-Limit Delay (sec)", 0.0, 3.0, 0.4, 0.2
        )

        st.divider()
        st.markdown("#### Daily API Quota")
        quotas = db.get_quota_status()
        for src, q in quotas.items():
            label = src.replace("_", " ").title()
            icon = "⚠️" if q["warning"] else "✅"
            st.caption(f"{icon} **{label}:** {q['used']} / {q['limit']} ({q['percent']}%)")

        stats = db.cache_stats()
        st.caption(f"💾 **Active Cache Entries:** {stats.get('total', 0)} (24h TTL)")
        if st.button("Clear API Cache", use_container_width=True):
            cleared = db.clear_cache()
            st.success(f"Cleared {cleared} cached records.")

        provider = detect_provider()
        st.caption(f"🤖 **AI Engine:** `{provider}`")
        st.divider()
        st.caption("🇳🇬 Nigerian Exchange (NGX) lives in your dedicated [NGX Tracker](https://ngx-tracker.pages.dev).")
        st.caption("*Educational research tool — not financial advice.*")

    return get_engine()


def parse_tickers(text: str) -> list[str]:
    raw = text.replace("\n", ",").replace(" ", ",").split(",")
    seen: list[str] = []
    for item in raw:
        sym = item.strip().upper()
        if sym and sym not in seen:
            seen.append(sym)
    return seen


def render_single_ticker_input(
    key_prefix: str,
    label: str = "Ticker",
    placeholder: str = "e.g. AAPL",
    asset_type: str | None = None,
) -> str:
    """Clean empty ticker input with optional quick-pick from Watchlist/Portfolio."""
    db = get_db()
    saved_syms: list[str] = []
    for item in db.list_watchlist(asset_type=asset_type):
        if item["ticker"] not in saved_syms:
            saved_syms.append(item["ticker"])
    for h in db.list_holdings():
        if h["ticker"] not in saved_syms:
            saved_syms.append(h["ticker"])

    txt_key = f"{key_prefix}_single_ticker"
    st.session_state.setdefault(txt_key, "")

    if saved_syms:
        c_in, c_pick = st.columns([3, 2])
        with c_pick:
            picked = st.selectbox(
                "Quick-Pick Saved",
                ["— Type manually —"] + saved_syms,
                key=f"{key_prefix}_quick_pick",
            )
            if picked != "— Type manually —" and st.session_state.get(f"{key_prefix}_last_pick") != picked:
                st.session_state[txt_key] = picked
                st.session_state[f"{key_prefix}_last_pick"] = picked
        with c_in:
            val = st.text_input(label, placeholder=placeholder, key=txt_key)
    else:
        val = st.text_input(label, placeholder=placeholder, key=txt_key)
    return val.strip().upper()


def render_ticker_selector(
    key_prefix: str,
    asset_class: str = "stock",
    placeholder: str = "Type tickers (e.g. AAPL, MSFT, GOOGL) or load a market universe above...",
) -> list[str]:
    """Blank-by-default ticker selector with Live Market Discovery, Watchlist, Curated & CSV loaders."""
    db = get_db()
    provider = UniverseProvider(db=db)
    txt_key = f"{key_prefix}_tickers_text"
    st.session_state.setdefault(txt_key, "")

    # Build source options appropriate for this asset class
    sources = ["Manual Entry (Blank)", "My Watchlist", "My Portfolio Holdings"]
    if asset_class in {"stock", "bagger"}:
        sources += [
            "S&P 500 (Live)",
            "NASDAQ-100 (Live)",
            "Full NASDAQ Exchange (Live)",
            "Full NYSE Exchange (Live)",
        ]
    elif asset_class == "etf":
        sources += ["All US ETFs — NASDAQ & NYSE Arca (Live)"]

    curated_map = {
        "stock": ["US Blue-Chip & Tech Leaders", "Dividend Aristocrats", "Under-$50 Value & Growth"],
        "etf": ["Core & Sector ETFs"],
        "mutual_fund": ["Popular Mutual Funds"],
        "bagger": ["100-Bagger Candidates (Small/Mid Growth)"],
    }
    sources += ["Curated Starter Preset", "Upload CSV / TXT"]

    with st.expander("🌐 Load Market Universe, Watchlist, or CSV (Optional)", expanded=False):
        s_col, opt_col = st.columns([2, 2])
        source = s_col.selectbox("Ticker Source", sources, key=f"{key_prefix}_src")

        entries_key = f"{key_prefix}_loaded_entries"
        loaded_src_key = f"{key_prefix}_loaded_src_name"

        if source == "Upload CSV / TXT":
            uploaded = opt_col.file_uploader(
                "Upload CSV (Ticker/Symbol column) or TXT list",
                type=["csv", "txt"],
                key=f"{key_prefix}_csv",
            )
            if uploaded is not None:
                syms = parse_uploaded_tickers(uploaded.getvalue(), uploaded.name)
                if syms:
                    st.caption(f"Parsed **{len(syms)}** unique tickers from `{uploaded.name}`.")
                    if st.button("Apply Uploaded Tickers", key=f"{key_prefix}_apply_csv"):
                        st.session_state[txt_key] = ", ".join(syms)
                        st.rerun()
                else:
                    st.warning("No valid ticker symbols detected in file.")

        elif source != "Manual Entry (Blank)":
            preset_choice = None
            if source == "Curated Starter Preset":
                preset_choice = opt_col.selectbox(
                    "Starter List",
                    curated_map.get(asset_class, list(CURATED_UNIVERSES.keys())),
                    key=f"{key_prefix}_curated",
                )

            c_lim, c_rand, c_btn = st.columns([2, 1, 1])
            limit = c_lim.slider("Max Tickers to Load", 5, 100, 20, 5, key=f"{key_prefix}_limit")
            randomize = c_rand.checkbox("Random Sample", value=False, key=f"{key_prefix}_rand")

            # Check if we already fetched sector metadata for S&P 500 / NASDAQ-100
            cached_entries = (
                st.session_state.get(entries_key, [])
                if st.session_state.get(loaded_src_key) == source
                else []
            )
            sector_choice = "All Sectors"
            if source in {"S&P 500 (Live)", "NASDAQ-100 (Live)"} and cached_entries:
                sectors = sorted({e.get("sector", "Unknown") for e in cached_entries if e.get("sector")})
                if len(sectors) > 1:
                    sector_choice = opt_col.selectbox(
                        "Filter by Sector",
                        ["All Sectors"] + sectors,
                        key=f"{key_prefix}_sector",
                    )

            with c_btn:
                st.markdown("<br>", unsafe_allow_html=True)
                load_clicked = st.button("Load Tickers", key=f"{key_prefix}_load_btn", use_container_width=True)

            if load_clicked:
                try:
                    with st.spinner(f"Loading {source}..."):
                        if source == "My Watchlist":
                            entries = provider.get_watchlist_entries(
                                asset_type=asset_class if asset_class != "bagger" else None
                            )
                        elif source == "My Portfolio Holdings":
                            entries = provider.get_portfolio_entries()
                        elif source == "S&P 500 (Live)":
                            entries = provider.get_sp500()
                        elif source == "NASDAQ-100 (Live)":
                            entries = provider.get_nasdaq100()
                        elif source == "Full NASDAQ Exchange (Live)":
                            entries = provider.get_exchange_directory("NASDAQ", etfs_only=False)
                        elif source == "Full NYSE Exchange (Live)":
                            entries = provider.get_exchange_directory("NYSE", etfs_only=False)
                        elif source == "All US ETFs — NASDAQ & NYSE Arca (Live)":
                            entries = provider.get_exchange_directory("ALL", etfs_only=True)
                        elif source == "Curated Starter Preset" and preset_choice:
                            entries = provider.get_curated(preset_choice)
                        else:
                            entries = []

                    st.session_state[entries_key] = entries
                    st.session_state[loaded_src_key] = source
                    if not entries:
                        st.warning(f"No tickers found in '{source}'.")
                    else:
                        picked = provider.select_tickers(entries, sector=sector_choice, limit=limit, randomize=randomize)
                        st.session_state[txt_key] = ", ".join(picked)
                        st.success(f"Loaded {len(picked)} of {len(entries)} tickers from {source}.")
                        st.rerun()
                except Exception as exc:
                    st.error(f"Could not fetch live universe ({source}): {exc}")

    t_col, clr_col = st.columns([6, 1])
    with t_col:
        raw_text = st.text_area(
            "Tickers to Analyze (comma or newline separated)",
            placeholder=placeholder,
            height=80,
            key=txt_key,
        )
    with clr_col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("Clear", key=f"{key_prefix}_clear", use_container_width=True):
            st.session_state[txt_key] = ""
            st.rerun()

    return parse_tickers(raw_text)


def render_download_buttons(df: pd.DataFrame, sheets: dict[str, pd.DataFrame], prefix: str) -> None:
    if df is None or df.empty:
        return
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "Download CSV",
            data=export_csv_bytes(df),
            file_name=f"{prefix}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "Download Styled Excel (.xlsx)",
            data=export_excel_bytes(sheets, title=f"MarketSage — {prefix}"),
            file_name=f"{prefix}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def plot_strategy_scores(df: pd.DataFrame, title: str = "Composite Strategy Scores") -> go.Figure:
    sorted_df = df.sort_values("Composite Score", ascending=True)
    colors = [
        "#10b981" if s >= 80 else "#3b82f6" if s >= 65 else "#f59e0b" if s >= 45 else "#ef4444"
        for s in sorted_df["Composite Score"]
    ]
    fig = go.Figure(
        go.Bar(
            x=sorted_df["Composite Score"],
            y=sorted_df["Ticker"],
            orientation="h",
            marker_color=colors,
            text=sorted_df["Composite Score"].round(1),
            textposition="outside",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Composite Score (0–100)",
        xaxis_range=[0, 110],
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#1e293b",
        height=max(320, 32 * len(sorted_df) + 90),
        margin=dict(l=60, r=40, t=50, b=40),
    )
    return fig


def plot_candlestick_technicals(ind_df: pd.DataFrame, ticker: str) -> go.Figure:
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.55, 0.22, 0.23],
        subplot_titles=(f"{ticker} Price, SMAs & Bollinger Bands", "RSI (14)", "MACD (12, 26, 9)"),
    )
    fig.add_trace(
        go.Candlestick(
            x=ind_df.index,
            open=ind_df["Open"],
            high=ind_df["High"],
            low=ind_df["Low"],
            close=ind_df["Close"],
            name="OHLC",
        ),
        row=1,
        col=1,
    )
    for col, color in [("SMA_20", "#f59e0b"), ("SMA_50", "#3b82f6"), ("SMA_200", "#a855f7")]:
        fig.add_trace(go.Scatter(x=ind_df.index, y=ind_df[col], name=col, line=dict(width=1.4, color=color)), row=1, col=1)
    fig.add_trace(
        go.Scatter(x=ind_df.index, y=ind_df["BB_Upper"], name="BB Upper", line=dict(width=1, dash="dot", color="#64748b")),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(x=ind_df.index, y=ind_df["BB_Lower"], name="BB Lower", line=dict(width=1, dash="dot", color="#64748b")),
        row=1,
        col=1,
    )

    fig.add_trace(go.Scatter(x=ind_df.index, y=ind_df["RSI_14"], name="RSI-14", line=dict(color="#38bdf8")), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#10b981", row=2, col=1)

    fig.add_trace(go.Bar(x=ind_df.index, y=ind_df["MACD_Hist"], name="MACD Hist", marker_color="#64748b"), row=3, col=1)
    fig.add_trace(go.Scatter(x=ind_df.index, y=ind_df["MACD"], name="MACD", line=dict(color="#3b82f6")), row=3, col=1)
    fig.add_trace(go.Scatter(x=ind_df.index, y=ind_df["MACD_Signal"], name="Signal", line=dict(color="#f59e0b")), row=3, col=1)

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#1e293b",
        xaxis_rangeslider_visible=False,
        height=760,
        margin=dict(l=40, r=30, t=50, b=30),
    )
    return fig


def plot_equity_curve(curve_df: pd.DataFrame, title: str) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.07,
        row_heights=[0.7, 0.3],
        subplot_titles=(title, "Drawdown (%)"),
    )
    fig.add_trace(
        go.Scatter(x=curve_df.index, y=curve_df["Equity"], name="Strategy", line=dict(color="#3b82f6", width=2.2)),
        row=1,
        col=1,
    )
    if "Benchmark" in curve_df.columns:
        fig.add_trace(
            go.Scatter(
                x=curve_df.index,
                y=curve_df["Benchmark"],
                name="Benchmark (SPY)",
                line=dict(color="#94a3b8", width=1.6, dash="dash"),
            ),
            row=1,
            col=1,
        )
    fig.add_trace(
        go.Scatter(
            x=curve_df.index,
            y=curve_df["Drawdown"],
            name="Drawdown",
            fill="tozeroy",
            line=dict(color="#ef4444", width=1.2),
        ),
        row=2,
        col=1,
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#1e293b",
        height=540,
        margin=dict(l=40, r=30, t=50, b=30),
    )
    return fig


def plot_correlation_heatmap(corr_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        go.Heatmap(
            z=corr_df.values,
            x=list(corr_df.columns),
            y=list(corr_df.index),
            zmin=-1,
            zmax=1,
            colorscale="RdBu_r",
            text=corr_df.values,
            texttemplate="%{text:.2f}",
        )
    )
    fig.update_layout(
        title="Asset Return Correlation Matrix",
        template="plotly_dark",
        paper_bgcolor="#0f172a",
        plot_bgcolor="#1e293b",
        height=440,
    )
    return fig
