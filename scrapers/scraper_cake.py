"""CakeResume Job Scraper.

Scrapes job listings from https://www.cake.me/jobs using HTTP requests
and BeautifulSoup HTML parsing.
"""

from __future__ import annotations

import time
import requests
from bs4 import BeautifulSoup
from scrapers.base import Job, BaseScraper

BASE_URL = "https://www.cake.me/jobs"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

# CakeResume area mapping
AREA_MAPPING = {
    "台北市": "Taipei City",
    "新北市": "New Taipei City",
    "桃園市": "Taoyuan City",
    "台中市": "Taichung City",
    "台南市": "Tainan City",
    "高雄市": "Kaohsiung City",
    "新竹市": "Hsinchu",
    "新竹縣": "Hsinchu",
}


class ScraperCake(BaseScraper):
    """Scraper for CakeResume (cake.me) job listings."""

    @property
    def name(self) -> str:
        return "CakeResume"

    def search(self, keyword: str, area: str = "") -> list[Job]:
        """Search CakeResume for jobs."""
        max_pages = self.config.get("max_pages", 3)
        jobs = []

        for page in range(1, max_pages + 1):
            page_jobs = self._search_page(keyword, area, page)
            if not page_jobs:
                break
            jobs.extend(page_jobs)
            time.sleep(1.5)  # Rate limiting

        return jobs

    def _search_page(self, keyword: str, area: str, page: int) -> list[Job]:
        """Fetch and parse a single page of search results."""
        params = {
            "q": keyword,
            "page": page,
        }
        if area:
            mapped = AREA_MAPPING.get(area, area)
            params["location"] = mapped

        try:
            resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"  [CakeResume] 第 {page} 頁搜尋失敗: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        jobs = []

        # CakeResume job cards - try multiple selectors for robustness
        job_cards = soup.select('a[class*="JobSearchItem"]')
        if not job_cards:
            job_cards = soup.select('div[class*="job-item"]')
        if not job_cards:
            job_cards = soup.select('a[href*="/jobs/"]')

        for card in job_cards:
            job = self._parse_card(card)
            if job:
                jobs.append(job)

        return jobs

    def _parse_card(self, card) -> Job | None:
        """Parse a job card element into a Job object."""
        try:
            # Extract URL
            href = card.get("href", "")
            if not href:
                link = card.find("a", href=True)
                href = link["href"] if link else ""
            
            if not href or "/jobs/" not in href:
                return None

            url = href if href.startswith("http") else f"https://www.cake.me{href}"

            # Extract text content
            title_el = card.select_one('h2, h3, [class*="title"], [class*="Title"]')
            title = title_el.get_text(strip=True) if title_el else ""

            company_el = card.select_one('[class*="company"], [class*="Company"]')
            company = company_el.get_text(strip=True) if company_el else ""

            location_el = card.select_one('[class*="location"], [class*="Location"]')
            location = location_el.get_text(strip=True) if location_el else ""

            salary_el = card.select_one('[class*="salary"], [class*="Salary"]')
            salary = salary_el.get_text(strip=True) if salary_el else "面議"

            if not title:
                # Fallback: get all text
                all_text = card.get_text(separator="|", strip=True).split("|")
                title = all_text[0] if all_text else ""
                company = all_text[1] if len(all_text) > 1 else ""

            if not title:
                return None

            # Get detail page for description
            description, requirements = self._get_detail(url)

            return Job(
                title=title,
                company=company,
                location=location,
                salary=salary,
                description=description,
                requirements=requirements,
                url=url,
                source="CakeResume",
            )
        except Exception as e:
            print(f"  [CakeResume] 解析職缺卡片失敗: {e}")
            return None

    def _get_detail(self, url: str) -> tuple[str, str]:
        """Fetch job detail page for description and requirements."""
        try:
            time.sleep(0.8)
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Try to find description sections
            desc_parts = []
            req_parts = []

            # Look for common section containers
            sections = soup.select('div[class*="ContentSection"], div[class*="content-section"], section')
            for section in sections:
                heading = section.find(["h2", "h3", "h4"])
                text = section.get_text(strip=True)
                if heading:
                    heading_text = heading.get_text(strip=True).lower()
                    if any(k in heading_text for k in ["要求", "條件", "requirement", "qualification"]):
                        req_parts.append(text)
                    else:
                        desc_parts.append(text)
                elif text:
                    desc_parts.append(text)

            # Fallback: get main content area
            if not desc_parts:
                main = soup.select_one('main, [class*="JobDescription"], [class*="job-description"]')
                if main:
                    desc_parts.append(main.get_text(strip=True)[:1000])

            return (
                "\n".join(desc_parts)[:1000],
                "\n".join(req_parts)[:500],
            )
        except Exception:
            return ("", "")
