"""Headless Streamlit AppTest smoke tests verifying app.py and all 9 pages render cleanly."""

from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
ALL_PAGES = [ROOT / "app.py"] + sorted((ROOT / "pages").glob("*.py"))


@pytest.mark.parametrize("page_path", ALL_PAGES, ids=lambda p: p.name)
def test_streamlit_page_renders_without_exception(page_path: Path, monkeypatch, tmp_path):
    monkeypatch.setenv("MARKETSAGE_DATA_DIR", str(tmp_path))
    at = AppTest.from_file(str(page_path), default_timeout=15)
    at.run()
    assert not at.exception, f"{page_path.name} raised: {at.exception}"
