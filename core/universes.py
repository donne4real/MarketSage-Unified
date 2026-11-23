"""Live & Cached Market Universe Discovery (S&P 500, NASDAQ-100, Full NASDAQ/NYSE, US ETFs, Watchlist, CSV).

All live fetches are cached in SQLite (`api_cache`) for 7 days so subsequent loads are instant.
"""

from __future__ import annotations

import csv
import io
import random
import re
from typing import Any, Optional
import httpx
from bs4 import BeautifulSoup

from .data_engine import UNIVERSES as CURATED_UNIVERSES
from .database import Database

WIKI_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
WIKI_NDX100_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

UNIVERSE_CACHE_TTL_HOURS = 168  # 7 days
HTTP_HEADERS = {"User-Agent": "MarketSageUnified/1.0 (https://github.com/donne4real)"}

_VALID_TICKER_RE = re.compile(r"^[A-Z]{1,5}(?:-[A-Z])?$")


def _clean_ticker(raw: str) -> str:
    return raw.strip().upper().replace(".", "-")


def parse_sp500_html(html: str) -> list[dict[str, str]]:
    """Parse Wikipedia S&P 500 constituents table into [{ticker, name, sector, industry}]."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"id": "constituents"}) or soup.find("table", {"class": "wikitable"})
    if not table:
        return []
    rows: list[dict[str, str]] = []
    for tr in table.find_all("tr")[1:]:
        cols = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cols) >= 4:
            sym = _clean_ticker(cols[0])
            if _VALID_TICKER_RE.match(sym):
                rows.append(
                    {
                        "ticker": sym,
                        "name": cols[1],
                        "sector": cols[2] or "Unknown",
                        "industry": cols[3] or "Unknown",
                    }
                )
    return rows


def parse_nasdaq100_html(html: str) -> list[dict[str, str]]:
    """Parse Wikipedia NASDAQ-100 constituents table into [{ticker, name, sector, industry}]."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"id": "constituents"})
    if not table:
        for t in soup.find_all("table", {"class": "wikitable"}):
            hdr = " ".join(th.get_text(strip=True).lower() for th in t.find_all("th"))
            if "ticker" in hdr or "symbol" in hdr:
                table = t
                break
    if not table:
        return []
    headers = [th.get_text(strip=True).lower() for th in table.find_all("tr")[0].find_all(["th", "td"])]
    sym_idx = next((i for i, h in enumerate(headers) if "ticker" in h or "symbol" in h), 0)
    name_idx = next((i for i, h in enumerate(headers) if "company" in h or "name" in h), 1 if sym_idx == 0 else 0)
    sec_idx = next((i for i, h in enumerate(headers) if "sector" in h or "industry" in h), 2)

    rows: list[dict[str, str]] = []
    for tr in table.find_all("tr")[1:]:
        cols = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cols) > max(sym_idx, name_idx):
            sym = _clean_ticker(cols[sym_idx])
            if _VALID_TICKER_RE.match(sym):
                rows.append(
                    {
                        "ticker": sym,
                        "name": cols[name_idx],
                        "sector": cols[sec_idx] if len(cols) > sec_idx else "Unknown",
                        "industry": "",
                    }
                )
    return rows


def parse_nasdaq_trader_txt(text: str, is_other_listed: bool = False) -> list[dict[str, Any]]:
    """Parse official NASDAQ Trader pipe-delimited symbol directory files."""
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    rows: list[dict[str, Any]] = []
    for r in reader:
        if r.get("Test Issue", "N") == "Y":
            continue
        sym_raw = r.get("ACT Symbol" if is_other_listed else "Symbol", "")
        if not sym_raw or sym_raw.startswith("File Creation"):
            continue
        sym = _clean_ticker(sym_raw)
        if not _VALID_TICKER_RE.match(sym):
            continue
        is_etf = r.get("ETF", "N") == "Y"
        exch_code = r.get("Exchange", "Q") if is_other_listed else "Q"
        exch_map = {"N": "NYSE", "P": "NYSE Arca", "A": "NYSE American", "Z": "BATS", "Q": "NASDAQ"}
        rows.append(
            {
                "ticker": sym,
                "name": (r.get("Security Name") or sym).split(" - ")[0].strip(),
                "exchange": exch_map.get(exch_code, exch_code),
                "is_etf": is_etf,
                "sector": "ETF" if is_etf else "All Sectors",
            }
        )
    return rows


