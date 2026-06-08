"""APScheduler-based firing for local scheduled automations."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from koraku.automations import local_store
from koraku.automations.cron_next import compute_next_cron_fire
from koraku.core.config import settings
from koraku.workspace.paths import workspace_dir

if TYPE_CHECKING:
    from koraku.agent.run import Agent

log = logging.getLogger(__name__)

_scheduler: Any = None
_agent: Agent | None = None
_leader_fd: int | None = None
_scheduler_leader_acquired: bool = False


def configure_automation_scheduler(agent: Agent | None) -> None:
    global _agent
    _agent = agent


def _try_acquire_leader_lock() -> bool:
    global _leader_fd
    if os.name == "nt":
        return True
    try:
        import fcntl
    except ImportError:
        return True
    path = Path(workspace_dir()) / ".koraku" / "scheduler.leader.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        log.info(
            "Another Koraku process holds %s; this worker will not run the automation cron scheduler.",
            path,
        )
        return False
    _leader_fd = fd
    return True


def _release_leader_lock() -> None:
    global _leader_fd
    if _leader_fd is None:
        return
    if os.name != "nt":
        try:
            import fcntl

            fcntl.flock(_leader_fd, fcntl.LOCK_UN)
        except OSError:
            pass
    try:
        os.close(_leader_fd)
    except OSError:
        pass
    _leader_fd = None


async def _scheduled_tick(automation_id: str) -> None:
    from koraku.automations.runner import queue_automation_run

    row = local_store.get_automation(automation_id)
    if not row or row.get("status") != "active" or row.get("trigger_mode") != "scheduled":
        return
    summary = f"Scheduled run ({row.get('cron_expression') or 'cron'} in {row.get('timezone') or 'UTC'})."
    try:
        await queue_automation_run(
            automation_id,
            agent=_agent,
            trigger_summary=summary,
        )
    except Exception:
        log.exception("Automation %s failed", automation_id)


def sync_scheduler_jobs() -> None:
    """Register or remove APScheduler jobs from the local store."""
    global _scheduler
    if _scheduler is None:
        return
    try:
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        log.warning("apscheduler not installed; scheduled automations will not fire")
        return

    wanted: set[str] = set()
    for row in local_store.list_scheduled_active():
        cron = (row.get("cron_expression") or "").strip()
        tz = (row.get("timezone") or "").strip()
        if not cron or not tz:
            continue
        aid = str(row.get("id") or "").strip()
        if not aid:
            continue
        job_id = f"koraku-auto-{aid}"
        wanted.add(job_id)
        try:
            trigger = CronTrigger.from_crontab(cron, timezone=tz)
        except Exception as e:
            log.warning("Invalid cron for automation %s: %s", aid, e)
            continue
        _scheduler.add_job(
            _scheduled_tick,
            trigger,
            id=job_id,
            replace_existing=True,
            kwargs={"automation_id": aid},
            max_instances=1,
            coalesce=True,
            misfire_grace_time=120,
        )
        nxt = compute_next_cron_fire(cron, tz, base=datetime.now(timezone.utc))
        if nxt:
            log.debug("automation %s next fire ~ %s", aid, nxt.isoformat())

    for job in list(_scheduler.get_jobs()):
        jid = job.id
        if isinstance(jid, str) and jid.startswith("koraku-auto-") and jid not in wanted:
            job.remove()


async def sync_scheduler_jobs_async() -> None:
    await asyncio.to_thread(sync_scheduler_jobs)


async def _periodic_resync() -> None:
    try:
        await asyncio.to_thread(sync_scheduler_jobs)
    except Exception:
        log.exception("automation scheduler periodic resync failed")


def start_automation_scheduler() -> None:
    global _scheduler, _scheduler_leader_acquired
    if _scheduler is not None:
        return
    if not settings.automation_scheduler_enabled:
        log.info("Automation scheduler disabled (automation_scheduler_enabled=False).")
        return
    if not _try_acquire_leader_lock():
        return
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        log.warning("apscheduler not installed; automation scheduler disabled")
        _release_leader_lock()
        return
    _scheduler = AsyncIOScheduler(timezone=timezone.utc)
    _scheduler.start()
    log.info("Local automation scheduler started (leader lock acquired)")
    sec = max(15, int(settings.automation_scheduler_resync_seconds))
    _scheduler.add_job(
        _periodic_resync,
        "interval",
        seconds=sec,
        id="koraku-auto-resync",
        replace_existing=True,
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )
    sync_scheduler_jobs()
    _scheduler_leader_acquired = True


def shutdown_automation_scheduler() -> None:
    global _scheduler, _scheduler_leader_acquired
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            log.exception("scheduler shutdown")
        _scheduler = None
    _scheduler_leader_acquired = False
    _release_leader_lock()


def is_running() -> bool:
    sch = _scheduler
    return sch is not None and getattr(sch, "running", False)


def is_automation_scheduler_leader() -> bool:
    return _scheduler_leader_acquired
