"""
tests/benchmark.py - Quantitative Latency & Memory Benchmark.
Evaluates high-throughput performance over 30 iterations:
  1. Ingestion & Columnar Filtering SLA (p95 < 100.0 ms)
  2. Constrained Linear Programming Solver SLA (p95 < 150.0 ms)
  3. Peak Heap Allocation Profile (Peak < 15.0 MB)
"""

import os
import sys
import time
import tempfile
import tracemalloc
from pathlib import Path
import numpy as np

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.data_generator import generate_domain_dataset
from src.core_engine import (
    ProsigliereMarketingOptimizationEngine,
    ProsigliereAttributionExplainer,
    create_default_optimization_request,
    PolarsMarketingIngestionAdapter,
    DuckDBStorageAdapter,
    DomainAnalyticsEngine
)


def run_quantitative_benchmarks(iterations: int = 30, num_records: int = 10000):
    print(f"[*] [Benchmark] Synthesizing calibrated marketing dataset ({num_records:,} observations)...")
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        generate_domain_dataset(num_records=num_records, output_path=tmp_path, seed=42)

        # ----------------------------------------------------------------------
        # Benchmark 1: Ingestion & Columnar Parquet Parse Latency
        # ----------------------------------------------------------------------
        adapter = PolarsMarketingIngestionAdapter()
        ingestion_latencies = []

        # Warmup
        adapter.load_lead_telemetry(tmp_path, limit=1000)

        for _ in range(iterations):
            t0 = time.perf_counter()
            adapter.load_lead_telemetry(tmp_path, limit=1000)
            ingestion_latencies.append((time.perf_counter() - t0) * 1000.0)

        ing_p50 = float(np.percentile(ingestion_latencies, 50))
        ing_p95 = float(np.percentile(ingestion_latencies, 95))
        ing_p99 = float(np.percentile(ingestion_latencies, 99))

        # ----------------------------------------------------------------------
        # Benchmark 2: Constrained Linear Programming Solver Latency
        # ----------------------------------------------------------------------
        optimizer = ProsigliereMarketingOptimizationEngine()
        explainer = ProsigliereAttributionExplainer()
        request = create_default_optimization_request(total_budget=1500000.0)
        solver_latencies = []

        # Warmup
        optimizer.solve_budget_allocation(request)

        for _ in range(iterations):
            t0 = time.perf_counter()
            res = optimizer.solve_budget_allocation(request)
            explainer.explain_allocations(res, request)
            solver_latencies.append((time.perf_counter() - t0) * 1000.0)

        solv_p50 = float(np.percentile(solver_latencies, 50))
        solv_p95 = float(np.percentile(solver_latencies, 95))
        solv_p99 = float(np.percentile(solver_latencies, 99))
        throughput_ops = 1000.0 / solv_p50 if solv_p50 > 0 else 0.0

        # ----------------------------------------------------------------------
        # Benchmark 3: Memory Footprint Profile (tracemalloc)
        # ----------------------------------------------------------------------
        tracemalloc.start()
        snapshot_start = tracemalloc.take_snapshot()

        for _ in range(10):
            res = optimizer.solve_budget_allocation(request)
            explainer.explain_allocations(res, request)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_mb = peak / (1024 * 1024)

        # ----------------------------------------------------------------------
        # Report & SLA Enforcement
        # ----------------------------------------------------------------------
        print("\n" + "=" * 74)
        print("  PROSIGLIERE MARKETING LINEAR OPTIMIZATION - QUANTITATIVE BENCHMARK")
        print("=" * 74)
        print(f"  Dataset Population       : {num_records:,} historical lead observations")
        print(f"  Profiling Iterations     : {iterations} passes")
        print(f"  Batch Lead Ingestion     : 1,000 active leads")
        print("-" * 74)
        print("  1. Columnar Ingestion & Parquet Parse (Polars):")
        print(f"     -> p50: {ing_p50:.2f} ms | p95: {ing_p95:.2f} ms | p99: {ing_p99:.2f} ms")
        print(f"     -> Production SLA Target : p95 < 100.0 ms [{'PASS' if ing_p95 < 100.0 else 'FAIL'}]")
        print("-" * 74)
        print("  2. Constrained Linear Programming Solver (SciPy HiGHS + XAI Shadows):")
        print(f"     -> p50: {solv_p50:.2f} ms | p95: {solv_p95:.2f} ms | p99: {solv_p99:.2f} ms")
        print(f"     -> Solver Throughput     : {throughput_ops:.1f} optimizations/sec")
        print(f"     -> Production SLA Target : p95 < 150.0 ms [{'PASS' if solv_p95 < 150.0 else 'FAIL'}]")
        print("-" * 74)
        print("  3. Memory Footprint Profile (tracemalloc):")
        print(f"     -> Peak Heap Allocation  : {peak_mb:.2f} MB [SLA < 15.0 MB: {'PASS' if peak_mb < 15.0 else 'FAIL'}]")
        print("=" * 74)

        assert ing_p95 < 100.0, f"Ingestion SLA breached: p95 = {ing_p95:.2f}ms >= 100ms"
        assert solv_p95 < 150.0, f"Solver SLA breached: p95 = {solv_p95:.2f}ms >= 150ms"
        assert peak_mb < 15.0, f"Memory SLA breached: Peak = {peak_mb:.2f}MB >= 15MB"

        print("  [+] All quantitative SLA and memory constraints verified successfully.\n")

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    run_quantitative_benchmarks()