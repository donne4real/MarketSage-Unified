"""Unified Multi-Source Data Engine.

Fallback chain: configurable priority across Alpha Vantage, Twelve Data, and yfinance,
backed by a 24-hour per-source SQLite cache, daily quota tracking, and SEC EDGAR integration.
"""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Optional
import pandas as pd
import yfinance as yf

from .config import DEFAULT_CACHE_TTL_HOURS, DEFAULT_RATE_LIMIT_DELAY, get_source_order
from .database import Database
from .sources import alpha_vantage, sec_edgar, twelve_data


# Curated starter universes across all 4 asset classes
UNIVERSES: dict[str, list[str]] = {
    "US Blue-Chip & Tech Leaders": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "BRK-B", "JPM",
        "V", "JNJ", "UNH", "PG", "HD", "COST", "AVGO", "LLY",
    ],
    "Dividend Aristocrats": [
        "JNJ", "PG", "KO", "PEP", "MCD", "WMT", "XOM", "CVX",
        "ABBV", "T", "VZ", "O", "MMM", "CAT", "CL", "ED",
    ],
    "Under-$50 Value & Growth": [
        "F", "BAC", "PFE", "INTC", "T", "SOFI", "PLTR", "NU",
        "WBD", "SNAP", "CSCO", "VALE", "AAL", "KMI", "HPE",
    ],
    "Core & Sector ETFs": [
        "VOO", "VTI", "QQQ", "SCHD", "VXUS", "BND", "VNQ", "XLK",
        "XLV", "XLF", "XLE", "ARKK", "IWM", "VEA", "VWO", "AGG",
    ],
    "Popular Mutual Funds": [
        "VFIAX", "FXAIX", "VTSAX", "SWPPX", "VWELX", "FBGRX",
        "VWELX", "PRGFX", "FCNTX", "VBTLX", "VTMGX", "DODGX",
    ],
    "100-Bagger Candidates (Small/Mid Growth)": [
        "CELH", "DUOL", "ELF", "HIMS", "TMDX", "AXON", "MELI",
        "CRWD", "DDOG", "TTD", "ENPH", "SOFI", "NU", "RKLB", "APP",
    ],
}


