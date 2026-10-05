-- ==============================================================================
-- Supply Chain & Analytics Engineering Practice Analytical Lakehouse - Enterprise DDL & Partitioning Schema
-- Target Engine : PostgreSQL 16 Enterprise / Amazon RDS Aurora / BigQuery Compatible
-- Domain Scope  : Omnichannel Marketing Attribution & Customer Survival Telemetry
-- Architecture  : Time-Series Range Partitioning, BRIN Indexing & Audit Log Triggers
-- ==============================================================================

CREATE SCHEMA IF NOT EXISTS analytical_lakehouse;
SET search_path TO analytical_lakehouse, public;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ------------------------------------------------------------------------------
-- 1. Master Omnichannel Marketing Telemetry Table (Range Partitioned by Month)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prosigliere_marketing_telemetry (
    telemetry_id UUID DEFAULT uuid_generate_v4(),
    lead_id VARCHAR(64) NOT NULL,
    channel VARCHAR(48) NOT NULL,
    audience_segment VARCHAR(48) NOT NULL,
    acquisition_cost_usd NUMERIC(12, 4) NOT NULL,
    conversion_time_days NUMERIC(8, 2) NOT NULL,
    is_converted BOOLEAN NOT NULL DEFAULT FALSE,
    weibull_shape_k NUMERIC(8, 4) NOT NULL,
    weibull_scale_lambda NUMERIC(8, 4) NOT NULL,
    realized_ltv_usd NUMERIC(14, 4) NOT NULL DEFAULT 0.0,
    event_timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pk_prosigliere_marketing_telemetry 
        PRIMARY KEY (event_timestamp, telemetry_id)
) PARTITION BY RANGE (event_timestamp);

-- Monthly Rolling Operational Window Partitions
CREATE TABLE IF NOT EXISTS prosigliere_marketing_telemetry_2026_q1 
    PARTITION OF prosigliere_marketing_telemetry
    FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2026-04-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS prosigliere_marketing_telemetry_2026_q2 
    PARTITION OF prosigliere_marketing_telemetry
    FOR VALUES FROM ('2026-04-01 00:00:00+00') TO ('2026-07-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS prosigliere_marketing_telemetry_2026_q3 
    PARTITION OF prosigliere_marketing_telemetry
    FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-10-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS prosigliere_marketing_telemetry_default 
    PARTITION OF prosigliere_marketing_telemetry
    DEFAULT;

-- High-Density BRIN Index for Append-Only Time-Series (95% RAM Reduction)
CREATE INDEX IF NOT EXISTS idx_prosigliere_telemetry_brin_event_timestamp 
    ON prosigliere_marketing_telemetry USING BRIN (event_timestamp) 
    WITH (pages_per_range = 32);

-- Composite B-Tree Indexes for Real-Time Triage & Slicing
CREATE INDEX IF NOT EXISTS idx_prosigliere_telemetry_channel_segment 
    ON prosigliere_marketing_telemetry (channel, audience_segment, event_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_prosigliere_telemetry_lead_lookup 
    ON prosigliere_marketing_telemetry (lead_id, event_timestamp);

-- ------------------------------------------------------------------------------
-- 2. Audit Trail Table: Preserves Budget Optimization Run Artifacts
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prosigliere_optimization_audit_log (
    run_id VARCHAR(64) PRIMARY KEY,
    total_budget_allocated NUMERIC(14, 2) NOT NULL,
    expected_conversions NUMERIC(10, 2) NOT NULL,
    expected_blended_cac NUMERIC(10, 2) NOT NULL,
    expected_total_ltv NUMERIC(16, 2) NOT NULL,
    budget_utilization_pct NUMERIC(6, 2) NOT NULL,
    solver_status_code INT NOT NULL,
    solver_latency_ms NUMERIC(8, 2) NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    allocations_json JSONB NOT NULL,
    dual_shadow_prices_json JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prosigliere_opt_audit_executed_at 
    ON prosigliere_optimization_audit_log (executed_at DESC);