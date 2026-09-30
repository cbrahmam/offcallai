# backend/app/background/worker.py
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import SessionLocal
from app.services.escalation_service import EscalationService
from app.services.alert_rule_service import AlertRuleService
from app.models.host import Host
from app.models.organization import Organization
from app.models.database_monitor import DatabaseInstance, DatabaseMetricSnapshot, DatabaseAlert
import logging
import ssl

# Try to import asyncpg for PostgreSQL monitoring
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

# Configure logging for background workers
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def escalation_worker():
    """Background worker that checks for escalations every 5 minutes"""
    logger.info("Escalation worker started")

    while True:
        try:
            async with SessionLocal() as db:
                logger.debug(f"Checking escalations at {datetime.now().strftime('%H:%M:%S')}")
                escalation_service = EscalationService(db)
                escalated = await escalation_service.check_incidents_for_escalation()

                if escalated:
                    logger.info(f"Escalated {len(escalated)} incidents: {escalated}")
                else:
                    logger.debug("No escalations needed")

        except Exception as e:
            logger.error(f"Escalation worker error: {e}", exc_info=True)

        # Wait 5 minutes before next check
        await asyncio.sleep(300)


async def alert_rule_evaluation_worker():
    """
    Background worker that evaluates metric-based alert rules every 60 seconds.
    This is the core of infrastructure monitoring alerting.
    """
    logger.info("Alert rule evaluation worker started")

    while True:
        try:
            async with SessionLocal() as db:
                # Get all organizations that have hosts (active monitoring)
                result = await db.execute(
                    select(Organization.id).join(
                        Host, Host.organization_id == Organization.id
                    ).distinct()
                )
                org_ids = [row[0] for row in result.fetchall()]

                if org_ids:
                    logger.debug(f"Evaluating alert rules for {len(org_ids)} organizations")

                    total_evaluated = 0
                    total_triggered = 0
                    total_resolved = 0

                    alert_service = AlertRuleService()

                    for org_id in org_ids:
                        try:
                            result = await alert_service.evaluate_rules(org_id, db)
                            total_evaluated += result.get("evaluated", 0)
                            total_triggered += result.get("triggered", 0)
                            total_resolved += result.get("resolved", 0)
                        except Exception as e:
                            logger.error(f"Error evaluating rules for org {org_id}: {e}")

                    if total_triggered > 0 or total_resolved > 0:
                        logger.info(f"Alert rules: {total_evaluated} evaluated, {total_triggered} triggered, {total_resolved} resolved")
                    else:
                        logger.debug(f"{total_evaluated} rules evaluated, no state changes")

        except Exception as e:
            logger.error(f"Alert rule evaluation error: {e}", exc_info=True)

        # Evaluate every 60 seconds
        await asyncio.sleep(60)


async def host_status_worker():
    """
    Background worker that checks host status based on heartbeats.
    Marks hosts as inactive if no heartbeat received in 5 minutes.
    """
    logger.info("Host status worker started")

    while True:
        try:
            async with SessionLocal() as db:
                # Mark hosts as inactive if no heartbeat in 5 minutes
                threshold = datetime.utcnow() - timedelta(minutes=5)

                result = await db.execute(
                    update(Host)
                    .where(
                        Host.status == "active",
                        Host.last_seen_at < threshold
                    )
                    .values(status="inactive")
                    .returning(Host.id)
                )
                inactive_hosts = result.fetchall()
                await db.commit()

                if inactive_hosts:
                    logger.warning(f"Marked {len(inactive_hosts)} hosts as inactive (no heartbeat)")

                # Also mark hosts as active if they've sent heartbeat recently
                result = await db.execute(
                    update(Host)
                    .where(
                        Host.status == "inactive",
                        Host.last_seen_at >= threshold
                    )
                    .values(status="active")
                    .returning(Host.id)
                )
                reactivated_hosts = result.fetchall()
                await db.commit()

                if reactivated_hosts:
                    logger.info(f"Marked {len(reactivated_hosts)} hosts as active (heartbeat received)")

        except Exception as e:
            logger.error(f"Host status worker error: {e}", exc_info=True)

        # Check every 2 minutes
        await asyncio.sleep(120)


