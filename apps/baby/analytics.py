"""Kick-session analytics: rolling baseline, slow-session flags, time of day and adherence."""
import datetime as dt
from dataclasses import dataclass
from statistics import median

from django.utils import formats, timezone

WINDOW = dt.timedelta(days=7)
MIN_BASELINE_SESSIONS = 3
SLOW_FACTOR = 2
NO_GOAL_ALERT_SECONDS = 2 * 60 * 60
ALERT_MAX_AGE = dt.timedelta(days=2)
TIME_BUCKETS = (("Madrugada", 0, 6), ("Mañana", 6, 12), ("Tarde", 12, 18), ("Noche", 18, 24))
RANGES = {"14": 14, "30": 30, "all": None}
# Two weeks for the weekly comparison plus a day of margin for the alert's baseline.
OVERVIEW_DAYS = 15


@dataclass
class SessionStat:
    session: object
    start: dt.datetime  # local time
    minutes: float | None  # time to reach the target
    baseline: float | None  # median minutes over the previous 7 days
    flagged: bool
    week: int | None  # gestational week

    @property
    def label(self):
        return formats.date_format(self.start, "D j M · H:i")


def session_stats(sessions, lmp=None):
    """Annotate sessions (ascending by start) with their baseline and alert flag."""
    stats = []
    for session in sessions:
        start = timezone.localtime(session.started_at)
        seconds = session.time_to_goal_seconds
        minutes = round(seconds / 60, 1) if seconds is not None else None
        prior = [s.minutes for s in stats if s.minutes is not None and start - WINDOW <= s.start < start]
        baseline = median(prior) if len(prior) >= MIN_BASELINE_SESSIONS else None
        slow = minutes is not None and baseline is not None and minutes > SLOW_FACTOR * baseline
        stalled = not session.goal_reached and (session.duration_seconds or 0) >= NO_GOAL_ALERT_SECONDS
        week = (start.date() - lmp).days // 7 if lmp else None
        stats.append(SessionStat(session, start, minutes, baseline, slow or stalled, week))
    return stats


def latest_alert(stats, now):
    recent = [s for s in stats if s.flagged and s.start >= timezone.localtime(now) - ALERT_MAX_AGE]
    return recent[-1] if recent else None


def _median(values):
    return round(median(values), 1) if values else None


def weekly_summary(stats, today):
    """Last 7 days (today included) against the 7 before."""
    last = [s for s in stats if today - dt.timedelta(days=7) < s.start.date() <= today]
    prev = [s for s in stats if today - dt.timedelta(days=14) < s.start.date() <= today - dt.timedelta(days=7)]
    median_last = _median([s.minutes for s in last if s.minutes is not None])
    median_prev = _median([s.minutes for s in prev if s.minutes is not None])
    return {
        "sessions": len(last),
        "days": len({s.start.date() for s in last}),
        "median": median_last,
        "delta": round(median_last - median_prev, 1) if median_last is not None and median_prev is not None else None,
    }


def recent_overview(sessions, *, now):
    """Dashboard numbers; pass at least the last OVERVIEW_DAYS of sessions, ascending."""
    stats = session_stats(sessions)
    today = timezone.localdate(now)
    return {
        "last": stats[-1] if stats else None,
        "today": sum(1 for s in stats if s.start.date() == today),
        "summary": weekly_summary(stats, today),
        "alert": latest_alert(stats, now),
    }


def _chart_x(value):
    # Wall-clock time encoded as UTC so the browser renders Lima time without shifting it.
    return int(value.replace(tzinfo=dt.UTC).timestamp() * 1000)


def build_report(sessions, *, now, lmp=None, days=30):
    stats = session_stats(sessions, lmp)
    today = timezone.localdate(now)
    report = {"has_data": bool(stats), "summary": weekly_summary(stats, today), "alert": latest_alert(stats, now)}
    if not stats:
        return report

    first_day = stats[0].start.date()
    start_day = max(first_day, today - dt.timedelta(days=days - 1)) if days else first_day
    in_range = [s for s in stats if s.start.date() >= start_day]
    day_count = (today - start_day).days + 1
    range_days = [start_day + dt.timedelta(days=i) for i in range(day_count)]

    line = []
    for day in range_days:
        window = [s.minutes for s in stats if s.minutes is not None and day - dt.timedelta(days=6) <= s.start.date() <= day]
        if window:
            noon = dt.datetime.combine(day, dt.time(12))
            line.append({"x": _chart_x(noon), "y": _median(window)})

    buckets = []
    for name, start_hour, end_hour in TIME_BUCKETS:
        values = [s.minutes for s in in_range if s.minutes is not None and start_hour <= s.start.hour < end_hour]
        buckets.append({"label": name, "hours": f"{start_hour}–{end_hour} h", "median": _median(values), "count": len(values)})

    counts = {}
    for s in in_range:
        counts[s.start.date()] = counts.get(s.start.date(), 0) + 1
    grid_start = start_day - dt.timedelta(days=start_day.weekday())
    grid_end = today + dt.timedelta(days=6 - today.weekday())
    weeks = []
    for offset in range(0, (grid_end - grid_start).days + 1, 7):
        week = []
        for i in range(7):
            day = grid_start + dt.timedelta(days=offset + i)
            count = counts.get(day, 0)
            week.append({
                "date": day,
                "count": count,
                "level": min(count, 3),
                "in_range": start_day <= day <= today,
                "is_today": day == today,
            })
        weeks.append(week)

    chart = {
        "points": [
            {
                "x": _chart_x(s.start.replace(tzinfo=None)),
                "y": s.minutes,
                "flagged": s.flagged,
                "label": s.label,
                "week": s.week,
                "baseline": s.baseline,
                "notes": s.session.notes,
            }
            for s in in_range
            if s.minutes is not None
        ],
        "line": line,
        "buckets": buckets,
        "x_min": _chart_x(dt.datetime.combine(start_day, dt.time())),
        "x_max": _chart_x(dt.datetime.combine(today + dt.timedelta(days=1), dt.time())),
    }
    report.update({"start_day": start_day, "chart": chart, "weeks": weeks, "rows": list(reversed(in_range))})
    return report
