"""
src/core_engine.py - Core Algorithmic & Optimization Engine for Prosigliere.
Implements Constrained Linear Programming (SciPy HiGHS) with Dual Shadow Price XAI.
Strictly decoupled via Dependency Inversion Principle (DIP).
"""

import os
import sys
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import duckdb
import numpy as np
import pandas as pd
import polars as pl
from scipy.optimize import linprog

# Standalone execution path resolution
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.domain.entities import (
    MarketingChannel,
    AudienceSegment,
    LeadConversionSurvivalEvent,
    ChannelBudgetConstraint,
    BudgetOptimizationRequest,
    OptimizationAllocationResult,
    ChannelAttributionExplanation
)
from src.domain.contracts import (
    MarketingDataIngestionProtocol,
    MarketingOptimizationEngineProtocol,
    AttributionExplainerProtocol,
    AnalyticalStorageProtocol,
    TelemetrySinkProtocol
)


# ============================================================================
# 1. INFRASTRUCTURE ADAPTERS (DIP IMPLEMENTATIONS)
# ============================================================================

class DuckDBStorageAdapter(AnalyticalStorageProtocol):
    """Adaptador de infraestructura desacoplado para OLAP local en memoria."""
    def __init__(self, database: str = ":memory:"):
        self.conn = duckdb.connect(database)

    def execute_query(self, query: str) -> pd.DataFrame:
        return self.conn.execute(query).df()

    def scan_dataset(self, base_path: str) -> pd.DataFrame:
        return self.conn.execute(f"SELECT * FROM read_parquet('{base_path}');").df()


class InMemoryTelemetrySink(TelemetrySinkProtocol):
    """Sink de telemetria en memoria para auditoria y testeo sin I/O de disco."""
    def __init__(self):
        self.audit_log: List[OptimizationAllocationResult] = []

    def persist_optimization_run(self, result: OptimizationAllocationResult) -> None:
        self.audit_log.append(result)


class PolarsMarketingIngestionAdapter(MarketingDataIngestionProtocol):
    """Adaptador de ingesta columnar de alto rendimiento para telemetria de marketing."""
    def load_lead_telemetry(
        self,
        file_path: str,
        limit: Optional[int] = None
    ) -> List[LeadConversionSurvivalEvent]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Marketing telemetry parquet not found at {file_path}")

        df = pl.read_parquet(file_path)
        if limit and limit > 0:
            df = df.head(limit)

        raw_dicts = df.to_dicts()
        return [
            LeadConversionSurvivalEvent(
                lead_id=r["lead_id"],
                channel=MarketingChannel(r["channel"]),
                audience_segment=AudienceSegment(r["audience_segment"]),
                acquisition_cost_usd=float(r["acquisition_cost_usd"]),
                conversion_time_days=float(r["conversion_time_days"]),
                is_converted=bool(r["is_converted"]),
                weibull_shape_k=float(r["weibull_shape_k"]),
                weibull_scale_lambda=float(r["weibull_scale_lambda"]),
                realized_ltv_usd=float(r["realized_ltv_usd"])
            )
            for r in raw_dicts
        ]


# ============================================================================
# 2. CORE OPTIMIZATION & XAI ENGINES
# ============================================================================

