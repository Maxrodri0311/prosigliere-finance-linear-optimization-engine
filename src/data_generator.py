"""
src/data_generator.py - Calibrated Stochastic Marketing & Lifecycle Telemetry Generator.
Physics: Omnichannel Marketing Attribution & Weibull Survival Dynamics for Supply Chain & Analytics Engineering Practice.
Simulates high-velocity lead interactions across Google Ads, Meta Ads, Braze, Reverse ETL,
and TikTok Acquisition with empirical conversion and hazard physics.
"""

import os
import sys
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import polars as pl

# Standalone execution path resolution
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.domain.entities import MarketingChannel, AudienceSegment


# Calibration parameters per channel
CHANNEL_PHYSICS_PROFILES = {
    MarketingChannel.GOOGLE_SEARCH_CORE.value: {
        "share": 0.28,
        "cac_mean": 165.0,
        "cac_std": 25.0,
        "shape_k": 1.85,
        "scale_lambda": 24.0,
        "base_conversion_rate": 0.42,
        "ltv_multiplier": 11.5
    },
    MarketingChannel.META_PERFORMANCE_MAX.value: {
        "share": 0.26,
        "cac_mean": 115.0,
        "cac_std": 18.0,
        "shape_k": 1.30,
        "scale_lambda": 14.0,
        "base_conversion_rate": 0.35,
        "ltv_multiplier": 8.4
    },
    MarketingChannel.BRAZE_LIFECYCLE_RETENTION.value: {
        "share": 0.20,
        "cac_mean": 48.0,
        "cac_std": 8.5,
        "shape_k": 2.20,
        "scale_lambda": 48.0,
        "base_conversion_rate": 0.68,
        "ltv_multiplier": 15.6
    },
    MarketingChannel.REVERSE_ETL_REMARKETING.value: {
        "share": 0.16,
        "cac_mean": 88.0,
        "cac_std": 14.0,
        "shape_k": 1.65,
        "scale_lambda": 21.0,
        "base_conversion_rate": 0.52,
        "ltv_multiplier": 12.2
    },
    MarketingChannel.TIKTOK_ACQUISITION.value: {
        "share": 0.10,
        "cac_mean": 95.0,
        "cac_std": 22.0,
        "shape_k": 1.10,
        "scale_lambda": 9.0,
        "base_conversion_rate": 0.24,
        "ltv_multiplier": 6.8
    }
}

SEGMENT_LTV_PROFILES = {
    AudienceSegment.ENTERPRISE_HIGH_INTENT.value: {
        "share": 0.25,
        "ltv_min": 3500.0,
        "ltv_max": 14000.0,
        "conversion_boost": 1.30
    },
    AudienceSegment.MIDMARKET_ENGAGED.value: {
        "share": 0.45,
        "ltv_min": 1200.0,
        "ltv_max": 4200.0,
        "conversion_boost": 1.05
    },
    AudienceSegment.SMB_TRANSACTIONAL.value: {
        "share": 0.30,
        "ltv_min": 350.0,
        "ltv_max": 1500.0,
        "conversion_boost": 0.85
    }
}


