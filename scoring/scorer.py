"""Job-Resume matching scorer using keyword matching (free, no API needed)."""

from __future__ import annotations

import re
from scrapers.base import Job

# Threshold: matching this many skills = full skill score
SKILL_FULL_SCORE_AT = 6

# Pairs that should be treated as equivalent when scoring
_ALIASES: list[tuple[str, str]] = [
    ("數據", "資料"),
    ("data analyst", "資料分析師"),
    ("data analyst", "數據分析師"),
    ("senior", "資深"),
    ("machine learning", "機器學習"),
    ("artificial intelligence", "人工智慧"),
    ("deep learning", "深度學習"),
]


def _normalize(text: str) -> str:
    """Expand alias pairs so either form matches the other."""
    for a, b in _ALIASES:
        text = text.replace(a, f"{a} {b}")
        text = text.replace(b, f"{b} {a}")
    return text


class KeywordScorer:
    """Score jobs against a resume using keyword matching.

    Completely free — no API calls needed.

    Scoring dimensions:
        1. Skill match    (40 pts): resume skills found in JD text or job tags
        2. Title match    (30 pts): job title vs desired titles
        3. Keyword overlap(20 pts): Chinese bigram + English word overlap
        4. Location match (10 pts): location vs preferred areas
    """

    def __init__(self, resume_data: dict, search_config: dict):
        raw_skills = [s.strip() for s in resume_data.get("skills", []) if s.strip()]
        self.skills = [s.lower() for s in raw_skills]
        self.desired_titles = [t.lower() for t in resume_data.get("desired_titles", [])]
        self.raw_text = resume_data.get("raw_text", "").lower()
        self.preferred_areas = [a.lower() for a in search_config.get("areas", [])]

        self.resume_keywords = self._extract_keywords(_normalize(self.raw_text))

    def score(self, job: Job) -> tuple[float, str]:
        """Score a single job. Returns (score: 0–100, reason: str)."""
        reasons = []

        job_text = _normalize(
            f"{job.title} {job.description} {job.requirements}".lower()
        )

        # 1. Skill match (40 pts)
        skill_score, matched_skills = self._score_skills(job_text, job.tags)
        if matched_skills:
            display = [s for s in matched_skills[:6]]
            reasons.append(f"技能匹配({len(matched_skills)}): {', '.join(display)}")

        # 2. Title match (30 pts)
        title_score, title_reason = self._score_title(job.title.lower())
        if title_reason:
            reasons.append(title_reason)

        # 3. Keyword overlap (20 pts)
        keyword_score = self._score_keywords(job_text)

        # 4. Location match (10 pts)
        location_score = self._score_location(job.location.lower())
        if location_score > 0:
            reasons.append(f"地點符合: {job.location[:30]}")

        total = skill_score + title_score + keyword_score + location_score
        total = min(100, max(0, total))

        # Add score breakdown to reason
        breakdown = (
            f"[技能{skill_score:.0f}+職稱{title_score:.0f}"
            f"+關鍵字{keyword_score:.0f}+地點{location_score:.0f}]"
        )
        reasons.append(breakdown)

        return round(total, 1), "; ".join(reasons) if reasons else "關聯度較低"

    def score_jobs(self, jobs: list[Job]) -> list[Job]:
        """Score all jobs and return sorted by score descending."""
        for job in jobs:
            score, reason = self.score(job)
            job.score = score
            job.score_reason = reason
        return sorted(jobs, key=lambda j: j.score, reverse=True)

    # ------------------------------------------------------------------
    # Scoring sub-methods
    # ------------------------------------------------------------------

    def _score_skills(self, job_text: str, job_tags: list) -> tuple[float, list[str]]:
        """Skill match — max 40 pts.

        Uses threshold scoring: SKILL_FULL_SCORE_AT matches = full score.
        This avoids the dilution problem of dividing by total resume skills (~70).
        """
        matched = []
        for skill in self.skills:
            if skill in job_text:
                matched.append(skill)

        # Also check job tags (CakeResume provides explicit skill tags)
        if job_tags:
            tag_set = {t.lower() for t in job_tags}
            for tag in tag_set:
                if tag in self.skills and tag not in matched:
                    matched.append(tag)

        ratio = min(len(matched), SKILL_FULL_SCORE_AT) / SKILL_FULL_SCORE_AT
        return ratio * 40, matched

    def _score_title(self, job_title: str) -> tuple[float, str]:
        """Title match — max 30 pts."""
        if not self.desired_titles:
            return 15, ""

        best_score = 0.0
        best_label = ""

        normalized_title = _normalize(job_title)

        for desired in self.desired_titles:
            norm_desired = _normalize(desired)

            # Full containment
            if norm_desired in normalized_title or normalized_title in norm_desired:
                return 30, f"職稱完全匹配: {desired}"

            # Word overlap
            desired_words = set(norm_desired.split())
            title_words = set(normalized_title.split())
            overlap = desired_words & title_words
            if overlap:
                ratio = len(overlap) / len(desired_words)
                pts = ratio * 25
                if pts > best_score:
                    best_score = pts
                    best_label = desired

        reason = f"職稱部分匹配: {best_label}" if best_score >= 8 else ""
        return best_score, reason

    def _score_keywords(self, job_text: str) -> float:
        """Keyword overlap (Chinese bigrams + English words) — max 20 pts."""
        job_keywords = self._extract_keywords(job_text)

        if not self.resume_keywords or not job_keywords:
            return 10  # neutral

        overlap = self.resume_keywords & job_keywords
        # Denominator capped at 60 to prevent tiny ratios when resume is large
        ratio = len(overlap) / min(len(self.resume_keywords), 60)
        return min(20, ratio * 20)

    def _score_location(self, location: str) -> float:
        """Location preference — max 10 pts."""
        if not self.preferred_areas:
            return 5
        for area in self.preferred_areas:
            if area in location or location in area:
                return 10
        return 0

    # ------------------------------------------------------------------
    # Keyword extraction
    # ------------------------------------------------------------------

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract English words and Chinese bigrams/trigrams from text."""
        stop_words = {
            "的", "了", "和", "是", "在", "有", "我", "們", "這", "那",
            "a", "an", "the", "is", "are", "was", "were", "be", "been",
            "and", "or", "but", "in", "on", "at", "to", "for", "of",
            "with", "by", "from", "as", "into", "through", "during",
            "we", "you", "they", "he", "she", "it", "this", "that",
            "will", "can", "have", "has", "do", "does", "not", "no",
        }

        keywords: set[str] = set()

        # English: whole words
        for word in re.findall(r'[a-zA-Z][a-zA-Z0-9+#\-/]*', text):
            w = word.lower()
            if len(w) > 1 and w not in stop_words:
                keywords.add(w)

        # Chinese: 2-gram and 3-gram sliding window
        for segment in re.findall(r'[一-鿿]+', text):
            for n in (2, 3):
                for i in range(len(segment) - n + 1):
                    keywords.add(segment[i:i + n])

        return keywords
