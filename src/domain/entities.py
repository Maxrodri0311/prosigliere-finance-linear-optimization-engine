"""
src/domain/entities.py - Pure domain models for Prosigliere Analytics Engineering.
Defines business entities for marketing attribution, Weibull survival lifecycle dynamics,
and constrained linear programming budget optimization.
Strict Clean Architecture: Zero vendor locking or external I/O imports.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class MarketingChannel(str, Enum):
    """Canales de adquisicion y retencion omnicanal gestionados por Prosigliere."""
    GOOGLE_SEARCH_CORE = "GOOGLE_SEARCH_CORE"
    META_PERFORMANCE_MAX = "META_PERFORMANCE_MAX"
    BRAZE_LIFECYCLE_RETENTION = "BRAZE_LIFECYCLE_RETENTION"
    REVERSE_ETL_REMARKETING = "REVERSE_ETL_REMARKETING"
    TIKTOK_ACQUISITION = "TIKTOK_ACQUISITION"


class AudienceSegment(str, Enum):
    """Segmentos de audiencia basados en valor y compromiso."""
    ENTERPRISE_HIGH_INTENT = "ENTERPRISE_HIGH_INTENT"
    MIDMARKET_ENGAGED = "MIDMARKET_ENGAGED"
    SMB_TRANSACTIONAL = "SMB_TRANSACTIONAL"


class CampaignAttributionType(str, Enum):
    """Modelos de atribucion comparativos."""
    FIRST_TOUCH = "FIRST_TOUCH"
    LAST_TOUCH = "LAST_TOUCH"
    TIME_DECAYED_WEIBULL = "TIME_DECAYED_WEIBULL"
    MARKOV_TRANSITION = "MARKOV_TRANSITION"


class LeadConversionSurvivalEvent(BaseModel):
    """Evento atomico de telemetria de marketing con fisica de decaimiento temporal."""
    lead_id: str = Field(..., description="Identificador unico del lead o cuenta")
    channel: MarketingChannel = Field(..., description="Canal de interaccion")
    audience_segment: AudienceSegment = Field(..., description="Segmento de valor de la audiencia")
    acquisition_cost_usd: float = Field(..., ge=0.0, description="Costo de adquisicion / impresion en USD")
    conversion_time_days: float = Field(..., ge=0.0, description="Tiempo hasta conversion o censura en dias")
    is_converted: bool = Field(..., description="Indica si la cuenta alcanzo conversion")
    weibull_shape_k: float = Field(..., gt=0.0, description="Parametro de forma Weibull de riesgo k")
    weibull_scale_lambda: float = Field(..., gt=0.0, description="Parametro de escala Weibull de vida media lambda")
    realized_ltv_usd: float = Field(..., ge=0.0, description="Valor del ciclo de vida acumulado en USD")


class ChannelBudgetConstraint(BaseModel):
    """Cotas fisicas y financieras de canal para optimizacion restringida."""
    channel: MarketingChannel
    min_budget_usd: float = Field(..., ge=0.0, description="Cota inferior obligatoria de presupuesto")
    max_budget_usd: float = Field(..., ge=0.0, description="Cota superior de capacidad o saturacion de canal")
    historical_cac: float = Field(..., gt=0.0, description="Costo de adquisicion historico promedio por cuenta")
    expected_ltv_multiplier: float = Field(..., gt=0.0, description="Multiplicador proyectado de LTV por dolar invertido")

    @field_validator("max_budget_usd")
    @classmethod
    def validate_bounds(cls, v: float, info) -> float:
        min_b = info.data.get("min_budget_usd", 0.0)
        if v < min_b:
            raise ValueError(f"max_budget_usd ({v}) no puede ser menor que min_budget_usd ({min_b})")
        return v


class BudgetOptimizationRequest(BaseModel):
    """Solicitud formal de optimizacion de presupuesto para Prosigliere."""
    request_id: str = Field(..., description="UUID unico de la corrida analitica")
    total_budget_usd: float = Field(..., gt=0.0, description="Presupuesto total a distribuir en el trimestre")
    max_blended_cac_target: float = Field(..., gt=0.0, description="Techo estricto de CAC promedio Blended")
    min_braze_retention_quota_pct: float = Field(
        default=15.0, ge=0.0, le=100.0,
        description="Porcentaje minimo garantizado para retencion y remarketing en Braze"
    )
    channel_constraints: List[ChannelBudgetConstraint] = Field(
        ..., min_length=2,
        description="Lista de restricciones por canal"
    )


class OptimizationAllocationResult(BaseModel):
    """Resultado determinista de la optimizacion lineal con explicabilidad dual."""
    run_id: str
    is_optimal: bool
    solver_status_code: int
    solver_latency_ms: float
    total_budget_allocated: float
    allocations_by_channel: Dict[MarketingChannel, float]
    expected_total_conversions: float
    expected_blended_cac: float
    expected_total_ltv: float
    dual_shadow_prices: Dict[MarketingChannel, float]
    budget_utilization_pct: float


class ChannelAttributionExplanation(BaseModel):
    """Desglose prescriptivo y explicabilidad de negocio para liderazgo ejecutivo."""
    channel: MarketingChannel
    allocated_usd: float
    budget_share_pct: float
    marginal_ltv_per_dollar: float
    dual_shadow_price: float
    attribution_weight_pct: float
    recommendation: str