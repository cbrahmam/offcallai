# backend/tests/load/locustfile.py
"""
Load Testing for OffCall AI using Locust

Run with:
    locust -f tests/load/locustfile.py --host=http://localhost:8000

Or for local testing:
    locust -f tests/load/locustfile.py --host=http://localhost:8000

Web UI will be available at http://localhost:8089
"""

from locust import HttpUser, task, between, events
from locust.runners import MasterRunner
import json
import random
import string
import time
import logging

logger = logging.getLogger(__name__)


def random_string(length=10):
    """Generate a random string."""
    return ''.join(random.choices(string.ascii_lowercase, k=length))


def random_email():
    """Generate a random email."""
    return f"loadtest-{random_string(8)}@example.com"


class OffCallUser(HttpUser):
    """
    Simulates a typical OffCall AI user.

    User behavior:
    - Logs in
    - Views dashboard
    - Lists incidents
    - Views specific incidents
    - Creates incidents occasionally
    - Checks alerts
    """

    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks

    def on_start(self):
        """Called when user starts - login and get tokens."""
        self.access_token = None
        self.refresh_token = None
        self.user_id = None
        self.org_id = None

        # Try to login with test credentials
        # In a real load test, you'd have pre-created test accounts
        self.login()

    def login(self):
        """Login and store tokens."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "loadtest@example.com",
                "password": "LoadTest123!"
            },
            name="/api/v1/auth/login"
        )

        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            user = data.get("user", {})
            self.user_id = user.get("id")
            self.org_id = user.get("organization_id")
        else:
            # If login fails, we'll continue without auth for public endpoints
            logger.warning(f"Login failed: {response.status_code}")

    @property
    def auth_headers(self):
        """Get authorization headers."""
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    # === Public Endpoints ===

    @task(10)
    def health_check(self):
        """Check health endpoint - high frequency."""
        self.client.get("/health", name="/health")

    @task(5)
    def root_endpoint(self):
        """Check root endpoint."""
        self.client.get("/", name="/")

    # === Authenticated Endpoints ===

    @task(20)
    def list_incidents(self):
        """List incidents - most common operation."""
        if not self.access_token:
            return

        self.client.get(
            "/api/v1/incidents",
            headers=self.auth_headers,
            name="/api/v1/incidents"
        )

    @task(15)
    def list_incidents_with_filters(self):
        """List incidents with various filters."""
        if not self.access_token:
            return

        status = random.choice(["open", "acknowledged", "resolved", "closed"])
        severity = random.choice(["critical", "high", "medium", "low"])

        self.client.get(
            f"/api/v1/incidents?status={status}&severity={severity}",
            headers=self.auth_headers,
            name="/api/v1/incidents?status=X&severity=X"
        )

    @task(10)
    def get_incident_detail(self):
        """Get a specific incident."""
        if not self.access_token:
            return

        # First get list of incidents
        response = self.client.get(
            "/api/v1/incidents?limit=10",
            headers=self.auth_headers,
            name="/api/v1/incidents (for detail)"
        )

        if response.status_code == 200:
            incidents = response.json().get("incidents", [])
            if incidents:
                incident_id = random.choice(incidents)["id"]
                self.client.get(
                    f"/api/v1/incidents/{incident_id}",
                    headers=self.auth_headers,
                    name="/api/v1/incidents/{id}"
                )

    @task(8)
    def list_alerts(self):
        """List alerts."""
        if not self.access_token:
            return

        self.client.get(
            "/api/v1/alerts",
            headers=self.auth_headers,
            name="/api/v1/alerts"
        )

    @task(5)
    def get_user_info(self):
        """Get current user info."""
        if not self.access_token:
            return

        self.client.get(
            "/api/v1/auth/me",
            headers=self.auth_headers,
            name="/api/v1/auth/me"
        )

    @task(3)
    def list_hosts(self):
        """List hosts."""
        if not self.access_token:
            return

        self.client.get(
            "/api/v1/hosts",
            headers=self.auth_headers,
            name="/api/v1/hosts"
        )

    @task(2)
    def get_metrics(self):
        """Get metrics."""
        if not self.access_token:
            return

        self.client.get(
            "/api/v1/metrics?timeframe=1h",
            headers=self.auth_headers,
            name="/api/v1/metrics"
        )

    @task(1)
    def create_incident(self):
        """Create a new incident - less frequent."""
        if not self.access_token:
            return

        self.client.post(
            "/api/v1/incidents",
            headers=self.auth_headers,
            json={
                "title": f"Load Test Incident {random_string(6)}",
                "description": "This is a load test incident",
                "severity": random.choice(["low", "medium", "high"]),
                "source": "load_test"
            },
            name="/api/v1/incidents [POST]"
        )

    @task(2)
    def get_oncall_schedule(self):
        """Get on-call schedule."""
        if not self.access_token:
            return

        self.client.get(
            "/api/v1/oncall/current",
            headers=self.auth_headers,
            name="/api/v1/oncall/current"
        )


class WebhookUser(HttpUser):
    """
    Simulates external systems sending webhooks.

    This tests the webhook ingestion endpoints.
    """

    wait_time = between(0.5, 2)  # Faster than regular users

    # Test organization ID for load testing
    TEST_ORG_ID = "00000000-0000-0000-0000-000000000001"

    @task(10)
    def send_prometheus_alert(self):
        """Send Prometheus-style alert webhook."""
        self.client.post(
            "/api/v1/webhooks/prometheus",
            headers={"X-Organization-ID": self.TEST_ORG_ID},
            json={
                "status": random.choice(["firing", "resolved"]),
                "alerts": [
                    {
                        "status": "firing",
                        "fingerprint": f"fp-{random_string(8)}",
                        "labels": {
                            "alertname": f"LoadTestAlert{random.randint(1, 100)}",
                            "severity": random.choice(["critical", "warning"]),
                            "instance": f"server-{random.randint(1, 50)}",
                            "job": "load-test"
                        },
                        "annotations": {
                            "summary": "Load test alert",
                            "description": "This is a load test alert"
                        }
                    }
                ]
            },
            name="/api/v1/webhooks/prometheus"
        )

    @task(5)
    def send_datadog_alert(self):
        """Send Datadog-style alert webhook."""
        self.client.post(
            "/api/v1/webhooks/datadog",
            headers={"X-Organization-ID": self.TEST_ORG_ID},
            json={
                "id": str(random.randint(1000000, 9999999)),
                "title": f"Load Test Alert {random_string(6)}",
                "text": "Load test alert description",
                "priority": random.choice(["low", "normal", "critical"]),
                "alert_type": random.choice(["error", "warning", "info"]),
                "tags": ["env:load-test", "service:test"]
            },
            name="/api/v1/webhooks/datadog"
        )


class AgentUser(HttpUser):
    """
    Simulates OffCall agents sending metrics.

    This tests the metrics ingestion endpoints.
    """

    wait_time = between(10, 30)  # Agents send less frequently

    def on_start(self):
        """Initialize agent with API key."""
        self.agent_id = f"agent-{random_string(8)}"
        self.api_key = "load-test-api-key"  # Would be a real key in production

    @task
    def send_metrics(self):
        """Send metrics batch."""
        metrics = []
        for i in range(random.randint(5, 20)):
            metrics.append({
                "name": random.choice([
                    "system.cpu.usage",
                    "system.memory.used",
                    "system.disk.used",
                    "system.network.bytes_sent"
                ]),
                "value": random.uniform(0, 100),
                "timestamp": time.time(),
                "tags": {
                    "host": f"host-{random.randint(1, 100)}",
                    "agent_id": self.agent_id
                }
            })

        self.client.post(
            "/api/v1/metrics/ingest",
            headers={"X-API-Key": self.api_key},
            json={"metrics": metrics},
            name="/api/v1/metrics/ingest"
        )


# Event hooks for custom reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    logger.info("Load test starting...")
    if isinstance(environment.runner, MasterRunner):
        logger.info("Running in distributed mode")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    logger.info("Load test completed")

    # Log summary stats
    stats = environment.stats
    logger.info(f"Total requests: {stats.total.num_requests}")
    logger.info(f"Total failures: {stats.total.num_failures}")
    logger.info(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"Requests per second: {stats.total.current_rps:.2f}")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Called for each request - can be used for custom metrics."""
    if exception:
        logger.warning(f"Request failed: {name} - {exception}")
    elif response_time > 5000:  # Log slow requests (> 5 seconds)
        logger.warning(f"Slow request: {name} took {response_time}ms")
