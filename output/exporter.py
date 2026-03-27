"""Export job search results to CSV, HTML dashboard, and terminal."""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime

import pandas as pd
from rich.console import Console
from rich.table import Table
from jinja2 import Template

from scrapers.base import Job

DASHBOARD_TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "templates", "dashboard.html"
)


class Exporter:
    """Export job results in multiple formats."""

    def __init__(self, jobs: list[Job], output_config: dict):
        self.jobs = jobs
        self.config = output_config

    def export_all(self):
        """Run all export methods."""
        self.export_terminal()
        csv_path = self.export_csv()
        html_path = self.export_dashboard()
        return csv_path, html_path

    def export_csv(self) -> str:
        """Export to CSV file."""
        csv_path = self.config.get("csv_path", "results/jobs.csv")
        Path(csv_path).parent.mkdir(parents=True, exist_ok=True)

        df = pd.DataFrame([j.to_dict() for j in self.jobs])
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"\n📄 CSV 已儲存: {csv_path} ({len(self.jobs)} 筆)")
        return csv_path

    def export_terminal(self):
        """Print results as a rich terminal table."""
        console = Console()

        if not self.jobs:
            console.print("\n[yellow]未找到任何職缺[/yellow]")
            return

        table = Table(
            title=f"🔍 職缺搜尋結果 ({len(self.jobs)} 筆)",
            show_lines=True,
            title_style="bold cyan",
        )

        table.add_column("分數", justify="center", style="bold", width=6)
        table.add_column("職缺名稱", style="white", max_width=30)
        table.add_column("公司", style="green", max_width=20)
        table.add_column("地點", style="blue", max_width=10)
        table.add_column("薪資", style="yellow", max_width=15)
        table.add_column("來源", justify="center", width=10)
        table.add_column("評分原因", style="dim", max_width=30)

        for job in self.jobs[:30]:  # Show top 30
            score_style = self._score_style(job.score)
            table.add_row(
                f"[{score_style}]{job.score}[/{score_style}]",
                job.title[:30],
                job.company[:20],
                job.location[:10],
                job.salary[:15],
                job.source,
                job.score_reason[:30],
            )

        console.print(table)

        # Summary stats
        sources = {}
        for j in self.jobs:
            sources[j.source] = sources.get(j.source, 0) + 1

        console.print(f"\n📊 來源統計: ", end="")
        for src, count in sources.items():
            console.print(f"[cyan]{src}[/cyan]: {count} 筆  ", end="")
        console.print()

        if self.jobs:
            avg = sum(j.score for j in self.jobs) / len(self.jobs)
            console.print(f"📈 平均適合度: [bold]{avg:.1f}[/bold] 分")

    def export_dashboard(self) -> str:
        """Export as HTML dashboard."""
        html_path = self.config.get("dashboard_path", "results/dashboard.html")
        Path(html_path).parent.mkdir(parents=True, exist_ok=True)

        # Load template
        try:
            tmpl_path = Path(DASHBOARD_TEMPLATE_PATH)
            template_str = tmpl_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            template_str = self._fallback_template()

        template = Template(template_str)

        # Prepare data
        jobs_data = [j.to_dict() for j in self.jobs]
        sources = {}
        for j in self.jobs:
            sources[j.source] = sources.get(j.source, 0) + 1

        score_dist = {"high": 0, "medium": 0, "low": 0}
        for j in self.jobs:
            if j.score >= 60:
                score_dist["high"] += 1
            elif j.score >= 30:
                score_dist["medium"] += 1
            else:
                score_dist["low"] += 1

        html = template.render(
            jobs=self.jobs,
            jobs_data=jobs_data,
            total=len(self.jobs),
            sources=sources,
            score_dist=score_dist,
            avg_score=sum(j.score for j in self.jobs) / len(self.jobs) if self.jobs else 0,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        Path(html_path).write_text(html, encoding="utf-8")
        print(f"🌐 Dashboard 已儲存: {html_path}")
        return html_path

    def _score_style(self, score: float) -> str:
        if score >= 60:
            return "green"
        elif score >= 30:
            return "yellow"
        return "red"

    def _fallback_template(self) -> str:
        """Minimal fallback if template file is missing."""
        return """<!DOCTYPE html>
<html><head><title>Job Search Results</title></head>
<body>
<h1>Job Search Results ({{ total }} jobs)</h1>
<p>Generated: {{ generated_at }}</p>
<table border="1">
<tr><th>Score</th><th>Title</th><th>Company</th><th>Location</th><th>Source</th></tr>
{% for job in jobs %}
<tr>
<td>{{ job.score }}</td>
<td><a href="{{ job.url }}">{{ job.title }}</a></td>
<td>{{ job.company }}</td>
<td>{{ job.location }}</td>
<td>{{ job.source }}</td>
</tr>
{% endfor %}
</table></body></html>"""
