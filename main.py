#!/usr/bin/env python3
"""
Job Auto Search — 職缺自動化搜尋與適配評分

Usage:
    python main.py                          # 使用 config.yaml 設定搜尋
    python main.py --keyword "python"       # 指定關鍵字
    python main.py --platform 104           # 只搜尋特定平台
    python main.py --keyword "data" --area "台北市"
"""

import argparse
import sys
from pathlib import Path

import yaml
from rich.console import Console

from scrapers.scraper_104 import Scraper104
from scrapers.scraper_cake import ScraperCake
from scrapers.scraper_linkedin import ScraperLinkedIn
from scoring.resume_parser import parse_resume
from scoring.scorer import KeywordScorer
from output.exporter import Exporter


console = Console()


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        console.print(f"[yellow]⚠️  找不到設定檔 {config_path}，使用預設值[/yellow]")
        return {
            "search": {"keywords": ["python"], "areas": ["台北市"]},
            "platforms": {
                "104": {"enabled": True, "max_pages": 2},
                "cakeresume": {"enabled": True, "max_pages": 2},
                "linkedin": {"enabled": True, "max_results": 20},
            },
            "output": {
                "csv_path": "results/jobs.csv",
                "dashboard_path": "results/dashboard.html",
            },
        }

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_search(config: dict, keywords: list[str] = None, areas: list[str] = None,
               platform: str = None):
    """Execute job search across all enabled platforms."""
    search_config = config.get("search", {})
    platform_config = config.get("platforms", {})
    output_config = config.get("output", {})

    # Override with CLI args
    kw_list = keywords or search_config.get("keywords", ["python"])
    area_list = areas or search_config.get("areas", ["台北市"])

    # Initialize scrapers
    scrapers = []
    if (platform is None or platform == "104") and platform_config.get("104", {}).get("enabled", True):
        scrapers.append(Scraper104(platform_config.get("104", {})))
    if (platform is None or platform == "cakeresume") and platform_config.get("cakeresume", {}).get("enabled", True):
        scrapers.append(ScraperCake(platform_config.get("cakeresume", {})))
    if (platform is None or platform == "linkedin") and platform_config.get("linkedin", {}).get("enabled", True):
        scrapers.append(ScraperLinkedIn(platform_config.get("linkedin", {})))

    if not scrapers:
        console.print("[red]❌ 沒有啟用的搜尋平台[/red]")
        return

    # Run searches
    all_jobs = []
    for scraper in scrapers:
        for kw in kw_list:
            for area in area_list:
                console.print(
                    f"🔍 [{scraper.name}] 搜尋 [cyan]{kw}[/cyan] "
                    f"- [blue]{area}[/blue]..."
                )
                try:
                    jobs = scraper.search(kw, area)
                    all_jobs.extend(jobs)
                    console.print(f"   ✅ 找到 {len(jobs)} 筆")
                except Exception as e:
                    console.print(f"   [red]❌ 錯誤: {e}[/red]")

    if not all_jobs:
        console.print("\n[yellow]未找到任何職缺，請嘗試調整搜尋條件[/yellow]")
        return

    # Deduplicate by URL
    seen_urls = set()
    unique_jobs = []
    for job in all_jobs:
        if job.url and job.url not in seen_urls:
            seen_urls.add(job.url)
            unique_jobs.append(job)
        elif not job.url:
            unique_jobs.append(job)

    console.print(f"\n📋 共找到 {len(unique_jobs)} 筆不重複職缺")

    # Score jobs
    console.print("📊 正在評分...")
    resume_data = parse_resume("resume.md")
    scorer = KeywordScorer(resume_data, search_config)
    scored_jobs = scorer.score_jobs(unique_jobs)

    # Export results
    console.print("📤 正在輸出結果...")
    exporter = Exporter(scored_jobs, output_config)
    csv_path, html_path = exporter.export_all()

    console.print(f"\n✨ [bold green]完成！[/bold green]")
    console.print(f"   📄 CSV:       {csv_path}")
    console.print(f"   🌐 Dashboard: {html_path}")
    console.print(f"   💡 開啟 dashboard: [cyan]open {html_path}[/cyan]")


def main():
    parser = argparse.ArgumentParser(
        description="職缺自動化搜尋與適配評分系統",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python main.py                                # 使用 config.yaml 設定
  python main.py --keyword "python developer"   # 指定關鍵字
  python main.py --platform 104                 # 只搜尋 104
  python main.py --keyword "資料分析" --area "台北市"
        """,
    )

    parser.add_argument(
        "--keyword", "-k",
        nargs="+",
        help="搜尋關鍵字（可多個）",
    )
    parser.add_argument(
        "--area", "-a",
        nargs="+",
        help="搜尋地區（可多個）",
    )
    parser.add_argument(
        "--platform", "-p",
        choices=["104", "cakeresume", "linkedin"],
        help="只搜尋特定平台",
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="設定檔路徑 (預設: config.yaml)",
    )
    parser.add_argument(
        "--resume", "-r",
        default="resume.md",
        help="履歷檔案路徑 (預設: resume.md)",
    )

    args = parser.parse_args()

    console.print("\n[bold]🚀 Job Auto Search — 職缺自動化搜尋[/bold]\n")

    config = load_config(args.config)
    run_search(
        config,
        keywords=args.keyword,
        areas=args.area,
        platform=args.platform,
    )


if __name__ == "__main__":
    main()
