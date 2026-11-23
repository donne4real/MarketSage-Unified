"""10 ETF Evaluation Strategies."""

from __future__ import annotations
from typing import Any


def _mk(name: str, score: float, reasons: list[str], threshold: float = 65.0):
    from . import StrategyResult, score_to_signal

    s = round(max(0.0, min(100.0, score)), 1)
    return StrategyResult(name=name, score=s, passed=s >= threshold, signal=score_to_signal(s), reasons=reasons)


def _num(info: dict[str, Any], key: str) -> float | None:
    v = info.get(key)
    return float(v) if isinstance(v, (int, float)) else None


def etf_cost_efficiency(info: dict[str, Any]):
    er = _num(info, "expense_ratio")
    if er is None:
        return _mk("Cost Efficiency", 50.0, ["Expense ratio unavailable"])
    if er <= 0.0010:
        return _mk("Cost Efficiency", 98.0, [f"Ultra-low expense ratio ({er*100:.2f}%)"])
    if er <= 0.0025:
        return _mk("Cost Efficiency", 82.0, [f"Low expense ratio ({er*100:.2f}%)"])
    if er <= 0.0050:
        return _mk("Cost Efficiency", 62.0, [f"Moderate expense ratio ({er*100:.2f}%)"])
    return _mk("Cost Efficiency", 30.0, [f"High expense ratio ({er*100:.2f}%)"])


def etf_liquidity_scale(info: dict[str, Any]):
    aum, vol = _num(info, "aum"), _num(info, "avg_volume")
    score, reasons = 0.0, []
    if aum and aum >= 10_000_000_000:
        score += 55; reasons.append(f"Institutional scale (AUM ${aum/1e9:.1f}B)")
    elif aum and aum >= 1_000_000_000:
        score += 40; reasons.append(f"Solid scale (AUM ${aum/1e9:.1f}B)")
    elif aum and aum >= 250_000_000:
        score += 25
    if vol and vol >= 1_000_000:
        score += 45; reasons.append(f"High daily liquidity ({vol/1e6:.1f}M shares)")
    elif vol and vol >= 200_000:
        score += 30
    return _mk("Liquidity & Scale", score, reasons)


def etf_dividend_income(info: dict[str, Any]):
    dy, er = _num(info, "dividend_yield"), _num(info, "expense_ratio")
    score, reasons = 0.0, []
    if dy and dy >= 0.03:
        score += 70; reasons.append(f"Strong income yield ({dy*100:.2f}%)")
    elif dy and dy >= 0.015:
        score += 45; reasons.append(f"Moderate yield ({dy*100:.2f}%)")
    if er is not None and er <= 0.0020:
        score += 30; reasons.append("Low fee preserves dividend income")
    return _mk("Dividend Income", score, reasons)


def etf_momentum(info: dict[str, Any]):
    price, s50, s200, ytd = _num(info, "price"), _num(info, "sma_50"), _num(info, "sma_200"), _num(info, "ytd_return")
    score, reasons = 0.0, []
    if price and s50 and price > s50:
        score += 35; reasons.append("Above 50-day SMA")
    if price and s200 and price > s200:
        score += 35; reasons.append("Above 200-day SMA")
    if ytd is not None and ytd > 0.10:
        score += 30; reasons.append(f"Strong YTD return ({ytd*100:.1f}%)")
    elif ytd is not None and ytd > 0:
        score += 18
    return _mk("Momentum", score, reasons)


def etf_value(info: dict[str, Any]):
    pe, pb, dy = _num(info, "pe_ratio"), _num(info, "pb_ratio"), _num(info, "dividend_yield")
    score, reasons = 0.0, []
    if pe and 0 < pe <= 18:
        score += 45; reasons.append(f"Value P/E ({pe:.1f})")
    elif pe and pe <= 24:
        score += 25
    if pb and 0 < pb <= 2.5:
        score += 30; reasons.append(f"Reasonable P/B ({pb:.2f})")
    if dy and dy >= 0.02:
        score += 25; reasons.append(f"Yield support ({dy*100:.2f}%)")
    return _mk("Value Tilt", score, reasons)


def etf_growth(info: dict[str, Any]):
    r3, r5, ytd = _num(info, "three_year_return"), _num(info, "five_year_return"), _num(info, "ytd_return")
    score, reasons = 0.0, []
    if r3 is not None and r3 >= 0.12:
        score += 40; reasons.append(f"Strong 3Y return ({r3*100:.1f}%)")
    elif r3 is not None and r3 >= 0.07:
        score += 25
    if r5 is not None and r5 >= 0.12:
        score += 40; reasons.append(f"Strong 5Y return ({r5*100:.1f}%)")
    elif r5 is not None and r5 >= 0.07:
        score += 25
    if ytd is not None and ytd >= 0.12:
        score += 20; reasons.append(f"Leading YTD ({ytd*100:.1f}%)")
    return _mk("Growth Compounding", score, reasons)


def etf_risk_adjusted(info: dict[str, Any]):
    beta, r3, er = _num(info, "beta"), _num(info, "three_year_return"), _num(info, "expense_ratio")
    score, reasons = 0.0, []
    if beta is not None and beta <= 1.05:
        score += 40; reasons.append(f"Controlled market beta ({beta:.2f})")
    elif beta is not None and beta <= 1.25:
        score += 22
    if r3 is not None and r3 >= 0.08:
        score += 35; reasons.append(f"Solid 3Y return ({r3*100:.1f}%)")
    if er is not None and er <= 0.0020:
        score += 25; reasons.append("Low fee drag")
    return _mk("Risk-Adjusted Return", score, reasons)


def etf_quality(info: dict[str, Any]):
    aum, er, r5 = _num(info, "aum"), _num(info, "expense_ratio"), _num(info, "five_year_return")
    score, reasons = 0.0, []
    if aum and aum >= 5_000_000_000:
        score += 35; reasons.append("Established flagship fund")
    if er is not None and er <= 0.0015:
        score += 35; reasons.append(f"Institutional pricing ({er*100:.2f}%)")
    if r5 is not None and r5 >= 0.08:
        score += 30; reasons.append(f"Consistent 5Y compounding ({r5*100:.1f}%)")
    return _mk("Fund Quality", score, reasons)


def etf_diversification(info: dict[str, Any]):
    cat = str(info.get("category", "") or info.get("name", "")).lower()
    aum = _num(info, "aum")
    score, reasons = 40.0, []
    if any(k in cat for k in ("total", "s&p 500", "blend", "world", "international", "bond", "aggregate", "large")):
        score += 40; reasons.append("Broad market diversification")
    if aum and aum >= 2_000_000_000:
        score += 20; reasons.append("Deep asset base")
    return _mk("Diversification", score, reasons)


def etf_core_holding(info: dict[str, Any]):
    c = etf_cost_efficiency(info).score
    l = etf_liquidity_scale(info).score
    d = etf_diversification(info).score
    score = 0.45 * c + 0.30 * l + 0.25 * d
    return _mk("Core Portfolio Anchor", score, [f"Blend of Cost ({c:.0f}), Scale ({l:.0f}), Diversification ({d:.0f})"])


ETF_STRATEGIES = {
    "Cost Efficiency": etf_cost_efficiency,
    "Liquidity & Scale": etf_liquidity_scale,
    "Dividend Income": etf_dividend_income,
    "Momentum": etf_momentum,
    "Value Tilt": etf_value,
    "Growth Compounding": etf_growth,
    "Risk-Adjusted Return": etf_risk_adjusted,
    "Fund Quality": etf_quality,
    "Diversification": etf_diversification,
    "Core Portfolio Anchor": etf_core_holding,
}
