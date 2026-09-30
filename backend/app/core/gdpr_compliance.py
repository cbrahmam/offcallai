# backend/app/core/gdpr_compliance.py
"""
GDPR Compliance System for OffCall AI
Implements data protection, privacy controls, and user rights management
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import secrets

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, text
from fastapi import HTTPException
import aiofiles

from app.database import get_async_session
from app.models.user import User
from app.models.organization import Organization

class DataCategory(Enum):
    """GDPR Data Categories"""
    PERSONAL_IDENTIFIABLE = "personal_identifiable"  # Name, email, phone
    TECHNICAL = "technical"  # IP addresses, device IDs, logs
    BEHAVIORAL = "behavioral"  # Usage patterns, preferences
    COMMUNICATION = "communication"  # Messages, incident comments
    SECURITY = "security"  # Authentication logs, access records

class ProcessingPurpose(Enum):
    """GDPR Processing Purposes"""
    SERVICE_PROVISION = "service_provision"  # Core platform functionality
    SECURITY = "security"  # Account security, fraud prevention
    ANALYTICS = "analytics"  # Usage analytics, performance monitoring
    COMMUNICATION = "communication"  # Service notifications, support
    LEGAL_COMPLIANCE = "legal_compliance"  # Regulatory requirements

class ConsentStatus(Enum):
    """User Consent Status"""
    GIVEN = "given"
    WITHDRAWN = "withdrawn"
    NOT_REQUIRED = "not_required"  # Legitimate interest basis
    PENDING = "pending"

@dataclass
class DataProcessingRecord:
    """Article 30 GDPR - Records of Processing Activities"""
    purpose: ProcessingPurpose
    data_categories: List[DataCategory]
    legal_basis: str
    data_subjects: str
    recipients: List[str]
    retention_period: str
    security_measures: List[str]
    cross_border_transfers: bool = False
    
class GDPRComplianceManager:
    """Main GDPR compliance manager"""
    
    def __init__(self):
        self.data_retention_policies = {
            DataCategory.PERSONAL_IDENTIFIABLE: timedelta(days=2555),  # 7 years
            DataCategory.TECHNICAL: timedelta(days=90),  # 3 months
            DataCategory.BEHAVIORAL: timedelta(days=365),  # 1 year
            DataCategory.COMMUNICATION: timedelta(days=1095),  # 3 years
            DataCategory.SECURITY: timedelta(days=2555),  # 7 years (legal requirement)
        }
    
    async def process_data_deletion_request(self, user_id: str, 
                                          db: AsyncSession) -> Dict[str, Any]:
        """Process Right to be Forgotten request (Article 17)"""
        
        deletion_report = {
            "user_id": user_id,
            "request_timestamp": datetime.utcnow().isoformat(),
            "status": "processing",
            "deleted_data": {},
            "retained_data": {},
            "anonymized_data": {}
        }
        
        try:
            # 1. Verify user exists and can be deleted
            user = await db.execute(select(User).where(User.id == user_id))
            user = user.scalar_one_or_none()
            
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # 2. Check for legal obligations to retain data
            legal_holds = await self._check_legal_holds(user_id, db)
            if legal_holds:
                deletion_report["status"] = "partial"
                deletion_report["legal_holds"] = legal_holds
            
            # 3. Delete personal data from all tables
            tables_to_clean = [
                ("users", "id", user_id),
                ("incidents", "created_by", user_id),
                ("audit_logs", "user_id", user_id),
                ("user_sessions", "user_id", user_id),
                ("mfa_secrets", "user_id", user_id),
                ("notification_preferences", "user_id", user_id)
            ]
            
            # SECURITY FIX: Whitelist allowed tables and columns to prevent SQL injection
            ALLOWED_TABLES = {
                "users": ["id"],
                "incidents": ["created_by"],
                "audit_logs": ["user_id"],
                "user_sessions": ["user_id"],
                "mfa_secrets": ["user_id"],
                "notification_preferences": ["user_id"]
            }

            for table, column, value in tables_to_clean:
                # Validate table and column are in whitelist
                if table not in ALLOWED_TABLES or column not in ALLOWED_TABLES[table]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid table/column combination: {table}.{column}"
                    )

                if table == "users":
                    # Complete user deletion
                    await db.execute(delete(User).where(User.id == user_id))
                    deletion_report["deleted_data"]["user_profile"] = "complete"
                elif table in ["incidents", "audit_logs"]:
                    # Anonymize instead of delete for business continuity
                    await self._anonymize_user_data(table, column, value, db)
                    deletion_report["anonymized_data"][table] = "anonymized"
                else:
                    # Delete supporting data - table/column already validated against whitelist
                    # Using parameterized query with validated identifiers
                    if table == "user_sessions" and column == "user_id":
                        await db.execute(text("DELETE FROM user_sessions WHERE user_id = :value"), {"value": value})
                    elif table == "mfa_secrets" and column == "user_id":
                        await db.execute(text("DELETE FROM mfa_secrets WHERE user_id = :value"), {"value": value})
                    elif table == "notification_preferences" and column == "user_id":
                        await db.execute(text("DELETE FROM notification_preferences WHERE user_id = :value"), {"value": value})
                    deletion_report["deleted_data"][table] = "deleted"
            
            # 4. Remove from Redis caches
            await self._clear_user_cache(user_id)
            
            # 5. Log the deletion for audit purposes
            await self._log_gdpr_action("data_deletion", user_id, deletion_report)
            
            deletion_report["status"] = "completed"
            deletion_report["completion_timestamp"] = datetime.utcnow().isoformat()
            
            await db.commit()
            return deletion_report
            
        except Exception as e:
            await db.rollback()
            deletion_report["status"] = "failed"
            deletion_report["error"] = str(e)
            raise HTTPException(status_code=500, detail=f"Data deletion failed: {str(e)}")
    
    async def process_data_portability_request(self, user_id: str, 
                                             db: AsyncSession) -> Dict[str, Any]:
        """Process Right to Data Portability request (Article 20)"""
        
        export_data = {
            "export_metadata": {
                "user_id": user_id,
                "export_timestamp": datetime.utcnow().isoformat(),
                "format": "JSON",
                "gdpr_article": "Article 20 - Right to Data Portability"
            },
            "personal_data": {},
            "activity_data": {},
            "preferences": {}
        }
        
        try:
            # 1. Export user profile data
            user = await db.execute(select(User).where(User.id == user_id))
            user = user.scalar_one_or_none()
            
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            export_data["personal_data"] = {
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "created_at": user.created_at.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "is_verified": user.is_verified
            }
            
            # 2. Export incident data (user created/participated in)
            incidents = await db.execute(
                text("""
                    SELECT id, title, description, severity, status, created_at, updated_at
                    FROM incidents 
                    WHERE created_by = :user_id OR assigned_to = :user_id
                    ORDER BY created_at DESC
                """), {"user_id": user_id}
            )
            
            export_data["activity_data"]["incidents"] = [
                {
                    "incident_id": row.id,
                    "title": row.title,
                    "description": row.description,
                    "severity": row.severity,
                    "status": row.status,
                    "created_at": row.created_at.isoformat(),
                    "updated_at": row.updated_at.isoformat()
                }
                for row in incidents.fetchall()
            ]
            
            # 3. Export audit logs (user's actions)
            audit_logs = await db.execute(
                text("""
                    SELECT action, resource_type, resource_id, timestamp, ip_address
                    FROM audit_logs 
                    WHERE user_id = :user_id
                    ORDER BY timestamp DESC
                    LIMIT 1000
                """), {"user_id": user_id}
            )
            
            export_data["activity_data"]["audit_logs"] = [
                {
                    "action": row.action,
                    "resource_type": row.resource_type,
                    "resource_id": row.resource_id,
                    "timestamp": row.timestamp.isoformat(),
                    "ip_address": row.ip_address
                }
                for row in audit_logs.fetchall()
            ]
            
            # 4. Export preferences and settings
            export_data["preferences"] = {
                "timezone": getattr(user, 'timezone', 'UTC'),
                "notification_preferences": await self._get_user_notification_preferences(user_id, db),
                "privacy_settings": await self._get_user_privacy_settings(user_id, db)
            }
            
            # 5. Log the export for audit purposes
            await self._log_gdpr_action("data_export", user_id, {"exported_records": len(export_data)})
            
            return export_data
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Data export failed: {str(e)}")
    
    async def manage_user_consent(self, user_id: str, purpose: ProcessingPurpose, 
                                 consent_given: bool, db: AsyncSession) -> Dict[str, Any]:
        """Manage user consent for data processing"""
        
        consent_record = {
            "user_id": user_id,
            "purpose": purpose.value,
            "consent_status": ConsentStatus.GIVEN.value if consent_given else ConsentStatus.WITHDRAWN.value,
            "timestamp": datetime.utcnow().isoformat(),
            "ip_address": None,  # Should be passed from request
            "user_agent": None   # Should be passed from request
        }
        
        try:
            # Store consent record
            await db.execute(
                text("""
                    INSERT INTO user_consents (user_id, purpose, consent_status, timestamp, metadata)
                    VALUES (:user_id, :purpose, :consent_status, :timestamp, :metadata)
                    ON CONFLICT (user_id, purpose) 
                    DO UPDATE SET 
                        consent_status = :consent_status,
                        timestamp = :timestamp,
                        metadata = :metadata
                """), {
                    "user_id": user_id,
                    "purpose": purpose.value,
                    "consent_status": consent_record["consent_status"],
                    "timestamp": datetime.utcnow(),
                    "metadata": json.dumps(consent_record)
                }
            )
            
            # If consent is withdrawn, stop processing for that purpose
            if not consent_given:
                await self._stop_data_processing(user_id, purpose, db)
            
            await db.commit()
            
            await self._log_gdpr_action("consent_update", user_id, consent_record)
            
            return consent_record
            
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Consent management failed: {str(e)}")
    
    async def generate_privacy_report(self, user_id: str, db: AsyncSession) -> Dict[str, Any]:
        """Generate comprehensive privacy report for user"""
        
        report = {
            "user_id": user_id,
            "report_timestamp": datetime.utcnow().isoformat(),
            "data_categories": {},
            "processing_purposes": {},
            "consent_status": {},
            "retention_schedule": {},
            "data_sharing": {}
        }
        
        try:
            # 1. Analyze data categories stored
            for category in DataCategory:
                data_count = await self._count_user_data_by_category(user_id, category, db)
                report["data_categories"][category.value] = {
                    "records_count": data_count,
                    "retention_period": str(self.data_retention_policies.get(category, "indefinite")),
                    "legal_basis": self._get_legal_basis_for_category(category)
                }
            
            # 2. Processing purposes analysis
            for purpose in ProcessingPurpose:
                consent_status = await self._get_consent_status(user_id, purpose, db)
                report["processing_purposes"][purpose.value] = {
                    "consent_required": purpose in [ProcessingPurpose.ANALYTICS, ProcessingPurpose.COMMUNICATION],
                    "consent_status": consent_status,
                    "legal_basis": self._get_legal_basis_for_purpose(purpose)
                }
            
            # 3. Data sharing information
            report["data_sharing"] = {
                # Self-hosted deployments should list their own processors here.
                "third_party_processors": [],
                "data_transfers": await self._get_data_transfer_log(user_id, db)
            }
            
            return report
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Privacy report generation failed: {str(e)}")
    
    async def handle_data_breach_notification(self, breach_details: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data breach notification (Article 33 & 34)"""
        
        breach_record = {
            "breach_id": secrets.token_urlsafe(16),
            "timestamp": datetime.utcnow().isoformat(),
            "detection_timestamp": breach_details.get("detection_timestamp"),
            "breach_type": breach_details.get("breach_type"),
            "affected_data_categories": breach_details.get("affected_data_categories", []),
            "affected_users_count": breach_details.get("affected_users_count", 0),
            "severity": breach_details.get("severity", "medium"),
            "containment_status": "in_progress",
            "notification_status": {
                "dpa_notified": False,
                "users_notified": False,
                "notification_deadline": (datetime.utcnow() + timedelta(hours=72)).isoformat()
            }
        }
        
        try:
            # 1. Store breach record
            async with aiofiles.open(f"breach_records/{breach_record['breach_id']}.json", "w") as f:
                await f.write(json.dumps(breach_record, indent=2))
            
            # 2. Assess if DPA notification required (within 72 hours)
            if self._requires_dpa_notification(breach_record):
                await self._schedule_dpa_notification(breach_record)
            
            # 3. Assess if user notification required
            if self._requires_user_notification(breach_record):
                await self._schedule_user_notifications(breach_record)
            
            # 4. Log security event
            await self._log_gdpr_action("data_breach", None, breach_record)
            
            return breach_record
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Breach notification handling failed: {str(e)}")
    
    # Helper methods
    async def _check_legal_holds(self, user_id: str, db: AsyncSession) -> List[str]:
        """Check if user data is subject to legal holds"""
        # Check for ongoing investigations, legal proceedings, etc.
        legal_holds = []
        
        # Example: Check if user has unresolved incidents
        active_incidents = await db.execute(
            text("SELECT COUNT(*) FROM incidents WHERE created_by = :user_id AND status != 'resolved'"),
            {"user_id": user_id}
        )
        
        if active_incidents.scalar() > 0:
            legal_holds.append("Active incidents require data retention")
        
        return legal_holds
    
    async def _anonymize_user_data(self, table: str, column: str, user_id: str, db: AsyncSession):
        """Anonymize user data instead of deletion"""
        anonymous_id = f"anonymous_{hashlib.sha256(user_id.encode()).hexdigest()[:8]}"

        # SECURITY FIX: Use explicit queries per table to prevent SQL injection
        # Only allowed tables can be anonymized
        ALLOWED_ANONYMIZE = {
            ("incidents", "created_by"),
            ("audit_logs", "user_id"),
        }

        if (table, column) not in ALLOWED_ANONYMIZE:
            raise ValueError(f"Anonymization not allowed for {table}.{column}")

        # Execute specific parameterized queries based on validated table/column
        if table == "incidents" and column == "created_by":
            await db.execute(
                text("UPDATE incidents SET created_by = :anonymous_id WHERE created_by = :user_id"),
                {"anonymous_id": anonymous_id, "user_id": user_id}
            )
        elif table == "audit_logs" and column == "user_id":
            await db.execute(
                text("UPDATE audit_logs SET user_id = :anonymous_id WHERE user_id = :user_id"),
                {"anonymous_id": anonymous_id, "user_id": user_id}
            )
    
    async def _clear_user_cache(self, user_id: str):
        """Clear user data from Redis caches"""
        from app.database import get_redis
        redis = get_redis()
        
        # Clear various cache keys
        cache_patterns = [
            f"user:{user_id}:*",
            f"session:{user_id}:*",
            f"mfa:{user_id}:*",
            f"rate_limit:user:{user_id}"
        ]
        
        for pattern in cache_patterns:
            keys = await redis.keys(pattern)
            if keys:
                await redis.delete(*keys)
    
    async def _log_gdpr_action(self, action: str, user_id: Optional[str], details: Dict[str, Any]):
        """Log GDPR-related actions for audit trail"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user_id": user_id,
            "details": details,
            "gdpr_compliance": True
        }
        
        # Store in audit system
        async with aiofiles.open("gdpr_audit.log", "a") as f:
            await f.write(json.dumps(log_entry) + "\n")
    
    def _get_legal_basis_for_category(self, category: DataCategory) -> str:
        """Get legal basis for processing each data category"""
        legal_bases = {
            DataCategory.PERSONAL_IDENTIFIABLE: "Contract performance (Art. 6(1)(b))",
            DataCategory.TECHNICAL: "Legitimate interest (Art. 6(1)(f))",
            DataCategory.BEHAVIORAL: "Consent (Art. 6(1)(a))",
            DataCategory.COMMUNICATION: "Consent (Art. 6(1)(a))",
            DataCategory.SECURITY: "Legitimate interest (Art. 6(1)(f))"
        }
        return legal_bases.get(category, "Not specified")
    
    def _requires_dpa_notification(self, breach_record: Dict) -> bool:
        """Determine if Data Protection Authority notification is required"""
        # High-risk breaches always require notification
        if breach_record.get("severity") in ["high", "critical"]:
            return True
        
        # Personal data breaches with potential harm
        sensitive_categories = [
            DataCategory.PERSONAL_IDENTIFIABLE.value,
            DataCategory.SECURITY.value
        ]
        
        return any(cat in breach_record.get("affected_data_categories", []) for cat in sensitive_categories)

# Initialize GDPR compliance manager
gdpr_manager = GDPRComplianceManager()

# Database migration for GDPR tables
GDPR_TABLES_SQL = """
-- User consent management
CREATE TABLE IF NOT EXISTS user_consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose VARCHAR(50) NOT NULL,
    consent_status VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    UNIQUE(user_id, purpose)
);

-- Data processing records (Article 30)
CREATE TABLE IF NOT EXISTS data_processing_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    purpose VARCHAR(50) NOT NULL,
    data_categories TEXT[] NOT NULL,
    legal_basis TEXT NOT NULL,
    retention_period INTERVAL NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Privacy settings
CREATE TABLE IF NOT EXISTS user_privacy_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    analytics_consent BOOLEAN DEFAULT FALSE,
    marketing_consent BOOLEAN DEFAULT FALSE,
    third_party_sharing BOOLEAN DEFAULT FALSE,
    data_retention_preference INTERVAL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_consents_user_id ON user_consents(user_id);
CREATE INDEX IF NOT EXISTS idx_user_privacy_settings_user_id ON user_privacy_settings(user_id);
"""