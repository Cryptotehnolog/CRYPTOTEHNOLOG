"""DTO модели для узкого reporting artifact catalog summary панели."""

from __future__ import annotations

from pydantic import BaseModel


class ReportingCatalogCountsDTO(BaseModel):
    """Агрегированные счётчики surfaced reporting catalog truth."""

    total_artifacts: int
    total_bundles: int
    validation_artifacts: int
    paper_artifacts: int
    replay_artifacts: int


class ReportingLastArtifactDTO(BaseModel):
    """Последний surfaced reporting artifact."""

    kind: str
    status: str
    source_layer: str
    generated_at: str


class ReportingLastBundleDTO(BaseModel):
    """Последний surfaced reporting bundle."""

    reporting_name: str
    generated_at: str
    artifact_count: int


class ReportingSummaryDTO(BaseModel):
    """Узкий read-only snapshot reporting artifact catalog summary."""

    module_status: str
    global_status: str
    catalog_counts: ReportingCatalogCountsDTO
    last_artifact_snapshot: ReportingLastArtifactDTO | None = None
    last_bundle_snapshot: ReportingLastBundleDTO | None = None
    summary_note: str
    summary_reason: str | None = None
