"""Reusable Streamlit sidebar, session engine, KPI styling, and Plotly visualizers."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core.ai_research import detect_provider
from core.data_engine import DataEngine
from core.database import Database
from core.exporter import export_csv_bytes, export_excel_bytes


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
