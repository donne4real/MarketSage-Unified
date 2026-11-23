"""Unified Backtesting Engine — Buy & Hold, SMA Crossover, RSI Mean Reversion & Multi-Ticker Portfolio."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd

from .technicals import calculate_rsi, calculate_sma


@dataclass
class BacktestResult:
    strategy_name: str
    initial_capital: float
    final_value: float
    total_return_pct: float
    cagr_pct: float
    volatility_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    num_trades: int
    equity_curve: pd.DataFrame  # columns: Equity, Benchmark (optional), Drawdown


def _compute_metrics(
    equity: pd.Series,
    strategy_name: str,
    initial_capital: float,
    num_trades: int,
    benchmark: Optional[pd.Series] = None,
    risk_free_rate: float = 0.04,
) -> BacktestResult:
    returns = equity.pct_change().dropna()
    final_val = float(equity.iloc[-1])
    total_ret = ((final_val / initial_capital) - 1.0) * 100.0

    days = max((equity.index[-1] - equity.index[0]).days, 1) if hasattr(equity.index[0], "year") else len(equity)
    years = max(days / 365.25, 1 / 252)
    cagr = (((final_val / initial_capital) ** (1.0 / years)) - 1.0) * 100.0 if final_val > 0 else -100.0

    vol = float(returns.std() * np.sqrt(252) * 100.0) if len(returns) > 1 else 0.0
    ann_ret = float(returns.mean() * 252) if len(returns) > 1 else 0.0
    sharpe = (ann_ret - risk_free_rate) / (vol / 100.0) if vol > 0 else 0.0

    downside = returns[returns < 0]
    down_std = float(downside.std() * np.sqrt(252)) if len(downside) > 1 else 0.0
    sortino = (ann_ret - risk_free_rate) / down_std if down_std > 0 else 0.0

    roll_max = equity.cummax()
    dd = ((equity - roll_max) / roll_max) * 100.0
    max_dd = float(dd.min())

    win_rate = float((returns > 0).mean() * 100.0) if len(returns) > 0 else 0.0

    curve = pd.DataFrame({"Equity": equity, "Drawdown": dd})
    if benchmark is not None and not benchmark.empty:
        aligned = benchmark.reindex(equity.index).ffill().bfill()
        if aligned.iloc[0] > 0:
            curve["Benchmark"] = initial_capital * (aligned / aligned.iloc[0])

    return BacktestResult(
        strategy_name=strategy_name,
        initial_capital=round(initial_capital, 2),
        final_value=round(final_val, 2),
        total_return_pct=round(total_ret, 2),
        cagr_pct=round(cagr, 2),
        volatility_pct=round(vol, 2),
        sharpe_ratio=round(sharpe, 2),
        sortino_ratio=round(sortino, 2),
        max_drawdown_pct=round(max_dd, 2),
        win_rate_pct=round(win_rate, 1),
        num_trades=int(num_trades),
        equity_curve=curve,
    )


def backtest_single(
    prices: pd.Series,
    strategy: str = "buy_and_hold",
    initial_capital: float = 10_000.0,
    benchmark: Optional[pd.Series] = None,
    fast_window: int = 20,
    slow_window: int = 50,
    rsi_buy: float = 30.0,
    rsi_sell: float = 70.0,
    commission_bps: float = 5.0,
) -> BacktestResult:
    """Run a single-ticker strategy backtest on a Close price Series."""
    close = prices.dropna().astype(float)
    if len(close) < 5:
        raise ValueError("Need at least 5 price points to backtest")

    daily_ret = close.pct_change().fillna(0.0)
    fee = commission_bps / 10_000.0

    if strategy == "sma_crossover":
        fast = calculate_sma(close, fast_window)
        slow = calculate_sma(close, slow_window)
        signal = (fast > slow).astype(float).shift(1).fillna(0.0)
        label = f"SMA Crossover ({fast_window}/{slow_window})"
    elif strategy == "rsi_mean_reversion":
        rsi = calculate_rsi(close, 14)
        pos = []
        holding = 0.0
        for val in rsi:
            if val <= rsi_buy:
                holding = 1.0
            elif val >= rsi_sell:
                holding = 0.0
            pos.append(holding)
        signal = pd.Series(pos, index=close.index).shift(1).fillna(0.0)
        label = f"RSI Mean Reversion ({int(rsi_buy)}/{int(rsi_sell)})"
    else:
        signal = pd.Series(1.0, index=close.index)
        label = "Buy & Hold"

    trades = signal.diff().abs().fillna(0.0)
    strat_ret = signal * daily_ret - trades * fee
    equity = initial_capital * (1.0 + strat_ret).cumprod()
    num_trades = int((trades > 0).sum()) if strategy != "buy_and_hold" else 1

    return _compute_metrics(equity, label, initial_capital, num_trades, benchmark=benchmark)


def backtest_portfolio(
    price_map: dict[str, pd.Series],
    weights: Optional[dict[str, float]] = None,
    initial_capital: float = 10_000.0,
    benchmark: Optional[pd.Series] = None,
) -> BacktestResult:
    """Backtest a weighted multi-asset portfolio over overlapping trading dates."""
    df = pd.DataFrame({k.upper(): s.astype(float) for k, s in price_map.items()}).dropna()
    if len(df) < 5:
        raise ValueError("Not enough overlapping price history across selected tickers")

    cols = list(df.columns)
    if weights:
        w = np.array([float(weights.get(c, 0.0)) for c in cols], dtype=float)
        w = w / w.sum() if w.sum() > 0 else np.ones(len(cols)) / len(cols)
    else:
        w = np.ones(len(cols)) / len(cols)

    rets = df.pct_change().fillna(0.0)
    port_ret = rets.values @ w
    equity = pd.Series(initial_capital * np.cumprod(1.0 + port_ret), index=df.index)
    return _compute_metrics(equity, f"Weighted Portfolio ({len(cols)} assets)", initial_capital, len(cols), benchmark=benchmark)
