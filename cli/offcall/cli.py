"""
OffCall CLI - Main Entry Point

Usage:
    offcall incidents list
    offcall incidents ack INCIDENT_ID
    offcall alerts list --severity=critical
    offcall oncall who
    offcall deploy notify --service=api --version=1.2.3
    offcall hosts list --status=inactive
    offcall logs search "error" --service=api --last=1h
"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_date
from typing import Optional

from .config import get_config, init_config, Config
from .api_client import APIClient, APIError

console = Console()


def get_client(profile: str = "default") -> APIClient:
    """Get configured API client."""
    config = get_config(profile)
    if not config.is_configured():
        console.print("[red]Not configured. Run 'offcall configure' first.[/red]")
        raise SystemExit(1)
    return APIClient(config)


def format_time(timestamp: str) -> str:
    """Format timestamp for display."""
    if not timestamp:
        return "-"
    try:
        dt = parse_date(timestamp)
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt

        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "just now"
    except:
        return timestamp


def severity_color(severity: str) -> str:
    """Get color for severity level."""
    colors = {
        "critical": "red",
        "high": "orange1",
        "medium": "yellow",
        "low": "blue",
        "info": "cyan",
    }
    return colors.get(severity.lower(), "white")


def status_color(status: str) -> str:
    """Get color for status."""
    colors = {
        "open": "red",
        "triggered": "red",
        "acknowledged": "yellow",
        "resolved": "green",
        "active": "green",
        "inactive": "gray",
        "firing": "red",
        "pending": "yellow",
    }
    return colors.get(status.lower(), "white")


@click.group()
@click.option("--profile", "-p", default="default", help="Configuration profile to use")
@click.pass_context
def main(ctx, profile):
    """OffCall AI Command Line Interface

    Manage incidents, alerts, deployments, and more from your terminal.

    Get started:
        offcall configure

    Examples:
        offcall incidents list
        offcall alerts list --severity=critical
        offcall oncall who
        offcall deploy notify --service=api --version=1.2.3
    """
    ctx.ensure_object(dict)
    ctx.obj["profile"] = profile


# ========================================
# Configure
# ========================================

@main.command()
@click.option("--api-key", prompt=True, hide_input=True, help="Your OffCall API key")
@click.option("--api-url", default=None, help="Custom API URL (optional)")
@click.pass_context
def configure(ctx, api_key, api_url):
    """Configure the CLI with your API credentials."""
    profile = ctx.obj.get("profile", "default")

    try:
        init_config(api_key, api_url, profile)
        console.print(f"[green]Configuration saved to profile '{profile}'[/green]")

        # Test connection
        config = get_config(profile)
        client = APIClient(config)
        user = client.get_current_user()
        console.print(f"[green]Connected as: {user.get('email', 'Unknown')}[/green]")
        client.close()

    except APIError as e:
        console.print(f"[red]Failed to verify credentials: {e.message}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@main.command()
@click.pass_context
def whoami(ctx):
    """Show current user and organization info."""
    try:
        client = get_client(ctx.obj.get("profile", "default"))
        user = client.get_current_user()

        table = Table(title="Current User", box=box.ROUNDED)
        table.add_column("Field", style="cyan")
        table.add_column("Value")

        table.add_row("Name", user.get("full_name", "-"))
        table.add_row("Email", user.get("email", "-"))
        table.add_row("Role", user.get("role", "-"))
        table.add_row("Organization", user.get("organization_name", "-"))

        console.print(table)
        client.close()

    except APIError as e:
        console.print(f"[red]Error: {e.message}[/red]")


# ========================================
# Incidents
# ========================================

@main.group()
def incidents():
    """Manage incidents."""
    pass


@incidents.command("list")
@click.option("--status", "-s", help="Filter by status (open, acknowledged, resolved)")
@click.option("--severity", help="Filter by severity (critical, high, medium, low)")
@click.option("--limit", "-n", default=20, help="Number of results")
@click.pass_context
def incidents_list(ctx, status, severity, limit):
    """List incidents."""
    try:
        client = get_client(ctx.obj.get("profile", "default"))
        result = client.list_incidents(status=status, severity=severity, limit=limit)
        incidents = result.get("incidents", result) if isinstance(result, dict) else result

        if not incidents:
            console.print("[yellow]No incidents found.[/yellow]")
            return

        table = Table(title="Incidents", box=box.ROUNDED)
        table.add_column("ID", style="dim")
        table.add_column("Title")
        table.add_column("Status")
        table.add_column("Severity")
        table.add_column("Created")

        for inc in incidents[:limit]:
            sev = inc.get("severity", "-")
            stat = inc.get("status", "-")
            table.add_row(
                inc.get("id", "-")[:8],
                inc.get("title", "-")[:50],
                f"[{status_color(stat)}]{stat}[/]",
                f"[{severity_color(sev)}]{sev}[/]",
                format_time(inc.get("created_at")),
            )

        console.print(table)
        client.close()

    except APIError as e:
        console.print(f"[red]Error: {e.message}[/red]")


@incidents.command("show")
@click.argument("incident_id")
@click.pass_context
def incidents_show(ctx, incident_id):
    """Show incident details."""
    try:
        client = get_client(ctx.obj.get("profile", "default"))
        inc = client.get_incident(incident_id)

        panel = Panel(
            f"""[bold]Title:[/bold] {inc.get('title', '-')}
