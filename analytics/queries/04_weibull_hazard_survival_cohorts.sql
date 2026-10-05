-- ==============================================================================
-- Supply Chain & Analytics Engineering Practice Analytics Engineering - Weibull & Kaplan-Meier Survival Analysis
-- Target Engine : PostgreSQL 16 / Snowflake / BigQuery Compatible
-- Domain Scope  : Actuarial Survival Curves S(t), Cumulative Hazard & Risk Sets
-- ==============================================================================

WITH discrete_timeline AS (
    SELECT
        channel,
        audience_segment,
        CEIL(conversion_time_days) AS time_interval_day,
        COUNT(DISTINCT lead_id) AS total_events_at_t,
        COUNT(DISTINCT CASE WHEN is_converted THEN lead_id END) AS conversions_at_t,
        COUNT(DISTINCT CASE WHEN NOT is_converted THEN lead_id END) AS censored_at_t
    FROM analytical_lakehouse.prosigliere_marketing_telemetry
    GROUP BY
        channel,
        audience_segment,
        CEIL(conversion_time_days)
),
channel_risk_sets AS (
    SELECT
        channel,
        audience_segment,
        time_interval_day,
        conversions_at_t,
        censored_at_t,

        -- Total population at risk at start of interval t: sum of all events at and after t
        SUM(total_events_at_t) OVER (
            PARTITION BY channel, audience_segment
            ORDER BY time_interval_day ASC
            ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING
        ) AS population_at_risk_n_t
    FROM discrete_timeline
),
kaplan_meier_step_hazards AS (
    SELECT
        channel,
        audience_segment,
        time_interval_day,
        conversions_at_t,
        population_at_risk_n_t,

        -- Step conditional hazard: h(t) = d_t / n_t
        CASE 
            WHEN population_at_risk_n_t > 0 
            THEN (conversions_at_t::numeric / population_at_risk_n_t)
            ELSE 0.0 
        END AS step_conditional_hazard,

        -- Interval survival factor: 1 - (d_t / n_t)
        CASE 
            WHEN population_at_risk_n_t > 0 
            THEN (1.0 - (conversions_at_t::numeric / population_at_risk_n_t))
            ELSE 1.0 
        END AS interval_survival_factor
    FROM channel_risk_sets
),
cumulative_hazard_estimators AS (
    SELECT
        channel,
        audience_segment,
        time_interval_day,
        conversions_at_t,
        population_at_risk_n_t,
        step_conditional_hazard,

        -- Nelson-Aalen Cumulative Hazard Estimator: H(t) = sum(d_t / n_t)
        SUM(step_conditional_hazard) OVER (
            PARTITION BY channel, audience_segment
            ORDER BY time_interval_day ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS nelson_aalen_cumulative_hazard,

        -- Greenwood's variance component: sum(d_t / (n_t * (n_t - d_t)))
        SUM(
            CASE 
                WHEN population_at_risk_n_t > conversions_at_t AND population_at_risk_n_t > 0
                THEN (conversions_at_t::numeric / (population_at_risk_n_t * (population_at_risk_n_t - conversions_at_t)))
                ELSE 0.0 
            END
        ) OVER (
            PARTITION BY channel, audience_segment
            ORDER BY time_interval_day ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS greenwood_variance_component
    FROM kaplan_meier_step_hazards
)
SELECT
    channel,
    audience_segment,
    time_interval_day,
    conversions_at_t,
    population_at_risk_n_t,
    ROUND(step_conditional_hazard::numeric, 6) AS step_hazard_h_t,
    ROUND(nelson_aalen_cumulative_hazard::numeric, 6) AS nelson_aalen_cum_hazard,

    -- Survival Function approximation S(t) = exp(-H(t))
    ROUND(EXP(-nelson_aalen_cumulative_hazard)::numeric, 4) AS kaplan_meier_survival_prob_s_t,

    -- 95% Log-Log Greenwood Confidence Interval Bound
    ROUND((1.96 * SQRT(greenwood_variance_component))::numeric, 6) AS greenwood_error_margin_95
FROM cumulative_hazard_estimators
WHERE time_interval_day <= 60
ORDER BY channel ASC, audience_segment ASC, time_interval_day ASC;
