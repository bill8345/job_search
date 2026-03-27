"""Base classes and data models for job scrapers."""

from __future__ import annotations

from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Optional


@dataclass
class Job:
    """Unified job listing data structure."""
    title: str
    company: str
    location: str
    salary: str
    description: str
    requirements: str
    url: str
    source: str  # "104" | "cakeresume" | "linkedin"
    posted_date: str = ""
    score: float = 0.0
    score_reason: str = ""
    tags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "職缺名稱": self.title,
            "公司": self.company,
            "地點": self.location,
            "薪資": self.salary,
            "來源": self.source,
            "發布日期": self.posted_date,
            "適合度分數": self.score,
            "評分原因": self.score_reason,
            "連結": self.url,
            "職缺描述": self.description[:200] + "..." if len(self.description) > 200 else self.description,
            "要求條件": self.requirements[:200] + "..." if len(self.requirements) > 200 else self.requirements,
        }


class BaseScraper(ABC):
    """Abstract base class for all job scrapers."""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def search(self, keyword: str, area: str = "") -> list[Job]:
        """Search for jobs with the given keyword and area.
        
        Returns a list of Job objects.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Scraper name for display."""
        pass
