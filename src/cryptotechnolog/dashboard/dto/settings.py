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
    bybit_universe_min_quote_volume_24h_usd: float = Field(
        description="Минимальный 24h quote volume в USD для coarse prefilter universe.",
    )
    bybit_universe_min_trade_count_24h: int = Field(
        description="Минимальное число сделок за 24h для coarse prefilter universe.",
    )
    bybit_universe_max_symbols_per_scope: int = Field(
        description="Максимальное число инструментов, передаваемых в active connector scope.",
    )

    @classmethod
    def from_settings(cls, settings: Settings) -> LiveFeedPolicySettingsDTO:
        """Build DTO from canonical project settings."""
        return cls(
            retry_delay_seconds=settings.live_feed_retry_delay_seconds,
            bybit_universe_min_quote_volume_24h_usd=settings.bybit_universe_min_quote_volume_24h_usd,
            bybit_universe_min_trade_count_24h=settings.bybit_universe_min_trade_count_24h,
            bybit_universe_max_symbols_per_scope=settings.bybit_universe_max_symbols_per_scope,
        )

    def to_settings_update(self) -> dict[str, float | int]:
        """Convert DTO back into Settings field updates."""
        return {
            "live_feed_retry_delay_seconds": self.retry_delay_seconds,
            "bybit_universe_min_quote_volume_24h_usd": self.bybit_universe_min_quote_volume_24h_usd,
            "bybit_universe_min_trade_count_24h": self.bybit_universe_min_trade_count_24h,
            "bybit_universe_max_symbols_per_scope": self.bybit_universe_max_symbols_per_scope,
        }


class BybitConnectorDiagnosticsDTO(BaseModel):
    """Read-only Bybit connector diagnostics surfaced for settings UI."""

    class SymbolSnapshotDTO(BaseModel):
        symbol: str = Field(description="Инструмент внутри текущего Bybit connector scope.")
        trade_seen: bool = Field(description="Поступали ли trade ticks для этого инструмента.")
        orderbook_seen: bool = Field(
            description="Поступал ли честный orderbook snapshot для этого инструмента."
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
        observed_trade_count_since_reset: int = Field(
            default=0,
            description="Сколько trade ticks накоплено с последнего reliability reset.",
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
        description="Количество reconnect/retry попыток в текущем lifecycle окне."
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
                        observed_trade_count_since_reset=int(
                            snapshot.get("observed_trade_count_since_reset", 0)
                        ),
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
