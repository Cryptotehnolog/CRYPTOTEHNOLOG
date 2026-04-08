"""Historical recovery coordinator for Bybit trade-count lifecycle."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


@dataclass(slots=True, frozen=True)
class BybitHistoricalRecoveryDecision:
    apply_restore: bool
    schedule_retry: bool
    mark_skipped: bool
    mark_unavailable: bool


@dataclass(slots=True, frozen=True)
class BybitHistoricalRecoveryCoordinatorSnapshot:
    state: str
    reason: str | None
    retry_pending: bool
    backfill_task_active: bool
    retry_task_active: bool
    cutoff_at: str | None


def classify_bybit_historical_recovery_result(
    result: Any,
) -> BybitHistoricalRecoveryDecision:
    can_apply_historical_restore = (
        result.restored_window_started_at is not None and result.covered_until_at is not None
    )
    retriable_latest_archive_skip = bool(
        result.status == "skipped"
        and isinstance(result.reason, str)
        and result.reason.startswith("historical trade archive not found for ")
    )
    return BybitHistoricalRecoveryDecision(
        apply_restore=can_apply_historical_restore,
        schedule_retry=retriable_latest_archive_skip,
        mark_skipped=result.status == "skipped" and not can_apply_historical_restore,
        mark_unavailable=result.status not in {"backfilled", "skipped"},
    )


@dataclass(slots=True)
class BybitHistoricalRecoveryCoordinator:
    exchange_name: str
    sleep_func: Callable[[float], Awaitable[None]]
    retry_delay_seconds: float
    _pending: bool = False
    _backfill_task: asyncio.Task[None] | None = None
    _retry_task: asyncio.Task[None] | None = None
    _cutoff_at: datetime | None = None
    _latest_retry_pending: bool = False

    @property
    def pending(self) -> bool:
        return self._pending

    @pending.setter
    def pending(self, value: bool) -> None:
        self._pending = bool(value)

    @property
    def backfill_task(self) -> asyncio.Task[None] | None:
        return self._backfill_task

    @backfill_task.setter
    def backfill_task(self, value: asyncio.Task[None] | None) -> None:
        self._backfill_task = value

    @property
    def retry_task(self) -> asyncio.Task[None] | None:
        return self._retry_task

    @retry_task.setter
    def retry_task(self, value: asyncio.Task[None] | None) -> None:
        self._retry_task = value

    @property
    def cutoff_at(self) -> datetime | None:
        return self._cutoff_at

    @cutoff_at.setter
    def cutoff_at(self, value: datetime | None) -> None:
        self._cutoff_at = value

    @property
    def latest_retry_pending(self) -> bool:
        return self._latest_retry_pending

    @latest_retry_pending.setter
    def latest_retry_pending(self, value: bool) -> None:
        self._latest_retry_pending = bool(value)

    def snapshot(
        self,
        *,
        admission_enabled: bool,
        has_restored_historical_window: bool,
    ) -> BybitHistoricalRecoveryCoordinatorSnapshot:
        if not admission_enabled:
            state = "not_applicable"
            reason = None
        elif self._backfill_task is not None:
            state = "backfilling"
            reason = "Historical recovery plan is currently being applied."
        elif self._retry_task is not None or self._latest_retry_pending:
            state = "retry_scheduled"
            reason = "Latest closed-day archive is missing; retry is scheduled."
        elif self._pending:
            state = "pending"
            reason = "Historical recovery is pending."
        elif has_restored_historical_window:
            state = "live_tail_only"
            reason = "Historical window is already restored; only live tail remains."
        else:
            state = "idle"
            reason = None
        return BybitHistoricalRecoveryCoordinatorSnapshot(
            state=state,
            reason=reason,
            retry_pending=self._latest_retry_pending,
            backfill_task_active=self._backfill_task is not None,
            retry_task_active=self._retry_task is not None,
            cutoff_at=(
                self._cutoff_at.astimezone(UTC).isoformat() if self._cutoff_at is not None else None
            ),
        )

    def note_disconnect(self, *, service_available: bool, reuse_historical_window: bool) -> bool:
        self._pending = service_available and (
            self._latest_retry_pending or not reuse_historical_window
        )
        if not self._pending:
            self._cutoff_at = None
        return self._pending

    def note_recovery_result(self, decision: BybitHistoricalRecoveryDecision) -> None:
        self._latest_retry_pending = decision.schedule_retry
        self._pending = decision.schedule_retry
        self._cutoff_at = None

    def schedule_backfill(
        self,
        *,
        scheduled_at: datetime,
        run_callback: Callable[[], Awaitable[None]],
    ) -> None:
        if not self._pending:
            return
        if self._backfill_task is not None:
            return
        self._cutoff_at = scheduled_at.astimezone(UTC)
        self._backfill_task = asyncio.create_task(
            self._run_backfill(run_callback),
            name=f"{self.exchange_name}_historical_trade_count_backfill",
        )

    async def _run_backfill(self, run_callback: Callable[[], Awaitable[None]]) -> None:
        try:
            await run_callback()
        except asyncio.CancelledError:
            raise
        finally:
            self._backfill_task = None

    def schedule_retry(
        self,
        *,
        stop_requested: Callable[[], bool],
        trigger_backfill: Callable[[], None],
    ) -> None:
        if stop_requested():
            return
        if not self._latest_retry_pending:
            return
        if self._retry_task is not None:
            return
        self._retry_task = asyncio.create_task(
            self._run_retry(stop_requested=stop_requested, trigger_backfill=trigger_backfill),
            name=f"{self.exchange_name}_latest_archive_backfill_retry",
        )

    async def _run_retry(
        self,
        *,
        stop_requested: Callable[[], bool],
        trigger_backfill: Callable[[], None],
    ) -> None:
        try:
            await self.sleep_func(self.retry_delay_seconds)
            if stop_requested():
                return
            if not self._latest_retry_pending:
                return
            if self._backfill_task is not None:
                return
            trigger_backfill()
        except asyncio.CancelledError:
            raise
        finally:
            self._retry_task = None

    def cancel(self) -> None:
        if self._backfill_task is not None:
            self._backfill_task.cancel()
            self._backfill_task = None
        if self._retry_task is not None:
            self._retry_task.cancel()
            self._retry_task = None
