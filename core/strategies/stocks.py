"""15 Stock Screening Strategies: 10 Classic Guru Philosophies + 5 Quantitative Models."""

from __future__ import annotations
from typing import Any


def _mk(name: str, score: float, reasons: list[str], threshold: float = 65.0):
    from . import StrategyResult, score_to_signal

    s = round(max(0.0, min(100.0, score)), 1)
    return StrategyResult(
        name=name, score=s, passed=s >= threshold, signal=score_to_signal(s), reasons=reasons
    )


def _num(info: dict[str, Any], key: str) -> float | None:
    v = info.get(key)
    return float(v) if isinstance(v, (int, float)) else None


def benjamin_graham(info: dict[str, Any]):
    score, reasons = 0.0, []
    pe, pb, cr, dte = _num(info, "pe_ratio"), _num(info, "pb_ratio"), _num(info, "current_ratio"), _num(info, "debt_to_equity")
    if pe is not None and 0 < pe <= 15:
        score += 30; reasons.append(f"Attractive P/E ({pe:.1f} <= 15)")
    elif pe is not None and 15 < pe <= 22:
        score += 15; reasons.append(f"Moderate P/E ({pe:.1f})")
    if pb is not None and 0 < pb <= 1.5:
        score += 25; reasons.append(f"Low P/B ({pb:.2f} <= 1.5)")
    elif pb is not None and 1.5 < pb <= 3.0:
        score += 12
    if cr is not None and cr >= 2.0:
        score += 25; reasons.append(f"Strong current ratio ({cr:.2f} >= 2.0)")
    elif cr is not None and cr >= 1.5:
        score += 15
    if dte is not None and dte <= 0.5:
        score += 20; reasons.append(f"Conservative debt/equity ({dte:.2f} <= 0.5)")
    elif dte is not None and dte <= 1.0:
        score += 10
    return _mk("Benjamin Graham (Defensive Value)", score, reasons)


def warren_buffett(info: dict[str, Any]):
    score, reasons = 0.0, []
    roe, gm, dte, fcf = _num(info, "roe"), _num(info, "gross_margin"), _num(info, "debt_to_equity"), _num(info, "free_cash_flow")
    pm = _num(info, "profit_margin")
    if roe is not None and roe >= 0.15:
        score += 30; reasons.append(f"High ROE ({roe*100:.1f}% >= 15%)")
    elif roe is not None and roe >= 0.10:
        score += 15
    if gm is not None and gm >= 0.40:
        score += 25; reasons.append(f"Wide gross margin ({gm*100:.1f}% >= 40%)")
    elif gm is not None and gm >= 0.25:
        score += 12
    if dte is not None and dte <= 0.5:
        score += 20; reasons.append(f"Low leverage (D/E {dte:.2f})")
    elif dte is not None and dte <= 1.0:
        score += 10
    if fcf is not None and fcf > 0:
        score += 15; reasons.append("Positive Free Cash Flow")
    if pm is not None and pm >= 0.15:
        score += 10; reasons.append(f"Strong net margin ({pm*100:.1f}%)")
    return _mk("Warren Buffett (Quality & Moat)", score, reasons)


def peter_lynch_garp(info: dict[str, Any]):
    score, reasons = 0.0, []
    peg, eg, dte = _num(info, "peg_ratio"), _num(info, "earnings_growth"), _num(info, "debt_to_equity")
    rg = _num(info, "revenue_growth")
    if peg is not None and 0 < peg <= 1.0:
        score += 40; reasons.append(f"Prime GARP PEG ({peg:.2f} <= 1.0)")
    elif peg is not None and 1.0 < peg <= 1.5:
        score += 25; reasons.append(f"Reasonable PEG ({peg:.2f})")
    if eg is not None and 0.15 <= eg <= 0.35:
        score += 30; reasons.append(f"Sweet-spot EPS growth ({eg*100:.1f}%)")
    elif eg is not None and eg > 0.10:
        score += 18
    elif rg is not None and rg > 0.12:
        score += 15; reasons.append(f"Solid revenue growth ({rg*100:.1f}%)")
    if dte is not None and dte <= 0.8:
        score += 30; reasons.append(f"Manageable debt (D/E {dte:.2f})")
    elif dte is not None and dte <= 1.5:
        score += 15
    return _mk("Peter Lynch (GARP)", score, reasons)


