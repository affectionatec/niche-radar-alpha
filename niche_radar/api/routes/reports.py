"""Report listing and content endpoints."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from niche_radar.config import get_settings

router = APIRouter(tags=["reports"])


@router.get("/api/reports")
def list_reports():
    settings = get_settings()
    report_dir = Path(settings.report_output_dir).resolve()
    if not report_dir.exists():
        return []
    files = sorted(
        (f for f in report_dir.iterdir() if f.is_file() and f.suffix == ".md"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return [
        {"filename": f.name, "size": f.stat().st_size, "modified": f.stat().st_mtime}
        for f in files
    ]


@router.get("/api/reports/{filename}")
def get_report_content(filename: str):
    settings = get_settings()
    report_dir = Path(settings.report_output_dir).resolve()
    try:
        file_path = (report_dir / filename).resolve()
        file_path.relative_to(report_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return {"content": file_path.read_text(encoding="utf-8")}
