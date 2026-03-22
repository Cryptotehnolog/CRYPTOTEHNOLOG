"""
Contract-first package boundary для Phase 7 Intelligence Foundation.

На шаге `Contract Lock` здесь фиксируются:
- typed indicator contracts;
- intelligence assessments;
- DERYA semantics basis;
- analysis-level event contracts.
"""

from .derya_engine import DeryaEngine, DeryaEngineConfig, DeryaRegimeTransition
from .events import (
    DeryaRegimeChangedPayload,
    IndicatorUpdatedPayload,
    IntelligenceAssessmentPayload,
    IntelligenceEventSource,
    IntelligenceEventType,
    build_intelligence_event,
    default_priority_for_intelligence_event,
)
from .models import (
    DEFAULT_DERYA_CLASSIFICATION_BASIS,
    DeryaAssessment,
    DeryaClassificationBasis,
    DeryaObservation,
    DeryaRegime,
    DeryaResolutionState,
    IndicatorSnapshot,
    IndicatorValidity,
    IndicatorValueStatus,
    IntelligenceAssessment,
    IntelligenceAssessmentKind,
    calculate_derya_confidence,
    classify_derya_regime_candidate,
    resolve_derya_regime,
)
from .runtime import (
    IntelligenceRuntime,
    IntelligenceRuntimeConfig,
    IntelligenceRuntimeDiagnostics,
    IntelligenceRuntimeUpdate,
    create_intelligence_runtime,
)

__all__ = [
    "DEFAULT_DERYA_CLASSIFICATION_BASIS",
    "DeryaAssessment",
    "DeryaClassificationBasis",
    "DeryaEngine",
    "DeryaEngineConfig",
    "DeryaObservation",
    "DeryaRegime",
    "DeryaRegimeChangedPayload",
    "DeryaRegimeTransition",
    "DeryaResolutionState",
    "IndicatorSnapshot",
    "IndicatorUpdatedPayload",
    "IndicatorValidity",
    "IndicatorValueStatus",
    "IntelligenceAssessment",
    "IntelligenceAssessmentKind",
    "IntelligenceAssessmentPayload",
    "IntelligenceEventSource",
    "IntelligenceEventType",
    "IntelligenceRuntime",
    "IntelligenceRuntimeConfig",
    "IntelligenceRuntimeDiagnostics",
    "IntelligenceRuntimeUpdate",
    "build_intelligence_event",
    "calculate_derya_confidence",
    "classify_derya_regime_candidate",
    "create_intelligence_runtime",
    "default_priority_for_intelligence_event",
    "resolve_derya_regime",
]
