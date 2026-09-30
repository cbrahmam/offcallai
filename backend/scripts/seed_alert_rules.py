#!/usr/bin/env python3
"""
Seed standard alert rules for an organization.

Usage:
    python scripts/seed_alert_rules.py

This creates industry-standard monitoring alert rules.
"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_async_session, async_engine
from app.models.alert_rule import AlertRule
from app.models.organization import Organization
from uuid import UUID


# Standard Alert Rules
STANDARD_RULES = [
    # CPU Alerts
    {
        "name": "CPU Critical - Over 90%",
        "description": "Alert when CPU usage exceeds 90% for 5 minutes. Indicates potential resource exhaustion.",
        "metric_name": "system.cpu.usage",
        "operator": "gt",
        "threshold": 90.0,
        "aggregation": "avg",
        "evaluation_window": 300,
        "duration": 300,
        "severity": "critical",
        "auto_create_incident": True,
        "auto_resolve": True,
        "cooldown_seconds": 600,
        "notify_channels": ["slack", "email"],
        "labels": {"category": "infrastructure", "type": "cpu"},
    },
    {
        "name": "CPU Warning - Over 80%",
        "description": "Warning when CPU usage exceeds 80% for 10 minutes.",
        "metric_name": "system.cpu.usage",
        "operator": "gt",
        "threshold": 80.0,
        "aggregation": "avg",
        "evaluation_window": 600,
        "duration": 600,
        "severity": "warning",
        "auto_create_incident": False,
        "auto_resolve": True,
        "cooldown_seconds": 900,
        "notify_channels": ["slack"],
        "labels": {"category": "infrastructure", "type": "cpu"},
    },

    # Memory Alerts
    {
        "name": "Memory Critical - Over 90%",
        "description": "Alert when memory usage exceeds 90% for 5 minutes. Risk of OOM kills.",
        "metric_name": "system.memory.usage_percent",
        "operator": "gt",
        "threshold": 90.0,
        "aggregation": "avg",
        "evaluation_window": 300,
        "duration": 300,
        "severity": "critical",
        "auto_create_incident": True,
        "auto_resolve": True,
        "cooldown_seconds": 600,
        "notify_channels": ["slack", "email"],
        "labels": {"category": "infrastructure", "type": "memory"},
    },
    {
        "name": "Memory Warning - Over 80%",
        "description": "Warning when memory usage exceeds 80% for 10 minutes.",
        "metric_name": "system.memory.usage_percent",
        "operator": "gt",
        "threshold": 80.0,
        "aggregation": "avg",
        "evaluation_window": 600,
        "duration": 600,
        "severity": "warning",
        "auto_create_incident": False,
        "auto_resolve": True,
        "cooldown_seconds": 900,
        "notify_channels": ["slack"],
        "labels": {"category": "infrastructure", "type": "memory"},
    },

    # Disk Alerts
    {
        "name": "Disk Critical - Over 95%",
        "description": "Critical alert when disk usage exceeds 95%. Immediate action required.",
        "metric_name": "system.disk.usage_percent",
        "operator": "gt",
        "threshold": 95.0,
        "aggregation": "max",
        "evaluation_window": 60,
        "duration": 60,
        "severity": "critical",
        "auto_create_incident": True,
        "auto_resolve": True,
        "cooldown_seconds": 300,
        "notify_channels": ["slack", "email"],
        "labels": {"category": "infrastructure", "type": "disk"},
    },
    {
        "name": "Disk Warning - Over 85%",
        "description": "Warning when disk usage exceeds 85% for 5 minutes.",
        "metric_name": "system.disk.usage_percent",
        "operator": "gt",
        "threshold": 85.0,
        "aggregation": "max",
        "evaluation_window": 300,
        "duration": 300,
        "severity": "warning",
        "auto_create_incident": False,
        "auto_resolve": True,
        "cooldown_seconds": 900,
        "notify_channels": ["slack"],
        "labels": {"category": "infrastructure", "type": "disk"},
    },

    # Host Status
    {
        "name": "Host Down",
        "description": "Alert when a host stops reporting metrics for 2 minutes.",
        "metric_name": "host.heartbeat",
        "operator": "lt",
        "threshold": 1.0,
        "aggregation": "last",
        "evaluation_window": 120,
        "duration": 120,
        "severity": "critical",
        "auto_create_incident": True,
        "auto_resolve": True,
        "cooldown_seconds": 300,
        "notify_channels": ["slack", "email"],
        "labels": {"category": "infrastructure", "type": "availability"},
    },

    # Application Performance
    {
        "name": "High Error Rate - Over 5%",
        "description": "Alert when application error rate exceeds 5% for 3 minutes.",
        "metric_name": "http.error_rate",
        "operator": "gt",
        "threshold": 5.0,
        "aggregation": "avg",
        "evaluation_window": 180,
        "duration": 180,
        "severity": "critical",
        "auto_create_incident": True,
        "auto_resolve": True,
        "cooldown_seconds": 600,
        "notify_channels": ["slack", "email"],
        "labels": {"category": "application", "type": "errors"},
    },
    {
        "name": "High Latency P95 - Over 2s",
        "description": "Alert when 95th percentile latency exceeds 2 seconds for 5 minutes.",
        "metric_name": "http.latency_p95",
        "operator": "gt",
        "threshold": 2000.0,
        "aggregation": "avg",
        "evaluation_window": 300,
        "duration": 300,
        "severity": "warning",
        "auto_create_incident": False,
        "auto_resolve": True,
        "cooldown_seconds": 600,
        "notify_channels": ["slack"],
        "labels": {"category": "application", "type": "latency"},
    },

    # Database
    {
        "name": "Database Connections High - Over 80%",
        "description": "Alert when database connection pool usage exceeds 80%.",
        "metric_name": "database.connections_percent",
        "operator": "gt",
        "threshold": 80.0,
        "aggregation": "avg",
        "evaluation_window": 300,
        "duration": 300,
        "severity": "warning",
        "auto_create_incident": False,
        "auto_resolve": True,
        "cooldown_seconds": 600,
        "notify_channels": ["slack"],
        "labels": {"category": "database", "type": "connections"},
    },
    {
        "name": "Database Replication Lag - Over 30s",
        "description": "Alert when database replication lag exceeds 30 seconds.",
        "metric_name": "database.replication_lag_seconds",
        "operator": "gt",
        "threshold": 30.0,
        "aggregation": "max",
        "evaluation_window": 120,
        "duration": 120,
        "severity": "critical",
        "auto_create_incident": True,
        "auto_resolve": True,
        "cooldown_seconds": 300,
        "notify_channels": ["slack", "email"],
        "labels": {"category": "database", "type": "replication"},
    },
]


async def seed_alert_rules(organization_id: UUID = None):
    """Seed standard alert rules for an organization."""

    async with AsyncSession(async_engine) as db:
        # If no org specified, get the first one (for dev/test)
        if organization_id is None:
            result = await db.execute(select(Organization).limit(1))
            org = result.scalar_one_or_none()
            if not org:
                print("No organization found. Please create one first.")
                return
            organization_id = org.id
            print(f"Using organization: {org.name} ({org.id})")

        created_count = 0
        skipped_count = 0

        for rule_data in STANDARD_RULES:
            # Check if rule already exists (by name)
            existing = await db.execute(
                select(AlertRule).where(
                    AlertRule.organization_id == organization_id,
                    AlertRule.name == rule_data["name"]
                )
            )
            if existing.scalar_one_or_none():
                print(f"  [SKIP] {rule_data['name']} - already exists")
                skipped_count += 1
                continue

            # Create the rule
            rule = AlertRule(
                organization_id=organization_id,
                name=rule_data["name"],
                description=rule_data.get("description"),
                metric_name=rule_data["metric_name"],
                operator=rule_data["operator"],
                threshold=rule_data["threshold"],
                aggregation=rule_data.get("aggregation", "avg"),
                evaluation_window=rule_data.get("evaluation_window", 300),
                duration=rule_data.get("duration", 0),
                severity=rule_data["severity"],
                status="enabled",
                auto_create_incident=rule_data.get("auto_create_incident", True),
                auto_resolve=rule_data.get("auto_resolve", True),
                cooldown_seconds=rule_data.get("cooldown_seconds", 300),
                notify_channels=rule_data.get("notify_channels"),
                labels=rule_data.get("labels"),
            )

            db.add(rule)
            print(f"  [CREATE] {rule_data['name']} ({rule_data['severity']})")
            created_count += 1

        await db.commit()

        print(f"\n{'='*50}")
        print(f"Alert Rules Seeded:")
        print(f"  Created: {created_count}")
        print(f"  Skipped: {skipped_count}")
        print(f"  Total:   {len(STANDARD_RULES)}")


if __name__ == "__main__":
    print("Seeding Standard Alert Rules")
    print("=" * 50)
    asyncio.run(seed_alert_rules())
