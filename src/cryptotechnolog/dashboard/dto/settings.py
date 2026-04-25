"""DTO модели для backend-backed dashboard settings endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from cryptotechnolog.config.settings import Settings


class UniversePolicySettingsDTO(BaseModel):
    """Universe policy settings surfaced for product settings UI."""

    max_spread_bps: float = Field(
        description="Максимально допустимый спред инструмента в bps.",
    )
    min_top_depth_usd: float = Field(
        description="Минимальная глубина в верхушке стакана в USD.",
    )
    min_depth_5bps_usd: float = Field(
        description="Минимальная суммарная глубина в диапазоне 5 bps в USD.",
    )
    max_latency_ms: float = Field(
        description="Максимально допустимая задержка рыночных данных в миллисекундах.",
    )
    min_coverage_ratio: float = Field(
        description="Минимальная доля покрытия рыночных данных для допуска инструмента.",
    )
    max_data_age_ms: int = Field(
        description="Максимально допустимая старость рыночных данных в миллисекундах.",
    )
    min_quality_score: float = Field(
        description="Минимальная оценка качества данных для допуска инструмента.",
    )
    min_ready_instruments: int = Field(
        description="Минимальное число пригодных инструментов для состояния READY.",
    )
    min_degraded_instruments_ratio: float = Field(
        description="Минимальная доля пригодных инструментов для режима DEGRADED.",
    )
    min_ready_confidence: float = Field(
        description="Минимальная уверенность universe для состояния READY.",
    )
    min_degraded_confidence: float = Field(
        description="Минимальная уверенность universe для режима DEGRADED.",
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> UniversePolicySettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            max_spread_bps=settings.universe_max_spread_bps,
            min_top_depth_usd=settings.universe_min_top_depth_usd,
            min_depth_5bps_usd=settings.universe_min_depth_5bps_usd,
            max_latency_ms=settings.universe_max_latency_ms,
            min_coverage_ratio=settings.universe_min_coverage_ratio,
            max_data_age_ms=settings.universe_max_data_age_ms,
            min_quality_score=settings.universe_min_quality_score,
            min_ready_instruments=settings.universe_min_ready_instruments,
            min_degraded_instruments_ratio=settings.universe_min_degraded_instruments_ratio,
            min_ready_confidence=settings.universe_min_ready_confidence,
            min_degraded_confidence=settings.universe_min_degraded_confidence,
        )

    def to_settings_update(self) -> dict[str, float | int]:
        """Convert DTO back into Settings field updates."""
        return {
            "universe_max_spread_bps": self.max_spread_bps,
            "universe_min_top_depth_usd": self.min_top_depth_usd,
            "universe_min_depth_5bps_usd": self.min_depth_5bps_usd,
            "universe_max_latency_ms": self.max_latency_ms,
            "universe_min_coverage_ratio": self.min_coverage_ratio,
            "universe_max_data_age_ms": self.max_data_age_ms,
            "universe_min_quality_score": self.min_quality_score,
            "universe_min_ready_instruments": self.min_ready_instruments,
            "universe_min_degraded_instruments_ratio": self.min_degraded_instruments_ratio,
            "universe_min_ready_confidence": self.min_ready_confidence,
            "universe_min_degraded_confidence": self.min_degraded_confidence,
        }


class DecisionChainSettingsDTO(BaseModel):
    """Decision-chain thresholds surfaced for product settings UI."""

    signal_min_trend_strength: float = Field(
        description="Минимальная сила тренда для генерации сигнала.",
    )
    signal_min_regime_confidence: float = Field(
        description="Минимальная уверенность режима для генерации сигнала.",
    )
    signal_target_risk_reward: float = Field(
        description="Целевое отношение риск/прибыль на уровне сигнала.",
    )
    signal_max_age_seconds: int = Field(
        description="Максимальный срок жизни сигнала в секундах.",
    )
    strategy_min_signal_confidence: float = Field(
        description="Минимальная уверенность сигнала для стратегического действия.",
    )
    strategy_max_candidate_age_seconds: int = Field(
        description="Максимальный срок жизни стратегического кандидата в секундах.",
    )
    execution_min_strategy_confidence: float = Field(
        description="Минимальная уверенность стратегии для намерения на исполнение.",
    )
    execution_max_intent_age_seconds: int = Field(
        description="Максимальный срок жизни намерения на исполнение в секундах.",
    )
    opportunity_min_confidence: float = Field(
        description="Минимальная уверенность для отбора возможности.",
    )
    opportunity_min_priority: float = Field(
        description="Минимальный приоритет для отбора возможности.",
    )
    opportunity_max_age_seconds: int = Field(
        description="Максимальный срок жизни выбранной возможности в секундах.",
    )
    orchestration_min_confidence: float = Field(
        description="Минимальная уверенность для передачи решения дальше.",
    )
    orchestration_min_priority: float = Field(
        description="Минимальный приоритет для передачи решения дальше.",
    )
    orchestration_max_decision_age_seconds: int = Field(
        description="Максимальный срок жизни orchestration-решения в секундах.",
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> DecisionChainSettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            signal_min_trend_strength=settings.signal_min_trend_strength,
            signal_min_regime_confidence=settings.signal_min_regime_confidence,
            signal_target_risk_reward=settings.signal_target_risk_reward,
            signal_max_age_seconds=settings.signal_max_age_seconds,
            strategy_min_signal_confidence=settings.strategy_min_signal_confidence,
            strategy_max_candidate_age_seconds=settings.strategy_max_candidate_age_seconds,
            execution_min_strategy_confidence=settings.execution_min_strategy_confidence,
            execution_max_intent_age_seconds=settings.execution_max_intent_age_seconds,
            opportunity_min_confidence=settings.opportunity_min_confidence,
            opportunity_min_priority=settings.opportunity_min_priority,
            opportunity_max_age_seconds=settings.opportunity_max_age_seconds,
            orchestration_min_confidence=settings.orchestration_min_confidence,
            orchestration_min_priority=settings.orchestration_min_priority,
            orchestration_max_decision_age_seconds=settings.orchestration_max_decision_age_seconds,
        )

    def to_settings_update(self) -> dict[str, float | int]:
        """Convert DTO back into Settings field updates."""
        return {
            "signal_min_trend_strength": self.signal_min_trend_strength,
            "signal_min_regime_confidence": self.signal_min_regime_confidence,
            "signal_target_risk_reward": self.signal_target_risk_reward,
            "signal_max_age_seconds": self.signal_max_age_seconds,
            "strategy_min_signal_confidence": self.strategy_min_signal_confidence,
            "strategy_max_candidate_age_seconds": self.strategy_max_candidate_age_seconds,
            "execution_min_strategy_confidence": self.execution_min_strategy_confidence,
            "execution_max_intent_age_seconds": self.execution_max_intent_age_seconds,
            "opportunity_min_confidence": self.opportunity_min_confidence,
            "opportunity_min_priority": self.opportunity_min_priority,
            "opportunity_max_age_seconds": self.opportunity_max_age_seconds,
            "orchestration_min_confidence": self.orchestration_min_confidence,
            "orchestration_min_priority": self.orchestration_min_priority,
            "orchestration_max_decision_age_seconds": self.orchestration_max_decision_age_seconds,
        }


class RiskLimitsSettingsDTO(BaseModel):
    """Base risk limits surfaced for product settings UI."""

    base_r_percent: float = Field(
        description="Базовый риск на сделку как доля капитала.",
    )
    max_r_per_trade: float = Field(
        description="Максимальный риск на одну сделку в R.",
    )
    max_portfolio_r: float = Field(
        description="Максимальный суммарный риск по портфелю в R.",
    )
    risk_max_total_exposure_usd: float = Field(
        description="Максимальная суммарная экспозиция по портфелю в USD.",
    )
    max_position_size: float = Field(
        description="Максимальный размер одной позиции в USD.",
    )
    risk_starting_equity: float = Field(
        description="Стартовый капитал для risk runtime и drawdown baseline.",
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> RiskLimitsSettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            base_r_percent=settings.base_r_percent,
            max_r_per_trade=settings.max_r_per_trade,
            max_portfolio_r=settings.max_portfolio_r,
            risk_max_total_exposure_usd=settings.risk_max_total_exposure_usd,
            max_position_size=settings.max_position_size,
            risk_starting_equity=settings.risk_starting_equity,
        )

    def to_settings_update(self) -> dict[str, float]:
        """Convert DTO back into Settings field updates."""
        return {
            "base_r_percent": self.base_r_percent,
            "max_r_per_trade": self.max_r_per_trade,
            "max_portfolio_r": self.max_portfolio_r,
            "risk_max_total_exposure_usd": self.risk_max_total_exposure_usd,
            "max_position_size": self.max_position_size,
            "risk_starting_equity": self.risk_starting_equity,
        }


class TrailingPolicySettingsDTO(BaseModel):
    """Trailing policy thresholds surfaced for product settings UI."""

    arm_at_pnl_r: float = Field(description="Порог прибыли в R для включения трейлинга.")
    t2_at_pnl_r: float = Field(description="Порог прибыли в R для второго уровня трейлинга.")
    t3_at_pnl_r: float = Field(description="Порог прибыли в R для третьего уровня трейлинга.")
    t4_at_pnl_r: float = Field(description="Порог прибыли в R для четвёртого уровня трейлинга.")
    t1_atr_multiplier: float = Field(description="ATR-множитель для первого уровня трейлинга.")
    t2_atr_multiplier: float = Field(description="ATR-множитель для второго уровня трейлинга.")
    t3_atr_multiplier: float = Field(description="ATR-множитель для третьего уровня трейлинга.")
    t4_atr_multiplier: float = Field(description="ATR-множитель для четвёртого уровня трейлинга.")
    emergency_buffer_bps: float = Field(description="Аварийный защитный буфер в bps.")
    structural_min_adx: float = Field(
        description="Минимальная сила тренда для structural trailing.",
    )
    structural_confirmed_highs: int = Field(
        description="Минимум подтверждённых максимумов для structural trailing.",
    )
    structural_confirmed_lows: int = Field(
        description="Минимум подтверждённых минимумов для structural trailing.",
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> TrailingPolicySettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            arm_at_pnl_r=settings.trailing_arm_at_pnl_r,
            t2_at_pnl_r=settings.trailing_t2_at_pnl_r,
            t3_at_pnl_r=settings.trailing_t3_at_pnl_r,
            t4_at_pnl_r=settings.trailing_t4_at_pnl_r,
            t1_atr_multiplier=settings.trailing_t1_atr_multiplier,
            t2_atr_multiplier=settings.trailing_t2_atr_multiplier,
            t3_atr_multiplier=settings.trailing_t3_atr_multiplier,
            t4_atr_multiplier=settings.trailing_t4_atr_multiplier,
            emergency_buffer_bps=settings.trailing_emergency_buffer_bps,
            structural_min_adx=settings.trailing_structural_min_adx,
            structural_confirmed_highs=settings.trailing_structural_confirmed_highs,
            structural_confirmed_lows=settings.trailing_structural_confirmed_lows,
        )

    def to_settings_update(self) -> dict[str, float | int]:
        """Convert DTO back into Settings field updates."""
        return {
            "trailing_arm_at_pnl_r": self.arm_at_pnl_r,
            "trailing_t2_at_pnl_r": self.t2_at_pnl_r,
            "trailing_t3_at_pnl_r": self.t3_at_pnl_r,
            "trailing_t4_at_pnl_r": self.t4_at_pnl_r,
            "trailing_t1_atr_multiplier": self.t1_atr_multiplier,
            "trailing_t2_atr_multiplier": self.t2_atr_multiplier,
            "trailing_t3_atr_multiplier": self.t3_atr_multiplier,
            "trailing_t4_atr_multiplier": self.t4_atr_multiplier,
            "trailing_emergency_buffer_bps": self.emergency_buffer_bps,
            "trailing_structural_min_adx": self.structural_min_adx,
            "trailing_structural_confirmed_highs": self.structural_confirmed_highs,
            "trailing_structural_confirmed_lows": self.structural_confirmed_lows,
        }


class CorrelationPolicySettingsDTO(BaseModel):
    """Correlation policy thresholds surfaced for product settings UI."""

    correlation_limit: float = Field(
        description="Максимально допустимая корреляция между позициями.",
    )
    same_group_correlation: float = Field(
        description="Допустимая корреляция внутри одной группы инструментов.",
    )
    cross_group_correlation: float = Field(
        description="Допустимая корреляция между разными группами инструментов.",
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> CorrelationPolicySettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            correlation_limit=settings.correlation_limit,
            same_group_correlation=settings.same_group_correlation,
            cross_group_correlation=settings.cross_group_correlation,
        )

    def to_settings_update(self) -> dict[str, float]:
        """Convert DTO back into Settings field updates."""
        return {
            "correlation_limit": self.correlation_limit,
            "same_group_correlation": self.same_group_correlation,
            "cross_group_correlation": self.cross_group_correlation,
        }


class ProtectionPolicySettingsDTO(BaseModel):
    """Protection policy thresholds surfaced for product settings UI."""

    halt_priority_threshold: float = Field(
        description="Порог, после которого включается жёсткая защита.",
    )
    freeze_priority_threshold: float = Field(
        description="Порог, после которого система замораживает новые действия.",
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> ProtectionPolicySettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            halt_priority_threshold=settings.protection_halt_priority_threshold,
            freeze_priority_threshold=settings.protection_freeze_priority_threshold,
        )

    def to_settings_update(self) -> dict[str, float]:
        """Convert DTO back into Settings field updates."""
        return {
            "protection_halt_priority_threshold": self.halt_priority_threshold,
            "protection_freeze_priority_threshold": self.freeze_priority_threshold,
        }


class FundingPolicySettingsDTO(BaseModel):
    """Funding-manager thresholds surfaced for product settings UI."""

    min_arbitrage_spread: float = Field(
        description="Минимальный funding-спред для межбиржевой возможности.",
    )
    min_annualized_spread: float = Field(
        description="Минимальный годовой funding-спред для межбиржевой возможности.",
    )
    max_acceptable_funding: float = Field(
        description="Максимально допустимая funding-ставка для новой позиции.",
    )
    min_exchange_improvement: float = Field(
        description="Минимальное улучшение между биржами для перевода позиции.",
    )
    min_quotes_for_opportunity: int = Field(
        description="Минимальное число котировок для поиска funding-возможности.",
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> FundingPolicySettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            min_arbitrage_spread=settings.funding_min_arbitrage_spread,
            min_annualized_spread=settings.funding_min_annualized_spread,
            max_acceptable_funding=settings.funding_max_acceptable_rate,
            min_exchange_improvement=settings.funding_min_exchange_improvement,
            min_quotes_for_opportunity=settings.funding_min_quotes_for_opportunity,
        )

    def to_settings_update(self) -> dict[str, float | int]:
        """Convert DTO back into Settings field updates."""
        return {
            "funding_min_arbitrage_spread": self.min_arbitrage_spread,
            "funding_min_annualized_spread": self.min_annualized_spread,
            "funding_max_acceptable_rate": self.max_acceptable_funding,
            "funding_min_exchange_improvement": self.min_exchange_improvement,
            "funding_min_quotes_for_opportunity": self.min_quotes_for_opportunity,
        }


class SystemStatePolicySettingsDTO(BaseModel):
    """System-state policy values surfaced for product settings UI."""

    trading_risk_multiplier: float = Field(description="Множитель риска для режима TRADING.")
    trading_max_positions: int = Field(description="Лимит открытых позиций для режима TRADING.")
    trading_max_order_size: float = Field(
        description="Максимальный размер новой позиции для режима TRADING.",
    )
    degraded_risk_multiplier: float = Field(description="Множитель риска для режима DEGRADED.")
    degraded_max_positions: int = Field(description="Лимит открытых позиций для режима DEGRADED.")
    degraded_max_order_size: float = Field(
        description="Максимальный размер новой позиции для режима DEGRADED.",
    )
    risk_reduction_risk_multiplier: float = Field(
        description="Множитель риска для режима RISK_REDUCTION.",
    )
    risk_reduction_max_positions: int = Field(
        description="Лимит открытых позиций для режима RISK_REDUCTION.",
    )
    risk_reduction_max_order_size: float = Field(
        description="Максимальный размер новой позиции для режима RISK_REDUCTION.",
    )
    survival_risk_multiplier: float = Field(description="Множитель риска для режима SURVIVAL.")
    survival_max_positions: int = Field(description="Лимит открытых позиций для режима SURVIVAL.")
    survival_max_order_size: float = Field(
        description="Максимальный размер новой позиции для режима SURVIVAL.",
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> SystemStatePolicySettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            trading_risk_multiplier=settings.system_trading_risk_multiplier,
            trading_max_positions=settings.system_trading_max_positions,
            trading_max_order_size=settings.system_trading_max_order_size,
            degraded_risk_multiplier=settings.system_degraded_risk_multiplier,
            degraded_max_positions=settings.system_degraded_max_positions,
            degraded_max_order_size=settings.system_degraded_max_order_size,
            risk_reduction_risk_multiplier=settings.system_risk_reduction_risk_multiplier,
            risk_reduction_max_positions=settings.system_risk_reduction_max_positions,
            risk_reduction_max_order_size=settings.system_risk_reduction_max_order_size,
            survival_risk_multiplier=settings.system_survival_risk_multiplier,
            survival_max_positions=settings.system_survival_max_positions,
            survival_max_order_size=settings.system_survival_max_order_size,
        )

    def to_settings_update(self) -> dict[str, float | int]:
        """Convert DTO back into Settings field updates."""
        return {
            "system_trading_risk_multiplier": self.trading_risk_multiplier,
            "system_trading_max_positions": self.trading_max_positions,
            "system_trading_max_order_size": self.trading_max_order_size,
            "system_degraded_risk_multiplier": self.degraded_risk_multiplier,
            "system_degraded_max_positions": self.degraded_max_positions,
            "system_degraded_max_order_size": self.degraded_max_order_size,
            "system_risk_reduction_risk_multiplier": self.risk_reduction_risk_multiplier,
            "system_risk_reduction_max_positions": self.risk_reduction_max_positions,
            "system_risk_reduction_max_order_size": self.risk_reduction_max_order_size,
            "system_survival_risk_multiplier": self.survival_risk_multiplier,
            "system_survival_max_positions": self.survival_max_positions,
            "system_survival_max_order_size": self.survival_max_order_size,
        }


class SystemStateTimeoutSettingsDTO(BaseModel):
    """System-state timeout values surfaced for product settings UI."""

    boot_max_seconds: int = Field(description="Максимальное время состояния BOOT в секундах.")
    init_max_seconds: int = Field(description="Максимальное время состояния INIT в секундах.")
    ready_max_seconds: int = Field(description="Максимальное время состояния READY в секундах.")
    risk_reduction_max_seconds: int = Field(
        description="Максимальное время состояния RISK_REDUCTION в секундах."
    )
    degraded_max_seconds: int = Field(
        description="Максимальное время состояния DEGRADED в секундах."
    )
    survival_max_seconds: int = Field(
        description="Максимальное время состояния SURVIVAL в секундах."
    )
    error_max_seconds: int = Field(description="Максимальное время состояния ERROR в секундах.")
    recovery_max_seconds: int = Field(
        description="Максимальное время состояния RECOVERY в секундах."
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> SystemStateTimeoutSettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            boot_max_seconds=settings.system_boot_max_seconds,
            init_max_seconds=settings.system_init_max_seconds,
            ready_max_seconds=settings.system_ready_max_seconds,
            risk_reduction_max_seconds=settings.system_risk_reduction_max_seconds,
            degraded_max_seconds=settings.system_degraded_max_seconds,
            survival_max_seconds=settings.system_survival_max_seconds,
            error_max_seconds=settings.system_error_max_seconds,
            recovery_max_seconds=settings.system_recovery_max_seconds,
        )

    def to_settings_update(self) -> dict[str, int]:
        """Convert DTO back into Settings field updates."""
        return {
            "system_boot_max_seconds": self.boot_max_seconds,
            "system_init_max_seconds": self.init_max_seconds,
            "system_ready_max_seconds": self.ready_max_seconds,
            "system_risk_reduction_max_seconds": self.risk_reduction_max_seconds,
            "system_degraded_max_seconds": self.degraded_max_seconds,
            "system_survival_max_seconds": self.survival_max_seconds,
            "system_error_max_seconds": self.error_max_seconds,
            "system_recovery_max_seconds": self.recovery_max_seconds,
        }


class ReliabilityPolicySettingsDTO(BaseModel):
    """Reliability and recovery policy surfaced for product settings UI."""

    circuit_breaker_failure_threshold: int = Field(
        description="Сколько сбоев подряд допускается до открытия circuit breaker.",
    )
    circuit_breaker_recovery_timeout_seconds: int = Field(
        description="Через сколько секунд circuit breaker пробует восстановление.",
    )
    circuit_breaker_success_threshold: int = Field(
        description="Сколько успешных попыток нужно для возврата circuit breaker в норму.",
    )
    watchdog_failure_threshold: int = Field(
        description="Сколько сбоев подряд watchdog считает проблемой.",
    )
    watchdog_backoff_base_seconds: float = Field(
        description="Базовая задержка перед повтором в watchdog.",
    )
    watchdog_backoff_multiplier: float = Field(
        description="Множитель увеличения задержки в watchdog.",
    )
    watchdog_max_backoff_seconds: float = Field(
        description="Максимальная задержка повтора в watchdog.",
    )
    watchdog_jitter_factor: float = Field(
        description="Коэффициент jitter для разброса watchdog retry.",
    )
    watchdog_check_interval_seconds: float = Field(
        description="Интервал проверки watchdog в секундах.",
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> ReliabilityPolicySettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            circuit_breaker_failure_threshold=settings.reliability_circuit_breaker_failure_threshold,
            circuit_breaker_recovery_timeout_seconds=(
                settings.reliability_circuit_breaker_recovery_timeout_seconds
            ),
            circuit_breaker_success_threshold=settings.reliability_circuit_breaker_success_threshold,
            watchdog_failure_threshold=settings.reliability_watchdog_failure_threshold,
            watchdog_backoff_base_seconds=settings.reliability_watchdog_backoff_base_seconds,
            watchdog_backoff_multiplier=settings.reliability_watchdog_backoff_multiplier,
            watchdog_max_backoff_seconds=settings.reliability_watchdog_max_backoff_seconds,
            watchdog_jitter_factor=settings.reliability_watchdog_jitter_factor,
            watchdog_check_interval_seconds=settings.reliability_watchdog_check_interval_seconds,
        )

    def to_settings_update(self) -> dict[str, float | int]:
        """Convert DTO back into Settings field updates."""
        return {
            "reliability_circuit_breaker_failure_threshold": (
                self.circuit_breaker_failure_threshold
            ),
            "reliability_circuit_breaker_recovery_timeout_seconds": (
                self.circuit_breaker_recovery_timeout_seconds
            ),
            "reliability_circuit_breaker_success_threshold": (
                self.circuit_breaker_success_threshold
            ),
            "reliability_watchdog_failure_threshold": self.watchdog_failure_threshold,
            "reliability_watchdog_backoff_base_seconds": self.watchdog_backoff_base_seconds,
            "reliability_watchdog_backoff_multiplier": self.watchdog_backoff_multiplier,
            "reliability_watchdog_max_backoff_seconds": self.watchdog_max_backoff_seconds,
            "reliability_watchdog_jitter_factor": self.watchdog_jitter_factor,
            "reliability_watchdog_check_interval_seconds": self.watchdog_check_interval_seconds,
        }


class HealthPolicySettingsDTO(BaseModel):
    """Health and readiness-check policy surfaced for product settings UI."""

    check_timeout_seconds: float = Field(
        description="Таймаут одной проверки здоровья в секундах.",
    )
    background_check_interval_seconds: float = Field(
        description="Интервал фоновой проверки здоровья в секундах.",
    )
    check_and_wait_timeout_seconds: float = Field(
        description="Максимальное время ожидания общей проверки готовности в секундах.",
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> HealthPolicySettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            check_timeout_seconds=settings.health_check_timeout_seconds,
            background_check_interval_seconds=settings.health_background_check_interval_seconds,
            check_and_wait_timeout_seconds=settings.health_check_and_wait_timeout_seconds,
        )

    def to_settings_update(self) -> dict[str, float]:
        """Convert DTO back into Settings field updates."""
        return {
            "health_check_timeout_seconds": self.check_timeout_seconds,
            "health_background_check_interval_seconds": self.background_check_interval_seconds,
            "health_check_and_wait_timeout_seconds": self.check_and_wait_timeout_seconds,
        }


class EventBusPolicySettingsDTO(BaseModel):
    """Event-bus queue and backpressure policy surfaced for product settings UI."""

    subscriber_capacity: int = Field(
        description="Базовая ёмкость очереди подписчика в событиях.",
    )
    fill_ratio_low: float = Field(
        description="Нижний порог заполнения очереди для backpressure.",
    )
    fill_ratio_normal: float = Field(
        description="Нормальный порог заполнения очереди для backpressure.",
    )
    fill_ratio_high: float = Field(
        description="Высокий порог заполнения очереди для backpressure.",
    )
    push_wait_timeout_seconds: float = Field(
        description="Таймаут ожидания при отправке события в секундах.",
    )
    drain_timeout_seconds: float = Field(
        description="Таймаут ожидания при дренировании очередей в секундах.",
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> EventBusPolicySettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            subscriber_capacity=settings.event_bus_subscriber_capacity,
            fill_ratio_low=settings.event_bus_fill_ratio_low,
            fill_ratio_normal=settings.event_bus_fill_ratio_normal,
            fill_ratio_high=settings.event_bus_fill_ratio_high,
            push_wait_timeout_seconds=settings.event_bus_push_wait_timeout_seconds,
            drain_timeout_seconds=settings.event_bus_drain_timeout_seconds,
        )

    def to_settings_update(self) -> dict[str, float | int]:
        """Convert DTO back into Settings field updates."""
        return {
            "event_bus_subscriber_capacity": self.subscriber_capacity,
            "event_bus_fill_ratio_low": self.fill_ratio_low,
            "event_bus_fill_ratio_normal": self.fill_ratio_normal,
            "event_bus_fill_ratio_high": self.fill_ratio_high,
            "event_bus_push_wait_timeout_seconds": self.push_wait_timeout_seconds,
            "event_bus_drain_timeout_seconds": self.drain_timeout_seconds,
        }


class ManualApprovalPolicySettingsDTO(BaseModel):
    """Manual-approval timeout surfaced for product settings UI."""

    approval_timeout_minutes: int = Field(
        description="Время ожидания ручного подтверждения действия в минутах.",
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> ManualApprovalPolicySettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            approval_timeout_minutes=settings.manual_approval_timeout_minutes,
        )

    def to_settings_update(self) -> dict[str, int]:
        """Convert DTO back into Settings field updates."""
        return {
            "manual_approval_timeout_minutes": self.approval_timeout_minutes,
        }


class WorkflowTimeoutsSettingsDTO(BaseModel):
    """Workflow and service-contour lifetimes surfaced for product settings UI."""

    manager_max_age_seconds: int = Field(
        description="Максимальный срок жизни manager workflow в секундах.",
    )
    validation_max_age_seconds: int = Field(
        description="Максимальный срок жизни validation review в секундах.",
    )
    paper_max_age_seconds: int = Field(
        description="Максимальный срок жизни paper rehearsal в секундах.",
    )
    replay_max_age_seconds: int = Field(
        description="Максимальный срок жизни replay/backtest сессии в секундах.",
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> WorkflowTimeoutsSettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            manager_max_age_seconds=settings.workflow_manager_max_age_seconds,
            validation_max_age_seconds=settings.workflow_validation_max_age_seconds,
            paper_max_age_seconds=settings.workflow_paper_max_age_seconds,
            replay_max_age_seconds=settings.workflow_replay_max_age_seconds,
        )

    def to_settings_update(self) -> dict[str, int]:
        """Convert DTO back into Settings field updates."""
        return {
            "workflow_manager_max_age_seconds": self.manager_max_age_seconds,
            "workflow_validation_max_age_seconds": self.validation_max_age_seconds,
            "workflow_paper_max_age_seconds": self.paper_max_age_seconds,
            "workflow_replay_max_age_seconds": self.replay_max_age_seconds,
        }


class LiveFeedPolicySettingsDTO(BaseModel):
    """Live-feed reconnect policy surfaced for product settings UI."""

    retry_delay_seconds: int = Field(
        description="Базовая задержка перед повторным подключением к live feed в секундах.",
    )
    bybit_spot_universe_min_quote_volume_24h_usd: float = Field(
        description="Минимальный 24h quote volume в USD для coarse prefilter universe of spot.",
    )
    bybit_spot_universe_min_trade_count_24h: int = Field(
        description="Минимальное число сделок за 24h для spot final selection.",
    )
    bybit_spot_quote_asset_filter: Literal["usdt", "usdc", "usdt_usdc"] = Field(
        default="usdt_usdc",
        description="Какие quote-asset пары допускаются в spot universe: usdt, usdc или usdt_usdc.",
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> LiveFeedPolicySettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            retry_delay_seconds=settings.live_feed_retry_delay_seconds,
            bybit_spot_universe_min_quote_volume_24h_usd=(
                settings.bybit_spot_universe_min_quote_volume_24h_usd
            ),
            bybit_spot_universe_min_trade_count_24h=(
                settings.bybit_spot_universe_min_trade_count_24h
            ),
            bybit_spot_quote_asset_filter=settings.bybit_spot_quote_asset_filter,
        )

    def to_settings_update(self) -> dict[str, float | int]:
        """Convert DTO back into Settings field updates."""
        return {
            "live_feed_retry_delay_seconds": self.retry_delay_seconds,
            "bybit_spot_universe_min_quote_volume_24h_usd": (
                self.bybit_spot_universe_min_quote_volume_24h_usd
            ),
            "bybit_spot_universe_min_trade_count_24h": self.bybit_spot_universe_min_trade_count_24h,
            "bybit_spot_quote_asset_filter": self.bybit_spot_quote_asset_filter,
        }


class BybitConnectorDiagnosticsDTO(BaseModel):
    """Read-only Bybit connector diagnostics surfaced for settings UI."""

    class SymbolSnapshotDTO(BaseModel):
        symbol: str = Field(description="Инструмент внутри текущего Bybit connector scope.")
        trade_seen: bool = Field(
            description="Session-local ingest flag: поступали ли trade ticks для этого инструмента в текущем runtime."
        )
        orderbook_seen: bool = Field(
            description="Session-local ingest flag: поступал ли orderbook snapshot для этого инструмента в текущем runtime."
        )
        trade_ingest_seen: bool = Field(
            default=False,
            description="Явный session-local ingest flag для trade ticks по этому инструменту."
        )
        orderbook_ingest_seen: bool = Field(
            default=False,
            description="Явный session-local ingest flag для orderbook snapshot по этому инструменту."
        )
        best_bid: str | None = Field(
            description="Лучший bid для этого инструмента из текущего snapshot."
        )
        best_ask: str | None = Field(
            description="Лучший ask для этого инструмента из текущего snapshot."
        )
        volume_24h_usd: str | None = Field(
            default=None,
            description="Оборот инструмента за 24 часа в USD, если метрика уже доступна.",
        )
        derived_trade_count_24h: int | None = Field(
            default=None,
            description="Derived rolling 24h trade count, когда слой trade-count уже надёжен.",
        )
        bucket_trade_count_24h: int | None = Field(
            default=None,
            description="Текущая bucket-based operational truth для rolling 24h trade count.",
        )
        ledger_trade_count_24h: int | None = Field(
            default=None,
            description="Read-only ledger-based rolling 24h trade count без product switch.",
        )
        trade_count_reconciliation_verdict: str | None = Field(
            default=None,
            description="Read-only comparison verdict между bucket и ledger truth для этого symbol.",
        )
        trade_count_reconciliation_reason: str | None = Field(
            default=None,
            description="Machine-readable причина reconciliation verdict для этого symbol.",
        )
        trade_count_reconciliation_absolute_diff: int | None = Field(
            default=None,
            description="Абсолютное расхождение между bucket и ledger trade count.",
        )
        trade_count_reconciliation_tolerance: int | None = Field(
            default=None,
            description="Какой tolerance policy был применён при reconciliation comparison.",
        )
        trade_count_cutover_readiness_state: str | None = Field(
            default=None,
            description="Read-only readiness groundwork state для этого symbol.",
        )
        trade_count_cutover_readiness_reason: str | None = Field(
            default=None,
            description="Machine-readable причина symbol-level cutover readiness state.",
        )
        observed_trade_count_since_reset: int = Field(
            default=0,
            description="Сколько trade ticks накоплено с последнего reliability reset.",
        )
        product_trade_count_24h: int | None = Field(
            default=None,
            description="User-facing 24h trade count. Может быть partial только вместе с non-final product state.",
        )
        product_trade_count_state: str | None = Field(
            default=None,
            description="Machine-readable product truth state для user-facing 24h trade count.",
        )
        product_trade_count_reason: str | None = Field(
            default=None,
            description="Machine-readable причина текущего product truth state для user-facing count.",
        )
        product_trade_count_truth_owner: str | None = Field(
            default=None,
            description="Кто владеет final product truth для symbol-level trade_count_24h.",
        )
        product_trade_count_truth_source: str | None = Field(
            default=None,
            description="Из какого source path пришёл final product truth для symbol-level trade_count_24h.",
        )

    class CutoverDiscussionVerdictCountDTO(BaseModel):
        name: str = Field(description="Имя reconciliation verdict внутри discussion artifact.")
        count: int = Field(description="Сколько symbol paths попало в этот reconciliation verdict.")

    class CutoverDiscussionExceptionDTO(BaseModel):
        symbol: str = Field(description="Какой symbol попал в discussion exceptions summary.")
        reconciliation_verdict: str | None = Field(
            default=None,
            description="Какой reconciliation verdict делает symbol exception-worthy.",
        )
        reconciliation_reason: str | None = Field(
            default=None,
            description="Machine-readable reconciliation reason для symbol exception.",
        )
        cutover_readiness_state: str | None = Field(
            default=None,
            description="Какой readiness state виден для symbol exception.",
        )
        cutover_readiness_reason: str | None = Field(
            default=None,
            description="Machine-readable readiness reason для symbol exception.",
        )

    class CutoverDiscussionArtifactDTO(BaseModel):
        discussion_state: str = Field(description="Operator-facing discussion state для current scope.")
        headline: str = Field(description="Краткая operator-readable summary line для cutover discussion.")
        contour: str = Field(description="Какой contour сейчас обсуждается.")
        scope_mode: str = Field(description="Какой scope_mode относится к discussion artifact.")
        scope_symbol_count: int = Field(description="Сколько symbols входит в current discussion scope.")
        reconciliation_summary: tuple["BybitConnectorDiagnosticsDTO.CutoverDiscussionVerdictCountDTO", ...] = Field(
            description="Aggregate breakdown reconciliation verdicts внутри discussion artifact."
        )
        cutover_readiness_state: str = Field(description="Aggregate readiness state внутри discussion artifact.")
        cutover_readiness_reason: str = Field(description="Aggregate readiness reason внутри discussion artifact.")
        cutover_evaluation_state: str = Field(description="Formal evaluation verdict внутри discussion artifact.")
        cutover_evaluation_reasons: tuple[str, ...] = Field(
            description="Machine-readable evaluation reasons внутри discussion artifact."
        )
        manual_review_state: str = Field(description="Manual-review verdict внутри discussion artifact.")
        manual_review_reasons: tuple[str, ...] = Field(
            description="Machine-readable manual-review reasons внутри discussion artifact."
        )
        compared_symbols: int = Field(description="Сколько symbols реально сравнивались для discussion artifact.")
        ready_symbols: int = Field(description="Сколько symbols сейчас выглядят ready внутри discussion artifact.")
        not_ready_symbols: int = Field(description="Сколько symbols сейчас not_ready внутри discussion artifact.")
        blocked_symbols: int = Field(description="Сколько symbols блокируют discussion artifact.")
        symbol_exceptions: tuple["BybitConnectorDiagnosticsDTO.CutoverDiscussionExceptionDTO", ...] = Field(
            description="Symbol-level exceptions summary для operator cutover discussion."
        )

    class CutoverReviewRecordDTO(BaseModel):
        captured_at: str = Field(description="Когда текущий cutover review record snapshot был собран.")
        contour: str = Field(description="Какой contour зафиксирован в review record.")
        scope_mode: str = Field(description="Какой scope_mode зафиксирован в review record.")
        scope_symbol_count: int = Field(description="Сколько symbols входит в archived review record.")
        discussion_state: str = Field(description="Какой discussion state зафиксирован в review record.")
        manual_review_state: str = Field(description="Какой manual-review state зафиксирован в review record.")
        cutover_evaluation_state: str = Field(description="Какой evaluation state зафиксирован в review record.")
        cutover_readiness_state: str = Field(description="Какой readiness state зафиксирован в review record.")
        compared_symbols: int = Field(description="Сколько compared symbols зафиксировано в review record.")
        ready_symbols: int = Field(description="Сколько ready symbols зафиксировано в review record.")
        not_ready_symbols: int = Field(description="Сколько not_ready symbols зафиксировано в review record.")
        blocked_symbols: int = Field(description="Сколько blocked symbols зафиксировано в review record.")
        headline: str = Field(description="Какой operator-facing headline зафиксирован в review record.")
        reasons_summary: tuple[str, ...] = Field(
            description="Какой machine-readable reasons summary зафиксирован в review record."
        )
        symbol_exceptions: tuple["BybitConnectorDiagnosticsDTO.CutoverDiscussionExceptionDTO", ...] = Field(
            description="Какие symbol-level exceptions зафиксированы в review record."
        )

    class CutoverReviewPackageDTO(BaseModel):
        contour: str = Field(description="Какой contour зафиксирован в review package.")
        scope_mode: str = Field(description="Какой scope_mode зафиксирован в review package.")
        scope_symbol_count: int = Field(description="Сколько symbols входит в review package.")
        discussion_state: str = Field(description="Какой discussion state включён в review package.")
        manual_review_state: str = Field(description="Какой manual-review state включён в review package.")
        cutover_evaluation_state: str = Field(description="Какой evaluation state включён в review package.")
        cutover_readiness_state: str = Field(description="Какой readiness state включён в review package.")
        compared_symbols: int = Field(description="Сколько compared symbols включено в review package.")
        ready_symbols: int = Field(description="Сколько ready symbols включено в review package.")
        not_ready_symbols: int = Field(description="Сколько not_ready symbols включено в review package.")
        blocked_symbols: int = Field(description="Сколько blocked symbols включено в review package.")
        headline: str = Field(description="Какой headline включён в review package.")
        reasons_summary: tuple[str, ...] = Field(
            description="Какой reasons summary включён в review package."
        )
        review_record: "BybitConnectorDiagnosticsDTO.CutoverReviewRecordDTO" = Field(
            description="Какой review record snapshot вложен в review package."
        )
        symbol_exceptions: tuple["BybitConnectorDiagnosticsDTO.CutoverDiscussionExceptionDTO", ...] = Field(
            description="Какие symbol-level exceptions включены в review package."
        )

    class CutoverReviewCatalogDTO(BaseModel):
        contour: str = Field(description="Какой contour сейчас отражён в review catalog.")
        scope_mode: str = Field(description="Какой scope_mode сейчас отражён в review catalog.")
        headline: str = Field(description="Какой current package headline отражён в review catalog.")
        discussion_state: str = Field(description="Какой discussion state отражён в review catalog.")
        manual_review_state: str = Field(description="Какой manual-review state отражён в review catalog.")
        cutover_evaluation_state: str = Field(description="Какой evaluation state отражён в review catalog.")
        cutover_readiness_state: str = Field(description="Какой readiness state отражён в review catalog.")
        compared_symbols: int = Field(description="Сколько compared symbols отражено в review catalog.")
        ready_symbols: int = Field(description="Сколько ready symbols отражено в review catalog.")
        not_ready_symbols: int = Field(description="Сколько not_ready symbols отражено в review catalog.")
        blocked_symbols: int = Field(description="Сколько blocked symbols отражено в review catalog.")
        reasons_summary: tuple[str, ...] = Field(
            description="Какой summary-level reasons bundle отражён в review catalog."
        )
        current_review_package: "BybitConnectorDiagnosticsDTO.CutoverReviewPackageDTO" = Field(
            description="Какой current review package payload вложен в review catalog."
        )

    class CutoverReviewSnapshotCollectionDTO(BaseModel):
        contour: str = Field(description="Какой contour сейчас отражён в review snapshot collection.")
        scope_mode: str = Field(description="Какой scope_mode сейчас отражён в review snapshot collection.")
        headline: str = Field(description="Какой current headline отражён в review snapshot collection.")
        discussion_state: str = Field(description="Какой discussion state отражён в review snapshot collection.")
        manual_review_state: str = Field(description="Какой manual-review state отражён в review snapshot collection.")
        cutover_evaluation_state: str = Field(description="Какой evaluation state отражён в review snapshot collection.")
        cutover_readiness_state: str = Field(description="Какой readiness state отражён в review snapshot collection.")
        compared_symbols: int = Field(description="Сколько compared symbols отражено в review snapshot collection.")
        ready_symbols: int = Field(description="Сколько ready symbols отражено в review snapshot collection.")
        not_ready_symbols: int = Field(description="Сколько not_ready symbols отражено в review snapshot collection.")
        blocked_symbols: int = Field(description="Сколько blocked symbols отражено в review snapshot collection.")
        reasons_summary: tuple[str, ...] = Field(
            description="Какой reasons summary отражён в review snapshot collection."
        )
        current_review_package_headline: str = Field(
            description="Какой current review package headline отражён в listing shape."
        )
        current_review_package_discussion_state: str = Field(
            description="Какой current review package discussion state отражён в listing shape."
        )
        current_review_catalog: "BybitConnectorDiagnosticsDTO.CutoverReviewCatalogDTO" = Field(
            description="Какой current review catalog payload вложен в review snapshot collection."
        )

    class CutoverReviewCompactDigestDTO(BaseModel):
        contour: str = Field(description="Какой contour сейчас отражён в compact digest.")
        scope_mode: str = Field(description="Какой scope_mode сейчас отражён в compact digest.")
        headline: str = Field(description="Какой краткий headline отражён в compact digest.")
        discussion_state: str = Field(description="Какой discussion state отражён в compact digest.")
        manual_review_state: str = Field(description="Какой manual-review state отражён в compact digest.")
        cutover_evaluation_state: str = Field(description="Какой evaluation state отражён в compact digest.")
        cutover_readiness_state: str = Field(description="Какой readiness state отражён в compact digest.")
        compared_symbols: int = Field(description="Сколько compared symbols отражено в compact digest.")
        ready_symbols: int = Field(description="Сколько ready symbols отражено в compact digest.")
        not_ready_symbols: int = Field(description="Сколько not_ready symbols отражено в compact digest.")
        blocked_symbols: int = Field(description="Сколько blocked symbols отражено в compact digest.")
        reasons_summary: tuple[str, ...] = Field(
            description="Какой reasons summary отражён в compact digest."
        )
        compact_symbol_exceptions: tuple[str, ...] = Field(
            description="Какой compact symbol-exception summary отражён в compact digest."
        )
        current_review_snapshot_collection: "BybitConnectorDiagnosticsDTO.CutoverReviewSnapshotCollectionDTO" = Field(
            description="Какой current review snapshot collection payload вложен в compact digest."
        )

    class CutoverExportReportBundleDTO(BaseModel):
        contour: str = Field(description="Какой contour сейчас отражён в export/report bundle.")
        scope_mode: str = Field(description="Какой scope_mode сейчас отражён в export/report bundle.")
        headline: str = Field(description="Какой headline сейчас отражён в export/report bundle.")
        discussion_state: str = Field(description="Какой discussion state отражён в export/report bundle.")
        manual_review_state: str = Field(description="Какой manual-review state отражён в export/report bundle.")
        cutover_evaluation_state: str = Field(description="Какой evaluation state отражён в export/report bundle.")
        cutover_readiness_state: str = Field(description="Какой readiness state отражён в export/report bundle.")
        compared_symbols: int = Field(description="Сколько compared symbols отражено в export/report bundle.")
        ready_symbols: int = Field(description="Сколько ready symbols отражено в export/report bundle.")
        not_ready_symbols: int = Field(description="Сколько not_ready symbols отражено в export/report bundle.")
        blocked_symbols: int = Field(description="Сколько blocked symbols отражено в export/report bundle.")
        reasons_summary: tuple[str, ...] = Field(
            description="Какой reasons summary отражён в export/report bundle."
        )
        compact_symbol_exceptions: tuple[str, ...] = Field(
            description="Какой compact symbol-exception summary отражён в export/report bundle."
        )
        export_text_summary: str = Field(
            description="Какой export-friendly text summary отражён в export/report bundle."
        )
        current_compact_digest: "BybitConnectorDiagnosticsDTO.CutoverReviewCompactDigestDTO" = Field(
            description="Какой current compact digest вложен в export/report bundle."
        )

    enabled: bool = Field(description="Включён ли Bybit connector в текущем runtime.")
    symbol: str | None = Field(description="Текущий symbol scope Bybit connector.")
    symbols: tuple[str, ...] = Field(description="Полный текущий symbol scope Bybit connector-а.")
    symbol_snapshots: tuple[SymbolSnapshotDTO, ...] = Field(
        description="Per-symbol diagnostics snapshots для operator truth."
    )
    transport_status: str = Field(description="Текущий transport status connector-а.")
    recovery_status: str = Field(description="Текущий recovery status connector-а.")
    subscription_alive: bool = Field(description="Признак живой подписки после reconnect.")
    trade_seen: bool = Field(description="Поступали ли trade ticks в ingest path.")
    orderbook_seen: bool = Field(
        description="Поступал ли честный orderbook snapshot в ingest path."
    )
    best_bid: str | None = Field(description="Лучший bid из текущего orderbook snapshot.")
    best_ask: str | None = Field(description="Лучший ask из текущего orderbook snapshot.")
    last_message_at: str | None = Field(description="Время последнего сообщения connector-а.")
    message_age_ms: int | None = Field(
        description="Возраст последнего transport-level сообщения в миллисекундах."
    )
    transport_rtt_ms: int | None = Field(
        description="RTT transport-level websocket ping/pong в миллисекундах."
    )
    last_ping_sent_at: str | None = Field(
        default=None,
        description="Когда transport-level ping в последний раз был отправлен.",
    )
    last_pong_at: str | None = Field(
        default=None,
        description="Когда transport-level pong в последний раз был успешно получен.",
    )
    application_ping_sent_at: str | None = Field(
        default=None,
        description="Когда Bybit application-level ping был отправлен в последний раз.",
    )
    application_pong_at: str | None = Field(
        default=None,
        description="Когда Bybit application-level pong был получен в последний раз.",
    )
    application_heartbeat_latency_ms: int | None = Field(
        default=None,
        description="Latency ответа Bybit на application-level ping в миллисекундах.",
    )
    last_ping_timeout_at: str | None = Field(
        default=None,
        description="Когда в последний раз был зафиксирован ping timeout.",
    )
    last_ping_timeout_message_age_ms: int | None = Field(
        default=None,
        description="Сколько прошло с последнего входящего сообщения в момент ping timeout.",
    )
    last_ping_timeout_loop_lag_ms: int | None = Field(
        default=None,
        description="Оценка event-loop lag вблизи последнего ping timeout.",
    )
    last_ping_timeout_backfill_status: str | None = Field(
        default=None,
        description="Какой historical backfill status был в момент последнего ping timeout.",
    )
    last_ping_timeout_processed_archives: int | None = Field(
        default=None,
        description="Сколько archive unit-ов было обработано в момент последнего ping timeout.",
    )
    last_ping_timeout_total_archives: int | None = Field(
        default=None,
        description="Сколько archive unit-ов планировалось обработать всего в момент последнего ping timeout.",
    )
    last_ping_timeout_cache_source: str | None = Field(
        default=None,
        description="Какой archive cache source был актуален в момент последнего ping timeout.",
    )
    last_ping_timeout_ignored_due_to_recent_messages: bool = Field(
        default=False,
        description="Был ли последний ping timeout проигнорирован, потому что входящие сообщения продолжали приходить.",
    )
    degraded_reason: str | None = Field(description="Причина деградации connector-а, если есть.")
    last_disconnect_reason: str | None = Field(
        description="Последняя причина disconnect connector-а, если есть."
    )
    retry_count: int | None = Field(
        description="Накопительное количество reconnect/retry попыток за lifecycle текущего runtime instance. Не сбрасывается после успешного reconnect и не описывает само по себе текущую деградацию transport path."
    )
    ready: bool = Field(description="Считает ли feed runtime connector готовым к работе.")
    started: bool = Field(description="Поднят ли feed runtime lifecycle connector-а.")
    lifecycle_state: str | None = Field(
        description="Текущее lifecycle-состояние feed runtime для operator truth."
    )
    reset_required: bool = Field(
        description="Требуется ли reset/recovery boundary перед честным продолжением ingest path."
    )
    derived_trade_count_state: str | None = Field(
        default=None,
        description="Readiness state derived trade_count_24h layer: warming_up, ready, not_reliable_after_gap или live_tail_pending_after_gap.",
    )
    derived_trade_count_ready: bool = Field(
        default=False,
        description="Готов ли derived trade_count_24h слой для честного использования в admission logic.",
    )
    derived_trade_count_observation_started_at: str | None = Field(
        default=None,
        description="Когда началось текущее непрерывное накопление derived trade_count_24h.",
    )
    derived_trade_count_reliable_after: str | None = Field(
        default=None,
        description="Когда derived trade_count_24h станет ready при непрерывном накоплении без gap.",
    )
    derived_trade_count_last_gap_at: str | None = Field(
        default=None,
        description="Когда последний disconnect/gap сделал derived trade_count_24h ненадёжным.",
    )
    derived_trade_count_last_gap_reason: str | None = Field(
        default=None,
        description="Последняя причина gap/reset для derived trade_count_24h слоя.",
    )
    derived_trade_count_backfill_status: str | None = Field(
        default=None,
        description="Статус последней попытки historical backfill для derived trade_count_24h.",
    )
    derived_trade_count_backfill_needed: bool | None = Field(
        default=None,
        description="Нужен ли historical backfill для текущего derived trade_count_24h состояния.",
    )
    derived_trade_count_backfill_processed_archives: int | None = Field(
        default=None,
        description="Сколько архивных unit-ов historical backfill уже обработал.",
    )
    derived_trade_count_backfill_total_archives: int | None = Field(
        default=None,
        description="Сколько архивных unit-ов historical backfill планирует обработать всего.",
    )
    derived_trade_count_backfill_progress_percent: int | None = Field(
        default=None,
        description="Прогресс historical backfill в процентах по архивным unit-ам, а не по readiness фильтра.",
    )
    derived_trade_count_last_backfill_at: str | None = Field(
        default=None,
        description="Когда historical backfill в последний раз применялся или честно завершился ошибкой.",
    )
    derived_trade_count_last_backfill_source: str | None = Field(
        default=None,
        description="Источник historical backfill для derived trade_count_24h слоя.",
    )
    derived_trade_count_last_backfill_reason: str | None = Field(
        default=None,
        description="Последняя причина unavailable/partial historical backfill для derived trade_count_24h.",
    )
    ledger_trade_count_available: bool = Field(
        default=False,
        description="Доступен ли сейчас read-only ledger query path для trade count diagnostics.",
    )
    ledger_trade_count_last_error: str | None = Field(
        default=None,
        description="Последняя ошибка ledger trade count read-path, если query временно недоступен.",
    )
    ledger_trade_count_last_synced_at: str | None = Field(
        default=None,
        description="Когда ledger trade count diagnostics в последний раз успешно обновлялся.",
    )
    trade_count_cutover_readiness_state: str | None = Field(
        default=None,
        description="Aggregate read-only readiness groundwork state для текущего scope/contour.",
    )
    trade_count_cutover_readiness_reason: str | None = Field(
        default=None,
        description="Machine-readable причина aggregate cutover readiness state.",
    )
    trade_count_cutover_compared_symbols: int = Field(
        default=0,
        description="Сколько symbol paths реально вошло в aggregate readiness comparison.",
    )
    trade_count_cutover_ready_symbols: int = Field(
        default=0,
        description="Сколько symbol paths сейчас выглядят ready_for_cutover_evaluation.",
    )
    trade_count_cutover_not_ready_symbols: int = Field(
        default=0,
        description="Сколько symbol paths сейчас помечены как not_ready.",
    )
    trade_count_cutover_blocked_symbols: int = Field(
        default=0,
        description="Сколько symbol paths сейчас блокируют readiness evaluation.",
    )
    trade_count_cutover_evaluation_state: str | None = Field(
        default=None,
        description="Formal read-only evaluation state для manual cutover review discussion.",
    )
    trade_count_cutover_evaluation_reasons: tuple[str, ...] = Field(
        default=(),
        description="Machine-readable formal evaluation reasons поверх readiness/reconciliation surface.",
    )
    trade_count_cutover_evaluation_minimum_compared_symbols: int = Field(
        default=1,
        description="Минимум compared symbols, требуемый formal evaluation policy.",
    )
    trade_count_cutover_manual_review_state: str | None = Field(
        default=None,
        description="Scoped read-only governance/manual-review state для текущего contour/scope.",
    )
    trade_count_cutover_manual_review_reasons: tuple[str, ...] = Field(
        default=(),
        description="Machine-readable governance/manual-review reasons поверх evaluation verdict.",
    )
    trade_count_cutover_manual_review_evaluation_state: str | None = Field(
        default=None,
        description="Какой formal cutover evaluation state лежит под текущим manual-review verdict.",
    )
    trade_count_cutover_manual_review_contour: str | None = Field(
        default=None,
        description="Какой contour сейчас оценивается для manual-review surface.",
    )
    trade_count_cutover_manual_review_scope_mode: str | None = Field(
        default=None,
        description="Какой scope_mode относится к текущему manual-review surface.",
    )
    trade_count_cutover_manual_review_scope_symbol_count: int = Field(
        default=0,
        description="Сколько symbols входит в текущий manual-review scope.",
    )
    trade_count_cutover_manual_review_compared_symbols: int = Field(
        default=0,
        description="Сколько symbols реально вошло в manual-review comparison scope.",
    )
    trade_count_cutover_manual_review_ready_symbols: int = Field(
        default=0,
        description="Сколько symbols поддерживают current manual-review verdict.",
    )
    trade_count_cutover_manual_review_not_ready_symbols: int = Field(
        default=0,
        description="Сколько symbols помечены как not_ready внутри manual-review surface.",
    )
    trade_count_cutover_manual_review_blocked_symbols: int = Field(
        default=0,
        description="Сколько symbols блокируют current manual-review surface.",
    )
    trade_count_cutover_discussion_artifact: CutoverDiscussionArtifactDTO | None = Field(
        default=None,
        description="Operator-facing read-only summary artifact для current cutover discussion.",
    )
    trade_count_cutover_review_record: CutoverReviewRecordDTO | None = Field(
        default=None,
        description="Read-only archived-style cutover review record snapshot для current discussion state.",
    )
    trade_count_cutover_review_package: CutoverReviewPackageDTO | None = Field(
        default=None,
        description="Read-only cutover review package bundle поверх discussion artifact и review record.",
    )
    trade_count_cutover_review_catalog: CutoverReviewCatalogDTO | None = Field(
        default=None,
        description="Read-only cutover review catalog/index поверх current review package bundle.",
    )
    trade_count_cutover_review_snapshot_collection: CutoverReviewSnapshotCollectionDTO | None = Field(
        default=None,
        description="Read-only review snapshot collection/listing поверх current review catalog.",
    )
    trade_count_cutover_review_compact_digest: CutoverReviewCompactDigestDTO | None = Field(
        default=None,
        description="Read-only compact review digest поверх current review snapshot collection.",
    )
    trade_count_cutover_export_report_bundle: CutoverExportReportBundleDTO | None = Field(
        default=None,
        description="Read-only cutover export/report bundle поверх current compact digest.",
    )
    desired_scope_mode: str | None = Field(
        default=None,
        description="Какой scope_mode сохранён как desired policy truth для этого contour-а.",
    )
    desired_trade_count_filter_minimum: int | None = Field(
        default=None,
        description="Какой min_trade_count_24h сохранён как desired policy truth.",
    )
    applied_scope_mode: str | None = Field(
        default=None,
        description="Какой scope_mode сейчас реально применён к running connector-у.",
    )
    applied_trade_count_filter_minimum: int | None = Field(
        default=None,
        description="Какой min_trade_count_24h сейчас реально применён к running connector-у.",
    )
    trade_count_product_truth_state: str | None = Field(
        default=None,
        description="Aggregate user-facing truth state для 24h trade count по текущему scope.",
    )
    trade_count_product_truth_reason: str | None = Field(
        default=None,
        description="Machine-readable причина aggregate trade-count product truth state.",
    )
    trade_count_truth_model: str | None = Field(
        default=None,
        description="Final truth model для trade_count_24h ownership boundary.",
    )
    trade_count_canonical_truth_owner: str | None = Field(
        default=None,
        description="Кто владеет canonical trade truth для product path.",
    )
    trade_count_canonical_truth_source: str | None = Field(
        default=None,
        description="Какой source path является canonical для product trade_count_24h.",
    )
    trade_count_operational_truth_owner: str | None = Field(
        default=None,
        description="Кто владеет connector runtime operational truth.",
    )
    trade_count_operational_truth_source: str | None = Field(
        default=None,
        description="Какой source path используется как operational trade truth.",
    )
    trade_count_connector_canonical_role: str | None = Field(
        default=None,
        description="Роль connector runtime по отношению к canonical trade truth.",
    )
    trade_count_admission_basis: str | None = Field(
        default=None,
        description="На какой truth basis сейчас опирается trade-count admission/filter path.",
    )
    trade_count_admission_truth_owner: str | None = Field(
        default=None,
        description="Кто владеет truth path, на который опирается admission.",
    )
    trade_count_admission_truth_source: str | None = Field(
        default=None,
        description="Какой source path используется admission для trade-count фильтра.",
    )
    policy_apply_status: str | None = Field(
        default=None,
        description="Статус применения saved Bybit policy к runtime: applied, deferred, waiting_for_scope или not_running.",
    )
    policy_apply_reason: str | None = Field(
        default=None,
        description="Почему runtime apply был отложен или ограничен, если это произошло.",
    )
    operator_runtime_state: str | None = Field(
        default=None,
        description="Operator-facing runtime truth: disabled, apply_deferred, connecting, waiting_for_live_tail, warming_up, ready, live, transport_unavailable или no_qualifying_instruments.",
    )
    operator_runtime_reason: str | None = Field(
        default=None,
        description="Краткая operator-facing причина текущего runtime state.",
    )
    operator_confidence_state: str | None = Field(
        default=None,
        description="Operator-facing confidence layer: steady, preserved_after_gap, cold_recovery, streams_recovering, deferred, transport_unavailable, steady_but_empty или disabled.",
    )
    operator_confidence_reason: str | None = Field(
        default=None,
        description="Краткая причина текущего operator confidence state.",
    )
    operator_state_surface: dict[str, object] | None = Field(
        default=None,
        description="Компактный operator-facing surface: runtime и ledger_sync оси.",
    )
    operational_recovery_state: str | None = Field(
        default=None,
        description="Операционное recovery состояние для operator-facing слоя.",
    )
    operational_recovery_reason: str | None = Field(
        default=None,
        description="Причина текущего operational recovery state.",
    )
    canonical_ledger_sync_state: str | None = Field(
        default=None,
        description="Состояние canonical ledger sync для operator-facing слоя.",
    )
    canonical_ledger_sync_reason: str | None = Field(
        default=None,
        description="Причина текущего canonical ledger sync state.",
    )
    post_recovery_materialization_status: str | None = Field(
        default=None,
        description="Статус post-recovery materialization stage.",
    )
    historical_recovery_state: str | None = Field(
        default=None,
        description="Состояние historical recovery coordinator: not_applicable, idle, pending, backfilling, retry_scheduled или live_tail_only.",
    )
    historical_recovery_reason: str | None = Field(
        default=None,
        description="Краткая причина текущего состояния historical recovery coordinator.",
    )
    historical_recovery_retry_pending: bool = Field(
        default=False,
        description="Запланирован ли delayed retry для latest-archive backfill.",
    )
    historical_recovery_backfill_task_active: bool = Field(
        default=False,
        description="Идёт ли сейчас активный historical backfill task.",
    )
    historical_recovery_retry_task_active: bool = Field(
        default=False,
        description="Идёт ли сейчас активный retry task latest closed-day archive.",
    )
    historical_recovery_cutoff_at: str | None = Field(
        default=None,
        description="По какой cutoff boundary сейчас или в последний раз планировался historical recovery plan.",
    )
    archive_cache_enabled: bool = Field(
        default=False,
        description="Включён ли disk-backed archive cache для этого contour-а.",
    )
    archive_cache_memory_hits: int = Field(
        default=0,
        description="Сколько раз payload был взят из in-memory archive cache.",
    )
    archive_cache_disk_hits: int = Field(
        default=0,
        description="Сколько раз payload был взят из disk archive cache.",
    )
    archive_cache_misses: int = Field(
        default=0,
        description="Сколько раз archive пришлось реально запрашивать с внешнего источника.",
    )
    archive_cache_writes: int = Field(
        default=0,
        description="Сколько archive payloads было записано в disk cache.",
    )
    archive_cache_last_hit_source: str | None = Field(
        default=None,
        description="Последний источник archive payload: memory, disk или network.",
    )
    archive_cache_last_url: str | None = Field(
        default=None,
        description="Последний archive URL, который использовался в backfill path.",
    )
    archive_cache_last_cleanup_at: str | None = Field(
        default=None,
        description="Когда disk archive cache в последний раз проходил cleanup.",
    )
    archive_cache_last_pruned_files: int = Field(
        default=0,
        description="Сколько cache files было удалено в последнем cleanup pass.",
    )
    archive_cache_last_network_fetch_ms: int | None = Field(
        default=None,
        description="Сколько занял последний network fetch archive payload в миллисекундах.",
    )
    archive_cache_last_disk_read_ms: int | None = Field(
        default=None,
        description="Сколько заняло последнее чтение archive payload с диска в миллисекундах.",
    )
    archive_cache_last_gzip_decode_ms: int | None = Field(
        default=None,
        description="Сколько заняла последняя стадия gzip decode в миллисекундах.",
    )
    archive_cache_last_csv_parse_ms: int | None = Field(
        default=None,
        description="Сколько заняла последняя стадия csv parse в миллисекундах.",
    )
    archive_cache_last_archive_total_ms: int | None = Field(
        default=None,
        description="Сколько заняла полная обработка последнего archive unit в миллисекундах.",
    )
    archive_cache_last_symbol_total_ms: int | None = Field(
        default=None,
        description="Сколько заняла последняя полная historical обработка одного symbol path.",
    )
    archive_cache_last_symbol: str | None = Field(
        default=None,
        description="Для какого symbol path в последний раз зафиксировано полное historical время.",
    )
    archive_cache_total_network_fetch_ms: int = Field(
        default=0,
        description="Суммарное время network fetch archive payloads в миллисекундах.",
    )
    archive_cache_total_disk_read_ms: int = Field(
        default=0,
        description="Суммарное время чтения archive payloads с диска в миллисекундах.",
    )
    archive_cache_total_gzip_decode_ms: int = Field(
        default=0,
        description="Суммарное время gzip decode по historical archives в миллисекундах.",
    )
    archive_cache_total_csv_parse_ms: int = Field(
        default=0,
        description="Суммарное время csv parse по historical archives в миллисекундах.",
    )
    archive_cache_total_archive_total_ms: int = Field(
        default=0,
        description="Суммарное полное время обработки archive units в миллисекундах.",
    )
    archive_cache_total_symbol_total_ms: int = Field(
        default=0,
        description="Суммарное полное время historical symbol paths в миллисекундах.",
    )
    scope_mode: str = Field(
        description="Режим формирования текущего connector scope. Для Bybit public connectors теперь всегда universe."
    )
    discovery_status: str | None = Field(
        default=None,
        description="Статус universe discovery truth: ready, unavailable или not_applicable.",
    )
    discovery_error: str | None = Field(
        default=None,
        description="Последняя ошибка universe discovery, если source оказался недоступен.",
    )
    total_instruments_discovered: int | None = Field(
        description="Сколько инструментов было найдено на этапе universe discovery."
    )
    instruments_passed_coarse_filter: int | None = Field(
        description="Сколько инструментов прошло coarse prefilter до handoff в connector."
    )
    quote_volume_filter_ready: bool | None = Field(
        default=None,
        description="Готов ли volume-based discovery filter для universe admission.",
    )
    trade_count_filter_ready: bool | None = Field(
        default=None,
        description="Готов ли derived trade_count_24h filter для universe admission.",
    )
    instruments_passed_trade_count_filter: int | None = Field(
        default=None,
        description="Сколько инструментов прошло derived trade_count_24h filter, когда он уже ready.",
    )
    universe_admission_state: str | None = Field(
        default=None,
        description="Состояние universe admission: waiting_for_filter_readiness, waiting_for_live_tail, waiting_for_qualifying_instruments или ready_for_selection.",
    )
    active_subscribed_scope_count: int = Field(
        description="Сколько инструментов реально находится в active subscribed scope."
    )
    live_trade_streams_count: int = Field(
        description="Сколько инструментов сейчас имеют живой trade stream."
    )
    live_orderbook_count: int = Field(
        description="Сколько инструментов сейчас имеют живой orderbook snapshot."
    )
    degraded_or_stale_count: int = Field(
        description="Сколько инструментов сейчас выглядят degraded или stale внутри scope."
    )

    @classmethod
    def from_connector_projection(
        cls,
        connector: object,
    ) -> BybitConnectorDiagnosticsDTO:
        """Build DTO from explicit backend connector projection contract."""
        if not isinstance(connector, dict):
            connector = {}

        return cls._from_connector_payload(connector)

    @classmethod
    def from_runtime_diagnostics(
        cls,
        diagnostics: object,
    ) -> BybitConnectorDiagnosticsDTO:
        """Build DTO from current runtime diagnostics snapshot."""
        connector: dict[str, object] = {}
        if isinstance(diagnostics, dict):
            raw_connector = diagnostics.get("bybit_market_data_connector")
            if isinstance(raw_connector, dict):
                connector = raw_connector

        return cls._from_connector_payload(connector)

    @classmethod
    def _from_connector_payload(
        cls,
        connector: dict[str, object],
    ) -> BybitConnectorDiagnosticsDTO:
        
        raw_symbols = connector.get("symbols")
        symbols = (
            tuple(entry for entry in raw_symbols if isinstance(entry, str))
            if isinstance(raw_symbols, (list, tuple))
            else ()
        )
        symbol = symbols[0] if symbols else None

        raw_symbol_snapshots = connector.get("symbol_snapshots")
        symbol_snapshots: list[BybitConnectorDiagnosticsDTO.SymbolSnapshotDTO] = []
        if isinstance(raw_symbol_snapshots, (list, tuple)):
            for snapshot in raw_symbol_snapshots:
                if not isinstance(snapshot, dict):
                    continue
                raw_symbol = snapshot.get("symbol")
                if not isinstance(raw_symbol, str):
                    continue
                symbol_snapshots.append(
                    cls.SymbolSnapshotDTO(
                        symbol=raw_symbol,
                        trade_seen=bool(snapshot.get("trade_seen", False)),
                        orderbook_seen=bool(snapshot.get("orderbook_seen", False)),
                        trade_ingest_seen=bool(
                            snapshot.get("trade_ingest_seen", snapshot.get("trade_seen", False))
                        ),
                        orderbook_ingest_seen=bool(
                            snapshot.get(
                                "orderbook_ingest_seen",
                                snapshot.get("orderbook_seen", False),
                            )
                        ),
                        best_bid=snapshot.get("best_bid")
                        if isinstance(snapshot.get("best_bid"), str)
                        else None,
                        best_ask=snapshot.get("best_ask")
                        if isinstance(snapshot.get("best_ask"), str)
                        else None,
                        volume_24h_usd=snapshot.get("volume_24h_usd")
                        if isinstance(snapshot.get("volume_24h_usd"), str)
                        else None,
                        derived_trade_count_24h=snapshot.get("derived_trade_count_24h")
                        if isinstance(snapshot.get("derived_trade_count_24h"), int)
                        else None,
                        bucket_trade_count_24h=snapshot.get("bucket_trade_count_24h")
                        if isinstance(snapshot.get("bucket_trade_count_24h"), int)
                        else None,
                        ledger_trade_count_24h=snapshot.get("ledger_trade_count_24h")
                        if isinstance(snapshot.get("ledger_trade_count_24h"), int)
                        else None,
                        trade_count_reconciliation_verdict=snapshot.get(
                            "trade_count_reconciliation_verdict"
                        )
                        if isinstance(snapshot.get("trade_count_reconciliation_verdict"), str)
                        else None,
                        trade_count_reconciliation_reason=snapshot.get(
                            "trade_count_reconciliation_reason"
                        )
                        if isinstance(snapshot.get("trade_count_reconciliation_reason"), str)
                        else None,
                        trade_count_reconciliation_absolute_diff=snapshot.get(
                            "trade_count_reconciliation_absolute_diff"
                        )
                        if isinstance(snapshot.get("trade_count_reconciliation_absolute_diff"), int)
                        else None,
                        trade_count_reconciliation_tolerance=snapshot.get(
                            "trade_count_reconciliation_tolerance"
                        )
                        if isinstance(snapshot.get("trade_count_reconciliation_tolerance"), int)
                        else None,
                        trade_count_cutover_readiness_state=snapshot.get(
                            "trade_count_cutover_readiness_state"
                        )
                        if isinstance(snapshot.get("trade_count_cutover_readiness_state"), str)
                        else None,
                        trade_count_cutover_readiness_reason=snapshot.get(
                            "trade_count_cutover_readiness_reason"
                        )
                        if isinstance(snapshot.get("trade_count_cutover_readiness_reason"), str)
                        else None,
                        observed_trade_count_since_reset=int(
                            snapshot.get("observed_trade_count_since_reset", 0)
                        ),
                        product_trade_count_24h=snapshot.get("product_trade_count_24h")
                        if isinstance(snapshot.get("product_trade_count_24h"), int)
                        else None,
                        product_trade_count_state=snapshot.get("product_trade_count_state")
                        if isinstance(snapshot.get("product_trade_count_state"), str)
                        else None,
                        product_trade_count_reason=snapshot.get("product_trade_count_reason")
                        if isinstance(snapshot.get("product_trade_count_reason"), str)
                        else None,
                        product_trade_count_truth_owner=snapshot.get(
                            "product_trade_count_truth_owner"
                        )
                        if isinstance(snapshot.get("product_trade_count_truth_owner"), str)
                        else None,
                        product_trade_count_truth_source=snapshot.get(
                            "product_trade_count_truth_source"
                        )
                        if isinstance(snapshot.get("product_trade_count_truth_source"), str)
                        else None,
                    )
                )

        return cls(
            enabled=bool(connector.get("enabled", False)),
            symbol=symbol,
            symbols=symbols,
            symbol_snapshots=tuple(symbol_snapshots),
            transport_status=str(connector.get("transport_status", "unavailable")),
            recovery_status=str(connector.get("recovery_status", "idle")),
            subscription_alive=bool(connector.get("subscription_alive", False)),
            trade_seen=bool(connector.get("trade_seen", False)),
            orderbook_seen=bool(connector.get("orderbook_seen", False)),
            best_bid=connector.get("best_bid")
            if isinstance(connector.get("best_bid"), str)
            else None,
            best_ask=connector.get("best_ask")
            if isinstance(connector.get("best_ask"), str)
            else None,
            last_message_at=connector.get("last_message_at")
            if isinstance(connector.get("last_message_at"), str)
            else None,
            message_age_ms=connector.get("message_age_ms")
            if isinstance(connector.get("message_age_ms"), int)
            else None,
            transport_rtt_ms=connector.get("transport_rtt_ms")
            if isinstance(connector.get("transport_rtt_ms"), int)
            else None,
            last_ping_sent_at=connector.get("last_ping_sent_at")
            if isinstance(connector.get("last_ping_sent_at"), str)
            else None,
            last_pong_at=connector.get("last_pong_at")
            if isinstance(connector.get("last_pong_at"), str)
            else None,
            application_ping_sent_at=connector.get("application_ping_sent_at")
            if isinstance(connector.get("application_ping_sent_at"), str)
            else None,
            application_pong_at=connector.get("application_pong_at")
            if isinstance(connector.get("application_pong_at"), str)
            else None,
            application_heartbeat_latency_ms=connector.get("application_heartbeat_latency_ms")
            if isinstance(connector.get("application_heartbeat_latency_ms"), int)
            else None,
            last_ping_timeout_at=connector.get("last_ping_timeout_at")
            if isinstance(connector.get("last_ping_timeout_at"), str)
            else None,
            last_ping_timeout_message_age_ms=connector.get("last_ping_timeout_message_age_ms")
            if isinstance(connector.get("last_ping_timeout_message_age_ms"), int)
            else None,
            last_ping_timeout_loop_lag_ms=connector.get("last_ping_timeout_loop_lag_ms")
            if isinstance(connector.get("last_ping_timeout_loop_lag_ms"), int)
            else None,
            last_ping_timeout_backfill_status=connector.get("last_ping_timeout_backfill_status")
            if isinstance(connector.get("last_ping_timeout_backfill_status"), str)
            else None,
            last_ping_timeout_processed_archives=connector.get(
                "last_ping_timeout_processed_archives"
            )
            if isinstance(connector.get("last_ping_timeout_processed_archives"), int)
            else None,
            last_ping_timeout_total_archives=connector.get("last_ping_timeout_total_archives")
            if isinstance(connector.get("last_ping_timeout_total_archives"), int)
            else None,
            last_ping_timeout_cache_source=connector.get("last_ping_timeout_cache_source")
            if isinstance(connector.get("last_ping_timeout_cache_source"), str)
            else None,
            last_ping_timeout_ignored_due_to_recent_messages=bool(
                connector.get("last_ping_timeout_ignored_due_to_recent_messages", False)
            ),
            degraded_reason=connector.get("degraded_reason")
            if isinstance(connector.get("degraded_reason"), str)
            else None,
            last_disconnect_reason=connector.get("last_disconnect_reason")
            if isinstance(connector.get("last_disconnect_reason"), str)
            else None,
            retry_count=connector.get("retry_count")
            if isinstance(connector.get("retry_count"), int)
            else None,
            ready=bool(connector.get("ready", False)),
            started=bool(connector.get("started", False)),
            lifecycle_state=connector.get("lifecycle_state")
            if isinstance(connector.get("lifecycle_state"), str)
            else None,
            reset_required=bool(connector.get("reset_required", False)),
            derived_trade_count_state=connector.get("derived_trade_count_state")
            if isinstance(connector.get("derived_trade_count_state"), str)
            else None,
            derived_trade_count_ready=bool(connector.get("derived_trade_count_ready", False)),
            derived_trade_count_observation_started_at=connector.get(
                "derived_trade_count_observation_started_at"
            )
            if isinstance(connector.get("derived_trade_count_observation_started_at"), str)
            else None,
            derived_trade_count_reliable_after=connector.get("derived_trade_count_reliable_after")
            if isinstance(connector.get("derived_trade_count_reliable_after"), str)
            else None,
            derived_trade_count_last_gap_at=connector.get("derived_trade_count_last_gap_at")
            if isinstance(connector.get("derived_trade_count_last_gap_at"), str)
            else None,
            derived_trade_count_last_gap_reason=connector.get("derived_trade_count_last_gap_reason")
            if isinstance(connector.get("derived_trade_count_last_gap_reason"), str)
            else None,
            derived_trade_count_backfill_status=connector.get("derived_trade_count_backfill_status")
            if isinstance(connector.get("derived_trade_count_backfill_status"), str)
            else None,
            derived_trade_count_backfill_needed=connector.get("derived_trade_count_backfill_needed")
            if isinstance(connector.get("derived_trade_count_backfill_needed"), bool)
            else None,
            derived_trade_count_backfill_processed_archives=connector.get(
                "derived_trade_count_backfill_processed_archives"
            )
            if isinstance(connector.get("derived_trade_count_backfill_processed_archives"), int)
            else None,
            derived_trade_count_backfill_total_archives=connector.get(
                "derived_trade_count_backfill_total_archives"
            )
            if isinstance(connector.get("derived_trade_count_backfill_total_archives"), int)
            else None,
            derived_trade_count_backfill_progress_percent=connector.get(
                "derived_trade_count_backfill_progress_percent"
            )
            if isinstance(connector.get("derived_trade_count_backfill_progress_percent"), int)
            else None,
            derived_trade_count_last_backfill_at=connector.get(
                "derived_trade_count_last_backfill_at"
            )
            if isinstance(connector.get("derived_trade_count_last_backfill_at"), str)
            else None,
            derived_trade_count_last_backfill_source=connector.get(
                "derived_trade_count_last_backfill_source"
            )
            if isinstance(connector.get("derived_trade_count_last_backfill_source"), str)
            else None,
            derived_trade_count_last_backfill_reason=connector.get(
                "derived_trade_count_last_backfill_reason"
            )
            if isinstance(connector.get("derived_trade_count_last_backfill_reason"), str)
            else None,
            ledger_trade_count_available=bool(connector.get("ledger_trade_count_available", False)),
            ledger_trade_count_last_error=connector.get("ledger_trade_count_last_error")
            if isinstance(connector.get("ledger_trade_count_last_error"), str)
            else None,
            ledger_trade_count_last_synced_at=connector.get("ledger_trade_count_last_synced_at")
            if isinstance(connector.get("ledger_trade_count_last_synced_at"), str)
            else None,
            trade_count_cutover_readiness_state=connector.get("trade_count_cutover_readiness_state")
            if isinstance(connector.get("trade_count_cutover_readiness_state"), str)
            else None,
            trade_count_cutover_readiness_reason=connector.get("trade_count_cutover_readiness_reason")
            if isinstance(connector.get("trade_count_cutover_readiness_reason"), str)
            else None,
            trade_count_cutover_compared_symbols=connector.get("trade_count_cutover_compared_symbols")
            if isinstance(connector.get("trade_count_cutover_compared_symbols"), int)
            else 0,
            trade_count_cutover_ready_symbols=connector.get("trade_count_cutover_ready_symbols")
            if isinstance(connector.get("trade_count_cutover_ready_symbols"), int)
            else 0,
            trade_count_cutover_not_ready_symbols=connector.get("trade_count_cutover_not_ready_symbols")
            if isinstance(connector.get("trade_count_cutover_not_ready_symbols"), int)
            else 0,
            trade_count_cutover_blocked_symbols=connector.get("trade_count_cutover_blocked_symbols")
            if isinstance(connector.get("trade_count_cutover_blocked_symbols"), int)
            else 0,
            trade_count_cutover_evaluation_state=connector.get("trade_count_cutover_evaluation_state")
            if isinstance(connector.get("trade_count_cutover_evaluation_state"), str)
            else None,
            trade_count_cutover_evaluation_reasons=tuple(
                str(reason)
                for reason in connector.get("trade_count_cutover_evaluation_reasons", ())
                if isinstance(reason, str)
            ),
            trade_count_cutover_evaluation_minimum_compared_symbols=connector.get(
                "trade_count_cutover_evaluation_minimum_compared_symbols"
            )
            if isinstance(
                connector.get("trade_count_cutover_evaluation_minimum_compared_symbols"), int
            )
            else 1,
            trade_count_cutover_manual_review_state=connector.get(
                "trade_count_cutover_manual_review_state"
            )
            if isinstance(connector.get("trade_count_cutover_manual_review_state"), str)
            else None,
            trade_count_cutover_manual_review_reasons=tuple(
                str(reason)
                for reason in connector.get("trade_count_cutover_manual_review_reasons", ())
                if isinstance(reason, str)
            ),
            trade_count_cutover_manual_review_evaluation_state=connector.get(
                "trade_count_cutover_manual_review_evaluation_state"
            )
            if isinstance(connector.get("trade_count_cutover_manual_review_evaluation_state"), str)
            else None,
            trade_count_cutover_manual_review_contour=connector.get(
                "trade_count_cutover_manual_review_contour"
            )
            if isinstance(connector.get("trade_count_cutover_manual_review_contour"), str)
            else None,
            trade_count_cutover_manual_review_scope_mode=connector.get(
                "trade_count_cutover_manual_review_scope_mode"
            )
            if isinstance(connector.get("trade_count_cutover_manual_review_scope_mode"), str)
            else None,
            trade_count_cutover_manual_review_scope_symbol_count=connector.get(
                "trade_count_cutover_manual_review_scope_symbol_count"
            )
            if isinstance(connector.get("trade_count_cutover_manual_review_scope_symbol_count"), int)
            else 0,
            trade_count_cutover_manual_review_compared_symbols=connector.get(
                "trade_count_cutover_manual_review_compared_symbols"
            )
            if isinstance(connector.get("trade_count_cutover_manual_review_compared_symbols"), int)
            else 0,
            trade_count_cutover_manual_review_ready_symbols=connector.get(
                "trade_count_cutover_manual_review_ready_symbols"
            )
            if isinstance(connector.get("trade_count_cutover_manual_review_ready_symbols"), int)
            else 0,
            trade_count_cutover_manual_review_not_ready_symbols=connector.get(
                "trade_count_cutover_manual_review_not_ready_symbols"
            )
            if isinstance(
                connector.get("trade_count_cutover_manual_review_not_ready_symbols"), int
            )
            else 0,
            trade_count_cutover_manual_review_blocked_symbols=connector.get(
                "trade_count_cutover_manual_review_blocked_symbols"
            )
            if isinstance(connector.get("trade_count_cutover_manual_review_blocked_symbols"), int)
            else 0,
            trade_count_cutover_discussion_artifact=(
                cls.CutoverDiscussionArtifactDTO(
                    discussion_state=str(artifact.get("discussion_state", "discussion_not_ready")),
                    headline=str(artifact.get("headline", "")),
                    contour=str(artifact.get("contour", "unknown")),
                    scope_mode=str(artifact.get("scope_mode", "universe")),
                    scope_symbol_count=int(artifact.get("scope_symbol_count", 0)),
                    reconciliation_summary=tuple(
                        cls.CutoverDiscussionVerdictCountDTO(
                            name=str(item.get("name", "")),
                            count=int(item.get("count", 0)),
                        )
                        for item in artifact.get("reconciliation_summary", ())
                        if isinstance(item, dict)
                    ),
                    cutover_readiness_state=str(artifact.get("cutover_readiness_state", "")),
                    cutover_readiness_reason=str(artifact.get("cutover_readiness_reason", "")),
                    cutover_evaluation_state=str(artifact.get("cutover_evaluation_state", "")),
                    cutover_evaluation_reasons=tuple(
                        str(reason)
                        for reason in artifact.get("cutover_evaluation_reasons", ())
                        if isinstance(reason, str)
                    ),
                    manual_review_state=str(artifact.get("manual_review_state", "")),
                    manual_review_reasons=tuple(
                        str(reason)
                        for reason in artifact.get("manual_review_reasons", ())
                        if isinstance(reason, str)
                    ),
                    compared_symbols=int(artifact.get("compared_symbols", 0)),
                    ready_symbols=int(artifact.get("ready_symbols", 0)),
                    not_ready_symbols=int(artifact.get("not_ready_symbols", 0)),
                    blocked_symbols=int(artifact.get("blocked_symbols", 0)),
                    symbol_exceptions=tuple(
                        cls.CutoverDiscussionExceptionDTO(
                            symbol=str(item.get("symbol", "")),
                            reconciliation_verdict=(
                                str(item["reconciliation_verdict"])
                                if isinstance(item.get("reconciliation_verdict"), str)
                                else None
                            ),
                            reconciliation_reason=(
                                str(item["reconciliation_reason"])
                                if isinstance(item.get("reconciliation_reason"), str)
                                else None
                            ),
                            cutover_readiness_state=(
                                str(item["cutover_readiness_state"])
                                if isinstance(item.get("cutover_readiness_state"), str)
                                else None
                            ),
                            cutover_readiness_reason=(
                                str(item["cutover_readiness_reason"])
                                if isinstance(item.get("cutover_readiness_reason"), str)
                                else None
                            ),
                        )
                        for item in artifact.get("symbol_exceptions", ())
                        if isinstance(item, dict)
                    ),
                )
                if isinstance(connector.get("trade_count_cutover_discussion_artifact"), dict)
                and isinstance(
                    (artifact := connector.get("trade_count_cutover_discussion_artifact")), dict
                )
                else None
            ),
            trade_count_cutover_review_record=(
                cls.CutoverReviewRecordDTO(
                    captured_at=str(record.get("captured_at", "")),
                    contour=str(record.get("contour", "unknown")),
                    scope_mode=str(record.get("scope_mode", "universe")),
                    scope_symbol_count=int(record.get("scope_symbol_count", 0)),
                    discussion_state=str(record.get("discussion_state", "")),
                    manual_review_state=str(record.get("manual_review_state", "")),
                    cutover_evaluation_state=str(record.get("cutover_evaluation_state", "")),
                    cutover_readiness_state=str(record.get("cutover_readiness_state", "")),
                    compared_symbols=int(record.get("compared_symbols", 0)),
                    ready_symbols=int(record.get("ready_symbols", 0)),
                    not_ready_symbols=int(record.get("not_ready_symbols", 0)),
                    blocked_symbols=int(record.get("blocked_symbols", 0)),
                    headline=str(record.get("headline", "")),
                    reasons_summary=tuple(
                        str(reason)
                        for reason in record.get("reasons_summary", ())
                        if isinstance(reason, str)
                    ),
                    symbol_exceptions=tuple(
                        cls.CutoverDiscussionExceptionDTO(
                            symbol=str(item.get("symbol", "")),
                            reconciliation_verdict=(
                                str(item["reconciliation_verdict"])
                                if isinstance(item.get("reconciliation_verdict"), str)
                                else None
                            ),
                            reconciliation_reason=(
                                str(item["reconciliation_reason"])
                                if isinstance(item.get("reconciliation_reason"), str)
                                else None
                            ),
                            cutover_readiness_state=(
                                str(item["cutover_readiness_state"])
                                if isinstance(item.get("cutover_readiness_state"), str)
                                else None
                            ),
                            cutover_readiness_reason=(
                                str(item["cutover_readiness_reason"])
                                if isinstance(item.get("cutover_readiness_reason"), str)
                                else None
                            ),
                        )
                        for item in record.get("symbol_exceptions", ())
                        if isinstance(item, dict)
                    ),
                )
                if isinstance(connector.get("trade_count_cutover_review_record"), dict)
                and isinstance((record := connector.get("trade_count_cutover_review_record")), dict)
                else None
            ),
            trade_count_cutover_review_package=(
                cls.CutoverReviewPackageDTO(
                    contour=str(package.get("contour", "unknown")),
                    scope_mode=str(package.get("scope_mode", "universe")),
                    scope_symbol_count=int(package.get("scope_symbol_count", 0)),
                    discussion_state=str(package.get("discussion_state", "")),
                    manual_review_state=str(package.get("manual_review_state", "")),
                    cutover_evaluation_state=str(package.get("cutover_evaluation_state", "")),
                    cutover_readiness_state=str(package.get("cutover_readiness_state", "")),
                    compared_symbols=int(package.get("compared_symbols", 0)),
                    ready_symbols=int(package.get("ready_symbols", 0)),
                    not_ready_symbols=int(package.get("not_ready_symbols", 0)),
                    blocked_symbols=int(package.get("blocked_symbols", 0)),
                    headline=str(package.get("headline", "")),
                    reasons_summary=tuple(
                        str(reason)
                        for reason in package.get("reasons_summary", ())
                        if isinstance(reason, str)
                    ),
                    review_record=cls.CutoverReviewRecordDTO(
                        captured_at=str(package_record.get("captured_at", "")),
                        contour=str(package_record.get("contour", "unknown")),
                        scope_mode=str(package_record.get("scope_mode", "universe")),
                        scope_symbol_count=int(package_record.get("scope_symbol_count", 0)),
                        discussion_state=str(package_record.get("discussion_state", "")),
                        manual_review_state=str(package_record.get("manual_review_state", "")),
                        cutover_evaluation_state=str(
                            package_record.get("cutover_evaluation_state", "")
                        ),
                        cutover_readiness_state=str(
                            package_record.get("cutover_readiness_state", "")
                        ),
                        compared_symbols=int(package_record.get("compared_symbols", 0)),
                        ready_symbols=int(package_record.get("ready_symbols", 0)),
                        not_ready_symbols=int(package_record.get("not_ready_symbols", 0)),
                        blocked_symbols=int(package_record.get("blocked_symbols", 0)),
                        headline=str(package_record.get("headline", "")),
                        reasons_summary=tuple(
                            str(reason)
                            for reason in package_record.get("reasons_summary", ())
                            if isinstance(reason, str)
                        ),
                        symbol_exceptions=tuple(
                            cls.CutoverDiscussionExceptionDTO(
                                symbol=str(item.get("symbol", "")),
                                reconciliation_verdict=(
                                    str(item["reconciliation_verdict"])
                                    if isinstance(item.get("reconciliation_verdict"), str)
                                    else None
                                ),
                                reconciliation_reason=(
                                    str(item["reconciliation_reason"])
                                    if isinstance(item.get("reconciliation_reason"), str)
                                    else None
                                ),
                                cutover_readiness_state=(
                                    str(item["cutover_readiness_state"])
                                    if isinstance(item.get("cutover_readiness_state"), str)
                                    else None
                                ),
                                cutover_readiness_reason=(
                                    str(item["cutover_readiness_reason"])
                                    if isinstance(item.get("cutover_readiness_reason"), str)
                                    else None
                                ),
                            )
                            for item in package_record.get("symbol_exceptions", ())
                            if isinstance(item, dict)
                        ),
                    ),
                    symbol_exceptions=tuple(
                        cls.CutoverDiscussionExceptionDTO(
                            symbol=str(item.get("symbol", "")),
                            reconciliation_verdict=(
                                str(item["reconciliation_verdict"])
                                if isinstance(item.get("reconciliation_verdict"), str)
                                else None
                            ),
                            reconciliation_reason=(
                                str(item["reconciliation_reason"])
                                if isinstance(item.get("reconciliation_reason"), str)
                                else None
                            ),
                            cutover_readiness_state=(
                                str(item["cutover_readiness_state"])
                                if isinstance(item.get("cutover_readiness_state"), str)
                                else None
                            ),
                            cutover_readiness_reason=(
                                str(item["cutover_readiness_reason"])
                                if isinstance(item.get("cutover_readiness_reason"), str)
                                else None
                            ),
                        )
                        for item in package.get("symbol_exceptions", ())
                        if isinstance(item, dict)
                    ),
                )
                if isinstance(connector.get("trade_count_cutover_review_package"), dict)
                and isinstance((package := connector.get("trade_count_cutover_review_package")), dict)
                and isinstance((package_record := package.get("review_record")), dict)
                else None
            ),
            trade_count_cutover_review_catalog=(
                cls.CutoverReviewCatalogDTO(
                    contour=str(catalog.get("contour", "unknown")),
                    scope_mode=str(catalog.get("scope_mode", "universe")),
                    headline=str(catalog.get("headline", "")),
                    discussion_state=str(catalog.get("discussion_state", "")),
                    manual_review_state=str(catalog.get("manual_review_state", "")),
                    cutover_evaluation_state=str(catalog.get("cutover_evaluation_state", "")),
                    cutover_readiness_state=str(catalog.get("cutover_readiness_state", "")),
                    compared_symbols=int(catalog.get("compared_symbols", 0)),
                    ready_symbols=int(catalog.get("ready_symbols", 0)),
                    not_ready_symbols=int(catalog.get("not_ready_symbols", 0)),
                    blocked_symbols=int(catalog.get("blocked_symbols", 0)),
                    reasons_summary=tuple(
                        str(reason)
                        for reason in catalog.get("reasons_summary", ())
                        if isinstance(reason, str)
                    ),
                    current_review_package=cls.CutoverReviewPackageDTO(
                        contour=str(catalog_package.get("contour", "unknown")),
                        scope_mode=str(catalog_package.get("scope_mode", "universe")),
                        scope_symbol_count=int(catalog_package.get("scope_symbol_count", 0)),
                        discussion_state=str(catalog_package.get("discussion_state", "")),
                        manual_review_state=str(catalog_package.get("manual_review_state", "")),
                        cutover_evaluation_state=str(
                            catalog_package.get("cutover_evaluation_state", "")
                        ),
                        cutover_readiness_state=str(
                            catalog_package.get("cutover_readiness_state", "")
                        ),
                        compared_symbols=int(catalog_package.get("compared_symbols", 0)),
                        ready_symbols=int(catalog_package.get("ready_symbols", 0)),
                        not_ready_symbols=int(catalog_package.get("not_ready_symbols", 0)),
                        blocked_symbols=int(catalog_package.get("blocked_symbols", 0)),
                        headline=str(catalog_package.get("headline", "")),
                        reasons_summary=tuple(
                            str(reason)
                            for reason in catalog_package.get("reasons_summary", ())
                            if isinstance(reason, str)
                        ),
                        review_record=cls.CutoverReviewRecordDTO(
                            captured_at=str(catalog_record.get("captured_at", "")),
                            contour=str(catalog_record.get("contour", "unknown")),
                            scope_mode=str(catalog_record.get("scope_mode", "universe")),
                            scope_symbol_count=int(catalog_record.get("scope_symbol_count", 0)),
                            discussion_state=str(catalog_record.get("discussion_state", "")),
                            manual_review_state=str(catalog_record.get("manual_review_state", "")),
                            cutover_evaluation_state=str(
                                catalog_record.get("cutover_evaluation_state", "")
                            ),
                            cutover_readiness_state=str(
                                catalog_record.get("cutover_readiness_state", "")
                            ),
                            compared_symbols=int(catalog_record.get("compared_symbols", 0)),
                            ready_symbols=int(catalog_record.get("ready_symbols", 0)),
                            not_ready_symbols=int(catalog_record.get("not_ready_symbols", 0)),
                            blocked_symbols=int(catalog_record.get("blocked_symbols", 0)),
                            headline=str(catalog_record.get("headline", "")),
                            reasons_summary=tuple(
                                str(reason)
                                for reason in catalog_record.get("reasons_summary", ())
                                if isinstance(reason, str)
                            ),
                            symbol_exceptions=tuple(
                                cls.CutoverDiscussionExceptionDTO(
                                    symbol=str(item.get("symbol", "")),
                                    reconciliation_verdict=(
                                        str(item["reconciliation_verdict"])
                                        if isinstance(item.get("reconciliation_verdict"), str)
                                        else None
                                    ),
                                    reconciliation_reason=(
                                        str(item["reconciliation_reason"])
                                        if isinstance(item.get("reconciliation_reason"), str)
                                        else None
                                    ),
                                    cutover_readiness_state=(
                                        str(item["cutover_readiness_state"])
                                        if isinstance(item.get("cutover_readiness_state"), str)
                                        else None
                                    ),
                                    cutover_readiness_reason=(
                                        str(item["cutover_readiness_reason"])
                                        if isinstance(item.get("cutover_readiness_reason"), str)
                                        else None
                                    ),
                                )
                                for item in catalog_record.get("symbol_exceptions", ())
                                if isinstance(item, dict)
                            ),
                        ),
                        symbol_exceptions=tuple(
                            cls.CutoverDiscussionExceptionDTO(
                                symbol=str(item.get("symbol", "")),
                                reconciliation_verdict=(
                                    str(item["reconciliation_verdict"])
                                    if isinstance(item.get("reconciliation_verdict"), str)
                                    else None
                                ),
                                reconciliation_reason=(
                                    str(item["reconciliation_reason"])
                                    if isinstance(item.get("reconciliation_reason"), str)
                                    else None
                                ),
                                cutover_readiness_state=(
                                    str(item["cutover_readiness_state"])
                                    if isinstance(item.get("cutover_readiness_state"), str)
                                    else None
                                ),
                                cutover_readiness_reason=(
                                    str(item["cutover_readiness_reason"])
                                    if isinstance(item.get("cutover_readiness_reason"), str)
                                    else None
                                ),
                            )
                            for item in catalog_package.get("symbol_exceptions", ())
                            if isinstance(item, dict)
                        ),
                    ),
                )
                if isinstance(connector.get("trade_count_cutover_review_catalog"), dict)
                and isinstance((catalog := connector.get("trade_count_cutover_review_catalog")), dict)
                and isinstance((catalog_package := catalog.get("current_review_package")), dict)
                and isinstance((catalog_record := catalog_package.get("review_record")), dict)
                else None
            ),
            trade_count_cutover_review_snapshot_collection=(
                cls.CutoverReviewSnapshotCollectionDTO(
                    contour=str(collection.get("contour", "unknown")),
                    scope_mode=str(collection.get("scope_mode", "universe")),
                    headline=str(collection.get("headline", "")),
                    discussion_state=str(collection.get("discussion_state", "")),
                    manual_review_state=str(collection.get("manual_review_state", "")),
                    cutover_evaluation_state=str(
                        collection.get("cutover_evaluation_state", "")
                    ),
                    cutover_readiness_state=str(
                        collection.get("cutover_readiness_state", "")
                    ),
                    compared_symbols=int(collection.get("compared_symbols", 0)),
                    ready_symbols=int(collection.get("ready_symbols", 0)),
                    not_ready_symbols=int(collection.get("not_ready_symbols", 0)),
                    blocked_symbols=int(collection.get("blocked_symbols", 0)),
                    reasons_summary=tuple(
                        str(reason)
                        for reason in collection.get("reasons_summary", ())
                        if isinstance(reason, str)
                    ),
                    current_review_package_headline=str(
                        collection.get("current_review_package_headline", "")
                    ),
                    current_review_package_discussion_state=str(
                        collection.get("current_review_package_discussion_state", "")
                    ),
                    current_review_catalog=cls.CutoverReviewCatalogDTO(
                        contour=str(collection_catalog.get("contour", "unknown")),
                        scope_mode=str(collection_catalog.get("scope_mode", "universe")),
                        headline=str(collection_catalog.get("headline", "")),
                        discussion_state=str(collection_catalog.get("discussion_state", "")),
                        manual_review_state=str(
                            collection_catalog.get("manual_review_state", "")
                        ),
                        cutover_evaluation_state=str(
                            collection_catalog.get("cutover_evaluation_state", "")
                        ),
                        cutover_readiness_state=str(
                            collection_catalog.get("cutover_readiness_state", "")
                        ),
                        compared_symbols=int(collection_catalog.get("compared_symbols", 0)),
                        ready_symbols=int(collection_catalog.get("ready_symbols", 0)),
                        not_ready_symbols=int(collection_catalog.get("not_ready_symbols", 0)),
                        blocked_symbols=int(collection_catalog.get("blocked_symbols", 0)),
                        reasons_summary=tuple(
                            str(reason)
                            for reason in collection_catalog.get("reasons_summary", ())
                            if isinstance(reason, str)
                        ),
                        current_review_package=cls.CutoverReviewPackageDTO(
                            contour=str(collection_package.get("contour", "unknown")),
                            scope_mode=str(collection_package.get("scope_mode", "universe")),
                            scope_symbol_count=int(
                                collection_package.get("scope_symbol_count", 0)
                            ),
                            discussion_state=str(
                                collection_package.get("discussion_state", "")
                            ),
                            manual_review_state=str(
                                collection_package.get("manual_review_state", "")
                            ),
                            cutover_evaluation_state=str(
                                collection_package.get("cutover_evaluation_state", "")
                            ),
                            cutover_readiness_state=str(
                                collection_package.get("cutover_readiness_state", "")
                            ),
                            compared_symbols=int(collection_package.get("compared_symbols", 0)),
                            ready_symbols=int(collection_package.get("ready_symbols", 0)),
                            not_ready_symbols=int(
                                collection_package.get("not_ready_symbols", 0)
                            ),
                            blocked_symbols=int(collection_package.get("blocked_symbols", 0)),
                            headline=str(collection_package.get("headline", "")),
                            reasons_summary=tuple(
                                str(reason)
                                for reason in collection_package.get("reasons_summary", ())
                                if isinstance(reason, str)
                            ),
                            review_record=cls.CutoverReviewRecordDTO(
                                captured_at=str(collection_record.get("captured_at", "")),
                                contour=str(collection_record.get("contour", "unknown")),
                                scope_mode=str(
                                    collection_record.get("scope_mode", "universe")
                                ),
                                scope_symbol_count=int(
                                    collection_record.get("scope_symbol_count", 0)
                                ),
                                discussion_state=str(
                                    collection_record.get("discussion_state", "")
                                ),
                                manual_review_state=str(
                                    collection_record.get("manual_review_state", "")
                                ),
                                cutover_evaluation_state=str(
                                    collection_record.get("cutover_evaluation_state", "")
                                ),
                                cutover_readiness_state=str(
                                    collection_record.get("cutover_readiness_state", "")
                                ),
                                compared_symbols=int(
                                    collection_record.get("compared_symbols", 0)
                                ),
                                ready_symbols=int(collection_record.get("ready_symbols", 0)),
                                not_ready_symbols=int(
                                    collection_record.get("not_ready_symbols", 0)
                                ),
                                blocked_symbols=int(
                                    collection_record.get("blocked_symbols", 0)
                                ),
                                headline=str(collection_record.get("headline", "")),
                                reasons_summary=tuple(
                                    str(reason)
                                    for reason in collection_record.get(
                                        "reasons_summary",
                                        (),
                                    )
                                    if isinstance(reason, str)
                                ),
                                symbol_exceptions=tuple(
                                    cls.CutoverDiscussionExceptionDTO(
                                        symbol=str(item.get("symbol", "")),
                                        reconciliation_verdict=(
                                            str(item["reconciliation_verdict"])
                                            if isinstance(
                                                item.get("reconciliation_verdict"),
                                                str,
                                            )
                                            else None
                                        ),
                                        reconciliation_reason=(
                                            str(item["reconciliation_reason"])
                                            if isinstance(item.get("reconciliation_reason"), str)
                                            else None
                                        ),
                                        cutover_readiness_state=(
                                            str(item["cutover_readiness_state"])
                                            if isinstance(
                                                item.get("cutover_readiness_state"),
                                                str,
                                            )
                                            else None
                                        ),
                                        cutover_readiness_reason=(
                                            str(item["cutover_readiness_reason"])
                                            if isinstance(
                                                item.get("cutover_readiness_reason"),
                                                str,
                                            )
                                            else None
                                        ),
                                    )
                                    for item in collection_record.get(
                                        "symbol_exceptions",
                                        (),
                                    )
                                    if isinstance(item, dict)
                                ),
                            ),
                            symbol_exceptions=tuple(
                                cls.CutoverDiscussionExceptionDTO(
                                    symbol=str(item.get("symbol", "")),
                                    reconciliation_verdict=(
                                        str(item["reconciliation_verdict"])
                                        if isinstance(item.get("reconciliation_verdict"), str)
                                        else None
                                    ),
                                    reconciliation_reason=(
                                        str(item["reconciliation_reason"])
                                        if isinstance(item.get("reconciliation_reason"), str)
                                        else None
                                    ),
                                    cutover_readiness_state=(
                                        str(item["cutover_readiness_state"])
                                        if isinstance(item.get("cutover_readiness_state"), str)
                                        else None
                                    ),
                                    cutover_readiness_reason=(
                                        str(item["cutover_readiness_reason"])
                                        if isinstance(item.get("cutover_readiness_reason"), str)
                                        else None
                                    ),
                                )
                                for item in collection_package.get("symbol_exceptions", ())
                                if isinstance(item, dict)
                            ),
                        ),
                    ),
                )
                if isinstance(connector.get("trade_count_cutover_review_snapshot_collection"), dict)
                and isinstance(
                    (
                        collection := connector.get(
                            "trade_count_cutover_review_snapshot_collection"
                        )
                    ),
                    dict,
                )
                and isinstance((collection_catalog := collection.get("current_review_catalog")), dict)
                and isinstance(
                    (collection_package := collection_catalog.get("current_review_package")),
                    dict,
                )
                and isinstance((collection_record := collection_package.get("review_record")), dict)
                else None
            ),
            trade_count_cutover_review_compact_digest=(
                cls.CutoverReviewCompactDigestDTO(
                    contour=str(digest.get("contour", "unknown")),
                    scope_mode=str(digest.get("scope_mode", "universe")),
                    headline=str(digest.get("headline", "")),
                    discussion_state=str(digest.get("discussion_state", "")),
                    manual_review_state=str(digest.get("manual_review_state", "")),
                    cutover_evaluation_state=str(digest.get("cutover_evaluation_state", "")),
                    cutover_readiness_state=str(digest.get("cutover_readiness_state", "")),
                    compared_symbols=int(digest.get("compared_symbols", 0)),
                    ready_symbols=int(digest.get("ready_symbols", 0)),
                    not_ready_symbols=int(digest.get("not_ready_symbols", 0)),
                    blocked_symbols=int(digest.get("blocked_symbols", 0)),
                    reasons_summary=tuple(
                        str(reason)
                        for reason in digest.get("reasons_summary", ())
                        if isinstance(reason, str)
                    ),
                    compact_symbol_exceptions=tuple(
                        str(symbol)
                        for symbol in digest.get("compact_symbol_exceptions", ())
                        if isinstance(symbol, str)
                    ),
                    current_review_snapshot_collection=cls.CutoverReviewSnapshotCollectionDTO(
                        contour=str(digest_collection.get("contour", "unknown")),
                        scope_mode=str(digest_collection.get("scope_mode", "universe")),
                        headline=str(digest_collection.get("headline", "")),
                        discussion_state=str(digest_collection.get("discussion_state", "")),
                        manual_review_state=str(digest_collection.get("manual_review_state", "")),
                        cutover_evaluation_state=str(
                            digest_collection.get("cutover_evaluation_state", "")
                        ),
                        cutover_readiness_state=str(
                            digest_collection.get("cutover_readiness_state", "")
                        ),
                        compared_symbols=int(digest_collection.get("compared_symbols", 0)),
                        ready_symbols=int(digest_collection.get("ready_symbols", 0)),
                        not_ready_symbols=int(digest_collection.get("not_ready_symbols", 0)),
                        blocked_symbols=int(digest_collection.get("blocked_symbols", 0)),
                        reasons_summary=tuple(
                            str(reason)
                            for reason in digest_collection.get("reasons_summary", ())
                            if isinstance(reason, str)
                        ),
                        current_review_package_headline=str(
                            digest_collection.get("current_review_package_headline", "")
                        ),
                        current_review_package_discussion_state=str(
                            digest_collection.get(
                                "current_review_package_discussion_state",
                                "",
                            )
                        ),
                        current_review_catalog=cls.CutoverReviewCatalogDTO(
                            contour=str(digest_catalog.get("contour", "unknown")),
                            scope_mode=str(digest_catalog.get("scope_mode", "universe")),
                            headline=str(digest_catalog.get("headline", "")),
                            discussion_state=str(digest_catalog.get("discussion_state", "")),
                            manual_review_state=str(
                                digest_catalog.get("manual_review_state", "")
                            ),
                            cutover_evaluation_state=str(
                                digest_catalog.get("cutover_evaluation_state", "")
                            ),
                            cutover_readiness_state=str(
                                digest_catalog.get("cutover_readiness_state", "")
                            ),
                            compared_symbols=int(digest_catalog.get("compared_symbols", 0)),
                            ready_symbols=int(digest_catalog.get("ready_symbols", 0)),
                            not_ready_symbols=int(digest_catalog.get("not_ready_symbols", 0)),
                            blocked_symbols=int(digest_catalog.get("blocked_symbols", 0)),
                            reasons_summary=tuple(
                                str(reason)
                                for reason in digest_catalog.get("reasons_summary", ())
                                if isinstance(reason, str)
                            ),
                            current_review_package=cls.CutoverReviewPackageDTO(
                                contour=str(digest_package.get("contour", "unknown")),
                                scope_mode=str(digest_package.get("scope_mode", "universe")),
                                scope_symbol_count=int(digest_package.get("scope_symbol_count", 0)),
                                discussion_state=str(digest_package.get("discussion_state", "")),
                                manual_review_state=str(digest_package.get("manual_review_state", "")),
                                cutover_evaluation_state=str(
                                    digest_package.get("cutover_evaluation_state", "")
                                ),
                                cutover_readiness_state=str(
                                    digest_package.get("cutover_readiness_state", "")
                                ),
                                compared_symbols=int(digest_package.get("compared_symbols", 0)),
                                ready_symbols=int(digest_package.get("ready_symbols", 0)),
                                not_ready_symbols=int(digest_package.get("not_ready_symbols", 0)),
                                blocked_symbols=int(digest_package.get("blocked_symbols", 0)),
                                headline=str(digest_package.get("headline", "")),
                                reasons_summary=tuple(
                                    str(reason)
                                    for reason in digest_package.get("reasons_summary", ())
                                    if isinstance(reason, str)
                                ),
                                review_record=cls.CutoverReviewRecordDTO(
                                    captured_at=str(digest_record.get("captured_at", "")),
                                    contour=str(digest_record.get("contour", "unknown")),
                                    scope_mode=str(digest_record.get("scope_mode", "universe")),
                                    scope_symbol_count=int(digest_record.get("scope_symbol_count", 0)),
                                    discussion_state=str(digest_record.get("discussion_state", "")),
                                    manual_review_state=str(digest_record.get("manual_review_state", "")),
                                    cutover_evaluation_state=str(
                                        digest_record.get("cutover_evaluation_state", "")
                                    ),
                                    cutover_readiness_state=str(
                                        digest_record.get("cutover_readiness_state", "")
                                    ),
                                    compared_symbols=int(digest_record.get("compared_symbols", 0)),
                                    ready_symbols=int(digest_record.get("ready_symbols", 0)),
                                    not_ready_symbols=int(digest_record.get("not_ready_symbols", 0)),
                                    blocked_symbols=int(digest_record.get("blocked_symbols", 0)),
                                    headline=str(digest_record.get("headline", "")),
                                    reasons_summary=tuple(
                                        str(reason)
                                        for reason in digest_record.get("reasons_summary", ())
                                        if isinstance(reason, str)
                                    ),
                                    symbol_exceptions=tuple(
                                        cls.CutoverDiscussionExceptionDTO(
                                            symbol=str(item.get("symbol", "")),
                                            reconciliation_verdict=(
                                                str(item["reconciliation_verdict"])
                                                if isinstance(item.get("reconciliation_verdict"), str)
                                                else None
                                            ),
                                            reconciliation_reason=(
                                                str(item["reconciliation_reason"])
                                                if isinstance(item.get("reconciliation_reason"), str)
                                                else None
                                            ),
                                            cutover_readiness_state=(
                                                str(item["cutover_readiness_state"])
                                                if isinstance(item.get("cutover_readiness_state"), str)
                                                else None
                                            ),
                                            cutover_readiness_reason=(
                                                str(item["cutover_readiness_reason"])
                                                if isinstance(item.get("cutover_readiness_reason"), str)
                                                else None
                                            ),
                                        )
                                        for item in digest_record.get("symbol_exceptions", ())
                                        if isinstance(item, dict)
                                    ),
                                ),
                                symbol_exceptions=tuple(
                                    cls.CutoverDiscussionExceptionDTO(
                                        symbol=str(item.get("symbol", "")),
                                        reconciliation_verdict=(
                                            str(item["reconciliation_verdict"])
                                            if isinstance(item.get("reconciliation_verdict"), str)
                                            else None
                                        ),
                                        reconciliation_reason=(
                                            str(item["reconciliation_reason"])
                                            if isinstance(item.get("reconciliation_reason"), str)
                                            else None
                                        ),
                                        cutover_readiness_state=(
                                            str(item["cutover_readiness_state"])
                                            if isinstance(item.get("cutover_readiness_state"), str)
                                            else None
                                        ),
                                        cutover_readiness_reason=(
                                            str(item["cutover_readiness_reason"])
                                            if isinstance(item.get("cutover_readiness_reason"), str)
                                            else None
                                        ),
                                    )
                                    for item in digest_package.get("symbol_exceptions", ())
                                    if isinstance(item, dict)
                                ),
                            ),
                        ),
                    ),
                )
                if isinstance(connector.get("trade_count_cutover_review_compact_digest"), dict)
                and isinstance(
                    (digest := connector.get("trade_count_cutover_review_compact_digest")),
                    dict,
                )
                and isinstance(
                    (digest_collection := digest.get("current_review_snapshot_collection")),
                    dict,
                )
                and isinstance((digest_catalog := digest_collection.get("current_review_catalog")), dict)
                and isinstance((digest_package := digest_catalog.get("current_review_package")), dict)
                and isinstance((digest_record := digest_package.get("review_record")), dict)
                else None
            ),
            trade_count_cutover_export_report_bundle=(
                cls.CutoverExportReportBundleDTO(
                    contour=str(bundle.get("contour", "unknown")),
                    scope_mode=str(bundle.get("scope_mode", "universe")),
                    headline=str(bundle.get("headline", "")),
                    discussion_state=str(bundle.get("discussion_state", "")),
                    manual_review_state=str(bundle.get("manual_review_state", "")),
                    cutover_evaluation_state=str(bundle.get("cutover_evaluation_state", "")),
                    cutover_readiness_state=str(bundle.get("cutover_readiness_state", "")),
                    compared_symbols=int(bundle.get("compared_symbols", 0)),
                    ready_symbols=int(bundle.get("ready_symbols", 0)),
                    not_ready_symbols=int(bundle.get("not_ready_symbols", 0)),
                    blocked_symbols=int(bundle.get("blocked_symbols", 0)),
                    reasons_summary=tuple(
                        str(reason)
                        for reason in bundle.get("reasons_summary", ())
                        if isinstance(reason, str)
                    ),
                    compact_symbol_exceptions=tuple(
                        str(symbol)
                        for symbol in bundle.get("compact_symbol_exceptions", ())
                        if isinstance(symbol, str)
                    ),
                    export_text_summary=str(bundle.get("export_text_summary", "")),
                    current_compact_digest=cls.CutoverReviewCompactDigestDTO(
                        contour=str(bundle_digest.get("contour", "unknown")),
                        scope_mode=str(bundle_digest.get("scope_mode", "universe")),
                        headline=str(bundle_digest.get("headline", "")),
                        discussion_state=str(bundle_digest.get("discussion_state", "")),
                        manual_review_state=str(bundle_digest.get("manual_review_state", "")),
                        cutover_evaluation_state=str(
                            bundle_digest.get("cutover_evaluation_state", "")
                        ),
                        cutover_readiness_state=str(
                            bundle_digest.get("cutover_readiness_state", "")
                        ),
                        compared_symbols=int(bundle_digest.get("compared_symbols", 0)),
                        ready_symbols=int(bundle_digest.get("ready_symbols", 0)),
                        not_ready_symbols=int(bundle_digest.get("not_ready_symbols", 0)),
                        blocked_symbols=int(bundle_digest.get("blocked_symbols", 0)),
                        reasons_summary=tuple(
                            str(reason)
                            for reason in bundle_digest.get("reasons_summary", ())
                            if isinstance(reason, str)
                        ),
                        compact_symbol_exceptions=tuple(
                            str(symbol)
                            for symbol in bundle_digest.get("compact_symbol_exceptions", ())
                            if isinstance(symbol, str)
                        ),
                        current_review_snapshot_collection=cls.CutoverReviewSnapshotCollectionDTO(
                            contour=str(bundle_collection.get("contour", "unknown")),
                            scope_mode=str(bundle_collection.get("scope_mode", "universe")),
                            headline=str(bundle_collection.get("headline", "")),
                            discussion_state=str(bundle_collection.get("discussion_state", "")),
                            manual_review_state=str(
                                bundle_collection.get("manual_review_state", "")
                            ),
                            cutover_evaluation_state=str(
                                bundle_collection.get("cutover_evaluation_state", "")
                            ),
                            cutover_readiness_state=str(
                                bundle_collection.get("cutover_readiness_state", "")
                            ),
                            compared_symbols=int(bundle_collection.get("compared_symbols", 0)),
                            ready_symbols=int(bundle_collection.get("ready_symbols", 0)),
                            not_ready_symbols=int(
                                bundle_collection.get("not_ready_symbols", 0)
                            ),
                            blocked_symbols=int(bundle_collection.get("blocked_symbols", 0)),
                            reasons_summary=tuple(
                                str(reason)
                                for reason in bundle_collection.get("reasons_summary", ())
                                if isinstance(reason, str)
                            ),
                            current_review_package_headline=str(
                                bundle_collection.get("current_review_package_headline", "")
                            ),
                            current_review_package_discussion_state=str(
                                bundle_collection.get(
                                    "current_review_package_discussion_state",
                                    "",
                                )
                            ),
                            current_review_catalog=cls.CutoverReviewCatalogDTO(
                                contour=str(bundle_catalog.get("contour", "unknown")),
                                scope_mode=str(bundle_catalog.get("scope_mode", "universe")),
                                headline=str(bundle_catalog.get("headline", "")),
                                discussion_state=str(bundle_catalog.get("discussion_state", "")),
                                manual_review_state=str(
                                    bundle_catalog.get("manual_review_state", "")
                                ),
                                cutover_evaluation_state=str(
                                    bundle_catalog.get("cutover_evaluation_state", "")
                                ),
                                cutover_readiness_state=str(
                                    bundle_catalog.get("cutover_readiness_state", "")
                                ),
                                compared_symbols=int(bundle_catalog.get("compared_symbols", 0)),
                                ready_symbols=int(bundle_catalog.get("ready_symbols", 0)),
                                not_ready_symbols=int(
                                    bundle_catalog.get("not_ready_symbols", 0)
                                ),
                                blocked_symbols=int(bundle_catalog.get("blocked_symbols", 0)),
                                reasons_summary=tuple(
                                    str(reason)
                                    for reason in bundle_catalog.get("reasons_summary", ())
                                    if isinstance(reason, str)
                                ),
                                current_review_package=cls.CutoverReviewPackageDTO(
                                    contour=str(bundle_package.get("contour", "unknown")),
                                    scope_mode=str(bundle_package.get("scope_mode", "universe")),
                                    scope_symbol_count=int(bundle_package.get("scope_symbol_count", 0)),
                                    discussion_state=str(bundle_package.get("discussion_state", "")),
                                    manual_review_state=str(bundle_package.get("manual_review_state", "")),
                                    cutover_evaluation_state=str(
                                        bundle_package.get("cutover_evaluation_state", "")
                                    ),
                                    cutover_readiness_state=str(
                                        bundle_package.get("cutover_readiness_state", "")
                                    ),
                                    compared_symbols=int(bundle_package.get("compared_symbols", 0)),
                                    ready_symbols=int(bundle_package.get("ready_symbols", 0)),
                                    not_ready_symbols=int(bundle_package.get("not_ready_symbols", 0)),
                                    blocked_symbols=int(bundle_package.get("blocked_symbols", 0)),
                                    headline=str(bundle_package.get("headline", "")),
                                    reasons_summary=tuple(
                                        str(reason)
                                        for reason in bundle_package.get("reasons_summary", ())
                                        if isinstance(reason, str)
                                    ),
                                    review_record=cls.CutoverReviewRecordDTO(
                                        captured_at=str(bundle_record.get("captured_at", "")),
                                        contour=str(bundle_record.get("contour", "unknown")),
                                        scope_mode=str(bundle_record.get("scope_mode", "universe")),
                                        scope_symbol_count=int(bundle_record.get("scope_symbol_count", 0)),
                                        discussion_state=str(bundle_record.get("discussion_state", "")),
                                        manual_review_state=str(bundle_record.get("manual_review_state", "")),
                                        cutover_evaluation_state=str(
                                            bundle_record.get("cutover_evaluation_state", "")
                                        ),
                                        cutover_readiness_state=str(
                                            bundle_record.get("cutover_readiness_state", "")
                                        ),
                                        compared_symbols=int(bundle_record.get("compared_symbols", 0)),
                                        ready_symbols=int(bundle_record.get("ready_symbols", 0)),
                                        not_ready_symbols=int(bundle_record.get("not_ready_symbols", 0)),
                                        blocked_symbols=int(bundle_record.get("blocked_symbols", 0)),
                                        headline=str(bundle_record.get("headline", "")),
                                        reasons_summary=tuple(
                                            str(reason)
                                            for reason in bundle_record.get("reasons_summary", ())
                                            if isinstance(reason, str)
                                        ),
                                        symbol_exceptions=tuple(
                                            cls.CutoverDiscussionExceptionDTO(
                                                symbol=str(item.get("symbol", "")),
                                                reconciliation_verdict=(
                                                    str(item["reconciliation_verdict"])
                                                    if isinstance(item.get("reconciliation_verdict"), str)
                                                    else None
                                                ),
                                                reconciliation_reason=(
                                                    str(item["reconciliation_reason"])
                                                    if isinstance(item.get("reconciliation_reason"), str)
                                                    else None
                                                ),
                                                cutover_readiness_state=(
                                                    str(item["cutover_readiness_state"])
                                                    if isinstance(item.get("cutover_readiness_state"), str)
                                                    else None
                                                ),
                                                cutover_readiness_reason=(
                                                    str(item["cutover_readiness_reason"])
                                                    if isinstance(item.get("cutover_readiness_reason"), str)
                                                    else None
                                                ),
                                            )
                                            for item in bundle_record.get("symbol_exceptions", ())
                                            if isinstance(item, dict)
                                        ),
                                    ),
                                    symbol_exceptions=tuple(
                                        cls.CutoverDiscussionExceptionDTO(
                                            symbol=str(item.get("symbol", "")),
                                            reconciliation_verdict=(
                                                str(item["reconciliation_verdict"])
                                                if isinstance(item.get("reconciliation_verdict"), str)
                                                else None
                                            ),
                                            reconciliation_reason=(
                                                str(item["reconciliation_reason"])
                                                if isinstance(item.get("reconciliation_reason"), str)
                                                else None
                                            ),
                                            cutover_readiness_state=(
                                                str(item["cutover_readiness_state"])
                                                if isinstance(item.get("cutover_readiness_state"), str)
                                                else None
                                            ),
                                            cutover_readiness_reason=(
                                                str(item["cutover_readiness_reason"])
                                                if isinstance(item.get("cutover_readiness_reason"), str)
                                                else None
                                            ),
                                        )
                                        for item in bundle_package.get("symbol_exceptions", ())
                                        if isinstance(item, dict)
                                    ),
                                ),
                            ),
                        ),
                    ),
                )
                if isinstance(connector.get("trade_count_cutover_export_report_bundle"), dict)
                and isinstance(
                    (bundle := connector.get("trade_count_cutover_export_report_bundle")),
                    dict,
                )
                and isinstance((bundle_digest := bundle.get("current_compact_digest")), dict)
                and isinstance(
                    (bundle_collection := bundle_digest.get("current_review_snapshot_collection")),
                    dict,
                )
                and isinstance((bundle_catalog := bundle_collection.get("current_review_catalog")), dict)
                and isinstance((bundle_package := bundle_catalog.get("current_review_package")), dict)
                and isinstance((bundle_record := bundle_package.get("review_record")), dict)
                else None
            ),
            desired_scope_mode=connector.get("desired_scope_mode")
            if isinstance(connector.get("desired_scope_mode"), str)
            else None,
            desired_trade_count_filter_minimum=connector.get("desired_trade_count_filter_minimum")
            if isinstance(connector.get("desired_trade_count_filter_minimum"), int)
            else None,
            applied_scope_mode=connector.get("applied_scope_mode")
            if isinstance(connector.get("applied_scope_mode"), str)
            else None,
            applied_trade_count_filter_minimum=connector.get("applied_trade_count_filter_minimum")
            if isinstance(connector.get("applied_trade_count_filter_minimum"), int)
            else None,
            trade_count_product_truth_state=connector.get("trade_count_product_truth_state")
            if isinstance(connector.get("trade_count_product_truth_state"), str)
            else None,
            trade_count_product_truth_reason=connector.get("trade_count_product_truth_reason")
            if isinstance(connector.get("trade_count_product_truth_reason"), str)
            else None,
            trade_count_truth_model=connector.get("trade_count_truth_model")
            if isinstance(connector.get("trade_count_truth_model"), str)
            else None,
            trade_count_canonical_truth_owner=connector.get("trade_count_canonical_truth_owner")
            if isinstance(connector.get("trade_count_canonical_truth_owner"), str)
            else None,
            trade_count_canonical_truth_source=connector.get("trade_count_canonical_truth_source")
            if isinstance(connector.get("trade_count_canonical_truth_source"), str)
            else None,
            trade_count_operational_truth_owner=connector.get("trade_count_operational_truth_owner")
            if isinstance(connector.get("trade_count_operational_truth_owner"), str)
            else None,
            trade_count_operational_truth_source=connector.get("trade_count_operational_truth_source")
            if isinstance(connector.get("trade_count_operational_truth_source"), str)
            else None,
            trade_count_connector_canonical_role=connector.get("trade_count_connector_canonical_role")
            if isinstance(connector.get("trade_count_connector_canonical_role"), str)
            else None,
            trade_count_admission_basis=connector.get("trade_count_admission_basis")
            if isinstance(connector.get("trade_count_admission_basis"), str)
            else None,
            trade_count_admission_truth_owner=connector.get("trade_count_admission_truth_owner")
            if isinstance(connector.get("trade_count_admission_truth_owner"), str)
            else None,
            trade_count_admission_truth_source=connector.get("trade_count_admission_truth_source")
            if isinstance(connector.get("trade_count_admission_truth_source"), str)
            else None,
            policy_apply_status=connector.get("policy_apply_status")
            if isinstance(connector.get("policy_apply_status"), str)
            else None,
            policy_apply_reason=connector.get("policy_apply_reason")
            if isinstance(connector.get("policy_apply_reason"), str)
            else None,
            operator_runtime_state=connector.get("operator_runtime_state")
            if isinstance(connector.get("operator_runtime_state"), str)
            else None,
            operator_runtime_reason=connector.get("operator_runtime_reason")
            if isinstance(connector.get("operator_runtime_reason"), str)
            else None,
            operator_confidence_state=connector.get("operator_confidence_state")
            if isinstance(connector.get("operator_confidence_state"), str)
            else None,
            operator_confidence_reason=connector.get("operator_confidence_reason")
            if isinstance(connector.get("operator_confidence_reason"), str)
            else None,
            operator_state_surface=connector.get("operator_state_surface")
            if isinstance(connector.get("operator_state_surface"), dict)
            else None,
            operational_recovery_state=connector.get("operational_recovery_state")
            if isinstance(connector.get("operational_recovery_state"), str)
            else None,
            operational_recovery_reason=connector.get("operational_recovery_reason")
            if isinstance(connector.get("operational_recovery_reason"), str)
            else None,
            canonical_ledger_sync_state=connector.get("canonical_ledger_sync_state")
            if isinstance(connector.get("canonical_ledger_sync_state"), str)
            else None,
            canonical_ledger_sync_reason=connector.get("canonical_ledger_sync_reason")
            if isinstance(connector.get("canonical_ledger_sync_reason"), str)
            else None,
            post_recovery_materialization_status=connector.get(
                "post_recovery_materialization_status"
            )
            if isinstance(connector.get("post_recovery_materialization_status"), str)
            else None,
            historical_recovery_state=connector.get("historical_recovery_state")
            if isinstance(connector.get("historical_recovery_state"), str)
            else None,
            historical_recovery_reason=connector.get("historical_recovery_reason")
            if isinstance(connector.get("historical_recovery_reason"), str)
            else None,
            historical_recovery_retry_pending=bool(
                connector.get("historical_recovery_retry_pending", False)
            ),
            historical_recovery_backfill_task_active=bool(
                connector.get("historical_recovery_backfill_task_active", False)
            ),
            historical_recovery_retry_task_active=bool(
                connector.get("historical_recovery_retry_task_active", False)
            ),
            historical_recovery_cutoff_at=connector.get("historical_recovery_cutoff_at")
            if isinstance(connector.get("historical_recovery_cutoff_at"), str)
            else None,
            archive_cache_enabled=bool(connector.get("archive_cache_enabled", False)),
            archive_cache_memory_hits=int(connector.get("archive_cache_memory_hits", 0)),
            archive_cache_disk_hits=int(connector.get("archive_cache_disk_hits", 0)),
            archive_cache_misses=int(connector.get("archive_cache_misses", 0)),
            archive_cache_writes=int(connector.get("archive_cache_writes", 0)),
            archive_cache_last_hit_source=connector.get("archive_cache_last_hit_source")
            if isinstance(connector.get("archive_cache_last_hit_source"), str)
            else None,
            archive_cache_last_url=connector.get("archive_cache_last_url")
            if isinstance(connector.get("archive_cache_last_url"), str)
            else None,
            archive_cache_last_cleanup_at=connector.get("archive_cache_last_cleanup_at")
            if isinstance(connector.get("archive_cache_last_cleanup_at"), str)
            else None,
            archive_cache_last_pruned_files=int(
                connector.get("archive_cache_last_pruned_files", 0)
            ),
            archive_cache_last_network_fetch_ms=connector.get("archive_cache_last_network_fetch_ms")
            if isinstance(connector.get("archive_cache_last_network_fetch_ms"), int)
            else None,
            archive_cache_last_disk_read_ms=connector.get("archive_cache_last_disk_read_ms")
            if isinstance(connector.get("archive_cache_last_disk_read_ms"), int)
            else None,
            archive_cache_last_gzip_decode_ms=connector.get("archive_cache_last_gzip_decode_ms")
            if isinstance(connector.get("archive_cache_last_gzip_decode_ms"), int)
            else None,
            archive_cache_last_csv_parse_ms=connector.get("archive_cache_last_csv_parse_ms")
            if isinstance(connector.get("archive_cache_last_csv_parse_ms"), int)
            else None,
            archive_cache_last_archive_total_ms=connector.get("archive_cache_last_archive_total_ms")
            if isinstance(connector.get("archive_cache_last_archive_total_ms"), int)
            else None,
            archive_cache_last_symbol_total_ms=connector.get("archive_cache_last_symbol_total_ms")
            if isinstance(connector.get("archive_cache_last_symbol_total_ms"), int)
            else None,
            archive_cache_last_symbol=connector.get("archive_cache_last_symbol")
            if isinstance(connector.get("archive_cache_last_symbol"), str)
            else None,
            archive_cache_total_network_fetch_ms=int(
                connector.get("archive_cache_total_network_fetch_ms", 0)
            ),
            archive_cache_total_disk_read_ms=int(
                connector.get("archive_cache_total_disk_read_ms", 0)
            ),
            archive_cache_total_gzip_decode_ms=int(
                connector.get("archive_cache_total_gzip_decode_ms", 0)
            ),
            archive_cache_total_csv_parse_ms=int(
                connector.get("archive_cache_total_csv_parse_ms", 0)
            ),
            archive_cache_total_archive_total_ms=int(
                connector.get("archive_cache_total_archive_total_ms", 0)
            ),
            archive_cache_total_symbol_total_ms=int(
                connector.get("archive_cache_total_symbol_total_ms", 0)
            ),
            scope_mode=str(connector.get("scope_mode", "universe")),
            discovery_status=connector.get("discovery_status")
            if isinstance(connector.get("discovery_status"), str)
            else None,
            discovery_error=connector.get("discovery_error")
            if isinstance(connector.get("discovery_error"), str)
            else None,
            total_instruments_discovered=connector.get("total_instruments_discovered")
            if isinstance(connector.get("total_instruments_discovered"), int)
            else None,
            instruments_passed_coarse_filter=connector.get("instruments_passed_coarse_filter")
            if isinstance(connector.get("instruments_passed_coarse_filter"), int)
            else None,
            quote_volume_filter_ready=connector.get("quote_volume_filter_ready")
            if isinstance(connector.get("quote_volume_filter_ready"), bool)
            else None,
            trade_count_filter_ready=connector.get("trade_count_filter_ready")
            if isinstance(connector.get("trade_count_filter_ready"), bool)
            else None,
            instruments_passed_trade_count_filter=connector.get(
                "instruments_passed_trade_count_filter"
            )
            if isinstance(connector.get("instruments_passed_trade_count_filter"), int)
            else None,
            universe_admission_state=connector.get("universe_admission_state")
            if isinstance(connector.get("universe_admission_state"), str)
            else None,
            active_subscribed_scope_count=int(connector.get("active_subscribed_scope_count", 0)),
            live_trade_streams_count=int(connector.get("live_trade_streams_count", 0)),
            live_orderbook_count=int(connector.get("live_orderbook_count", 0)),
            degraded_or_stale_count=int(connector.get("degraded_or_stale_count", 0)),
        )


class BybitConnectorToggleDTO(BaseModel):
    """Narrow backend control payload for enabling or disabling the Bybit connector."""

    enabled: bool = Field(
        description="Должен ли canonical backend runtime держать Bybit connector включённым."
    )