def joel_greenblatt(info: dict[str, Any]):
    score, reasons = 0.0, []
    ev_ebitda, roe, roa = _num(info, "ev_to_ebitda"), _num(info, "roe"), _num(info, "roa")
    om = _num(info, "operating_margin")
    if ev_ebitda is not None and 0 < ev_ebitda <= 12:
        score += 35; reasons.append(f"High earnings yield (EV/EBITDA {ev_ebitda:.1f})")
    elif ev_ebitda is not None and 12 < ev_ebitda <= 18:
        score += 20
    if roe is not None and roe >= 0.20:
        score += 30; reasons.append(f"Strong return on equity ({roe*100:.1f}%)")
    elif roe is not None and roe >= 0.12:
        score += 15
    if roa is not None and roa >= 0.10:
        score += 20; reasons.append(f"High ROA ({roa*100:.1f}%)")
    if om is not None and om >= 0.15:
        score += 15; reasons.append(f"Healthy operating margin ({om*100:.1f}%)")
    return _mk("Joel Greenblatt (Magic Formula)", score, reasons)


def william_oneil_canslim(info: dict[str, Any]):
    score, reasons = 0.0, []
    eg, rg = _num(info, "earnings_growth"), _num(info, "revenue_growth")
    price, h52 = _num(info, "price"), _num(info, "week_52_high")
    inst = _num(info, "institutional_ownership")
    if eg is not None and eg >= 0.25:
        score += 35; reasons.append(f"Explosive earnings growth ({eg*100:.1f}% >= 25%)")
    elif eg is not None and eg >= 0.15:
        score += 20
    if rg is not None and rg >= 0.20:
        score += 25; reasons.append(f"Strong top-line expansion ({rg*100:.1f}%)")
    elif rg is not None and rg >= 0.10:
        score += 12
    if price and h52 and h52 > 0 and price >= h52 * 0.85:
        score += 25; reasons.append("Trading within 15% of 52-week high")
    if inst is not None and inst >= 0.40:
        score += 15; reasons.append(f"Institutional sponsorship ({inst*100:.0f}%)")
    return _mk("William O'Neil (CAN SLIM)", score, reasons)


def piotroski_fscore(info: dict[str, Any]):
    pts, reasons = 0, []
    roa = _num(info, "roa")
    fcf = _num(info, "free_cash_flow")
    pm = _num(info, "profit_margin")
    cr = _num(info, "current_ratio")
    dte = _num(info, "debt_to_equity")
    gm = _num(info, "gross_margin")
    rg = _num(info, "revenue_growth")
    if roa is not None and roa > 0:
        pts += 1; reasons.append("Positive ROA")
    if fcf is not None and fcf > 0:
        pts += 2; reasons.append("Positive Free Cash Flow")
    if pm is not None and pm > 0.08:
        pts += 1; reasons.append(f"Healthy profit margin ({pm*100:.1f}%)")
    if cr is not None and cr >= 1.5:
        pts += 2; reasons.append(f"Solid liquidity (CR {cr:.2f})")
    if dte is not None and dte <= 0.7:
        pts += 1; reasons.append("Low financial leverage")
    if gm is not None and gm >= 0.30:
        pts += 1; reasons.append("Strong gross profitability")
    if rg is not None and rg > 0:
        pts += 1; reasons.append("Growing revenue")
    score = (pts / 9.0) * 100.0
    return _mk("Joseph Piotroski (F-Score)", score, reasons, threshold=66.0)


def oshaughnessy_trending_value(info: dict[str, Any]):
    score, reasons = 0.0, []
    mc, ps, price, sma200 = _num(info, "market_cap"), _num(info, "ps_ratio"), _num(info, "price"), _num(info, "sma_200")
    pe = _num(info, "pe_ratio")
    if mc is not None and mc >= 200_000_000:
        score += 20; reasons.append("Meets $200M+ market-cap floor")
    if ps is not None and 0 < ps <= 2.0:
        score += 30; reasons.append(f"Low Price/Sales ({ps:.2f} <= 2.0)")
    elif ps is not None and ps <= 4.0:
        score += 15
    if pe is not None and 0 < pe <= 18:
        score += 20; reasons.append(f"Value P/E ({pe:.1f})")
    if price and sma200 and price > sma200:
        score += 30; reasons.append("Positive long-term trend (Price > 200-SMA)")
    return _mk("James O'Shaughnessy (Trending Value)", score, reasons)


