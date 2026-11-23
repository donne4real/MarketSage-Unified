"""Tests for AI Research offline fallback, SEC HTML parser, Excel/CSV export & Streamlit page syntax."""

import ast
import io
from pathlib import Path
import pandas as pd
from openpyxl import load_workbook

from core.ai_research import detect_red_flags, generate_research_brief, score_thesis_quality
from core.exporter import export_csv_bytes, export_excel_bytes
from core.sources.sec_edgar import strip_html

ROOT = Path(__file__).resolve().parent.parent


def test_red_flags_offline_brief_and_thesis_scorer():
    risky = {
        "ticker": "RISK",
        "name": "Risky Corp",
        "sector": "Energy",
        "pe_ratio": 65.0,
        "debt_to_equity": 3.1,
        "current_ratio": 0.7,
        "profit_margin": -0.10,
        "free_cash_flow": -50_000_000,
    }
    flags = detect_red_flags(risky)
    assert len(flags) >= 4

    brief = generate_research_brief(risky, provider_override="offline")
    assert brief["provider"] == "offline"
    assert len(brief["thesis_prompts"]) == 3

    graded = score_thesis_quality(
        "MSFT",
        thesis="Enterprise cloud dominance with high switching costs, recurring cash flows, and disciplined capital allocation over 5+ years.",
        sell_criteria="Cloud margins compress below 30% for 3 quarters",
        stop_loss="-25%",
        position_pct=12.0,
    )
    assert graded["score"] >= 8


def test_sec_html_stripper():
    html = "<html><body><script>var x=1;</script><div>Item 1A. Risk Factors</div></body></html>"
    plain = strip_html(html)
    assert "Risk Factors" in plain
    assert "var x=1" not in plain


def test_excel_and_csv_exporters():
    df = pd.DataFrame([{"Ticker": "AAPL", "Score": 84.5}, {"Ticker": "MSFT", "Score": 88.0}])
    csv_bytes = export_csv_bytes(df)
    assert b"AAPL" in csv_bytes

    xlsx_bytes = export_excel_bytes({"Summary": df, "Details": df}, title="Unit Test Report")
    wb = load_workbook(io.BytesIO(xlsx_bytes))
    assert wb.sheetnames == ["Summary", "Details"]
    assert wb["Summary"]["A4"].value == "Ticker"


def test_all_streamlit_pages_parse_cleanly():
    files = [ROOT / "app.py", ROOT / "ui" / "components.py"] + sorted((ROOT / "pages").glob("*.py"))
    assert len(files) == 11  # app.py + ui/components.py + 9 pages
    for path in files:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))
