"""CakeResume Job Scraper.

Scrapes job listings from https://www.cake.me/jobs using HTTP requests
and BeautifulSoup HTML parsing.
"""

from __future__ import annotations

import re
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

_SALARY_RE = re.compile(r'[\d.]+萬|USD|TWD|\$', re.IGNORECASE)
_LOCATION_RE = re.compile(r'City|District|Taiwan|市|縣|區', re.IGNORECASE)


class ScraperCake(BaseScraper):
    """Scraper for CakeResume (cake.me) job listings."""

    @property
    def name(self) -> str:
        return "CakeResume"

    def search(self, keyword: str, area: str = "") -> list[Job]:
        max_pages = self.config.get("max_pages", 3)
        jobs = []

        for page in range(1, max_pages + 1):
            page_jobs = self._search_page(keyword, area, page)
            if not page_jobs:
                break
            jobs.extend(page_jobs)
            time.sleep(1.5)

        return jobs

    def _search_page(self, keyword: str, area: str, page: int) -> list[Job]:
        params = {"q": keyword, "page": page}
        if area:
            params["location"] = AREA_MAPPING.get(area, area)

        try:
            resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"  [CakeResume] 第 {page} 頁搜尋失敗: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        title_links = soup.select('a[class*="__jobTitle"]')
        if not title_links:
            return []

        jobs = []
        for title_link in title_links:
            job = self._parse_card(title_link)
            if job:
                jobs.append(job)

        return jobs

    def _parse_card(self, title_link) -> Job | None:
        try:
            title = title_link.get_text(" ", strip=True)
            if not title:
                return None

            href = title_link.get("href", "")
            if not href:
                return None
            url = href if href.startswith("http") else f"https://www.cake.me{href}"

            # Navigate up to the card container (ancestor that has InlineMessage)
            card = title_link
            for _ in range(10):
                if card.parent is None:
                    break
                card = card.parent
                if card.select('div[class*="InlineMessage"]'):
                    break

            company_el = card.select_one('a[class*="__companyName"]')
            company = company_el.get_text(strip=True) if company_el else ""

            desc_el = card.select_one('div[class*="__description"]')
            listing_desc = desc_el.get_text(strip=True) if desc_el else ""

            tags = [
                t.get_text(strip=True)
                for t in card.select('div[class*="Tags-module"] div[class*="__item"]')
                if t.get_text(strip=True) not in ("…", "")
            ]

            labels = [
                m.get_text(" ", strip=True)
                for m in card.select('div[class*="InlineMessage"] div[class*="__label"]')
            ]
            salary = next((l for l in labels if _SALARY_RE.search(l)), "面議")
            location = next(
                (l for l in labels if _LOCATION_RE.search(l) and l != salary), ""
            )

            description, requirements = self._get_detail(url)
            if not description:
                description = listing_desc

            return Job(
                title=title,
                company=company,
                location=location,
                salary=salary,
                description=description,
                requirements=requirements,
                url=url,
                source="CakeResume",
                tags=tags,
            )
        except Exception as e:
            print(f"  [CakeResume] 解析職缺失敗: {e}")
            return None

    def _get_detail(self, url: str) -> tuple[str, str]:
        try:
            time.sleep(0.8)
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            left = soup.select_one('div[class*="JobDescriptionLeftColumn"]')
            if not left:
                return ("", "")

            # Use full text + regex split — more robust than DOM traversal
            text = left.get_text(separator="\n", strip=True)

            desc_match = re.search(
                r'職缺描述\n?(.*?)(?:任職條件|職務需求|面試流程|$)',
                text, re.DOTALL
            )
            req_match = re.search(
                r'(?:任職條件|職務需求)\n?(.*?)(?:面試流程|$)',
                text, re.DOTALL
            )

            description = desc_match.group(1).strip() if desc_match else ""
            requirements = req_match.group(1).strip() if req_match else ""

            return (description[:2000], requirements[:1000])
        except Exception:
            return ("", "")