def david_dreman_contrarian(info: dict[str, Any]):
    score, reasons = 0.0, []
    pe, dy, cr, price, h52 = _num(info, "pe_ratio"), _num(info, "dividend_yield"), _num(info, "current_ratio"), _num(info, "price"), _num(info, "week_52_high")
    if pe is not None and 0 < pe <= 14:
        score += 35; reasons.append(f"Deep-value P/E ({pe:.1f})")
    elif pe is not None and pe <= 18:
        score += 20
    if dy is not None and dy >= 0.025:
        score += 25; reasons.append(f"Above-market dividend yield ({dy*100:.2f}%)")
    if cr is not None and cr >= 1.5:
        score += 20; reasons.append(f"Resilient balance sheet (CR {cr:.2f})")
    if price and h52 and h52 > 0 and price <= h52 * 0.85:
        score += 20; reasons.append("Pulled back >15% from 52-week high (contrarian setup)")
    return _mk("David Dreman (Contrarian)", score, reasons)


def philip_fisher_growth(info: dict[str, Any]):
    score, reasons = 0.0, []
    rg, pm, om, roe = _num(info, "revenue_growth"), _num(info, "profit_margin"), _num(info, "operating_margin"), _num(info, "roe")
    if rg is not None and rg >= 0.15:
        score += 35; reasons.append(f"High sales growth ({rg*100:.1f}% >= 15%)")
    elif rg is not None and rg >= 0.08:
        score += 20
    if pm is not None and pm >= 0.12:
        score += 25; reasons.append(f"Strong net margin ({pm*100:.1f}%)")
    elif pm is not None and pm >= 0.05:
        score += 15
    if om is not None and om >= 0.18:
        score += 20; reasons.append(f"Superior operating margin ({om*100:.1f}%)")
    if roe is not None and roe >= 0.18:
        score += 20; reasons.append(f"High capital efficiency (ROE {roe*100:.1f}%)")
    return _mk("Philip Fisher (Growth)", score, reasons)


def dividend_aristocrats(info: dict[str, Any]):
    score, reasons = 0.0, []
    dy, pr, dte, fcf = _num(info, "dividend_yield"), _num(info, "payout_ratio"), _num(info, "debt_to_equity"), _num(info, "free_cash_flow")
    if dy is not None and 0.025 <= dy <= 0.08:
        score += 35; reasons.append(f"Attractive sustainable yield ({dy*100:.2f}%)")
    elif dy is not None and dy >= 0.015:
        score += 20; reasons.append(f"Paying dividend ({dy*100:.2f}%)")
    if pr is not None and 0 < pr <= 0.65:
        score += 30; reasons.append(f"Safe payout ratio ({pr*100:.0f}% <= 65%)")
    elif pr is not None and pr <= 0.80:
        score += 15
    if fcf is not None and fcf > 0:
        score += 20; reasons.append("Dividend backed by positive FCF")
    if dte is not None and dte <= 1.2:
        score += 15; reasons.append("Balanced debt load")
    return _mk("Dividend Aristocrats", score, reasons)


def altman_z_safety(info: dict[str, Any]):
    score, reasons = 0.0, []
    cr, dte, roa, pm = _num(info, "current_ratio"), _num(info, "debt_to_equity"), _num(info, "roa"), _num(info, "profit_margin")
    if cr is not None and cr >= 1.8:
        score += 30; reasons.append(f"Strong working capital (CR {cr:.2f})")
    elif cr is not None and cr >= 1.2:
        score += 15
    if dte is not None and dte <= 0.6:
        score += 30; reasons.append(f"Low solvency risk (D/E {dte:.2f})")
    elif dte is not None and dte <= 1.2:
        score += 15
    if roa is not None and roa >= 0.08:
        score += 20; reasons.append(f"Productive assets (ROA {roa*100:.1f}%)")
    if pm is not None and pm >= 0.10:
        score += 20; reasons.append("Consistent profitability")
    return _mk("Altman Z-Score Safety", score, reasons)


