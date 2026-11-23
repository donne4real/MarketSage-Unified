"""Technical Analysis Engine — Moving Averages, RSI, MACD, Bollinger Bands, Support/Resistance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple
import numpy as np
import pandas as pd


@dataclass
class TechnicalSummary:
    ticker: str
    current_price: float
    sma_20: float
    sma_50: float
    sma_200: float
    ema_12: float
    ema_26: float
    rsi_14: float
    macd: float
    macd_signal: float
    macd_hist: float
    bb_upper: float
    bb_middle: float
    bb_lower: float
    bb_position_pct: float
    support_1: float
    resistance_1: float
    volume_ratio: float
    trend_signal: str
    momentum_signal: str
    volatility_signal: str
    risk_reward_ratio: float


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=1).mean()


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0.0)).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def calculate_macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    macd_line = calculate_ema(series, fast) - calculate_ema(series, slow)
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(
    series: pd.Series, period: int = 20, num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    mid = calculate_sma(series, period)
    std = series.rolling(window=period, min_periods=1).std().fillna(0.0)
    return mid + num_std * std, mid, mid - num_std * std


def enrich_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of OHLCV DataFrame enriched with technical indicator columns."""
    out = df.copy()
    close = out["Close"].astype(float)
    out["SMA_20"] = calculate_sma(close, 20)
    out["SMA_50"] = calculate_sma(close, 50)
    out["SMA_200"] = calculate_sma(close, 200)
    out["EMA_12"] = calculate_ema(close, 12)
    out["EMA_26"] = calculate_ema(close, 26)
    out["RSI_14"] = calculate_rsi(close, 14)
    out["MACD"], out["MACD_Signal"], out["MACD_Hist"] = calculate_macd(close)
    out["BB_Upper"], out["BB_Middle"], out["BB_Lower"] = calculate_bollinger_bands(close)
    return out


def analyze_technicals(ticker: str, df: pd.DataFrame) -> TechnicalSummary:
    """Compute a complete TechnicalSummary snapshot from an OHLCV DataFrame."""
    if df is None or df.empty:
        raise ValueError(f"Price history is empty for {ticker}")

    ind = enrich_indicators(df)
    last = ind.iloc[-1]
    price = float(last["Close"])
    sma20, sma50, sma200 = float(last["SMA_20"]), float(last["SMA_50"]), float(last["SMA_200"])
    ema12, ema26 = float(last["EMA_12"]), float(last["EMA_26"])
    rsi = float(last["RSI_14"])
    macd, sig, hist = float(last["MACD"]), float(last["MACD_Signal"]), float(last["MACD_Hist"])
    bb_u, bb_m, bb_l = float(last["BB_Upper"]), float(last["BB_Middle"]), float(last["BB_Lower"])

    bb_span = max(bb_u - bb_l, 1e-9)
    bb_pos = max(0.0, min(100.0, ((price - bb_l) / bb_span) * 100.0))

    window = ind.tail(min(60, len(ind)))
    support_1 = float(window["Low"].min()) if "Low" in window else float(window["Close"].min())
    resistance_1 = float(window["High"].max()) if "High" in window else float(window["Close"].max())

    if "Volume" in ind and ind["Volume"].tail(20).mean() > 0:
        vol_ratio = float(ind["Volume"].iloc[-1] / ind["Volume"].tail(20).mean())
    else:
        vol_ratio = 1.0

    # Signals
    above = sum([price > sma20, price > sma50, price > sma200])
    trend_signal = "Bullish" if above >= 2 else "Bearish" if above == 0 else "Neutral"

    if rsi >= 70:
        momentum_signal = "Overbought"
    elif rsi <= 30:
        momentum_signal = "Oversold"
    elif macd > sig:
        momentum_signal = "Bullish Momentum"
    else:
        momentum_signal = "Bearish Momentum"

    if bb_pos >= 85:
        volatility_signal = "Near Upper Band"
    elif bb_pos <= 15:
        volatility_signal = "Near Lower Band"
    else:
        volatility_signal = "Mid-Band Normal"

    upside = max(resistance_1 - price, 0.0)
    downside = max(price - support_1, 0.01)
    rr = round(upside / downside, 2)

    return TechnicalSummary(
        ticker=ticker.upper(),
        current_price=round(price, 2),
        sma_20=round(sma20, 2),
        sma_50=round(sma50, 2),
        sma_200=round(sma200, 2),
        ema_12=round(ema12, 2),
        ema_26=round(ema26, 2),
        rsi_14=round(rsi, 1),
        macd=round(macd, 3),
        macd_signal=round(sig, 3),
        macd_hist=round(hist, 3),
        bb_upper=round(bb_u, 2),
        bb_middle=round(bb_m, 2),
        bb_lower=round(bb_l, 2),
        bb_position_pct=round(bb_pos, 1),
        support_1=round(support_1, 2),
        resistance_1=round(resistance_1, 2),
        volume_ratio=round(vol_ratio, 2),
        trend_signal=trend_signal,
        momentum_signal=momentum_signal,
        volatility_signal=volatility_signal,
        risk_reward_ratio=rr,
    )