def _to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if pd.isna(val):
            return None
        return float(val)
    s = str(val).strip().replace("%", "").replace(",", "")
    if not s or s.lower() in {"none", "nan", "n/a", "-"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _is_rate_limit(err: Exception) -> bool:
    msg = str(err).lower()
    return any(k in msg for k in ("429", "too many requests", "rate limit", "expecting value"))


def normalize_info(raw: dict[str, Any], source: str, ticker: str) -> dict[str, Any]:
    """Normalize raw info from Alpha Vantage, Twelve Data, or yfinance into a canonical schema."""
    sym = ticker.upper().strip()

    if source == "alpha_vantage":
        asset_raw = str(raw.get("AssetType", "")).lower()
        asset_type = "etf" if "etf" in asset_raw else "mutual_fund" if "fund" in asset_raw else "stock"
        price = _to_float(raw.get("50DayMovingAverage")) or _to_float(raw.get("AnalystTargetPrice")) or 0.0
        return {
            "ticker": sym,
            "source": source,
            "asset_type": asset_type,
            "name": raw.get("Name") or sym,
            "sector": raw.get("Sector") or "Unknown",
            "industry": raw.get("Industry") or "Unknown",
            "exchange": raw.get("Exchange") or "",
            "currency": raw.get("Currency") or "USD",
            "summary": raw.get("Description") or "",
            "price": price,
            "market_cap": _to_float(raw.get("MarketCapitalization")),
            "pe_ratio": _to_float(raw.get("PERatio")),
            "forward_pe": _to_float(raw.get("ForwardPE")),
            "pb_ratio": _to_float(raw.get("PriceToBookRatio")),
            "ps_ratio": _to_float(raw.get("PriceToSalesRatioTTM")),
            "peg_ratio": _to_float(raw.get("PEGRatio")),
            "ev_to_ebitda": _to_float(raw.get("EVToEBITDA")),
            "roe": _to_float(raw.get("ReturnOnEquityTTM")),
            "roa": _to_float(raw.get("ReturnOnAssetsTTM")),
            "gross_margin": _to_float(raw.get("GrossProfitTTM")),
            "operating_margin": _to_float(raw.get("OperatingMarginTTM")),
            "profit_margin": _to_float(raw.get("ProfitMargin")),
            "revenue_growth": _to_float(raw.get("QuarterlyRevenueGrowthYOY")),
            "earnings_growth": _to_float(raw.get("QuarterlyEarningsGrowthYOY")),
            "debt_to_equity": None,
            "current_ratio": None,
            "free_cash_flow": None,
            "dividend_yield": _to_float(raw.get("DividendYield")),
            "dividend_rate": _to_float(raw.get("DividendPerShare")),
            "payout_ratio": None,
            "beta": _to_float(raw.get("Beta")),
            "week_52_high": _to_float(raw.get("52WeekHigh")),
            "week_52_low": _to_float(raw.get("52WeekLow")),
            "sma_50": _to_float(raw.get("50DayMovingAverage")),
            "sma_200": _to_float(raw.get("200DayMovingAverage")),
            "avg_volume": None,
            "shares_outstanding": _to_float(raw.get("SharesOutstanding")),
            "insider_ownership": None,
            "institutional_ownership": None,
            "expense_ratio": _to_float(raw.get("ExpenseRatio")),
            "aum": _to_float(raw.get("NetAssets")),
            "ytd_return": None,
            "three_year_return": None,
            "five_year_return": None,
            "category": raw.get("Sector") or "",
            "fund_family": "",
            "target_mean_price": _to_float(raw.get("AnalystTargetPrice")),
        }

    if source == "twelve_data":
        inst_type = str(raw.get("instrument_type", raw.get("type", ""))).lower()
        asset_type = "etf" if "etf" in inst_type else "mutual_fund" if "fund" in inst_type else "stock"
        wk52 = raw.get("fifty_two_week") or {}
        return {
            "ticker": sym,
            "source": source,
            "asset_type": asset_type,
            "name": raw.get("name") or raw.get("instrument_name") or sym,
            "sector": raw.get("sector") or "Unknown",
            "industry": raw.get("industry") or "Unknown",
            "exchange": raw.get("exchange") or "",
            "currency": raw.get("currency") or "USD",
            "summary": "",
            "price": _to_float(raw.get("close") or raw.get("price")) or 0.0,
            "market_cap": _to_float(raw.get("market_cap")),
            "pe_ratio": None,
            "forward_pe": None,
            "pb_ratio": None,
            "ps_ratio": None,
            "peg_ratio": None,
            "ev_to_ebitda": None,
            "roe": None,
            "roa": None,
            "gross_margin": None,
            "operating_margin": None,
            "profit_margin": None,
            "revenue_growth": None,
            "earnings_growth": None,
            "debt_to_equity": None,
            "current_ratio": None,
            "free_cash_flow": None,
            "dividend_yield": None,
            "dividend_rate": None,
            "payout_ratio": None,
            "beta": None,
            "week_52_high": _to_float(wk52.get("high") if isinstance(wk52, dict) else None),
            "week_52_low": _to_float(wk52.get("low") if isinstance(wk52, dict) else None),
            "sma_50": None,
            "sma_200": None,
            "avg_volume": _to_float(raw.get("average_volume") or raw.get("volume")),
            "shares_outstanding": None,
            "insider_ownership": None,
            "institutional_ownership": None,
            "expense_ratio": None,
            "aum": None,
            "ytd_return": None,
            "three_year_return": None,
            "five_year_return": None,
            "category": "",
            "fund_family": "",
            "target_mean_price": None,
        }

    # Default: yfinance schema
    qtype = str(raw.get("quoteType", "")).upper()
    if qtype == "ETF":
        asset_type = "etf"
    elif qtype == "MUTUALFUND":
        asset_type = "mutual_fund"
    else:
        asset_type = "stock"

    price = (
        _to_float(raw.get("currentPrice"))
        or _to_float(raw.get("regularMarketPrice"))
        or _to_float(raw.get("navPrice"))
        or _to_float(raw.get("previousClose"))
        or 0.0
    )

    # Normalize yfinance debtToEquity (often returned as percentage like 150.0 -> 1.50)
    dte = _to_float(raw.get("debtToEquity"))
    if dte is not None and dte > 10:
        dte = dte / 100.0

    # Normalize dividend yield (yfinance v1 sometimes returns 0.025 vs 2.5)
    div_y = _to_float(raw.get("dividendYield"))
    if div_y is None:
        div_y = _to_float(raw.get("yield"))
    if div_y is not None and div_y > 0.5:
        div_y = div_y / 100.0

    exp_ratio = _to_float(raw.get("annualReportExpenseRatio"))
    if exp_ratio is None:
        net_exp = _to_float(raw.get("netExpenseRatio"))
        if net_exp is not None:
            exp_ratio = net_exp / 100.0 if net_exp > 0.2 else net_exp

    return {
        "ticker": sym,
        "source": source,
        "asset_type": asset_type,
        "name": raw.get("longName") or raw.get("shortName") or sym,
        "sector": raw.get("sector") or raw.get("category") or "Unknown",
        "industry": raw.get("industry") or raw.get("fundFamily") or "Unknown",
        "exchange": raw.get("exchange") or "",
        "currency": raw.get("currency") or "USD",
        "summary": raw.get("longBusinessSummary") or "",
        "price": price,
        "market_cap": _to_float(raw.get("marketCap")),
        "pe_ratio": _to_float(raw.get("trailingPE")),
        "forward_pe": _to_float(raw.get("forwardPE")),
        "pb_ratio": _to_float(raw.get("priceToBook")),
        "ps_ratio": _to_float(raw.get("priceToSalesTrailing12Months")),
        "peg_ratio": _to_float(raw.get("pegRatio") or raw.get("trailingPegRatio")),
        "ev_to_ebitda": _to_float(raw.get("enterpriseToEbitda")),
        "roe": _to_float(raw.get("returnOnEquity")),
        "roa": _to_float(raw.get("returnOnAssets")),
        "gross_margin": _to_float(raw.get("grossMargins")),
        "operating_margin": _to_float(raw.get("operatingMargins")),
        "profit_margin": _to_float(raw.get("profitMargins")),
        "revenue_growth": _to_float(raw.get("revenueGrowth")),
        "earnings_growth": _to_float(raw.get("earningsGrowth") or raw.get("earningsQuarterlyGrowth")),
        "debt_to_equity": dte,
        "current_ratio": _to_float(raw.get("currentRatio")),
        "free_cash_flow": _to_float(raw.get("freeCashflow")),
        "total_cash": _to_float(raw.get("totalCash")),
        "total_debt": _to_float(raw.get("totalDebt")),
        "dividend_yield": div_y,
        "dividend_rate": _to_float(raw.get("dividendRate")),
        "payout_ratio": _to_float(raw.get("payoutRatio")),
        "beta": _to_float(raw.get("beta") or raw.get("beta3Year")),
        "week_52_high": _to_float(raw.get("fiftyTwoWeekHigh")),
        "week_52_low": _to_float(raw.get("fiftyTwoWeekLow")),
        "sma_50": _to_float(raw.get("fiftyDayAverage")),
        "sma_200": _to_float(raw.get("twoHundredDayAverage")),
        "avg_volume": _to_float(raw.get("averageVolume")),
        "shares_outstanding": _to_float(raw.get("sharesOutstanding")),
        "insider_ownership": _to_float(raw.get("heldPercentInsiders")),
        "institutional_ownership": _to_float(raw.get("heldPercentInstitutions")),
        "expense_ratio": exp_ratio,
        "aum": _to_float(raw.get("totalAssets")),
        "ytd_return": _to_float(raw.get("ytdReturn")),
        "three_year_return": _to_float(raw.get("threeYearAverageReturn")),
        "five_year_return": _to_float(raw.get("fiveYearAverageReturn")),
        "category": raw.get("category") or "",
        "fund_family": raw.get("fundFamily") or "",
        "target_mean_price": _to_float(raw.get("targetMeanPrice")),
        "target_high_price": _to_float(raw.get("targetHighPrice")),
        "target_low_price": _to_float(raw.get("targetLowPrice")),
        "num_analysts": int(raw.get("numberOfAnalystOpinions") or 0),
        "recommendation_key": raw.get("recommendationKey") or "N/A",
    }


class DataEngine:
    """Resilient, cache-first multi-source market data engine."""

    def __init__(
        self,
        db: Optional[Database] = None,
        source_order: Optional[str] = None,
        rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY,
        ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
    ):
        self.db = db or Database()
        self.source_order_mode = source_order
        self.rate_limit_delay = rate_limit_delay
        self.ttl_hours = ttl_hours

    def _sources(self) -> list[str]:
        return get_source_order(self.source_order_mode)

    def _yf_info(self, ticker: str) -> dict:
        t = yf.Ticker(ticker.upper())
        for attempt in range(2):
            try:
                info = t.info or {}
                if info and (info.get("regularMarketPrice") or info.get("currentPrice") or info.get("longName") or info.get("previousClose")):
                    return info
                return info
            except Exception as err:
                if _is_rate_limit(err) and attempt == 0:
                    time.sleep(1.5 + random.uniform(0, 0.5))
                    continue
                raise
        return {}

    def _yf_history(self, ticker: str, period: str = "2y") -> pd.DataFrame:
        t = yf.Ticker(ticker.upper())
        df = t.history(period=period, auto_adjust=True)
        if df is None or df.empty:
            return pd.DataFrame()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])

    def get_ticker_info(self, ticker: str, force_refresh: bool = False) -> dict[str, Any]:
        """Fetch normalized security metrics with cache-first + multi-source fallback."""
        sym = ticker.upper().strip()
        sources = self._sources()

        if not force_refresh:
            for src in sources:
                cached = self.db.get_cached(src, "info", sym)
                if cached:
                    out = normalize_info(cached, src, sym)
                    out["from_cache"] = True
                    return out

        errors: list[str] = []
        for src in sources:
            try:
                if src == "alpha_vantage":
                    if not alpha_vantage.is_configured():
                        continue
                    raw = alpha_vantage.get_overview(sym)
                    self.db.set_cached(src, "info", sym, raw, ttl_hours=self.ttl_hours)
                    self.db.increment_quota(src)
                    out = normalize_info(raw, src, sym)
                    out["from_cache"] = False
                    return out

                if src == "twelve_data":
                    if not twelve_data.is_configured():
                        continue
                    raw = {**twelve_data.get_symbol_info(sym), **twelve_data.get_quote(sym)}
                    if not raw:
                        raise RuntimeError("Empty Twelve Data response")
                    self.db.set_cached(src, "info", sym, raw, ttl_hours=self.ttl_hours)
                    self.db.increment_quota(src)
                    out = normalize_info(raw, src, sym)
                    out["from_cache"] = False
                    return out

                if src == "yfinance":
                    raw = self._yf_info(sym)
                    if not raw:
                        raise RuntimeError(f"No yfinance info for {sym}")
                    self.db.set_cached(src, "info", sym, raw, ttl_hours=self.ttl_hours)
                    self.db.increment_quota(src)
                    out = normalize_info(raw, src, sym)
                    out["from_cache"] = False
                    return out
            except Exception as exc:
                errors.append(f"{src}: {exc}")

        raise RuntimeError(f"Failed to fetch info for {sym} ({'; '.join(errors) or 'no configured source'})")

    def get_price_history(
        self, ticker: str, period: str = "2y", force_refresh: bool = False
    ) -> pd.DataFrame:
        """Fetch OHLCV price history DataFrame with 24h SQLite caching."""
        sym = ticker.upper().strip()
        params = {"period": period}
        sources = self._sources()

        if not force_refresh:
            for src in sources:
                cached = self.db.get_cached(src, "history", sym, params=params)
                if cached:
                    df = pd.DataFrame(cached)
                    df["Date"] = pd.to_datetime(df["Date"])
                    return df.set_index("Date").sort_index()

        errors: list[str] = []
        for src in sources:
            try:
                df = pd.DataFrame()
                if src == "alpha_vantage" and alpha_vantage.is_configured():
                    out_size = "full" if period in {"3y", "5y", "10y", "max"} else "compact"
                    df = alpha_vantage.get_daily_prices(sym, outputsize=out_size)
                elif src == "twelve_data" and twelve_data.is_configured():
                    df = twelve_data.get_time_series(sym)
                elif src == "yfinance":
                    df = self._yf_history(sym, period=period)
                else:
                    continue

                if not df.empty:
                    records = df.reset_index().rename(columns={df.index.name or "index": "Date"})
                    records["Date"] = records["Date"].astype(str)
                    self.db.set_cached(
                        src, "history", sym, records.to_dict(orient="records"), params=params, ttl_hours=self.ttl_hours
                    )
                    self.db.increment_quota(src)
                    return df
            except Exception as exc:
                errors.append(f"{src}: {exc}")

        raise RuntimeError(f"Failed to fetch price history for {sym} ({'; '.join(errors)})")

    def get_batch_info(
        self,
        tickers: list[str],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[dict[str, Any]]:
        """Fetch multiple tickers politely with progress callback and failure isolation."""
        results: list[dict[str, Any]] = []
        clean = [t.upper().strip() for t in tickers if t.strip()]
        total = len(clean)
        for idx, sym in enumerate(clean):
            if progress_callback:
                progress_callback(idx + 1, total, sym)
            try:
                info = self.get_ticker_info(sym)
                results.append(info)
                if not info.get("from_cache") and self.rate_limit_delay > 0 and idx < total - 1:
                    time.sleep(self.rate_limit_delay)
            except Exception:
                continue
        return results

    def get_etf_holdings(self, ticker: str) -> dict[str, Any]:
        """Fetch ETF top holdings and sector weights (yfinance primary, Alpha Vantage fallback)."""
        sym = ticker.upper().strip()
        cached = self.db.get_cached("yfinance", "etf_holdings", sym)
        if cached:
            return cached

        result: dict[str, Any] = {"top_holdings": [], "sector_breakdown": []}
        try:
            t = yf.Ticker(sym)
            fd = getattr(t, "funds_data", None)
            if fd is not None:
                top = getattr(fd, "top_holdings", None)
                if top is not None and not getattr(top, "empty", True):
                    rows = []
                    for idx, row in top.iterrows():
                        rows.append(
                            {
                                "symbol": str(idx),
                                "name": str(row.get("Name", idx)),
                                "weight": float(row.get("Holding Percent", 0) or 0),
                            }
                        )
                    result["top_holdings"] = rows
                sec = getattr(fd, "sector_weightings", None)
                if isinstance(sec, dict):
                    result["sector_breakdown"] = [
                        {"sector": k.replace("_", " ").title(), "weight": float(v or 0)}
                        for k, v in sec.items()
                    ]
        except Exception:
            pass

        if not result["top_holdings"] and alpha_vantage.is_configured():
            try:
                prof = alpha_vantage.get_etf_profile(sym)
                result["top_holdings"] = prof.get("holdings", [])[:15]
                result["sector_breakdown"] = prof.get("sectors", [])
                self.db.increment_quota("alpha_vantage")
            except Exception:
                pass

        if result["top_holdings"] or result["sector_breakdown"]:
            self.db.set_cached("yfinance", "etf_holdings", sym, result, ttl_hours=self.ttl_hours)
        return result

    def get_analyst_ratings(self, ticker: str) -> dict[str, Any]:
        """Fetch analyst consensus, price targets, and upside potential."""
        sym = ticker.upper().strip()
        info = self.get_ticker_info(sym)
        price = info.get("price") or 0.0
        target = info.get("target_mean_price")
        upside = round(((target - price) / price) * 100, 2) if (target and price > 0) else None
        rec_counts = {"Strong Buy": 0, "Buy": 0, "Hold": 0, "Sell": 0, "Strong Sell": 0}
        try:
            recs = yf.Ticker(sym).recommendations
            if recs is not None and not recs.empty:
                latest = recs.iloc[0]
                mapping = {
                    "strongBuy": "Strong Buy",
                    "buy": "Buy",
                    "hold": "Hold",
                    "sell": "Sell",
                    "strongSell": "Strong Sell",
                }
                for src_k, dst_k in mapping.items():
                    if src_k in latest:
                        rec_counts[dst_k] = int(latest[src_k] or 0)
        except Exception:
            pass

        return {
            "ticker": sym,
            "consensus": str(info.get("recommendation_key", "N/A")).replace("_", " ").title(),
            "num_analysts": info.get("num_analysts", 0),
            "current_price": price,
            "target_mean": target,
            "target_high": info.get("target_high_price"),
            "target_low": info.get("target_low_price"),
            "upside_pct": upside,
            "recommendations": rec_counts,
        }

    def get_sec_filings(self, ticker: str, form_types: Optional[list[str]] = None) -> list[dict]:
        sym = ticker.upper().strip()
        params = {"forms": form_types or ["10-K", "10-Q", "8-K"]}
        cached = self.db.get_cached("sec_edgar", "filings", sym, params=params)
        if cached is not None:
            return cached
        filings = sec_edgar.get_recent_filings(sym, form_types=form_types)
        if filings:
            self.db.set_cached("sec_edgar", "filings", sym, filings, params=params, ttl_hours=self.ttl_hours)
            self.db.increment_quota("sec_edgar")
        return filings

    def get_latest_10k(self, ticker: str) -> Optional[dict]:
        sym = ticker.upper().strip()
        cached = self.db.get_cached("sec_edgar", "10k_text", sym)
        if cached is not None:
            return cached
        doc = sec_edgar.get_latest_10k_text(sym)
        if doc:
            self.db.set_cached("sec_edgar", "10k_text", sym, doc, ttl_hours=72)
            self.db.increment_quota("sec_edgar")
        return doc