async def metrics_aggregation_worker():
    """
    Background worker that aggregates raw metrics into hourly buckets.
    This improves query performance for dashboards.
    """
    logger.info("Metrics aggregation worker started")

    while True:
        try:
            async with SessionLocal() as db:
                # Aggregate metrics from the last 2 hours into hourly buckets
                # This ensures we catch any late-arriving metrics

                # Note: metrics table uses 'time' and 'name' columns
                # metrics_hourly uses 'bucket' and 'name' columns
                await db.execute(text("""
                    INSERT INTO metrics_hourly (bucket, organization_id, host_id, name, avg_value, min_value, max_value, sample_count)
                    SELECT
                        date_trunc('hour', time) as bucket,
                        organization_id,
                        host_id,
                        name,
                        AVG(value) as avg_value,
                        MIN(value) as min_value,
                        MAX(value) as max_value,
                        COUNT(*) as sample_count
                    FROM metrics
                    WHERE time >= NOW() - INTERVAL '2 hours'
                      AND time < date_trunc('hour', NOW())
                    GROUP BY date_trunc('hour', time), organization_id, host_id, name
                    ON CONFLICT (bucket, organization_id, host_id, name)
                    DO UPDATE SET
                        avg_value = EXCLUDED.avg_value,
                        min_value = EXCLUDED.min_value,
                        max_value = EXCLUDED.max_value,
                        sample_count = EXCLUDED.sample_count
                """))
                await db.commit()
                logger.debug(f"Metrics aggregation completed at {datetime.now().strftime('%H:%M:%S')}")

        except Exception as e:
            # This might fail if tables don't exist yet, which is okay
            if "does not exist" not in str(e):
                logger.error(f"Metrics aggregation error: {e}")

        # Run every 15 minutes
        await asyncio.sleep(900)


async def database_monitoring_worker():
    """
    Background worker that polls PostgreSQL databases for metrics every 60 seconds.
    Collects connection stats, query performance, storage, and replication info.
    """
    logger.info("Database monitoring worker started")

    if not ASYNCPG_AVAILABLE:
        logger.warning("asyncpg not installed - database monitoring disabled. Install with: pip install asyncpg")
        return

    # Password storage - in production, use secrets manager
    # For now, we'll use a simple dict that can be populated via API
    # Also read DB_MONITOR_PASSWORDS env var as JSON: {"user": "pass", ...}
    import os as _os
    DB_PASSWORDS = {
        "offcall_monitor": "OffcallMon2024!Secure",  # Default monitoring user password
    }
    _env_passwords = _os.environ.get("DB_MONITOR_PASSWORDS", "")
    if _env_passwords:
        try:
            import json as _json
            DB_PASSWORDS.update(_json.loads(_env_passwords))
        except Exception:
            logger.warning("Failed to parse DB_MONITOR_PASSWORDS env var")

    while True:
        try:
            async with SessionLocal() as db:
                # Get all enabled PostgreSQL database instances
                result = await db.execute(
                    select(DatabaseInstance).where(
                        DatabaseInstance.monitoring_enabled == "true",
                        DatabaseInstance.database_type == "postgresql"
                    )
                )
                instances = result.scalars().all()

                if not instances:
                    logger.debug("No PostgreSQL databases to monitor")
                else:
                    logger.debug(f"Monitoring {len(instances)} PostgreSQL databases")

                for instance in instances:
                    try:
                        await poll_postgresql_instance(instance, db, DB_PASSWORDS)
                    except Exception as e:
                        logger.error(f"Error polling database {instance.name}: {e}")
                        # Update status to show error
                        await db.execute(
                            update(DatabaseInstance)
                            .where(DatabaseInstance.id == instance.id)
                            .values(
                                status="unreachable",
                                connection_status="error",
                                last_check=datetime.utcnow()
                            )
                        )
                        await db.commit()

        except Exception as e:
            logger.error(f"Database monitoring worker error: {e}", exc_info=True)

        # Poll every 60 seconds
        await asyncio.sleep(60)


