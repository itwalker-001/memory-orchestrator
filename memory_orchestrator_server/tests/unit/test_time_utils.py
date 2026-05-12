from datetime import datetime, timedelta, timezone

from memory_orchestrator_server.time_utils import isoformat_utc, to_utc, utc_now


def test_utc_now_returns_timezone_aware_utc_datetime():
    now = utc_now()

    assert now.tzinfo is timezone.utc
    assert now.utcoffset() == timedelta(0)


def test_to_utc_treats_naive_datetime_as_utc():
    dt = to_utc(datetime(2026, 4, 30, 12, 0, 0))

    assert dt.tzinfo is timezone.utc
    assert dt.isoformat() == "2026-04-30T12:00:00+00:00"


def test_isoformat_utc_normalizes_offsets():
    source = datetime(2026, 4, 30, 20, 0, 0, tzinfo=timezone(timedelta(hours=8)))

    assert isoformat_utc(source) == "2026-04-30T12:00:00+00:00"
