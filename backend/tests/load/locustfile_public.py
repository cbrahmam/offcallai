"""
Load Testing for OffCall AI - Public Endpoints Only
"""

from locust import HttpUser, task, between, events
import logging
import random

logger = logging.getLogger(__name__)


class PublicEndpointUser(HttpUser):
    """Test only public endpoints that don't require auth or database"""

    wait_time = between(0.5, 2)

    @task(30)
    def health_check(self):
        """Main health check - most important endpoint"""
        self.client.get("/health", name="/health")

    @task(20)
    def root_endpoint(self):
        """Root endpoint"""
        self.client.get("/", name="/")

    @task(10)
    def webhook_health(self):
        """Webhook system health check"""
        self.client.get("/api/v1/webhooks/health", name="/api/v1/webhooks/health")

    @task(5)
    def api_docs(self):
        """OpenAPI docs endpoint"""
        self.client.get("/docs", name="/docs")

    @task(5)
    def openapi_json(self):
        """OpenAPI spec"""
        self.client.get("/openapi.json", name="/openapi.json")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logger.info("Public endpoint load test starting...")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats = environment.stats
    logger.info(f"Total requests: {stats.total.num_requests}")
    logger.info(f"Total failures: {stats.total.num_failures}")
    logger.info(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    logger.info(f"Requests per second: {stats.total.current_rps:.2f}")
