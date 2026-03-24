"""
Phase 21 Reporting Artifact Foundation.

На шаге `Reporting Contract Lock` пакет intentionally включает только:
- typed reporting contracts;
- typed report artifacts;
- bundle/provenance/read-only truth.

На этом шаге пакет intentionally не включает:
- analytics runtime/platform;
- dashboard / operator semantics;
- comparison / ranking semantics;
- persistence / delivery / orchestration.
"""

from .models import (
    PaperReportArtifact,
    ReplayReportArtifact,
    ReportingArtifactBundle,
    ReportingArtifactKind,
    ReportingArtifactProvenance,
    ReportingArtifactStatus,
    ReportingSourceLayer,
    ValidationReportArtifact,
)

__all__ = [
    "PaperReportArtifact",
    "ReplayReportArtifact",
    "ReportingArtifactBundle",
    "ReportingArtifactKind",
    "ReportingArtifactProvenance",
    "ReportingArtifactStatus",
    "ReportingSourceLayer",
    "ValidationReportArtifact",
]
