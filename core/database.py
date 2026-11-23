"""Unified SQLite persistence layer for MarketSage Unified.

Tables:
- api_cache: Per-source 24h TTL cache for market/SEC API responses
- api_quota: Daily API call counters per provider
- watchlist: Cross-asset watchlist (stocks, ETFs, mutual funds, 100-baggers)
- holdings: Portfolio positions for Portfolio & Risk analysis
- decisions: Investment Decision Journal with thesis & P&L tracking
- ai_cache: Memoized LLM research briefs
- screener_runs: History of executed screens
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .config import DAILY_QUOTAS, DB_PATH, DEFAULT_CACHE_TTL_HOURS


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(dt: Optional[datetime] = None) -> str:
    return (dt or _utc_now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today_str() -> str:
    return _utc_now().strftime("%Y-%m-%d")


class Database:
    """Thread-safe SQLite repository with clean CRUD across all platform tables."""

    def __init__(self, db_path: Optional[Path | str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            env_dir = os.getenv("MARKETSAGE_DATA_DIR")
            self.db_path = (Path(env_dir) / "marketsage.db") if env_dir else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS api_cache (
                    source TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    params_key TEXT NOT NULL DEFAULT '',
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    PRIMARY KEY (source, endpoint, ticker, params_key)
                );
                CREATE INDEX IF NOT EXISTS idx_api_cache_exp ON api_cache(expires_at);

                CREATE TABLE IF NOT EXISTS api_quota (
                    source TEXT NOT NULL,
                    date TEXT NOT NULL,
                    call_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (source, date)
                );

                CREATE TABLE IF NOT EXISTS watchlist (
                    ticker TEXT PRIMARY KEY,
                    asset_type TEXT NOT NULL DEFAULT 'stock',
                    name TEXT DEFAULT '',
                    target_price REAL,
                    notes TEXT DEFAULT '',
                    added_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    shares REAL NOT NULL,
                    cost_basis REAL NOT NULL,
                    asset_type TEXT NOT NULL DEFAULT 'stock',
                    bucket TEXT NOT NULL DEFAULT 'core',
                    target_weight REAL,
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_holdings_ticker ON holdings(ticker);

                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    asset_type TEXT NOT NULL DEFAULT 'stock',
                    decision TEXT NOT NULL,
                    thesis TEXT NOT NULL,
                    sell_criteria TEXT DEFAULT '',
                    stop_loss TEXT DEFAULT '',
                    position_pct REAL,
                    price_at_decision REAL,
                    current_price REAL,
                    return_pct REAL,
                    thesis_quality_score INTEGER,
                    status TEXT NOT NULL DEFAULT 'open',
                    sold_price REAL,
                    sold_at TEXT,
                    review_notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_decisions_ticker ON decisions(ticker);
                CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);

                CREATE TABLE IF NOT EXISTS ai_cache (
                    ticker TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    analysis_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (ticker, asset_type)
                );

                CREATE TABLE IF NOT EXISTS screener_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    screen_name TEXT NOT NULL,
                    parameters_json TEXT DEFAULT '{}',
                    result_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                """
            )

    # ---------- API Cache ----------

    @staticmethod
    def _params_key(params: Optional[dict]) -> str:
        if not params:
            return ""
        return json.dumps(params, sort_keys=True, separators=(",", ":"))

    def get_cached(
        self, source: str, endpoint: str, ticker: str, params: Optional[dict] = None
    ) -> Optional[Any]:
        now = _utc_iso()
        pk = self._params_key(params)
        with self._connect() as conn:
            row = conn.execute(
                """SELECT response_json, expires_at FROM api_cache
                   WHERE source = ? AND endpoint = ? AND ticker = ? AND params_key = ?""",
                (source, endpoint, ticker.upper(), pk),
            ).fetchone()
            if not row:
                return None
            if row["expires_at"] <= now:
                conn.execute(
                    """DELETE FROM api_cache
                       WHERE source = ? AND endpoint = ? AND ticker = ? AND params_key = ?""",
                    (source, endpoint, ticker.upper(), pk),
                )
                return None
            return json.loads(row["response_json"])

    def set_cached(
        self,
        source: str,
        endpoint: str,
        ticker: str,
        payload: Any,
        params: Optional[dict] = None,
        ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
    ) -> None:
        now = _utc_now()
        exp = now + timedelta(hours=ttl_hours)
        pk = self._params_key(params)
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO api_cache
                   (source, endpoint, ticker, params_key, response_json, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    source,
                    endpoint,
                    ticker.upper(),
                    pk,
                    json.dumps(payload, default=str),
                    _utc_iso(now),
                    _utc_iso(exp),
                ),
            )

    def clear_cache(self, source: Optional[str] = None) -> int:
        with self._connect() as conn:
            if source:
                cur = conn.execute("DELETE FROM api_cache WHERE source = ?", (source,))
            else:
                cur = conn.execute("DELETE FROM api_cache")
            return cur.rowcount

    def cache_stats(self) -> dict[str, int]:
        now = _utc_iso()
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM api_cache WHERE expires_at > ?", (now,)
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT source, COUNT(*) as cnt FROM api_cache WHERE expires_at > ? GROUP BY source",
                (now,),
            ).fetchall()
            by_source = {r["source"]: r["cnt"] for r in rows}
            by_source["total"] = total
            return by_source

    # ---------- API Quota ----------

    def increment_quota(self, source: str, count: int = 1, date_str: Optional[str] = None) -> int:
        day = date_str or _today_str()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO api_quota (source, date, call_count)
                   VALUES (?, ?, ?)
                   ON CONFLICT(source, date) DO UPDATE SET call_count = call_count + excluded.call_count""",
                (source, day, count),
            )
            row = conn.execute(
                "SELECT call_count FROM api_quota WHERE source = ? AND date = ?",
                (source, day),
            ).fetchone()
            return int(row["call_count"])

    def get_quota_status(self, date_str: Optional[str] = None) -> dict[str, dict[str, Any]]:
        day = date_str or _today_str()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT source, call_count FROM api_quota WHERE date = ?", (day,)
            ).fetchall()
            used_map = {r["source"]: int(r["call_count"]) for r in rows}

        status: dict[str, dict[str, Any]] = {}
        for source, limit in DAILY_QUOTAS.items():
            used = used_map.get(source, 0)
            pct = round((used / limit) * 100, 1) if limit > 0 else 0.0
            status[source] = {
                "used": used,
                "limit": limit,
                "remaining": max(0, limit - used),
                "percent": pct,
                "warning": pct >= 80.0,
            }
        return status

    # ---------- Watchlist ----------

    def add_watchlist(
        self,
        ticker: str,
        asset_type: str = "stock",
        name: str = "",
        target_price: Optional[float] = None,
        notes: str = "",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO watchlist
                   (ticker, asset_type, name, target_price, notes, added_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (ticker.upper().strip(), asset_type, name, target_price, notes, _utc_iso()),
            )

    def remove_watchlist(self, ticker: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.upper().strip(),))
            return cur.rowcount > 0

    def list_watchlist(self, asset_type: Optional[str] = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if asset_type and asset_type != "all":
                rows = conn.execute(
                    "SELECT * FROM watchlist WHERE asset_type = ? ORDER BY added_at DESC",
                    (asset_type,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM watchlist ORDER BY added_at DESC").fetchall()
            return [dict(r) for r in rows]

    # ---------- Portfolio Holdings ----------

    def add_holding(
        self,
        ticker: str,
        shares: float,
        cost_basis: float,
        asset_type: str = "stock",
        bucket: str = "core",
        target_weight: Optional[float] = None,
        notes: str = "",
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO holdings
                   (ticker, shares, cost_basis, asset_type, bucket, target_weight, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticker.upper().strip(),
                    float(shares),
                    float(cost_basis),
                    asset_type,
                    bucket,
                    target_weight,
                    notes,
                    _utc_iso(),
                ),
            )
            return int(cur.lastrowid)

    def list_holdings(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM holdings ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def delete_holding(self, holding_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))
            return cur.rowcount > 0

    # ---------- Decision Log ----------

    def add_decision(
        self,
        ticker: str,
        asset_type: str,
        decision: str,
        thesis: str,
        sell_criteria: str = "",
        stop_loss: str = "",
        position_pct: Optional[float] = None,
        price_at_decision: Optional[float] = None,
        thesis_quality_score: Optional[int] = None,
    ) -> int:
        now = _utc_iso()
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO decisions
                   (ticker, asset_type, decision, thesis, sell_criteria, stop_loss,
                    position_pct, price_at_decision, thesis_quality_score, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
                (
                    ticker.upper().strip(),
                    asset_type,
                    decision,
                    thesis,
                    sell_criteria,
                    stop_loss,
                    position_pct,
                    price_at_decision,
                    thesis_quality_score,
                    now,
                    now,
                ),
            )
            return int(cur.lastrowid)

    def list_decisions(self, status: Optional[str] = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if status and status != "all":
                rows = conn.execute(
                    "SELECT * FROM decisions WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM decisions ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    def update_decision_status(
        self,
        decision_id: int,
        status: str,
        review_notes: str = "",
        sold_price: Optional[float] = None,
    ) -> None:
        now = _utc_iso()
        with self._connect() as conn:
            if status == "sold" and sold_price is not None:
                row = conn.execute(
                    "SELECT price_at_decision FROM decisions WHERE id = ?", (decision_id,)
                ).fetchone()
                ret = None
                if row and row["price_at_decision"] and row["price_at_decision"] > 0:
                    ret = round(((sold_price - row["price_at_decision"]) / row["price_at_decision"]) * 100, 2)
                conn.execute(
                    """UPDATE decisions
                       SET status = ?, review_notes = ?, sold_price = ?, sold_at = ?,
                           current_price = ?, return_pct = ?, updated_at = ?
                       WHERE id = ?""",
                    (status, review_notes, sold_price, now, sold_price, ret, now, decision_id),
                )
            else:
                conn.execute(
                    "UPDATE decisions SET status = ?, review_notes = ?, updated_at = ? WHERE id = ?",
                    (status, review_notes, now, decision_id),
                )

    def update_decision_price(self, decision_id: int, current_price: float) -> Optional[float]:
        now = _utc_iso()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT price_at_decision FROM decisions WHERE id = ?", (decision_id,)
            ).fetchone()
            ret = None
            if row and row["price_at_decision"] and row["price_at_decision"] > 0:
                ret = round(((current_price - row["price_at_decision"]) / row["price_at_decision"]) * 100, 2)
            conn.execute(
                "UPDATE decisions SET current_price = ?, return_pct = ?, updated_at = ? WHERE id = ?",
                (current_price, ret, now, decision_id),
            )
            return ret

    def delete_decision(self, decision_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM decisions WHERE id = ?", (decision_id,))
            return cur.rowcount > 0

    def decision_summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
            open_cnt = conn.execute("SELECT COUNT(*) FROM decisions WHERE status = 'open'").fetchone()[0]
            sold_cnt = conn.execute("SELECT COUNT(*) FROM decisions WHERE status = 'sold'").fetchone()[0]
            avg_ret = conn.execute(
                "SELECT AVG(return_pct) FROM decisions WHERE return_pct IS NOT NULL"
            ).fetchone()[0]
            avg_q = conn.execute(
                "SELECT AVG(thesis_quality_score) FROM decisions WHERE thesis_quality_score IS NOT NULL"
            ).fetchone()[0]
            return {
                "total": total,
                "open": open_cnt,
                "sold": sold_cnt,
                "avg_return_pct": round(avg_ret, 2) if avg_ret is not None else None,
                "avg_thesis_score": round(avg_q, 1) if avg_q is not None else None,
            }

    # ---------- AI Cache & Screener History ----------

    def get_ai_cache(self, ticker: str, asset_type: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT provider, analysis_json, created_at FROM ai_cache WHERE ticker = ? AND asset_type = ?",
                (ticker.upper(), asset_type),
            ).fetchone()
            if not row:
                return None
            return {
                "provider": row["provider"],
                "data": json.loads(row["analysis_json"]),
                "created_at": row["created_at"],
            }

    def set_ai_cache(self, ticker: str, asset_type: str, provider: str, analysis: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO ai_cache (ticker, asset_type, provider, analysis_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (ticker.upper(), asset_type, provider, json.dumps(analysis, default=str), _utc_iso()),
            )

    def log_screener_run(self, screen_name: str, parameters: dict[str, Any], result_count: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO screener_runs (screen_name, parameters_json, result_count, created_at) VALUES (?, ?, ?, ?)",
                (screen_name, json.dumps(parameters, default=str), int(result_count), _utc_iso()),
            )

    def list_screener_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM screener_runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
