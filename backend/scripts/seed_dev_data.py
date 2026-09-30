#!/usr/bin/env python3
"""
Seed a local OffCall AI database with sample data.

Creates an organization and an admin user if they don't exist yet, then fills
in teams, hosts, incidents, alerts, runbooks, schedules and status pages so a
fresh install has something to look at.

Usage:
    export DATABASE_URL=postgresql://postgres@localhost:5432/offcall_ai
    python scripts/seed_dev_data.py [--email admin@example.com] [--password ...]

Time-series data (metrics, logs, traces) lives in ClickHouse; seed that with
scripts/seed_clickhouse_data.py.
"""

import argparse
import asyncio
import os
import sys
from uuid import uuid4, UUID
from datetime import datetime, timedelta, time
import random
import json

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Resolved (or created) at runtime by bootstrap_org_and_user().
ORG_ID: UUID
USER_ID: UUID

DEFAULT_EMAIL = "admin@example.com"
DEFAULT_PASSWORD = "ChangeMe123!"
DEFAULT_ORG = "Example Org"


def normalize_dsn(url: str) -> str:
    """asyncpg wants postgres:// and does not accept SQLAlchemy driver suffixes."""
    for prefix in ("postgresql+asyncpg://", "postgresql://"):
        if url.startswith(prefix):
            return "postgres://" + url[len(prefix):]
    return url


def to_alert_patterns(values: list) -> list:
    """Shape bare match strings into the {field, operator, value} form the API returns."""
    return [{"field": "title", "operator": "regex", "value": v} for v in values]


async def bootstrap_org_and_user(conn, email: str, password: str, org_name: str) -> None:
    """Ensure an organization and admin user exist, and bind their ids globally."""
    global ORG_ID, USER_ID

    user = await conn.fetchrow(
        "SELECT id, organization_id, email FROM users WHERE email = $1", email
    )
    if user:
        USER_ID = user["id"]
        ORG_ID = user["organization_id"]
        print(f"Using existing user {user['email']} in organization {ORG_ID}")
        return

    # Reuse the application's hashing so seeded passwords verify on login.
    from app.core.security import get_password_hash

    slug = org_name.lower().replace(" ", "-")

    # Reuse the organization if a previous run created it.
    existing_org = await conn.fetchval("SELECT id FROM organizations WHERE slug = $1", slug)
    if existing_org:
        ORG_ID = existing_org
    else:
        ORG_ID = uuid4()
        await conn.execute(
            """
            INSERT INTO organizations (id, name, slug, is_active, max_users,
                                       max_incidents_per_month, created_at, updated_at)
            VALUES ($1, $2, $3, true, 25, 1000, now(), now())
            """,
            ORG_ID, org_name, slug,
        )

    USER_ID = uuid4()
    await conn.execute(
        """
        INSERT INTO users (id, organization_id, email, password_hash, full_name,
                           role, is_active, is_verified, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, 'admin', true, true, now(), now())
        """,
        USER_ID, ORG_ID, email, get_password_hash(password), "Admin User",
    )
    print(f"Created organization {org_name!r} and admin user {email}")
    print(f"  Log in with: {email} / {password}")


