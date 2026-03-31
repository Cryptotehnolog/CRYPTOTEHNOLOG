"""
Узкий explicit runtime foundation для Phase 22 Live Feed Connectivity Foundation.

Этот runtime:
- стартует и останавливается явно;
- держит lifecycle одной feed session;
- отражает narrow connectivity/degraded/retry truth;
- формирует typed ingest handoff в existing market_data;
- не вводит adapter ecosystem, event bus, persistence или platform semantics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from cryptotechnolog.config import get_settings

from .models import (
    FeedConnectionState,
    FeedConnectionStatus,
    FeedConnectivityAssessment,
    FeedIngestRequest,
    FeedIngressEnvelope,
    FeedSessionIdentity,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from cryptotechnolog.config.settings import Settings


@dataclass(slots=True, frozen=True)
class FeedConnectivityRuntimeConfig:
    """Typed config для narrow connectivity runtime."""

    runtime_name: str = "phase22_live_feed_connectivity"
    default_retry_delay_seconds: int = 5

    def __post_init__(self) -> None:
        if self.default_retry_delay_seconds <= 0:
            raise ValueError("default_retry_delay_seconds должен быть положительным")

    @classmethod
    def from_settings(cls, settings: Settings) -> FeedConnectivityRuntimeConfig:
        """Build live-feed runtime config from canonical project settings."""
        return cls(
            default_retry_delay_seconds=settings.live_feed_retry_delay_seconds,
        )


@dataclass(slots=True, frozen=True)
class FeedConnectivityRuntimeState:
    """In-memory state narrow connectivity runtime."""

    session: FeedSessionIdentity
    connection: FeedConnectionState
    last_disconnect_reason: str | None = None


@dataclass(slots=True)
class FeedConnectivityRuntimeDiagnostics:
    """Operator-visible diagnostics без dashboard/platform semantics."""

    started: bool = False
    ready: bool = False
    lifecycle_state: str = "built"
    status: str = FeedConnectionStatus.DISCONNECTED.value
    retry_count: int = 0
    next_retry_at: str | None = None
    last_message_at: str | None = None
    last_disconnect_reason: str | None = None
    degraded_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class FeedConnectivityRuntime:
    """Explicit runtime contour для одной live feed session."""

    def __init__(
        self,
        *,
        session: FeedSessionIdentity,
        config: FeedConnectivityRuntimeConfig | None = None,
        diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.session = session
        self.config = config or FeedConnectivityRuntimeConfig()
        self._diagnostics_sink = diagnostics_sink
        self._started = False
        initial_connection = FeedConnectionState(
            session=session,
            status=FeedConnectionStatus.DISCONNECTED,
            observed_at=datetime.min,
        )
        self.state = FeedConnectivityRuntimeState(
            session=session,
            connection=initial_connection,
        )
        self._diagnostics = FeedConnectivityRuntimeDiagnostics()
        self._push_diagnostics()

    @property
    def is_started(self) -> bool:
        """Проверить, активирован ли runtime contour."""
        return self._started

    async def start(self, *, observed_at: datetime) -> FeedConnectionState:
        """Явно активировать runtime без hidden background behavior."""
        if self._started:
            return self.state.connection
        self._started = True
        self.state = replace(
            self.state,
            connection=FeedConnectionState(
                session=self.session,
                status=FeedConnectionStatus.DISCONNECTED,
                observed_at=observed_at,
                retry_count=self.state.connection.retry_count,
                next_retry_at=self.state.connection.next_retry_at,
            ),
        )
        self._refresh_diagnostics(lifecycle_state="started", ready=False)
        return self.state.connection

    async def stop(self, *, observed_at: datetime) -> FeedConnectionState:
        """Остановить runtime и вернуть его в explicit disconnected state."""
        self._started = False
        self.state = replace(
            self.state,
            connection=FeedConnectionState(
                session=self.session,
                status=FeedConnectionStatus.DISCONNECTED,
                observed_at=observed_at,
                retry_count=self.state.connection.retry_count,
                next_retry_at=self.state.connection.next_retry_at,
            ),
        )
        self._refresh_diagnostics(lifecycle_state="stopped", ready=False)
        return self.state.connection

    def begin_connecting(self, *, observed_at: datetime) -> FeedConnectionState:
        """Перевести runtime в explicit CONNECTING state."""
        self._ensure_started()
        connection = FeedConnectionState(
            session=self.session,
            status=FeedConnectionStatus.CONNECTING,
            observed_at=observed_at,
            retry_count=self.state.connection.retry_count,
            next_retry_at=self.state.connection.next_retry_at,
        )
        self.state = replace(self.state, connection=connection)
        self._refresh_diagnostics(lifecycle_state="connecting", ready=False)
        return connection

    def mark_connected(self, *, observed_at: datetime) -> FeedConnectionState:
        """Зафиксировать успешное установление feed session."""
        self._ensure_started()
        connection = FeedConnectionState(
            session=self.session,
            status=FeedConnectionStatus.CONNECTED,
            observed_at=observed_at,
            connected_at=observed_at,
            last_message_at=self.state.connection.last_message_at,
            retry_count=self.state.connection.retry_count,
        )
        self.state = replace(self.state, connection=connection)
        self._refresh_diagnostics(lifecycle_state="connected", ready=True)
        return connection

    def mark_degraded(
        self,
        *,
        observed_at: datetime,
        reason: str,
        staleness_ms: int | None = None,
    ) -> FeedConnectivityAssessment:
        """Перевести session в narrow degraded truth без platform semantics."""
        self._ensure_started()
        connected_at = self.state.connection.connected_at or observed_at
        connection = FeedConnectionState(
            session=self.session,
            status=FeedConnectionStatus.DEGRADED,
            observed_at=observed_at,
            connected_at=connected_at,
            last_message_at=self.state.connection.last_message_at,
            degraded_reason=reason,
            retry_count=self.state.connection.retry_count,
            next_retry_at=self.state.connection.next_retry_at,
        )
        self.state = replace(self.state, connection=connection)
        assessment = FeedConnectivityAssessment(
            session=self.session,
            status=FeedConnectionStatus.DEGRADED,
            observed_at=observed_at,
            is_ready=False,
            is_degraded=True,
            degraded_reason=reason,
            staleness_ms=staleness_ms,
        )
        self._refresh_diagnostics(lifecycle_state="degraded", ready=False)
        return assessment

    def mark_disconnected(
        self,
        *,
        observed_at: datetime,
        reason: str,
        retry_delay: timedelta | None = None,
    ) -> FeedConnectionState:
        """Зафиксировать disconnect и minimal retry/backoff truth."""
        self._ensure_started()
        next_retry_at = observed_at + (
            retry_delay or timedelta(seconds=self.config.default_retry_delay_seconds)
        )
        connection = FeedConnectionState(
            session=self.session,
            status=FeedConnectionStatus.DISCONNECTED,
            observed_at=observed_at,
            retry_count=self.state.connection.retry_count + 1,
            next_retry_at=next_retry_at,
        )
        self.state = replace(
            self.state,
            connection=connection,
            last_disconnect_reason=reason,
        )
        self._refresh_diagnostics(
            lifecycle_state="disconnected",
            ready=False,
            last_disconnect_reason=reason,
        )
        return connection

    def get_connectivity_assessment(self, *, observed_at: datetime) -> FeedConnectivityAssessment:
        """Вернуть typed assessment поверх текущего connection state."""
        self._ensure_started()
        connection = self.state.connection
        return FeedConnectivityAssessment(
            session=self.session,
            status=connection.status,
            observed_at=observed_at,
            is_ready=connection.status == FeedConnectionStatus.CONNECTED,
            is_degraded=connection.status == FeedConnectionStatus.DEGRADED,
            degraded_reason=connection.degraded_reason,
        )

    def build_ingest_request(
        self,
        *,
        payload_kind: str,
        transport_payload: dict[str, object],
        ingested_at: datetime,
        source_sequence: int | None = None,
    ) -> FeedIngestRequest:
        """Собрать narrow ingest handoff в existing market_data layer."""
        self._ensure_started()
        if self.state.connection.status not in (
            FeedConnectionStatus.CONNECTED,
            FeedConnectionStatus.DEGRADED,
        ):
            raise RuntimeError("Ingest handoff допустим только в CONNECTED/DEGRADED state")

        envelope = FeedIngressEnvelope(
            session=self.session,
            payload_kind=payload_kind,
            ingested_at=ingested_at,
            transport_payload=transport_payload,
            source_sequence=source_sequence,
        )
        connection = replace(
            self.state.connection,
            observed_at=ingested_at,
            last_message_at=ingested_at,
        )
        self.state = replace(self.state, connection=connection)
        self._refresh_diagnostics(
            lifecycle_state=(
                "connected" if connection.status == FeedConnectionStatus.CONNECTED else "degraded"
            ),
            ready=connection.status == FeedConnectionStatus.CONNECTED,
        )
        return FeedIngestRequest(
            envelope=envelope,
            requested_at=ingested_at,
        )

    def get_connection_state(self) -> FeedConnectionState:
        """Вернуть текущую typed connection truth."""
        return self.state.connection

    def get_runtime_diagnostics(self) -> dict[str, object]:
        """Вернуть operator-visible diagnostics."""
        return self._diagnostics.to_dict()

    def _ensure_started(self) -> None:
        if not self._started:
            raise RuntimeError(
                "FeedConnectivityRuntime должен быть явно запущен перед lifecycle operations"
            )

    def _refresh_diagnostics(
        self,
        *,
        lifecycle_state: str,
        ready: bool,
        last_disconnect_reason: str | None = None,
    ) -> None:
        connection = self.state.connection
        self._diagnostics.started = self._started
        self._diagnostics.ready = ready
        self._diagnostics.lifecycle_state = lifecycle_state
        self._diagnostics.status = connection.status.value
        self._diagnostics.retry_count = connection.retry_count
        self._diagnostics.next_retry_at = (
            connection.next_retry_at.isoformat() if connection.next_retry_at is not None else None
        )
        self._diagnostics.last_message_at = (
            connection.last_message_at.isoformat()
            if connection.last_message_at is not None
            else None
        )
        self._diagnostics.degraded_reason = connection.degraded_reason
        if last_disconnect_reason is not None:
            self._diagnostics.last_disconnect_reason = last_disconnect_reason
        elif self.state.last_disconnect_reason is not None:
            self._diagnostics.last_disconnect_reason = self.state.last_disconnect_reason
        self._push_diagnostics()

    def _push_diagnostics(self) -> None:
        if self._diagnostics_sink is not None:
            self._diagnostics_sink(self._diagnostics.to_dict())


def create_live_feed_runtime(
    *,
    session: FeedSessionIdentity,
    config: FeedConnectivityRuntimeConfig | None = None,
    diagnostics_sink: Callable[[dict[str, object]], None] | None = None,
) -> FeedConnectivityRuntime:
    """Собрать explicit runtime contour для одной live feed session."""
    return FeedConnectivityRuntime(
        session=session,
        config=config or FeedConnectivityRuntimeConfig.from_settings(get_settings()),
        diagnostics_sink=diagnostics_sink,
    )


__all__ = [
    "FeedConnectivityRuntime",
    "FeedConnectivityRuntimeConfig",
    "FeedConnectivityRuntimeDiagnostics",
    "FeedConnectivityRuntimeState",
    "create_live_feed_runtime",
]
