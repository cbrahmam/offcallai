# backend/app/workers/background_tasks.py
"""
Background tasks for OffCall AI.
These tasks can be run via a scheduler (cron, Kubernetes CronJob, etc.)
or manually via API endpoints.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)


async def get_async_session() -> AsyncSession:
    """Create a standalone async session for background tasks"""
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True
    )
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    return async_session()


async def run_uptime_calculation(date: Optional[datetime] = None) -> dict:
    """
    Calculate daily uptime for all status page services.
    Should be run daily, typically after midnight.

    Args:
        date: The date to calculate uptime for. Defaults to yesterday.

    Returns:
        dict with results summary
    """
    logger.info("Starting uptime calculation task")

    try:
        async with await get_async_session() as db:
            from app.services.status_page_service import StatusPageService

            service = StatusPageService(db)
            count = await service.calculate_uptime_for_all_services(date)

            result = {
                "success": True,
                "services_processed": count,
                "date": (date or datetime.utcnow() - timedelta(days=1)).date().isoformat(),
                "executed_at": datetime.utcnow().isoformat()
            }

            logger.info(f"Uptime calculation completed: {count} services processed")
            return result

    except Exception as e:
        logger.error(f"Uptime calculation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "executed_at": datetime.utcnow().isoformat()
        }


async def run_maintenance_auto_resolve() -> dict:
    """
    Auto-resolve incidents for maintenance windows that have ended.
    Should be run periodically (every 5-15 minutes).

    Returns:
        dict with results summary
    """
    logger.info("Starting maintenance auto-resolve task")

    try:
        async with await get_async_session() as db:
            from app.services.maintenance_window_service import MaintenanceWindowService

            service = MaintenanceWindowService(db)

            # Get windows that ended recently and need incident resolution
            windows = await service.get_ended_windows_needing_resolution()

            total_resolved = 0
            windows_processed = 0

            for window in windows:
                try:
                    resolved_count = await service.auto_resolve_maintenance_incidents(
                        window_id=window.id,
                        organization_id=window.organization_id
                    )
                    total_resolved += resolved_count
                    windows_processed += 1
                except Exception as e:
                    logger.error(f"Failed to process window {window.id}: {e}")

            result = {
                "success": True,
                "windows_processed": windows_processed,
                "incidents_resolved": total_resolved,
                "executed_at": datetime.utcnow().isoformat()
            }

            logger.info(
                f"Maintenance auto-resolve completed: "
                f"{windows_processed} windows, {total_resolved} incidents resolved"
            )
            return result

    except Exception as e:
        logger.error(f"Maintenance auto-resolve failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "executed_at": datetime.utcnow().isoformat()
        }


async def run_on_call_sync() -> dict:
    """
    Sync User.is_currently_on_call flag based on current schedules.
    Should be run frequently (every 1-5 minutes).

    Returns:
        dict with results summary
    """
    logger.info("Starting on-call sync task")

    try:
        async with await get_async_session() as db:
            from app.services.on_call_service import OnCallService
            from sqlalchemy import select
            from app.models.organization import Organization

            service = OnCallService(db)

            # Get all organizations
            result = await db.execute(select(Organization))
            organizations = result.scalars().all()

            total_updated = 0

            for org in organizations:
                try:
                    updated = await service.sync_user_on_call_status(org.id)
                    total_updated += updated
                except Exception as e:
                    logger.error(f"Failed to sync on-call for org {org.id}: {e}")

            result = {
                "success": True,
                "organizations_processed": len(organizations),
                "users_updated": total_updated,
                "executed_at": datetime.utcnow().isoformat()
            }

            logger.info(f"On-call sync completed: {total_updated} users updated")
            return result

    except Exception as e:
        logger.error(f"On-call sync failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "executed_at": datetime.utcnow().isoformat()
        }


async def run_health_checks() -> dict:
    """
    Run health checks for status page services with health_check_url configured.
    Should be run frequently (every 1-5 minutes).

    Returns:
        dict with results summary
    """
    logger.info("Starting health check task")

    try:
        import aiohttp
        async with await get_async_session() as db:
            from sqlalchemy import select, and_
            from app.models.status_page import StatusPageService, ServiceStatus

            # Get services with health check URLs
            result = await db.execute(
                select(StatusPageService).where(
                    and_(
                        StatusPageService.health_check_url.isnot(None),
                        StatusPageService.is_visible == True
                    )
                )
            )
            services = result.scalars().all()

            checked = 0
            status_changes = 0

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                for service in services:
                    try:
                        async with session.get(service.health_check_url) as response:
                            new_status = "healthy" if response.status < 400 else "unhealthy"

                            # Update service status based on health check
                            old_status = service.status
                            if new_status == "healthy" and old_status != ServiceStatus.OPERATIONAL:
                                service.status = ServiceStatus.OPERATIONAL
                                status_changes += 1
                            elif new_status == "unhealthy" and old_status == ServiceStatus.OPERATIONAL:
                                service.status = ServiceStatus.DEGRADED
                                status_changes += 1

                            service.last_health_check = datetime.utcnow()
                            service.last_health_check_status = new_status
                            checked += 1

                    except Exception as e:
                        service.last_health_check = datetime.utcnow()
                        service.last_health_check_status = f"error: {str(e)[:50]}"
                        if service.status == ServiceStatus.OPERATIONAL:
                            service.status = ServiceStatus.DEGRADED
                            status_changes += 1
                        checked += 1

            await db.commit()

            result = {
                "success": True,
                "services_checked": checked,
                "status_changes": status_changes,
                "executed_at": datetime.utcnow().isoformat()
            }

            logger.info(f"Health checks completed: {checked} services, {status_changes} status changes")
            return result

    except Exception as e:
        logger.error(f"Health checks failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "executed_at": datetime.utcnow().isoformat()
        }


async def run_alert_rules_evaluation() -> dict:
    """
    Evaluate all enabled alert rules across all organizations.
    Should be run frequently (every 1-2 minutes).

    This checks metric thresholds and creates incidents when conditions are met.

    Returns:
        dict with results summary
    """
    logger.info("Starting alert rules evaluation task")

    try:
        async with await get_async_session() as db:
            from app.services.alert_rule_service import alert_rule_service
            from sqlalchemy import select
            from app.models.organization import Organization

            # Get all active organizations
            result = await db.execute(
                select(Organization).where(Organization.is_active == True)
            )
            organizations = result.scalars().all()

            total_evaluated = 0
            total_triggered = 0
            total_resolved = 0
            total_errors = 0
            orgs_processed = 0

            for org in organizations:
                try:
                    eval_result = await alert_rule_service.evaluate_rules(org.id, db)
                    total_evaluated += eval_result.get("evaluated", 0)
                    total_triggered += eval_result.get("triggered", 0)
                    total_resolved += eval_result.get("resolved", 0)
                    total_errors += eval_result.get("errors", 0)
                    orgs_processed += 1
                except Exception as e:
                    logger.error(f"Failed to evaluate rules for org {org.id}: {e}")
                    total_errors += 1

            result = {
                "success": True,
                "organizations_processed": orgs_processed,
                "rules_evaluated": total_evaluated,
                "alerts_triggered": total_triggered,
                "alerts_resolved": total_resolved,
                "errors": total_errors,
                "executed_at": datetime.utcnow().isoformat()
            }

            logger.info(
                f"Alert rules evaluation completed: "
                f"{total_evaluated} rules evaluated, {total_triggered} triggered, {total_resolved} resolved"
            )
            return result

    except Exception as e:
        logger.error(f"Alert rules evaluation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "executed_at": datetime.utcnow().isoformat()
        }


async def run_metrics_cleanup(days_to_keep: int = 7) -> dict:
    """
    Clean up old raw metrics data.
    Should be run daily to manage storage.

    Args:
        days_to_keep: Number of days of raw metrics to retain (default 7)

    Returns:
        dict with results summary
    """
    logger.info(f"Starting metrics cleanup task (keeping {days_to_keep} days)")

    try:
        async with await get_async_session() as db:
            from app.services.metrics_service import metrics_service

            deleted_count = await metrics_service.cleanup_old_metrics(db, days_to_keep)

            result = {
                "success": True,
                "metrics_deleted": deleted_count,
                "days_retained": days_to_keep,
                "executed_at": datetime.utcnow().isoformat()
            }

            logger.info(f"Metrics cleanup completed: {deleted_count} old metrics deleted")
            return result

    except Exception as e:
        logger.error(f"Metrics cleanup failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "executed_at": datetime.utcnow().isoformat()
        }


async def run_host_status_check() -> dict:
    """
    Update host status based on last_seen_at timestamp.
    Marks hosts as inactive if no heartbeat received recently.
    Should be run every 5 minutes.

    Returns:
        dict with results summary
    """
    logger.info("Starting host status check task")

    try:
        async with await get_async_session() as db:
            from sqlalchemy import text

            # Mark hosts as inactive if no heartbeat in last 5 minutes
            result = await db.execute(
                text("""
                    UPDATE hosts
                    SET status = 'inactive', updated_at = NOW()
                    WHERE status = 'active'
                      AND last_seen_at < NOW() - INTERVAL '5 minutes'
                    RETURNING id
                """)
            )
            inactive_hosts = result.fetchall()

            # Mark hosts as active if received heartbeat recently
            result = await db.execute(
                text("""
                    UPDATE hosts
                    SET status = 'active', updated_at = NOW()
                    WHERE status = 'inactive'
                      AND last_seen_at > NOW() - INTERVAL '5 minutes'
                    RETURNING id
                """)
            )
            reactivated_hosts = result.fetchall()

            await db.commit()

            result = {
                "success": True,
                "hosts_marked_inactive": len(inactive_hosts),
                "hosts_reactivated": len(reactivated_hosts),
                "executed_at": datetime.utcnow().isoformat()
            }

            if inactive_hosts or reactivated_hosts:
                logger.info(
                    f"Host status check: {len(inactive_hosts)} marked inactive, "
                    f"{len(reactivated_hosts)} reactivated"
                )
            return result

    except Exception as e:
        logger.error(f"Host status check failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "executed_at": datetime.utcnow().isoformat()
        }


async def run_all_scheduled_tasks() -> dict:
    """
    Run all scheduled background tasks.
    Useful for testing or manual execution.

    Returns:
        dict with all task results
    """
    logger.info("Running all scheduled tasks")

    results = {}

    # Run alert rules evaluation (frequent - every 1-2 min)
    results["alert_rules_evaluation"] = await run_alert_rules_evaluation()

    # Run host status check (frequent - every 5 min)
    results["host_status_check"] = await run_host_status_check()

    # Run maintenance auto-resolve (frequent)
    results["maintenance_auto_resolve"] = await run_maintenance_auto_resolve()

    # Run on-call sync (frequent)
    results["on_call_sync"] = await run_on_call_sync()

    # Run health checks (frequent)
    results["health_checks"] = await run_health_checks()


    # Run uptime calculation (daily - only if after midnight)
    current_hour = datetime.utcnow().hour
    if current_hour < 2:  # Only run between midnight and 2am
        results["uptime_calculation"] = await run_uptime_calculation()
    else:
        results["uptime_calculation"] = {"skipped": True, "reason": "Not in scheduled window"}

    # Run metrics cleanup (daily - only if after midnight)
    if current_hour < 2:
        results["metrics_cleanup"] = await run_metrics_cleanup()
    else:
        results["metrics_cleanup"] = {"skipped": True, "reason": "Not in scheduled window"}

    return results


# CLI entry point for running tasks directly
if __name__ == "__main__":
    import sys

    task_map = {
        "uptime": run_uptime_calculation,
        "maintenance": run_maintenance_auto_resolve,
        "on_call_sync": run_on_call_sync,
        "health_checks": run_health_checks,
        "alert_rules": run_alert_rules_evaluation,
        "host_status": run_host_status_check,
        "metrics_cleanup": run_metrics_cleanup,
        "all": run_all_scheduled_tasks
    }

    if len(sys.argv) < 2 or sys.argv[1] not in task_map:
        print(f"Usage: python -m app.workers.background_tasks <task>")
        print(f"Available tasks: {', '.join(task_map.keys())}")
        sys.exit(1)

    task_name = sys.argv[1]
    print(f"Running task: {task_name}")

    result = asyncio.run(task_map[task_name]())
    print(f"Result: {result}")
