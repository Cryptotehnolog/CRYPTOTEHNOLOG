"""
Единый source of truth для release/runtime identity платформы.

Этот модуль хранит только inert metadata и не должен выполнять bootstrap.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

PROJECT_NAME = "CRYPTOTEHNOLOG"
PACKAGE_VERSION = "1.13.0"


@dataclass(slots=True, frozen=True)
class RuntimeIdentity:
    """Согласованная runtime identity платформы."""

    project_name: str
    version: str
    bootstrap_module: str | None = None
    bootstrap_mode: str | None = None
    active_risk_path: str | None = None
    config_identity: str | None = None
    config_revision: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Преобразовать identity в словарь для health и diagnostics."""
        return asdict(self)


def get_project_name() -> str:
    """Вернуть canonical project name."""
    return PROJECT_NAME


def get_runtime_version() -> str:
    """Вернуть canonical package/runtime version."""
    return PACKAGE_VERSION


def get_release_identity() -> RuntimeIdentity:
    """Вернуть базовую release identity без runtime-specific контекста."""
    return RuntimeIdentity(
        project_name=get_project_name(),
        version=get_runtime_version(),
    )


def build_runtime_identity(
    *,
    bootstrap_module: str,
    bootstrap_mode: str,
    active_risk_path: str | None = None,
    config_identity: str | None = None,
    config_revision: str | None = None,
) -> RuntimeIdentity:
    """Собрать runtime identity для уже выбранного bootstrap path."""
    release_identity = get_release_identity()
    return RuntimeIdentity(
        project_name=release_identity.project_name,
        version=release_identity.version,
        bootstrap_module=bootstrap_module,
        bootstrap_mode=bootstrap_mode,
        active_risk_path=active_risk_path,
        config_identity=config_identity,
        config_revision=config_revision,
    )
