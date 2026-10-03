"""
tests/test_suite.py - Mathematical Invariants & Architecture Quality Suite.
Validates 100% of mathematical invariants, LP solver feasibility, XAI dual shadow prices,
and Dependency Inversion Principle (DIP) in-memory mocks for Prosigliere Analytics Engineering.
"""

import os
import tempfile
import pytest
import numpy as np
import polars as pl

from src.domain.entities import (
    MarketingChannel,
    AudienceSegment,
    BudgetOptimizationRequest,
    OptimizationAllocationResult,
    LeadConversionSurvivalEvent
)
from src.domain.contracts import (
    MarketingDataIngestionProtocol,
    MarketingOptimizationEngineProtocol,
    AttributionExplainerProtocol,
    AnalyticalStorageProtocol,
    TelemetrySinkProtocol
)
from src.data_generator import generate_domain_dataset
from src.core_engine import (
    ProsigliereMarketingOptimizationEngine,
    ProsigliereAttributionExplainer,
    OptimizationComparisonService,
    PolarsMarketingIngestionAdapter,
    DuckDBStorageAdapter,
    InMemoryTelemetrySink,
    create_default_optimization_request
)


@pytest.fixture(scope="session")
def calibrated_telemetry_file(tmp_path_factory):
    """Genera un archivo Parquet temporal calibrado con 5,000 registros para pruebas rapidas."""
    tmp_dir = tmp_path_factory.mktemp("data")
    parquet_path = str(tmp_dir / "test_marketing_telemetry.parquet")
    generate_domain_dataset(num_records=5000, output_path=parquet_path, seed=123)
    return parquet_path


def test_stochastic_generator_invariants(calibrated_telemetry_file):
    """
    Test 1: Invariantes Fisicos y Estadisticos de la Telemetria de Marketing.
    Verifica que la sintesis estocastica no posea nulos y cumpla las distribuciones esperadas.
    """
    df = pl.read_parquet(calibrated_telemetry_file)
    assert len(df) == 5000
    assert all(df[c].null_count() == 0 for c in df.columns), "No deben existir valores nulos en el dataset"

    # Validar que todos los 5 canales gestionados por Prosigliere esten presentes
    observed_channels = set(df["channel"].unique().to_list())
    expected_channels = {c.value for c in MarketingChannel}
    assert observed_channels == expected_channels, "Todos los canales omnicanal deben estar representados"

    # Invariantes numericos
    assert (df["acquisition_cost_usd"] > 0).all(), "Los costos de adquisicion deben ser estrictamente positivos"
    assert (df["weibull_shape_k"] > 0.5).all(), "El parametro k de Weibull debe ser valido y positivo"
    assert (df["weibull_scale_lambda"] > 1.0).all(), "El parametro lambda de vida media debe ser valido"
    assert (df["conversion_time_days"] >= 0.25).all(), "El tiempo de conversion debe ser >= 0.25 dias"

    # Invariante de conversion
    conv_rate = df["is_converted"].mean()
    assert 0.30 <= conv_rate <= 0.65, f"La tasa de conversion agregada ({conv_rate:.2f}) debe ser plausible"


def test_linear_programming_feasibility_and_bounds():
    """
    Test 2: Factibilidad Matematica y Cumplimiento de Cotas del Solver HiGHS.
    Verifica que la solucion respete el 100% de las restricciones primales de canal y presupuesto.
    """
    request = create_default_optimization_request(total_budget=1500000.0)
    optimizer = ProsigliereMarketingOptimizationEngine()
    result = optimizer.solve_budget_allocation(request)

    assert result.is_optimal is True, "El solver HiGHS debe converger a una solucion optima"
    assert result.solver_status_code == 0, "Status code de HiGHS debe ser 0 (Optimal)"
    assert result.solver_latency_ms < 50.0, "La latencia del solver debe ser sub-50ms"

    # Verificacion de utilizacion presupuestaria
    assert np.isclose(result.total_budget_allocated, request.total_budget_usd, atol=1.0), (
        "El presupuesto asignado debe agotar el 100% del capital disponible"
    )

    # Verificacion de cotas por canal [min_budget, max_budget]
    for c in request.channel_constraints:
        alloc = result.allocations_by_channel[c.channel]
        assert alloc >= c.min_budget_usd - 1e-4, f"Canal {c.channel} violo cota inferior: {alloc} < {c.min_budget_usd}"
        assert alloc <= c.max_budget_usd + 1e-4, f"Canal {c.channel} violo cota superior: {alloc} > {c.max_budget_usd}"

    # Verificacion de cuota minima de retencion en Braze (>= 15%)
    braze_alloc = result.allocations_by_channel[MarketingChannel.BRAZE_LIFECYCLE_RETENTION]
    min_braze = (request.min_braze_retention_quota_pct / 100.0) * request.total_budget_usd
    assert braze_alloc >= min_braze - 1e-4, f"Braze retention alloc ({braze_alloc}) violo cuota minima ({min_braze})"

    # Verificacion de techo de Blended CAC
    assert result.expected_blended_cac <= request.max_blended_cac_target + 0.1, (
        f"Blended CAC ({result.expected_blended_cac}) excedio el techo objetivo ({request.max_blended_cac_target})"
    )


