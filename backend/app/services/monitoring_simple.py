"""Simple monitoring service for OffCall AI"""
import os
import logging

logger = logging.getLogger(__name__)

class MonitoringService:
    def __init__(self):
        self.datadog_enabled = bool(os.getenv("DD_API_KEY"))
        self.newrelic_enabled = bool(os.getenv("NEW_RELIC_LICENSE_KEY"))
        
        if self.datadog_enabled:
            logger.info("✅ Datadog integration ready")
        if self.newrelic_enabled:
            logger.info("✅ New Relic integration ready")
    
    def get_status(self):
        return {
            "datadog": self.datadog_enabled,
            "newrelic": self.newrelic_enabled,
            "status": "active"
        }

monitoring_service = MonitoringService()
