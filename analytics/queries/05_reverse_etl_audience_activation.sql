-- ==============================================================================
-- Prosigliere Analytics Engineering - Reverse ETL Audience Activation Mart
-- Target Engine : PostgreSQL 16 / Snowflake / BigQuery Compatible
-- Domain Scope  : Hightouch & Census Reverse ETL Payloads for Braze and Meta Ads
-- Architecture  : RFM Value Deciles, Churn Hazard Flags & JSON Sync Serialization
-- ==============================================================================

WITH account_touchpoint_history AS (
    SELECT
        lead_id,
        channel,
        audience_segment,
        acquisition_cost_usd,
        conversion_time_days,
        is_converted,
        weibull_shape_k,
        weibull_scale_lambda,
        realized_ltv_usd,
        event_timestamp,

        -- Most recent interaction per account
        ROW_NUMBER() OVER (
            PARTITION BY lead_id
            ORDER BY event_timestamp DESC
        ) AS recency_sequence,

        -- Total interactions count and aggregate spend
        COUNT(*) OVER (
            PARTITION BY lead_id
        ) AS total_account_touchpoints,

        SUM(acquisition_cost_usd) OVER (
            PARTITION BY lead_id
        ) AS cumulative_acquisition_cost_usd,

        MAX(realized_ltv_usd) OVER (
            PARTITION BY lead_id
        ) AS max_account_ltv_usd
    FROM analytical_lakehouse.prosigliere_marketing_telemetry
),
account_lifecycle_scoring AS (
    SELECT
        lead_id,
        channel AS last_touch_channel,
        audience_segment,
        conversion_time_days,
        is_converted,
        weibull_shape_k,
        weibull_scale_lambda,
        max_account_ltv_usd,
        cumulative_acquisition_cost_usd,
        total_account_touchpoints,
        event_timestamp AS last_activity_timestamp,

        -- Recency / Retention Tier based on Weibull Scale parameter lambda
        CASE
            WHEN conversion_time_days <= (weibull_scale_lambda * 0.50) THEN 'HIGH_ENGAGEMENT_WINDOW'
            WHEN conversion_time_days <= weibull_scale_lambda THEN 'STABLE_NURTURE_WINDOW'
            ELSE 'ACCELERATING_CHURN_RISK'
        END AS lifecycle_hazard_state,

        -- LTV Decile Rank across active client base
        NTILE(10) OVER (
            ORDER BY max_account_ltv_usd DESC
        ) AS ltv_decile_rank,

        -- Unit ROAS Efficiency Ratio
        CASE
            WHEN cumulative_acquisition_cost_usd > 0
            THEN ROUND((max_account_ltv_usd / cumulative_acquisition_cost_usd)::numeric, 2)
            ELSE 0.0
        END AS account_roas_efficiency
    FROM account_touchpoint_history
    WHERE recency_sequence = 1
),
activation_payload_generation AS (
    SELECT
        lead_id,
        last_touch_channel,
        audience_segment,
        lifecycle_hazard_state,
        ltv_decile_rank,
        account_roas_efficiency,
        max_account_ltv_usd,
        last_activity_timestamp,

        -- Target Reverse ETL Activation Destination
        CASE
            WHEN lifecycle_hazard_state = 'ACCELERATING_CHURN_RISK' AND ltv_decile_rank <= 3
                THEN 'BRAZE_VIP_WINBACK_JOURNEY'
            WHEN is_converted = TRUE AND ltv_decile_rank <= 2
                THEN 'META_LOOKALIKE_HIGH_LTV_SEED'
            WHEN is_converted = FALSE AND lifecycle_hazard_state = 'HIGH_ENGAGEMENT_WINDOW'
                THEN 'GOOGLE_SEARCH_RETARGETING_LIST'
            ELSE 'STANDARD_NURTURE_CAMPAIGN'
        END AS sync_destination_campaign,

        -- Sync priority score based on LTV and urgency
        DENSE_RANK() OVER (
            PARTITION BY lifecycle_hazard_state
            ORDER BY max_account_ltv_usd DESC
        ) AS sync_dispatch_priority
    FROM account_lifecycle_scoring
)
SELECT
    lead_id,
    last_touch_channel,
    audience_segment,
    lifecycle_hazard_state,
    ltv_decile_rank,
    sync_destination_campaign,
    sync_dispatch_priority,
    ROUND(max_account_ltv_usd::numeric, 2) AS max_account_ltv_usd,
    account_roas_efficiency,
    last_activity_timestamp,

    -- Serialized Reverse ETL JSON Payload for Hightouch / Census Webhook
    json_build_object(
        'external_id', lead_id,
        'destination_campaign', sync_destination_campaign,
        'audience_tier', audience_segment,
        'ltv_decile', ltv_decile_rank,
        'realized_ltv', max_account_ltv_usd,
        'lifecycle_state', lifecycle_hazard_state,
        'sync_priority', sync_dispatch_priority,
        'timestamp', last_activity_timestamp
    ) AS reverse_etl_json_payload
FROM activation_payload_generation
WHERE ltv_decile_rank <= 5 OR lifecycle_hazard_state = 'ACCELERATING_CHURN_RISK'
ORDER BY sync_dispatch_priority ASC, max_account_ltv_usd DESC;
