"""Unified Strategy Engine across Stocks, ETFs, Mutual Funds, and 100-Bagger candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
import pandas as pd

from .stocks import STOCK_STRATEGIES
from .etfs import ETF_STRATEGIES
from .mutual_funds import MUTUAL_FUND_STRATEGIES
from .bagger import BAGGER_STRATEGIES


@dataclass
class StrategyResult:
    """Standardized evaluation result for a single strategy on a single security."""

    name: str
    score: float  # 0 to 100
    passed: bool
    signal: str  # Strong Buy / Buy / Hold / Avoid (educational scoring signal)
    reasons: list[str] = field(default_factory=list)


StrategyFn = Callable[[dict[str, Any]], StrategyResult]

STRATEGY_REGISTRIES: dict[str, dict[str, StrategyFn]] = {
    "stock": STOCK_STRATEGIES,
    "etf": ETF_STRATEGIES,
    "mutual_fund": MUTUAL_FUND_STRATEGIES,
    "bagger": BAGGER_STRATEGIES,
}


def score_to_signal(score: float) -> str:
    if score >= 80:
        return "Strong Pass"
    if score >= 65:
        return "Pass"
    if score >= 45:
        return "Watch"
    return "Fail"


def evaluate_security(
    info: dict[str, Any],
    asset_class: str = "stock",
    selected_strategies: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate one security across selected (or all) strategies for its asset class."""
    registry = STRATEGY_REGISTRIES.get(asset_class, STOCK_STRATEGIES)
    names = selected_strategies or list(registry.keys())
    results: list[StrategyResult] = []
    for name in names:
        fn = registry.get(name)
        if fn is None:
            continue
        results.append(fn(info))

    avg_score = round(sum(r.score for r in results) / len(results), 1) if results else 0.0
    passed_names = [r.name for r in results if r.passed]
    return {
        "ticker": info.get("ticker", ""),
        "name": info.get("name", ""),
        "sector": info.get("sector", "Unknown"),
        "price": info.get("price", 0.0),
        "market_cap": info.get("market_cap"),
        "pe_ratio": info.get("pe_ratio"),
        "pb_ratio": info.get("pb_ratio"),
        "peg_ratio": info.get("peg_ratio"),
        "roe": info.get("roe"),
        "profit_margin": info.get("profit_margin"),
        "revenue_growth": info.get("revenue_growth"),
        "debt_to_equity": info.get("debt_to_equity"),
        "dividend_yield": info.get("dividend_yield"),
        "expense_ratio": info.get("expense_ratio"),
        "aum": info.get("aum"),
        "beta": info.get("beta"),
        "composite_score": avg_score,
        "signal": score_to_signal(avg_score),
        "strategies_passed": len(passed_names),
        "strategies_total": len(results),
        "passed_list": ", ".join(passed_names),
        "details": results,
        "raw_info": info,
    }


def evaluate_batch(
    infos: list[dict[str, Any]],
    asset_class: str = "stock",
    selected_strategies: list[str] | None = None,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Evaluate a list of securities and return (sorted summary DataFrame, full evaluations)."""
    evals = [evaluate_security(info, asset_class, selected_strategies) for info in infos]
    evals.sort(key=lambda x: (x["composite_score"], x["strategies_passed"]), reverse=True)
    rows = []
    for e in evals:
        rows.append(
            {
                "Ticker": e["ticker"],
                "Name": e["name"],
                "Sector": e["sector"],
                "Price": round(e["price"], 2) if e["price"] else None,
                "Composite Score": e["composite_score"],
                "Rating": e["signal"],
                "Passed": f"{e['strategies_passed']}/{e['strategies_total']}",
                "P/E": round(e["pe_ratio"], 2) if e["pe_ratio"] is not None else None,
                "P/B": round(e["pb_ratio"], 2) if e["pb_ratio"] is not None else None,
                "ROE %": round(e["roe"] * 100, 1) if e["roe"] is not None else None,
                "Rev Growth %": round(e["revenue_growth"] * 100, 1) if e["revenue_growth"] is not None else None,
                "Div Yield %": round(e["dividend_yield"] * 100, 2) if e["dividend_yield"] is not None else None,
                "Exp Ratio %": round(e["expense_ratio"] * 100, 2) if e["expense_ratio"] is not None else None,
                "Passed Strategies": e["passed_list"],
            }
        )
    return pd.DataFrame(rows), evals