async def seed_all_demo_data(email: str, password: str, org_name: str):
    """Seed sample data for every major feature."""

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit(
            "DATABASE_URL is not set. Example:\n"
            "  export DATABASE_URL=postgresql://postgres@localhost:5432/offcall_ai"
        )

    conn = await asyncpg.connect(normalize_dsn(database_url))

    await bootstrap_org_and_user(conn, email, password, org_name)

    try:
        now = datetime.utcnow()

        # =====================
        # 1. CREATE TEAMS
        # =====================
        print("\n--- Creating Teams ---")
        teams_data = [
            ("Platform Engineering", "Core platform infrastructure and services"),
            ("Backend Services", "API and backend service development"),
            ("Frontend Team", "Web and mobile UI development"),
            ("DevOps", "CI/CD, deployment, and infrastructure automation"),
            ("SRE Team", "Site reliability and incident response"),
        ]

        team_ids = {}
        for name, description in teams_data:
            existing = await conn.fetchrow(
                "SELECT id FROM teams WHERE organization_id = $1 AND name = $2",
                ORG_ID, name
            )
            if existing:
                team_ids[name] = existing['id']
                print(f"Team '{name}' already exists")
            else:
                team_id = uuid4()
                await conn.execute("""
                    INSERT INTO teams (id, organization_id, name, description, is_active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, true, $5, $5)
                """, team_id, ORG_ID, name, description, now)
                team_ids[name] = team_id
                print(f"Created team: {name}")

                # Add user to team
                await conn.execute("""
                    INSERT INTO team_members (team_id, user_id, role, joined_at)
                    VALUES ($1, $2, 'admin', $3)
                    ON CONFLICT DO NOTHING
                """, team_id, USER_ID, now)

        # =====================
        # 2. CREATE SERVICES
        # =====================
        print("\n--- Creating Services ---")
        services_data = [
            ("Payment Gateway", "payment-gateway", "Handles all payment processing, Stripe integration, and billing", "tier1", "production", "api", "healthy", ["payments", "critical", "pci"], "Platform Engineering"),
            ("User Authentication", "user-auth", "OAuth2/JWT authentication, session management, and SSO", "tier1", "production", "api", "healthy", ["auth", "security", "core"], "Backend Services"),
            ("Order Service", "order-service", "Order processing, inventory checks, and fulfillment", "tier1", "production", "api", "healthy", ["orders", "core", "business-critical"], "Backend Services"),
            ("Notification Hub", "notification-hub", "Email, SMS, push notifications via Twilio/SendGrid", "tier2", "production", "worker", "healthy", ["notifications", "async"], "Platform Engineering"),
            ("Search Service", "search-service", "Elasticsearch-powered product and content search", "tier2", "production", "api", "degraded", ["search", "elasticsearch"], "Backend Services"),
            ("Analytics Engine", "analytics-engine", "Real-time analytics, metrics aggregation, ClickHouse", "tier2", "production", "worker", "healthy", ["analytics", "data"], "Platform Engineering"),
            ("PostgreSQL Primary", "postgres-primary", "Primary PostgreSQL 15 cluster with streaming replication", "tier1", "production", "database", "healthy", ["database", "postgresql", "critical"], "DevOps"),
            ("Redis Cluster", "redis-cluster", "Redis 7 cluster for caching, sessions, and pub/sub", "tier1", "production", "cache", "healthy", ["cache", "redis", "sessions"], "DevOps"),
            ("Kafka Cluster", "kafka-cluster", "Apache Kafka for event streaming and async messaging", "tier1", "production", "queue", "healthy", ["kafka", "events", "messaging"], "Platform Engineering"),
            ("API Gateway", "api-gateway", "Kong API Gateway with rate limiting and auth", "tier1", "production", "api", "healthy", ["gateway", "routing", "security"], "Platform Engineering"),
            ("Web App", "web-app", "Next.js frontend application", "tier2", "production", "web", "healthy", ["frontend", "nextjs", "react"], "Frontend Team"),
            ("Mobile BFF", "mobile-bff", "Backend-for-frontend for iOS and Android apps", "tier2", "production", "api", "healthy", ["mobile", "bff", "api"], "Frontend Team"),
        ]

        service_ids = {}
        for name, slug, desc, tier, env, stype, health, tags, team_name in services_data:
            existing = await conn.fetchrow(
                "SELECT id FROM services WHERE organization_id = $1 AND slug = $2",
                ORG_ID, slug
            )
            if existing:
                service_ids[slug] = existing['id']
                print(f"Service '{name}' already exists")
            else:
                service_id = uuid4()
                team_id = team_ids.get(team_name)
                await conn.execute("""
                    INSERT INTO services (id, organization_id, owner_id, team_id, name, slug, description, tier, environment, service_type, health_status, tags, is_active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, true, $13, $13)
                """, service_id, ORG_ID, USER_ID, team_id, name, slug, desc, tier, env, stype, health, tags, now)
                service_ids[slug] = service_id
                print(f"Created service: {name}")

        # Service dependencies
        dependencies = [
            ("payment-gateway", "postgres-primary"),
            ("payment-gateway", "redis-cluster"),
            ("payment-gateway", "kafka-cluster"),
            ("user-auth", "postgres-primary"),
            ("user-auth", "redis-cluster"),
            ("order-service", "postgres-primary"),
            ("order-service", "kafka-cluster"),
            ("order-service", "payment-gateway"),
            ("notification-hub", "kafka-cluster"),
            ("notification-hub", "redis-cluster"),
            ("search-service", "redis-cluster"),
            ("analytics-engine", "kafka-cluster"),
            ("analytics-engine", "postgres-primary"),
            ("api-gateway", "user-auth"),
            ("api-gateway", "redis-cluster"),
            ("web-app", "api-gateway"),
            ("mobile-bff", "api-gateway"),
        ]

        for upstream, downstream in dependencies:
            if upstream in service_ids and downstream in service_ids:
                existing = await conn.fetchrow("""
                    SELECT 1 FROM service_dependencies
                    WHERE upstream_service_id = $1 AND downstream_service_id = $2
                """, service_ids[upstream], service_ids[downstream])
                if not existing:
                    await conn.execute("""
                        INSERT INTO service_dependencies (upstream_service_id, downstream_service_id, dependency_type)
                        VALUES ($1, $2, 'requires')
                    """, service_ids[upstream], service_ids[downstream])

        # =====================
        # 3. CREATE SLOs
        # =====================
        print("\n--- Creating SLOs ---")
        slos_data = [
            ("Payment API Availability", "99.99% of payment requests succeed", "availability", 99.99, None, "30d", 99.97, 25.0, 75.0, False, "payment-gateway"),
            ("Payment API Latency P99", "99% of payments complete under 2s", "latency", 99.0, 2000, "7d", 99.5, 80.0, 20.0, False, "payment-gateway"),
            ("Auth Service Availability", "99.95% availability for authentication", "availability", 99.95, None, "30d", 99.98, 90.0, 10.0, False, "user-auth"),
            ("Auth Token Latency P95", "95% of token validations under 100ms", "latency", 95.0, 100, "7d", 97.8, 85.0, 15.0, False, "user-auth"),
            ("Order Processing Availability", "99.9% of orders processed successfully", "availability", 99.9, None, "30d", 99.85, 35.0, 65.0, False, "order-service"),
            ("Search Latency P95", "95% of searches return under 500ms", "latency", 95.0, 500, "7d", 91.2, 0.0, 100.0, True, "search-service"),
            ("Database Availability", "99.999% database uptime", "availability", 99.999, None, "30d", 100.0, 100.0, 0.0, False, "postgres-primary"),
            ("Notification Delivery", "99% delivered within 5 minutes", "availability", 99.0, None, "7d", 99.2, 55.0, 45.0, False, "notification-hub"),
            ("API Gateway Latency P99", "99% of requests under 50ms overhead", "latency", 99.0, 50, "7d", 99.8, 95.0, 5.0, False, "api-gateway"),
            ("Cache Hit Rate", "95% cache hit rate", "availability", 95.0, None, "7d", 96.5, 70.0, 30.0, False, "redis-cluster"),
        ]

        slo_ids = {}
        for name, desc, slo_type, target_pct, target_val, window, current, budget_remain, budget_consumed, breached, service_slug in slos_data:
            existing = await conn.fetchrow(
                "SELECT id FROM slos WHERE organization_id = $1 AND name = $2",
                ORG_ID, name
            )
            if existing:
                slo_ids[name] = existing['id']
                print(f"SLO '{name}' already exists")
            else:
                slo_id = uuid4()
                service_id = service_ids.get(service_slug)
                await conn.execute("""
                    INSERT INTO slos (id, organization_id, service_id, name, description, slo_type, target_percentage, target_value, measurement_window, current_percentage, error_budget_remaining, error_budget_consumed, is_breached, is_active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, true, $14, $14)
                """, slo_id, ORG_ID, service_id, name, desc, slo_type, target_pct, target_val, window, current, budget_remain, budget_consumed, breached, now)
                slo_ids[name] = slo_id
                print(f"Created SLO: {name}")

                # Add SLI records
                for i in range(14):
                    record_date = now - timedelta(days=i)
                    total = random.randint(500000, 800000)
                    good = int(total * (current / 100 + random.uniform(-0.002, 0.002)))
                    await conn.execute("""
                        INSERT INTO sli_records (id, slo_id, timestamp, period, total_requests, good_requests, bad_requests, sli_value, p50_latency_ms, p95_latency_ms, p99_latency_ms)
                        VALUES ($1, $2, $3, '1d', $4, $5, $6, $7, $8, $9, $10)
                    """, uuid4(), slo_id, record_date, total, good, total - good, round(good / total * 100),
                        random.randint(10, 30) if slo_type == "latency" else None,
                        random.randint(50, 150) if slo_type == "latency" else None,
                        random.randint(150, 400) if slo_type == "latency" else None)

        # =====================
        # 4. CREATE ESCALATION POLICIES
        # =====================
        print("\n--- Creating Escalation Policies ---")
        escalation_policies_data = [
            ("Critical Infrastructure", "For tier1 infrastructure failures", [
                {"level": 1, "users": [str(USER_ID)], "delay_minutes": 0, "notify_channels": ["slack", "sms", "push"]},
                {"level": 2, "users": [str(USER_ID)], "delay_minutes": 5, "notify_channels": ["slack", "sms", "phone"]},
                {"level": 3, "users": [str(USER_ID)], "delay_minutes": 15, "notify_channels": ["phone"]}
            ]),
            ("Payment Alerts", "Payment service escalation", [
                {"level": 1, "users": [str(USER_ID)], "delay_minutes": 0, "notify_channels": ["slack", "email"]},
                {"level": 2, "users": [str(USER_ID)], "delay_minutes": 10, "notify_channels": ["sms", "slack"]},
            ]),
            ("Default Policy", "Standard escalation for most services", [
                {"level": 1, "users": [str(USER_ID)], "delay_minutes": 5, "notify_channels": ["slack", "email"]},
                {"level": 2, "users": [str(USER_ID)], "delay_minutes": 30, "notify_channels": ["sms"]},
            ]),
        ]

        policy_ids = {}
        for name, desc, rules in escalation_policies_data:
            existing = await conn.fetchrow(
                "SELECT id FROM escalation_policies WHERE organization_id = $1 AND name = $2",
                ORG_ID, name
            )
            if existing:
                policy_ids[name] = existing['id']
                print(f"Escalation Policy '{name}' already exists")
            else:
                policy_id = uuid4()
                await conn.execute("""
                    INSERT INTO escalation_policies (id, organization_id, name, description, escalation_rules, is_active, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, true, $6, $6)
                """, policy_id, ORG_ID, name, desc, json.dumps(rules), now)
                policy_ids[name] = policy_id
                print(f"Created Escalation Policy: {name}")

        # =====================
        # 5. CREATE ON-CALL SCHEDULES
        # =====================
        print("\n--- Creating On-Call Schedules ---")
        schedules_data = [
            ("Primary On-Call", "24/7 primary responder rotation", "America/Los_Angeles", "SRE Team", "Critical Infrastructure"),
            ("Backend On-Call", "Business hours backend support", "America/New_York", "Backend Services", "Default Policy"),
            ("Payment On-Call", "Payment team on-call", "UTC", "Platform Engineering", "Payment Alerts"),
        ]

        schedule_ids = {}
        for name, desc, tz, team_name, policy_name in schedules_data:
            existing = await conn.fetchrow(
                "SELECT id FROM on_call_schedules WHERE organization_id = $1 AND name = $2",
                ORG_ID, name
            )
            if existing:
                schedule_ids[name] = existing['id']
                print(f"Schedule '{name}' already exists")
            else:
                schedule_id = uuid4()
                team_id = team_ids.get(team_name)
                policy_id = policy_ids.get(policy_name)
                await conn.execute("""
                    INSERT INTO on_call_schedules (id, organization_id, team_id, name, description, timezone, escalation_policy_id, is_active, created_by_id, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, true, $8, $9, $9)
                """, schedule_id, ORG_ID, team_id, name, desc, tz, policy_id, USER_ID, now)
                schedule_ids[name] = schedule_id
                print(f"Created Schedule: {name}")

                # Add shifts (user is on-call weekdays 9-5 and weekends all day)
                for day in range(5):  # Mon-Fri
                    await conn.execute("""
                        INSERT INTO on_call_shifts (id, schedule_id, user_id, shift_type, day_of_week, start_time, end_time, notify_channels, created_at, updated_at)
                        VALUES ($1, $2, $3, 'recurring', $4, $5, $6, $7, $8, $8)
                    """, uuid4(), schedule_id, USER_ID, day, time(9, 0), time(17, 0), json.dumps(["slack", "email", "push"]), now)

                for day in [5, 6]:  # Sat-Sun
                    await conn.execute("""
                        INSERT INTO on_call_shifts (id, schedule_id, user_id, shift_type, day_of_week, start_time, end_time, notify_channels, created_at, updated_at)
                        VALUES ($1, $2, $3, 'recurring', $4, $5, $6, $7, $8, $8)
                    """, uuid4(), schedule_id, USER_ID, day, time(0, 0), time(23, 59), json.dumps(["sms", "push"]), now)

        # =====================
        # 6. CREATE RUNBOOKS
        # =====================
        print("\n--- Creating Runbooks ---")
        runbooks_data = [
            (
                "Database Connection Pool Exhaustion",
                "Steps to diagnose and resolve PostgreSQL connection pool issues",
                ["database", "postgresql", "connections"],
                ["postgres-primary"],
                ["connection.*pool", "too many connections", "FATAL.*connection"],
                """# Database Connection Pool Exhaustion

## Symptoms
- Application errors: "connection pool exhausted"
- Database logs showing "too many connections"
- Increased latency in database-dependent services

## Immediate Actions

### 1. Check Current Connections
```sql
SELECT count(*) FROM pg_stat_activity;
SELECT usename, application_name, count(*)
FROM pg_stat_activity
GROUP BY usename, application_name
ORDER BY count DESC;
```

### 2. Identify Idle Connections
```sql
SELECT pid, usename, application_name, state, query_start
FROM pg_stat_activity
WHERE state = 'idle'
AND query_start < now() - interval '10 minutes';
```

### 3. Kill Long-Running Idle Connections
```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
AND query_start < now() - interval '30 minutes';
```

## Root Cause Investigation
1. Check if connection pooler (PgBouncer) is running: `systemctl status pgbouncer`
2. Review application connection pool settings
3. Check for connection leaks in application logs

## Prevention
- Ensure proper connection pool configuration
- Set connection timeouts
- Implement connection health checks
"""
            ),
            (
                "High Memory Usage Alert",
                "Troubleshoot and resolve high memory usage on application servers",
                ["memory", "performance", "oom"],
                ["order-service", "payment-gateway", "user-auth"],
                ["memory.*high", "OOM", "out of memory", "memory pressure"],
                """# High Memory Usage Alert

## Symptoms
- Memory usage above 85% threshold
- Potential OOM killer activity
- Degraded application performance

## Immediate Actions

### 1. Check Current Memory State
```bash
free -h
top -o %MEM
ps aux --sort=-%mem | head -20
```

### 2. Check for Memory Leaks
```bash
# Check heap dumps (Java)
jmap -histo:live <pid> | head -30

# Check Node.js memory
node --expose-gc -e "console.log(process.memoryUsage())"
```

### 3. Emergency Relief
```bash
# Clear system caches (safe)
sync; echo 3 > /proc/sys/vm/drop_caches

# Restart service if needed
kubectl rollout restart deployment/<service-name>
```

## Investigation
1. Review recent deployments
2. Check for traffic spikes
3. Analyze heap dumps for memory leaks
4. Review garbage collection logs

## Long-term Fixes
- Tune JVM heap settings
- Implement memory limits in Kubernetes
- Add memory profiling to CI/CD
"""
            ),
            (
                "API Latency Spike",
                "Diagnose and resolve sudden increases in API response times",
                ["latency", "performance", "api"],
                ["api-gateway", "payment-gateway", "order-service"],
                ["latency.*spike", "slow.*response", "timeout", "p99.*high"],
                """# API Latency Spike Troubleshooting

## Symptoms
- P95/P99 latency exceeding SLO thresholds
- Increased timeout errors
- User-facing performance complaints

## Quick Diagnosis

### 1. Check System Metrics
```bash
# CPU and load
uptime
top -bn1 | head -20

# Network connections
ss -s
netstat -an | grep ESTABLISHED | wc -l
```

### 2. Check Downstream Dependencies
- Database: Check slow query log
- Cache: Check Redis latency `redis-cli --latency`
- External APIs: Check third-party status pages

### 3. Review Recent Changes
```bash
# Recent deployments
kubectl rollout history deployment/<service>

# Recent config changes
git log --oneline -10 config/
```

## Common Causes and Fixes

| Cause | Solution |
|-------|----------|
| Database slow queries | Add missing indexes, optimize queries |
| Cache miss storm | Pre-warm cache, increase TTL |
| Upstream throttling | Implement circuit breakers |
| Resource contention | Scale horizontally |

## Mitigation Steps
1. Enable traffic shedding if available
2. Scale up affected services
3. Enable fallback/degraded mode
4. Communicate with stakeholders
"""
            ),
            (
                "Kafka Consumer Lag",
                "Address high consumer lag in Kafka topics",
                ["kafka", "consumer", "lag", "events"],
                ["kafka-cluster", "notification-hub", "analytics-engine"],
                ["consumer.*lag", "kafka.*behind", "event.*backlog"],
                """# Kafka Consumer Lag Resolution

## Symptoms
- Consumer group showing high lag
- Delayed event processing
- Stale data in downstream systems

## Immediate Assessment

### 1. Check Consumer Lag
```bash
kafka-consumer-groups --bootstrap-server localhost:9092 \\
  --describe --group <consumer-group>
```

### 2. Check Topic Health
```bash
kafka-topics --bootstrap-server localhost:9092 \\
  --describe --topic <topic-name>
```

### 3. Check Consumer Health
```bash
# Check if consumers are running
kubectl get pods -l app=<consumer-app>

# Check consumer logs
kubectl logs -l app=<consumer-app> --tail=100
```

## Resolution Steps

### Scale Consumers
```bash
kubectl scale deployment/<consumer> --replicas=<new-count>
```

### Reset Offset (if needed)
```bash
kafka-consumer-groups --bootstrap-server localhost:9092 \\
  --group <group> --topic <topic> --reset-offsets --to-latest --execute
```

## Prevention
- Set up lag alerting thresholds
- Auto-scaling based on lag metrics
- Monitor consumer throughput
"""
            ),
            (
                "SSL Certificate Expiring",
                "Steps to renew SSL/TLS certificates before expiration",
                ["ssl", "tls", "certificate", "security"],
                ["api-gateway", "web-app"],
                ["certificate.*expir", "ssl.*expire", "tls.*warning"],
                """# SSL Certificate Renewal

## Symptoms
- Certificate expiration warning (< 30 days)
- Browser security warnings
- API connection failures

## Check Certificate Status
```bash
# Check certificate expiration
openssl s_client -connect example.com:443 2>/dev/null | openssl x509 -noout -dates

# Check all certificates in Kubernetes
kubectl get certificates -A
```

## Renewal Process

### For Let's Encrypt (cert-manager)
```bash
# Check cert-manager logs
kubectl logs -n cert-manager deploy/cert-manager

# Force renewal
kubectl delete certificate <cert-name>
# cert-manager will auto-create new one
```

### For Manual Certificates
1. Generate new CSR
2. Submit to CA
3. Download new certificate
4. Update Kubernetes secret:
```bash
kubectl create secret tls <secret-name> \\
  --cert=new-cert.pem \\
  --key=private.key \\
  --dry-run=client -o yaml | kubectl apply -f -
```

## Verification
```bash
# Verify new certificate
curl -vI https://your-domain.com 2>&1 | grep -i "expire"
```
"""
            ),
        ]

        for title, desc, tags, services, patterns, content in runbooks_data:
            existing = await conn.fetchrow(
                "SELECT id FROM runbooks WHERE organization_id = $1 AND title = $2",
                ORG_ID, title
            )
            if existing:
                print(f"Runbook '{title}' already exists")
            else:
                await conn.execute("""
                    INSERT INTO runbooks (id, organization_id, created_by_id, title, description, content, tags, service_names, alert_patterns, is_active, usage_count, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, true, $10, $11, $11)
                """, uuid4(), ORG_ID, USER_ID, title, desc, content, json.dumps(tags), services,
                    json.dumps(to_alert_patterns(patterns)), random.randint(5, 50), now)
                print(f"Created Runbook: {title}")

        # =====================
        # 7. CREATE INCIDENTS
        # =====================
        print("\n--- Creating Incidents ---")
        incidents_data = [
            ("Payment Service Degradation", "Payment processing latency increased significantly", "high", "resolved",
             "Payment gateway experiencing 3x normal latency due to database connection pool exhaustion",
             ["Increased connection pool size", "Added connection timeout monitoring"],
             45, 5, -72),  # resolved 72 hours ago
            ("Search Service Outage", "Elasticsearch cluster became unresponsive", "critical", "resolved",
             "Primary ES node ran out of disk space causing cluster to go red",
             ["Scale ES storage", "Add disk space monitoring"],
             120, 8, -168),  # resolved 1 week ago
            ("Authentication Timeout Spike", "JWT validation taking >5s intermittently", "medium", "resolved",
             "Redis cluster failover caused temporary connection drops",
             ["Implement connection retry logic", "Add Redis sentinel monitoring"],
             30, 3, -24),  # resolved 24 hours ago
            ("API Gateway 5xx Errors", "Intermittent 502 errors on API gateway", "high", "acknowledged",
             "Investigating upstream service health check failures",
             None, None, 2, -2),  # acknowledged 2 hours ago
            ("High Memory on Order Service", "Order service pods showing 90%+ memory", "medium", "open",
             None, None, None, None, 0),  # just opened
            ("Kafka Consumer Lag Alert", "Notification consumer 30 minutes behind", "low", "open",
             None, None, None, None, -1),  # opened 1 hour ago
        ]

        incident_ids = []
        for title, desc, severity, status, ai_summary, ai_actions, resolution_mins, ack_mins, hours_ago in incidents_data:
            existing = await conn.fetchrow(
                "SELECT id FROM incidents WHERE organization_id = $1 AND title = $2",
                ORG_ID, title
            )
            if existing:
                incident_ids.append(existing['id'])
                print(f"Incident '{title}' already exists")
            else:
                incident_id = uuid4()
                created = now + timedelta(hours=hours_ago) if hours_ago else now
                acked = created + timedelta(minutes=ack_mins) if ack_mins else None
                resolved = created + timedelta(minutes=resolution_mins) if resolution_mins else None

                await conn.execute("""
                    INSERT INTO incidents (id, organization_id, title, description, severity, status, assigned_to_id, created_by_id, acknowledged_by_id, resolved_by_id, created_at, acknowledged_at, resolved_at, updated_at, ai_summary, ai_suggested_actions, ai_confidence_score, tags)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                """, incident_id, ORG_ID, title, desc, severity.upper(), status.upper(), USER_ID,
                    USER_ID if acked else None, USER_ID if resolved else None,
                    created, acked, resolved, now, ai_summary, json.dumps(ai_actions) if ai_actions else None,
                    random.randint(75, 95) if ai_summary else None, json.dumps(["auto-created"]))
                incident_ids.append(incident_id)
                print(f"Created Incident: {title}")

        # =====================
        # 8. CREATE ALERTS
        # =====================
        print("\n--- Creating Alerts ---")
        alerts_data = [
            ("High CPU Usage - api-gateway-pod-1", "CPU usage exceeded 85% threshold", "warning", "active", "prometheus", "api-gateway", 0),
            ("Payment API Latency P99 > 2s", "Payment endpoint latency SLO breach", "high", "resolved", "datadog", "payment-gateway", -24),
            ("Redis Memory Usage Critical", "Redis memory at 95%", "critical", "acknowledged", "prometheus", "redis-cluster", -2),
            ("Kafka Consumer Lag > 10000", "notification-consumer behind by 15000 messages", "warning", "active", "prometheus", "notification-hub", -1),
            ("Database Connection Spike", "Connection count increased 3x in 5 minutes", "warning", "resolved", "datadog", "postgres-primary", -48),
            ("SSL Certificate Expiring", "api.example.com certificate expires in 14 days", "warning", "active", "prometheus", "api-gateway", 0),
            ("Order Service Health Check Failed", "3 consecutive health check failures", "error", "active", "prometheus", "order-service", -0.5),
            ("Search Cluster Yellow Status", "Elasticsearch cluster degraded", "warning", "acknowledged", "prometheus", "search-service", -12),
        ]

        for title, desc, severity, status, source, service, hours_ago in alerts_data:
            existing = await conn.fetchrow(
                "SELECT id FROM alerts WHERE organization_id = $1 AND title = $2",
                ORG_ID, title
            )
            if existing:
                print(f"Alert '{title}' already exists")
            else:
                created = now + timedelta(hours=hours_ago)
                await conn.execute("""
                    INSERT INTO alerts (id, organization_id, external_id, fingerprint, title, description, severity, status, source, service_name, environment, started_at, created_at, updated_at, labels, raw_data)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'production', $11, $11, $12, $13, $14)
                """, uuid4(), ORG_ID, f"ext-{uuid4().hex[:8]}", f"fp-{uuid4().hex[:12]}",
                    title, desc, severity.upper(), status.upper(), source, service, created, now,
                    json.dumps({"env": "production", "team": "platform"}),
                    json.dumps({"original_alert": "data"}))
                print(f"Created Alert: {title}")

        # =====================
        # 9. CREATE MAINTENANCE WINDOWS
        # =====================
        print("\n--- Creating Maintenance Windows ---")
        maint_windows = [
            ("Weekly Database Maintenance", "PostgreSQL vacuum and index maintenance",
             now + timedelta(days=3, hours=2), now + timedelta(days=3, hours=4), ["postgres-primary"], False),
            ("API Gateway Upgrade", "Upgrading Kong to v3.5",
             now + timedelta(days=7, hours=1), now + timedelta(days=7, hours=3), ["api-gateway"], False),
            ("Past: Redis Cluster Migration", "Migrated to new Redis cluster",
             now - timedelta(days=5, hours=2), now - timedelta(days=5), ["redis-cluster"], False),
        ]

        for name, desc, start, end, services, recurring in maint_windows:
            existing = await conn.fetchrow(
                "SELECT id FROM maintenance_windows WHERE organization_id = $1 AND name = $2",
                ORG_ID, name
            )
            if existing:
                print(f"Maintenance Window '{name}' already exists")
            else:
                await conn.execute("""
                    INSERT INTO maintenance_windows (id, organization_id, name, description, start_time, end_time,
                                                     services, tags, suppress_alerts, auto_resolve_incidents,
                                                     is_recurring, is_active, is_cancelled, notify_before_minutes,
                                                     notification_sent, created_by_id, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, true, false, $9, true, false, 30, false, $10, $11, $11)
                """, uuid4(), ORG_ID, name, desc, start, end, json.dumps(services), json.dumps([]),
                    recurring, USER_ID, now)
                print(f"Created Maintenance Window: {name}")

        # =====================
        # 10. CREATE POST-MORTEM
        # =====================
        print("\n--- Creating Post-Mortems ---")
        if incident_ids:
            pm_data = (
                "Search Service Outage - Root Cause Analysis",
                incident_ids[1] if len(incident_ids) > 1 else incident_ids[0],  # Search outage incident
                "Elasticsearch cluster became unresponsive due to disk space exhaustion on the primary node, causing a cascade failure across the cluster.",
                "Search functionality was completely unavailable for 2 hours. Approximately 15,000 users were affected, resulting in degraded user experience and potential lost conversions.",
                "The primary Elasticsearch node's data disk reached 100% capacity due to excessive index growth from debug logging that was accidentally left enabled after a troubleshooting session last week.",
                "1. Cleared old indices to free disk space\n2. Restarted Elasticsearch cluster\n3. Disabled debug logging\n4. Verified cluster health returned to green",
                "1. Need automated disk space monitoring with earlier alerts\n2. Debug logging should have automatic expiration\n3. Index lifecycle policies should be enforced",
                [
                    {"id": str(uuid4()), "description": "Implement disk space alerts at 70% and 85%", "assignee_id": str(USER_ID), "due_date": (now + timedelta(days=7)).isoformat(), "status": "in_progress"},
                    {"id": str(uuid4()), "description": "Add ILM policy for all indices", "assignee_id": str(USER_ID), "due_date": (now + timedelta(days=14)).isoformat(), "status": "open"},
                    {"id": str(uuid4()), "description": "Create runbook for ES disk issues", "assignee_id": str(USER_ID), "due_date": (now + timedelta(days=7)).isoformat(), "status": "completed"},
                ],
                120, 8, 115, 120,
            )

            existing = await conn.fetchrow(
                "SELECT id FROM post_mortems WHERE organization_id = $1 AND title = $2",
                ORG_ID, pm_data[0]
            )
            if existing:
                print(f"Post-Mortem '{pm_data[0]}' already exists")
            else:
                await conn.execute("""
                    INSERT INTO post_mortems (id, organization_id, incident_id, title, status, summary, impact, root_cause, resolution, lessons_learned, action_items, detection_time_minutes, response_time_minutes, resolution_time_minutes, total_downtime_minutes, assessed_severity, customer_impact_score, tags, contributing_factors, created_by_id, published_by_id, published_at, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, 'published', $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, 'critical', 8, $15, $16, $17, $17, $18, $18, $18)
                """, uuid4(), ORG_ID, pm_data[1], pm_data[0], pm_data[2], pm_data[3], pm_data[4], pm_data[5], pm_data[6], json.dumps(pm_data[7]), pm_data[8], pm_data[9], pm_data[10], pm_data[11],
                    json.dumps(["outage", "elasticsearch", "disk-space"]),
                    json.dumps(["inadequate monitoring", "debug logging", "missing ILM"]),
                    USER_ID, now)
                print(f"Created Post-Mortem: {pm_data[0]}")

        # =====================
        # 11. CREATE STATUS PAGE
        # =====================
        print("\n--- Creating Status Page ---")
        existing = await conn.fetchrow(
            "SELECT id FROM status_pages WHERE organization_id = $1",
            ORG_ID
        )
        if existing:
            print("Status Page already exists")
            status_page_id = existing['id']
        else:
            status_page_id = uuid4()
            await conn.execute("""
                INSERT INTO status_pages (id, organization_id, name, slug, description, primary_color,
                                          is_public, show_historical_uptime, historical_days,
                                          show_incident_history, incident_history_days,
                                          allow_subscriptions, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, true, true, 90, true, 30, true, $7, $7)
            """, status_page_id, ORG_ID, "Example Org Status", "example-org-status",
                "Real-time status and uptime information for our services", "#6366F1", now)
            print("Created Status Page")

            # Add status page services
            sp_services = [
                ("API", "Core API endpoints", "operational", 0, "Core Services"),
                ("Web Application", "Web dashboard and UI", "operational", 1, "Core Services"),
                ("Authentication", "Login and SSO services", "operational", 2, "Core Services"),
                ("Webhooks", "Incoming webhook processing", "operational", 3, "Integrations"),
                ("Notifications", "Email, SMS, and push notifications", "degraded", 4, "Integrations"),
                ("Slack Integration", "Slack bot and commands", "operational", 5, "Integrations"),
            ]

            for name, desc, status, order, group in sp_services:
                sp_service_id = uuid4()
                await conn.execute("""
                    INSERT INTO status_page_services (id, status_page_id, name, description, status,
                                                      display_order, is_visible, group_name,
                                                      health_check_interval_minutes, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, true, $7, 5, $8, $8)
                """, sp_service_id, status_page_id, name, desc, status.upper(), order, group, now)

                # Add uptime records for last 30 days
                for i in range(30):
                    day = now - timedelta(days=i)
                    uptime = random.randint(98, 100) if status == "operational" else random.randint(95, 99)
                    downtime = int((100 - uptime) / 100 * 1440)  # minutes
                    await conn.execute("""
                        INSERT INTO service_uptime_records (id, service_id, date, uptime_percentage, total_incidents, total_downtime_minutes, operational_minutes, degraded_minutes, outage_minutes)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """, uuid4(), sp_service_id, day, uptime,
                        1 if uptime < 100 else 0, downtime,
                        1440 - downtime, downtime if uptime > 95 else 0, 0 if uptime > 95 else downtime)

            print("Created Status Page Services and Uptime Records")

        print("\n" + "="*50)
        print("Demo data seeding completed successfully!")
        print("="*50)

    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Seed OffCall AI with sample data")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="admin user email")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="admin user password")
    parser.add_argument("--org", default=DEFAULT_ORG, help="organization name")
    args = parser.parse_args()
    asyncio.run(seed_all_demo_data(args.email, args.password, args.org))


if __name__ == "__main__":
    main()
