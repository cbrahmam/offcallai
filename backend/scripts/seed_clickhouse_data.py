#!/usr/bin/env python3
"""
Comprehensive ClickHouse demo data seeder for all features.
Seeds: metrics, logs, spans/traces, RUM events, network flows, profiles
"""

import asyncio
import httpx
import random
import json
from datetime import datetime, timedelta
from uuid import uuid4

# ClickHouse connection
CLICKHOUSE_HOST = "op8vy24caq.eastus2.azure.clickhouse.cloud"
CLICKHOUSE_PORT = 8443
CLICKHOUSE_USER = "default"
CLICKHOUSE_PASSWORD = "CQ_lCL2V.Ib14"
CLICKHOUSE_DATABASE = "offcall"

# Demo organization
ORG_ID = "8a1d227e-d348-42e6-ab39-67456a362ef3"

# Demo hosts
HOSTS = [
    {"id": "host-001", "name": "web-server-1", "ip": "10.0.1.10"},
    {"id": "host-002", "name": "web-server-2", "ip": "10.0.1.11"},
    {"id": "host-003", "name": "api-server-1", "ip": "10.0.2.10"},
    {"id": "host-004", "name": "api-server-2", "ip": "10.0.2.11"},
    {"id": "host-005", "name": "db-primary", "ip": "10.0.3.10"},
    {"id": "host-006", "name": "db-replica", "ip": "10.0.3.11"},
    {"id": "host-007", "name": "cache-server", "ip": "10.0.4.10"},
    {"id": "host-008", "name": "worker-1", "ip": "10.0.5.10"},
]

# Services for traces
SERVICES = [
    "api-gateway",
    "user-service",
    "order-service",
    "payment-service",
    "inventory-service",
    "notification-service",
    "auth-service",
    "analytics-service",
]

# RUM applications
RUM_APPS = [
    {"id": "app-web", "name": "Web Dashboard"},
    {"id": "app-mobile", "name": "Mobile App"},
    {"id": "app-admin", "name": "Admin Portal"},
]


async def execute_query(client: httpx.AsyncClient, query: str) -> dict:
    """Execute a ClickHouse query."""
    url = f"https://{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}/"
    params = {
        "user": CLICKHOUSE_USER,
        "password": CLICKHOUSE_PASSWORD,
        "database": CLICKHOUSE_DATABASE,
    }
    try:
        response = await client.post(url, params=params, content=query, timeout=60.0)
        if response.status_code == 200:
            if "FORMAT JSON" in query:
                return response.json()
            return {"success": True}
        else:
            print(f"Query error: {response.text[:200]}")
            return {"error": response.text}
    except Exception as e:
        print(f"Query exception: {e}")
        return {"error": str(e)}


async def insert_json(client: httpx.AsyncClient, table: str, rows: list) -> bool:
    """Insert rows as JSON."""
    if not rows:
        return True

    url = f"https://{CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}/"
    params = {
        "user": CLICKHOUSE_USER,
        "password": CLICKHOUSE_PASSWORD,
        "database": CLICKHOUSE_DATABASE,
        "query": f"INSERT INTO {table} FORMAT JSONEachRow",
    }

    data = "\n".join(json.dumps(row) for row in rows)

    try:
        response = await client.post(url, params=params, content=data, timeout=60.0)
        if response.status_code != 200:
            print(f"Insert error for {table}: {response.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"Insert exception for {table}: {e}")
        return False


def format_dt(dt: datetime) -> str:
    """Format datetime for ClickHouse."""
    return dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]


