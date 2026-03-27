"""104 人力銀行 Job Scraper.

Uses curl_cffi to bypass Cloudflare TLS fingerprinting and access the
104 search API at https://www.104.com.tw/jobs/search/api/jobs.
"""

from __future__ import annotations

import time
from scrapers.base import Job, BaseScraper

# 104 area code mapping (常用地區)
AREA_CODES = {
    "台北市": "6001001000",
    "新北市": "6001002000",
    "桃園市": "6001003000",
    "台中市": "6001006000",
    "台南市": "6001010000",
    "高雄市": "6001011000",
    "新竹市": "6001004000",
    "新竹縣": "6001004000",
    "全台灣": "",
}

API_URL = "https://www.104.com.tw/jobs/search/api/jobs"
DETAIL_URL = "https://www.104.com.tw/job/ajax/content/{job_no}"

API_HEADERS = {
    "Referer": "https://www.104.com.tw/jobs/search/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}


class Scraper104(BaseScraper):
    """Scraper for 104.com.tw job listings using curl_cffi."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._session = None

    def _get_session(self):
        """Lazy-init a curl_cffi session with browser impersonation."""
        if self._session is None:
            try:
                from curl_cffi import requests as cffi_requests
                self._session = cffi_requests.Session(impersonate="chrome")
            except ImportError:
                print("  [104] 需要安裝 curl_cffi: pip install curl_cffi")
                return None
        return self._session

    @property
    def name(self) -> str:
        return "104"

    def search(self, keyword: str, area: str = "") -> list[Job]:
        """Search 104 for jobs matching keyword and area."""
        session = self._get_session()
        if not session:
            return []

        area_code = AREA_CODES.get(area, "")
        max_pages = self.config.get("max_pages", 3)
        jobs = []

        for page in range(1, max_pages + 1):
            page_jobs = self._search_page(session, keyword, area_code, page)
            if not page_jobs:
                break
            jobs.extend(page_jobs)
            time.sleep(1)

        return jobs

    def _search_page(self, session, keyword: str, area_code: str, page: int) -> list[Job]:
        """Fetch a single page of search results from the API."""
        params = {
            "keyword": keyword,
            "order": "15",
            "pagesize": "20",
            "page": str(page),
        }
        if area_code:
            params["area"] = area_code

        try:
            resp = session.get(API_URL, headers=API_HEADERS, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  [104] 第 {page} 頁搜尋失敗: {e}")
            return []

        # Response structure: {"data": [...jobs], "metadata": {...}}
        job_list = data.get("data", [])
        if not isinstance(job_list, list):
            job_list = job_list.get("list", []) if isinstance(job_list, dict) else []

        jobs = []
        for item in job_list:
            job = self._parse_item(item)
            if job:
                jobs.append(job)

        return jobs

    def _parse_item(self, item: dict) -> Job | None:
        """Parse a job from the API response."""
        try:
            link_obj = item.get("link", {})
            job_url = link_obj.get("job", "")
            
            if job_url:
                if job_url.startswith("//"):
                    full_url = "https:" + job_url
                else:
                    full_url = job_url
            else:
                job_no = item.get("jobNo", "")
                full_url = f"https://www.104.com.tw/job/{job_no}" if job_no else ""

            # Location
            location = item.get("jobAddrNoDesc", "") or item.get("jobAddress", "")

            # Salary
            salary = item.get("salaryDesc", "面議")

            # Description from search results
            description = item.get("description", "")

            # Tags
            tags = []
            for t in item.get("tags", []):
                if isinstance(t, dict):
                    tags.append(t.get("desc", ""))
                elif isinstance(t, str):
                    tags.append(t)

            return Job(
                title=item.get("jobName", ""),
                company=item.get("custName", ""),
                location=location,
                salary=salary,
                description=description,
                requirements="",
                url=full_url,
                source="104",
                posted_date=item.get("appearDate", ""),
                tags=[t for t in tags if t],
            )
        except Exception as e:
            print(f"  [104] 解析職缺失敗: {e}")
            return None

    def get_job_detail(self, job: Job) -> None:
        """Enrich a job with detailed description from the detail API."""
        session = self._get_session()
        if not session or not job.url:
            return

        job_no = job.url.rstrip("/").split("/")[-1].split("?")[0]
        if not job_no:
            return

        detail_url = DETAIL_URL.format(job_no=job_no)
        detail_headers = {
            **API_HEADERS,
            "Referer": job.url,
        }

        try:
            resp = session.get(detail_url, headers=detail_headers, timeout=15)
            if resp.status_code != 200:
                return

            data = resp.json().get("data", {})
            condition = data.get("condition", {})
            job_detail = data.get("jobDetail", {})

            if job_detail.get("jobDescription"):
                job.description = job_detail["jobDescription"]

            req_parts = []
            if condition.get("specialty"):
                specialties = [s.get("description", "") for s in condition["specialty"]]
                req_parts.append("專長: " + ", ".join(specialties))
            if condition.get("skill"):
                skills = [s.get("description", "") for s in condition["skill"]]
                req_parts.append("技能: " + ", ".join(skills))
            if condition.get("other"):
                req_parts.append("其他: " + condition["other"])

            job.requirements = "\n".join(req_parts)
            time.sleep(0.5)
        except Exception:
            pass
