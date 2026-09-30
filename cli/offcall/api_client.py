"""
HTTP API client for OffCall CLI.
"""

import httpx
from typing import Optional, Dict, Any, List
from .config import Config


class APIError(Exception):
    """API error with status code and message."""

    def __init__(self, status_code: int, message: str, details: Dict = None):
        self.status_code = status_code
        self.message = message
        self.details = details or {}
        super().__init__(f"API Error {status_code}: {message}")


class APIClient:
    """HTTP client for OffCall API."""

    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.Client(
            base_url=config.api_url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "offcall-cli/1.0.0",
            },
            timeout=30.0,
        )

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle API response."""
        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("detail", str(error_data))
            except:
                message = response.text or f"HTTP {response.status_code}"
            raise APIError(response.status_code, message)

        if response.status_code == 204:
            return {}

        try:
            return response.json()
        except:
            return {"data": response.text}

    def get(self, path: str, params: Dict = None) -> Dict[str, Any]:
        """Make GET request."""
        response = self.client.get(path, params=params)
        return self._handle_response(response)

    def post(self, path: str, data: Dict = None) -> Dict[str, Any]:
        """Make POST request."""
        response = self.client.post(path, json=data)
        return self._handle_response(response)

    def patch(self, path: str, data: Dict = None) -> Dict[str, Any]:
        """Make PATCH request."""
        response = self.client.patch(path, json=data)
        return self._handle_response(response)

    def delete(self, path: str) -> Dict[str, Any]:
        """Make DELETE request."""
        response = self.client.delete(path)
        return self._handle_response(response)

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    # ========================================
    # Incidents
    # ========================================

    def list_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List incidents."""
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if severity:
            params["severity"] = severity
        return self.get("/incidents/", params=params)

    def get_incident(self, incident_id: str) -> Dict[str, Any]:
        """Get incident by ID."""
        return self.get(f"/incidents/{incident_id}")

    def acknowledge_incident(self, incident_id: str) -> Dict[str, Any]:
        """Acknowledge incident."""
        return self.post(f"/incidents/{incident_id}/acknowledge")

    def resolve_incident(self, incident_id: str) -> Dict[str, Any]:
        """Resolve incident."""
        return self.post(f"/incidents/{incident_id}/resolve")

    # ========================================
    # Alerts
    # ========================================

    def list_alerts(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List alerts."""
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if severity:
            params["severity"] = severity
        return self.get("/alerts/", params=params)

    def get_alert(self, alert_id: str) -> Dict[str, Any]:
        """Get alert by ID."""
        return self.get(f"/alerts/{alert_id}")

    def acknowledge_alert(self, alert_id: str) -> Dict[str, Any]:
        """Acknowledge alert."""
        return self.patch(f"/alerts/{alert_id}", {"status": "acknowledged"})

    # ========================================
    # On-Call
    # ========================================

    def get_current_oncall(self) -> Dict[str, Any]:
        """Get current on-call user."""
        return self.get("/on-call/current")

    def list_schedules(self) -> Dict[str, Any]:
        """List on-call schedules."""
        return self.get("/on-call/schedules/")

    def get_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Get schedule by ID."""
        return self.get(f"/on-call/schedules/{schedule_id}")

    # ========================================
    # Deployments
    # ========================================

    def notify_deployment(
        self,
        service_name: str,
        version: str,
        environment: str = "production",
        commit_sha: str = None,
        commit_message: str = None,
        deployed_by: str = None,
        repository: str = None,
        branch: str = None,
    ) -> Dict[str, Any]:
        """Notify about a deployment."""
        data = {
            "service_name": service_name,
            "version": version,
            "environment": environment,
        }
        if commit_sha:
            data["commit_sha"] = commit_sha
        if commit_message:
            data["commit_message"] = commit_message
        if deployed_by:
            data["deployed_by"] = deployed_by
        if repository:
            data["repository"] = repository
        if branch:
            data["branch"] = branch

        return self.post("/deployments/notify", data)

    def list_deployments(
        self,
        service_name: Optional[str] = None,
        environment: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """List deployments."""
        params = {"limit": limit}
        if service_name:
            params["service_name"] = service_name
        if environment:
            params["environment"] = environment
        return self.get("/deployments/", params=params)

    # ========================================
    # Hosts
    # ========================================

    def list_hosts(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List hosts."""
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        return self.get("/hosts/", params=params)

    def get_host(self, host_id: str) -> Dict[str, Any]:
        """Get host by ID."""
        return self.get(f"/hosts/{host_id}")

    def get_host_metrics(self, host_id: str, period: str = "1h") -> Dict[str, Any]:
        """Get host metrics."""
        return self.get(f"/hosts/{host_id}/metrics", {"period": period})

    # ========================================
    # Logs
    # ========================================

    def search_logs(
        self,
        query: Optional[str] = None,
        service: Optional[str] = None,
        level: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Search logs."""
        params = {"limit": limit}
        if query:
            params["query"] = query
        if service:
            params["service"] = service
        if level:
            params["level"] = level
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        return self.get("/logs/search", params=params)

    # ========================================
    # Services
    # ========================================

    def list_services(self) -> Dict[str, Any]:
        """List services."""
        return self.get("/services/")

    def get_service(self, service_id: str) -> Dict[str, Any]:
        """Get service by ID."""
        return self.get(f"/services/{service_id}")

    # ========================================
    # User / Auth
    # ========================================

    def get_current_user(self) -> Dict[str, Any]:
        """Get current user info."""
        return self.get("/users/me")

    def get_organization(self) -> Dict[str, Any]:
        """Get organization info."""
        return self.get("/organizations/current")
