"""SEC EDGAR client for CIK resolution, recent 10-K/10-Q/13F filings & clean text extraction."""

from __future__ import annotations

import time
from typing import Optional
import httpx
from bs4 import BeautifulSoup

from ..config import get_sec_user_agent

EDGAR_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions"


def _headers() -> dict[str, str]:
    return {"User-Agent": get_sec_user_agent(), "Accept-Encoding": "gzip, deflate"}


def strip_html(content: str) -> str:
    """Convert SEC HTML filing to readable plain text."""
    if "<html" in content.lower() or "<body" in content.lower() or "<div" in content.lower():
        soup = BeautifulSoup(content, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    return content


def get_cik_from_ticker(ticker: str) -> Optional[str]:
    try:
        resp = httpx.get(EDGAR_TICKERS_URL, headers=_headers(), timeout=15)
        resp.raise_for_status()
        target = ticker.upper().strip()
        for entry in resp.json().values():
            if entry.get("ticker", "").upper() == target:
                return str(entry["cik_str"]).zfill(10)
    except Exception:
        return None
    return None


def get_recent_filings(
    ticker: str, form_types: Optional[list[str]] = None, limit: int = 15
) -> list[dict]:
    wanted = set(form_types or ["10-K", "10-Q", "8-K"])
    cik = get_cik_from_ticker(ticker)
    if not cik:
        return []
    try:
        time.sleep(0.12)
        resp = httpx.get(f"{EDGAR_SUBMISSIONS_URL}/CIK{cik}.json", headers=_headers(), timeout=15)
        resp.raise_for_status()
        recent = resp.json().get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])
        out = []
        cik_int = str(int(cik))
        for i, form in enumerate(forms):
            if form in wanted:
                acc = accessions[i]
                acc_clean = acc.replace("-", "")
                doc = docs[i]
                out.append(
                    {
                        "form": form,
                        "filing_date": dates[i],
                        "accession": acc,
                        "primary_document": doc,
                        "cik": cik,
                        "url": f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{doc}",
                    }
                )
                if len(out) >= limit:
                    break
        return out
    except Exception:
        return []


def get_latest_10k_text(ticker: str, max_chars: int = 40_000) -> Optional[dict]:
    """Fetch the most recent 10-K filing text and metadata."""
    filings = get_recent_filings(ticker, form_types=["10-K"], limit=1)
    if not filings:
        return None
    f = filings[0]
    try:
        time.sleep(0.15)
        resp = httpx.get(f["url"], headers=_headers(), timeout=30, follow_redirects=True)
        resp.raise_for_status()
        text = strip_html(resp.text)[:max_chars]
        return {**f, "text": text, "char_count": len(text)}
    except Exception:
        return None
