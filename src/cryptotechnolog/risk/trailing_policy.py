"""
Доменная логика TrailingPolicy.

Это институциональный модуль Risk Engine, а не helper стратегии.
Ключевой инвариант:
    движение стопа допускается только при успешной синхронизации с RiskLedger.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from cryptotechnolog.core.state_machine_enums import SystemState

from .models import (
    MarketSnapshot,
    PositionRiskRecord,
    PositionSide,
    StopUpdate,
    TrailingEvaluationType,
    TrailingMode,
    TrailingState,
    TrailingTier,
)

if TYPE_CHECKING:
    from .risk_ledger import RiskLedger


class TrailingPolicyError(Exception):
    """Базовая ошибка TrailingPolicy."""


class TrailingInputError(TrailingPolicyError):
    """Некорректные входные данные для оценки трейлинга."""


@dataclass(slots=True, frozen=True)
class TrailingPolicyConfig:
    """
    Конфигурация доменной логики трейлинга.
    """

    arm_at_pnl_r: Decimal = Decimal("1.0")
    t2_at_pnl_r: Decimal = Decimal("2.0")
    t3_at_pnl_r: Decimal = Decimal("4.0")
    t4_at_pnl_r: Decimal = Decimal("6.0")
    t1_atr_multiplier: Decimal = Decimal("2.0")
    t2_atr_multiplier: Decimal = Decimal("1.5")
    t3_atr_multiplier: Decimal = Decimal("1.1")
    t4_atr_multiplier: Decimal = Decimal("0.8")
    emergency_buffer_bps: Decimal = Decimal("50")
    structural_min_adx: Decimal = Decimal("25.0")
    structural_confirmed_highs: int = 2
    structural_confirmed_lows: int = 2


class TrailingPolicy:
    """
    Институциональная логика трейлинг-стопа поверх позиционного RiskLedger.
    """

    def __init__(
        self,
        risk_ledger: RiskLedger,
        config: TrailingPolicyConfig | None = None,
    ) -> None:
        self._risk_ledger = risk_ledger
        self._config = config or TrailingPolicyConfig()

    def evaluate(
        self,
        *,
        position_id: str,
        pnl_r: Decimal,
        market: MarketSnapshot,
        system_state: SystemState | str,
    ) -> StopUpdate:
        """
        Оценить необходимость движения стопа по позиции.
        """
        record = self._risk_ledger.get_position_record(position_id)
        resolved_state = self._normalize_system_state(system_state)
        self._validate_inputs(record=record, pnl_r=pnl_r, market=market)

        if record.trailing_state is TrailingState.TERMINATED:
            return self._blocked_update(
                record=record,
                pnl_r=pnl_r,
                mode=TrailingMode.NORMAL,
                tier=self._select_tier(pnl_r),
                state=resolved_state,
                reason="Трейлинг уже завершён",
            )

        if resolved_state is SystemState.HALT:
            return self._blocked_update(
                record=record,
                pnl_r=pnl_r,
                mode=TrailingMode.NORMAL,
                tier=self._select_tier(pnl_r),
                state=resolved_state,
                reason="В состоянии HALT движение стопа запрещено",
            )

        if market.is_stale:
            return self._sync_state_without_stop_move(
                record=record,
                next_state=TrailingState.EMERGENCY,
                pnl_r=pnl_r,
                mode=TrailingMode.EMERGENCY,
                tier=self._select_tier(pnl_r),
                system_state=resolved_state,
                reason="Рыночные данные устарели, движение стопа заблокировано",
            )

        mode = self._determine_mode(
            record=record,
            pnl_r=pnl_r,
            market=market,
            system_state=resolved_state,
        )
        tier = self._select_tier(pnl_r)
        next_state = self._next_trailing_state(
            current_state=record.trailing_state,
            pnl_r=pnl_r,
            mode=mode,
        )

        if pnl_r < self._config.arm_at_pnl_r:
            return self._sync_state_without_stop_move(
                record=record,
                next_state=next_state,
                pnl_r=pnl_r,
                mode=mode,
                tier=tier,
                system_state=resolved_state,
                reason="Arm threshold ещё не достигнут, движение стопа заблокировано",
            )

        candidate_stop = self._calculate_candidate_stop(
            record=record,
            market=market,
            tier=tier,
            mode=mode,
        )
        next_stop = self._ensure_monotonic_stop(record=record, candidate_stop=candidate_stop)

        if next_stop == record.current_stop:
            return self._sync_state_without_stop_move(
                record=record,
                next_state=next_state,
                pnl_r=pnl_r,
                mode=mode,
                tier=tier,
                system_state=resolved_state,
                reason="Новый стоп не улучшает текущий уровень риска",
            )

        risk_after = self._calculate_risk_r(record=record, stop=next_stop)
        update = self._build_update(
            record=record,
            new_stop=next_stop,
            pnl_r=pnl_r,
            evaluation_type=TrailingEvaluationType.MOVE,
            tier=tier,
            mode=mode,
            system_state=resolved_state,
            risk_after=risk_after,
            should_execute=True,
            reason="Стоп передвинут по правилам TrailingPolicy",
        )
        self._check_invariants(record=record, update=update)
        return self._sync_stop_move(update=update, next_state=next_state)

    def force_emergency(
        self,
        *,
        position_id: str,
        pnl_r: Decimal,
        market: MarketSnapshot,
        system_state: SystemState | str,
    ) -> StopUpdate:
        """
        Принудительно оценить stop move в EMERGENCY режиме.
        """
        record = self._risk_ledger.get_position_record(position_id)
        resolved_state = self._normalize_system_state(system_state)
        self._validate_inputs(record=record, pnl_r=pnl_r, market=market)

        if resolved_state is SystemState.HALT:
            return self._blocked_update(
                record=record,
                pnl_r=pnl_r,
                mode=TrailingMode.EMERGENCY,
                tier=self._select_tier(pnl_r),
                state=resolved_state,
                reason="В состоянии HALT emergency trailing запрещён",
            )

        candidate_stop = self._calculate_candidate_stop(
            record=record,
            market=market,
            tier=self._select_tier(pnl_r),
            mode=TrailingMode.EMERGENCY,
        )
        next_stop = self._ensure_monotonic_stop(record=record, candidate_stop=candidate_stop)

        if next_stop == record.current_stop:
            return self._sync_state_without_stop_move(
                record=record,
                next_state=TrailingState.EMERGENCY,
                pnl_r=pnl_r,
                mode=TrailingMode.EMERGENCY,
                tier=self._select_tier(pnl_r),
                system_state=resolved_state,
                reason="Emergency trailing не дал более жёсткого стопа",
            )

        risk_after = self._calculate_risk_r(record=record, stop=next_stop)
        update = self._build_update(
            record=record,
            new_stop=next_stop,
            pnl_r=pnl_r,
            evaluation_type=TrailingEvaluationType.MOVE,
            tier=self._select_tier(pnl_r),
            mode=TrailingMode.EMERGENCY,
            system_state=resolved_state,
            risk_after=risk_after,
            should_execute=True,
            reason="Стоп передвинут в EMERGENCY режиме",
        )
        self._check_invariants(record=record, update=update)
        return self._sync_stop_move(update=update, next_state=TrailingState.EMERGENCY)

    def terminate(self, *, position_id: str, system_state: SystemState | str) -> StopUpdate:
        """
        Завершить трейлинг без движения стопа.
        """
        record = self._risk_ledger.get_position_record(position_id)
        resolved_state = self._normalize_system_state(system_state)
        return self._sync_state_without_stop_move(
            record=record,
            next_state=TrailingState.TERMINATED,
            pnl_r=Decimal("0"),
            evaluation_type=TrailingEvaluationType.TERMINATE,
            mode=TrailingMode.NORMAL,
            tier=TrailingTier.T1,
            system_state=resolved_state,
            reason="Трейлинг переведён в TERMINATED; pnl_r для terminate snapshot не применяется",
        )

    def _select_tier(self, pnl_r: Decimal) -> TrailingTier:
        """Выбрать tier по текущему PnL в R."""
        if pnl_r >= self._config.t4_at_pnl_r:
            return TrailingTier.T4
        if pnl_r >= self._config.t3_at_pnl_r:
            return TrailingTier.T3
        if pnl_r >= self._config.t2_at_pnl_r:
            return TrailingTier.T2
        return TrailingTier.T1

    def _determine_mode(
        self,
        *,
        record: PositionRiskRecord,
        pnl_r: Decimal,
        market: MarketSnapshot,
        system_state: SystemState,
    ) -> TrailingMode:
        """Определить режим работы трейлинга."""
        if system_state in {
            SystemState.RISK_REDUCTION,
            SystemState.SURVIVAL,
        }:
            return TrailingMode.EMERGENCY
        if record.trailing_state is TrailingState.EMERGENCY:
            return TrailingMode.EMERGENCY
        if self._can_use_structural_trailing(
            record=record,
            market=market,
            pnl_r=pnl_r,
            system_state=system_state,
        ):
            return TrailingMode.STRUCTURAL
        return TrailingMode.NORMAL

    def _can_use_structural_trailing(
        self,
        *,
        record: PositionRiskRecord,
        market: MarketSnapshot,
        pnl_r: Decimal,
        system_state: SystemState,
    ) -> bool:
        """Проверить допустимость structural trailing."""
        if pnl_r < self._config.arm_at_pnl_r:
            return False
        if market.structural_stop is None:
            return False
        if system_state is not SystemState.TRADING:
            return False
        if market.adx <= self._config.structural_min_adx:
            return False
        if record.side is PositionSide.LONG:
            return market.confirmed_highs >= self._config.structural_confirmed_highs
        return market.confirmed_lows >= self._config.structural_confirmed_lows

    def _next_trailing_state(
        self,
        *,
        current_state: TrailingState,
        pnl_r: Decimal,
        mode: TrailingMode,
    ) -> TrailingState:
        """Определить следующее состояние трейлинга."""
        if current_state is TrailingState.TERMINATED:
            return current_state
        if mode is TrailingMode.EMERGENCY:
            return TrailingState.EMERGENCY
        if pnl_r < self._config.arm_at_pnl_r:
            return current_state if current_state is not TrailingState.INACTIVE else TrailingState.INACTIVE
        if pnl_r < self._config.t2_at_pnl_r:
            return TrailingState.ARMED
        return TrailingState.ACTIVE

    def _calculate_candidate_stop(
        self,
        *,
        record: PositionRiskRecord,
        market: MarketSnapshot,
        tier: TrailingTier,
        mode: TrailingMode,
    ) -> Decimal:
        """Рассчитать кандидат на новый стоп."""
        if mode is TrailingMode.EMERGENCY:
            return self._calculate_emergency_stop(record=record, market=market)
        if mode is TrailingMode.STRUCTURAL and market.structural_stop is not None:
            return market.structural_stop
        return self._calculate_normal_stop(record=record, market=market, tier=tier)

    def _calculate_normal_stop(
        self,
        *,
        record: PositionRiskRecord,
        market: MarketSnapshot,
        tier: TrailingTier,
    ) -> Decimal:
        """Рассчитать стоп в NORMAL режиме."""
        multiplier = {
            TrailingTier.T1: self._config.t1_atr_multiplier,
            TrailingTier.T2: self._config.t2_atr_multiplier,
            TrailingTier.T3: self._config.t3_atr_multiplier,
            TrailingTier.T4: self._config.t4_atr_multiplier,
        }[tier]
        offset = market.atr * multiplier
        if record.side is PositionSide.LONG:
            return market.mark_price - offset
        return market.mark_price + offset

    def _calculate_emergency_stop(
        self,
        *,
        record: PositionRiskRecord,
        market: MarketSnapshot,
    ) -> Decimal:
        """Рассчитать более жёсткий стоп в EMERGENCY режиме."""
        buffer_multiplier = Decimal("1") + (
            self._config.emergency_buffer_bps / Decimal("10000")
        )
        inverse_buffer_multiplier = Decimal("1") - (
            self._config.emergency_buffer_bps / Decimal("10000")
        )
        if record.side is PositionSide.LONG:
            return market.best_bid * inverse_buffer_multiplier
        return market.best_ask * buffer_multiplier

    def _ensure_monotonic_stop(
        self,
        *,
        record: PositionRiskRecord,
        candidate_stop: Decimal,
    ) -> Decimal:
        """Обеспечить монотонность стопа."""
        if record.side is PositionSide.LONG:
            return max(candidate_stop, record.current_stop)
        return min(candidate_stop, record.current_stop)

    def _check_invariants(self, *, record: PositionRiskRecord, update: StopUpdate) -> None:
        """Проверить инварианты трейлинга перед синхронизацией с ledger."""
        if update.mode is not TrailingMode.EMERGENCY and update.state == SystemState.HALT.value:
            raise TrailingInputError("Нельзя двигать стоп в состоянии HALT")
        if record.side is PositionSide.LONG and update.new_stop < update.old_stop:
            raise TrailingInputError("Стоп LONG-позиции не может двигаться вниз")
        if record.side is PositionSide.SHORT and update.new_stop > update.old_stop:
            raise TrailingInputError("Стоп SHORT-позиции не может двигаться вверх")
        if update.risk_after > update.risk_before:
            raise TrailingInputError("Трейлинг не может увеличивать риск позиции")

    def _sync_stop_move(self, *, update: StopUpdate, next_state: TrailingState) -> StopUpdate:
        """Синхронизировать движение стопа с RiskLedger."""
        try:
            synced = self._risk_ledger.update_position_risk(
                position_id=update.position_id,
                new_stop=update.new_stop,
                trailing_state=next_state,
            )
        except Exception as error:
            return StopUpdate(
                position_id=update.position_id,
                old_stop=update.old_stop,
                new_stop=update.old_stop,
                pnl_r=update.pnl_r,
                evaluation_type=TrailingEvaluationType.BLOCKED,
                tier=update.tier,
                mode=update.mode,
                state=update.state,
                risk_before=update.risk_before,
                risk_after=update.risk_before,
                should_execute=False,
                reason=f"Движение стопа заблокировано: ошибка синхронизации с RiskLedger ({error})",
            )

        return StopUpdate(
            position_id=update.position_id,
            old_stop=update.old_stop,
            new_stop=synced.current_stop,
            pnl_r=update.pnl_r,
            evaluation_type=update.evaluation_type,
            tier=update.tier,
            mode=update.mode,
            state=update.state,
            risk_before=update.risk_before,
            risk_after=synced.current_risk_r,
            should_execute=True,
            reason=update.reason,
        )

    def _sync_state_without_stop_move(
        self,
        *,
        record: PositionRiskRecord,
        next_state: TrailingState,
        pnl_r: Decimal,
        mode: TrailingMode,
        tier: TrailingTier,
        system_state: SystemState,
        reason: str,
        evaluation_type: TrailingEvaluationType = TrailingEvaluationType.STATE_SYNC,
    ) -> StopUpdate:
        """Синхронизировать state-only изменение через RiskLedger без движения стопа."""
        blocked = self._build_update(
            record=record,
            new_stop=record.current_stop,
            pnl_r=pnl_r,
            evaluation_type=evaluation_type,
            tier=tier,
            mode=mode,
            system_state=system_state,
            risk_after=record.current_risk_r,
            should_execute=False,
            reason=reason,
        )
        try:
            synced = self._risk_ledger.update_position_risk(
                position_id=record.position_id,
                new_stop=record.current_stop,
                trailing_state=next_state,
            )
        except Exception as error:
            return StopUpdate(
                position_id=blocked.position_id,
                old_stop=blocked.old_stop,
                new_stop=blocked.old_stop,
                pnl_r=blocked.pnl_r,
                evaluation_type=TrailingEvaluationType.BLOCKED,
                tier=blocked.tier,
                mode=blocked.mode,
                state=blocked.state,
                risk_before=blocked.risk_before,
                risk_after=blocked.risk_before,
                should_execute=False,
                reason=f"{reason}. Синхронизация состояния с RiskLedger не удалась: {error}",
            )

        return StopUpdate(
            position_id=blocked.position_id,
            old_stop=blocked.old_stop,
            new_stop=blocked.old_stop,
            pnl_r=blocked.pnl_r,
            evaluation_type=blocked.evaluation_type,
            tier=blocked.tier,
            mode=blocked.mode,
            state=blocked.state,
            risk_before=blocked.risk_before,
            risk_after=synced.current_risk_r,
            should_execute=False,
            reason=reason,
        )

    def _build_update(
        self,
        *,
        record: PositionRiskRecord,
        new_stop: Decimal,
        pnl_r: Decimal,
        evaluation_type: TrailingEvaluationType,
        tier: TrailingTier,
        mode: TrailingMode,
        system_state: SystemState,
        risk_after: Decimal,
        should_execute: bool,
        reason: str,
    ) -> StopUpdate:
        """Собрать доменный результат оценки стопа."""
        return StopUpdate(
            position_id=record.position_id,
            old_stop=record.current_stop,
            new_stop=new_stop,
            pnl_r=pnl_r,
            evaluation_type=evaluation_type,
            tier=tier,
            mode=mode,
            state=system_state.value,
            risk_before=record.current_risk_r,
            risk_after=risk_after,
            should_execute=should_execute,
            reason=reason,
        )

    def _blocked_update(
        self,
        *,
        record: PositionRiskRecord,
        pnl_r: Decimal,
        mode: TrailingMode,
        tier: TrailingTier,
        state: SystemState,
        reason: str,
    ) -> StopUpdate:
        """Сформировать заблокированный результат без движения стопа."""
        return StopUpdate(
            position_id=record.position_id,
            old_stop=record.current_stop,
            new_stop=record.current_stop,
            pnl_r=pnl_r,
            evaluation_type=TrailingEvaluationType.BLOCKED,
            tier=tier,
            mode=mode,
            state=state.value,
            risk_before=record.current_risk_r,
            risk_after=record.current_risk_r,
            should_execute=False,
            reason=reason,
        )

    @staticmethod
    def _normalize_system_state(system_state: SystemState | str) -> SystemState:
        """Нормализовать входное состояние системы."""
        return system_state if isinstance(system_state, SystemState) else SystemState(system_state)

    @staticmethod
    def _validate_inputs(
        *,
        record: PositionRiskRecord,
        pnl_r: Decimal,
        market: MarketSnapshot,
    ) -> None:
        """Проверить входные данные оценки трейлинга."""
        if pnl_r < 0:
            raise TrailingInputError("PnL в R не может быть отрицательным для трейлинга")
        for name, value in {
            "mark_price": market.mark_price,
            "atr": market.atr,
            "best_bid": market.best_bid,
            "best_ask": market.best_ask,
            "adx": market.adx,
            "entry_price": record.entry_price,
            "current_stop": record.current_stop,
        }.items():
            if value <= 0:
                raise TrailingInputError(f"Поле {name} должно быть положительным")
        if market.best_bid > market.best_ask:
            raise TrailingInputError("best_bid не может быть больше best_ask")

    @staticmethod
    def _calculate_risk_r(
        *,
        record: PositionRiskRecord,
        stop: Decimal,
    ) -> Decimal:
        """Рассчитать риск позиции в R для кандидата нового стопа."""
        if record.side is PositionSide.LONG:
            risk_usd = max(record.entry_price - stop, Decimal("0")) * record.quantity
        else:
            risk_usd = max(stop - record.entry_price, Decimal("0")) * record.quantity
        return risk_usd / record.risk_capital_usd
