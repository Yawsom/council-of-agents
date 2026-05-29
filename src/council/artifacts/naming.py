"""Filesystem-safe run directory names from the deliberation question."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_RUN_NUM_RE = re.compile(r"^\d+$")


def slugify_question(question: str, max_len: int = 80) -> str:
    """Turn a question into a short, filesystem-safe slug."""
    slug = _SLUG_RE.sub("-", question.strip().lower()).strip("-")
    if not slug:
        return "run"
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "run"


def next_run_number(base_dir: Path, slug: str) -> int:
    """Return the next run index for this question slug under base_dir."""
    marker = f"_{slug}_"
    highest = 0
    if not base_dir.exists():
        return 1
    for path in base_dir.iterdir():
        if not path.is_dir():
            continue
        name = path.name
        if marker not in name:
            continue
        suffix = name.split(marker, 1)[-1]
        if _RUN_NUM_RE.match(suffix):
            highest = max(highest, int(suffix))
    return highest + 1


def build_run_dir_name(question: str, base_dir: str | Path) -> str:
    """Build `{timestamp}_{question-slug}_{run_number}` for a new run folder."""
    base = Path(base_dir)
    slug = slugify_question(question)
    run_num = next_run_number(base, slug)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{slug}_{run_num}"