def generate_domain_dataset(
    num_records: int = 50000,
    output_path: str = "data/raw_dataset.parquet",
    seed: int = 42
) -> pl.DataFrame:
    """
    Sintetiza telemetria estocastica de marketing omnicanal y retencion para Supply Chain & Analytics Engineering Practice.
    Aplica la fisica de supervivencia de Weibull para modelar el tiempo hasta conversion o churn.
    """
    print(f"[*] [Data Generator] Simulating {num_records:,} calibrated omnichannel marketing lead records for Supply Chain & Analytics Engineering Practice...")
    start_time = time.perf_counter()
    rng = np.random.default_rng(seed)

    # 1. Identificadores unicos
    lead_ids = [f"LEAD-PRO-{i:07d}" for i in range(1, num_records + 1)]

    # 2. Asignacion estocastica de canales
    channel_names = list(CHANNEL_PHYSICS_PROFILES.keys())
    channel_probs = [CHANNEL_PHYSICS_PROFILES[c]["share"] for c in channel_names]
    assigned_channels = rng.choice(channel_names, size=num_records, p=channel_probs)

    # 3. Asignacion estocastica de segmentos de audiencia
    segment_names = list(SEGMENT_LTV_PROFILES.keys())
    segment_probs = [SEGMENT_LTV_PROFILES[s]["share"] for s in segment_names]
    assigned_segments = rng.choice(segment_names, size=num_records, p=segment_probs)

    # 4. Parametros fisicos y de supervivencia vectorizados
    cac_values = np.empty(num_records, dtype=np.float64)
    shape_k_values = np.empty(num_records, dtype=np.float64)
    scale_lambda_values = np.empty(num_records, dtype=np.float64)
    conversion_prob_base = np.empty(num_records, dtype=np.float64)
    ltv_multipliers = np.empty(num_records, dtype=np.float64)

    for c in channel_names:
        idx = (assigned_channels == c)
        count = np.sum(idx)
        if count == 0:
            continue
        prof = CHANNEL_PHYSICS_PROFILES[c]
        cac_values[idx] = np.maximum(prof["cac_mean"] + rng.normal(0, prof["cac_std"], count), 15.0)
        shape_k_values[idx] = prof["shape_k"] + rng.uniform(-0.08, 0.08, count)
        scale_lambda_values[idx] = np.maximum(prof["scale_lambda"] + rng.normal(0, 2.5, count), 3.0)
        conversion_prob_base[idx] = prof["base_conversion_rate"]
        ltv_multipliers[idx] = prof["ltv_multiplier"]

    # 5. Ajuste de probabilidad por segmento de audiencia
    segment_boosts = np.array([SEGMENT_LTV_PROFILES[s]["conversion_boost"] for s in assigned_segments])
    effective_conv_prob = np.clip(conversion_prob_base * segment_boosts, 0.05, 0.95)
    random_draws = rng.uniform(0.0, 1.0, num_records)
    is_converted = random_draws < effective_conv_prob

    # 6. Simulacion de tiempo hasta evento (Weibull Distribution t = lambda * (-ln(U))^(1/k))
    uniform_decay = rng.uniform(0.001, 0.999, num_records)
    conversion_times = scale_lambda_values * np.power(-np.log(uniform_decay), 1.0 / shape_k_values)
    conversion_times = np.round(np.clip(conversion_times, 0.25, 90.0), 2)

    # 7. Asignacion de LTV realizado segun segmento y conversion
    realized_ltvs = np.zeros(num_records, dtype=np.float64)
    for s in segment_names:
        s_idx = (assigned_segments == s) & is_converted
        s_count = np.sum(s_idx)
        if s_count == 0:
            continue
        prof_s = SEGMENT_LTV_PROFILES[s]
        base_ltv = rng.uniform(prof_s["ltv_min"], prof_s["ltv_max"], s_count)
        realized_ltvs[s_idx] = base_ltv * (ltv_multipliers[s_idx] / 10.0)

    # 8. Marcas de tiempo de eventos dentro de un periodo de 180 dias
    base_timestamp = datetime(2026, 1, 1, 0, 0, 0)
    random_offsets = rng.uniform(0, 180 * 86400, num_records)
    event_timestamps = [base_timestamp + timedelta(seconds=float(offset)) for offset in random_offsets]

    # 9. Construccion del DataFrame Polars columnar de alta velocidad
    df = pl.DataFrame({
        "lead_id": lead_ids,
        "channel": assigned_channels,
        "audience_segment": assigned_segments,
        "acquisition_cost_usd": np.round(cac_values, 2),
        "conversion_time_days": conversion_times,
        "is_converted": is_converted,
        "weibull_shape_k": np.round(shape_k_values, 4),
        "weibull_scale_lambda": np.round(scale_lambda_values, 4),
        "realized_ltv_usd": np.round(realized_ltvs, 2),
        "event_timestamp": event_timestamps
    })

    # 10. Persistencia columnar en Parquet
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(str(dest), compression="snappy")

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    converted_count = int(df["is_converted"].sum())
    total_spend = float(df["acquisition_cost_usd"].sum())
    total_ltv = float(df["realized_ltv_usd"].sum())

    print(f"[*] [Data Generator] Successfully synthesized {num_records:,} records in {elapsed_ms:.1f}ms -> {output_path}")
    print(f"    Converted Accounts: {converted_count:,} ({converted_count/num_records*100:.1f}%) | "
          f"Total Spend: ${total_spend:,.2f} | Total LTV Pipeline: ${total_ltv:,.2f}")

    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate calibrated omnichannel marketing telemetry.")
    parser.add_argument("--records", type=int, default=50000, help="Number of records to synthesize")
    parser.add_argument("--output", type=str, default="data/raw_dataset.parquet", help="Destination path")
    parser.add_argument("--seed", type=int, default=42, help="Stochastic RNG seed")
    args = parser.parse_args()

    generate_domain_dataset(
        num_records=args.records,
        output_path=args.output,
        seed=args.seed
    )