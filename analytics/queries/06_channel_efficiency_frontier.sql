-- ==============================================================================
-- Prosigliere Analytics Engineering - Channel Efficiency & Diminishing Returns
-- Target Engine : PostgreSQL 16 / Snowflake / BigQuery Compatible
-- Domain Scope  : Non-Linear Saturation Frontiers, Marginal CAC & Spend Elasticity
-- ==============================================================================

WITH weekly_spend_brackets AS (
    SELECT
        DATE_TRUNC('week', event_timestamp) AS calendar_week,
        channel,
        SUM(acquisition_cost_usd) AS weekly_channel_spend,
        COUNT(DISTINCT lead_id) AS weekly_leads_touched,
        COUNT(DISTINCT CASE WHEN is_converted THEN lead_id END) AS weekly_conversions,
        SUM(realized_ltv_usd) AS weekly_realized_ltv,

        -- Moving 4-week average spend to smooth weekly volatility
        AVG(SUM(acquisition_cost_usd)) OVER (
            PARTITION BY channel
            ORDER BY DATE_TRUNC('week', event_timestamp)
            ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
        ) AS smoothed_4w_spend_usd
    FROM analytical_lakehouse.prosigliere_marketing_telemetry
    GROUP BY
        DATE_TRUNC('week', event_timestamp),
        channel
),
marginal_gain_derivatives AS (
    SELECT
        calendar_week,
        channel,
        weekly_channel_spend,
        weekly_leads_touched,
        weekly_conversions,
        weekly_realized_ltv,
        smoothed_4w_spend_usd,

        -- Prior week spend and conversion lag
        LAG(weekly_channel_spend, 1) OVER (
            PARTITION BY channel
            ORDER BY calendar_week ASC
        ) AS prior_week_spend,

        LAG(weekly_conversions, 1) OVER (
            PARTITION BY channel
            ORDER BY calendar_week ASC
        ) AS prior_week_conversions,

        LAG(weekly_realized_ltv, 1) OVER (
            PARTITION BY channel
            ORDER BY calendar_week ASC
        ) AS prior_week_ltv
    FROM weekly_spend_brackets
),
elasticity_and_marginal_cac AS (
    SELECT
        calendar_week,
        channel,
        weekly_channel_spend,
        weekly_conversions,
        weekly_realized_ltv,

        -- Marginal delta calculations: d(Spend) and d(Conversions)
        (weekly_channel_spend - prior_week_spend) AS delta_spend_usd,
        (weekly_conversions - prior_week_conversions) AS delta_conversions,
        (weekly_realized_ltv - prior_week_ltv) AS delta_ltv_usd,

        -- Average Cost Per Acquisition (Spot CAC)
        CASE
            WHEN weekly_conversions > 0
            THEN ROUND((weekly_channel_spend / weekly_conversions)::numeric, 2)
            ELSE NULL
        END AS spot_weekly_cac,

        -- Marginal CAC: d(Spend) / d(Conversions)
        CASE
            WHEN (weekly_conversions - prior_week_conversions) > 0
            THEN ROUND(((weekly_channel_spend - prior_week_spend) / (weekly_conversions - prior_week_conversions))::numeric, 2)
            ELSE NULL
        END AS marginal_incremental_cac,

        -- Marginal ROAS: d(LTV) / d(Spend)
        CASE
            WHEN (weekly_channel_spend - prior_week_spend) > 0
            THEN ROUND(((weekly_realized_ltv - prior_week_ltv) / (weekly_channel_spend - prior_week_spend))::numeric, 4)
            ELSE NULL
        END AS marginal_ltv_multiplier
    FROM marginal_gain_derivatives
)
SELECT
    calendar_week,
    channel,
    ROUND(weekly_channel_spend::numeric, 2) AS weekly_channel_spend,
    weekly_conversions,
    spot_weekly_cac,
    marginal_incremental_cac,
    marginal_ltv_multiplier,

    -- Frontier Categorization: Evaluates if channel is in diminishing returns or sweet spot
    CASE
        WHEN marginal_incremental_cac IS NOT NULL AND marginal_incremental_cac > (spot_weekly_cac * 1.50)
            THEN 'CAPACITY_SATURATION_STAGE'
        WHEN marginal_ltv_multiplier IS NOT NULL AND marginal_ltv_multiplier > 10.0
            THEN 'HIGH_RETURN_SCALING_STAGE'
        WHEN marginal_incremental_cac IS NOT NULL AND marginal_incremental_cac <= spot_weekly_cac
            THEN 'EFFICIENCY_SWEET_SPOT'
        ELSE 'STEADY_STATE'
    END AS channel_frontier_state,

    -- Efficiency rank within calendar week
    RANK() OVER (
        PARTITION BY calendar_week
        ORDER BY spot_weekly_cac ASC NULLS LAST
    ) AS weekly_efficiency_rank
FROM elasticity_and_marginal_cac
ORDER BY calendar_week DESC, weekly_efficiency_rank ASC;
