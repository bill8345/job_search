"""CakeResume Job Scraper.

Reads cake.me listings from the Next.js data endpoint
(``_next/data/<buildId>/en/jobs/<keyword>.json``), which returns structured
JSON and is not behind Cloudflare's challenge — unlike the HTML search route,
which now serves a JS challenge that plain HTTP clients cannot pass. The
per-deploy ``buildId`` is read from the (open) homepage on each run.
"""

from __future__ import annotations

import re
import time
from urllib.parse import quote

from scrapers.base import Job, BaseScraper

HOME_URL = "https://www.cake.me/"
DATA_URL = "https://www.cake.me/_next/data/{build_id}/en/jobs/{keyword}.json"

# cake.me is pan-Asian; keep only Taiwan-based listings when an area is requested.
_TAIWAN_RE = re.compile(
    r'台灣|Taiwan|台北|Taipei|新北|New Taipei|桃園|Taoyuan|台中|臺中|Taichung|'
    r'台南|臺南|Tainan|高雄|Kaohsiung|新竹|Hsinchu',
    re.IGNORECASE,
)

_SALARY_PERIOD = {"per_month": "/月", "per_year": "/年", "per_hour": "/時", "per_day": "/日"}


class ScraperCake(BaseScraper):
    """Scraper for CakeResume (cake.me) via its Next.js data API."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._session = None
        self._build_id = None

    @property
    def name(self) -> str:
        return "CakeResume"

    def _get_session(self):
        """Lazy-init a curl_cffi session with browser TLS impersonation."""
        if self._session is None:
            try:
                from curl_cffi import requests as cffi_requests
            except ImportError:
                print("  [CakeResume] 需要安裝 curl_cffi: pip install curl_cffi")
                return None
            self._session = cffi_requests.Session(impersonate="chrome")
        return self._session

    def _get_build_id(self, session) -> str | None:
        """Read the current Next.js buildId from the homepage (changes per deploy)."""
        if self._build_id:
            return self._build_id
        try:
            resp = session.get(HOME_URL, timeout=20)
            resp.raise_for_status()
            match = re.search(r'"buildId":"([^"]+)"', resp.text)
            if not match:
                print("  [CakeResume] 首頁找不到 buildId,網站可能改版")
                return None
            self._build_id = match.group(1)
            return self._build_id
        except Exception as e:
            print(f"  [CakeResume] 取得 buildId 失敗: {e}")
            return None

    def search(self, keyword: str, area: str = "") -> list[Job]:
        session = self._get_session()
        if not session:
            return []
        build_id = self._get_build_id(session)
        if not build_id:
            return []

        max_pages = self.config.get("max_pages", 3)
        jobs: list[Job] = []
        for page in range(1, max_pages + 1):
            page_jobs, total_pages = self._search_page(session, build_id, keyword, page)
            jobs.extend(page_jobs)
            if not page_jobs or page >= total_pages:
                break
            time.sleep(1.0)

        if area:
            before = len(jobs)
            jobs = [j for j in jobs if not j.location or _TAIWAN_RE.search(j.location)]
            filtered = before - len(jobs)
            if filtered:
                print(f"  [CakeResume] 過濾掉 {filtered} 筆非台灣職缺")
        return jobs

    def _search_page(self, session, build_id: str, keyword: str, page: int) -> tuple[list[Job], int]:
        url = DATA_URL.format(build_id=build_id, keyword=quote(keyword))
        params = {"page": page} if page > 1 else None
        try:
            resp = session.get(url, params=params, timeout=20)
            resp.raise_for_status()
            state = resp.json()["pageProps"]["initialState"]["jobSearch"]
        except Exception as e:
            print(f"  [CakeResume] 第 {page} 頁搜尋失敗: {e}")
            return [], 0

        total_pages = 0
        for view in state.get("viewsByFilterKey", {}).values():
            total_pages = view.get("pagination", {}).get("total_pages", 0)
            break

        jobs = []
        for item in state.get("entityByPathId", {}).values():
            job = self._parse_item(item)
            if job:
                jobs.append(job)
        return jobs, total_pages

    def _parse_item(self, item: dict) -> Job | None:
        try:
            title = (item.get("title") or "").strip()
            path = item.get("path") or ""
            if not title or not path:
                return None

            page = item.get("page") or {}
            company_path = page.get("path") or ""
            url = (
                f"https://www.cake.me/companies/{company_path}/jobs/{path}"
                if company_path else f"https://www.cake.me/jobs/{path}"
            )

            locations = item.get("locations") or []
            location = next(
                (l for l in locations if _TAIWAN_RE.search(l)),
                locations[0] if locations else "",
            )

            return Job(
                title=title,
                company=(page.get("name") or "").strip(),
                location=location,
                salary=self._format_salary(item.get("salary") or {}),
                description=(item.get("description") or "")[:2000],
                requirements="",
                url=url,
                source="CakeResume",
                tags=[t for t in (item.get("tags") or []) if t],
            )
        except Exception as e:
            print(f"  [CakeResume] 解析職缺失敗: {e}")
            return None

    @staticmethod
    def _format_salary(salary: dict) -> str:
        def _num(v):
            try:
                n = int(v)
                return f"{n:,}" if n > 0 else ""
            except (TypeError, ValueError):
                return ""

        lo, hi = _num(salary.get("min")), _num(salary.get("max"))
        currency = salary.get("currency") or ""
        period = _SALARY_PERIOD.get(salary.get("type", ""), "")
        if lo and hi:
            return f"{currency} {lo}-{hi} {period}".strip()
        if lo:
            return f"{currency} {lo}+ {period}".strip()
        return "面議"
