"""Small markdown reports for ML pipeline runs."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REPORT_ROOT = Path(__file__).resolve().parent.parent / "reports"


def write_run_report(
    *,
    category: str,
    stage: str,
    title: str,
    summary: str,
    details: Iterable[str] = (),
    extra_markdown: str = "",
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    report_dir = REPORT_ROOT / category
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{timestamp}-{stage}.md"

    lines = [
        f"# {title}",
        "",
        f"- Timestamp: `{timestamp}`",
        f"- Stage: `{stage}`",
        "",
        summary,
        "",
    ]
    if details:
        lines.append("## Details")
        lines.append("")
        lines.extend(f"- {detail}" for detail in details)
        lines.append("")
    if extra_markdown:
        lines.append(extra_markdown.rstrip())
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
