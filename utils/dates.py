from datetime import datetime, timezone, timedelta

UTC_PLUS_3 = timezone(timedelta(hours=3))
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

def format_duration(td):
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def format_total_duration(count_time_dt: datetime | None) -> str:
    if not count_time_dt:
        return "00:00:00"

    # если хранится без tzinfo (SQLite), считаем это UTC-naive
    if count_time_dt.tzinfo is None:
        count_time_dt = count_time_dt.replace(tzinfo=timezone.utc)

    total_seconds = int((count_time_dt - EPOCH).total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def hhmmss_to_seconds(value: str) -> int | None:
    try:
        h, m, s = value.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except:
        return None

def hhmmss_to_timedelta(value: str) -> timedelta | None:
    seconds=hhmmss_to_seconds(value)
    if seconds == None:
        return
    return timedelta(seconds)
