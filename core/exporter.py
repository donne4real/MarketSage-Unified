"""Unified Styled Excel (.xlsx) & CSV Exporter."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Optional
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils.dataframe import dataframe_to_rows


HEADER_FILL = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="F8FAFC")
TITLE_FONT = Font(name="Calibri", size=14, bold=True, color="1E3A8A")


def export_excel_bytes(
    sheets: dict[str, pd.DataFrame],
    title: str = "MarketSage Unified Report",
) -> bytes:
    """Build a multi-sheet styled Excel workbook in memory and return bytes."""
    wb = Workbook()
    first = True
    for sheet_name, df in sheets.items():
        safe_name = sheet_name[:31]
        ws = wb.active if first else wb.create_sheet(title=safe_name)
        ws.title = safe_name
        first = False

        ws["A1"] = f"{title} — {sheet_name}"
        ws["A1"].font = TITLE_FONT
        ws["A2"] = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        start_row = 4
        if df is None or df.empty:
            ws.cell(row=start_row, column=1, value="No data available")
            continue

        for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), start=start_row):
            for c_idx, val in enumerate(row, start=1):
                cell = ws.cell(row=r_idx, column=c_idx, value=val)
                if r_idx == start_row:
                    cell.fill = HEADER_FILL
                    cell.font = HEADER_FONT
                    cell.alignment = Alignment(horizontal="center")

        # Auto-fit column widths
        for col in ws.columns:
            max_len = 10
            col_letter = col[0].column_letter
            for cell in col:
                if cell.value is not None:
                    max_len = max(max_len, min(len(str(cell.value)) + 3, 42))
            ws.column_dimensions[col_letter].width = max_len

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def save_excel_report(
    sheets: dict[str, pd.DataFrame], output_dir: Path, prefix: str = "marketsage_report"
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"{prefix}_{ts}.xlsx"
    path.write_bytes(export_excel_bytes(sheets))
    return path
