from __future__ import annotations

from typing import Any


def resolve_window_ns(job: Any, now_ns: int) -> tuple[int, int]:
    source_filter = job.source_filter or {}
    schedule = job.schedule or {}
    lookback_hours = int(source_filter.get('lookback_hours') or schedule.get('lookback_hours') or 24)
    end_at = int(source_filter.get('end_at') or now_ns // 1_000_000_000)
    start_at = int(source_filter.get('start_at') or (end_at - lookback_hours * 60 * 60))
    return start_at, end_at
