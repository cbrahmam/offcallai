# backend/app/middleware/self_monitoring.py
import time
import asyncio
from fastapi import Request
from datetime import datetime
import httpx
import psutil
import os
from app.core.config import settings

class SelfMonitoringMiddleware:
    """Monitor OffCallAI's own performance and create alerts"""
    
    def __init__(self, app):
        self.app = app
        self.alert_threshold = {
            'response_time': 2.0,
            'error_rate': 0.1,
            'memory_usage': 500
        }
        self.process = psutil.Process(os.getpid())
        # Use environment variable or fallback to localhost for dev
        self.webhook_url = f"{settings.API_URL}/api/v1/webhooks/generic"
    
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        
        request = Request(scope, receive)
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message['type'] == 'http.response.start':
                status_code = message['status']
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
            
            response_time = time.time() - start_time
            if response_time > self.alert_threshold['response_time']:
                asyncio.create_task(self.create_alert(
                    title=f"Slow response on {request.url.path}",
                    severity="warning",
                    metrics={"response_time": response_time},
                    service="offcallai-backend"
                ))
            
            # Memory check
            mem_info = self.process.memory_info()
            mem_mb = mem_info.rss / 1024 / 1024
            if mem_mb > self.alert_threshold['memory_usage']:
                asyncio.create_task(self.create_alert(
                    title=f"High memory usage detected",
                    severity="warning",
                    metrics={"memory_mb": mem_mb},
                    service="offcallai-backend"
                ))
            
        except Exception as e:
            asyncio.create_task(self.create_alert(
                title=f"Error on {request.url.path}: {str(e)}",
                severity="error",
                service="offcallai-backend"
            ))
            raise
    
    async def create_alert(self, title, severity, metrics={}, service="offcallai"):
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    self.webhook_url,
                    json={
                        "alert_id": f"self-monitor-{int(time.time())}",
                        "title": title,
                        "severity": severity,
                        "service": service,
                        "environment": "production",
                        "source": "self-monitoring",
                        "raw_data": {
                            "metrics": metrics,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    },
                    timeout=5.0
                )
        except Exception as e:
            print(f"Failed to send self-monitoring alert: {e}")