async def seed_metrics(client: httpx.AsyncClient, hours: int = 24):
    """Seed metrics data."""
    print(f"Seeding metrics for last {hours} hours...")

    metric_types = [
        ("system.cpu.usage", "%", 0, 100),
        ("system.cpu.user", "%", 0, 80),
        ("system.cpu.system", "%", 0, 30),
        ("system.memory.usage_percent", "%", 30, 95),
        ("system.memory.used_bytes", "bytes", 1e9, 16e9),
        ("system.disk.usage_percent", "%", 20, 90),
        ("system.disk.read_bytes", "bytes/s", 0, 100e6),
        ("system.disk.write_bytes", "bytes/s", 0, 50e6),
        ("system.network.bytes_recv", "bytes/s", 0, 500e6),
        ("system.network.bytes_sent", "bytes/s", 0, 200e6),
        ("system.load.1min", "", 0, 8),
        ("system.load.5min", "", 0, 6),
        ("process.count", "", 50, 500),
        ("container.cpu.usage", "%", 0, 100),
        ("container.memory.usage", "%", 10, 90),
    ]

    now = datetime.utcnow()
    rows = []

    for minutes_ago in range(hours * 60, 0, -1):  # Every minute
        timestamp = now - timedelta(minutes=minutes_ago)

        for host in HOSTS:
            for metric_name, unit, min_val, max_val in metric_types:
                # Add some variation based on time of day
                hour_factor = 1 + 0.3 * abs(12 - timestamp.hour) / 12
                base_value = min_val + (max_val - min_val) * 0.5 * hour_factor
                value = base_value + random.uniform(-0.2, 0.2) * (max_val - min_val)
                value = max(min_val, min(max_val, value))

                rows.append({
                    "timestamp": format_dt(timestamp),
                    "organization_id": ORG_ID,
                    "host_id": host["id"],
                    "name": metric_name,
                    "value": round(value, 2),
                    "unit": unit,
                    "tags": {"hostname": host["name"], "environment": "production"},
                })

        # Insert in batches
        if len(rows) >= 5000:
            await insert_json(client, "metrics", rows)
            rows = []

    if rows:
        await insert_json(client, "metrics", rows)

    print(f"  Seeded {hours * 60 * len(HOSTS) * len(metric_types)} metrics")


async def seed_logs(client: httpx.AsyncClient, hours: int = 24):
    """Seed log data."""
    print(f"Seeding logs for last {hours} hours...")

    log_templates = [
        ("INFO", "Request processed successfully", "api-gateway"),
        ("INFO", "User authenticated", "auth-service"),
        ("INFO", "Order created", "order-service"),
        ("INFO", "Payment processed", "payment-service"),
        ("INFO", "Notification sent", "notification-service"),
        ("INFO", "Cache hit for key", "cache-service"),
        ("DEBUG", "Database query executed in {duration}ms", "user-service"),
        ("DEBUG", "Redis connection established", "cache-service"),
        ("WARN", "High memory usage detected: {value}%", "monitoring"),
        ("WARN", "Slow query detected: {duration}ms", "order-service"),
        ("WARN", "Rate limit approaching for client", "api-gateway"),
        ("ERROR", "Failed to connect to database", "user-service"),
        ("ERROR", "Payment gateway timeout", "payment-service"),
        ("ERROR", "Invalid authentication token", "auth-service"),
        ("ERROR", "Inventory check failed", "inventory-service"),
    ]

    now = datetime.utcnow()
    rows = []

    for minutes_ago in range(hours * 60, 0, -1):
        timestamp = now - timedelta(minutes=minutes_ago)

        # Generate 5-20 logs per minute
        num_logs = random.randint(5, 20)
        for _ in range(num_logs):
            level, message_template, service = random.choice(log_templates)
            host = random.choice(HOSTS)

            # Fill in template variables
            message = message_template.format(
                duration=random.randint(10, 5000),
                value=random.randint(70, 99)
            )

            # Add some randomness to the timestamp within the minute
            ts = timestamp + timedelta(seconds=random.randint(0, 59))

            rows.append({
                "timestamp": format_dt(ts),
                "organization_id": ORG_ID,
                "host_id": host["id"],
                "level": level,
                "message": message,
                "service": service,
                "source": f"/var/log/{service}.log",
                "trace_id": str(uuid4()).replace("-", "")[:32] if random.random() > 0.7 else "",
                "span_id": str(uuid4()).replace("-", "")[:16] if random.random() > 0.7 else "",
                "fields": {
                    "hostname": host["name"],
                    "environment": "production",
                    "version": f"1.{random.randint(0, 9)}.{random.randint(0, 20)}",
                },
            })

        if len(rows) >= 5000:
            await insert_json(client, "logs", rows)
            rows = []

    if rows:
        await insert_json(client, "logs", rows)

    print(f"  Seeded logs")


