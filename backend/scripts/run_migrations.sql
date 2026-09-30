-- OffCall AI Database Migration Script
-- Run this in Azure Portal Query Editor or from a Kubernetes pod
-- Created: 2026-01-10

-- ============================================
-- 1. On-Call Schedules Table
-- ============================================
CREATE TABLE IF NOT EXISTS on_call_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    team_id UUID REFERENCES teams(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    is_active BOOLEAN DEFAULT true,
    escalation_policy_id UUID REFERENCES escalation_policies(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_by_id UUID REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS ix_on_call_schedules_organization_id ON on_call_schedules(organization_id);
CREATE INDEX IF NOT EXISTS ix_on_call_schedules_team_id ON on_call_schedules(team_id);
CREATE INDEX IF NOT EXISTS ix_on_call_schedules_is_active ON on_call_schedules(is_active);

-- ============================================
-- 2. On-Call Shifts Table
-- ============================================
CREATE TABLE IF NOT EXISTS on_call_shifts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id UUID NOT NULL REFERENCES on_call_schedules(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    shift_type VARCHAR(20) NOT NULL DEFAULT 'recurring',
    day_of_week INTEGER,
    start_time TIME,
    end_time TIME,
    start_datetime TIMESTAMPTZ,
    end_datetime TIMESTAMPTZ,
    notify_channels JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_on_call_shifts_schedule_id ON on_call_shifts(schedule_id);
CREATE INDEX IF NOT EXISTS ix_on_call_shifts_user_id ON on_call_shifts(user_id);
CREATE INDEX IF NOT EXISTS ix_on_call_shifts_day_of_week ON on_call_shifts(day_of_week);

-- ============================================
-- 3. Maintenance Windows Table
-- ============================================
CREATE TABLE IF NOT EXISTS maintenance_windows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    services JSONB DEFAULT '[]',
    tags JSONB DEFAULT '[]',
    suppress_alerts BOOLEAN NOT NULL DEFAULT true,
    auto_resolve_incidents BOOLEAN NOT NULL DEFAULT false,
    is_recurring BOOLEAN NOT NULL DEFAULT false,
    recurrence_pattern JSONB,
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_cancelled BOOLEAN NOT NULL DEFAULT false,
    cancelled_at TIMESTAMPTZ,
    cancelled_by_id UUID REFERENCES users(id),
    notify_before_minutes INTEGER NOT NULL DEFAULT 30,
    notification_sent BOOLEAN NOT NULL DEFAULT false,
    created_by_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_maintenance_windows_organization_id ON maintenance_windows(organization_id);
CREATE INDEX IF NOT EXISTS ix_maintenance_windows_start_time ON maintenance_windows(start_time);
CREATE INDEX IF NOT EXISTS ix_maintenance_windows_end_time ON maintenance_windows(end_time);
CREATE INDEX IF NOT EXISTS ix_maintenance_windows_is_active ON maintenance_windows(is_active);
CREATE INDEX IF NOT EXISTS ix_maintenance_windows_is_cancelled ON maintenance_windows(is_cancelled);
CREATE INDEX IF NOT EXISTS ix_maintenance_windows_org_active_time ON maintenance_windows(organization_id, is_active, is_cancelled, start_time, end_time);

-- ============================================
-- 4. Post-Mortems Enum and Table
-- ============================================
DO $$ BEGIN
    CREATE TYPE postmortemstatus AS ENUM ('draft', 'in_review', 'published', 'archived');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS post_mortems (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    incident_id UUID NOT NULL REFERENCES incidents(id),
    title VARCHAR(255) NOT NULL,
    status postmortemstatus NOT NULL DEFAULT 'draft',
    summary TEXT,
    impact TEXT,
    root_cause TEXT,
    resolution TEXT,
    lessons_learned TEXT,
    timeline JSONB DEFAULT '[]',
    action_items JSONB DEFAULT '[]',
    tags JSONB DEFAULT '[]',
    contributing_factors JSONB DEFAULT '[]',
    detection_time_minutes INTEGER,
    response_time_minutes INTEGER,
    resolution_time_minutes INTEGER,
    total_downtime_minutes INTEGER,
    assessed_severity VARCHAR(20),
    customer_impact_score INTEGER,
    reviewed_by_id UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    published_by_id UUID REFERENCES users(id),
    published_at TIMESTAMPTZ,
    created_by_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_post_mortems_organization_id ON post_mortems(organization_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_post_mortems_incident_id ON post_mortems(incident_id);
CREATE INDEX IF NOT EXISTS ix_post_mortems_status ON post_mortems(status);
CREATE INDEX IF NOT EXISTS ix_post_mortems_org_status ON post_mortems(organization_id, status);
CREATE INDEX IF NOT EXISTS ix_post_mortems_created_at ON post_mortems(created_at);

-- ============================================
-- 5. Post-Mortem Comments Table
-- ============================================
CREATE TABLE IF NOT EXISTS post_mortem_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_mortem_id UUID NOT NULL REFERENCES post_mortems(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    section VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_post_mortem_comments_post_mortem_id ON post_mortem_comments(post_mortem_id);
CREATE INDEX IF NOT EXISTS ix_post_mortem_comments_user_id ON post_mortem_comments(user_id);

-- ============================================
-- Done!
-- ============================================
SELECT 'Migration completed successfully!' as status;
