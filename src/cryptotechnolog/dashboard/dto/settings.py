"""DTO модели для backend-backed dashboard settings endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

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

    @classmethod
    def from_settings(cls, settings: Settings) -> LiveFeedPolicySettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            retry_delay_seconds=settings.live_feed_retry_delay_seconds,
        )

    def to_settings_update(self) -> dict[str, int]:
        """Convert DTO back into Settings field updates."""
        return {
            "live_feed_retry_delay_seconds": self.retry_delay_seconds,
        }
