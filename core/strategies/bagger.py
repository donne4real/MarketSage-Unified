"""10 Peter Lynch / Chris Mayer 100-Bagger Hunting Strategies."""

from __future__ import annotations
from typing import Any


def _mk(name: str, score: float, reasons: list[str], threshold: float = 65.0):
    from . import StrategyResult, score_to_signal

    s = round(max(0.0, min(100.0, score)), 1)
    return StrategyResult(name=name, score=s, passed=s >= threshold, signal=score_to_signal(s), reasons=reasons)


def _num(info: dict[str, Any], key: str) -> float | None:
    v = info.get(key)
    return float(v) if isinstance(v, (int, float)) else None


def bagger_runway(info: dict[str, Any]):
    mc = _num(info, "market_cap")
    if mc is None:
        return _mk("Small/Mid-Cap Runway", 40.0, ["Market cap unavailable"])
    if 300_000_000 <= mc <= 15_000_000_000:
        return _mk("Small/Mid-Cap Runway", 95.0, [f"Ideal multi-bagger runway (${mc/1e9:.2f}B)"])
    if 15_000_000_000 < mc <= 50_000_000_000:
        return _mk("Small/Mid-Cap Runway", 70.0, [f"Mid-to-large cap runway (${mc/1e9:.1f}B)"])
    if mc < 300_000_000:
        return _mk("Small/Mid-Cap Runway", 55.0, [f"Micro-cap (${mc/1e6:.0f}M — higher risk)"])
    return _mk("Small/Mid-Cap Runway", 25.0, [f"Mega-cap (${mc/1e9:.0f}B — harder to 100x)"])


def bagger_hyper_growth(info: dict[str, Any]):
    rg, eg = _num(info, "revenue_growth"), _num(info, "earnings_growth")
    score, reasons = 0.0, []
    if rg is not None and rg >= 0.25:
        score += 55; reasons.append(f"Rapid revenue expansion ({rg*100:.1f}% >= 25%)")
    elif rg is not None and rg >= 0.15:
        score += 35; reasons.append(f"Solid revenue growth ({rg*100:.1f}%)")
    if eg is not None and eg >= 0.25:
        score += 45; reasons.append(f"Accelerating earnings ({eg*100:.1f}%)")
    elif eg is not None and eg >= 0.12:
        score += 25
    return _mk("Hyper-Growth Engine", score, reasons)


def bagger_twin_engine_value(info: dict[str, Any]):
    peg, pe, ps = _num(info, "peg_ratio"), _num(info, "pe_ratio"), _num(info, "ps_ratio")
    score, reasons = 0.0, []
    if peg is not None and 0 < peg <= 1.2:
        score += 50; reasons.append(f"Twin-engine PEG ({peg:.2f} <= 1.2)")
    elif peg is not None and peg <= 1.8:
        score += 30
    if pe is not None and 0 < pe <= 28:
        score += 25; reasons.append(f"Reasonable P/E ({pe:.1f})")
    if ps is not None and 0 < ps <= 6:
        score += 25; reasons.append(f"Sensible P/S ({ps:.2f})")
    return _mk("Twin-Engine Valuation (PEG)", score, reasons)


def bagger_roic_profitability(info: dict[str, Any]):
    roe, roa, om = _num(info, "roe"), _num(info, "roa"), _num(info, "operating_margin")
    score, reasons = 0.0, []
    if roe is not None and roe >= 0.20:
        score += 45; reasons.append(f"High reinvestment ROE ({roe*100:.1f}%)")
    elif roe is not None and roe >= 0.12:
        score += 25
    if roa is not None and roa >= 0.10:
        score += 30; reasons.append(f"High ROA ({roa*100:.1f}%)")
    if om is not None and om >= 0.15:
        score += 25; reasons.append(f"Scalable operating margin ({om*100:.1f}%)")
    return _mk("ROIC & Reinvestment", score, reasons)


