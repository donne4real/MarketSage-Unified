# 📈 MarketSage Unified

**One coherent financial intelligence platform** consolidating all US/global stock, ETF, mutual fund, 100-bagger, technical analysis, dividend/DCF valuation, portfolio risk, SEC EDGAR, and AI research workflows into a single zero-duplication codebase.

*(Nigerian Exchange equities remain dedicated to your standalone [NGX Tracker](https://ngx-tracker.pages.dev).)*

---

## Architecture

```text
MarketSage-Unified/
├── app.py                              # Command Center landing page & quick lookup
├── core/                               # Pure Python domain engine (100% decoupled from UI)
│   ├── config.py                       # Env config, source priority & daily API quotas
│   ├── database.py                     # Single SQLite DB (24h cache, quotas, watchlist, holdings, decisions, AI cache)
│   ├── sources/                        # Alpha Vantage, Twelve Data, SEC EDGAR clients
│   ├── data_engine.py                  # Multi-source fallback chain + normalization + analyst ratings
│   ├── universes.py                    # Live 7-day cached S&P 500, NASDAQ-100, NASDAQ/NYSE, US ETFs & CSV loaders
│   ├── strategies/                     # 45 Models: Stocks (15), ETFs (10), Mutual Funds (10), 100-Bagger (10)
│   ├── technicals.py                   # SMA/EMA, RSI-14, MACD, Bollinger Bands, Support/Resistance
│   ├── dividends.py                    # Gordon Growth, 5-Yr FCF DCF, Safety Score & DRIP Compounder
│   ├── backtester.py                   # Unified Buy & Hold, SMA Crossover, RSI & Multi-Asset Backtester
│   ├── portfolio.py                    # VaR/CVaR, Sortino, Beta, Correlation, Stress Tests & Rebalancer
│   ├── screener.py                     # Custom Metric Filter Builder, Presets & Comparison Matrix
│   ├── ai_research.py                  # Multi-provider LLM (Claude / Gemini / OpenAI) + Offline Quant Fallback
│   └── exporter.py                     # Styled multi-sheet Excel (.xlsx) & CSV exporter
├── ui/components.py                    # Shared dark theme, sidebar quota monitor & Plotly charts
├── pages/                              # 9 Streamlit Multi-Page Dashboards
└── tests/                              # Automated pytest suite covering core engine & pages
```

---

## Quick Start

```powershell
cd "C:\Users\leyea\OneDrive\Documents\Vibe Coding\MarketSage-Unified"
pip install -r requirements.txt
copy .env.example .env   # Optional: add API keys (yfinance + offline brief work with zero keys)
streamlit run app.py
```

## Running Tests

```powershell
pytest -v
```

---

## What Was Consolidated
Merged the best capabilities from:
- `Qwen\CombinedMarketAnalyzer` & `Qwen\UnifiedInvestmentPlatform` (4-asset screeners, watchlist, analyst ratings, SQLite decision log)
- `Qwen\100BaggerScreener`, `ETFAnalyzer`, `MutualFundAnalyzer`, `QwenStockMarketAnalysis` (all 40 asset strategies)
- `Minimax\investment-platform` (Alpha Vantage → Twelve Data → yfinance → SEC EDGAR fallback chain, 24h SQLite cache, daily quota monitor, Claude narrative & thesis grader)
- `Minimax\workspace` (*MarketSage Analyzer*: 10 classic guru philosophies, technical analysis, dividend/DCF/DRIP tools, portfolio builder, VaR/CVaR/stress-test risk management, custom filters)
- `ZCodeProject\StockMarketAnalysis` (Under-$50 screener preset & multi-sheet Excel reporting)

---

*Disclaimer: For educational and personal research purposes only. Not financial advice.*
