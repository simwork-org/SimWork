"""Post-query downsampling for chart artifacts.

When SQL returns more data points than are useful for visualization,
this module reduces them via time-bucket averaging (for date axes)
or stride thinning (for categorical axes).
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

DEFAULT_MAX_POINTS = 200


def downsample_chart(
    labels: list[str],
    series: list[dict[str, Any]],
    max_points: int = DEFAULT_MAX_POINTS,
) -> tuple[list[str], list[dict[str, Any]], bool]:
    """Downsample chart data if it exceeds max_points.

    Returns (labels, series, was_downsampled).
    """
    if len(labels) <= max_points:
        return labels, series, False

    # Try time-based bucketing first
    parsed = [_parse_time_label(lbl) for lbl in labels]
    if all(d is not None for d in parsed):
        dates: list[date] = parsed  # type: ignore[assignment]
        bucket = _choose_bucket(len(labels))
        new_labels, new_series = _time_bucket_average(labels, dates, series, bucket)
        return new_labels, new_series, True

    # Categorical: stride thinning
    new_labels, new_series = _stride_thin(labels, series, max_points)
    return new_labels, new_series, True


def _parse_time_label(label: str) -> date | None:
    """Try to parse a label as a date."""
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m"):
        try:
            from datetime import datetime

            return datetime.strptime(label.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _choose_bucket(n_points: int) -> str:
    if n_points <= 1000:
        return "week"
    return "month"


def _bucket_key(d: date, bucket: str) -> str:
    if bucket == "month":
        return d.strftime("%Y-%m")
    # ISO week
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _bucket_label(d: date, bucket: str) -> str:
    """Human-readable label for the bucket's first date."""
    if bucket == "month":
        return d.strftime("%b %Y")
    return d.strftime("%b %d")


def _time_bucket_average(
    labels: list[str],
    dates: list[date],
    series: list[dict[str, Any]],
    bucket: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Group by time bucket and average values."""
    from collections import OrderedDict

    # Build buckets preserving order
    buckets: OrderedDict[str, list[int]] = OrderedDict()
    bucket_first_date: dict[str, date] = {}

    for i, d in enumerate(dates):
        key = _bucket_key(d, bucket)
        if key not in buckets:
            buckets[key] = []
            bucket_first_date[key] = d
        buckets[key].append(i)

    new_labels = [_bucket_label(bucket_first_date[k], bucket) for k in buckets]
    new_series = []
    for s in series:
        vals = s["values"]
        averaged = []
        for indices in buckets.values():
            avg = sum(vals[i] for i in indices) / len(indices)
            averaged.append(round(avg, 2))
        new_series.append({"name": s["name"], "values": averaged})

    return new_labels, new_series


def _stride_thin(
    labels: list[str],
    series: list[dict[str, Any]],
    max_points: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Keep every Nth point, always including first and last."""
    n = len(labels)
    stride = math.ceil(n / max_points)

    indices = list(range(0, n, stride))
    if indices[-1] != n - 1:
        indices.append(n - 1)

    new_labels = [labels[i] for i in indices]
    new_series = [
        {"name": s["name"], "values": [s["values"][i] for i in indices]}
        for s in series
    ]
    return new_labels, new_series
