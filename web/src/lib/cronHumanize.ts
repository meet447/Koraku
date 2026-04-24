/**
 * Turn common 5-field cron expressions into short English for automation UI.
 * Unknown shapes return null so callers can show the raw expression.
 */
const DOW_NAMES = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
] as const;

function pad2(n: number): string {
  return String(Math.trunc(n)).padStart(2, "0");
}

function format24h(minute: number, hour: number): string {
  return `${pad2(hour)}:${pad2(minute)}`;
}

/** Internal markers for grouped days-of-week. */
const _WEEKDAYS = "__weekdays__";
const _WEEKENDS = "__weekends__";

function parseDowLabel(dow: string): string | null {
  const d = dow.trim();
  if (d === "*" || d === "?") return null;
  if (d === "1-5" || d === "MON-FRI") return _WEEKDAYS;
  if (d === "0,6" || d === "6,0" || d === "SAT,SUN") return _WEEKENDS;
  if (/^\d$/.test(d)) {
    const i = parseInt(d, 10);
    if (i >= 0 && i <= 6) return DOW_NAMES[i] ?? null;
  }
  return null;
}

export function humanizeCronExpression(cron: string): string | null {
  const raw = cron.trim().replace(/\s+/g, " ");
  if (!raw || raw === "—") return null;
  const parts = raw.split(" ");
  if (parts.length !== 5) return null;

  const [min, hour, dom, month, dow] = parts;

  // */N * * * * — every N minutes
  const minStep = /^\*\/(\d+)$/.exec(min);
  if (minStep && hour === "*" && dom === "*" && month === "*" && dow === "*") {
    const n = parseInt(minStep[1], 10);
    if (n >= 1 && n <= 59) {
      if (n === 1) return "Every minute";
      return `Every ${n} minutes`;
    }
  }

  // 0 * * * * — top of each hour
  if (min === "0" && hour === "*" && dom === "*" && month === "*" && dow === "*") {
    return "Every hour";
  }

  // 0 */N * * * — every N hours on the hour
  const hourStep = /^\*\/(\d+)$/.exec(hour);
  if (min === "0" && hourStep && dom === "*" && month === "*" && dow === "*") {
    const n = parseInt(hourStep[1], 10);
    if (n >= 1 && n <= 23) {
      if (n === 1) return "Every hour";
      return `Every ${n} hours`;
    }
  }

  // N * * * * — same minute each hour (not */n)
  if (/^\d{1,2}$/.test(min) && hour === "*" && dom === "*" && month === "*" && dow === "*") {
    const m = parseInt(min, 10);
    if (m >= 0 && m <= 59) {
      return `Every hour at :${pad2(m)}`;
    }
  }

  // M H * * * — daily at fixed time (calendar day)
  if (/^\d{1,2}$/.test(min) && /^\d{1,2}$/.test(hour) && dom === "*" && month === "*" && dow === "*") {
    const mi = parseInt(min, 10);
    const h = parseInt(hour, 10);
    if (h >= 0 && h <= 23 && mi >= 0 && mi <= 59) {
      return `Daily at ${format24h(mi, h)}`;
    }
  }

  // M H * * DOW — weekly on a named day / weekdays
  if (/^\d{1,2}$/.test(min) && /^\d{1,2}$/.test(hour) && dom === "*" && month === "*") {
    const mi = parseInt(min, 10);
    const h = parseInt(hour, 10);
    const dowLabel = parseDowLabel(dow);
    if (dowLabel && h >= 0 && h <= 23 && mi >= 0 && mi <= 59) {
      const t = format24h(mi, h);
      if (dowLabel === _WEEKDAYS) return `Weekdays at ${t}`;
      if (dowLabel === _WEEKENDS) return `Weekends at ${t}`;
      return `Weekly on ${dowLabel} at ${t}`;
    }
  }

  // 0 0 D * * — monthly on day D at midnight
  if (min === "0" && hour === "0" && /^\d{1,2}$/.test(dom) && month === "*" && dow === "*") {
    const day = parseInt(dom, 10);
    if (day >= 1 && day <= 31) {
      return `Monthly on day ${day} at 00:00`;
    }
  }

  return null;
}

/** Re-write legacy "Scheduled run (cron in tz)." lines using {@link humanizeCronExpression}. */
export function prettifyScheduledTriggerSummary(summary: string): string {
  const t = summary.trim();
  const re = /^Scheduled run \((.+?) in (.+?)\)\s*\.?\s*$/;
  const m = t.match(re);
  if (!m) return summary;
  const inner = m[1].trim();
  const tz = m[2].trim();
  const human = humanizeCronExpression(inner);
  return `Scheduled run (${human ?? inner} in ${tz}).`;
}
