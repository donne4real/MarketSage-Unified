"""10 Mutual Fund Evaluation Strategies."""

from __future__ import annotations
from typing import Any


def _mk(name: str, score: float, reasons: list[str], threshold: float = 65.0):
    from . import StrategyResult, score_to_signal

    s = round(max(0.0, min(100.0, score)), 1)
    return StrategyResult(name=name, score=s, passed=s >= threshold, signal=score_to_signal(s), reasons=reasons)


def _num(info: dict[str, Any], key: str) -> float | None:
    v = info.get(key)
    return float(v) if isinstance(v, (int, float)) else None


def mf_cost(info: dict[str, Any]):
    er = _num(info, "expense_ratio")
    if er is None:
        return _mk("Cost Efficiency", 50.0, ["Expense ratio not reported"])
    if er <= 0.0010:
        return _mk("Cost Efficiency", 98.0, [f"Index-class fee ({er*100:.2f}%)"])
    if er <= 0.0040:
        return _mk("Cost Efficiency", 80.0, [f"Low mutual fund fee ({er*100:.2f}%)"])
    if er <= 0.0075:
        return _mk("Cost Efficiency", 58.0, [f"Average active fee ({er*100:.2f}%)"])
    return _mk("Cost Efficiency", 25.0, [f"High fee drag ({er*100:.2f}%)"])


def mf_performance(info: dict[str, Any]):
    r3, r5, ytd = _num(info, "three_year_return"), _num(info, "five_year_return"), _num(info, "ytd_return")
    score, reasons = 0.0, []
    if r5 is not None and r5 >= 0.10:
        score += 45; reasons.append(f"Strong 5Y return ({r5*100:.1f}%)")
    elif r5 is not None and r5 >= 0.06:
        score += 28
    if r3 is not None and r3 >= 0.09:
        score += 35; reasons.append(f"Strong 3Y return ({r3*100:.1f}%)")
    elif r3 is not None and r3 >= 0.05:
        score += 22
    if ytd is not None and ytd > 0.05:
        score += 20; reasons.append(f"Positive YTD ({ytd*100:.1f}%)")
    return _mk("Long-Term Performance", score, reasons)


def mf_risk_adjusted(info: dict[str, Any]):
    beta, r5, er = _num(info, "beta"), _num(info, "five_year_return"), _num(info, "expense_ratio")
    score, reasons = 0.0, []
    if beta is not None and beta <= 1.05:
        score += 40; reasons.append(f"Controlled beta ({beta:.2f})")
    if r5 is not None and r5 >= 0.08:
        score += 35; reasons.append("Strong 5Y return per unit risk")
    if er is not None and er <= 0.0030:
        score += 25; reasons.append("Low fee boosts net alpha")
    return _mk("Risk-Adjusted Return", score, reasons)


def mf_scale_stability(info: dict[str, Any]):
    aum = _num(info, "aum")
    fam = str(info.get("fund_family", "")).lower()
    score, reasons = 20.0, []
    if aum and aum >= 10_000_000_000:
        score += 55; reasons.append(f"Large flagship fund (${aum/1e9:.1f}B AUM)")
    elif aum and aum >= 1_000_000_000:
        score += 40; reasons.append(f"Well-scaled fund (${aum/1e9:.1f}B AUM)")
    if any(k in fam for k in ("vanguard", "fidelity", "schwab", "t. rowe", "dodge", "american")):
        score += 25; reasons.append(f"Top-tier fund family ({info.get('fund_family')})")
    return _mk("Manager & Family Quality", score, reasons)


def mf_income(info: dict[str, Any]):
    dy, er = _num(info, "dividend_yield"), _num(info, "expense_ratio")
    score, reasons = 0.0, []
    if dy and dy >= 0.03:
        score += 70; reasons.append(f"Strong distribution yield ({dy*100:.2f}%)")
    elif dy and dy >= 0.015:
        score += 45; reasons.append(f"Moderate yield ({dy*100:.2f}%)")
    if er is not None and er <= 0.0035:
        score += 30; reasons.append("Low fee preserves yield")
    return _mk("Income Generation", score, reasons)


def mf_growth(info: dict[str, Any]):
    r3, r5 = _num(info, "three_year_return"), _num(info, "five_year_return")
    cat = str(info.get("category", "") or info.get("name", "")).lower()
    score, reasons = 0.0, []
    if r5 and r5 >= 0.12:
        score += 45; reasons.append(f"High 5Y growth ({r5*100:.1f}%)")
    if r3 and r3 >= 0.12:
        score += 35; reasons.append(f"High 3Y growth ({r3*100:.1f}%)")
    if "growth" in cat or "500" in cat or "total" in cat:
        score += 20; reasons.append("Growth/broad equity mandate")
    return _mk("Growth Orientation", score, reasons)


def mf_tax_efficiency(info: dict[str, Any]):
    er = _num(info, "expense_ratio")
    name = str(info.get("name", "")).lower()
    score, reasons = 40.0, []
    if "index" in name or "500" in name or "total" in name:
        score += 35; reasons.append("Low-turnover index structure")
    if er is not None and er <= 0.0015:
        score += 25; reasons.append("Passive low-cost wrapper")
    return _mk("Tax Efficiency", score, reasons)


def mf_diversification(info: dict[str, Any]):
    cat = str(info.get("category", "") or info.get("name", "")).lower()
    score, reasons = 45.0, []
    if any(k in cat for k in ("total", "500", "blend", "balanced", "allocation", "international", "bond")):
        score += 40; reasons.append("Broad multi-sector diversification")
    if _num(info, "aum") and (_num(info, "aum") or 0) >= 5_000_000_000:
        score += 15
    return _mk("Diversification", score, reasons)


def mf_consistency(info: dict[str, Any]):
    r3, r5, ytd = _num(info, "three_year_return"), _num(info, "five_year_return"), _num(info, "ytd_return")
    score, reasons = 0.0, []
    if r3 is not None and r3 > 0.06:
        score += 35; reasons.append("Positive 3Y compounding")
    if r5 is not None and r5 > 0.07:
        score += 40; reasons.append("Positive 5Y compounding")
    if ytd is not None and ytd > 0:
        score += 25; reasons.append("Positive YTD momentum")
    return _mk("Return Consistency", score, reasons)


def mf_core_quality(info: dict[str, Any]):
    c = mf_cost(info).score
    s = mf_scale_stability(info).score
    p = mf_performance(info).score
    score = 0.40 * c + 0.30 * s + 0.30 * p
    return _mk("Core Fund Quality", score, [f"Weighted Cost ({c:.0f}), Family ({s:.0f}), Performance ({p:.0f})"])


MUTUAL_FUND_STRATEGIES = {
    "Cost Efficiency": mf_cost,
    "Long-Term Performance": mf_performance,
    "Risk-Adjusted Return": mf_risk_adjusted,
    "Manager & Family Quality": mf_scale_stability,
    "Income Generation": mf_income,
    "Growth Orientation": mf_growth,
    "Tax Efficiency": mf_tax_efficiency,
    "Diversification": mf_diversification,
    "Return Consistency": mf_consistency,
    "Core Fund Quality": mf_core_quality,
}