async def poll_postgresql_instance(instance: DatabaseInstance, db: AsyncSession, passwords: dict):
    """Poll a PostgreSQL database instance for metrics."""

    # Get password from passwords dict or extra_config
    password = passwords.get(instance.username)
    if not password and instance.extra_config:
        password = instance.extra_config.get("password")

    if not password:
        logger.warning(f"No password for database {instance.name} user {instance.username}")
        return

    conn = None
    try:
        # Create SSL context for Azure PostgreSQL
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        # Connect to the database
        conn = await asyncpg.connect(
            host=instance.hostname,
            port=instance.port,
            database=instance.database_name or "postgres",
            user=instance.username,
            password=password,
            ssl=ssl_context,
            timeout=10
        )

        # Collect metrics
        metrics = {}

        # 1. Get PostgreSQL version
        version_row = await conn.fetchrow("SELECT version()")
        if version_row:
            version_str = version_row[0]
            # Extract version number
            import re
            version_match = re.search(r'PostgreSQL (\d+\.\d+)', version_str)
            if version_match:
                metrics['version'] = version_match.group(1)

        # 2. Connection statistics
        conn_stats = await conn.fetchrow("""
            SELECT
                count(*) as total_connections,
                count(*) FILTER (WHERE state = 'active') as active_connections,
                count(*) FILTER (WHERE state = 'idle') as idle_connections,
                count(*) FILTER (WHERE wait_event IS NOT NULL) as waiting_connections
            FROM pg_stat_activity
            WHERE datname = current_database()
        """)
        if conn_stats:
            metrics['connections_total'] = conn_stats['total_connections']
            metrics['connections_active'] = conn_stats['active_connections']
            metrics['connections_idle'] = conn_stats['idle_connections']
            metrics['connections_waiting'] = conn_stats['waiting_connections']

        # 3. Max connections setting
        max_conn = await conn.fetchrow("SHOW max_connections")
        if max_conn:
            metrics['connections_max'] = int(max_conn[0])
            if metrics.get('connections_total') and metrics['connections_max']:
                metrics['connection_utilization'] = (metrics['connections_total'] / metrics['connections_max']) * 100

        # 4. Database size
        size_row = await conn.fetchrow("""
            SELECT pg_database_size(current_database()) as db_size
        """)
        if size_row:
            metrics['storage_used_bytes'] = float(size_row['db_size'])

        # 5. Query statistics (if pg_stat_statements is available)
        try:
            query_stats = await conn.fetchrow("""
                SELECT
                    sum(calls) as total_calls,
                    sum(total_exec_time) as total_time_ms,
                    avg(mean_exec_time) as avg_time_ms,
                    count(*) FILTER (WHERE mean_exec_time > 1000) as slow_queries
                FROM pg_stat_statements
                WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
            """)
            if query_stats and query_stats['total_calls']:
                metrics['queries_total'] = query_stats['total_calls']
                metrics['avg_query_time_ms'] = query_stats['avg_time_ms']
                metrics['slow_queries_count'] = query_stats['slow_queries'] or 0
        except Exception:
            # pg_stat_statements might not be enabled
            pass

        # 6. Cache hit ratio
        cache_stats = await conn.fetchrow("""
            SELECT
                sum(heap_blks_hit) as hits,
                sum(heap_blks_read) as reads
            FROM pg_statio_user_tables
        """)
        if cache_stats and cache_stats['hits'] is not None:
            total = (cache_stats['hits'] or 0) + (cache_stats['reads'] or 0)
            if total > 0:
                metrics['cache_hit_ratio'] = (cache_stats['hits'] / total) * 100

        # 7. Lock statistics
        lock_stats = await conn.fetchrow("""
            SELECT
                count(*) FILTER (WHERE granted) as locks_held,
                count(*) FILTER (WHERE NOT granted) as locks_waiting
            FROM pg_locks
        """)
        if lock_stats:
            metrics['locks_waiting'] = lock_stats['locks_waiting'] or 0

        # 8. Transaction statistics
        xact_stats = await conn.fetchrow("""
            SELECT
                xact_commit + xact_rollback as total_transactions,
                xact_commit as commits,
                xact_rollback as rollbacks,
                deadlocks
            FROM pg_stat_database
            WHERE datname = current_database()
        """)
        if xact_stats:
            metrics['deadlocks_count'] = xact_stats['deadlocks'] or 0

        # 9. Replication lag (if replica)
        if instance.replication_role == "replica":
            try:
                lag_row = await conn.fetchrow("""
                    SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) as lag_seconds
                """)
                if lag_row and lag_row['lag_seconds']:
                    metrics['replication_lag_seconds'] = lag_row['lag_seconds']
            except Exception:
                pass

        # Determine health status
        status = "healthy"
        if metrics.get('connection_utilization', 0) > instance.alert_on_connection_threshold:
            status = "warning"
        if metrics.get('connection_utilization', 0) > 95:
            status = "critical"
        if metrics.get('replication_lag_seconds', 0) > instance.alert_on_replication_lag:
            status = "warning" if status == "healthy" else status

        # Update instance with metrics
        await db.execute(
            update(DatabaseInstance)
            .where(DatabaseInstance.id == instance.id)
            .values(
                status=status,
                connection_status="connected",
                last_check=datetime.utcnow(),
                last_successful_check=datetime.utcnow(),
                version=metrics.get('version'),
                connections_used=metrics.get('connections_total'),
                connections_max=metrics.get('connections_max'),
                connection_utilization=metrics.get('connection_utilization'),
                storage_used_bytes=metrics.get('storage_used_bytes'),
                avg_query_time_ms=metrics.get('avg_query_time_ms'),
                slow_queries_count=metrics.get('slow_queries_count'),
                cache_hit_ratio=metrics.get('cache_hit_ratio'),
                locks_waiting=metrics.get('locks_waiting'),
                deadlocks_count=metrics.get('deadlocks_count'),
                replication_lag_seconds=metrics.get('replication_lag_seconds'),
            )
        )

        # Store metrics snapshot for historical data
        snapshot = DatabaseMetricSnapshot(
            organization_id=instance.organization_id,
            instance_id=instance.id,
            timestamp=datetime.utcnow(),
            connections_active=metrics.get('connections_active'),
            connections_idle=metrics.get('connections_idle'),
            connections_waiting=metrics.get('connections_waiting'),
            connections_total=metrics.get('connections_total'),
            avg_query_time_ms=metrics.get('avg_query_time_ms'),
            slow_queries=metrics.get('slow_queries_count'),
            locks_waiting=metrics.get('locks_waiting'),
            deadlocks=metrics.get('deadlocks_count'),
            cache_hit_ratio=metrics.get('cache_hit_ratio'),
            replication_lag_seconds=metrics.get('replication_lag_seconds'),
            storage_used_bytes=metrics.get('storage_used_bytes'),
        )
        db.add(snapshot)

        await db.commit()

        logger.info(f"Database {instance.name}: status={status}, connections={metrics.get('connections_total')}/{metrics.get('connections_max')}, cache_hit={metrics.get('cache_hit_ratio', 0):.1f}%")

        # Check for alerts
        await check_database_alerts(instance, metrics, db)

    except asyncpg.exceptions.InvalidPasswordError:
        logger.error(f"Invalid password for database {instance.name}")
        await db.execute(
            update(DatabaseInstance)
            .where(DatabaseInstance.id == instance.id)
            .values(status="unreachable", connection_status="auth_error", last_check=datetime.utcnow())
        )
        await db.commit()
    except asyncpg.exceptions.ConnectionDoesNotExistError:
        logger.error(f"Cannot connect to database {instance.name}")
        await db.execute(
            update(DatabaseInstance)
            .where(DatabaseInstance.id == instance.id)
            .values(status="unreachable", connection_status="disconnected", last_check=datetime.utcnow())
        )
        await db.commit()
    except Exception as e:
        logger.error(f"Error polling database {instance.name}: {e}")
        await db.execute(
            update(DatabaseInstance)
            .where(DatabaseInstance.id == instance.id)
            .values(status="unreachable", connection_status="error", last_check=datetime.utcnow())
        )
        await db.commit()
    finally:
        if conn:
            await conn.close()


