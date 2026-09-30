# backend/app/services/incident_service.py - Incident Management Service
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from app.models.incident import Incident

class IncidentService:
    """Service for incident management operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_incident_from_webhook(
        self, 
        webhook_data: Dict[str, Any], 
        organization_id: str
    ) -> Incident:
        """Create incident from webhook payload"""
        
        # Extract incident data from webhook
        title = webhook_data.get("title", "Unknown Incident")
        description = webhook_data.get("description", "")
        severity = webhook_data.get("severity", "MEDIUM")
        source = webhook_data.get("source", "webhook")
        tags = webhook_data.get("tags", [])
        
        # Create incident object (mock implementation)
        incident = Incident(
            id=f"inc_{int(datetime.utcnow().timestamp())}",
            organization_id=organization_id,
            title=title,
            description=description,
            severity=severity,
            status="OPEN",
            source=source,
            tags=tags,
            created_at=datetime.utcnow()
        )
        
        return incident
    def create_incident(
        self, 
        incident_data, 
        user_id: Optional[str], 
        organization_id: str
    ):
        """Create a new incident - called by AlertService"""
        
        
        # Create the incident
        incident = Incident(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            title=incident_data.title,
            description=incident_data.description,
            severity=incident_data.severity,
            status="open",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Add to session but don't commit here - let AlertService handle it
        self.db.add(incident)
        
        return incident

    async def find_similar_incidents(
        self, 
        incident: Incident, 
        organization_id: str,
        limit: int = 5
    ) -> List[Incident]:
        """Find similar historical incidents for pattern analysis"""
        
        # Mock implementation - replace with actual similarity search
        similar_incidents = []
        
        # Simple keyword-based similarity
        keywords = self._extract_keywords(incident.title + " " + (incident.description or ""))
        
        # Would typically use vector similarity or keyword matching
        return similar_incidents
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from incident text"""
        import re
        words = re.findall(r'\w+', text.lower())
        # Filter out common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        keywords = [word for word in words if len(word) > 3 and word not in stop_words]
        return list(set(keywords))[:10]
    
    async def update_incident_status(
        self, 
        incident_id: str, 
        status: str, 
        organization_id: str
    ) -> bool:
        """Update incident status"""
        
        # Mock implementation
        return True
    
    async def get_incident_metrics(
        self, 
        organization_id: str, 
        days: int = 30
    ) -> Dict[str, Any]:
        """Get incident metrics for organization"""
        
        # Mock implementation
        return {
            "total_incidents": 45,
            "avg_resolution_time_minutes": 35,
            "mttr_reduction": "65%",
            "auto_resolved_percentage": 40,
            "top_incident_types": [
                {"type": "kubernetes_pod_failure", "count": 15},
                {"type": "database_performance", "count": 12},
                {"type": "memory_leak", "count": 8},
                {"type": "network_connectivity", "count": 6},
                {"type": "ssl_certificate", "count": 4}
            ],
            "severity_distribution": {
                "CRITICAL": 5,
                "HIGH": 18,
                "MEDIUM": 15,
                "LOW": 7
            }
        }
