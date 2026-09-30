-- ClickHouse Schema for OffCall AI
-- Time-series data: metrics, logs, traces, RUM events

-- =============================================================================
-- DATABASE
-- =============================================================================
CREATE DATABASE IF NOT EXISTS offcall;

-- =============================================================================
-- METRICS TABLE
-- Optimized for time-series metric data with high cardinality tags
-- =============================================================================
CREATE TABLE IF NOT EXISTS offcall.metrics
(
    -- Time partitioning
    timestamp DateTime64(3) DEFAULT now64(3),

    -- Organization isolation (multi-tenant)
    organization_id UUID,

    -- Host/source identification
    host_id Nullable(UUID),

    -- Metric data
    name LowCardinality(String),
    value Float64,
    unit LowCardinality(String) DEFAULT '',

    -- Tags for filtering (service, env, region, etc.)
    tags Map(LowCardinality(String), String) DEFAULT map(),

    -- Indexes
    INDEX idx_name name TYPE bloom_filter GRANULARITY 4,
    INDEX idx_tags_keys mapKeys(tags) TYPE bloom_filter GRANULARITY 4
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (organization_id, name, timestamp)
TTL toDateTime(timestamp) + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- =============================================================================
-- LOGS TABLE
-- Optimized for log search with full-text capabilities
-- =============================================================================
CREATE TABLE IF NOT EXISTS offcall.logs
(
    -- Time partitioning
    timestamp DateTime64(3) DEFAULT now64(3),

    -- Organization isolation
    organization_id UUID,

    -- Source identification
    host_id Nullable(UUID),

    -- Log data
    level LowCardinality(String) DEFAULT 'INFO',  -- TRACE, DEBUG, INFO, WARN, ERROR, FATAL
    message String,
    service LowCardinality(String) DEFAULT '',
    source LowCardinality(String) DEFAULT '',

    -- Correlation IDs for distributed tracing
    trace_id String DEFAULT '',
    span_id String DEFAULT '',

    -- Structured fields (JSON)
    fields Map(String, String) DEFAULT map(),

    -- Full-text search index on message
    INDEX idx_message message TYPE tokenbf_v1(10240, 3, 0) GRANULARITY 4,
    INDEX idx_level level TYPE set(10) GRANULARITY 4,
    INDEX idx_service service TYPE bloom_filter GRANULARITY 4
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (organization_id, timestamp, level)
TTL toDateTime(timestamp) + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;

-- =============================================================================
-- SPANS TABLE (Distributed Tracing)
-- OpenTelemetry-compatible span storage
-- =============================================================================
CREATE TABLE IF NOT EXISTS offcall.spans
(
    -- Time partitioning
    timestamp DateTime64(3) DEFAULT now64(3),

    -- Organization isolation
    organization_id UUID,

    -- Trace identification
    trace_id String,
    span_id String,
    parent_span_id String DEFAULT '',

    -- Span metadata
    service_name LowCardinality(String),
    operation_name String,
    span_kind LowCardinality(String) DEFAULT 'INTERNAL',  -- INTERNAL, SERVER, CLIENT, PRODUCER, CONSUMER

    -- Timing
    duration_ms Float64 DEFAULT 0,

    -- Status
    status_code LowCardinality(String) DEFAULT 'OK',  -- OK, ERROR, UNSET
    status_message String DEFAULT '',

    -- Attributes (OpenTelemetry attributes)
    attributes Map(String, String) DEFAULT map(),

    -- Events within span
    events String DEFAULT '[]',  -- JSON array of events

    -- Links to other traces
    links String DEFAULT '[]',  -- JSON array of links

    -- Indexes
    INDEX idx_trace_id trace_id TYPE bloom_filter GRANULARITY 4,
    INDEX idx_service service_name TYPE bloom_filter GRANULARITY 4,
    INDEX idx_status status_code TYPE set(10) GRANULARITY 4
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (organization_id, trace_id, timestamp)
TTL toDateTime(timestamp) + INTERVAL 14 DAY
SETTINGS index_granularity = 8192;

-- =============================================================================
-- SERVICE METRICS (Aggregated APM data)
-- Pre-aggregated metrics per service for fast dashboard queries
-- =============================================================================
CREATE TABLE IF NOT EXISTS offcall.service_metrics
(
    -- Time bucket
    time_bucket DateTime,

    -- Organization isolation
    organization_id UUID,

    -- Service identification
    service_name LowCardinality(String),

    -- Aggregated metrics
    request_count UInt64 DEFAULT 0,
    error_count UInt64 DEFAULT 0,

    -- Latency percentiles
    latency_sum Float64 DEFAULT 0,
    latency_p50 Float64 DEFAULT 0,
    latency_p90 Float64 DEFAULT 0,
    latency_p95 Float64 DEFAULT 0,
    latency_p99 Float64 DEFAULT 0,
    latency_max Float64 DEFAULT 0
)
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(time_bucket)
ORDER BY (organization_id, service_name, time_bucket)
TTL time_bucket + INTERVAL 90 DAY;

-- =============================================================================
-- RUM EVENTS (Real User Monitoring)
-- Browser performance and error tracking
-- =============================================================================
CREATE TABLE IF NOT EXISTS offcall.rum_events
(
    -- Time partitioning
    timestamp DateTime64(3) DEFAULT now64(3),

    -- Organization isolation
    organization_id UUID,

    -- Application identification
    application_id UUID,

    -- Session tracking
    session_id String,

    -- Event type
    event_type LowCardinality(String),  -- pageview, error, resource, webvital, click

    -- Page/URL info
    url String DEFAULT '',

    -- User identification (optional)
    user_id String DEFAULT '',

    -- Device info
    device_type LowCardinality(String) DEFAULT '',  -- desktop, mobile, tablet
    browser LowCardinality(String) DEFAULT '',
    os LowCardinality(String) DEFAULT '',

    -- Geo info
    country LowCardinality(String) DEFAULT '',

    -- Performance metrics
    duration_ms Float64 DEFAULT 0,

    -- Core Web Vitals
    lcp_ms Float64 DEFAULT 0,  -- Largest Contentful Paint
    fid_ms Float64 DEFAULT 0,  -- First Input Delay
    cls_score Float64 DEFAULT 0,  -- Cumulative Layout Shift

    -- Error data (for error events)
    error_message String DEFAULT '',
    error_stack String DEFAULT '',

    -- Additional metadata
    metadata Map(String, String) DEFAULT map(),

    -- Indexes
    INDEX idx_session session_id TYPE bloom_filter GRANULARITY 4,
    INDEX idx_event_type event_type TYPE set(10) GRANULARITY 4,
    INDEX idx_url url TYPE tokenbf_v1(10240, 3, 0) GRANULARITY 4
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (organization_id, application_id, timestamp)
TTL toDateTime(timestamp) + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;

-- =============================================================================
-- NETWORK FLOWS
-- Network traffic monitoring
-- =============================================================================
CREATE TABLE IF NOT EXISTS offcall.network_flows
(
    -- Time partitioning
    timestamp DateTime64(3) DEFAULT now64(3),

    -- Organization isolation
    organization_id UUID,

    -- Flow identification
    src_ip String,
    dst_ip String,
    src_port UInt16,
    dst_port UInt16,
    protocol LowCardinality(String),  -- TCP, UDP, ICMP

    -- Flow metrics
    bytes_in UInt64 DEFAULT 0,
    bytes_out UInt64 DEFAULT 0,
    packets_in UInt64 DEFAULT 0,
    packets_out UInt64 DEFAULT 0,

    -- Connection info
    device_id Nullable(UUID),
    interface_name LowCardinality(String) DEFAULT '',

    -- Indexes
    INDEX idx_src_ip src_ip TYPE bloom_filter GRANULARITY 4,
    INDEX idx_dst_ip dst_ip TYPE bloom_filter GRANULARITY 4
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (organization_id, timestamp)
TTL toDateTime(timestamp) + INTERVAL 7 DAY
SETTINGS index_granularity = 8192;

-- =============================================================================
-- PROFILES (Continuous Profiling)
-- CPU/Memory profiling data
-- =============================================================================
CREATE TABLE IF NOT EXISTS offcall.profiles
(
    -- Time partitioning
    timestamp DateTime64(3) DEFAULT now64(3),

    -- Organization isolation
    organization_id UUID,

    -- Service/host identification
    service_name LowCardinality(String),
    host_id Nullable(UUID),

    -- Profile type
    profile_type LowCardinality(String),  -- cpu, heap, goroutine, mutex, block

    -- Profile data (compressed pprof format)
    profile_data String,  -- base64 encoded

    -- Metadata
    duration_seconds Float64 DEFAULT 0,
    sample_count UInt64 DEFAULT 0,

    -- Environment
    environment LowCardinality(String) DEFAULT '',
    runtime LowCardinality(String) DEFAULT '',
    runtime_version String DEFAULT '',

    -- Labels for filtering
    labels Map(String, String) DEFAULT map()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (organization_id, service_name, profile_type, timestamp)
TTL toDateTime(timestamp) + INTERVAL 7 DAY
SETTINGS index_granularity = 8192;

-- =============================================================================
-- MATERIALIZED VIEWS FOR FAST AGGREGATIONS
-- =============================================================================

-- Metrics aggregation (1 minute buckets)
CREATE MATERIALIZED VIEW IF NOT EXISTS offcall.metrics_1m
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(time_bucket)
ORDER BY (organization_id, name, time_bucket)
AS SELECT
    toStartOfMinute(timestamp) as time_bucket,
    organization_id,
    name,
    avg(value) as avg_value,
    min(value) as min_value,
    max(value) as max_value,
    count() as sample_count
FROM offcall.metrics
GROUP BY time_bucket, organization_id, name;

-- Log level counts (hourly)
CREATE MATERIALIZED VIEW IF NOT EXISTS offcall.log_stats_hourly
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(time_bucket)
ORDER BY (organization_id, time_bucket, level)
AS SELECT
    toStartOfHour(timestamp) as time_bucket,
    organization_id,
    level,
    count() as log_count
FROM offcall.logs
GROUP BY time_bucket, organization_id, level;

-- Service latency aggregation (5 minute buckets)
CREATE MATERIALIZED VIEW IF NOT EXISTS offcall.service_latency_5m
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(time_bucket)
ORDER BY (organization_id, service_name, time_bucket)
AS SELECT
    toStartOfFiveMinutes(timestamp) as time_bucket,
    organization_id,
    service_name,
    count() as request_count,
    countIf(status_code = 'ERROR') as error_count,
    avg(duration_ms) as avg_latency,
    quantile(0.50)(duration_ms) as p50_latency,
    quantile(0.95)(duration_ms) as p95_latency,
    quantile(0.99)(duration_ms) as p99_latency,
    max(duration_ms) as max_latency
FROM offcall.spans
WHERE parent_span_id = ''  -- Root spans only
GROUP BY time_bucket, organization_id, service_name;

-- RUM Core Web Vitals aggregation (hourly by app)
CREATE MATERIALIZED VIEW IF NOT EXISTS offcall.rum_webvitals_hourly
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(time_bucket)
ORDER BY (organization_id, application_id, time_bucket)
AS SELECT
    toStartOfHour(timestamp) as time_bucket,
    organization_id,
    application_id,
    countIf(event_type = 'pageview') as page_views,
    countIf(event_type = 'error') as error_count,
    uniqExact(session_id) as unique_sessions,
    avg(lcp_ms) as avg_lcp,
    avg(fid_ms) as avg_fid,
    avg(cls_score) as avg_cls,
    quantile(0.75)(lcp_ms) as p75_lcp,
    quantile(0.75)(fid_ms) as p75_fid,
    quantile(0.75)(cls_score) as p75_cls
FROM offcall.rum_events
GROUP BY time_bucket, organization_id, application_id;