[bold]Status:[/bold] [{status_color(inc.get('status', '-'))}]{inc.get('status', '-')}[/]
[bold]Severity:[/bold] [{severity_color(inc.get('severity', '-'))}]{inc.get('severity', '-')}[/]
[bold]Created:[/bold] {inc.get('created_at', '-')}
[bold]Description:[/bold]
{inc.get('description', '-')}""",
            title=f"Incident {incident_id[:8]}",
            box=box.ROUNDED,
        )
        console.print(panel)
        client.close()

    except APIError as e:
        console.print(f"[red]Error: {e.message}[/red]")


@incidents.command("ack")
@click.argument("incident_id")
@click.pass_context
def incidents_ack(ctx, incident_id):
    """Acknowledge an incident."""
    try:
        client = get_client(ctx.obj.get("profile", "default"))
        result = client.acknowledge_incident(incident_id)
        console.print(f"[green]Incident {incident_id[:8]} acknowledged.[/green]")
        client.close()

    except APIError as e:
        console.print(f"[red]Error: {e.message}[/red]")


@incidents.command("resolve")
@click.argument("incident_id")
@click.pass_context
def incidents_resolve(ctx, incident_id):
    """Resolve an incident."""
    try:
        client = get_client(ctx.obj.get("profile", "default"))
        result = client.resolve_incident(incident_id)
        console.print(f"[green]Incident {incident_id[:8]} resolved.[/green]")
        client.close()

    except APIError as e:
        console.print(f"[red]Error: {e.message}[/red]")


# ========================================
# Alerts
# ========================================

@main.group()
def alerts():
    """Manage alerts."""
    pass


@alerts.command("list")
@click.option("--status", "-s", help="Filter by status")
@click.option("--severity", help="Filter by severity")
@click.option("--limit", "-n", default=20, help="Number of results")
@click.pass_context
def alerts_list(ctx, status, severity, limit):
    """List alerts."""
    try:
        client = get_client(ctx.obj.get("profile", "default"))
        result = client.list_alerts(status=status, severity=severity, limit=limit)
        alerts = result.get("alerts", result) if isinstance(result, dict) else result

        if not alerts:
            console.print("[yellow]No alerts found.[/yellow]")
            return

        table = Table(title="Alerts", box=box.ROUNDED)
        table.add_column("ID", style="dim")
        table.add_column("Title")
        table.add_column("Status")
        table.add_column("Severity")
        table.add_column("Fired")

        for alert in alerts[:limit]:
            sev = alert.get("severity", "-")
            stat = alert.get("status", "-")
            table.add_row(
                alert.get("id", "-")[:8],
                alert.get("title", "-")[:50],
                f"[{status_color(stat)}]{stat}[/]",
                f"[{severity_color(sev)}]{sev}[/]",
                format_time(alert.get("fired_at")),
            )

        console.print(table)
        client.close()

    except APIError as e:
        console.print(f"[red]Error: {e.message}[/red]")


@alerts.command("ack")
@click.argument("alert_id")
@click.pass_context
def alerts_ack(ctx, alert_id):
    """Acknowledge an alert."""
    try:
        client = get_client(ctx.obj.get("profile", "default"))
        result = client.acknowledge_alert(alert_id)
        console.print(f"[green]Alert {alert_id[:8]} acknowledged.[/green]")
        client.close()

    except APIError as e:
        console.print(f"[red]Error: {e.message}[/red]")


# ========================================
# On-Call
# ========================================

@main.group()
def oncall():
    """On-call schedules and status."""
    pass


@oncall.command("who")
@click.pass_context
def oncall_who(ctx):
    """Show who is currently on-call."""
    try:
        client = get_client(ctx.obj.get("profile", "default"))
        result = client.get_current_oncall()

        if not result:
            console.print("[yellow]No one is currently on-call.[/yellow]")
            return

        user = result.get("user", result)
        schedule = result.get("schedule", {})

        panel = Panel(
            f"""[bold green]Currently On-Call[/bold green]

