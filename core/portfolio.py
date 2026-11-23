"""Portfolio Construction, Risk Management (VaR/CVaR/Sortino/Correlation), Stress Testing & Rebalancing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import numpy as np
import pandas as pd


@dataclass
class RiskProfile:
    expected_annual_return_pct: float
    annual_volatility_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    beta: float
    var_95_daily_pct: float
    var_99_daily_pct: float
    cvar_95_daily_pct: float
    max_drawdown_pct: float
    diversification_score: float  # 0-100


def calculate_var(returns: pd.Series, confidence: float = 0.95, method: str = "historical") -> float:
    """Return positive percentage daily Value at Risk."""
    r = returns.dropna()
    if len(r) < 10:
        return 0.0
    if method == "parametric":
        z = 1.645 if confidence <= 0.95 else 2.326
        val = r.mean() - z * r.std()
        return round(abs(min(val, 0.0)) * 100.0, 2)
    if method == "monte_carlo":
        rng = np.random.default_rng(42)
        sims = rng.normal(r.mean(), max(r.std(), 1e-9), 10_000)
        val = float(np.percentile(sims, (1.0 - confidence) * 100.0))
        return round(abs(min(val, 0.0)) * 100.0, 2)
    val = float(r.quantile(1.0 - confidence))
    return round(abs(min(val, 0.0)) * 100.0, 2)


def calculate_cvar(returns: pd.Series, confidence: float = 0.95) -> float:
    """Conditional Value at Risk (Expected Shortfall)."""
    r = returns.dropna()
    if len(r) < 10:
        return 0.0
    thresh = float(r.quantile(1.0 - confidence))
    tail = r[r <= thresh]
    if tail.empty:
        return calculate_var(r, confidence)
    return round(abs(min(float(tail.mean()), 0.0)) * 100.0, 2)


def calculate_beta(asset_returns: pd.Series, market_returns: Optional[pd.Series]) -> float:
    if market_returns is None:
        return 1.0
    joined = pd.concat([asset_returns, market_returns], axis=1).dropna()
    if len(joined) < 15:
        return 1.0
    var_m = float(np.var(joined.iloc[:, 1]))
    if var_m <= 0:
        return 1.0
    cov = float(np.cov(joined.iloc[:, 0], joined.iloc[:, 1])[0, 1])
    return round(cov / var_m, 2)


def analyze_portfolio_risk(
    price_map: dict[str, pd.Series],
    weights: dict[str, float],
    market_prices: Optional[pd.Series] = None,
    risk_free_rate: float = 0.04,
) -> tuple[RiskProfile, pd.DataFrame]:
    """Compute portfolio RiskProfile and pairwise correlation matrix."""
    df = pd.DataFrame({k.upper(): s.astype(float) for k, s in price_map.items()}).dropna()
    if len(df) < 10:
        raise ValueError("Need at least 10 overlapping trading days to compute risk metrics")

    cols = list(df.columns)
    w = np.array([float(weights.get(c, 0.0)) for c in cols], dtype=float)
    w = w / w.sum() if w.sum() > 0 else np.ones(len(cols)) / len(cols)

    rets = df.pct_change().dropna()
    port_rets = pd.Series(rets.values @ w, index=rets.index)
    corr = rets.corr().round(2)

    ann_ret = float(port_rets.mean() * 252)
    ann_vol = float(port_rets.std() * np.sqrt(252))
    sharpe = (ann_ret - risk_free_rate) / ann_vol if ann_vol > 0 else 0.0

    down = port_rets[port_rets < 0]
    down_std = float(down.std() * np.sqrt(252)) if len(down) > 1 else 0.0
    sortino = (ann_ret - risk_free_rate) / down_std if down_std > 0 else 0.0

    mkt_rets = market_prices.pct_change().dropna() if market_prices is not None else None
    beta = calculate_beta(port_rets, mkt_rets)

    equity = (1.0 + port_rets).cumprod()
    dd = ((equity - equity.cummax()) / equity.cummax()) * 100.0
    max_dd = float(dd.min())

    # Diversification score: rewards lower concentration (HHI) and lower avg pairwise correlation
    hhi = float(np.sum(w ** 2))
    eff_n = 1.0 / max(hhi, 1e-9)
    n_score = min(100.0, (eff_n / max(len(cols), 1)) * 60.0 + min(len(cols) * 4.0, 40.0))
    if len(cols) > 1:
        upper = corr.values[np.triu_indices(len(cols), k=1)]
        avg_corr = float(np.nanmean(upper)) if len(upper) else 1.0
        corr_score = max(0.0, min(100.0, (1.0 - avg_corr) * 100.0))
        div_score = round(0.55 * n_score + 0.45 * corr_score, 1)
    else:
        div_score = 20.0

    profile = RiskProfile(
        expected_annual_return_pct=round(ann_ret * 100.0, 2),
        annual_volatility_pct=round(ann_vol * 100.0, 2),
        sharpe_ratio=round(sharpe, 2),
        sortino_ratio=round(sortino, 2),
        beta=beta,
        var_95_daily_pct=calculate_var(port_rets, 0.95),
        var_99_daily_pct=calculate_var(port_rets, 0.99),
        cvar_95_daily_pct=calculate_cvar(port_rets, 0.95),
        max_drawdown_pct=round(max_dd, 2),
        diversification_score=div_score,
    )
    return profile, corr


def stress_test_portfolio(total_value: float, beta: float) -> pd.DataFrame:
    """Estimate portfolio impact under classic historical & macro market shocks."""
    scenarios = [
        ("Mild Pullback (-10% Market)", -0.10),
        ("Rate Shock / Correction (-20% Market)", -0.20),
        ("2020 COVID Crash (-34% Market)", -0.34),
        ("2008 Financial Crisis (-50% Market)", -0.50),
        ("Bull Rally (+20% Market)", 0.20),
    ]
    rows = []
    for name, mkt_shock in scenarios:
        est_pct = mkt_shock * beta * 100.0
        est_pnl = total_value * (est_pct / 100.0)
        rows.append(
            {
                "Scenario": name,
                "Est. Portfolio Impact (%)": round(est_pct, 1),
                "Est. P&L ($)": round(est_pnl, 2),
                "Projected Value ($)": round(max(0.0, total_value + est_pnl), 2),
            }
        )
    return pd.DataFrame(rows)


def compute_rebalance_plan(
    holdings_rows: list[dict[str, Any]],
    current_prices: dict[str, float],
) -> pd.DataFrame:
    """Compute current weights, unrealized P&L, and buy/sell rebalance amounts vs target weights."""
    enriched = []
    total_val = 0.0
    for h in holdings_rows:
        sym = h["ticker"].upper()
        shares = float(h["shares"])
        cost = float(h["cost_basis"])
        price = float(current_prices.get(sym, cost))
        val = shares * price
        total_val += val
        enriched.append({**h, "ticker": sym, "price": price, "value": val, "cost_total": shares * cost})

    rows = []
    for e in enriched:
        curr_w = (e["value"] / total_val * 100.0) if total_val > 0 else 0.0
        target_w = e.get("target_weight")
        pnl = e["value"] - e["cost_total"]
        pnl_pct = (pnl / e["cost_total"] * 100.0) if e["cost_total"] > 0 else 0.0
        rebal_usd = ((float(target_w) - curr_w) / 100.0 * total_val) if target_w is not None else 0.0
        action = "HOLD"
        if target_w is not None:
            if rebal_usd > 25:
                action = f"BUY ${rebal_usd:,.0f}"
            elif rebal_usd < -25:
                action = f"TRIM ${abs(rebal_usd):,.0f}"
        rows.append(
            {
                "Ticker": e["ticker"],
                "Bucket": e.get("bucket", "core"),
                "Shares": round(e["shares"], 4),
                "Avg Cost ($)": round(e["cost_basis"], 2),
                "Price ($)": round(e["price"], 2),
                "Market Value ($)": round(e["value"], 2),
                "Unrealized P&L ($)": round(pnl, 2),
                "Return (%)": round(pnl_pct, 1),
                "Current Wt (%)": round(curr_w, 1),
                "Target Wt (%)": round(float(target_w), 1) if target_w is not None else None,
                "Rebalance Action": action,
            }
        )
    return pd.DataFrame(rows)
