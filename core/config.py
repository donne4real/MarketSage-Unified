"""Central configuration for MarketSage Unified."""

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

APP_DATA_DIR = Path(os.getenv("MARKETSAGE_DATA_DIR", Path.home() / ".marketsage_unified"))
DB_PATH = APP_DATA_DIR / "marketsage.db"
EXPORT_DIR = PROJECT_ROOT / "output"

DAILY_QUOTAS: dict[str, int] = {
    "alpha_vantage": 25,
    "twelve_data": 800,
    "yfinance": 2000,
    "sec_edgar": 10000,
}

DEFAULT_CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))
DEFAULT_RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "0.5"))


def get_source_order(override: str | None = None) -> list[str]:
    """Return ordered data source fallback chain."""
    mode = (override or os.getenv("DATA_SOURCE_ORDER", "yf_first")).strip().lower()
    if mode == "av_first":
        return ["alpha_vantage", "twelve_data", "yfinance"]
    if mode == "td_first":
        return ["twelve_data", "alpha_vantage", "yfinance"]
    return ["yfinance", "alpha_vantage", "twelve_data"]


def get_sec_user_agent() -> str:
    return os.getenv("SEC_USER_AGENT", "MarketSageUnified research@example.com")
