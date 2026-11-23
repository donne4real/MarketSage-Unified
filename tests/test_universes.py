"""Tests for live & cached market universe parsers, CSV upload, sector slicing & SQLite caching."""

from unittest.mock import patch

from core.database import Database
from core.universes import (
    UniverseProvider,
    parse_nasdaq100_html,
    parse_nasdaq_trader_txt,
    parse_sp500_html,
    parse_uploaded_tickers,
)

SAMPLE_SP500_HTML = """
<html><body>
<table id="constituents" class="wikitable">
  <tr><th>Symbol</th><th>Security</th><th>GICS Sector</th><th>GICS Sub-Industry</th></tr>
  <tr><td>AAPL</td><td>Apple Inc.</td><td>Information Technology</td><td>Hardware</td></tr>
  <tr><td>BRK.B</td><td>Berkshire Hathaway</td><td>Financials</td><td>Multi-Sector</td></tr>
  <tr><td>JNJ</td><td>Johnson &amp; Johnson</td><td>Health Care</td><td>Pharma</td></tr>
</table>
</body></html>
"""

SAMPLE_NDX_HTML = """
<html><body>
<table id="constituents" class="wikitable">
  <tr><th>Ticker</th><th>Company</th><th>ICB Sector</th></tr>
  <tr><td>NVDA</td><td>NVIDIA</td><td>Technology</td></tr>
  <tr><td>COST</td><td>Costco</td><td>Consumer Staples</td></tr>
</table>
</body></html>
"""

SAMPLE_NASDAQ_TXT = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N
QQQ|Invesco QQQ Trust|G|N|N|100|Y|N
ZTEST|Test Security|Q|Y|N|100|N|N
File Creation Time: 1123202612:00|||||||
"""


def test_parsers_extract_clean_tickers_and_sectors():
    sp = parse_sp500_html(SAMPLE_SP500_HTML)
    assert [r["ticker"] for r in sp] == ["AAPL", "BRK-B", "JNJ"]
    assert sp[0]["sector"] == "Information Technology"

    ndx = parse_nasdaq100_html(SAMPLE_NDX_HTML)
    assert [r["ticker"] for r in ndx] == ["NVDA", "COST"]

    nas = parse_nasdaq_trader_txt(SAMPLE_NASDAQ_TXT, is_other_listed=False)
    assert [r["ticker"] for r in nas] == ["AAPL", "QQQ"]
    assert nas[0]["is_etf"] is False
    assert nas[1]["is_etf"] is True


def test_csv_and_txt_upload_parsing():
    csv_bytes = b"Ticker,Notes\naapl,Core\nBRK.B,Value\naapl,Duplicate\n"
    assert parse_uploaded_tickers(csv_bytes, "my_list.csv") == ["AAPL", "BRK-B"]

    txt_bytes = b"VOO, QQQ\nSCHD\nVXUS"
    assert parse_uploaded_tickers(txt_bytes, "etfs.txt") == ["VOO", "QQQ", "SCHD", "VXUS"]


def test_universe_provider_caches_and_filters_by_sector(tmp_path):
    db = Database(tmp_path / "uni.db")
    prov = UniverseProvider(db=db)

    with patch.object(prov, "_fetch_text", return_value=SAMPLE_SP500_HTML) as mock_fetch:
        first = prov.get_sp500()
        second = prov.get_sp500()
        assert len(first) == 3
        assert len(second) == 3
        assert mock_fetch.call_count == 1  # second call came from SQLite cache

    tech = prov.select_tickers(first, sector="Information Technology", limit=10)
    assert tech == ["AAPL"]
