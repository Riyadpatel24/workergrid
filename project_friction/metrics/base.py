from datetime import datetime


def parse_iso(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None


def hours_between(start_str: str | None, end_str: str | None) -> float | None:
    dt1 = parse_iso(start_str)
    dt2 = parse_iso(end_str)
    if not dt1 or not dt2 or dt2 < dt1:
        return None
    return (dt2 - dt1).total_seconds() / 3600.0


def calculate_percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int((len(sorted_vals) - 1) * (percentile / 100.0))
    return round(sorted_vals[idx], 2)