async def seed_spans(client: httpx.AsyncClient, hours: int = 24):
    """Seed span/trace data."""
    print(f"Seeding spans for last {hours} hours...")

    operations = {
        "api-gateway": ["HTTP GET", "HTTP POST", "HTTP PUT", "HTTP DELETE", "route", "auth_check"],
        "user-service": ["get_user", "create_user", "update_user", "list_users", "validate_token"],
        "order-service": ["create_order", "get_order", "update_order", "cancel_order", "list_orders"],
        "payment-service": ["process_payment", "refund", "verify_card", "charge"],
        "inventory-service": ["check_stock", "reserve_items", "release_items", "update_stock"],
        "notification-service": ["send_email", "send_sms", "send_push", "queue_notification"],
        "auth-service": ["login", "logout", "refresh_token", "validate_session"],
        "analytics-service": ["track_event", "get_metrics", "aggregate_data"],
    }

    now = datetime.utcnow()
    rows = []

    for minutes_ago in range(hours * 60, 0, -1):
        base_time = now - timedelta(minutes=minutes_ago)

        # Generate 5-15 traces per minute
        num_traces = random.randint(5, 15)
        for _ in range(num_traces):
            trace_id = str(uuid4()).replace("-", "")[:32]

            # Root span (usually api-gateway)
            root_service = "api-gateway"
            root_span_id = str(uuid4()).replace("-", "")[:16]
            root_duration = random.randint(50, 1000)
            root_start = base_time + timedelta(seconds=random.randint(0, 59))
            is_error = random.random() < 0.03

            rows.append({
                "timestamp": format_dt(root_start),
                "organization_id": ORG_ID,
                "trace_id": trace_id,
                "span_id": root_span_id,
                "parent_span_id": "",
                "service_name": root_service,
                "operation_name": random.choice(operations[root_service]),
                "span_kind": "SERVER",
                "duration_ms": root_duration,
                "status_code": "ERROR" if is_error else "OK",
                "status_message": "Internal server error" if is_error else "",
                "attributes": {"http.method": "GET", "http.url": "/api/v1/resource"},
                "events": "[]",
                "links": "[]",
            })

            # Child spans (2-5 downstream calls)
            num_children = random.randint(2, 5)
            child_services = random.sample([s for s in SERVICES if s != root_service], min(num_children, len(SERVICES) - 1))

            offset_ms = 5
            for child_service in child_services:
                child_span_id = str(uuid4()).replace("-", "")[:16]
                child_duration = random.randint(10, root_duration // 2)
                child_start = root_start + timedelta(milliseconds=offset_ms)
                child_error = is_error and random.random() < 0.5

                rows.append({
                    "timestamp": format_dt(child_start),
                    "organization_id": ORG_ID,
                    "trace_id": trace_id,
                    "span_id": child_span_id,
                    "parent_span_id": root_span_id,
                    "service_name": child_service,
                    "operation_name": random.choice(operations[child_service]),
                    "span_kind": "CLIENT",
                    "duration_ms": child_duration,
                    "status_code": "ERROR" if child_error else "OK",
                    "status_message": "Service unavailable" if child_error else "",
                    "attributes": {"peer.service": child_service},
                    "events": "[]",
                    "links": "[]",
                })

                offset_ms += child_duration + random.randint(1, 10)

        if len(rows) >= 5000:
            await insert_json(client, "spans", rows)
            rows = []

    if rows:
        await insert_json(client, "spans", rows)

    print(f"  Seeded spans")


async def seed_rum_events(client: httpx.AsyncClient, hours: int = 24):
    """Seed RUM (Real User Monitoring) events."""
    print(f"Seeding RUM events for last {hours} hours...")

    pages = [
        "/", "/dashboard", "/settings", "/profile", "/orders", "/products",
        "/checkout", "/cart", "/search", "/login", "/signup", "/help"
    ]

    browsers = ["Chrome", "Firefox", "Safari", "Edge"]
    os_list = ["Windows", "macOS", "Linux", "iOS", "Android"]
    devices = ["desktop", "mobile", "tablet"]
    countries = ["US", "UK", "DE", "FR", "JP", "AU", "CA", "IN", "BR"]

    now = datetime.utcnow()
    rows = []

    for minutes_ago in range(hours * 60, 0, -1):
        base_time = now - timedelta(minutes=minutes_ago)

        # Generate 10-50 events per minute
        num_events = random.randint(10, 50)
        for _ in range(num_events):
            app = random.choice(RUM_APPS)
            session_id = str(uuid4())
            event_time = base_time + timedelta(seconds=random.randint(0, 59))

            # Determine event type
            event_type = random.choices(
                ["pageview", "error", "resource", "webvital"],
                weights=[0.6, 0.05, 0.25, 0.1]
            )[0]

            row = {
                "timestamp": format_dt(event_time),
                "organization_id": ORG_ID,
                "application_id": app["id"],
                "session_id": session_id,
                "event_type": event_type,
                "url": f"https://app.example.com{random.choice(pages)}",
                "user_id": f"user-{random.randint(1, 1000)}" if random.random() > 0.3 else "",
                "device_type": random.choice(devices),
                "browser": random.choice(browsers),
                "os": random.choice(os_list),
                "country": random.choice(countries),
                "duration_ms": random.randint(100, 5000) if event_type == "pageview" else 0,
                "lcp_ms": random.randint(500, 4000) if event_type in ["pageview", "webvital"] else 0,
                "fid_ms": random.randint(10, 300) if event_type in ["pageview", "webvital"] else 0,
                "cls_score": round(random.uniform(0, 0.5), 3) if event_type in ["pageview", "webvital"] else 0,
                "error_message": "Uncaught TypeError: Cannot read property 'x' of undefined" if event_type == "error" else "",
                "error_stack": "at Object.<anonymous> (app.js:123:45)" if event_type == "error" else "",
                "metadata": {"app_version": "2.1.0", "build": "1234"},
            }
            rows.append(row)

        if len(rows) >= 5000:
            await insert_json(client, "rum_events", rows)
            rows = []

    if rows:
        await insert_json(client, "rum_events", rows)

    print(f"  Seeded RUM events")


async def seed_network_flows(client: httpx.AsyncClient, hours: int = 24):
    """Seed network flow data."""
    print(f"Seeding network flows for last {hours} hours...")

    # First check if table exists with right schema
    check_query = "DESCRIBE TABLE network_flows FORMAT JSON"
    result = await execute_query(client, check_query)

    if "error" in result:
        print("  Creating network_flows table...")
        create_query = """
        CREATE TABLE IF NOT EXISTS network_flows (
            timestamp DateTime64(3),
            organization_id String,
            source_ip String,
            source_port UInt16,
            dest_ip String,
            dest_port UInt16,
            protocol String,
            bytes_sent UInt64,
            bytes_recv UInt64,
            packets_sent UInt32,
            packets_recv UInt32,
            duration_ms UInt32,
            status String,
            application String,
            source_host String,
            dest_host String,
            tags Map(String, String)
        ) ENGINE = MergeTree()
        ORDER BY (organization_id, timestamp, source_ip, dest_ip)
        PARTITION BY toYYYYMMDD(timestamp)
        """
        await execute_query(client, create_query)

    protocols = ["TCP", "UDP", "HTTP", "HTTPS", "gRPC"]
    applications = ["web", "api", "database", "cache", "queue", "monitoring"]
    statuses = ["established", "closed", "timeout", "reset"]

    external_ips = ["203.0.113.1", "198.51.100.50", "192.0.2.100", "203.0.113.200"]

    now = datetime.utcnow()
    rows = []

    for minutes_ago in range(hours * 60, 0, -5):  # Every 5 minutes
        base_time = now - timedelta(minutes=minutes_ago)

        # Internal traffic between hosts
        for _ in range(random.randint(20, 50)):
            src_host = random.choice(HOSTS)
            dst_host = random.choice([h for h in HOSTS if h["id"] != src_host["id"]])

            rows.append({
                "timestamp": format_dt(base_time + timedelta(seconds=random.randint(0, 299))),
                "organization_id": ORG_ID,
                "source_ip": src_host["ip"],
                "source_port": random.randint(30000, 60000),
                "dest_ip": dst_host["ip"],
                "dest_port": random.choice([80, 443, 3306, 5432, 6379, 8080, 9090]),
                "protocol": random.choice(protocols),
                "bytes_sent": random.randint(100, 1000000),
                "bytes_recv": random.randint(100, 5000000),
                "packets_sent": random.randint(10, 1000),
                "packets_recv": random.randint(10, 5000),
                "duration_ms": random.randint(1, 30000),
                "status": random.choice(statuses),
                "application": random.choice(applications),
                "source_host": src_host["name"],
                "dest_host": dst_host["name"],
                "tags": {"environment": "production", "datacenter": "us-east-1"},
            })

        # External traffic
        for _ in range(random.randint(5, 15)):
            host = random.choice(HOSTS)
            external_ip = random.choice(external_ips)
            is_inbound = random.random() > 0.5

            rows.append({
                "timestamp": format_dt(base_time + timedelta(seconds=random.randint(0, 299))),
                "organization_id": ORG_ID,
                "source_ip": external_ip if is_inbound else host["ip"],
                "source_port": random.randint(30000, 60000),
                "dest_ip": host["ip"] if is_inbound else external_ip,
                "dest_port": 443 if is_inbound else random.randint(30000, 60000),
                "protocol": "HTTPS",
                "bytes_sent": random.randint(1000, 100000),
                "bytes_recv": random.randint(1000, 500000),
                "packets_sent": random.randint(10, 500),
                "packets_recv": random.randint(10, 2000),
                "duration_ms": random.randint(10, 5000),
                "status": "established",
                "application": "web",
                "source_host": "" if is_inbound else host["name"],
                "dest_host": host["name"] if is_inbound else "",
                "tags": {"environment": "production", "traffic_type": "external"},
            })

        if len(rows) >= 3000:
            await insert_json(client, "network_flows", rows)
            rows = []

    if rows:
        await insert_json(client, "network_flows", rows)

    print(f"  Seeded network flows")


async def seed_profiles(client: httpx.AsyncClient, hours: int = 24):
    """Seed profiling data."""
    print(f"Seeding profiles for last {hours} hours...")

    # Check if table exists
    check_query = "DESCRIBE TABLE profiles FORMAT JSON"
    result = await execute_query(client, check_query)

    if "error" in result:
        print("  Creating profiles table...")
        create_query = """
        CREATE TABLE IF NOT EXISTS profiles (
            timestamp DateTime64(3),
            organization_id String,
            host_id String,
            service_name String,
            profile_type String,
            format String,
            start_time DateTime64(3),
            end_time DateTime64(3),
            duration_seconds Float32,
            sample_count UInt32,
            profile_size_bytes UInt32,
            trace_id String,
            span_id String,
            environment String,
            runtime String,
            runtime_version String,
            tags Map(String, String),
            top_functions Array(Tuple(String, Float32))
        ) ENGINE = MergeTree()
        ORDER BY (organization_id, timestamp, service_name, profile_type)
        PARTITION BY toYYYYMMDD(timestamp)
        """
        await execute_query(client, create_query)

    profile_types = ["cpu", "heap", "goroutine", "block", "mutex"]
    runtimes = [
        ("go", "1.21.5"),
        ("python", "3.11.4"),
        ("node", "20.10.0"),
        ("java", "21.0.1"),
    ]

    function_names = {
        "cpu": [
            ("runtime.gcBgMarkWorker", 15.2),
            ("net/http.(*conn).serve", 12.5),
            ("encoding/json.Marshal", 8.3),
            ("database/sql.(*DB).query", 7.1),
            ("main.handleRequest", 5.8),
            ("crypto/tls.(*Conn).Read", 4.2),
            ("runtime.mallocgc", 3.9),
        ],
        "heap": [
            ("bytes.makeSlice", 25.5),
            ("encoding/json.(*decodeState).object", 18.2),
            ("net/http.(*Transport).dialConn", 12.1),
            ("runtime.makeslice", 8.7),
            ("fmt.Sprintf", 6.3),
        ],
    }

    now = datetime.utcnow()
    rows = []

    for minutes_ago in range(hours * 60, 0, -15):  # Every 15 minutes
        base_time = now - timedelta(minutes=minutes_ago)

        for service in SERVICES:
            for profile_type in random.sample(profile_types, random.randint(1, 3)):
                host = random.choice(HOSTS)
                runtime, version = random.choice(runtimes)
                duration = random.randint(10, 60)

                top_funcs = function_names.get(profile_type, function_names["cpu"])
                funcs = [(f[0], round(f[1] + random.uniform(-2, 2), 1)) for f in top_funcs]

                rows.append({
                    "timestamp": format_dt(base_time),
                    "organization_id": ORG_ID,
                    "host_id": host["id"],
                    "service_name": service,
                    "profile_type": profile_type,
                    "format": "pprof",
                    "start_time": format_dt(base_time),
                    "end_time": format_dt(base_time + timedelta(seconds=duration)),
                    "duration_seconds": float(duration),
                    "sample_count": random.randint(1000, 50000),
                    "profile_size_bytes": random.randint(10000, 500000),
                    "trace_id": "",
                    "span_id": "",
                    "environment": "production",
                    "runtime": runtime,
                    "runtime_version": version,
                    "tags": {"version": f"1.{random.randint(0,9)}.0"},
                    "top_functions": funcs,
                })

        if len(rows) >= 1000:
            await insert_json(client, "profiles", rows)
            rows = []

    if rows:
        await insert_json(client, "profiles", rows)

    print(f"  Seeded profiles")


async def main():
    print("=" * 60)
    print("ClickHouse Demo Data Seeder")
    print("=" * 60)
    print(f"Organization ID: {ORG_ID}")
    print(f"ClickHouse: {CLICKHOUSE_HOST}")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        # Test connection
        result = await execute_query(client, "SELECT 1 FORMAT JSON")
        if "error" in result:
            print(f"Failed to connect to ClickHouse: {result['error']}")
            return
        print("Connected to ClickHouse successfully\n")

        # Seed all data types
        hours = 24  # Seed last 24 hours

        await seed_metrics(client, hours)
        await seed_logs(client, hours)
        await seed_spans(client, hours)
        await seed_rum_events(client, hours)
        await seed_network_flows(client, hours)
        await seed_profiles(client, hours)

        print("\n" + "=" * 60)
        print("Seeding complete! Verifying counts...")
        print("=" * 60)

        for table in ["metrics", "logs", "spans", "rum_events", "network_flows", "profiles"]:
            query = f"SELECT count() as cnt FROM {table} WHERE organization_id = '{ORG_ID}' FORMAT JSON"
            result = await execute_query(client, query)
            count = result.get("data", [{}])[0].get("cnt", 0) if "data" in result else "error"
            print(f"  {table}: {count} rows")


if __name__ == "__main__":
    asyncio.run(main())