def bagger_moat_margins(info: dict[str, Any]):
    gm, pm = _num(info, "gross_margin"), _num(info, "profit_margin")
    score, reasons = 0.0, []
    if gm is not None and gm >= 0.55:
        score += 60; reasons.append(f"Software/brand-like gross margin ({gm*100:.1f}%)")
    elif gm is not None and gm >= 0.40:
        score += 40; reasons.append(f"Healthy gross margin ({gm*100:.1f}%)")
    if pm is not None and pm >= 0.15:
        score += 40; reasons.append(f"Strong net margin ({pm*100:.1f}%)")
    elif pm is not None and pm >= 0.08:
        score += 22
    return _mk("Moat & Pricing Power", score, reasons)


def bagger_financial_fortress(info: dict[str, Any]):
    dte, cr, fcf = _num(info, "debt_to_equity"), _num(info, "current_ratio"), _num(info, "free_cash_flow")
    score, reasons = 0.0, []
    if dte is not None and dte <= 0.5:
        score += 40; reasons.append(f"Low debt (D/E {dte:.2f})")
    elif dte is not None and dte <= 1.0:
        score += 20
    if cr is not None and cr >= 1.8:
        score += 30; reasons.append(f"Strong cash cushion (CR {cr:.2f})")
    if fcf is not None and fcf > 0:
        score += 30; reasons.append("Self-funding Free Cash Flow")
    return _mk("Financial Fortress", score, reasons)


def bagger_insider_alignment(info: dict[str, Any]):
    ins, inst = _num(info, "insider_ownership"), _num(info, "institutional_ownership")
    score, reasons = 0.0, []
    if ins is not None and ins >= 0.10:
        score += 65; reasons.append(f"Strong founder/insider skin-in-the-game ({ins*100:.1f}%)")
    elif ins is not None and ins >= 0.03:
        score += 40; reasons.append(f"Meaningful insider ownership ({ins*100:.1f}%)")
    if inst is not None and 0.25 <= inst <= 0.85:
        score += 35; reasons.append(f"Healthy institutional backing ({inst*100:.0f}%)")
    return _mk("Insider & Founder Alignment", score, reasons)


def bagger_momentum(info: dict[str, Any]):
    price, s50, s200 = _num(info, "price"), _num(info, "sma_50"), _num(info, "sma_200")
    score, reasons = 0.0, []
    if price and s50 and price > s50:
        score += 35; reasons.append("Uptrend above 50-SMA")
    if price and s200 and price > s200:
        score += 35; reasons.append("Secular uptrend above 200-SMA")
    if s50 and s200 and s50 > s200:
        score += 30; reasons.append("Golden cross alignment")
    return _mk("Secular Momentum", score, reasons)


def bagger_cash_compounder(info: dict[str, Any]):
    fcf, mc, rg = _num(info, "free_cash_flow"), _num(info, "market_cap"), _num(info, "revenue_growth")
    score, reasons = 0.0, []
    if fcf and fcf > 0:
        score += 40; reasons.append("Positive Free Cash Flow")
        if mc and mc > 0 and (fcf / mc) >= 0.03:
            score += 30; reasons.append(f"Attractive FCF yield ({fcf/mc*100:.1f}%)")
    if rg and rg >= 0.15:
        score += 30; reasons.append("Compounding top-line")
    return _mk("Cash Compounder", score, reasons)


def bagger_lynch_composite(info: dict[str, Any]):
    parts = [
        bagger_runway(info).score,
        bagger_hyper_growth(info).score,
        bagger_roic_profitability(info).score,
        bagger_moat_margins(info).score,
        bagger_financial_fortress(info).score,
    ]
    avg = sum(parts) / len(parts)
    return _mk("100-Bagger Master Score", avg, ["Composite of Runway, Growth, ROIC, Moat & Fortress"])


BAGGER_STRATEGIES = {
    "100-Bagger Master Score": bagger_lynch_composite,
    "Small/Mid-Cap Runway": bagger_runway,
    "Hyper-Growth Engine": bagger_hyper_growth,
    "Twin-Engine Valuation (PEG)": bagger_twin_engine_value,
    "ROIC & Reinvestment": bagger_roic_profitability,
    "Moat & Pricing Power": bagger_moat_margins,
    "Financial Fortress": bagger_financial_fortress,
    "Insider & Founder Alignment": bagger_insider_alignment,
    "Secular Momentum": bagger_momentum,
    "Cash Compounder": bagger_cash_compounder,
}
