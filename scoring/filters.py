"""Title-level gate: decide whether a job belongs in the list at all.

The platforms' keyword search matches JD body text, not just the title, so a
warehouse clerk whose JD mentions "資料分析" gets returned. Scoring alone can't
fix that — an irrelevant job with a generic tech JD still collects skill points.
"""

from __future__ import annotations

import re

_CJK_GAP = re.compile(r"(?<=[一-鿿])\s+(?=[一-鿿])")


def strip_cjk_gaps(text: str) -> str:
    """~4% of scraped titles carry stray spaces between CJK characters
    ("商業分析 師", "資料 科學家"), which breaks every CJK pattern."""
    return _CJK_GAP.sub("", text)

# Job title must signal an analytics role. Matched case-insensitively.
_CORE_ROLE = re.compile(
    r"data\s*analy|business\s*analy|product\s*analy|marketing\s*analy"
    r"|growth\s*analy|operations?\s*analy|quantitative\s*analy"
    r"|data\s*scien|decision\s*scien|business\s*intelligence|\bBI\b"
    r"|analytics|analytics\s*engineer"
    r"|資料分析|數據分析|商業分析|產品分析|營運分析|行銷分析|經營分析"
    r"|資料科學|數據科學|商業智慧|數據應用|數據運營|數據策略|數據洞察",
    re.I,
)

# Hard-drop even when _CORE_ROLE matches.
#   系統分析師/SA — requirements engineering, a different profession
#   intern/實習    — wrong seniority entirely
_DISQUALIFY = re.compile(
    r"系統分析|system\s*analyst"
    r"|\bintern\b|internship|實習|工讀|建教",
    re.I,
)


# Fallback for titles where the two halves are split by other words, e.g.
# "Data & Digital Transformation Analyst".
_ANALYST_WORD = re.compile(r"\banalyst\b|分析師", re.I)
_DATA_CONTEXT = re.compile(r"\bdata\b|數據|資料", re.I)


def is_target_role(title: str) -> bool:
    """True if the job title is an analytics role Bill would actually apply to."""
    if not title:
        return False
    title = strip_cjk_gaps(title)
    if _DISQUALIFY.search(title):
        return False
    if _CORE_ROLE.search(title):
        return True
    return bool(_ANALYST_WORD.search(title) and _DATA_CONTEXT.search(title))
