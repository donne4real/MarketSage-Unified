"""Dividend Analysis, Gordon Growth Model, 5-Year DCF Valuation & DRIP Income Projector."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import pandas as pd


@dataclass
class ValuationResult:
    method: str
    intrinsic_value: float
    current_price: float
    margin_of_safety_pct: float
    verdict: str


def gordon_growth_valuation(
    current_price: float,
    annual_dividend: float,
    dividend_growth_rate: float = 0.05,
    required_return: float = 0.095,
) -> ValuationResult:
    """Gordon Growth Model: V = D1 / (r - g)."""
    if annual_dividend <= 0 or required_return <= dividend_growth_rate or current_price <= 0:
        return ValuationResult("Gordon Growth Model", 0.0, current_price, 0.0, "Not Applicable")
    d1 = annual_dividend * (1.0 + dividend_growth_rate)
    intrinsic = d1 / (required_return - dividend_growth_rate)
    mos = ((intrinsic - current_price) / current_price) * 100.0
    verdict = "Undervalued" if mos >= 15 else "Fairly Valued" if mos >= -10 else "Overvalued"
    return ValuationResult(
        method="Gordon Growth Model",
        intrinsic_value=round(intrinsic, 2),
        current_price=round(current_price, 2),
        margin_of_safety_pct=round(mos, 1),
        verdict=verdict,
    )


def dcf_valuation(
    current_price: float,
    fcf_per_share: float,
    growth_rate_5y: float = 0.10,
    terminal_growth: float = 0.025,
    discount_rate: float = 0.10,
    net_cash_per_share: float = 0.0,
) -> ValuationResult:
    """5-year Discounted Free Cash Flow valuation per share."""
    if fcf_per_share <= 0 or discount_rate <= terminal_growth or current_price <= 0:
        return ValuationResult("5-Year FCF DCF", 0.0, current_price, 0.0, "Negative/Invalid FCF")

    pv_cash_flows = 0.0
    fcf = fcf_per_share
    for yr in range(1, 6):
        fcf *= 1.0 + growth_rate_5y
        pv_cash_flows += fcf / ((1.0 + discount_rate) ** yr)

    terminal_val = (fcf * (1.0 + terminal_growth)) / (discount_rate - terminal_growth)
    pv_terminal = terminal_val / ((1.0 + discount_rate) ** 5)
    intrinsic = max(0.0, pv_cash_flows + pv_terminal + net_cash_per_share)
    mos = ((intrinsic - current_price) / current_price) * 100.0
    verdict = "Undervalued" if mos >= 15 else "Fairly Valued" if mos >= -10 else "Overvalued"
    return ValuationResult(
        method="5-Year FCF DCF",
        intrinsic_value=round(intrinsic, 2),
        current_price=round(current_price, 2),
        margin_of_safety_pct=round(mos, 1),
        verdict=verdict,
    )


def dividend_safety_assessment(info: dict[str, Any]) -> dict[str, Any]:
    """Assess dividend sustainability from yield, payout ratio, FCF, and leverage."""
    dy = info.get("dividend_yield") or 0.0
    payout = info.get("payout_ratio")
    fcf = info.get("free_cash_flow")
    dte = info.get("debt_to_equity")

    if dy <= 0:
        return {"score": 0, "rating": "Non-Dividend", "notes": ["Security does not currently pay a dividend."]}

    score = 50
    notes: list[str] = []

    if payout is not None:
        if 0 < payout <= 0.50:
            score += 25; notes.append(f"Very safe payout ratio ({payout*100:.0f}%)")
        elif payout <= 0.70:
            score += 12; notes.append(f"Healthy payout ratio ({payout*100:.0f}%)")
        elif payout > 0.90:
            score -= 25; notes.append(f"Elevated payout risk ({payout*100:.0f}%)")

    if fcf is not None:
        if fcf > 0:
            score += 15; notes.append("Positive Free Cash Flow supports dividend")
        else:
            score -= 20; notes.append("Negative Free Cash Flow — sustainability watch")

    if dte is not None:
        if dte <= 0.8:
            score += 10; notes.append(f"Conservative debt load (D/E {dte:.2f})")
        elif dte > 2.0:
            score -= 15; notes.append(f"High leverage (D/E {dte:.2f})")

    if dy > 0.09:
        score -= 15; notes.append(f"Very high yield ({dy*100:.2f}%) — verify against yield-trap risk")

    score = max(0, min(100, score))
    rating = "Safe" if score >= 75 else "Moderate" if score >= 50 else "At Risk"
    return {"score": score, "rating": rating, "notes": notes}


def project_drip(
    initial_investment: float,
    monthly_contribution: float,
    starting_yield: float,
    dividend_growth_rate: float = 0.06,
    price_growth_rate: float = 0.05,
    years: int = 15,
    reinvest: bool = True,
) -> pd.DataFrame:
    """Year-by-year DRIP dividend income & portfolio value projection."""
    rows = []
    balance = float(initial_investment)
    total_contributed = float(initial_investment)
    cum_dividends = 0.0
    curr_yield = max(0.0, float(starting_yield))

    for yr in range(1, years + 1):
        annual_contrib = monthly_contribution * 12.0
        total_contributed += annual_contrib
        balance += annual_contrib
        annual_div = balance * curr_yield
        cum_dividends += annual_div
        balance = balance * (1.0 + price_growth_rate) + (annual_div if reinvest else 0.0)
        # Adjust effective yield based on dividend growth vs price growth
        curr_yield = curr_yield * ((1.0 + dividend_growth_rate) / max(1.0 + price_growth_rate, 0.01))
        rows.append(
            {
                "Year": yr,
                "Total Contributed ($)": round(total_contributed, 2),
                "Portfolio Value ($)": round(balance, 2),
                "Annual Dividend ($)": round(annual_div, 2),
                "Monthly Dividend ($)": round(annual_div / 12.0, 2),
                "Cumulative Dividends ($)": round(cum_dividends, 2),
                "Yield on Cost (%)": round((annual_div / max(total_contributed, 1.0)) * 100.0, 2),
            }
        )
    return pd.DataFrame(rows)
