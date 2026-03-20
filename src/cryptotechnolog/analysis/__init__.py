"""
Shared analysis source/truth layer для derived inputs corrective line C_7R.

Этот package пока intentionally узкий:
- не дублирует raw market-data truth;
- не расширяет DERYA-first intelligence line задним числом;
- не принадлежит risk layer;
- хранит shared derived analysis inputs как query/state-first foundation.
"""

from .models import (
    AdxSnapshot,
    AtrSnapshot,
    DerivedInputStatus,
    DerivedInputValidity,
    RiskDerivedInputsSnapshot,
)
from .runtime import (
    SharedAnalysisRuntime,
    SharedAnalysisRuntimeConfig,
    SharedAnalysisRuntimeDiagnostics,
    SharedAnalysisRuntimeUpdate,
    create_shared_analysis_runtime,
)

__all__ = [
    "AdxSnapshot",
    "AtrSnapshot",
    "DerivedInputStatus",
    "DerivedInputValidity",
    "RiskDerivedInputsSnapshot",
    "SharedAnalysisRuntime",
    "SharedAnalysisRuntimeConfig",
    "SharedAnalysisRuntimeDiagnostics",
    "SharedAnalysisRuntimeUpdate",
    "create_shared_analysis_runtime",
]
