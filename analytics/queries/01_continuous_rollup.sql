-- ==============================================================================
-- Supply Chain & Analytics Engineering Practice Analytics Engineering - Continuous Window Rollups
-- Target Engine : PostgreSQL 16 / Snowflake / BigQuery Compatible
-- Domain Scope  : 7-Day & 30-Day Moving CAC, Conversion Velocity & LTV Multipliers
-- ==============================================================================

WITH daily_channel_aggregates AS (
    SELECT
        DATE_TRUNC('day', event_timestamp) AS event_date,
        channel,
        audience_segment,
        COUNT(DISTINCT lead_id) AS total_touchpoints,
        COUNT(DISTINCT CASE WHEN is_converted THEN lead_id END) AS converted_accounts,
        SUM(acquisition_cost_usd) AS daily_spend_usd,
        SUM(realized_ltv_usd) AS daily_realized_ltv_usd,
        AVG(conversion_time_days) AS avg_time_to_convert_days
    FROM analytical_lakehouse.prosigliere_marketing_telemetry
    GROUP BY 
        DATE_TRUNC('day', event_timestamp),
        channel,
        audience_segment
),
rolling_window_calculations AS (
    SELECT
        event_date,
        channel,
        audience_segment,
        total_touchpoints,
        converted_accounts,
        daily_spend_usd,
        daily_realized_ltv_usd,
        avg_time_to_convert_days,

        -- 7-Day Moving Window Averages
        AVG(daily_spend_usd) OVER (
            PARTITION BY channel, audience_segment
            ORDER BY event_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_7d_spend_usd,

        SUM(converted_accounts) OVER (
            PARTITION BY channel, audience_segment
            ORDER BY event_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_7d_conversions,

        SUM(daily_spend_usd) OVER (
            PARTITION BY channel, audience_segment
            ORDER BY event_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_7d_cumulative_spend,

        -- 30-Day Moving Window Performance
        AVG(daily_spend_usd) OVER (
            PARTITION BY channel, audience_segment
            ORDER BY event_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS rolling_30d_spend_usd,

        SUM(daily_realized_ltv_usd) OVER (
            PARTITION BY channel, audience_segment
            ORDER BY event_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS rolling_30d_realized_ltv_usd,

        -- Window Rank of Channel Daily Volume
        DENSE_RANK() OVER (
            PARTITION BY event_date
            ORDER BY daily_spend_usd DESC
        ) AS channel_daily_spend_rank
    FROM daily_channel_aggregates
)
SELECT
    event_date,
    channel,
    audience_segment,
    ROUND(daily_spend_usd::numeric, 2) AS daily_spend_usd,
    converted_accounts,
    ROUND(
        CASE 
            WHEN converted_accounts > 0 THEN (daily_spend_usd / converted_accounts)::numeric
            ELSE NULL 
        END, 2
    ) AS spot_cac_usd,

    ROUND(
        CASE 
            WHEN rolling_7d_conversions > 0 THEN (rolling_7d_cumulative_spend / rolling_7d_conversions)::numeric
            ELSE NULL 
        END, 2
    ) AS rolling_7d_blended_cac_usd,

    ROUND(
        CASE 
            WHEN rolling_30d_spend_usd > 0 THEN (rolling_30d_realized_ltv_usd / (rolling_30d_spend_usd * 30))::numeric
            ELSE NULL 
        END, 2
    ) AS rolling_30d_ltv_roas_ratio,

    channel_daily_spend_rank
FROM rolling_window_calculations
ORDER BY event_date DESC, channel_daily_spend_rank ASC;