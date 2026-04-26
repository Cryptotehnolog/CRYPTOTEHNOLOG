"""Explicit historical restore lifecycle coordinator for Bybit connector."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from .bybit_recovery_coordinator import (
    BybitHistoricalRecoveryCoordinator,
    BybitHistoricalRecoveryCoordinatorSnapshot,
    BybitHistoricalRecoveryDecision,
    classify_bybit_historical_recovery_result,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from .bybit_trade_backfill import (
        BybitHistoricalRecoveryPlan,
        BybitHistoricalTradeBackfillResult,
        BybitHistoricalTradeBackfillService,
    )


@dataclass(slots=True, frozen=True)
class BybitHistoricalRestoreExecution:
    observed_at: datetime
    plan: BybitHistoricalRecoveryPlan
    result: BybitHistoricalTradeBackfillResult
    decision: BybitHistoricalRecoveryDecision


@dataclass(slots=True)
class BybitHistoricalRestoreCoordinator:
    """Owns restore planning/progress/retry scheduling around historical trade truth."""

    exchange_name: str
    sleep_func: Callable[[float], Awaitable[None]]
    retry_delay_seconds: float
    backfill_service: BybitHistoricalTradeBackfillService | None = None
    _recovery: BybitHistoricalRecoveryCoordinator = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._recovery = BybitHistoricalRecoveryCoordinator(
            exchange_name=self.exchange_name,
            sleep_func=self.sleep_func,
            retry_delay_seconds=self.retry_delay_seconds,
        )

    @property
    def recovery(self) -> BybitHistoricalRecoveryCoordinator:
        return self._recovery

    @property
    def pending(self) -> bool:
        return self._recovery.pending

    @pending.setter
    def pending(self, value: bool) -> None:
        self._recovery.pending = value

    @property
    def backfill_task(self) -> asyncio.Task[None] | None:
        return self._recovery.backfill_task

    @backfill_task.setter
    def backfill_task(self, value: asyncio.Task[None] | None) -> None:
        self._recovery.backfill_task = value

    @property
    def retry_task(self) -> asyncio.Task[None] | None:
        return self._recovery.retry_task

    @retry_task.setter
    def retry_task(self, value: asyncio.Task[None] | None) -> None:
        self._recovery.retry_task = value

    @property
    def cutoff_at(self) -> datetime | None:
        return self._recovery.cutoff_at

    @cutoff_at.setter
    def cutoff_at(self, value: datetime | None) -> None:
        self._recovery.cutoff_at = value

    @property
    def latest_retry_pending(self) -> bool:
        return self._recovery.latest_retry_pending

    @latest_retry_pending.setter
    def latest_retry_pending(self, value: bool) -> None:
        self._recovery.latest_retry_pending = value

    def initialize(
        self,
        *,
        admission_enabled: bool,
        trade_truth_ready: bool,
        mark_backfill_pending: Callable[[], None],
        mark_backfill_not_needed: Callable[[], None],
    ) -> None:
        self.pending = admission_enabled and self.backfill_service is not None and not trade_truth_ready
        if not admission_enabled or not self.pending:
            mark_backfill_not_needed()
            return
        mark_backfill_pending()

    def snapshot(
        self,
        *,
        admission_enabled: bool,
        has_restored_historical_window: bool,
    ) -> BybitHistoricalRecoveryCoordinatorSnapshot:
        return self._recovery.snapshot(
            admission_enabled=admission_enabled,
            has_restored_historical_window=has_restored_historical_window,
        )

    def note_disconnect(self, *, reuse_historical_window: bool) -> bool:
        pending = self._recovery.note_disconnect(
            service_available=self.backfill_service is not None,
            reuse_historical_window=reuse_historical_window,
        )
        return pending

    def schedule_backfill(
        self,
        *,
        symbols: tuple[str, ...],
        observed_at: datetime,
        mark_backfill_pending: Callable[[int | None], None],
        run_callback: Callable[[], Awaitable[None]],
    ) -> None:
        if not self.pending or self.backfill_service is None or self.backfill_task is not None:
            return
        self.cutoff_at = observed_at
        recovery_plan = self.backfill_service.build_recovery_plan(
            symbols=symbols,
            observed_at=observed_at,
            covered_until_at=observed_at,
        )
        mark_backfill_pending(recovery_plan.total_archives)
        self._recovery.schedule_backfill(
            scheduled_at=observed_at,
            run_callback=run_callback,
        )

    async def load_pending_restore(
        self,
        *,
        symbols: tuple[str, ...],
        update_progress: Callable[[int, int], None],
        now_func: Callable[[], datetime],
    ) -> BybitHistoricalRestoreExecution | None:
        if not self.pending:
            return None
        if self.backfill_service is None or self.cutoff_at is None:
            return None
        observed_at = now_func()
        plan = self.backfill_service.build_recovery_plan(
            symbols=symbols,
            observed_at=observed_at,
            covered_until_at=self.cutoff_at,
        )
        loop = asyncio.get_running_loop()

        def progress_callback(processed_archives: int, total_archives: int) -> None:
            loop.call_soon_threadsafe(update_progress, processed_archives, total_archives)

        result = await asyncio.to_thread(
            self.backfill_service.load_plan,
            plan=plan,
            progress_callback=progress_callback,
        )
        decision = classify_bybit_historical_recovery_result(result)
        self._recovery.note_recovery_result(decision)
        return BybitHistoricalRestoreExecution(
            observed_at=observed_at,
            plan=plan,
            result=result,
            decision=decision,
        )

    def schedule_retry_if_needed(
        self,
        *,
        stop_requested: Callable[[], bool],
        trigger_backfill: Callable[[], None],
    ) -> None:
        self._recovery.schedule_retry(
            stop_requested=stop_requested,
            trigger_backfill=trigger_backfill,
        )

    def cancel(self) -> None:
        self._recovery.cancel()
