-- ==============================================================================
-- Supply Chain & Analytics Engineering Practice Analytics Engineering - Anomaly Detection Event Triggers
-- Target Engine : PostgreSQL 16 Enterprise / Aurora
-- Domain Scope  : Real-Time Audit on Channel CAC Surges (>3x Moving Median)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS analytical_lakehouse.prosigliere_telemetry_anomaly_alerts (
    alert_id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    lead_id VARCHAR(64) NOT NULL,
    channel VARCHAR(48) NOT NULL,
    audience_segment VARCHAR(48) NOT NULL,
    anomalous_cost_usd NUMERIC(12, 4) NOT NULL,
    channel_historical_median_cac NUMERIC(12, 4) NOT NULL,
    surge_multiplier NUMERIC(8, 2) NOT NULL,
    alert_severity VARCHAR(24) NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload_metadata JSONB NOT NULL
);

-- Trigger Function: Inspects incoming marketing telemetry rows for unit cost anomalies
CREATE OR REPLACE FUNCTION analytical_lakehouse.fn_audit_marketing_cost_anomalies()
RETURNS TRIGGER AS $$
DECLARE
    v_median_cac NUMERIC(12, 4);
    v_surge_ratio NUMERIC(8, 2);
    v_severity VARCHAR(24);
BEGIN
    -- Compute 30-day baseline historical median for the specific channel
    SELECT COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY acquisition_cost_usd), 100.0)
    INTO v_median_cac
    FROM analytical_lakehouse.prosigliere_marketing_telemetry
    WHERE channel = NEW.channel
      AND event_timestamp >= NEW.event_timestamp - INTERVAL '30 days';

    -- Evaluate surge ratio relative to rolling baseline
    IF v_median_cac > 0 THEN
        v_surge_ratio := ROUND((NEW.acquisition_cost_usd / v_median_cac)::numeric, 2);
    ELSE
        v_surge_ratio := 1.0;
    END IF;

    -- Flag anomalies exceeding critical 3.0x threshold
    IF v_surge_ratio >= 3.0 THEN
        IF v_surge_ratio >= 5.0 THEN
            v_severity := 'CRITICAL_SPIKE';
        ELSE
            v_severity := 'HIGH_VARIANCE';
        END IF;

        INSERT INTO analytical_lakehouse.prosigliere_telemetry_anomaly_alerts (
            lead_id,
            channel,
            audience_segment,
            anomalous_cost_usd,
            channel_historical_median_cac,
            surge_multiplier,
            alert_severity,
            detected_at,
            payload_metadata
        ) VALUES (
            NEW.lead_id,
            NEW.channel,
            NEW.audience_segment,
            NEW.acquisition_cost_usd,
            v_median_cac,
            v_surge_ratio,
            v_severity,
            CURRENT_TIMESTAMP,
            jsonb_build_object(
                'conversion_time_days', NEW.conversion_time_days,
                'weibull_shape_k', NEW.weibull_shape_k,
                'weibull_scale_lambda', NEW.weibull_scale_lambda,
                'is_converted', NEW.is_converted
            )
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Bind Trigger to Main Telemetry Table
DROP TRIGGER IF EXISTS trg_audit_marketing_cost_anomalies 
ON analytical_lakehouse.prosigliere_marketing_telemetry;

CREATE TRIGGER trg_audit_marketing_cost_anomalies
    AFTER INSERT ON analytical_lakehouse.prosigliere_marketing_telemetry
    FOR EACH ROW
    EXECUTE FUNCTION analytical_lakehouse.fn_audit_marketing_cost_anomalies();