#!/usr/bin/env python3
"""
Initialize ClickHouse schema for OffCall AI.
Run this script after setting up ClickHouse Cloud.

Usage:
    python scripts/init_clickhouse.py

Environment variables required:
    CLICKHOUSE_HOST - ClickHouse Cloud host (e.g., xxx.clickhouse.cloud)
    CLICKHOUSE_PASSWORD - ClickHouse password
    CLICKHOUSE_USER - ClickHouse user (default: default)
    CLICKHOUSE_DATABASE - Database name (default: offcall)
"""

import os
import sys
import httpx
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_clickhouse_config():
    """Get ClickHouse configuration from environment."""
    host = os.getenv('CLICKHOUSE_HOST')
    password = os.getenv('CLICKHOUSE_PASSWORD')
    user = os.getenv('CLICKHOUSE_USER', 'default')
    database = os.getenv('CLICKHOUSE_DATABASE', 'offcall')
    port = int(os.getenv('CLICKHOUSE_PORT', '8443'))
    use_ssl = os.getenv('CLICKHOUSE_USE_SSL', 'true').lower() == 'true'

    if not host:
        print("ERROR: CLICKHOUSE_HOST environment variable not set")
        print("\nSet it with:")
        print("  export CLICKHOUSE_HOST=your-host.clickhouse.cloud")
        sys.exit(1)

    if not password:
        print("ERROR: CLICKHOUSE_PASSWORD environment variable not set")
        print("\nSet it with:")
        print("  export CLICKHOUSE_PASSWORD=your-password")
        sys.exit(1)

    return {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'database': database,
        'use_ssl': use_ssl
    }


def execute_query(config: dict, query: str, database: str = None) -> str:
    """Execute a ClickHouse query via HTTP interface."""
    protocol = "https" if config['use_ssl'] else "http"
    url = f"{protocol}://{config['host']}:{config['port']}/"

    if database:
        url += f"?database={database}"

    try:
        response = httpx.post(
            url,
            content=query,
            auth=(config['user'], config['password']),
            timeout=30.0
        )
        response.raise_for_status()
        return response.text
    except httpx.HTTPStatusError as e:
        print(f"Query failed: {e.response.text}")
        raise
    except Exception as e:
        print(f"Connection error: {e}")
        raise


def init_schema(config: dict):
    """Initialize ClickHouse schema from SQL file."""
    schema_file = Path(__file__).parent.parent / 'clickhouse' / 'schema.sql'

    if not schema_file.exists():
        print(f"ERROR: Schema file not found: {schema_file}")
        sys.exit(1)

    print(f"Reading schema from: {schema_file}")

    with open(schema_file, 'r') as f:
        schema_sql = f.read()

    # Split by semicolons and filter out comments/empty statements
    statements = []
    current_statement = []

    for line in schema_sql.split('\n'):
        stripped = line.strip()

        # Skip empty lines and full-line comments
        if not stripped or stripped.startswith('--'):
            continue

        # Remove inline comments
        if '--' in line:
            line = line[:line.index('--')]

        current_statement.append(line)

        # Check if statement is complete
        if stripped.endswith(';'):
            statement = '\n'.join(current_statement)
            if statement.strip():
                statements.append(statement)
            current_statement = []

    print(f"Found {len(statements)} SQL statements to execute")

    # Execute each statement
    success_count = 0
    error_count = 0

    for i, statement in enumerate(statements, 1):
        # Get first line for display
        first_line = statement.strip().split('\n')[0][:60]
        print(f"\n[{i}/{len(statements)}] Executing: {first_line}...")

        try:
            result = execute_query(config, statement)
            print(f"   SUCCESS")
            success_count += 1
        except Exception as e:
            error_msg = str(e)
            # Ignore "already exists" errors
            if 'already exists' in error_msg.lower() or 'ALREADY_EXISTS' in error_msg:
                print(f"   SKIPPED (already exists)")
                success_count += 1
            else:
                print(f"   ERROR: {error_msg[:100]}")
                error_count += 1

    return success_count, error_count


def verify_tables(config: dict):
    """Verify that tables were created."""
    print("\n" + "=" * 60)
    print("VERIFYING TABLES")
    print("=" * 60)

    query = "SHOW TABLES FROM offcall FORMAT TabSeparated"

    try:
        result = execute_query(config, query, database='offcall')
        tables = [t.strip() for t in result.strip().split('\n') if t.strip()]

        print(f"\nTables in 'offcall' database:")
        for table in tables:
            print(f"  - {table}")

        expected_tables = [
            'metrics', 'logs', 'spans', 'service_metrics',
            'rum_events', 'network_flows', 'profiles'
        ]

        missing = [t for t in expected_tables if t not in tables]
        if missing:
            print(f"\n WARNING: Missing tables: {missing}")
        else:
            print(f"\n All {len(expected_tables)} expected tables present!")

        return len(tables)
    except Exception as e:
        print(f"Failed to verify tables: {e}")
        return 0


def main():
    print("=" * 60)
    print("ClickHouse Schema Initialization for OffCall AI")
    print("=" * 60)

    # Get configuration
    config = get_clickhouse_config()

    print(f"\nConfiguration:")
    print(f"  Host: {config['host']}")
    print(f"  Port: {config['port']}")
    print(f"  User: {config['user']}")
    print(f"  Database: {config['database']}")
    print(f"  SSL: {config['use_ssl']}")

    # Test connection
    print("\nTesting connection...")
    try:
        result = execute_query(config, "SELECT 1")
        print("Connection successful!")
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    # Initialize schema
    print("\n" + "=" * 60)
    print("INITIALIZING SCHEMA")
    print("=" * 60)

    success, errors = init_schema(config)

    # Verify tables
    table_count = verify_tables(config)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Statements executed: {success}")
    print(f"  Errors: {errors}")
    print(f"  Tables created: {table_count}")

    if errors > 0:
        print("\n Some statements failed. Check errors above.")
        sys.exit(1)
    else:
        print("\n Schema initialization complete!")
        print("\nNext steps:")
        print("  1. Set CLICKHOUSE_ENABLED=true in your environment")
        print("  2. Restart the backend to use ClickHouse")
        print("  3. Run the demo data seeder to populate sample data")


if __name__ == '__main__':
    main()
