-- ==============================================================================
-- Prosigliere Analytics Engineering - Multi-Touch Markov Attribution Model
-- Target Engine : PostgreSQL 16 / Snowflake / BigQuery Compatible
-- Domain Scope  : State Transition Matrices, Removal Effects & Dynamic Journey Weights
-- ==============================================================================

WITH journey_ordered_touches AS (
    SELECT
        lead_id,
        channel,
        event_timestamp,
        is_converted,
        ROW_NUMBER() OVER (
            PARTITION BY lead_id
            ORDER BY event_timestamp ASC
        ) AS touch_step,
        LEAD(channel, 1) OVER (
            PARTITION BY lead_id
            ORDER BY event_timestamp ASC
        ) AS next_channel,
        LAST_VALUE(is_converted) OVER (
            PARTITION BY lead_id
            ORDER BY event_timestamp ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS journey_converted
    FROM analytical_lakehouse.prosigliere_marketing_telemetry
),
transition_pairs AS (
    SELECT
        channel AS from_state,
        COALESCE(
            next_channel,
            CASE WHEN journey_converted THEN '(CONVERSION)' ELSE '(CHURN)' END
        ) AS to_state,
        COUNT(*) AS transition_count
    FROM journey_ordered_touches
    GROUP BY
        channel,
        COALESCE(
            next_channel,
            CASE WHEN journey_converted THEN '(CONVERSION)' ELSE '(CHURN)' END
        )
),
transition_probabilities AS (
    SELECT
        from_state,
        to_state,
        transition_count,
        SUM(transition_count) OVER (
            PARTITION BY from_state
        ) AS total_from_transitions,
        ROUND(
            (transition_count::numeric / SUM(transition_count) OVER (PARTITION BY from_state))::numeric,
            4
        ) AS transition_probability
    FROM transition_pairs
),
channel_removal_effect_simulation AS (
    SELECT
        from_state AS channel,
        SUM(CASE WHEN to_state = '(CONVERSION)' THEN transition_count ELSE 0 END) AS direct_conversions,
        SUM(transition_count) AS total_engagements,
        ROUND(
            (SUM(CASE WHEN to_state = '(CONVERSION)' THEN transition_count ELSE 0 END)::numeric / 
             NULLIF(SUM(transition_count), 0))::numeric, 4
        ) AS unconditioned_conversion_rate
    FROM transition_pairs
    WHERE from_state NOT IN ('(CONVERSION)', '(CHURN)')
    GROUP BY from_state
)
SELECT
    tp.from_state,
    tp.to_state,
    tp.transition_count,
    tp.transition_probability,
    cr.direct_conversions,
    cr.unconditioned_conversion_rate,

    -- Window rank of dominant pathways
    DENSE_RANK() OVER (
        PARTITION BY tp.from_state
        ORDER BY tp.transition_count DESC
    ) AS transition_dominance_rank
FROM transition_probabilities tp
LEFT JOIN channel_removal_effect_simulation cr ON tp.from_state = cr.channel
ORDER BY tp.from_state ASC, tp.transition_count DESC;
