"""
src/domain/contracts.py - Protocols for Dependency Inversion Principle (DIP).
Abstract interfaces for data ingestion, mathematical optimization, XAI attribution,
and decoupled storage/telemetry persistence.
Prohibited: Direct instantiation or imports of concrete infrastructure inside domain.
"""

from typing import Protocol, List, Dict, Any, Optional
from src.domain.entities import (
    LeadConversionSurvivalEvent,
    BudgetOptimizationRequest,
    OptimizationAllocationResult,
    ChannelAttributionExplanation
)


class MarketingDataIngestionProtocol(Protocol):
    """Contrato para adaptadores de ingesta columnar de telemetria de marketing y retencion."""
    def load_lead_telemetry(
        self,
        file_path: str,
        limit: Optional[int] = None
    ) -> List[LeadConversionSurvivalEvent]:
        """Carga y parsea eventos de telemetria desde Apache Parquet particionado."""
        ...


class MarketingOptimizationEngineProtocol(Protocol):
    """Contrato para solvers de optimizacion lineal primal-dual (SciPy HiGHS)."""
    def solve_budget_allocation(
        self,
        request: BudgetOptimizationRequest,
        historical_events: Optional[List[LeadConversionSurvivalEvent]] = None
    ) -> OptimizationAllocationResult:
        """Resuelve el problema primal restringido y extrae variables duales (precios sombra)."""
        ...


class AttributionExplainerProtocol(Protocol):
    """Contrato para motores de explicabilidad XAI y generacion prescriptiva."""
    def explain_allocations(
        self,
        result: OptimizationAllocationResult,
        request: BudgetOptimizationRequest
    ) -> List[ChannelAttributionExplanation]:
        """Genera desgloses interpretables y recomendaciones accionables para C-Level."""
        ...


class AnalyticalStorageProtocol(Protocol):
    """Contrato para motores analiticos OLAP desacoplados (DuckDB / PostgreSQL)."""
    def execute_query(self, query: str) -> Any:
        """Ejecuta una consulta analitica estructurada y retorna el resultado en memoria."""
        ...


class TelemetrySinkProtocol(Protocol):
    """Contrato para persistencia y auditoria de corridas de optimizacion."""
    def persist_optimization_run(self, result: OptimizationAllocationResult) -> None:
        """Emite el resultado a un registro persistente o sink en memoria para auditoria."""
        ...