def parse_uploaded_tickers(file_bytes: bytes, filename: str = "") -> list[str]:
    """Extract unique uppercase ticker symbols from an uploaded CSV or TXT file."""
    text = file_bytes.decode("utf-8-sig", errors="ignore").strip()
    if not text:
        return []

    tickers: list[str] = []
    if filename.lower().endswith(".csv"):
        reader = csv.reader(io.StringIO(text))
        all_rows = [r for r in reader if any(c.strip() for c in r)]
        if not all_rows:
            return []
        header = [c.strip().lower() for c in all_rows[0]]
        col_idx = next((i for i, h in enumerate(header) if h in {"ticker", "symbol", "tickers", "symbols"}), None)
        if col_idx is not None:
            for row in all_rows[1:]:
                if len(row) > col_idx:
                    sym = _clean_ticker(row[col_idx])
                    if _VALID_TICKER_RE.match(sym) and sym not in tickers:
                        tickers.append(sym)
            return tickers
        # Headerless CSV: if every row is 1-col or pure ticker cells, scan all cells
        for row in all_rows:
            for cell in row:
                sym = _clean_ticker(cell)
                if _VALID_TICKER_RE.match(sym) and sym not in tickers:
                    tickers.append(sym)
        return tickers

    for token in re.split(r"[\s,;]+", text):
        sym = _clean_ticker(token)
        if _VALID_TICKER_RE.match(sym) and sym not in tickers:
            tickers.append(sym)
    return tickers


class UniverseProvider:
    """Provides live (7-day SQLite cached) and local market universes for discovery."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def _fetch_text(self, url: str) -> str:
        resp = httpx.get(url, headers=HTTP_HEADERS, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        return resp.text

    def get_sp500(self, force_refresh: bool = False) -> list[dict[str, str]]:
        if not force_refresh:
            cached = self.db.get_cached("universe", "sp500", "ALL")
            if cached:
                return cached
        html = self._fetch_text(WIKI_SP500_URL)
        rows = parse_sp500_html(html)
        if rows:
            self.db.set_cached("universe", "sp500", "ALL", rows, ttl_hours=UNIVERSE_CACHE_TTL_HOURS)
        return rows

    def get_nasdaq100(self, force_refresh: bool = False) -> list[dict[str, str]]:
        if not force_refresh:
            cached = self.db.get_cached("universe", "nasdaq100", "ALL")
            if cached:
                return cached
        html = self._fetch_text(WIKI_NDX100_URL)
        rows = parse_nasdaq100_html(html)
        if rows:
            self.db.set_cached("universe", "nasdaq100", "ALL", rows, ttl_hours=UNIVERSE_CACHE_TTL_HOURS)
        return rows

    def get_exchange_directory(self, exchange: str = "NASDAQ", etfs_only: bool = False, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Fetch live NASDAQ, NYSE, or All US ETFs from official NASDAQ Trader symbol directories."""
        cache_key = f"{exchange.upper()}_{'ETF' if etfs_only else 'EQ'}"
        if not force_refresh:
            cached = self.db.get_cached("universe", "exchange_dir", cache_key)
            if cached:
                return cached

        rows: list[dict[str, Any]] = []
        if exchange.upper() in {"NASDAQ", "ALL"}:
            txt = self._fetch_text(NASDAQ_LISTED_URL)
            rows.extend(parse_nasdaq_trader_txt(txt, is_other_listed=False))
        if exchange.upper() in {"NYSE", "ALL"}:
            txt = self._fetch_text(OTHER_LISTED_URL)
            other = parse_nasdaq_trader_txt(txt, is_other_listed=True)
            if exchange.upper() == "NYSE":
                other = [r for r in other if r["exchange"] == "NYSE" or (etfs_only and "NYSE" in r["exchange"])]
            rows.extend(other)

        filtered = [r for r in rows if r["is_etf"]] if etfs_only else [r for r in rows if not r["is_etf"]]
        if filtered:
            self.db.set_cached("universe", "exchange_dir", cache_key, filtered, ttl_hours=UNIVERSE_CACHE_TTL_HOURS)
        return filtered

    def get_watchlist_entries(self, asset_type: Optional[str] = None) -> list[dict[str, str]]:
        rows = self.db.list_watchlist(asset_type=asset_type)
        return [{"ticker": r["ticker"], "name": r.get("name", ""), "sector": "Watchlist"} for r in rows]

    def get_portfolio_entries(self) -> list[dict[str, str]]:
        rows = self.db.list_holdings()
        seen: set[str] = set()
        out: list[dict[str, str]] = []
        for r in rows:
            if r["ticker"] not in seen:
                seen.add(r["ticker"])
                out.append({"ticker": r["ticker"], "name": "", "sector": r.get("bucket", "Portfolio")})
        return out

    def get_curated(self, preset_name: str) -> list[dict[str, str]]:
        syms = list(dict.fromkeys(CURATED_UNIVERSES.get(preset_name, [])))
        return [{"ticker": s, "name": "", "sector": preset_name} for s in syms]

    @staticmethod
    def select_tickers(
        entries: list[dict[str, Any]],
        sector: str = "All Sectors",
        limit: int = 25,
        randomize: bool = False,
    ) -> list[str]:
        """Filter entries by sector and slice to requested batch size."""
        filtered = entries
        if sector and sector != "All Sectors":
            filtered = [e for e in entries if e.get("sector") == sector]
        syms = [e["ticker"] for e in filtered]
        if randomize and len(syms) > limit:
            return sorted(random.sample(syms, limit))
        return syms[:limit]
