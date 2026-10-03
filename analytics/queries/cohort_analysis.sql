-- ==============================================================================
-- Prosigliere Analytics Engineering - Longitudinal Cohort & Conversion Analysis
-- Target Engine : PostgreSQL 16 / Snowflake / BigQuery Compatible
-- Domain Scope  : Omnichannel Acquisition Cohorts, Quartile Slicing & LTV Maturation
-- ==============================================================================

WITH cohort_base AS (
    SELECT
        lead_id,
        channel,
        audience_segment,
        DATE_TRUNC('month', event_timestamp) AS cohort_month,
        acquisition_cost_usd,
        conversion_time_days,
        is_converted,
        realized_ltv_usd,

        -- Quartile rank of acquisition cost within channel
        NTILE(4) OVER (
            PARTITION BY channel
            ORDER BY acquisition_cost_usd ASC
        ) AS cac_quartile,

        -- Order of touchpoint per account
        ROW_NUMBER() OVER (
            PARTITION BY lead_id
            ORDER BY event_timestamp ASC
        ) AS touchpoint_sequence
    FROM analytical_lakehouse.prosigliere_marketing_telemetry
),
cohort_maturation AS (
    SELECT
        cohort_month,
        channel,
        cac_quartile,
        COUNT(DISTINCT lead_id) AS total_cohort_accounts,
        COUNT(DISTINCT CASE WHEN is_converted THEN lead_id END) AS converted_accounts,
        SUM(acquisition_cost_usd) AS total_cohort_spend_usd,
        SUM(realized_ltv_usd) AS total_cohort_ltv_usd,

        -- Conversion milestone counts
        COUNT(DISTINCT CASE WHEN is_converted AND conversion_time_days <= 7.0 THEN lead_id END) AS converted_under_7d,
        COUNT(DISTINCT CASE WHEN is_converted AND conversion_time_days <= 14.0 THEN lead_id END) AS converted_under_14d,
        COUNT(DISTINCT CASE WHEN is_converted AND conversion_time_days <= 30.0 THEN lead_id END) AS converted_under_30d,
        COUNT(DISTINCT CASE WHEN is_converted AND conversion_time_days <= 60.0 THEN lead_id END) AS converted_under_60d,

        AVG(conversion_time_days) AS avg_days_to_convert
    FROM cohort_base
    GROUP BY
        cohort_month,
        channel,
        cac_quartile
)
SELECT
    cohort_month,
    channel,
    cac_quartile,
    total_cohort_accounts,
    converted_accounts,
    ROUND(total_cohort_spend_usd::numeric, 2) AS total_cohort_spend_usd,
    ROUND(total_cohort_ltv_usd::numeric, 2) AS total_cohort_ltv_usd,

    -- Empirical Conversion Rates
    ROUND((converted_accounts::numeric / NULLIF(total_cohort_accounts, 0) * 100.0), 2) AS overall_conversion_rate_pct,
    ROUND((converted_under_7d::numeric / NULLIF(total_cohort_accounts, 0) * 100.0), 2) AS day7_conversion_rate_pct,
    ROUND((converted_under_14d::numeric / NULLIF(total_cohort_accounts, 0) * 100.0), 2) AS day14_conversion_rate_pct,
    ROUND((converted_under_30d::numeric / NULLIF(total_cohort_accounts, 0) * 100.0), 2) AS day30_conversion_rate_pct,

    -- Unit Economics
    ROUND((total_cohort_spend_usd / NULLIF(converted_accounts, 0))::numeric, 2) AS cohort_blended_cac_usd,
    ROUND((total_cohort_ltv_usd / NULLIF(total_cohort_spend_usd, 0))::numeric, 2) AS cohort_ltv_roas_multiplier
FROM cohort_maturation
ORDER BY cohort_month DESC, channel ASC, cac_quartile ASC;