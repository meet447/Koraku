"""Human-readable labels for common 5-field cron expressions (keep in sync with web/src/lib/cronHumanize.ts)."""

from __future__ import annotations

import re

_DOW_NAMES = (
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
)

_WEEKDAYS = "__weekdays__"
_WEEKENDS = "__weekends__"


def _pad2(n: int) -> str:
    return str(int(n)).zfill(2)


def _format_24h(minute: int, hour: int) -> str:
    return f"{_pad2(hour)}:{_pad2(minute)}"


def _parse_dow_label(dow: str) -> str | None:
    d = dow.strip()
    if d in ("*", "?"):
        return None
    if d in ("1-5", "MON-FRI"):
        return _WEEKDAYS
    if d in ("0,6", "6,0", "SAT,SUN"):
        return _WEEKENDS
    if re.fullmatch(r"\d", d):
        i = int(d, 10)
        if 0 <= i <= 6:
            return _DOW_NAMES[i]
    return None


def humanize_cron_expression(cron: str) -> str | None:
    raw = " ".join((cron or "").strip().split())
    if not raw or raw == "—":
        return None
    parts = raw.split(" ")
    if len(parts) != 5:
        return None

    min_f, hour, dom, month, dow = parts

    m_step = re.fullmatch(r"\*/(\d+)", min_f)
    if m_step and hour == dom == month == dow == "*":
        n = int(m_step.group(1), 10)
        if 1 <= n <= 59:
            return "Every minute" if n == 1 else f"Every {n} minutes"

    if min_f == "0" and hour == dom == month == dow == "*":
        return "Every hour"

    h_step = re.fullmatch(r"\*/(\d+)", hour)
    if min_f == "0" and h_step and dom == month == dow == "*":
        n = int(h_step.group(1), 10)
        if 1 <= n <= 23:
            return "Every hour" if n == 1 else f"Every {n} hours"

    if re.fullmatch(r"\d{1,2}", min_f) and hour == dom == month == dow == "*":
        m = int(min_f, 10)
        if 0 <= m <= 59:
            return f"Every hour at :{_pad2(m)}"

    if re.fullmatch(r"\d{1,2}", min_f) and re.fullmatch(r"\d{1,2}", hour) and dom == month == dow == "*":
        mi = int(min_f, 10)
        h = int(hour, 10)
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return f"Daily at {_format_24h(mi, h)}"

    if re.fullmatch(r"\d{1,2}", min_f) and re.fullmatch(r"\d{1,2}", hour) and dom == month == "*" and dow != "*":
        mi = int(min_f, 10)
        h = int(hour, 10)
        dow_label = _parse_dow_label(dow)
        if dow_label and 0 <= h <= 23 and 0 <= mi <= 59:
            t = _format_24h(mi, h)
            if dow_label == _WEEKDAYS:
                return f"Weekdays at {t}"
            if dow_label == _WEEKENDS:
                return f"Weekends at {t}"
            return f"Weekly on {dow_label} at {t}"

    if min_f == "0" and hour == "0" and re.fullmatch(r"\d{1,2}", dom) and month == dow == "*":
        day = int(dom, 10)
        if 1 <= day <= 31:
            return f"Monthly on day {day} at 00:00"

    return None
