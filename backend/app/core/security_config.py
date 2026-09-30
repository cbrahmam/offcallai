# backend/app/core/security_config.py
"""
Enhanced security configuration for OffCall AI
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class SecuritySettings(BaseSettings):
    """Security-specific settings"""
    
    # JWT Security
    SECRET_KEY: str = Field(..., description="JWT signing secret key")
    ALGORITHM: str = Field(default="RS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, description="Access token expiration")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30, description="Refresh token expiration")
    JWT_KEY_ID: str = Field(default="offcall-ai-key-1", description="JWT key identifier")
    
    # Encryption
    ENCRYPTION_KEY: str = Field(..., description="Data encryption key")
    
    # Rate Limiting
    REDIS_URL: str = Field(default="redis://localhost:6379", description="Redis URL for caching")
    GLOBAL_RATE_LIMIT: int = Field(default=1000, description="Global requests per minute")
    USER_RATE_LIMIT: int = Field(default=100, description="User requests per minute")
    LOGIN_RATE_LIMIT: int = Field(default=5, description="Login attempts per minute")
    
    # Security Headers
    ALLOWED_HOSTS: List[str] = Field(default=["localhost", "127.0.0.1"])
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"])
    
    # OAuth2 Settings
    GOOGLE_CLIENT_ID: Optional[str] = Field(default=None, description="Google OAuth2 client ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = Field(default=None, description="Google OAuth2 client secret")
    MICROSOFT_CLIENT_ID: Optional[str] = Field(default=None, description="Microsoft OAuth2 client ID") 
    MICROSOFT_CLIENT_SECRET: Optional[str] = Field(default=None, description="Microsoft OAuth2 client secret")
    GITHUB_CLIENT_ID: Optional[str] = Field(default=None, description="GitHub OAuth2 client ID")
    GITHUB_CLIENT_SECRET: Optional[str] = Field(default=None, description="GitHub OAuth2 client secret")
    
    # Security Monitoring
    SECURITY_EMAIL: str = Field(default="", description="Security alerts email")
    SLACK_SECURITY_WEBHOOK: Optional[str] = Field(default=None, description="Slack webhook for security alerts")
    
    # GDPR Compliance
    DATA_RETENTION_DAYS: int = Field(default=2555, description="Default data retention period (7 years)")
    ANONYMIZATION_ENABLED: bool = Field(default=True, description="Enable data anonymization")
    
    # Session Security
    SESSION_COOKIE_SECURE: bool = Field(default=True, description="Secure cookie flag")
    SESSION_COOKIE_HTTPONLY: bool = Field(default=True, description="HttpOnly cookie flag")
    SESSION_COOKIE_SAMESITE: str = Field(default="strict", description="SameSite cookie attribute")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Alembic migration for security tables
# backend/alembic/versions/security_tables.py

"""Add security and GDPR compliance tables

Revision ID: security_001
Revises: previous_revision
Create Date: 2025-01-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'security_001'
down_revision = 'previous_revision'  # Replace with actual previous revision
branch_labels = None
depends_on = None