def dividend_discount_model(info: dict[str, Any]):
    score, reasons = 0.0, []
    price, div_rate, rg = _num(info, "price"), _num(info, "dividend_rate"), _num(info, "revenue_growth")
    if not price or not div_rate or div_rate <= 0:
        return _mk("Dividend Discount Model (DDM)", 0.0, ["No dividend paid"])
    g = min(max((rg or 0.04) * 0.5, 0.02), 0.07)
    r = 0.095
    intrinsic = (div_rate * (1 + g)) / (r - g)
    upside = ((intrinsic - price) / price) * 100
    if upside >= 15:
        score = 90; reasons.append(f"DDM intrinsic ${intrinsic:.2f} (+{upside:.1f}% margin of safety)")
    elif upside >= 0:
        score = 70; reasons.append(f"Fairly valued on DDM (${intrinsic:.2f}, +{upside:.1f}%)")
    elif upside >= -20:
        score = 50; reasons.append(f"Modest premium to DDM (${intrinsic:.2f})")
    else:
        score = 25; reasons.append(f"Price well above DDM value (${intrinsic:.2f})")
    return _mk("Dividend Discount Model (DDM)", score, reasons)


def price_momentum(info: dict[str, Any]):
    score, reasons = 0.0, []
    price, s50, s200, h52, l52 = _num(info, "price"), _num(info, "sma_50"), _num(info, "sma_200"), _num(info, "week_52_high"), _num(info, "week_52_low")
    if price and s50 and price > s50:
        score += 30; reasons.append("Price above 50-day SMA")
    if price and s200 and price > s200:
        score += 30; reasons.append("Price above 200-day SMA")
    if s50 and s200 and s50 > s200:
        score += 20; reasons.append("Golden Cross structure (50-SMA > 200-SMA)")
    if price and h52 and l52 and h52 > l52:
        pos = (price - l52) / (h52 - l52)
        if pos >= 0.70:
            score += 20; reasons.append(f"Upper 52-week range ({pos*100:.0f}%)")
    return _mk("Price Momentum", score, reasons)


def compounding_quality(info: dict[str, Any]):
    score, reasons = 0.0, []
    roe, om, fcf, rg = _num(info, "roe"), _num(info, "operating_margin"), _num(info, "free_cash_flow"), _num(info, "revenue_growth")
    if roe is not None and roe >= 0.20:
        score += 30; reasons.append(f"Elite ROE ({roe*100:.1f}%)")
    elif roe is not None and roe >= 0.12:
        score += 15
    if om is not None and om >= 0.20:
        score += 25; reasons.append(f"High operating margin ({om*100:.1f}%)")
    elif om is not None and om >= 0.12:
        score += 12
    if fcf is not None and fcf > 0:
        score += 25; reasons.append("Strong free cash generation")
    if rg is not None and rg >= 0.08:
        score += 20; reasons.append(f"Durable growth ({rg*100:.1f}%)")
    return _mk("Compounding Quality", score, reasons)


def mean_reversion(info: dict[str, Any]):
    score, reasons = 0.0, []
    price, s50, s200, pe, roe = _num(info, "price"), _num(info, "sma_50"), _num(info, "sma_200"), _num(info, "pe_ratio"), _num(info, "roe")
    if price and s50 and price < s50 * 0.96:
        score += 35; reasons.append("Short-term pullback below 50-day SMA")
    if price and s200 and price >= s200 * 0.90:
        score += 25; reasons.append("Long-term structural support near 200-SMA")
    if pe is not None and 0 < pe <= 22:
        score += 20; reasons.append(f"Valuation cushion (P/E {pe:.1f})")
    if roe is not None and roe >= 0.12:
        score += 20; reasons.append("Quality fundamentals intact during dip")
    return _mk("Mean Reversion", score, reasons)


STOCK_STRATEGIES = {
    "Benjamin Graham (Defensive Value)": benjamin_graham,
    "Warren Buffett (Quality & Moat)": warren_buffett,
    "Peter Lynch (GARP)": peter_lynch_garp,
    "Joel Greenblatt (Magic Formula)": joel_greenblatt,
    "William O'Neil (CAN SLIM)": william_oneil_canslim,
    "Joseph Piotroski (F-Score)": piotroski_fscore,
    "James O'Shaughnessy (Trending Value)": oshaughnessy_trending_value,
    "David Dreman (Contrarian)": david_dreman_contrarian,
    "Philip Fisher (Growth)": philip_fisher_growth,
    "Dividend Aristocrats": dividend_aristocrats,
    "Altman Z-Score Safety": altman_z_safety,
    "Dividend Discount Model (DDM)": dividend_discount_model,
    "Price Momentum": price_momentum,
    "Compounding Quality": compounding_quality,
    "Mean Reversion": mean_reversion,
}
