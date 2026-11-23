"""Multi-Provider AI Research Assistant (Anthropic Claude, Google Gemini, OpenAI + Deterministic Fallback).

Design principles:
- Interpretation, never fabricated numbers; all quantitative facts come from DataEngine.
- Never issues buy/sell financial advice; surfaces business thesis, risks, and decision prompts.
- Gracefully falls back to a structured quantitative & red-flag brief when no API key is set.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional
import httpx


SYSTEM_PROMPT = """You are an objective investment research analyst assisting a long-term retail investor.
Rules:
1. NEVER invent numbers. Only cite facts provided in the prompt.
2. NEVER issue buy/sell recommendations. Focus on business mechanics, valuation context, and risks.
3. Be concise, specific to this security, and return valid JSON matching the requested schema.
"""


def detect_provider(preferred: Optional[str] = None) -> str:
    """Detect available LLM provider: anthropic | gemini | openai | offline."""
    pref = (preferred or os.getenv("LLM_PROVIDER", "auto")).strip().lower()
    keys = {
        "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
        "gemini": os.getenv("GEMINI_API_KEY", ""),
        "openai": os.getenv("OPENAI_API_KEY", ""),
    }

    def _valid(k: str) -> bool:
        return bool(k and not k.startswith("your") and len(k) > 10)

    if pref in keys and _valid(keys[pref]):
        return pref
    for p in ("anthropic", "gemini", "openai"):
        if _valid(keys[p]):
            return p
    return "offline"


def detect_red_flags(info: dict[str, Any]) -> list[str]:
    """Deterministic financial health & valuation red-flag detector."""
    flags: list[str] = []
    dte = info.get("debt_to_equity")
    cr = info.get("current_ratio")
    pe = info.get("pe_ratio")
    pm = info.get("profit_margin")
    rg = info.get("revenue_growth")
    fcf = info.get("free_cash_flow")
    payout = info.get("payout_ratio")
    er = info.get("expense_ratio")

    if dte is not None and dte > 2.0:
        flags.append(f"High leverage: Debt/Equity of {dte:.2f} (> 2.0)")
    if cr is not None and cr < 1.0:
        flags.append(f"Tight short-term liquidity: Current Ratio of {cr:.2f} (< 1.0)")
    if pe is not None and pe > 50:
        flags.append(f"Rich valuation multiple: Trailing P/E of {pe:.1f} (> 50)")
    if pm is not None and pm < 0:
        flags.append(f"Unprofitable: Net Profit Margin of {pm*100:.1f}%")
    if rg is not None and rg < -0.05:
        flags.append(f"Contracting top-line: Revenue growth of {rg*100:.1f}%")
    if fcf is not None and fcf < 0:
        flags.append("Negative Free Cash Flow")
    if payout is not None and payout > 0.90:
        flags.append(f"Stretched dividend payout ratio ({payout*100:.0f}%)")
    if er is not None and er > 0.0075:
        flags.append(f"High fund expense ratio ({er*100:.2f}% > 0.75%)")
    return flags


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    try:
        return json.loads(cleaned)
    except Exception:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except Exception:
                pass
    return {"raw_response": text}


def _call_llm(prompt: str, provider: str) -> str:
    if provider == "anthropic":
        from anthropic import Anthropic

        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=1800,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        resp = httpx.post(
            url,
            params={"key": api_key},
            json={
                "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"parts": [{"text": prompt}]}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    raise RuntimeError("No LLM provider configured")


def _offline_brief(info: dict[str, Any], red_flags: list[str], has_10k: bool) -> dict[str, Any]:
    sym = info.get("ticker", "")
    name = info.get("name", sym)
    sector = info.get("sector", "Unknown")
    pe = info.get("pe_ratio")
    roe = info.get("roe")
    rg = info.get("revenue_growth")
    dy = info.get("dividend_yield")

    strengths = []
    if roe is not None and roe >= 0.15:
        strengths.append(f"Strong return on equity ({roe*100:.1f}%)")
    if rg is not None and rg >= 0.10:
        strengths.append(f"Solid revenue growth ({rg*100:.1f}%)")
    if dy is not None and dy >= 0.02:
        strengths.append(f"Meaningful dividend yield ({dy*100:.2f}%)")
    if pe is not None and 0 < pe <= 18:
        strengths.append(f"Reasonable earnings multiple (P/E {pe:.1f})")
    if not strengths:
        strengths.append("Review full multi-strategy scorecard for sector-specific context.")

    summary = info.get("summary") or f"{name} ({sym}) operates in the {sector} sector."
    return {
        "provider": "offline",
        "business_summary": summary[:600],
        "key_strengths": strengths,
        "bear_case": red_flags or ["No automated financial red flags triggered; assess competitive & macro risks."],
        "valuation_read": (
            f"Trailing P/E is {pe:.1f}." if pe else "Valuation multiple unavailable; inspect FCF/DCF and peer comparisons."
        ),
        "filing_note": (
            "10-K excerpt fetched. Configure ANTHROPIC_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY in .env for deep AI narrative synthesis."
            if has_10k
            else "Configure an LLM API key in .env to unlock deep AI synthesis of SEC 10-K filings."
        ),
        "thesis_prompts": [
            f"What durable competitive advantage protects {sym}'s margins over the next 5 years?",
            f"What specific metric or event would falsify your thesis on {sym}?",
            "How does this position size fit alongside your core index ETF allocation?",
        ],
    }


def generate_research_brief(
    info: dict[str, Any],
    ten_k_excerpt: Optional[str] = None,
    provider_override: Optional[str] = None,
) -> dict[str, Any]:
    """Generate a structured research brief using configured LLM or offline analytical fallback."""
    red_flags = detect_red_flags(info)
    provider = detect_provider(provider_override)
    if provider == "offline":
        return _offline_brief(info, red_flags, has_10k=bool(ten_k_excerpt))

    prompt = f"""Analyze {info.get('ticker')} ({info.get('name')}) for a long-term investor.