[bold]Name:[/bold] {user.get('full_name', user.get('name', '-'))}
[bold]Email:[/bold] {user.get('email', '-')}
[bold]Phone:[/bold] {user.get('phone', '-')}
[bold]Schedule:[/bold] {schedule.get('name', '-')}
[bold]Until:[/bold] {result.get('end_time', '-')}""",
            box=box.ROUNDED,
        )
        console.print(panel)
        client.close()

    except APIError as e:
        console.print(f"[red]Error: {e.message}[/red]")


@oncall.command("schedule")
@click.pass_context
def oncall_schedule(ctx):
    """List on-call schedules."""
    try:
        client = get_client(ctx.obj.get("profile", "default"))
        result = client.list_schedules()
        schedules = result.get("schedules", result) if isinstance(result, dict) else result

        if not schedules:
            console.print("[yellow]No schedules found.[/yellow]")
            return

        table = Table(title="On-Call Schedules", box=box.ROUNDED)
        table.add_column("ID", style="dim")
        table.add_column("Name")
        table.add_column("Timezone")
        table.add_column("Current On-Call")

        for sched in schedules:
            current = sched.get("current_oncall", {})
            table.add_row(
                sched.get("id", "-")[:8],
                sched.get("name", "-"),
                sched.get("timezone", "-"),
                current.get("full_name", "-") if current else "-",
            )

        console.print(table)
        client.close()

    except APIError as e:
        console.print(f"[red]Error: {e.message}[/red]")


# ========================================
# Deploy
# ========================================

@main.group()
def deploy():
    """Deployment notifications."""
    pass


@deploy.command("notify")
@click.option("--service", "-s", required=True, help="Service name")
@click.option("--version", "-v", required=True, help="Version/release")
@click.option("--environment", "-e", default="production", help="Environment")
@click.option("--commit", help="Commit SHA")
@click.option("--message", "-m", help="Commit message")
@click.option("--user", "-u", help="Deployed by (username or email)")
@click.option("--repo", help="Repository URL")
@click.option("--branch", "-b", help="Branch name")
@click.pass_context
def deploy_notify(ctx, service, version, environment, commit, message, user, repo, branch):
    """Notify about a deployment.

    Example:
        offcall deploy notify --service=api --version=1.2.3 --commit=abc123
    """
    try:
        client = get_client(ctx.obj.get("profile", "default"))
        result = client.notify_deployment(
            service_name=service,
            version=version,
            environment=environment,
            commit_sha=commit,
            commit_message=message,
            deployed_by=user,
            repository=repo,
            branch=branch,
        )

        console.print(f"[green]Deployment recorded:[/green]")
        console.print(f"  Service: {service}")
        console.print(f"  Version: {version}")
        console.print(f"  Environment: {environment}")
        if result.get("id"):
            console.print(f"  ID: {result['id'][:8]}")

        client.close()

    except APIError as e:
        console.print(f"[red]Error: {e.message}[/red]")


@deploy.command("list")
@click.option("--service", "-s", help="Filter by service")
@click.option("--environment", "-e", help="Filter by environment")
@click.option("--limit", "-n", default=20, help="Number of results")
@click.pass_context
def deploy_list(ctx, service, environment, limit):
    """List recent deployments."""
    try:
        client = get_client(ctx.obj.get("profile", "default"))
        result = client.list_deployments(service_name=service, environment=environment, limit=limit)
        deployments = result.get("deployments", result) if isinstance(result, dict) else result

        if not deployments:
            console.print("[yellow]No deployments found.[/yellow]")
            return

        table = Table(title="Deployments", box=box.ROUNDED)
        table.add_column("Service")
        table.add_column("Version")
        table.add_column("Env")
        table.add_column("Status")
        table.add_column("Deployed")

        for dep in deployments[:limit]:
            stat = dep.get("status", "-")
            table.add_row(
                dep.get("service_name", "-"),
                dep.get("version", "-"),
                dep.get("environment", "-"),
                f"[{status_color(stat)}]{stat}[/]",
                format_time(dep.get("deployed_at")),
            )

        console.print(table)
        client.close()

    except APIError as e:
        console.print(f"[red]Error: {e.message}[/red]")


# ========================================
# Hosts
# ========================================

@main.group()
def hosts():
    """Host infrastructure management."""
    pass


@hosts.command("list")
@click.option("--status", "-s", help="Filter by status (active, inactive)")
@click.option("--limit", "-n", default=50, help="Number of results")
@click.pass_context
def hosts_list(ctx, status, limit):
    """List hosts."""
    try:
        client = get_client(ctx.obj.get("profile", "default"))
        result = client.list_hosts(status=status, limit=limit)
        hosts = result.get("hosts", result) if isinstance(result, dict) else result

        if not hosts:
            console.print("[yellow]No hosts found.[/yellow]")
            return

        table = Table(title="Hosts", box=box.ROUNDED)
        table.add_column("Hostname")
        table.add_column("Status")
        table.add_column("OS")
        table.add_column("CPU")
        table.add_column("Memory")
        table.add_column("Last Seen")

        for host in hosts[:limit]:
            stat = host.get("status", "-")
            table.add_row(
                host.get("hostname", "-"),
                f"[{status_color(stat)}]{stat}[/]",
                host.get("os", "-"),
                f"{host.get('cpu_usage', 0):.1f}%",
                f"{host.get('memory_usage', 0):.1f}%",
                format_time(host.get("last_seen")),
            )

        console.print(table)
        client.close()

    except APIError as e:
        console.print(f"[red]Error: {e.message}[/red]")


@hosts.command("show")
@click.argument("host_id")
@click.pass_context
def hosts_show(ctx, host_id):
    """Show host details."""
    try:
        client = get_client(ctx.obj.get("profile", "default"))
        host = client.get_host(host_id)

        panel = Panel(
            f"""[bold]Hostname:[/bold] {host.get('hostname', '-')}
