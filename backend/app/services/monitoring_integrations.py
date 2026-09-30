# backend/app/services/monitoring_integrations.py
"""
Monitoring integrations stub.

External monitoring tool integrations (Datadog, Grafana, CloudWatch, New Relic,
Prometheus, Azure Monitor) have been removed. This stub provides a compatible
interface that returns empty data so existing code continues to work.

For alert enrichment, the system now relies on internal metrics data only.
"""

from typing import Dict, List, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MonitoringIntegrationManager:
    """
    Stub for monitoring integrations.
    Returns empty data to maintain compatibility with existing code.
    """

    def __init__(self):
        logger.info("MonitoringIntegrationManager initialized (stub mode - external integrations removed)")

    async def fetch_enrichment_data(
        self,
        source: str,
        service: str,
        start_time: datetime,
        end_time: datetime,
        host: str = None,
        environment: str = None
    ) -> Dict[str, Any]:
        """
        Stub method that returns empty enrichment data.
        External monitoring integrations have been removed.
        """
        logger.debug(f"fetch_enrichment_data called for source={source}, service={service} (returning empty data)")

        return {
            "metrics": {},
            "logs": [],
            "traces": [],
            "dashboard_url": None,
            "logs_url": None,
            "traces_url": None
        }
