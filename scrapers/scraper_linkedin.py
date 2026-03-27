"""LinkedIn Job Scraper.

Uses LinkedIn's public guest jobs API which doesn't require authentication.
Endpoint: https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
"""

from __future__ import annotations

import time
import requests
from bs4 import BeautifulSoup
from scrapers.base import Job, BaseScraper

GUEST_JOBS_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

# LinkedIn location mapping
LOCATION_MAPPING = {
    "台北市": "Taipei, Taiwan",
    "新北市": "New Taipei City, Taiwan",
    "桃園市": "Taoyuan, Taiwan",
    "台中市": "Taichung, Taiwan",
    "台南市": "Tainan, Taiwan",
    "高雄市": "Kaohsiung, Taiwan",
    "新竹市": "Hsinchu, Taiwan",
    "全台灣": "Taiwan",
}


class ScraperLinkedIn(BaseScraper):
    """Scraper for LinkedIn jobs via public guest API."""

    @property
    def name(self) -> str:
        return "LinkedIn"

    def search(self, keyword: str, area: str = "") -> list[Job]:
        """Search LinkedIn for jobs."""
        max_results = self.config.get("max_results", 30)
        location = LOCATION_MAPPING.get(area, area if area else "Taiwan")
        jobs = []

        # LinkedIn returns 25 results per page
        pages_needed = (max_results // 25) + 1
        for page in range(pages_needed):
            start = page * 25
            if len(jobs) >= max_results:
                break

            page_jobs = self._search_page(keyword, location, start)
            if not page_jobs:
                break
            jobs.extend(page_jobs)
            time.sleep(1.5)  # Rate limiting

        return jobs[:max_results]

    def _search_page(self, keyword: str, location: str, start: int) -> list[Job]:
        """Fetch one page of LinkedIn guest job results."""
        params = {
            "keywords": keyword,
            "location": location,
            "start": start,
            "f_TP": "1,2",  # Posted in the last week
        }

        try:
            resp = requests.get(
                GUEST_JOBS_URL, headers=HEADERS, params=params, timeout=15
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"  [LinkedIn] 搜尋失敗 (start={start}): {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        jobs = []

        # LinkedIn guest API returns <li> elements with base-card class
        cards = soup.select("div.base-card, li")
        seen_urls = set()

        for card in cards:
            job = self._parse_card(card)
            if job and job.url and job.url not in seen_urls:
                seen_urls.add(job.url)
                jobs.append(job)

        return jobs

    def _parse_card(self, card) -> Job | None:
        """Parse a LinkedIn job card into a Job object."""
        try:
            # Title
            title_el = card.select_one(".base-search-card__title")
            if not title_el:
                return None
            title = title_el.get_text(strip=True)

            # Company
            company_el = card.select_one(".base-search-card__subtitle")
            company = company_el.get_text(strip=True) if company_el else ""

            # Location
            location_el = card.select_one(".job-search-card__location")
            location = location_el.get_text(strip=True) if location_el else ""

            # URL
            link_el = card.select_one("a.base-card__full-link")
            url = ""
            if link_el and link_el.get("href"):
                url = link_el["href"].split("?")[0]  # Remove tracking params

            # Posted date
            date_el = card.select_one("time")
            posted_date = ""
            if date_el:
                posted_date = date_el.get("datetime", "") or date_el.get_text(strip=True)

            if not title:
                return None

            return Job(
                title=title,
                company=company,
                location=location,
                salary="面議",  # LinkedIn rarely shows salary
                description="",
                requirements="",
                url=url,
                source="LinkedIn",
                posted_date=posted_date,
            )
        except Exception:
            return None
