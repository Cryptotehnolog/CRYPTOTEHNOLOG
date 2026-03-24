"""
Local read-only retrieval helpers для Phase 21 reporting artifact layer.

Этот модуль intentionally не является runtime/service boundary.
Он даёт только in-memory query surface поверх artifacts и bundles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

    from cryptotechnolog.reporting.models import (
        ReportArtifact,
        ReportingArtifactBundle,
        ReportingArtifactKind,
        ReportingSourceLayer,
    )


@dataclass(slots=True, frozen=True)
class ReportingArtifactCatalog:
    """Immutable local catalog для read-only retrieval reporting artifacts."""

    artifacts: tuple[ReportArtifact, ...]
    bundles: tuple[ReportingArtifactBundle, ...] = ()
    _artifacts_by_id: dict[UUID, ReportArtifact] = field(init=False, repr=False)
    _bundles_by_id: dict[UUID, ReportingArtifactBundle] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        artifacts_by_id = {}
        for artifact in self.artifacts:
            existing = artifacts_by_id.get(artifact.artifact_id)
            if existing is not None and existing != artifact:
                raise ValueError(
                    "ReportingArtifactCatalog не допускает conflicting artifacts с одинаковым id"
                )
            artifacts_by_id[artifact.artifact_id] = artifact

        bundles_by_id = {}
        for bundle in self.bundles:
            if bundle.bundle_id in bundles_by_id:
                raise ValueError(
                    "ReportingArtifactCatalog не допускает несколько bundles с одинаковым id"
                )
            bundles_by_id[bundle.bundle_id] = bundle
            for artifact in bundle.artifacts:
                existing = artifacts_by_id.get(artifact.artifact_id)
                if existing is not None and existing != artifact:
                    raise ValueError(
                        "ReportingArtifactCatalog не допускает conflicting bundle artifacts"
                    )
                artifacts_by_id[artifact.artifact_id] = artifact

        ordered_artifacts = tuple(
            sorted(
                artifacts_by_id.values(),
                key=lambda artifact: (artifact.generated_at, str(artifact.artifact_id)),
            )
        )
        ordered_bundles = tuple(
            sorted(
                bundles_by_id.values(),
                key=lambda bundle: (bundle.generated_at, str(bundle.bundle_id)),
            )
        )

        object.__setattr__(self, "artifacts", ordered_artifacts)
        object.__setattr__(self, "bundles", ordered_bundles)
        object.__setattr__(self, "_artifacts_by_id", artifacts_by_id)
        object.__setattr__(self, "_bundles_by_id", bundles_by_id)

    def get_artifact(self, artifact_id: UUID) -> ReportArtifact | None:
        """Вернуть artifact по id или `None`."""
        return self._artifacts_by_id.get(artifact_id)

    def get_bundle(self, bundle_id: UUID) -> ReportingArtifactBundle | None:
        """Вернуть bundle по id или `None`."""
        return self._bundles_by_id.get(bundle_id)

    def list_artifacts(
        self,
        *,
        kind: ReportingArtifactKind | None = None,
        source_layer: ReportingSourceLayer | None = None,
    ) -> tuple[ReportArtifact, ...]:
        """Вернуть read-only artifacts c optional local filtering."""
        return tuple(
            artifact
            for artifact in self.artifacts
            if (kind is None or artifact.kind == kind)
            and (source_layer is None or artifact.source_layer == source_layer)
        )

    def find_by_source_candidate_id(
        self,
        source_candidate_id: UUID,
        *,
        source_layer: ReportingSourceLayer | None = None,
    ) -> tuple[ReportArtifact, ...]:
        """Найти artifacts по source candidate id."""
        return tuple(
            artifact
            for artifact in self.artifacts
            if artifact.source_candidate_id == source_candidate_id
            and (source_layer is None or artifact.source_layer == source_layer)
        )

    def get_bundle_artifacts(self, bundle_id: UUID) -> tuple[ReportArtifact, ...]:
        """Вернуть artifacts, принадлежащие bundle, или пустой tuple."""
        bundle = self.get_bundle(bundle_id)
        if bundle is None:
            return ()
        return bundle.artifacts


def build_reporting_artifact_catalog(
    *,
    artifacts: Iterable[ReportArtifact] = (),
    bundles: Iterable[ReportingArtifactBundle] = (),
) -> ReportingArtifactCatalog:
    """Собрать immutable local catalog поверх artifacts и bundles."""
    return ReportingArtifactCatalog(
        artifacts=tuple(artifacts),
        bundles=tuple(bundles),
    )
