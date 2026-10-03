#!/usr/bin/env bash
set -euo pipefail

echo "================================================================================"
echo "  PROSIGLIERE: OMNICHANNEL ATTRIBUTION AND LINEAR OPTIMIZATION ENGINE"
echo "  Automated Execution, Mathematical Invariants and Quantitative Benchmarks"
echo "================================================================================"
echo ""

echo "[1/5] Executing Production Quality and CI/CD Security Guards..."
python scripts/validate_no_credentials.py
python scripts/validate_no_internal_leaks.py
python scripts/validate_sql_complexity.py
python scripts/validate_sql_minimum_viable.py
python scripts/validate_terraform_minimum_viable.py
python scripts/validate_byte_budget.py

echo ""
echo "[2/5] Synthesizing Calibrated Omnichannel Marketing Dataset (50,000 observations)..."
python src/data_generator.py --records 50000

echo ""
echo "[3/5] Solving HiGHS Linear Programming and Dual Shadow Prices..."
python src/core_engine.py

echo ""
echo "[4/5] Executing Mathematical Invariants and Test Suite..."
python -m pytest tests/ -v

echo ""
echo "[5/5] Running Quantitative Latency and Throughput Benchmarks (30 iterations)..."
python tests/benchmark.py

echo ""
echo "================================================================================"
echo "  Execution Complete: All Invariants, Security and Latency SLAs Verified!"
echo "================================================================================"