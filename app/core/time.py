from datetime import UTC, datetime


def utcnow_naive():
    """Return UTC time as a naive datetime for existing PostgreSQL columns."""
    return datetime.now(UTC).replace(tzinfo=None)