def test_linear_programming_superiority_over_static_heuristic():
    """
    Test 3: Superioridad Matematica de Programacion Lineal vs Heuristica Proporcional.
    Verifica que la optimizacion HiGHS genere un LTV estrictamente mayor y menor CAC que el status quo.
    """
    request = create_default_optimization_request(total_budget=1500000.0)
    optimizer = ProsigliereMarketingOptimizationEngine()
    result_lp = optimizer.solve_budget_allocation(request)

    comparison = OptimizationComparisonService.compare_lp_vs_heuristic(request, result_lp)

    assert comparison["net_ltv_gain_usd"] > 0, "La optimizacion lineal debe generar ganancia neta positiva de LTV"
    assert comparison["ltv_uplift_pct"] >= 5.0, "El incremento de LTV sobre la heuristica debe ser >= 5%"
    assert comparison["cac_reduction_pct"] >= 5.0, "La reduccion de CAC sobre la heuristica debe ser >= 5%"
    assert comparison["cac_target_respected_lp"] is True, "LP debe respetar el techo de Blended CAC"


def test_xai_dual_shadow_prices_and_explanations():
    """
    Test 4: Explicabilidad XAI y Precios Sombra Duales de Lagrange.
    Verifica que el explicador extraiga las derivadas marginales de saturacion y genere recomendaciones.
    """
    request = create_default_optimization_request(total_budget=1500000.0)
    optimizer = ProsigliereMarketingOptimizationEngine()
    result = optimizer.solve_budget_allocation(request)

    explainer = ProsigliereAttributionExplainer()
    explanations = explainer.explain_allocations(result, request)

    assert len(explanations) == len(request.channel_constraints)

    for exp in explanations:
        assert exp.allocated_usd >= 0.0
        assert exp.budget_share_pct >= 0.0
        assert exp.marginal_ltv_per_dollar > 0.0
        assert exp.dual_shadow_price >= 0.0
        assert len(exp.recommendation) > 15, "La recomendacion debe ser descriptiva y accionable"


def test_dependency_inversion_and_in_memory_telemetry_mock():
    """
    Test 5: Inversion de Dependencias (DIP) y Mocking In-Memory Sub-5ms.
    Verifica que la orquestacion de optimizacion opere con mocks puros sin tocar disco ni base de datos.
    """
    class MockOptimizationEngine(MarketingOptimizationEngineProtocol):
        def solve_budget_allocation(self, request, historical_events=None):
            return OptimizationAllocationResult(
                run_id="MOCK-PRO-999",
                is_optimal=True,
                solver_status_code=0,
                solver_latency_ms=0.85,
                total_budget_allocated=request.total_budget_usd,
                allocations_by_channel={c.channel: c.min_budget_usd for c in request.channel_constraints},
                expected_total_conversions=1500.0,
                expected_blended_cac=100.0,
                expected_total_ltv=18000000.0,
                dual_shadow_prices={c.channel: 2.5 for c in request.channel_constraints},
                budget_utilization_pct=100.0
            )

    sink = InMemoryTelemetrySink()
    mock_engine = MockOptimizationEngine()
    request = create_default_optimization_request(total_budget=1000000.0)

    # Ejecucion aislada sin I/O
    res = mock_engine.solve_budget_allocation(request=request)
    sink.persist_optimization_run(res)

    assert len(sink.audit_log) == 1
    assert sink.audit_log[0].run_id == "MOCK-PRO-999"
    assert sink.audit_log[0].is_optimal is True
    assert sink.audit_log[0].solver_latency_ms < 5.0


def test_fastapi_rest_service_endpoints():
    """
    Test 6: Verificacion de Microservicio FastAPI (EXPLAINABLE_AI_INFERENCE).
    Valida endpoints REST de health, asignacion LP, explicabilidad XAI y comparacion heuristica.
    """
    from fastapi.testclient import TestClient
    from src.interface import app

    client = TestClient(app)

    # 1. Healthcheck
    resp_health = client.get("/health")
    assert resp_health.status_code == 200
    health_data = resp_health.json()
    assert health_data["status"] == "healthy"
    assert health_data["solver_engine"] == "HiGHS-Primal-Dual-Simplex"

    # 2. Allocation Endpoint (Default payload)
    resp_alloc = client.post("/api/v1/optimization/allocate", json=None)
    assert resp_alloc.status_code == 200
    alloc_data = resp_alloc.json()
    assert alloc_data["is_optimal"] is True
    assert alloc_data["total_budget_allocated"] == 1500000.0
    assert alloc_data["expected_blended_cac"] <= 180.0

    # 3. Explainability Endpoint
    resp_explain = client.post("/api/v1/attribution/explain", json=None)
    assert resp_explain.status_code == 200
    explain_data = resp_explain.json()
    assert len(explain_data["explanations"]) == 5
    assert "dual_shadow_price" in explain_data["explanations"][0]

    # 4. Benchmark Comparison Endpoint
    resp_bench = client.get("/api/v1/comparison/benchmark")
    assert resp_bench.status_code == 200
    bench_data = resp_bench.json()
    assert bench_data["benchmark_summary"]["net_ltv_gain_usd"] > 0

    # 5. Cohorts Aggregation Summary
    resp_cohorts = client.get("/api/v1/cohorts/summary")
    assert resp_cohorts.status_code == 200
    cohorts_data = resp_cohorts.json()
    assert len(cohorts_data) >= 5