Sector: {info.get('sector')} | Industry: {info.get('industry')} | Asset Type: {info.get('asset_type')}
Metrics: {json.dumps({k: info.get(k) for k in ['price','market_cap','pe_ratio','forward_pe','pb_ratio','peg_ratio','roe','gross_margin','operating_margin','profit_margin','revenue_growth','debt_to_equity','current_ratio','dividend_yield','expense_ratio','aum']}, indent=2)}
Detected Red Flags: {red_flags or ['None']}
Business Summary: {(info.get('summary') or '')[:1500]}
10-K Filing Excerpt: {(ten_k_excerpt or 'Not provided')[:12000]}

Return strict JSON with keys:
{{
  "business_summary": "2 concise paragraphs on how it makes money and its edge",
  "key_strengths": ["point 1", "point 2", "point 3"],
  "bear_case": ["specific risk 1", "specific risk 2", "specific risk 3"],
  "valuation_read": "2 sentences contextualizing valuation without buy/sell advice",
  "filing_note": "1 paragraph on management tone & key 10-K risk takeaways (or note if unavailable)",
  "thesis_prompts": ["question 1", "question 2", "question 3"]
}}"""

    try:
        raw = _call_llm(prompt, provider)
        parsed = _extract_json(raw)
        parsed["provider"] = provider
        parsed.setdefault("red_flags", red_flags)
        return parsed
    except Exception as exc:
        fallback = _offline_brief(info, red_flags, has_10k=bool(ten_k_excerpt))
        fallback["llm_error"] = str(exc)
        return fallback


def score_thesis_quality(
    ticker: str,
    thesis: str,
    sell_criteria: str = "",
    stop_loss: str = "",
    position_pct: Optional[float] = None,
) -> dict[str, Any]:
    """Score investment decision process quality (1-10) deterministically (plus LLM feedback if configured)."""
    score = 2
    feedback: list[str] = []
    t_len = len((thesis or "").strip())
    if t_len >= 120:
        score += 3; feedback.append("Detailed investment thesis articulated.")
    elif t_len >= 40:
        score += 2; feedback.append("Moderate thesis detail — consider adding quantitative expectations.")
    else:
        feedback.append("Thesis is brief — explain why this asset outperforms over 3–5 years.")

    if sell_criteria and len(sell_criteria.strip()) >= 15:
        score += 2; feedback.append("Clear thesis-falsification / sell criteria defined.")
    else:
        feedback.append("Add explicit sell criteria (what would prove you wrong?).")

    if stop_loss and stop_loss.strip():
        score += 1; feedback.append("Downside / stop-loss discipline recorded.")

    if position_pct is not None and 0 < position_pct <= 25:
        score += 2; feedback.append(f"Prudent position sizing ({position_pct:.1f}%).")
    elif position_pct is not None and position_pct > 25:
        score += 1; feedback.append(f"Concentrated position ({position_pct:.1f}%) — ensure conviction matches risk.")
    else:
        feedback.append("Record target position size (% of portfolio).")

    return {"score": min(10, score), "feedback": feedback}