class ProsigliereMarketingOptimizationEngine(MarketingOptimizationEngineProtocol):
    """
    Motor de Optimizacion Lineal Primal-Dual para Prosigliere Analytics Engineering.
    Maximiza el LTV Total Adquirido sujeto a:
      - Presupuesto Total Trimestral B
      - Techo Estricto de CAC Promedio Blended
      - Cuota Minima de Retencion de Ciclo de Vida en Braze (>= 15%)
      - Cotas de Saturacion y Capacidad por Canal [min_budget, max_budget]
    """
    def solve_budget_allocation(
        self,
        request: BudgetOptimizationRequest,
        historical_events: Optional[List[LeadConversionSurvivalEvent]] = None
    ) -> OptimizationAllocationResult:
        start_time = time.perf_counter()

        constraints = request.channel_constraints
        n_channels = len(constraints)
        channel_list = [c.channel for c in constraints]

        # 1. Vector de Costo c (Maximizar LTV <=> Minimizar -LTV)
        c = np.array([-c.expected_ltv_multiplier for c in constraints], dtype=np.float64)

        # 2. Matriz de Desigualdad A_ub * x <= b_ub
        # Restriccion 1: Gasto Total <= Presupuesto Global
        # sum(x_j) <= total_budget
        row_budget = np.ones(n_channels, dtype=np.float64)
        b_budget = request.total_budget_usd

        # Restriccion 2: Techo de Blended CAC
        # sum(x_j / CAC_j) >= total_budget / max_cac <=> -sum(1/CAC_j * x_j) <= -total_budget / max_cac
        row_cac = np.array([-1.0 / c.historical_cac for c in constraints], dtype=np.float64)
        min_conversions_required = request.total_budget_usd / request.max_blended_cac_target
        b_cac = -min_conversions_required

        # Restriccion 3: Cuota Minima de Retencion en Braze
        # x_braze >= quota_pct * total_budget <=> -x_braze <= -quota_pct * total_budget
        row_braze = np.zeros(n_channels, dtype=np.float64)
        braze_idx = None
        for i, ch in enumerate(channel_list):
            if ch == MarketingChannel.BRAZE_LIFECYCLE_RETENTION:
                braze_idx = i
                break

        if braze_idx is not None:
            row_braze[braze_idx] = -1.0
            min_braze_spend = (request.min_braze_retention_quota_pct / 100.0) * request.total_budget_usd
            b_braze = -min_braze_spend
            A_ub = np.vstack([row_budget, row_cac, row_braze])
            b_ub = np.array([b_budget, b_cac, b_braze], dtype=np.float64)
        else:
            A_ub = np.vstack([row_budget, row_cac])
            b_ub = np.array([b_budget, b_cac], dtype=np.float64)

        # 3. Cotas de Capacidad [min_budget, max_budget]
        bounds = [(c.min_budget_usd, c.max_budget_usd) for c in constraints]

        # 4. Invocacion del Solver HiGHS Primal-Dual Simplex
        res = linprog(
            c=c,
            A_ub=A_ub,
            b_ub=b_ub,
            bounds=bounds,
            method="highs",
            options={"disp": False, "presolve": True}
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if not res.success:
            return OptimizationAllocationResult(
                run_id=f"RUN-{uuid.uuid4().hex[:8].upper()}",
                is_optimal=False,
                solver_status_code=int(res.status),
                solver_latency_ms=np.round(latency_ms, 2),
                total_budget_allocated=0.0,
                allocations_by_channel={c.channel: 0.0 for c in constraints},
                expected_total_conversions=0.0,
                expected_blended_cac=0.0,
                expected_total_ltv=0.0,
                dual_shadow_prices={c.channel: 0.0 for c in constraints},
                budget_utilization_pct=0.0
            )

        # 5. Extraccion de Resultados Primales
        alloc_vector = res.x
        allocations = {
            constraints[i].channel: float(np.round(alloc_vector[i], 2))
            for i in range(n_channels)
        }

        total_allocated = float(np.sum(alloc_vector))
        expected_conversions = float(sum(
            alloc_vector[i] / constraints[i].historical_cac
            for i in range(n_channels)
        ))
        expected_ltv = float(sum(
            alloc_vector[i] * constraints[i].expected_ltv_multiplier
            for i in range(n_channels)
        ))
        blended_cac = total_allocated / expected_conversions if expected_conversions > 0 else 0.0
        utilization_pct = (total_allocated / request.total_budget_usd) * 100.0

        # 6. Extraccion de Precios Sombra Duales XAI (Marginal Return on Capacity)
        dual_shadows: Dict[MarketingChannel, float] = {}
        if hasattr(res, "upper") and hasattr(res.upper, "marginals") and res.upper.marginals is not None:
            for i, c in enumerate(constraints):
                raw_dual = float(res.upper.marginals[i])
                dual_shadows[c.channel] = float(np.round(abs(raw_dual), 4))
        else:
            for c in constraints:
                dual_shadows[c.channel] = 0.0

        return OptimizationAllocationResult(
            run_id=f"RUN-{uuid.uuid4().hex[:8].upper()}",
            is_optimal=True,
            solver_status_code=int(res.status),
            solver_latency_ms=np.round(latency_ms, 2),
            total_budget_allocated=np.round(total_allocated, 2),
            allocations_by_channel=allocations,
            expected_total_conversions=np.round(expected_conversions, 2),
            expected_blended_cac=np.round(blended_cac, 2),
            expected_total_ltv=np.round(expected_ltv, 2),
            dual_shadow_prices=dual_shadows,
            budget_utilization_pct=np.round(utilization_pct, 2)
        )


class ProsigliereAttributionExplainer(AttributionExplainerProtocol):
    """Generador de Explicabilidad XAI para Directores de Growth y Liderazgo Ejecutivo."""
    def explain_allocations(
        self,
        result: OptimizationAllocationResult,
        request: BudgetOptimizationRequest
    ) -> List[ChannelAttributionExplanation]:
        explanations: List[ChannelAttributionExplanation] = []
        constraint_map = {c.channel: c for c in request.channel_constraints}
        total_alloc = max(result.total_budget_allocated, 1.0)
        total_ltv = max(result.expected_total_ltv, 1.0)

        for channel, alloc_usd in result.allocations_by_channel.items():
            c = constraint_map[channel]
            share_pct = (alloc_usd / total_alloc) * 100.0
            channel_ltv = alloc_usd * c.expected_ltv_multiplier
            attr_weight = (channel_ltv / total_ltv) * 100.0
            dual_price = result.dual_shadow_prices.get(channel, 0.0)

            # Recomendacion prescriptiva accionable
            if alloc_usd >= c.max_budget_usd * 0.95:
                rec = "Canal en saturacion optima; aumentar techo presupuestario en Q+1 para capturar LTV marginal."
            elif alloc_usd <= c.min_budget_usd * 1.05:
                rec = "Canal en cota minima obligatoria; bajo retorno relativo frente a canales de retencion."
            else:
                rec = "Asignacion balanceada; opera en punto dulce de eficiencia de CAC y conversion."

            explanations.append(ChannelAttributionExplanation(
                channel=channel,
                allocated_usd=alloc_usd,
                budget_share_pct=np.round(share_pct, 2),
                marginal_ltv_per_dollar=np.round(c.expected_ltv_multiplier, 2),
                dual_shadow_price=dual_price,
                attribution_weight_pct=np.round(attr_weight, 2),
                recommendation=rec
            ))

        return explanations


class OptimizationComparisonService:
    """Servicio comparativo: Programacion Lineal Restringida vs Heuristica Proporcional Estatica."""
    @staticmethod
    def compare_lp_vs_heuristic(
        request: BudgetOptimizationRequest,
        result_lp: OptimizationAllocationResult
    ) -> Dict[str, Any]:
        constraints = request.channel_constraints
        total_budget = request.total_budget_usd

        # Heuristica Estatica: Distribucion Proporcional a Limites Maximos
        max_sum = sum(c.max_budget_usd for c in constraints)
        heuristic_allocs = {
            c.channel: np.round((c.max_budget_usd / max_sum) * total_budget, 2)
            for c in constraints
        }
        heuristic_conversions = sum(
            heuristic_allocs[c.channel] / c.historical_cac for c in constraints
        )
        heuristic_ltv = sum(
            heuristic_allocs[c.channel] * c.expected_ltv_multiplier for c in constraints
        )
        heuristic_cac = total_budget / heuristic_conversions if heuristic_conversions > 0 else 0.0

        ltv_uplift_pct = ((result_lp.expected_total_ltv - heuristic_ltv) / heuristic_ltv) * 100.0
        cac_reduction_pct = ((heuristic_cac - result_lp.expected_blended_cac) / heuristic_cac) * 100.0

        return {
            "lp_expected_ltv": result_lp.expected_total_ltv,
            "heuristic_expected_ltv": np.round(heuristic_ltv, 2),
            "net_ltv_gain_usd": np.round(result_lp.expected_total_ltv - heuristic_ltv, 2),
            "ltv_uplift_pct": np.round(ltv_uplift_pct, 2),
            "lp_blended_cac": result_lp.expected_blended_cac,
            "heuristic_blended_cac": np.round(heuristic_cac, 2),
            "cac_reduction_pct": np.round(cac_reduction_pct, 2),
            "cac_target_respected_lp": result_lp.expected_blended_cac <= request.max_blended_cac_target,
            "cac_target_respected_heuristic": heuristic_cac <= request.max_blended_cac_target
        }


# ============================================================================
# 3. BACKWARD-COMPATIBLE DOMAIN ANALYTICS ENGINE
# ============================================================================

class DomainAnalyticsEngine:
    """Clase analitica compatible para soporte de fixtures heredadas."""
    def __init__(
        self,
        storage: AnalyticalStorageProtocol,
        data_path: str = "data/raw_dataset.parquet",
    ):
        self.storage = storage
        self.data_path = data_path

    def execute_analysis(self) -> pd.DataFrame:
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Dataset not found at {self.data_path}")

        query = f"""
            SELECT 
                COUNT(*) as total_records,
                ROUND(AVG(acquisition_cost_usd), 4) as mean_primary_metric,
                ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY acquisition_cost_usd), 4) as p95_metric,
                ROUND(MIN(acquisition_cost_usd), 4) as min_metric,
                ROUND(MAX(acquisition_cost_usd), 4) as max_metric
            FROM read_parquet('{self.data_path}');
        """
        return self.storage.execute_query(query)


def create_engine(data_path: str = "data/raw_dataset.parquet") -> DomainAnalyticsEngine:
    adapter = DuckDBStorageAdapter()
    return DomainAnalyticsEngine(storage=adapter, data_path=data_path)


# ============================================================================
# 4. DEFAULT COMPOSITION ROOT FOR PROSIGLIERE OPTIMIZATION
# ============================================================================

def create_default_optimization_request(total_budget: float = 1500000.0) -> BudgetOptimizationRequest:
    """Genera la especificacion de presupuesto predeterminada de Prosigliere."""
    constraints = [
        ChannelBudgetConstraint(
            channel=MarketingChannel.GOOGLE_SEARCH_CORE,
            min_budget_usd=200000.0,
            max_budget_usd=600000.0,
            historical_cac=165.0,
            expected_ltv_multiplier=11.5
        ),
        ChannelBudgetConstraint(
            channel=MarketingChannel.META_PERFORMANCE_MAX,
            min_budget_usd=180000.0,
            max_budget_usd=500000.0,
            historical_cac=115.0,
            expected_ltv_multiplier=8.4
        ),
        ChannelBudgetConstraint(
            channel=MarketingChannel.BRAZE_LIFECYCLE_RETENTION,
            min_budget_usd=225000.0,
            max_budget_usd=450000.0,
            historical_cac=48.0,
            expected_ltv_multiplier=15.6
        ),
        ChannelBudgetConstraint(
            channel=MarketingChannel.REVERSE_ETL_REMARKETING,
            min_budget_usd=100000.0,
            max_budget_usd=350000.0,
            historical_cac=88.0,
            expected_ltv_multiplier=12.2
        ),
        ChannelBudgetConstraint(
            channel=MarketingChannel.TIKTOK_ACQUISITION,
            min_budget_usd=50000.0,
            max_budget_usd=200000.0,
            historical_cac=95.0,
            expected_ltv_multiplier=6.8
        )
    ]
    return BudgetOptimizationRequest(
        request_id=f"REQ-{uuid.uuid4().hex[:8].upper()}",
        total_budget_usd=total_budget,
        max_blended_cac_target=180.0,
        min_braze_retention_quota_pct=15.0,
        channel_constraints=constraints
    )


if __name__ == "__main__":
    from src.data_generator import generate_domain_dataset

    path = "data/raw_dataset.parquet"
    if not os.path.exists(path):
        print(f"[Core Engine] Synthesizing dataset at {path}...")
        generate_domain_dataset(num_records=10000, output_path=path)

    # 1. Ejecucion de optimizacion HiGHS
    request = create_default_optimization_request(total_budget=1500000.0)
    optimizer = ProsigliereMarketingOptimizationEngine()
    result = optimizer.solve_budget_allocation(request)

    # 2. Explicabilidad XAI
    explainer = ProsigliereAttributionExplainer()
    explanations = explainer.explain_allocations(result, request)

    # 3. Comparacion vs Heuristica Estatica
    comparison = OptimizationComparisonService.compare_lp_vs_heuristic(request, result)

    print("\n" + "=" * 80)
    print("  PROSIGLIERE: OMNICHANNEL MARKETING ATTRIBUTION & LINEAR OPTIMIZATION (HiGHS)")
    print("=" * 80)
    print(f" Run ID                     : {result.run_id}")
    print(f" Solver Optimal             : {result.is_optimal} (Status: {result.solver_status_code})")
    print(f" Solver Latency             : {result.solver_latency_ms:.2f} ms")
    print(f" Total Budget Allocated     : ${result.total_budget_allocated:,.2f} ({result.budget_utilization_pct:.1f}% util)")
    print(f" Expected Converted Accounts: {result.expected_total_conversions:,.1f} accounts")
    print(f" Blended CAC Achieved       : ${result.expected_blended_cac:.2f} (Target: <${request.max_blended_cac_target:.2f})")
    print(f" Total Expected LTV Acquired: ${result.expected_total_ltv:,.2f}")
    print("-" * 80)
    print(" CHANNEL ALLOCATIONS & XAI ATTRIBUTION EXPLANATIONS:")
    print(f" {'Channel':<26} | {'Budget ($)':<12} | {'Share':<6} | {'Dual Shadow':<12} | {'Action'}")
    print("-" * 80)
    for exp in explanations:
        action = exp.recommendation[:32] + "..." if len(exp.recommendation) > 35 else exp.recommendation
        print(f" {exp.channel.value:<26} | ${exp.allocated_usd:>10,.2f} | {exp.budget_share_pct:>5.1f}% | ${exp.dual_shadow_price:>10.4f} | {action}")
    print("-" * 80)
    print(" COMPARISON: CONSTRAINED LINEAR PROGRAMMING VS STATIC HEURISTIC")
    print(f" -> LTV Net Gain            : +${comparison['net_ltv_gain_usd']:,.2f} (+{comparison['ltv_uplift_pct']}%)")
    print(f" -> CAC Reduction           : -{comparison['cac_reduction_pct']}% (${result.expected_blended_cac:.2f} vs ${comparison['heuristic_blended_cac']:.2f})")
    print(f" -> CAC Target Respected    : LP: {comparison['cac_target_respected_lp']} | Heuristic: {comparison['cac_target_respected_heuristic']}")
    print("=" * 80 + "\n")