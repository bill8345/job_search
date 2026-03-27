"""Job-Resume matching scorer using keyword matching (free, no API needed)."""

from __future__ import annotations

import re
from scrapers.base import Job


class KeywordScorer:
    """Score jobs against a resume using keyword matching.
    
    Completely free - no API calls needed.
    Scoring dimensions:
        1. Skill match (40%): How many resume skills appear in job description
        2. Title match (30%): How well job title matches desired titles
        3. Keyword relevance (20%): General keyword overlap
        4. Location match (10%): Whether location matches preference
    """

    def __init__(self, resume_data: dict, search_config: dict):
        self.skills = [s.lower() for s in resume_data.get("skills", [])]
        self.desired_titles = [t.lower() for t in resume_data.get("desired_titles", [])]
        self.experience = resume_data.get("experience", [])
        self.raw_text = resume_data.get("raw_text", "").lower()
        self.preferred_areas = [a.lower() for a in search_config.get("areas", [])]
        
        # Build keyword set from entire resume
        self.resume_keywords = self._extract_keywords(self.raw_text)

    def score(self, job: Job) -> tuple[float, str]:
        """Score a single job against the resume.
        
        Returns (score: 0-100, reason: str).
        """
        reasons = []
        
        job_text = f"{job.title} {job.description} {job.requirements}".lower()
        
        # 1. Skill match (40 points)
        skill_score, matched_skills = self._score_skills(job_text)
        if matched_skills:
            reasons.append(f"匹配技能: {', '.join(matched_skills[:5])}")
        
        # 2. Title match (30 points)
        title_score, title_reason = self._score_title(job.title.lower())
        if title_reason:
            reasons.append(title_reason)
        
        # 3. Keyword relevance (20 points)
        keyword_score = self._score_keywords(job_text)
        
        # 4. Location match (10 points)
        location_score = self._score_location(job.location.lower())
        if location_score > 0:
            reasons.append(f"地點匹配: {job.location}")
        
        total = skill_score + title_score + keyword_score + location_score
        total = min(100, max(0, total))
        
        if not reasons:
            reasons.append("關聯度較低")
        
        return round(total, 1), "; ".join(reasons)

    def score_jobs(self, jobs: list[Job]) -> list[Job]:
        """Score all jobs and return them sorted by score."""
        for job in jobs:
            score, reason = self.score(job)
            job.score = score
            job.score_reason = reason
        
        return sorted(jobs, key=lambda j: j.score, reverse=True)

    def _score_skills(self, job_text: str) -> tuple[float, list[str]]:
        """Score based on skill keyword matching (max 40 points)."""
        if not self.skills:
            return 20, []  # Neutral if no skills defined
        
        matched = []
        for skill in self.skills:
            # Allow partial matching for compound skills
            if skill in job_text:
                matched.append(skill)
        
        ratio = len(matched) / len(self.skills) if self.skills else 0
        score = ratio * 40
        return score, matched

    def _score_title(self, job_title: str) -> tuple[float, str]:
        """Score based on title matching (max 30 points)."""
        if not self.desired_titles:
            return 15, ""  # Neutral
        
        best_match = 0
        best_title = ""
        
        for desired in self.desired_titles:
            # Exact match
            if desired in job_title or job_title in desired:
                best_match = 30
                best_title = desired
                break
            
            # Partial word match
            desired_words = set(desired.split())
            title_words = set(job_title.split())
            overlap = desired_words & title_words
            
            if overlap:
                ratio = len(overlap) / len(desired_words)
                match_score = ratio * 25
                if match_score > best_match:
                    best_match = match_score
                    best_title = desired
        
        reason = f"職稱匹配: {best_title}" if best_match > 10 else ""
        return best_match, reason

    def _score_keywords(self, job_text: str) -> float:
        """Score based on general keyword overlap (max 20 points)."""
        job_keywords = self._extract_keywords(job_text)
        
        if not self.resume_keywords or not job_keywords:
            return 10  # Neutral
        
        overlap = self.resume_keywords & job_keywords
        ratio = len(overlap) / min(len(self.resume_keywords), 50)  # Cap denominator
        
        return min(20, ratio * 20)

    def _score_location(self, location: str) -> float:
        """Score based on location preference (max 10 points)."""
        if not self.preferred_areas:
            return 5  # Neutral
        
        for area in self.preferred_areas:
            if area in location or location in area:
                return 10
        
        return 0

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract meaningful keywords from text."""
        # Remove common stop words (Chinese + English)
        stop_words = {
            "的", "了", "和", "是", "在", "有", "我", "們", "這", "那",
            "a", "an", "the", "is", "are", "was", "were", "be", "been",
            "and", "or", "but", "in", "on", "at", "to", "for", "of",
            "with", "by", "from", "as", "into", "through", "during",
            "we", "you", "they", "he", "she", "it", "this", "that",
        }
        
        # Extract English words and Chinese segments
        words = re.findall(r'[a-zA-Z]+|[\u4e00-\u9fff]+', text)
        keywords = set()
        
        for word in words:
            w = word.lower().strip()
            if w and len(w) > 1 and w not in stop_words:
                keywords.add(w)
        
        return keywords