def upgrade():
    """Create security and GDPR compliance tables"""
    
    # User consent management table
    op.create_table(
        'user_consents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('purpose', sa.String(50), nullable=False),
        sa.Column('consent_status', sa.String(20), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), server_default=sa.func.current_timestamp()),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.Text),
        sa.Column('metadata', postgresql.JSONB),
        sa.UniqueConstraint('user_id', 'purpose', name='unique_user_purpose_consent')
    )
    
    # Privacy settings table
    op.create_table(
        'user_privacy_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('analytics_consent', sa.Boolean, default=False),
        sa.Column('marketing_consent', sa.Boolean, default=False),
        sa.Column('third_party_sharing', sa.Boolean, default=False),
        sa.Column('data_retention_preference', sa.Interval),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp())
    )
    
    # Security events table
    op.create_table(
        'security_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.Text),
        sa.Column('risk_level', sa.String(20), nullable=False),
        sa.Column('details', postgresql.JSONB),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), server_default=sa.func.current_timestamp()),
        sa.Column('resolved', sa.Boolean, default=False),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'))
    )
    
    # Rate limiting tracking table
    op.create_table(
        'rate_limit_violations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('identifier', sa.String(255), nullable=False),  # IP, user_id, etc.
        sa.Column('identifier_type', sa.String(50), nullable=False),  # 'ip', 'user', 'api_key'
        sa.Column('endpoint', sa.String(255)),
        sa.Column('limit_type', sa.String(50)),
        sa.Column('requests_count', sa.Integer),
        sa.Column('limit_exceeded', sa.Integer),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), server_default=sa.func.current_timestamp()),
        sa.Column('blocked_duration', sa.Interval),
        sa.Column('user_agent', sa.Text)
    )
    
    # MFA secrets table (encrypted)
    op.create_table(
        'mfa_secrets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('encrypted_secret', sa.Text, nullable=False),
        sa.Column('backup_codes', postgresql.JSONB),  # Encrypted backup codes
        sa.Column('enabled', sa.Boolean, default=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.current_timestamp()),
        sa.Column('last_used', sa.TIMESTAMP(timezone=True))
    )
    
    # User sessions tracking
    op.create_table(
        'user_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_token', sa.String(255), nullable=False, unique=True),
        sa.Column('device_fingerprint', sa.String(64)),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.Text),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.current_timestamp()),
        sa.Column('last_activity', sa.TIMESTAMP(timezone=True), server_default=sa.func.current_timestamp()),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True)
    )
    
    # OAuth2 provider accounts
    op.create_table(
        'oauth_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),  # 'google', 'microsoft', 'github'
        sa.Column('provider_user_id', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255)),
        sa.Column('name', sa.String(255)),
        sa.Column('avatar_url', sa.String(500)),
        sa.Column('access_token', sa.Text),  # Encrypted
        sa.Column('refresh_token', sa.Text),  # Encrypted
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint('provider', 'provider_user_id', name='unique_provider_user')
    )
    
    # Data processing records (GDPR Article 30)
    op.create_table(
        'data_processing_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('purpose', sa.String(100), nullable=False),
        sa.Column('data_categories', postgresql.ARRAY(sa.String(50)), nullable=False),
        sa.Column('legal_basis', sa.Text, nullable=False),
        sa.Column('data_subjects', sa.Text, nullable=False),
        sa.Column('recipients', postgresql.ARRAY(sa.String(100))),
        sa.Column('retention_period', sa.Interval, nullable=False),
        sa.Column('security_measures', postgresql.ARRAY(sa.Text)),
        sa.Column('cross_border_transfers', sa.Boolean, default=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.current_timestamp())
    )
    
    # GDPR requests tracking
    op.create_table(
        'gdpr_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('request_type', sa.String(50), nullable=False),  # 'deletion', 'portability', 'rectification'
        sa.Column('status', sa.String(20), nullable=False, default='pending'),  # 'pending', 'processing', 'completed', 'failed'
        sa.Column('requested_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.current_timestamp()),
        sa.Column('processed_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('request_details', postgresql.JSONB),
        sa.Column('processing_log', postgresql.JSONB),
        sa.Column('verification_token', sa.String(255)),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.Text)
    )
    
    # Create indexes for performance
    op.create_index('idx_user_consents_user_id', 'user_consents', ['user_id'])
    op.create_index('idx_user_consents_purpose', 'user_consents', ['purpose'])
    op.create_index('idx_security_events_user_id', 'security_events', ['user_id'])
    op.create_index('idx_security_events_timestamp', 'security_events', ['timestamp'])
    op.create_index('idx_security_events_risk_level', 'security_events', ['risk_level'])
    op.create_index('idx_security_events_event_type', 'security_events', ['event_type'])
    op.create_index('idx_rate_limit_violations_identifier', 'rate_limit_violations', ['identifier'])
    op.create_index('idx_rate_limit_violations_timestamp', 'rate_limit_violations', ['timestamp'])
    op.create_index('idx_user_sessions_user_id', 'user_sessions', ['user_id'])
    op.create_index('idx_user_sessions_token', 'user_sessions', ['session_token'])
    op.create_index('idx_user_sessions_active', 'user_sessions', ['is_active'])
    op.create_index('idx_oauth_accounts_user_id', 'oauth_accounts', ['user_id'])
    op.create_index('idx_oauth_accounts_provider', 'oauth_accounts', ['provider'])
    op.create_index('idx_gdpr_requests_user_id', 'gdpr_requests', ['user_id'])
    op.create_index('idx_gdpr_requests_status', 'gdpr_requests', ['status'])
    op.create_index('idx_gdpr_requests_type', 'gdpr_requests', ['request_type'])
    
    # Add MFA enabled column to users table
    op.add_column('users', sa.Column('mfa_enabled', sa.Boolean, default=False))
    op.add_column('users', sa.Column('last_password_change', sa.TIMESTAMP(timezone=True)))
    op.add_column('users', sa.Column('failed_login_attempts', sa.Integer, default=0))
    op.add_column('users', sa.Column('account_locked_until', sa.TIMESTAMP(timezone=True)))
    op.add_column('users', sa.Column('password_reset_token', sa.String(255)))
    op.add_column('users', sa.Column('password_reset_expires', sa.TIMESTAMP(timezone=True)))
    op.add_column('users', sa.Column('email_verification_token', sa.String(255)))
    op.add_column('users', sa.Column('email_verified_at', sa.TIMESTAMP(timezone=True)))
    
    # Update audit_logs table for enhanced security logging
    op.add_column('audit_logs', sa.Column('session_id', sa.String(255)))
    op.add_column('audit_logs', sa.Column('device_fingerprint', sa.String(64)))
    op.add_column('audit_logs', sa.Column('risk_score', sa.Integer))
    op.add_column('audit_logs', sa.Column('security_event_id', postgresql.UUID(as_uuid=True)))

def downgrade():
    """Remove security and GDPR compliance tables"""
    
    # Remove added columns from existing tables
    op.drop_column('users', 'mfa_enabled')
    op.drop_column('users', 'last_password_change')
    op.drop_column('users', 'failed_login_attempts')
    op.drop_column('users', 'account_locked_until')
    op.drop_column('users', 'password_reset_token')
    op.drop_column('users', 'password_reset_expires')
    op.drop_column('users', 'email_verification_token')
    op.drop_column('users', 'email_verified_at')
    
    op.drop_column('audit_logs', 'session_id')
    op.drop_column('audit_logs', 'device_fingerprint')
    op.drop_column('audit_logs', 'risk_score')
    op.drop_column('audit_logs', 'security_event_id')
    
    # Drop tables in reverse order
    op.drop_table('gdpr_requests')
    op.drop_table('data_processing_records')
    op.drop_table('oauth_accounts')
    op.drop_table('user_sessions')
    op.drop_table('mfa_secrets')
    op.drop_table('rate_limit_violations')
    op.drop_table('security_events')
    op.drop_table('user_privacy_settings')
    op.drop_table('user_consents')

# Security initialization script
# backend/scripts/init_security.py

"""
Security initialization script for OffCall AI
Sets up initial security configuration and data
"""

import asyncio
import asyncpg
import redis
from datetime import datetime, timedelta
from app.core.gdpr_compliance import DataProcessingRecord, ProcessingPurpose, DataCategory

async def initialize_security_data():
    """Initialize security-related data in the database"""
    
    # Connect to PostgreSQL
    conn = await asyncpg.connect(
        host="localhost",
        port=5432,
        user="admin",
        password="password",
        database="offcall_ai"
    )
    
    try:
        print("🔐 Initializing security data...")
        
        # 1. Insert GDPR data processing records
        processing_records = [
            {
                "purpose": ProcessingPurpose.SERVICE_PROVISION.value,
                "data_categories": [DataCategory.PERSONAL_IDENTIFIABLE.value, DataCategory.TECHNICAL.value],
                "legal_basis": "Contract performance (GDPR Art. 6(1)(b))",
                "data_subjects": "OffCall AI platform users",
                "recipients": ["OffCall AI Inc.", "AWS (Infrastructure)", "SendGrid (Email)"],
                "retention_period": timedelta(days=2555),  # 7 years
                "security_measures": [
                    "End-to-end encryption",
                    "Access controls with RBAC",
                    "Regular security audits",
                    "Data anonymization"
                ],
                "cross_border_transfers": True
            },
            {
                "purpose": ProcessingPurpose.SECURITY.value,
                "data_categories": [DataCategory.SECURITY.value, DataCategory.TECHNICAL.value],
                "legal_basis": "Legitimate interest (GDPR Art. 6(1)(f))",
                "data_subjects": "OffCall AI platform users",
                "recipients": ["OffCall AI Inc.", "Security team"],
                "retention_period": timedelta(days=2555),  # 7 years (legal requirement)
                "security_measures": [
                    "Encrypted storage",
                    "Limited access controls",
                    "Audit logging",
                    "Regular deletion schedules"
                ],
                "cross_border_transfers": False
            },
            {
                "purpose": ProcessingPurpose.ANALYTICS.value,
                "data_categories": [DataCategory.BEHAVIORAL.value, DataCategory.TECHNICAL.value],
                "legal_basis": "Consent (GDPR Art. 6(1)(a))",
                "data_subjects": "OffCall AI platform users who have given consent",
                "recipients": ["OffCall AI Inc.", "Analytics team"],
                "retention_period": timedelta(days=365),  # 1 year
                "security_measures": [
                    "Data anonymization",
                    "Aggregated reporting only",
                    "Limited data retention",
                    "Opt-out mechanisms"
                ],
                "cross_border_transfers": False
            }
        ]
        
        for record in processing_records:
            await conn.execute("""
                INSERT INTO data_processing_records 
                (purpose, data_categories, legal_basis, data_subjects, recipients, 
                 retention_period, security_measures, cross_border_transfers)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT DO NOTHING
            """, 
                record["purpose"],
                record["data_categories"],
                record["legal_basis"],
                record["data_subjects"],
                record["recipients"],
                record["retention_period"],
                record["security_measures"],
                record["cross_border_transfers"]
            )
        
        print("✅ GDPR data processing records initialized")
        
        # 2. Set up Redis security keys structure
        r = redis.Redis(host='localhost', port=6379, db=0)
        
        # Initialize rate limiting buckets
        security_keys = [
            "security_events",  # Security event log
            "rate_limits",      # Rate limiting data
            "blocked_ips",      # Temporarily blocked IPs
            "suspicious_patterns", # Attack pattern detection
        ]
        
        for key in security_keys:
            r.sadd(f"security:initialized:{key}", "true")
            r.expire(f"security:initialized:{key}", 86400)  # 24 hours
        
        print("✅ Redis security structure initialized")
        
        # 3. Create default privacy settings for existing users
        existing_users = await conn.fetch("SELECT id FROM users")
        
        for user in existing_users:
            await conn.execute("""
                INSERT INTO user_privacy_settings (user_id, analytics_consent, marketing_consent, third_party_sharing)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO NOTHING
            """, user['id'], False, False, False)
        
        print(f"✅ Privacy settings initialized for {len(existing_users)} existing users")
        
        # 4. Set up security monitoring alerts
        await conn.execute("""
            INSERT INTO security_events (event_type, risk_level, details)
            VALUES ($1, $2, $3)
        """, 
            "security_system_initialized",
            "low",
            {
                "timestamp": datetime.utcnow().isoformat(),
                "message": "OffCall AI security system successfully initialized",
                "features_enabled": [
                    "GDPR compliance",
                    "Enhanced authentication",
                    "Rate limiting",
                    "Security monitoring",
                    "Data encryption"
                ]
            }
        )
        
        print("✅ Security monitoring initialized")
        
        print("\n🎉 Security initialization completed successfully!")
        print("\n📋 Security Features Enabled:")
        print("   ✅ Enhanced JWT authentication with refresh tokens")
        print("   ✅ Multi-factor authentication (TOTP + backup codes)")
        print("   ✅ Advanced rate limiting and DDoS protection")
        print("   ✅ GDPR compliance (data export, deletion, consent)")
        print("   ✅ Security event monitoring and alerting")
        print("   ✅ Device fingerprinting and session management")
        print("   ✅ Attack pattern detection and blocking")
        print("   ✅ Comprehensive audit logging")
        print("   ✅ Data encryption and privacy controls")
        
        print("\n🔒 Next Steps:")
        print("   1. Update environment variables with security keys")
        print("   2. Configure OAuth2 providers (Google, Microsoft, GitHub)")
        print("   3. Set up security monitoring alerts (Slack/email)")
        print("   4. Test MFA setup and authentication flows")
        print("   5. Review and customize rate limiting rules")
        
    except Exception as e:
        print(f"❌ Security initialization failed: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(initialize_security_data())
