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

from .assembly import (
    assemble_paper_report_artifact,
    assemble_replay_report_artifact,
    assemble_reporting_artifact_bundle,
    assemble_reporting_bundle_from_candidates,
    assemble_validation_report_artifact,
)
from .models import (
    PaperReportArtifact,
    ReplayReportArtifact,
    ReportArtifact,
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
    "ReportArtifact",
    "ReportingArtifactBundle",
    "ReportingArtifactKind",
    "ReportingArtifactProvenance",
    "ReportingArtifactStatus",
    "ReportingSourceLayer",
    "ValidationReportArtifact",
    "assemble_paper_report_artifact",
    "assemble_replay_report_artifact",
    "assemble_reporting_artifact_bundle",
    "assemble_reporting_bundle_from_candidates",
    "assemble_validation_report_artifact",
]