[bold]Status:[/bold] [{status_color(host.get('status', '-'))}]{host.get('status', '-')}[/]
[bold]OS:[/bold] {host.get('os', '-')}
[bold]IP:[/bold] {host.get('ip_address', '-')}
[bold]CPU:[/bold] {host.get('cpu_cores', '-')} cores ({host.get('cpu_usage', 0):.1f}% used)
[bold]Memory:[/bold] {host.get('memory_total_gb', '-')} GB ({host.get('memory_usage', 0):.1f}% used)
[bold]Disk:[/bold] {host.get('disk_total_gb', '-')} GB ({host.get('disk_usage', 0):.1f}% used)
[bold]Last Seen:[/bold] {host.get('last_seen', '-')}""",
            title=f"Host {host.get('hostname', host_id)}",
            box=box.ROUNDED,
        )
        console.print(panel)
        client.close()

    except APIError as e:
        console.print(f"[red]Error: {e.message}[/red]")


# ========================================
# Logs
# ========================================

@main.group()
def logs():
    """Log search and streaming."""
    pass


@logs.command("search")
@click.argument("query", default="")
@click.option("--service", "-s", help="Filter by service")
@click.option("--level", "-l", help="Filter by level (debug, info, warning, error)")
@click.option("--last", default="1h", help="Time range (e.g., 1h, 30m, 1d)")
@click.option("--limit", "-n", default=100, help="Number of results")
@click.pass_context
def logs_search(ctx, query, service, level, last, limit):
    """Search logs.

    Example:
        offcall logs search "error" --service=api --last=1h
    """
    try:
        # Parse time range
        now = datetime.utcnow()
        if last.endswith("m"):
            delta = timedelta(minutes=int(last[:-1]))
        elif last.endswith("h"):
            delta = timedelta(hours=int(last[:-1]))
        elif last.endswith("d"):
            delta = timedelta(days=int(last[:-1]))
        else:
            delta = timedelta(hours=1)

        start_time = (now - delta).isoformat() + "Z"

        client = get_client(ctx.obj.get("profile", "default"))
        result = client.search_logs(
            query=query if query else None,
            service=service,
            level=level,
            start_time=start_time,
            limit=limit,
        )
        logs = result.get("logs", result) if isinstance(result, dict) else result

        if not logs:
            console.print("[yellow]No logs found.[/yellow]")
            return

        for log in logs[:limit]:
            lvl = log.get("level", "info").upper()
            lvl_color = {
                "DEBUG": "dim",
                "INFO": "blue",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red bold",
            }.get(lvl, "white")

            timestamp = format_time(log.get("timestamp"))
            svc = log.get("service_name", "-")
            msg = log.get("message", "-")

            console.print(
                f"[dim]{timestamp}[/dim] [{lvl_color}]{lvl:8}[/] [cyan]{svc:15}[/cyan] {msg}"
            )

        client.close()

    except APIError as e:
        console.print(f"[red]Error: {e.message}[/red]")


# ========================================
# Services
# ========================================

@main.group()
def services():
    """Service catalog."""
    pass


@services.command("list")
@click.pass_context
def services_list(ctx):
    """List services."""
    try:
        client = get_client(ctx.obj.get("profile", "default"))
        result = client.list_services()
        services = result.get("services", result) if isinstance(result, dict) else result

        if not services:
            console.print("[yellow]No services found.[/yellow]")
            return

        table = Table(title="Services", box=box.ROUNDED)
        table.add_column("Name")
        table.add_column("Owner")
        table.add_column("Tier")
        table.add_column("Status")

        for svc in services:
            stat = svc.get("status", "-")
            table.add_row(
                svc.get("name", "-"),
                svc.get("owner_team", "-"),
                svc.get("tier", "-"),
                f"[{status_color(stat)}]{stat}[/]",
            )

        console.print(table)
        client.close()

    except APIError as e:
        console.print(f"[red]Error: {e.message}[/red]")


if __name__ == "__main__":
    main()