async def check_database_alerts(instance: DatabaseInstance, metrics: dict, db: AsyncSession):
    """Check metrics against thresholds and create alerts if needed."""

    alerts_to_create = []
    now = datetime.utcnow()

    # Check connection utilization
    conn_util = metrics.get('connection_utilization', 0)
    if conn_util > instance.alert_on_connection_threshold:
        severity = "critical" if conn_util > 95 else "warning"
        alerts_to_create.append({
            "alert_type": "connection_high",
            "severity": severity,
            "title": f"High connection utilization on {instance.display_name or instance.name}",
            "message": f"Connection utilization is {conn_util:.1f}% (threshold: {instance.alert_on_connection_threshold}%)",
            "metric_name": "connection_utilization",
            "metric_value": conn_util,
            "threshold_value": instance.alert_on_connection_threshold,
        })

    # Check replication lag
    rep_lag = metrics.get('replication_lag_seconds', 0)
    if rep_lag and rep_lag > instance.alert_on_replication_lag:
        severity = "critical" if rep_lag > 60 else "warning"
        alerts_to_create.append({
            "alert_type": "replication_lag",
            "severity": severity,
            "title": f"High replication lag on {instance.display_name or instance.name}",
            "message": f"Replication lag is {rep_lag:.1f} seconds (threshold: {instance.alert_on_replication_lag}s)",
            "metric_name": "replication_lag_seconds",
            "metric_value": rep_lag,
            "threshold_value": instance.alert_on_replication_lag,
        })

    # Check for deadlocks
    deadlocks = metrics.get('deadlocks_count', 0)
    if deadlocks > 0:
        # Check if we already have an active deadlock alert
        existing = await db.execute(
            select(DatabaseAlert).where(
                DatabaseAlert.instance_id == instance.id,
                DatabaseAlert.alert_type == "deadlock",
                DatabaseAlert.status == "active"
            )
        )
        if not existing.scalar():
            alerts_to_create.append({
                "alert_type": "deadlock",
                "severity": "warning",
                "title": f"Deadlocks detected on {instance.display_name or instance.name}",
                "message": f"{deadlocks} deadlocks have been detected",
                "metric_name": "deadlocks_count",
                "metric_value": deadlocks,
                "threshold_value": 0,
            })

    # Create alerts
    for alert_data in alerts_to_create:
        # Check if similar alert already exists and is active
        existing = await db.execute(
            select(DatabaseAlert).where(
                DatabaseAlert.instance_id == instance.id,
                DatabaseAlert.alert_type == alert_data["alert_type"],
                DatabaseAlert.status == "active"
            )
        )
        if not existing.scalar():
            alert = DatabaseAlert(
                organization_id=instance.organization_id,
                instance_id=instance.id,
                alert_type=alert_data["alert_type"],
                severity=alert_data["severity"],
                status="active",
                title=alert_data["title"],
                message=alert_data["message"],
                metric_name=alert_data["metric_name"],
                metric_value=alert_data["metric_value"],
                threshold_value=alert_data["threshold_value"],
                triggered_at=now,
            )
            db.add(alert)
            logger.warning(f"Database alert: {alert_data['title']}")

    # Auto-resolve alerts if conditions are back to normal
    if conn_util <= instance.alert_on_connection_threshold:
        await db.execute(
            update(DatabaseAlert)
            .where(
                DatabaseAlert.instance_id == instance.id,
                DatabaseAlert.alert_type == "connection_high",
                DatabaseAlert.status == "active"
            )
            .values(status="resolved", resolved_at=now)
        )

    if rep_lag <= instance.alert_on_replication_lag:
        await db.execute(
            update(DatabaseAlert)
            .where(
                DatabaseAlert.instance_id == instance.id,
                DatabaseAlert.alert_type == "replication_lag",
                DatabaseAlert.status == "active"
            )
            .values(status="resolved", resolved_at=now)
        )

    await db.commit()


async def start_background_workers():
    """Start all background workers"""
    tasks = [
        asyncio.create_task(escalation_worker()),
        asyncio.create_task(alert_rule_evaluation_worker()),
        asyncio.create_task(host_status_worker()),
        asyncio.create_task(metrics_aggregation_worker()),
        asyncio.create_task(database_monitoring_worker()),
    ]

    logger.info("Starting all background workers...")
    logger.info("   - Escalation worker (every 5 min)")
    logger.info("   - Alert rule evaluation (every 60 sec)")
    logger.info("   - Host status check (every 2 min)")
    logger.info("   - Metrics cleanup (every 1 hour)")
    logger.info("   - Metrics aggregation (every 15 min)")
    logger.info("   - Database monitoring (every 60 sec)")

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(start_background_workers())
