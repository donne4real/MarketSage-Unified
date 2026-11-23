"""Custom Metric Filter Builder, Screening Presets & Side-by-Side Comparison Matrix."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import pandas as pd


@dataclass
class FilterRule:
    metric: str
    op: str  # <=, >=, <, >, ==
    value: float


PRESET_FILTERS: dict[str, list[FilterRule]] = {
    "Under-$50 Value & Growth": [
        FilterRule("price", "<=", 50.0),
        FilterRule("pe_ratio", "<=", 25.0),
    ],
    "Deep Value (Graham-style)": [
        FilterRule("pe_ratio", "<=", 15.0),
        FilterRule("pb_ratio", "<=", 2.0),
        FilterRule("debt_to_equity", "<=", 0.8),
    ],
    "High-ROIC Quality Compounders": [
        FilterRule("roe", ">=", 0.18),
        FilterRule("operating_margin", ">=", 0.15),
        FilterRule("revenue_growth", ">=", 0.08),
    ],
    "Dividend Income Shield": [
        FilterRule("dividend_yield", ">=", 0.025),
        FilterRule("payout_ratio", "<=", 0.70),
    ],
    "Low-Cost Core ETFs": [
        FilterRule("expense_ratio", "<=", 0.0020),
    ],
}


def apply_custom_filters(infos: list[dict[str, Any]], rules: list[FilterRule]) -> list[dict[str, Any]]:
    """Filter normalized security dicts by all specified FilterRules."""
    if not rules:
        return list(infos)
    matched = []
    for info in infos:
        ok = True
        for r in rules:
            val = info.get(r.metric)
            if val is None:
                ok = False
                break
            v = float(val)
            if r.op == "<=" and not (v <= r.value):
                ok = False; break
            elif r.op == ">=" and not (v >= r.value):
                ok = False; break
            elif r.op == "<" and not (v < r.value):
                ok = False; break
            elif r.op == ">" and not (v > r.value):
                ok = False; break
            elif r.op == "==" and not (abs(v - r.value) < 1e-9):
                ok = False; break
        if ok:
            matched.append(info)
    return matched


def build_comparison_table(infos: list[dict[str, Any]]) -> pd.DataFrame:
    """Create a clean side-by-side comparison matrix across selected tickers."""
    metrics = [
        ("Name", "name", lambda v: str(v)),
        ("Asset Type", "asset_type", lambda v: str(v).upper()),
        ("Sector", "sector", lambda v: str(v)),
        ("Price ($)", "price", lambda v: f"${v:,.2f}"),
        ("Market Cap ($B)", "market_cap", lambda v: f"${v/1e9:,.2f}B"),
        ("P/E Ratio", "pe_ratio", lambda v: f"{v:.2f}"),
        ("Forward P/E", "forward_pe", lambda v: f"{v:.2f}"),
        ("P/B Ratio", "pb_ratio", lambda v: f"{v:.2f}"),
        ("PEG Ratio", "peg_ratio", lambda v: f"{v:.2f}"),
        ("ROE (%)", "roe", lambda v: f"{v*100:.1f}%"),
        ("Gross Margin (%)", "gross_margin", lambda v: f"{v*100:.1f}%"),
        ("Operating Margin (%)", "operating_margin", lambda v: f"{v*100:.1f}%"),
        ("Revenue Growth (%)", "revenue_growth", lambda v: f"{v*100:.1f}%"),
        ("Debt / Equity", "debt_to_equity", lambda v: f"{v:.2f}"),
        ("Current Ratio", "current_ratio", lambda v: f"{v:.2f}"),
        ("Dividend Yield (%)", "dividend_yield", lambda v: f"{v*100:.2f}%"),
        ("Expense Ratio (%)", "expense_ratio", lambda v: f"{v*100:.2f}%"),
        ("Beta", "beta", lambda v: f"{v:.2f}"),
    ]
    data: dict[str, list[str]] = {"Metric": [m[0] for m in metrics]}
    for info in infos:
        sym = info.get("ticker", "?")
        col_vals = []
        for _, key, fmt in metrics:
            val = info.get(key)
            if val is None or val == "":
                col_vals.append("—")
            else:
                try:
                    col_vals.append(fmt(val))
                except Exception:
                    col_vals.append(str(val))
        data[sym] = col_vals
    return pd.DataFrame(data)
