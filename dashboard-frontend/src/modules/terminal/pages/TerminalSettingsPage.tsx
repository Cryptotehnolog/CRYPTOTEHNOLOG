import { useEffect, useMemo, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { TerminalBadge } from "../components/TerminalBadge";
import { getCorrelationPolicySettings } from "../api/getCorrelationPolicySettings";
import { getDecisionChainSettings } from "../api/getDecisionChainSettings";
import { getEventBusPolicySettings } from "../api/getEventBusPolicySettings";
import { getFundingPolicySettings } from "../api/getFundingPolicySettings";
import { getHealthPolicySettings } from "../api/getHealthPolicySettings";
import { getLiveFeedPolicySettings } from "../api/getLiveFeedPolicySettings";
import { getManualApprovalPolicySettings } from "../api/getManualApprovalPolicySettings";
import { getProtectionPolicySettings } from "../api/getProtectionPolicySettings";
import { getReliabilityPolicySettings } from "../api/getReliabilityPolicySettings";
import { getRiskLimitsSettings } from "../api/getRiskLimitsSettings";
import { getSystemStatePolicySettings } from "../api/getSystemStatePolicySettings";
import { getSystemStateTimeoutSettings } from "../api/getSystemStateTimeoutSettings";
import { getTrailingPolicySettings } from "../api/getTrailingPolicySettings";
import { getUniversePolicySettings } from "../api/getUniversePolicySettings";
import { getWorkflowTimeoutSettings } from "../api/getWorkflowTimeoutSettings";
import { updateCorrelationPolicySettings } from "../api/updateCorrelationPolicySettings";
import { updateDecisionChainSettings } from "../api/updateDecisionChainSettings";
import { updateEventBusPolicySettings } from "../api/updateEventBusPolicySettings";
import { updateFundingPolicySettings } from "../api/updateFundingPolicySettings";
import { updateHealthPolicySettings } from "../api/updateHealthPolicySettings";
import { updateManualApprovalPolicySettings } from "../api/updateManualApprovalPolicySettings";
import { updateProtectionPolicySettings } from "../api/updateProtectionPolicySettings";
import { updateReliabilityPolicySettings } from "../api/updateReliabilityPolicySettings";
import { updateRiskLimitsSettings } from "../api/updateRiskLimitsSettings";
import { updateSystemStatePolicySettings } from "../api/updateSystemStatePolicySettings";
import { updateSystemStateTimeoutSettings } from "../api/updateSystemStateTimeoutSettings";
import { updateTrailingPolicySettings } from "../api/updateTrailingPolicySettings";
import { updateUniversePolicySettings } from "../api/updateUniversePolicySettings";
import { updateWorkflowTimeoutSettings } from "../api/updateWorkflowTimeoutSettings";
import { useTerminalUiStore } from "../state/useTerminalUiStore";
import { useTerminalWidgetStore } from "../state/useTerminalWidgetStore";
import type {
  CorrelationPolicySettingsResponse,
  DecisionChainSettingsResponse,
  EventBusPolicySettingsResponse,
  FundingPolicySettingsResponse,
  HealthPolicySettingsResponse,
  ManualApprovalPolicySettingsResponse,
  ProtectionPolicySettingsResponse,
  ReliabilityPolicySettingsResponse,
  RiskLimitsSettingsResponse,
  SystemStatePolicySettingsResponse,
  SystemStateTimeoutSettingsResponse,
  TrailingPolicySettingsResponse,
  UniversePolicySettingsResponse,
  WorkflowTimeoutsSettingsResponse,
} from "../../../shared/types/dashboard";
import {
  comparisonBodyCell,
  comparisonHeadCell,
  comparisonInput,
  comparisonRecommendation,
  comparisonRowCaption,
  comparisonRowDescription,
  comparisonRowHeader,
  comparisonRowTitle,
  comparisonTable,
  comparisonTableCompact,
  comparisonTableWrap,
  exchangeMeta,
  fieldDescription,
  fieldInput,
  fieldLabel,
  saveButton,
  saveButtonDisabled,
  settingsErrorState,
  settingsFieldCard,
  settingsFieldGrid,
  settingsFieldHeader,
  settingsFieldMeta,
  settingsForm,
  localStateNote,
  modeButton,
  modeControls,
  pageRoot,
  sectionBody,
  sectionCaption,
  sectionHeader,
  sectionTitle,
  settingsCard,
  stateValue,
  widgetSettingsCard,
  widgetSettingsGrid,
  widgetSettingsMeta,
  widgetSettingsRow,
  widgetVisibilityCheckbox,
  widgetVisibilityControl,
} from "./TerminalSettingsPage.css";

type UniversePolicyFieldKey = keyof UniversePolicySettingsResponse;
type UniversePolicyDraft = Record<UniversePolicyFieldKey, string>;
type DecisionChainFieldKey = keyof DecisionChainSettingsResponse;
type DecisionChainDraft = Record<DecisionChainFieldKey, string>;
type RiskLimitsFieldKey = keyof RiskLimitsSettingsResponse;
type RiskLimitsDraft = Record<RiskLimitsFieldKey, string>;
type TrailingPolicyFieldKey = keyof TrailingPolicySettingsResponse;
type TrailingPolicyDraft = Record<TrailingPolicyFieldKey, string>;
type CorrelationPolicyFieldKey = keyof CorrelationPolicySettingsResponse;
type CorrelationPolicyDraft = Record<CorrelationPolicyFieldKey, string>;
type ProtectionPolicyFieldKey = keyof ProtectionPolicySettingsResponse;
type ProtectionPolicyDraft = Record<ProtectionPolicyFieldKey, string>;
type FundingPolicyFieldKey = keyof FundingPolicySettingsResponse;
type FundingPolicyDraft = Record<FundingPolicyFieldKey, string>;
type HealthPolicyFieldKey = keyof HealthPolicySettingsResponse;
type HealthPolicyDraft = Record<HealthPolicyFieldKey, string>;
type EventBusPolicyFieldKey = keyof EventBusPolicySettingsResponse;
type EventBusPolicyDraft = Record<EventBusPolicyFieldKey, string>;
type ManualApprovalPolicyFieldKey = keyof ManualApprovalPolicySettingsResponse;
type ManualApprovalPolicyDraft = Record<ManualApprovalPolicyFieldKey, string>;
type WorkflowTimeoutFieldKey = keyof WorkflowTimeoutsSettingsResponse;
type WorkflowTimeoutDraft = Record<WorkflowTimeoutFieldKey, string>;
type ReliabilityPolicyFieldKey = keyof ReliabilityPolicySettingsResponse;
type ReliabilityPolicyDraft = Record<ReliabilityPolicyFieldKey, string>;
type SystemStatePolicyFieldKey = keyof SystemStatePolicySettingsResponse;
type SystemStatePolicyDraft = Record<SystemStatePolicyFieldKey, string>;
type SystemStateTimeoutFieldKey = keyof SystemStateTimeoutSettingsResponse;
type SystemStateTimeoutDraft = Record<SystemStateTimeoutFieldKey, string>;

const universePolicyFieldDefinitions: Array<{
  key: UniversePolicyFieldKey;
  label: string;
  description: string;
  recommended: string;
  inputMode: "decimal" | "numeric";
  step: string;
}> = [
  {
    key: "max_spread_bps",
    label: "Максимальный допустимый спред",
    description: "Порог спреда, выше которого инструмент исключается из рабочего universe.",
    recommended: "25 bps",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "min_top_depth_usd",
    label: "Минимальная глубина в верхушке стакана",
    description: "Минимальная ликвидность в топе книги заявок для допуска инструмента.",
    recommended: "75 000 USD",
    inputMode: "decimal",
    step: "1000",
  },
  {
    key: "min_depth_5bps_usd",
    label: "Минимальная глубина в диапазоне 5 bps",
    description: "Минимальная суммарная глубина внутри диапазона 5 bps от mid-price.",
    recommended: "200 000 USD",
    inputMode: "decimal",
    step: "1000",
  },
  {
    key: "max_latency_ms",
    label: "Максимальная допустимая задержка данных",
    description: "Максимальный latency market-data path до перевода инструмента в low-confidence.",
    recommended: "250 ms",
    inputMode: "decimal",
    step: "1",
  },
  {
    key: "min_coverage_ratio",
    label: "Минимальное покрытие данных",
    description: "Минимальная доля валидного покрытия market-data для допуска инструмента.",
    recommended: "0.90",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "max_data_age_ms",
    label: "Максимальная допустимая старость данных",
    description: "Порог stale market-data, после которого инструмент исключается из universe.",
    recommended: "3000 ms",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "min_quality_score",
    label: "Минимальная оценка качества данных",
    description: "Нижняя граница quality score для допуска инструмента.",
    recommended: "0.60",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "min_ready_instruments",
    label: "Минимальное число пригодных инструментов для режима ready",
    description: "Минимальное количество admissible инструментов для состояния READY.",
    recommended: "5",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "min_degraded_instruments_ratio",
    label: "Минимальная доля пригодных инструментов для degraded режима",
    description: "Нижняя доля admissible universe, ниже которой состояние падает в BLOCKED.",
    recommended: "0.10",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "min_ready_confidence",
    label: "Минимальная уверенность universe для ready",
    description: "Порог universe confidence для перехода в READY.",
    recommended: "0.70",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "min_degraded_confidence",
    label: "Минимальная уверенность universe для degraded",
    description: "Минимальная universe confidence, при которой система ещё остаётся в DEGRADED.",
    recommended: "0.45",
    inputMode: "decimal",
    step: "0.01",
  },
];

const decisionChainFieldDefinitions: Array<{
  key: DecisionChainFieldKey;
  label: string;
  description: string;
  recommended: string;
  inputMode: "decimal" | "numeric";
  step: string;
}> = [
  {
    key: "signal_min_trend_strength",
    label: "Минимальная сила тренда для сигнала",
    description: "Нижняя граница силы тренда, ниже которой signal layer не активирует идею.",
    recommended: "20",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "signal_min_regime_confidence",
    label: "Минимальная уверенность режима для сигнала",
    description: "Минимальная уверенность regime layer для активации сигнала.",
    recommended: "0.50",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "signal_target_risk_reward",
    label: "Целевое отношение риск/прибыль",
    description: "Базовый risk/reward target, который signal layer считает достаточным.",
    recommended: "2.0",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "signal_max_age_seconds",
    label: "Максимальный срок жизни сигнала",
    description: "Через сколько секунд сигнал считается устаревшим и больше не проходит дальше.",
    recommended: "300 сек",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "strategy_min_signal_confidence",
    label: "Минимальная уверенность сигнала для действия",
    description: "Нижняя граница signal confidence, при которой strategy layer ещё готов действовать.",
    recommended: "0.50",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "strategy_max_candidate_age_seconds",
    label: "Максимальный срок жизни стратегического кандидата",
    description: "Через сколько секунд стратегический кандидат считается протухшим.",
    recommended: "300 сек",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "execution_min_strategy_confidence",
    label: "Минимальная уверенность стратегии для исполнения",
    description: "Минимальная уверенность strategy layer для формирования execution intent.",
    recommended: "0.50",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "execution_max_intent_age_seconds",
    label: "Максимальный срок жизни намерения на исполнение",
    description: "Через сколько секунд execution intent больше не считается актуальным.",
    recommended: "300 сек",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "opportunity_min_confidence",
    label: "Минимальная уверенность для отбора возможности",
    description: "Нижняя граница уверенности, при которой opportunity layer ещё выбирает идею.",
    recommended: "0.50",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "opportunity_min_priority",
    label: "Минимальный приоритет для отбора возможности",
    description: "Минимальный priority score для попадания в selection stage.",
    recommended: "0.50",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "opportunity_max_age_seconds",
    label: "Максимальный срок жизни выбранной возможности",
    description: "Через сколько секунд выбранная opportunity больше не передаётся дальше.",
    recommended: "300 сек",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "orchestration_min_confidence",
    label: "Минимальная уверенность для передачи дальше",
    description: "Минимальная уверенность selection layer для forwarding в orchestration path.",
    recommended: "0.50",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "orchestration_min_priority",
    label: "Минимальный приоритет для передачи дальше",
    description: "Минимальный priority score для дальнейшей оркестрации решения.",
    recommended: "0.50",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "orchestration_max_decision_age_seconds",
    label: "Максимальный срок жизни orchestration-решения",
    description: "Через сколько секунд orchestration decision больше не считается пригодным.",
    recommended: "300 сек",
    inputMode: "numeric",
    step: "1",
  },
];

const riskLimitsFieldDefinitions: Array<{
  key: RiskLimitsFieldKey;
  label: string;
  description: string;
  recommended: string;
  inputMode: "decimal" | "numeric";
  step: string;
}> = [
  {
    key: "base_r_percent",
    label: "Базовый риск на сделку",
    description: "Базовая доля капитала, которую система считает нормальным риском на одну сделку.",
    recommended: "0.01",
    inputMode: "decimal",
    step: "0.001",
  },
  {
    key: "max_r_per_trade",
    label: "Максимальный риск на одну сделку",
    description: "Верхний лимит риска на одну сделку в единицах R.",
    recommended: "1.0",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "max_portfolio_r",
    label: "Максимальный суммарный риск по портфелю",
    description: "Максимальный допустимый совокупный риск всех открытых позиций в R.",
    recommended: "5.0",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "risk_max_total_exposure_usd",
    label: "Максимальная суммарная экспозиция по портфелю в USD",
    description: "Верхний лимит общей денежной экспозиции всех позиций по портфелю.",
    recommended: "50 000 USD",
    inputMode: "decimal",
    step: "1000",
  },
  {
    key: "max_position_size",
    label: "Максимальный размер позиции в USD",
    description: "Максимальный денежный размер одной позиции, который допускает risk layer.",
    recommended: "10 000 USD",
    inputMode: "decimal",
    step: "100",
  },
  {
    key: "risk_starting_equity",
    label: "Стартовый капитал для risk runtime",
    description: "Базовый equity baseline, от которого считаются drawdown и risk discipline.",
    recommended: "10 000 USD",
    inputMode: "decimal",
    step: "100",
  },
];

const trailingPolicyFieldDefinitions: Array<{
  key: TrailingPolicyFieldKey;
  label: string;
  description: string;
  recommended: string;
  inputMode: "decimal" | "numeric";
  step: string;
}> = [
  {
    key: "arm_at_pnl_r",
    label: "Когда включать трейлинг по прибыли в R",
    description: "Порог прибыли, после которого система вооружает trailing-stop.",
    recommended: "1.0 R",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "t2_at_pnl_r",
    label: "Порог второго уровня трейлинга по прибыли в R",
    description: "Уровень прибыли, на котором trailing переходит ко второму tier.",
    recommended: "2.0 R",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "t3_at_pnl_r",
    label: "Порог третьего уровня трейлинга по прибыли в R",
    description: "Уровень прибыли, на котором trailing переходит к третьему tier.",
    recommended: "4.0 R",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "t4_at_pnl_r",
    label: "Порог четвёртого уровня трейлинга по прибыли в R",
    description: "Уровень прибыли, на котором trailing переходит к самому плотному tier.",
    recommended: "6.0 R",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "t1_atr_multiplier",
    label: "Множитель ATR для первого уровня",
    description: "Ширина стопа через ATR для первого tier trailing policy.",
    recommended: "2.0",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "t2_atr_multiplier",
    label: "Множитель ATR для второго уровня",
    description: "Ширина стопа через ATR для второго tier trailing policy.",
    recommended: "1.5",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "t3_atr_multiplier",
    label: "Множитель ATR для третьего уровня",
    description: "Ширина стопа через ATR для третьего tier trailing policy.",
    recommended: "1.1",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "t4_atr_multiplier",
    label: "Множитель ATR для четвёртого уровня",
    description: "Ширина стопа через ATR для четвёртого tier trailing policy.",
    recommended: "0.8",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "emergency_buffer_bps",
    label: "Аварийный защитный буфер в bps",
    description: "Защитный буфер для emergency stop movement при стрессовом рынке.",
    recommended: "50 bps",
    inputMode: "decimal",
    step: "1",
  },
  {
    key: "structural_min_adx",
    label: "Минимальная сила тренда для структурного режима",
    description: "Минимальная сила тренда, ниже которой structural trailing не включается.",
    recommended: "25.0",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "structural_confirmed_highs",
    label: "Минимум подтверждённых максимумов",
    description: "Сколько подтверждённых максимумов нужно для structural trailing в long path.",
    recommended: "2",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "structural_confirmed_lows",
    label: "Минимум подтверждённых минимумов",
    description: "Сколько подтверждённых минимумов нужно для structural trailing в short path.",
    recommended: "2",
    inputMode: "numeric",
    step: "1",
  },
];

const correlationPolicyFieldDefinitions: Array<{
  key: CorrelationPolicyFieldKey;
  label: string;
  description: string;
  recommended: string;
  inputMode: "decimal" | "numeric";
  step: string;
}> = [
  {
    key: "correlation_limit",
    label: "Максимально допустимая корреляция между позициями",
    description: "Верхний порог, выше которого новая позиция считается слишком похожей на портфель.",
    recommended: "0.80",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "same_group_correlation",
    label: "Допустимая корреляция внутри одной группы инструментов",
    description: "Базовая оценка схожести для инструментов внутри одной correlation group.",
    recommended: "0.65",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "cross_group_correlation",
    label: "Допустимая корреляция между разными группами инструментов",
    description: "Базовая оценка схожести для инструментов из разных correlation groups.",
    recommended: "0.25",
    inputMode: "decimal",
    step: "0.01",
  },
];

const protectionPolicyFieldDefinitions: Array<{
  key: ProtectionPolicyFieldKey;
  label: string;
  description: string;
  recommended: string;
  inputMode: "decimal" | "numeric";
  step: string;
}> = [
  {
    key: "halt_priority_threshold",
    label: "Порог для жёсткой защиты",
    description:
      "При этом уровне приоритета protection layer переводит систему в режим жёсткой защиты.",
    recommended: "0.90",
    inputMode: "decimal",
    step: "0.001",
  },
  {
    key: "freeze_priority_threshold",
    label: "Порог для заморозки новых действий",
    description:
      "При этом уровне приоритета система перестаёт пропускать новые действия и расширения.",
    recommended: "0.975",
    inputMode: "decimal",
    step: "0.001",
  },
];

const fundingPolicyFieldDefinitions: Array<{
  key: FundingPolicyFieldKey;
  label: string;
  description: string;
  recommended: string;
  inputMode: "decimal" | "numeric";
  step: string;
}> = [
  {
    key: "min_arbitrage_spread",
    label: "Минимальный спред для funding-возможности",
    description: "Нижняя граница funding spread за период для обнаружения межбиржевой идеи.",
    recommended: "0.002",
    inputMode: "decimal",
    step: "0.0001",
  },
  {
    key: "min_annualized_spread",
    label: "Минимальный годовой спред для funding-возможности",
    description: "Нижняя граница annualized spread, ниже которой возможность считается слишком слабой.",
    recommended: "0.05",
    inputMode: "decimal",
    step: "0.001",
  },
  {
    key: "max_acceptable_funding",
    label: "Максимально допустимый funding rate",
    description: "Предельная funding-ставка, выше которой новая позиция считается слишком дорогой.",
    recommended: "0.003",
    inputMode: "decimal",
    step: "0.0001",
  },
  {
    key: "min_exchange_improvement",
    label: "Минимальное улучшение между биржами",
    description: "Минимальная выгода по funding, которая оправдывает перевод на другую биржу.",
    recommended: "0.0005",
    inputMode: "decimal",
    step: "0.0001",
  },
  {
    key: "min_quotes_for_opportunity",
    label: "Минимальное число котировок для поиска возможности",
    description: "Сколько funding-котировок нужно, чтобы система вообще искала межбиржевую возможность.",
    recommended: "2",
    inputMode: "numeric",
    step: "1",
  },
];

const systemStatePolicyFieldDefinitions: Array<{
  key: SystemStatePolicyFieldKey;
  label: string;
  description: string;
  recommended: string;
  inputMode: "decimal" | "numeric";
  step: string;
}> = [
  {
    key: "trading_risk_multiplier",
    label: "Множитель риска",
    description: "Насколько агрессивно система работает в режиме обычной торговли.",
    recommended: "1.0",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "trading_max_positions",
    label: "Максимум одновременно открытых позиций",
    description: "Сколько позиций система может держать одновременно в обычном торговом режиме.",
    recommended: "100",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "trading_max_order_size",
    label: "Максимальный размер новой позиции",
    description: "Верхний лимит новой позиции как доля портфеля в обычном торговом режиме.",
    recommended: "0.10",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "degraded_risk_multiplier",
    label: "Множитель риска",
    description: "Насколько сильно система ужимает риск в деградированном режиме.",
    recommended: "0.50",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "degraded_max_positions",
    label: "Максимум одновременно открытых позиций",
    description: "Сколько позиций разрешено держать одновременно в деградированном режиме.",
    recommended: "50",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "degraded_max_order_size",
    label: "Максимальный размер новой позиции",
    description: "Верхний лимит новой позиции как доля портфеля в деградированном режиме.",
    recommended: "0.05",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "risk_reduction_risk_multiplier",
    label: "Множитель риска",
    description: "Насколько агрессивно система может действовать в режиме снижения риска.",
    recommended: "0.25",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "risk_reduction_max_positions",
    label: "Максимум одновременно открытых позиций",
    description: "Сколько позиций разрешено держать одновременно в режиме снижения риска.",
    recommended: "20",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "risk_reduction_max_order_size",
    label: "Максимальный размер новой позиции",
    description: "Верхний лимит новой позиции как доля портфеля в режиме снижения риска.",
    recommended: "0.02",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "survival_risk_multiplier",
    label: "Множитель риска",
    description: "Насколько система сокращает риск в режиме выживания.",
    recommended: "0.10",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "survival_max_positions",
    label: "Максимум одновременно открытых позиций",
    description: "Сколько позиций можно держать в режиме выживания.",
    recommended: "0",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "survival_max_order_size",
    label: "Максимальный размер новой позиции",
    description: "Верхний лимит новой позиции как доля портфеля в режиме выживания.",
    recommended: "0.01",
    inputMode: "decimal",
    step: "0.01",
  },
];

const systemStatePolicyGroups: Array<{
  title: string;
  caption: string;
  description: string;
  keys: SystemStatePolicyFieldKey[];
}> = [
  {
    title: "Обычная торговля",
    caption: "TRADING",
    description: "Нормальный рабочий режим с полной торговой активностью и базовыми лимитами.",
    keys: ["trading_risk_multiplier", "trading_max_positions", "trading_max_order_size"],
  },
  {
    title: "Деградированный режим",
    caption: "DEGRADED",
    description: "Осторожный режим, когда рынок или инфраструктура уже потеряли часть качества.",
    keys: ["degraded_risk_multiplier", "degraded_max_positions", "degraded_max_order_size"],
  },
  {
    title: "Снижение риска",
    caption: "RISK_REDUCTION",
    description: "Режим принудительного ужатия новых действий и размера позиций.",
    keys: [
      "risk_reduction_risk_multiplier",
      "risk_reduction_max_positions",
      "risk_reduction_max_order_size",
    ],
  },
  {
    title: "Режим выживания",
    caption: "SURVIVAL",
    description: "Крайне консервативный режим для сохранения капитала и остановки расширения риска.",
    keys: ["survival_risk_multiplier", "survival_max_positions", "survival_max_order_size"],
  },
];

const systemStateTimeoutFieldDefinitions: Array<{
  key: SystemStateTimeoutFieldKey;
  label: string;
  description: string;
  recommended: string;
  inputMode: "decimal" | "numeric";
  step: string;
}> = [
  {
    key: "boot_max_seconds",
    label: "Максимальное время в состоянии",
    description: "Сколько система может находиться в состоянии загрузки до автоматического перехода в ошибку.",
    recommended: "60 сек",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "init_max_seconds",
    label: "Максимальное время в состоянии",
    description: "Сколько времени даётся на инициализацию компонентов до перехода в ошибку.",
    recommended: "120 сек",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "ready_max_seconds",
    label: "Максимальное время в состоянии",
    description: "Как долго система может оставаться в состоянии готовности без перехода дальше.",
    recommended: "3600 сек",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "degraded_max_seconds",
    label: "Максимальное время в состоянии",
    description: "Сколько система может оставаться в деградированном режиме до автоматического HALT.",
    recommended: "3600 сек",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "risk_reduction_max_seconds",
    label: "Максимальное время в состоянии",
    description: "Сколько система может оставаться в режиме снижения риска до автоматического HALT.",
    recommended: "1800 сек",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "survival_max_seconds",
    label: "Максимальное время в состоянии",
    description: "Сколько система может оставаться в режиме выживания до автоматического HALT.",
    recommended: "1800 сек",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "error_max_seconds",
    label: "Максимальное время в состоянии",
    description: "Сколько времени система может находиться в состоянии ошибки до аварийного перехода.",
    recommended: "300 сек",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "recovery_max_seconds",
    label: "Максимальное время в состоянии",
    description: "Сколько времени даётся на восстановление системы до аварийного перехода.",
    recommended: "600 сек",
    inputMode: "numeric",
    step: "1",
  },
];

const systemStateTimeoutGroups: Array<{
  title: string;
  caption: string;
  description: string;
  keys: SystemStateTimeoutFieldKey[];
}> = [
  {
    title: "Загрузка",
    caption: "BOOT",
    description: "Начальный запуск ядра и первичная подготовка системных компонентов.",
    keys: ["boot_max_seconds"],
  },
  {
    title: "Инициализация",
    caption: "INIT",
    description: "Поднятие сервисов, подписок и внутренних связей перед рабочим циклом.",
    keys: ["init_max_seconds"],
  },
  {
    title: "Готовность",
    caption: "READY",
    description: "Система готова к работе и удерживает нормальную рабочую готовность.",
    keys: ["ready_max_seconds"],
  },
  {
    title: "Деградированный режим",
    caption: "DEGRADED",
    description: "Работа продолжается, но уже с пониженным качеством среды или данных.",
    keys: ["degraded_max_seconds"],
  },
  {
    title: "Снижение риска",
    caption: "RISK_REDUCTION",
    description: "Переходный режим для принудительного сжатия новых действий и риска.",
    keys: ["risk_reduction_max_seconds"],
  },
  {
    title: "Режим выживания",
    caption: "SURVIVAL",
    description: "Кризисный режим сохранения капитала и минимизации новых воздействий.",
    keys: ["survival_max_seconds"],
  },
  {
    title: "Ошибка",
    caption: "ERROR",
    description: "Состояние сбоя, в котором система не должна зависать слишком долго.",
    keys: ["error_max_seconds"],
  },
  {
    title: "Восстановление",
    caption: "RECOVERY",
    description: "Окно на возврат к рабочему контуру после ошибки или деградации.",
    keys: ["recovery_max_seconds"],
  },
];

const reliabilityCircuitBreakerFieldDefinitions: Array<{
  key: ReliabilityPolicyFieldKey;
  label: string;
  description: string;
  recommended: string;
  inputMode: "decimal" | "numeric";
  step: string;
}> = [
  {
    key: "circuit_breaker_failure_threshold",
    label: "Сбоев подряд до открытия защиты",
    description: "После этого числа подряд идущих сбоев circuit breaker перестаёт пропускать вызовы.",
    recommended: "5",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "circuit_breaker_recovery_timeout_seconds",
    label: "Задержка до попытки восстановления",
    description: "Через сколько секунд circuit breaker пробует вернуться в half-open и проверить сервис.",
    recommended: "60 сек",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "circuit_breaker_success_threshold",
    label: "Успешных попыток для возврата в норму",
    description: "Сколько успешных вызовов нужно, чтобы закрыть circuit breaker после восстановления.",
    recommended: "3",
    inputMode: "numeric",
    step: "1",
  },
];

const reliabilityWatchdogFieldDefinitions: Array<{
  key: ReliabilityPolicyFieldKey;
  label: string;
  description: string;
  recommended: string;
  inputMode: "decimal" | "numeric";
  step: string;
}> = [
  {
    key: "watchdog_failure_threshold",
    label: "Сбоев подряд до фиксации проблемы",
    description: "После этого числа подряд watchdog начинает считать компонент проблемным и переходит к recovery path.",
    recommended: "3",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "watchdog_backoff_base_seconds",
    label: "Базовая задержка перед повтором",
    description: "Начальная пауза перед первой повторной попыткой восстановления.",
    recommended: "1.0 сек",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "watchdog_backoff_multiplier",
    label: "Множитель увеличения задержки",
    description: "Во сколько раз увеличивается пауза между повторными recovery-попытками.",
    recommended: "2.0",
    inputMode: "decimal",
    step: "0.1",
  },
  {
    key: "watchdog_max_backoff_seconds",
    label: "Максимальная задержка повтора",
    description: "Потолок ожидания между recovery-попытками, даже если backoff продолжает расти.",
    recommended: "60.0 сек",
    inputMode: "decimal",
    step: "0.5",
  },
  {
    key: "watchdog_jitter_factor",
    label: "Коэффициент jitter",
    description: "Добавляет контролируемый разброс к задержке, чтобы повторные попытки не шли синхронно.",
    recommended: "0.5",
    inputMode: "decimal",
    step: "0.05",
  },
  {
    key: "watchdog_check_interval_seconds",
    label: "Интервал проверки",
    description: "Как часто watchdog заново проверяет здоровье зарегистрированных компонентов.",
    recommended: "30.0 сек",
    inputMode: "decimal",
    step: "0.5",
  },
];

const healthPolicyFieldDefinitions: Array<{
  key: HealthPolicyFieldKey;
  label: string;
  description: string;
  recommended: string;
  inputMode: "decimal" | "numeric";
  step: string;
}> = [
  {
    key: "check_timeout_seconds",
    label: "Таймаут одной проверки здоровья",
    description: "Сколько времени даётся одной health-проверке компонента перед ошибкой по timeout.",
    recommended: "5.0 сек",
    inputMode: "decimal",
    step: "0.5",
  },
  {
    key: "background_check_interval_seconds",
    label: "Интервал фоновой проверки здоровья",
    description: "Как часто система автоматически запускает очередной цикл health-checks.",
    recommended: "60.0 сек",
    inputMode: "decimal",
    step: "1",
  },
  {
    key: "check_and_wait_timeout_seconds",
    label: "Максимальное ожидание общей проверки готовности",
    description: "Сколько времени helper проверки готовности ждёт общий healthy/ready результат перед ошибкой.",
    recommended: "30.0 сек",
    inputMode: "decimal",
    step: "0.5",
  },
];

const eventBusPolicyFieldDefinitions: Array<{
  key: EventBusPolicyFieldKey;
  label: string;
  description: string;
  recommended: string;
  inputMode: "decimal" | "numeric";
  step: string;
}> = [
  {
    key: "subscriber_capacity",
    label: "Базовая ёмкость очереди подписчика",
    description: "Сколько событий по умолчанию может накопить очередь одного подписчика до жёсткого давления на delivery path.",
    recommended: "1024",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "fill_ratio_low",
    label: "Нижний порог заполнения очереди",
    description: "На этом уровне заполнения шина начинает считать давление на очереди заметным для low-priority path.",
    recommended: "0.70",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "fill_ratio_normal",
    label: "Нормальный порог заполнения очереди",
    description: "Средний уровень давления, при котором шина событий может сильнее ограничивать поток публикаций.",
    recommended: "0.80",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "fill_ratio_high",
    label: "Высокий порог заполнения очереди",
    description: "Верхний уровень заполнения, после которого включаются самые жёсткие меры защиты от перегрузки.",
    recommended: "0.90",
    inputMode: "decimal",
    step: "0.01",
  },
  {
    key: "push_wait_timeout_seconds",
    label: "Таймаут ожидания при отправке события",
    description: "Сколько секунд publish path ждёт место в очереди перед отказом по timeout.",
    recommended: "5.0 сек",
    inputMode: "decimal",
    step: "0.5",
  },
  {
    key: "drain_timeout_seconds",
    label: "Таймаут ожидания при дренировании очередей",
    description: "Максимальное ожидание очистки очередей при controlled stop или drain операции.",
    recommended: "30.0 сек",
    inputMode: "decimal",
    step: "0.5",
  },
];

const manualApprovalPolicyFieldDefinitions: Array<{
  key: ManualApprovalPolicyFieldKey;
  label: string;
  description: string;
  recommended: string;
  inputMode: "decimal" | "numeric";
  step: string;
}> = [
  {
    key: "approval_timeout_minutes",
    label: "Время ожидания ручного подтверждения",
    description: "Сколько минут критическое действие ждёт ручного подтверждения второго оператора перед автоматическим истечением.",
    recommended: "5 мин",
    inputMode: "numeric",
    step: "1",
  },
];

const workflowTimeoutFieldDefinitions: Array<{
  key: WorkflowTimeoutFieldKey;
  label: string;
  description: string;
  recommended: string;
  inputMode: "decimal" | "numeric";
  step: string;
}> = [
  {
    key: "manager_max_age_seconds",
    label: "Максимальный срок жизни manager workflow",
    description: "Через сколько секунд manager workflow считается устаревшим и истекает.",
    recommended: "3600 сек",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "validation_max_age_seconds",
    label: "Максимальный срок жизни validation review",
    description: "Через сколько секунд validation review больше не считается актуальным.",
    recommended: "3600 сек",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "paper_max_age_seconds",
    label: "Максимальный срок жизни paper rehearsal",
    description: "Через сколько секунд paper rehearsal истекает в служебном контуре.",
    recommended: "3600 сек",
    inputMode: "numeric",
    step: "1",
  },
  {
    key: "replay_max_age_seconds",
    label: "Максимальный срок жизни replay / backtest сессии",
    description: "Через сколько секунд replay или backtest сессия считается протухшей.",
    recommended: "3600 сек",
    inputMode: "numeric",
    step: "1",
  },
];

function toDraft(values: UniversePolicySettingsResponse): UniversePolicyDraft {
  return {
    max_spread_bps: String(values.max_spread_bps),
    min_top_depth_usd: String(values.min_top_depth_usd),
    min_depth_5bps_usd: String(values.min_depth_5bps_usd),
    max_latency_ms: String(values.max_latency_ms),
    min_coverage_ratio: String(values.min_coverage_ratio),
    max_data_age_ms: String(values.max_data_age_ms),
    min_quality_score: String(values.min_quality_score),
    min_ready_instruments: String(values.min_ready_instruments),
    min_degraded_instruments_ratio: String(values.min_degraded_instruments_ratio),
    min_ready_confidence: String(values.min_ready_confidence),
    min_degraded_confidence: String(values.min_degraded_confidence),
  };
}

function toDecisionDraft(values: DecisionChainSettingsResponse): DecisionChainDraft {
  return {
    signal_min_trend_strength: String(values.signal_min_trend_strength),
    signal_min_regime_confidence: String(values.signal_min_regime_confidence),
    signal_target_risk_reward: String(values.signal_target_risk_reward),
    signal_max_age_seconds: String(values.signal_max_age_seconds),
    strategy_min_signal_confidence: String(values.strategy_min_signal_confidence),
    strategy_max_candidate_age_seconds: String(values.strategy_max_candidate_age_seconds),
    execution_min_strategy_confidence: String(values.execution_min_strategy_confidence),
    execution_max_intent_age_seconds: String(values.execution_max_intent_age_seconds),
    opportunity_min_confidence: String(values.opportunity_min_confidence),
    opportunity_min_priority: String(values.opportunity_min_priority),
    opportunity_max_age_seconds: String(values.opportunity_max_age_seconds),
    orchestration_min_confidence: String(values.orchestration_min_confidence),
    orchestration_min_priority: String(values.orchestration_min_priority),
    orchestration_max_decision_age_seconds: String(values.orchestration_max_decision_age_seconds),
  };
}

function toRiskDraft(values: RiskLimitsSettingsResponse): RiskLimitsDraft {
  return {
    base_r_percent: String(values.base_r_percent),
    max_r_per_trade: String(values.max_r_per_trade),
    max_portfolio_r: String(values.max_portfolio_r),
    risk_max_total_exposure_usd: String(values.risk_max_total_exposure_usd),
    max_position_size: String(values.max_position_size),
    risk_starting_equity: String(values.risk_starting_equity),
  };
}

function toTrailingDraft(values: TrailingPolicySettingsResponse): TrailingPolicyDraft {
  return {
    arm_at_pnl_r: String(values.arm_at_pnl_r),
    t2_at_pnl_r: String(values.t2_at_pnl_r),
    t3_at_pnl_r: String(values.t3_at_pnl_r),
    t4_at_pnl_r: String(values.t4_at_pnl_r),
    t1_atr_multiplier: String(values.t1_atr_multiplier),
    t2_atr_multiplier: String(values.t2_atr_multiplier),
    t3_atr_multiplier: String(values.t3_atr_multiplier),
    t4_atr_multiplier: String(values.t4_atr_multiplier),
    emergency_buffer_bps: String(values.emergency_buffer_bps),
    structural_min_adx: String(values.structural_min_adx),
    structural_confirmed_highs: String(values.structural_confirmed_highs),
    structural_confirmed_lows: String(values.structural_confirmed_lows),
  };
}

function toCorrelationDraft(values: CorrelationPolicySettingsResponse): CorrelationPolicyDraft {
  return {
    correlation_limit: String(values.correlation_limit),
    same_group_correlation: String(values.same_group_correlation),
    cross_group_correlation: String(values.cross_group_correlation),
  };
}

function toProtectionDraft(values: ProtectionPolicySettingsResponse): ProtectionPolicyDraft {
  return {
    halt_priority_threshold: String(values.halt_priority_threshold),
    freeze_priority_threshold: String(values.freeze_priority_threshold),
  };
}

function toFundingDraft(values: FundingPolicySettingsResponse): FundingPolicyDraft {
  return {
    min_arbitrage_spread: String(values.min_arbitrage_spread),
    min_annualized_spread: String(values.min_annualized_spread),
    max_acceptable_funding: String(values.max_acceptable_funding),
    min_exchange_improvement: String(values.min_exchange_improvement),
    min_quotes_for_opportunity: String(values.min_quotes_for_opportunity),
  };
}

function toSystemStatePolicyDraft(
  values: SystemStatePolicySettingsResponse,
): SystemStatePolicyDraft {
  return {
    trading_risk_multiplier: String(values.trading_risk_multiplier),
    trading_max_positions: String(values.trading_max_positions),
    trading_max_order_size: String(values.trading_max_order_size),
    degraded_risk_multiplier: String(values.degraded_risk_multiplier),
    degraded_max_positions: String(values.degraded_max_positions),
    degraded_max_order_size: String(values.degraded_max_order_size),
    risk_reduction_risk_multiplier: String(values.risk_reduction_risk_multiplier),
    risk_reduction_max_positions: String(values.risk_reduction_max_positions),
    risk_reduction_max_order_size: String(values.risk_reduction_max_order_size),
    survival_risk_multiplier: String(values.survival_risk_multiplier),
    survival_max_positions: String(values.survival_max_positions),
    survival_max_order_size: String(values.survival_max_order_size),
  };
}

function toSystemStateTimeoutDraft(
  values: SystemStateTimeoutSettingsResponse,
): SystemStateTimeoutDraft {
  return {
    boot_max_seconds: String(values.boot_max_seconds),
    init_max_seconds: String(values.init_max_seconds),
    ready_max_seconds: String(values.ready_max_seconds),
    risk_reduction_max_seconds: String(values.risk_reduction_max_seconds),
    degraded_max_seconds: String(values.degraded_max_seconds),
    survival_max_seconds: String(values.survival_max_seconds),
    error_max_seconds: String(values.error_max_seconds),
    recovery_max_seconds: String(values.recovery_max_seconds),
  };
}

function toReliabilityPolicyDraft(
  values: ReliabilityPolicySettingsResponse,
): ReliabilityPolicyDraft {
  return {
    circuit_breaker_failure_threshold: String(values.circuit_breaker_failure_threshold),
    circuit_breaker_recovery_timeout_seconds: String(
      values.circuit_breaker_recovery_timeout_seconds,
    ),
    circuit_breaker_success_threshold: String(values.circuit_breaker_success_threshold),
    watchdog_failure_threshold: String(values.watchdog_failure_threshold),
    watchdog_backoff_base_seconds: String(values.watchdog_backoff_base_seconds),
    watchdog_backoff_multiplier: String(values.watchdog_backoff_multiplier),
    watchdog_max_backoff_seconds: String(values.watchdog_max_backoff_seconds),
    watchdog_jitter_factor: String(values.watchdog_jitter_factor),
    watchdog_check_interval_seconds: String(values.watchdog_check_interval_seconds),
  };
}

function toHealthPolicyDraft(values: HealthPolicySettingsResponse): HealthPolicyDraft {
  return {
    check_timeout_seconds: String(values.check_timeout_seconds),
    background_check_interval_seconds: String(values.background_check_interval_seconds),
    check_and_wait_timeout_seconds: String(values.check_and_wait_timeout_seconds),
  };
}

function toEventBusPolicyDraft(values: EventBusPolicySettingsResponse): EventBusPolicyDraft {
  return {
    subscriber_capacity: String(values.subscriber_capacity),
    fill_ratio_low: String(values.fill_ratio_low),
    fill_ratio_normal: String(values.fill_ratio_normal),
    fill_ratio_high: String(values.fill_ratio_high),
    push_wait_timeout_seconds: String(values.push_wait_timeout_seconds),
    drain_timeout_seconds: String(values.drain_timeout_seconds),
  };
}

function toManualApprovalPolicyDraft(
  values: ManualApprovalPolicySettingsResponse,
): ManualApprovalPolicyDraft {
  return {
    approval_timeout_minutes: String(values.approval_timeout_minutes),
  };
}

function toWorkflowTimeoutDraft(values: WorkflowTimeoutsSettingsResponse): WorkflowTimeoutDraft {
  return {
    manager_max_age_seconds: String(values.manager_max_age_seconds),
    validation_max_age_seconds: String(values.validation_max_age_seconds),
    paper_max_age_seconds: String(values.paper_max_age_seconds),
    replay_max_age_seconds: String(values.replay_max_age_seconds),
  };
}

const settingsQueryBehavior = {
  retry: 1,
  refetchOnWindowFocus: true,
  refetchOnReconnect: true,
} as const;

const settingsSaveButtonLabel = "Сохранить настройки";

export function TerminalSettingsPage() {
  const widgets = useTerminalWidgetStore((state) => state.widgets);
  const setWidgetVisible = useTerminalWidgetStore((state) => state.setWidgetVisible);
  const queryClient = useQueryClient();
  const [universeDraft, setUniverseDraft] = useState<UniversePolicyDraft | null>(null);
  const [decisionDraft, setDecisionDraft] = useState<DecisionChainDraft | null>(null);
  const [riskDraft, setRiskDraft] = useState<RiskLimitsDraft | null>(null);
  const [trailingDraft, setTrailingDraft] = useState<TrailingPolicyDraft | null>(null);
  const [correlationDraft, setCorrelationDraft] = useState<CorrelationPolicyDraft | null>(null);
  const [protectionDraft, setProtectionDraft] = useState<ProtectionPolicyDraft | null>(null);
  const [fundingDraft, setFundingDraft] = useState<FundingPolicyDraft | null>(null);
  const [healthDraft, setHealthDraft] = useState<HealthPolicyDraft | null>(null);
  const [eventBusDraft, setEventBusDraft] = useState<EventBusPolicyDraft | null>(null);
  const [manualApprovalDraft, setManualApprovalDraft] = useState<ManualApprovalPolicyDraft | null>(
    null,
  );
  const [workflowTimeoutDraft, setWorkflowTimeoutDraft] = useState<WorkflowTimeoutDraft | null>(
    null,
  );
  const [reliabilityDraft, setReliabilityDraft] = useState<ReliabilityPolicyDraft | null>(null);
  const [systemStateDraft, setSystemStateDraft] = useState<SystemStatePolicyDraft | null>(null);
  const [systemStateTimeoutDraft, setSystemStateTimeoutDraft] =
    useState<SystemStateTimeoutDraft | null>(null);
  const [universeSaveNotice, setUniverseSaveNotice] = useState<string | null>(null);
  const [decisionSaveNotice, setDecisionSaveNotice] = useState<string | null>(null);
  const [riskSaveNotice, setRiskSaveNotice] = useState<string | null>(null);
  const [trailingSaveNotice, setTrailingSaveNotice] = useState<string | null>(null);
  const [correlationSaveNotice, setCorrelationSaveNotice] = useState<string | null>(null);
  const [protectionSaveNotice, setProtectionSaveNotice] = useState<string | null>(null);
  const [fundingSaveNotice, setFundingSaveNotice] = useState<string | null>(null);
  const [healthSaveNotice, setHealthSaveNotice] = useState<string | null>(null);
  const [eventBusSaveNotice, setEventBusSaveNotice] = useState<string | null>(null);
  const [manualApprovalSaveNotice, setManualApprovalSaveNotice] = useState<string | null>(null);
  const [workflowTimeoutSaveNotice, setWorkflowTimeoutSaveNotice] = useState<string | null>(null);
  const [reliabilitySaveNotice, setReliabilitySaveNotice] = useState<string | null>(null);
  const [systemStateSaveNotice, setSystemStateSaveNotice] = useState<string | null>(null);
  const [systemStateTimeoutSaveNotice, setSystemStateTimeoutSaveNotice] = useState<string | null>(
    null,
  );

  const universePolicyQuery = useQuery({
    ...settingsQueryBehavior,
    queryKey: ["dashboard", "settings", "universe-policy"],
    queryFn: getUniversePolicySettings,
  });
  const decisionChainQuery = useQuery({
    ...settingsQueryBehavior,
    queryKey: ["dashboard", "settings", "decision-thresholds"],
    queryFn: getDecisionChainSettings,
  });
  const riskLimitsQuery = useQuery({
    ...settingsQueryBehavior,
    queryKey: ["dashboard", "settings", "risk-limits"],
    queryFn: getRiskLimitsSettings,
  });
  const trailingPolicyQuery = useQuery({
    ...settingsQueryBehavior,
    queryKey: ["dashboard", "settings", "trailing-policy"],
    queryFn: getTrailingPolicySettings,
  });
  const correlationPolicyQuery = useQuery({
    ...settingsQueryBehavior,
    queryKey: ["dashboard", "settings", "correlation-policy"],
    queryFn: getCorrelationPolicySettings,
  });
  const protectionPolicyQuery = useQuery({
    ...settingsQueryBehavior,
    queryKey: ["dashboard", "settings", "protection-policy"],
    queryFn: getProtectionPolicySettings,
  });
  const fundingPolicyQuery = useQuery({
    ...settingsQueryBehavior,
    queryKey: ["dashboard", "settings", "funding-policy"],
    queryFn: getFundingPolicySettings,
  });
  const healthPolicyQuery = useQuery({
    ...settingsQueryBehavior,
    queryKey: ["dashboard", "settings", "health-policy"],
    queryFn: getHealthPolicySettings,
  });
  const eventBusPolicyQuery = useQuery({
    ...settingsQueryBehavior,
    queryKey: ["dashboard", "settings", "event-bus-policy"],
    queryFn: getEventBusPolicySettings,
  });
  const manualApprovalPolicyQuery = useQuery({
    ...settingsQueryBehavior,
    queryKey: ["dashboard", "settings", "manual-approval-policy"],
    queryFn: getManualApprovalPolicySettings,
  });
  const workflowTimeoutQuery = useQuery({
    ...settingsQueryBehavior,
    queryKey: ["dashboard", "settings", "workflow-timeouts"],
    queryFn: getWorkflowTimeoutSettings,
  });
  const liveFeedPolicyQuery = useQuery({
    ...settingsQueryBehavior,
    queryKey: ["dashboard", "settings", "live-feed-policy"],
    queryFn: getLiveFeedPolicySettings,
  });
  const reliabilityPolicyQuery = useQuery({
    ...settingsQueryBehavior,
    queryKey: ["dashboard", "settings", "reliability-policy"],
    queryFn: getReliabilityPolicySettings,
  });
  const systemStatePolicyQuery = useQuery({
    ...settingsQueryBehavior,
    queryKey: ["dashboard", "settings", "system-state-policy"],
    queryFn: getSystemStatePolicySettings,
  });
  const systemStateTimeoutQuery = useQuery({
    ...settingsQueryBehavior,
    queryKey: ["dashboard", "settings", "system-state-timeouts"],
    queryFn: getSystemStateTimeoutSettings,
  });

  useEffect(() => {
    if (universePolicyQuery.data) {
      setUniverseDraft(toDraft(universePolicyQuery.data));
    }
  }, [universePolicyQuery.data]);
  useEffect(() => {
    if (decisionChainQuery.data) {
      setDecisionDraft(toDecisionDraft(decisionChainQuery.data));
    }
  }, [decisionChainQuery.data]);
  useEffect(() => {
    if (riskLimitsQuery.data) {
      setRiskDraft(toRiskDraft(riskLimitsQuery.data));
    }
  }, [riskLimitsQuery.data]);
  useEffect(() => {
    if (trailingPolicyQuery.data) {
      setTrailingDraft(toTrailingDraft(trailingPolicyQuery.data));
    }
  }, [trailingPolicyQuery.data]);
  useEffect(() => {
    if (correlationPolicyQuery.data) {
      setCorrelationDraft(toCorrelationDraft(correlationPolicyQuery.data));
    }
  }, [correlationPolicyQuery.data]);
  useEffect(() => {
    if (protectionPolicyQuery.data) {
      setProtectionDraft(toProtectionDraft(protectionPolicyQuery.data));
    }
  }, [protectionPolicyQuery.data]);
  useEffect(() => {
    if (fundingPolicyQuery.data) {
      setFundingDraft(toFundingDraft(fundingPolicyQuery.data));
    }
  }, [fundingPolicyQuery.data]);
  useEffect(() => {
    if (healthPolicyQuery.data) {
      setHealthDraft(toHealthPolicyDraft(healthPolicyQuery.data));
    }
  }, [healthPolicyQuery.data]);
  useEffect(() => {
    if (eventBusPolicyQuery.data) {
      setEventBusDraft(toEventBusPolicyDraft(eventBusPolicyQuery.data));
    }
  }, [eventBusPolicyQuery.data]);
  useEffect(() => {
    if (manualApprovalPolicyQuery.data) {
      setManualApprovalDraft(toManualApprovalPolicyDraft(manualApprovalPolicyQuery.data));
    }
  }, [manualApprovalPolicyQuery.data]);
  useEffect(() => {
    if (workflowTimeoutQuery.data) {
      setWorkflowTimeoutDraft(toWorkflowTimeoutDraft(workflowTimeoutQuery.data));
    }
  }, [workflowTimeoutQuery.data]);
  useEffect(() => {
    if (reliabilityPolicyQuery.data) {
      setReliabilityDraft(toReliabilityPolicyDraft(reliabilityPolicyQuery.data));
    }
  }, [reliabilityPolicyQuery.data]);
  useEffect(() => {
    if (systemStatePolicyQuery.data) {
      setSystemStateDraft(toSystemStatePolicyDraft(systemStatePolicyQuery.data));
    }
  }, [systemStatePolicyQuery.data]);
  useEffect(() => {
    if (systemStateTimeoutQuery.data) {
      setSystemStateTimeoutDraft(toSystemStateTimeoutDraft(systemStateTimeoutQuery.data));
    }
  }, [systemStateTimeoutQuery.data]);

  const universePolicyMutation = useMutation({
    mutationFn: updateUniversePolicySettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "universe-policy"], data);
      setUniverseDraft(toDraft(data));
      setUniverseSaveNotice("Изменения сохранены");
    },
  });
  const decisionChainMutation = useMutation({
    mutationFn: updateDecisionChainSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "decision-thresholds"], data);
      setDecisionDraft(toDecisionDraft(data));
      setDecisionSaveNotice("Изменения сохранены");
    },
  });
  const riskLimitsMutation = useMutation({
    mutationFn: updateRiskLimitsSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "risk-limits"], data);
      setRiskDraft(toRiskDraft(data));
      setRiskSaveNotice("Изменения сохранены");
    },
  });
  const trailingPolicyMutation = useMutation({
    mutationFn: updateTrailingPolicySettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "trailing-policy"], data);
      setTrailingDraft(toTrailingDraft(data));
      setTrailingSaveNotice("Изменения сохранены");
    },
  });
  const correlationPolicyMutation = useMutation({
    mutationFn: updateCorrelationPolicySettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "correlation-policy"], data);
      setCorrelationDraft(toCorrelationDraft(data));
      setCorrelationSaveNotice("Изменения сохранены");
    },
  });
  const protectionPolicyMutation = useMutation({
    mutationFn: updateProtectionPolicySettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "protection-policy"], data);
      setProtectionDraft(toProtectionDraft(data));
      setProtectionSaveNotice("Изменения сохранены");
    },
  });
  const fundingPolicyMutation = useMutation({
    mutationFn: updateFundingPolicySettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "funding-policy"], data);
      setFundingDraft(toFundingDraft(data));
      setFundingSaveNotice("Изменения сохранены");
    },
  });
  const healthPolicyMutation = useMutation({
    mutationFn: updateHealthPolicySettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "health-policy"], data);
      setHealthDraft(toHealthPolicyDraft(data));
      setHealthSaveNotice("Изменения сохранены");
    },
  });
  const eventBusPolicyMutation = useMutation({
    mutationFn: updateEventBusPolicySettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "event-bus-policy"], data);
      setEventBusDraft(toEventBusPolicyDraft(data));
      setEventBusSaveNotice("Изменения сохранены");
    },
  });
  const manualApprovalPolicyMutation = useMutation({
    mutationFn: updateManualApprovalPolicySettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "manual-approval-policy"], data);
      setManualApprovalDraft(toManualApprovalPolicyDraft(data));
      setManualApprovalSaveNotice("Изменения сохранены");
    },
  });
  const workflowTimeoutMutation = useMutation({
    mutationFn: updateWorkflowTimeoutSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "workflow-timeouts"], data);
      setWorkflowTimeoutDraft(toWorkflowTimeoutDraft(data));
      setWorkflowTimeoutSaveNotice("Изменения сохранены");
    },
  });
  const reliabilityPolicyMutation = useMutation({
    mutationFn: updateReliabilityPolicySettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "reliability-policy"], data);
      setReliabilityDraft(toReliabilityPolicyDraft(data));
      setReliabilitySaveNotice("Изменения сохранены");
    },
  });
  const systemStatePolicyMutation = useMutation({
    mutationFn: updateSystemStatePolicySettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "system-state-policy"], data);
      setSystemStateDraft(toSystemStatePolicyDraft(data));
      setSystemStateSaveNotice("Изменения сохранены");
    },
  });
  const systemStateTimeoutMutation = useMutation({
    mutationFn: updateSystemStateTimeoutSettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "system-state-timeouts"], data);
      setSystemStateTimeoutDraft(toSystemStateTimeoutDraft(data));
      setSystemStateTimeoutSaveNotice("Изменения сохранены");
    },
  });

  const universePayload = useMemo<UniversePolicySettingsResponse | null>(() => {
    if (!universeDraft) {
      return null;
    }

    const maxDataAgeMs = Number.parseInt(universeDraft.max_data_age_ms, 10);
    const minReadyInstruments = Number.parseInt(universeDraft.min_ready_instruments, 10);
    const payload: UniversePolicySettingsResponse = {
      max_spread_bps: Number(universeDraft.max_spread_bps),
      min_top_depth_usd: Number(universeDraft.min_top_depth_usd),
      min_depth_5bps_usd: Number(universeDraft.min_depth_5bps_usd),
      max_latency_ms: Number(universeDraft.max_latency_ms),
      min_coverage_ratio: Number(universeDraft.min_coverage_ratio),
      max_data_age_ms: maxDataAgeMs,
      min_quality_score: Number(universeDraft.min_quality_score),
      min_ready_instruments: minReadyInstruments,
      min_degraded_instruments_ratio: Number(universeDraft.min_degraded_instruments_ratio),
      min_ready_confidence: Number(universeDraft.min_ready_confidence),
      min_degraded_confidence: Number(universeDraft.min_degraded_confidence),
    };

    const hasInvalidNumber = Object.values(payload).some((value) => Number.isNaN(value));
    return hasInvalidNumber ? null : payload;
  }, [universeDraft]);
  const decisionPayload = useMemo<DecisionChainSettingsResponse | null>(() => {
    if (!decisionDraft) {
      return null;
    }

    const signalMaxAgeSeconds = Number.parseInt(decisionDraft.signal_max_age_seconds, 10);
    const strategyMaxCandidateAgeSeconds = Number.parseInt(
      decisionDraft.strategy_max_candidate_age_seconds,
      10,
    );
    const executionMaxIntentAgeSeconds = Number.parseInt(
      decisionDraft.execution_max_intent_age_seconds,
      10,
    );
    const opportunityMaxAgeSeconds = Number.parseInt(
      decisionDraft.opportunity_max_age_seconds,
      10,
    );
    const orchestrationMaxDecisionAgeSeconds = Number.parseInt(
      decisionDraft.orchestration_max_decision_age_seconds,
      10,
    );

    const payload: DecisionChainSettingsResponse = {
      signal_min_trend_strength: Number(decisionDraft.signal_min_trend_strength),
      signal_min_regime_confidence: Number(decisionDraft.signal_min_regime_confidence),
      signal_target_risk_reward: Number(decisionDraft.signal_target_risk_reward),
      signal_max_age_seconds: signalMaxAgeSeconds,
      strategy_min_signal_confidence: Number(decisionDraft.strategy_min_signal_confidence),
      strategy_max_candidate_age_seconds: strategyMaxCandidateAgeSeconds,
      execution_min_strategy_confidence: Number(decisionDraft.execution_min_strategy_confidence),
      execution_max_intent_age_seconds: executionMaxIntentAgeSeconds,
      opportunity_min_confidence: Number(decisionDraft.opportunity_min_confidence),
      opportunity_min_priority: Number(decisionDraft.opportunity_min_priority),
      opportunity_max_age_seconds: opportunityMaxAgeSeconds,
      orchestration_min_confidence: Number(decisionDraft.orchestration_min_confidence),
      orchestration_min_priority: Number(decisionDraft.orchestration_min_priority),
      orchestration_max_decision_age_seconds: orchestrationMaxDecisionAgeSeconds,
    };

    const hasInvalidNumber = Object.values(payload).some((value) => Number.isNaN(value));
    return hasInvalidNumber ? null : payload;
  }, [decisionDraft]);
  const riskPayload = useMemo<RiskLimitsSettingsResponse | null>(() => {
    if (!riskDraft) {
      return null;
    }

    const payload: RiskLimitsSettingsResponse = {
      base_r_percent: Number(riskDraft.base_r_percent),
      max_r_per_trade: Number(riskDraft.max_r_per_trade),
      max_portfolio_r: Number(riskDraft.max_portfolio_r),
      risk_max_total_exposure_usd: Number(riskDraft.risk_max_total_exposure_usd),
      max_position_size: Number(riskDraft.max_position_size),
      risk_starting_equity: Number(riskDraft.risk_starting_equity),
    };

    const hasInvalidNumber = Object.values(payload).some((value) => Number.isNaN(value));
    return hasInvalidNumber ? null : payload;
  }, [riskDraft]);
  const trailingPayload = useMemo<TrailingPolicySettingsResponse | null>(() => {
    if (!trailingDraft) {
      return null;
    }

    const structuralConfirmedHighs = Number.parseInt(trailingDraft.structural_confirmed_highs, 10);
    const structuralConfirmedLows = Number.parseInt(trailingDraft.structural_confirmed_lows, 10);

    const payload: TrailingPolicySettingsResponse = {
      arm_at_pnl_r: Number(trailingDraft.arm_at_pnl_r),
      t2_at_pnl_r: Number(trailingDraft.t2_at_pnl_r),
      t3_at_pnl_r: Number(trailingDraft.t3_at_pnl_r),
      t4_at_pnl_r: Number(trailingDraft.t4_at_pnl_r),
      t1_atr_multiplier: Number(trailingDraft.t1_atr_multiplier),
      t2_atr_multiplier: Number(trailingDraft.t2_atr_multiplier),
      t3_atr_multiplier: Number(trailingDraft.t3_atr_multiplier),
      t4_atr_multiplier: Number(trailingDraft.t4_atr_multiplier),
      emergency_buffer_bps: Number(trailingDraft.emergency_buffer_bps),
      structural_min_adx: Number(trailingDraft.structural_min_adx),
      structural_confirmed_highs: structuralConfirmedHighs,
      structural_confirmed_lows: structuralConfirmedLows,
    };

    const hasInvalidNumber = Object.values(payload).some((value) => Number.isNaN(value));
    return hasInvalidNumber ? null : payload;
  }, [trailingDraft]);
  const correlationPayload = useMemo<CorrelationPolicySettingsResponse | null>(() => {
    if (!correlationDraft) {
      return null;
    }

    const payload: CorrelationPolicySettingsResponse = {
      correlation_limit: Number(correlationDraft.correlation_limit),
      same_group_correlation: Number(correlationDraft.same_group_correlation),
      cross_group_correlation: Number(correlationDraft.cross_group_correlation),
    };

    const hasInvalidNumber = Object.values(payload).some((value) => Number.isNaN(value));
    return hasInvalidNumber ? null : payload;
  }, [correlationDraft]);
  const protectionPayload = useMemo<ProtectionPolicySettingsResponse | null>(() => {
    if (!protectionDraft) {
      return null;
    }

    const payload: ProtectionPolicySettingsResponse = {
      halt_priority_threshold: Number(protectionDraft.halt_priority_threshold),
      freeze_priority_threshold: Number(protectionDraft.freeze_priority_threshold),
    };

    const hasInvalidNumber = Object.values(payload).some((value) => Number.isNaN(value));
    return hasInvalidNumber ? null : payload;
  }, [protectionDraft]);
  const fundingPayload = useMemo<FundingPolicySettingsResponse | null>(() => {
    if (!fundingDraft) {
      return null;
    }

    const minQuotesForOpportunity = Number.parseInt(fundingDraft.min_quotes_for_opportunity, 10);
    const payload: FundingPolicySettingsResponse = {
      min_arbitrage_spread: Number(fundingDraft.min_arbitrage_spread),
      min_annualized_spread: Number(fundingDraft.min_annualized_spread),
      max_acceptable_funding: Number(fundingDraft.max_acceptable_funding),
      min_exchange_improvement: Number(fundingDraft.min_exchange_improvement),
      min_quotes_for_opportunity: minQuotesForOpportunity,
    };

    const hasInvalidNumber = Object.values(payload).some((value) => Number.isNaN(value));
    return hasInvalidNumber ? null : payload;
  }, [fundingDraft]);
  const reliabilityPayload = useMemo<ReliabilityPolicySettingsResponse | null>(() => {
    if (!reliabilityDraft) {
      return null;
    }

    const payload: ReliabilityPolicySettingsResponse = {
      circuit_breaker_failure_threshold: Number.parseInt(
        reliabilityDraft.circuit_breaker_failure_threshold,
        10,
      ),
      circuit_breaker_recovery_timeout_seconds: Number.parseInt(
        reliabilityDraft.circuit_breaker_recovery_timeout_seconds,
        10,
      ),
      circuit_breaker_success_threshold: Number.parseInt(
        reliabilityDraft.circuit_breaker_success_threshold,
        10,
      ),
      watchdog_failure_threshold: Number.parseInt(reliabilityDraft.watchdog_failure_threshold, 10),
      watchdog_backoff_base_seconds: Number(reliabilityDraft.watchdog_backoff_base_seconds),
      watchdog_backoff_multiplier: Number(reliabilityDraft.watchdog_backoff_multiplier),
      watchdog_max_backoff_seconds: Number(reliabilityDraft.watchdog_max_backoff_seconds),
      watchdog_jitter_factor: Number(reliabilityDraft.watchdog_jitter_factor),
      watchdog_check_interval_seconds: Number(reliabilityDraft.watchdog_check_interval_seconds),
    };

    const hasInvalidNumber = Object.values(payload).some((value) => Number.isNaN(value));
    return hasInvalidNumber ? null : payload;
  }, [reliabilityDraft]);
  const healthPayload = useMemo<HealthPolicySettingsResponse | null>(() => {
    if (!healthDraft) {
      return null;
    }

    const payload: HealthPolicySettingsResponse = {
      check_timeout_seconds: Number(healthDraft.check_timeout_seconds),
      background_check_interval_seconds: Number(healthDraft.background_check_interval_seconds),
      check_and_wait_timeout_seconds: Number(healthDraft.check_and_wait_timeout_seconds),
    };

    const hasInvalidNumber = Object.values(payload).some((value) => Number.isNaN(value));
    return hasInvalidNumber ? null : payload;
  }, [healthDraft]);
  const eventBusPayload = useMemo<EventBusPolicySettingsResponse | null>(() => {
    if (!eventBusDraft) {
      return null;
    }

    const payload: EventBusPolicySettingsResponse = {
      subscriber_capacity: Number.parseInt(eventBusDraft.subscriber_capacity, 10),
      fill_ratio_low: Number(eventBusDraft.fill_ratio_low),
      fill_ratio_normal: Number(eventBusDraft.fill_ratio_normal),
      fill_ratio_high: Number(eventBusDraft.fill_ratio_high),
      push_wait_timeout_seconds: Number(eventBusDraft.push_wait_timeout_seconds),
      drain_timeout_seconds: Number(eventBusDraft.drain_timeout_seconds),
    };

    const hasInvalidNumber = Object.values(payload).some((value) => Number.isNaN(value));
    return hasInvalidNumber ? null : payload;
  }, [eventBusDraft]);
  const manualApprovalPayload = useMemo<ManualApprovalPolicySettingsResponse | null>(() => {
    if (!manualApprovalDraft) {
      return null;
    }

    const payload: ManualApprovalPolicySettingsResponse = {
      approval_timeout_minutes: Number.parseInt(manualApprovalDraft.approval_timeout_minutes, 10),
    };

    const hasInvalidNumber = Object.values(payload).some((value) => Number.isNaN(value));
    return hasInvalidNumber ? null : payload;
  }, [manualApprovalDraft]);
  const workflowTimeoutPayload = useMemo<WorkflowTimeoutsSettingsResponse | null>(() => {
    if (!workflowTimeoutDraft) {
      return null;
    }

    const payload: WorkflowTimeoutsSettingsResponse = {
      manager_max_age_seconds: Number.parseInt(workflowTimeoutDraft.manager_max_age_seconds, 10),
      validation_max_age_seconds: Number.parseInt(
        workflowTimeoutDraft.validation_max_age_seconds,
        10,
      ),
      paper_max_age_seconds: Number.parseInt(workflowTimeoutDraft.paper_max_age_seconds, 10),
      replay_max_age_seconds: Number.parseInt(workflowTimeoutDraft.replay_max_age_seconds, 10),
    };

    const hasInvalidNumber = Object.values(payload).some((value) => Number.isNaN(value));
    return hasInvalidNumber ? null : payload;
  }, [workflowTimeoutDraft]);
  const systemStatePayload = useMemo<SystemStatePolicySettingsResponse | null>(() => {
    if (!systemStateDraft) {
      return null;
    }

    const tradingMaxPositions = Number.parseInt(systemStateDraft.trading_max_positions, 10);
    const degradedMaxPositions = Number.parseInt(systemStateDraft.degraded_max_positions, 10);
    const riskReductionMaxPositions = Number.parseInt(
      systemStateDraft.risk_reduction_max_positions,
      10,
    );
    const survivalMaxPositions = Number.parseInt(systemStateDraft.survival_max_positions, 10);
    const payload: SystemStatePolicySettingsResponse = {
      trading_risk_multiplier: Number(systemStateDraft.trading_risk_multiplier),
      trading_max_positions: tradingMaxPositions,
      trading_max_order_size: Number(systemStateDraft.trading_max_order_size),
      degraded_risk_multiplier: Number(systemStateDraft.degraded_risk_multiplier),
      degraded_max_positions: degradedMaxPositions,
      degraded_max_order_size: Number(systemStateDraft.degraded_max_order_size),
      risk_reduction_risk_multiplier: Number(systemStateDraft.risk_reduction_risk_multiplier),
      risk_reduction_max_positions: riskReductionMaxPositions,
      risk_reduction_max_order_size: Number(systemStateDraft.risk_reduction_max_order_size),
      survival_risk_multiplier: Number(systemStateDraft.survival_risk_multiplier),
      survival_max_positions: survivalMaxPositions,
      survival_max_order_size: Number(systemStateDraft.survival_max_order_size),
    };

    const hasInvalidNumber = Object.values(payload).some((value) => Number.isNaN(value));
    return hasInvalidNumber ? null : payload;
  }, [systemStateDraft]);
  const systemStateTimeoutPayload = useMemo<SystemStateTimeoutSettingsResponse | null>(() => {
    if (!systemStateTimeoutDraft) {
      return null;
    }

    const payload: SystemStateTimeoutSettingsResponse = {
      boot_max_seconds: Number.parseInt(systemStateTimeoutDraft.boot_max_seconds, 10),
      init_max_seconds: Number.parseInt(systemStateTimeoutDraft.init_max_seconds, 10),
      ready_max_seconds: Number.parseInt(systemStateTimeoutDraft.ready_max_seconds, 10),
      risk_reduction_max_seconds: Number.parseInt(
        systemStateTimeoutDraft.risk_reduction_max_seconds,
        10,
      ),
      degraded_max_seconds: Number.parseInt(systemStateTimeoutDraft.degraded_max_seconds, 10),
      survival_max_seconds: Number.parseInt(systemStateTimeoutDraft.survival_max_seconds, 10),
      error_max_seconds: Number.parseInt(systemStateTimeoutDraft.error_max_seconds, 10),
      recovery_max_seconds: Number.parseInt(systemStateTimeoutDraft.recovery_max_seconds, 10),
    };

    const hasInvalidNumber = Object.values(payload).some((value) => Number.isNaN(value));
    return hasInvalidNumber ? null : payload;
  }, [systemStateTimeoutDraft]);

  const isUniverseDirty =
    !!universePolicyQuery.data &&
    !!universeDraft &&
    JSON.stringify(toDraft(universePolicyQuery.data)) !== JSON.stringify(universeDraft);
  const isDecisionDirty =
    !!decisionChainQuery.data &&
    !!decisionDraft &&
    JSON.stringify(toDecisionDraft(decisionChainQuery.data)) !== JSON.stringify(decisionDraft);
  const isRiskDirty =
    !!riskLimitsQuery.data &&
    !!riskDraft &&
    JSON.stringify(toRiskDraft(riskLimitsQuery.data)) !== JSON.stringify(riskDraft);
  const isTrailingDirty =
    !!trailingPolicyQuery.data &&
    !!trailingDraft &&
    JSON.stringify(toTrailingDraft(trailingPolicyQuery.data)) !== JSON.stringify(trailingDraft);
  const isCorrelationDirty =
    !!correlationPolicyQuery.data &&
    !!correlationDraft &&
    JSON.stringify(toCorrelationDraft(correlationPolicyQuery.data)) !==
      JSON.stringify(correlationDraft);
  const isProtectionDirty =
    !!protectionPolicyQuery.data &&
    !!protectionDraft &&
    JSON.stringify(toProtectionDraft(protectionPolicyQuery.data)) !==
      JSON.stringify(protectionDraft);
  const isFundingDirty =
    !!fundingPolicyQuery.data &&
    !!fundingDraft &&
    JSON.stringify(toFundingDraft(fundingPolicyQuery.data)) !== JSON.stringify(fundingDraft);
  const isHealthDirty =
    !!healthPolicyQuery.data &&
    !!healthDraft &&
    JSON.stringify(toHealthPolicyDraft(healthPolicyQuery.data)) !== JSON.stringify(healthDraft);
  const isEventBusDirty =
    !!eventBusPolicyQuery.data &&
    !!eventBusDraft &&
    JSON.stringify(toEventBusPolicyDraft(eventBusPolicyQuery.data)) !==
      JSON.stringify(eventBusDraft);
  const isManualApprovalDirty =
    !!manualApprovalPolicyQuery.data &&
    !!manualApprovalDraft &&
    JSON.stringify(toManualApprovalPolicyDraft(manualApprovalPolicyQuery.data)) !==
      JSON.stringify(manualApprovalDraft);
  const isWorkflowTimeoutDirty =
    !!workflowTimeoutQuery.data &&
    !!workflowTimeoutDraft &&
    JSON.stringify(toWorkflowTimeoutDraft(workflowTimeoutQuery.data)) !==
      JSON.stringify(workflowTimeoutDraft);
  const isReliabilityDirty =
    !!reliabilityPolicyQuery.data &&
    !!reliabilityDraft &&
    JSON.stringify(toReliabilityPolicyDraft(reliabilityPolicyQuery.data)) !==
      JSON.stringify(reliabilityDraft);
  const isSystemStateDirty =
    !!systemStatePolicyQuery.data &&
    !!systemStateDraft &&
    JSON.stringify(toSystemStatePolicyDraft(systemStatePolicyQuery.data)) !==
      JSON.stringify(systemStateDraft);
  const isSystemStateTimeoutDirty =
    !!systemStateTimeoutQuery.data &&
    !!systemStateTimeoutDraft &&
    JSON.stringify(toSystemStateTimeoutDraft(systemStateTimeoutQuery.data)) !==
      JSON.stringify(systemStateTimeoutDraft);

  const universeStatusTone =
    universePolicyQuery.isLoading || universePolicyMutation.isPending
      ? "warning"
      : universePolicyQuery.isError || universePolicyMutation.isError
        ? "danger"
        : universeSaveNotice
          ? "success"
          : "neutral";
  const decisionStatusTone =
    decisionChainQuery.isLoading || decisionChainMutation.isPending
      ? "warning"
      : decisionChainQuery.isError || decisionChainMutation.isError
        ? "danger"
        : decisionSaveNotice
          ? "success"
          : "neutral";
  const riskStatusTone =
    riskLimitsQuery.isLoading || riskLimitsMutation.isPending
      ? "warning"
      : riskLimitsQuery.isError || riskLimitsMutation.isError
        ? "danger"
        : riskSaveNotice
          ? "success"
          : "neutral";
  const trailingStatusTone =
    trailingPolicyQuery.isLoading || trailingPolicyMutation.isPending
      ? "warning"
      : trailingPolicyQuery.isError || trailingPolicyMutation.isError
        ? "danger"
        : trailingSaveNotice
          ? "success"
          : "neutral";
  const correlationStatusTone =
    correlationPolicyQuery.isLoading || correlationPolicyMutation.isPending
      ? "warning"
      : correlationPolicyQuery.isError || correlationPolicyMutation.isError
        ? "danger"
        : correlationSaveNotice
          ? "success"
          : "neutral";
  const protectionStatusTone =
    protectionPolicyQuery.isLoading || protectionPolicyMutation.isPending
      ? "warning"
      : protectionPolicyQuery.isError || protectionPolicyMutation.isError
        ? "danger"
        : protectionSaveNotice
          ? "success"
          : "neutral";
  const fundingStatusTone =
    fundingPolicyQuery.isLoading || fundingPolicyMutation.isPending
      ? "warning"
      : fundingPolicyQuery.isError || fundingPolicyMutation.isError
        ? "danger"
        : fundingSaveNotice
          ? "success"
          : "neutral";
  const healthStatusTone =
    healthPolicyQuery.isLoading || healthPolicyMutation.isPending
      ? "warning"
      : healthPolicyQuery.isError || healthPolicyMutation.isError
        ? "danger"
        : healthSaveNotice
          ? "success"
          : "neutral";
  const eventBusStatusTone =
    eventBusPolicyQuery.isLoading || eventBusPolicyMutation.isPending
      ? "warning"
      : eventBusPolicyQuery.isError || eventBusPolicyMutation.isError
        ? "danger"
        : eventBusSaveNotice
          ? "success"
          : "neutral";
  const manualApprovalStatusTone =
    manualApprovalPolicyQuery.isLoading || manualApprovalPolicyMutation.isPending
      ? "warning"
      : manualApprovalPolicyQuery.isError || manualApprovalPolicyMutation.isError
        ? "danger"
        : manualApprovalSaveNotice
          ? "success"
          : "neutral";
  const workflowTimeoutStatusTone =
    workflowTimeoutQuery.isLoading || workflowTimeoutMutation.isPending
      ? "warning"
      : workflowTimeoutQuery.isError || workflowTimeoutMutation.isError
        ? "danger"
        : workflowTimeoutSaveNotice
          ? "success"
          : "neutral";
  const reliabilityStatusTone =
    reliabilityPolicyQuery.isLoading || reliabilityPolicyMutation.isPending
      ? "warning"
      : reliabilityPolicyQuery.isError || reliabilityPolicyMutation.isError
        ? "danger"
        : reliabilitySaveNotice
          ? "success"
          : "neutral";
  const systemStateStatusTone =
    systemStatePolicyQuery.isLoading || systemStatePolicyMutation.isPending
      ? "warning"
      : systemStatePolicyQuery.isError || systemStatePolicyMutation.isError
        ? "danger"
        : systemStateSaveNotice
          ? "success"
          : "neutral";
  const systemStateTimeoutStatusTone =
    systemStateTimeoutQuery.isLoading || systemStateTimeoutMutation.isPending
      ? "warning"
      : systemStateTimeoutQuery.isError || systemStateTimeoutMutation.isError
        ? "danger"
        : systemStateTimeoutSaveNotice
          ? "success"
          : "neutral";

  const universeStatusLabel = universePolicyQuery.isLoading
    ? "Загрузка"
    : universePolicyMutation.isPending
      ? "Сохранение"
      : universePolicyQuery.isError
        ? "Ошибка загрузки"
        : universePolicyMutation.isError
          ? "Ошибка сохранения"
          : universeSaveNotice
            ? "Сохранено"
            : "Backend";
  const decisionStatusLabel = decisionChainQuery.isLoading
    ? "Загрузка"
    : decisionChainMutation.isPending
      ? "Сохранение"
      : decisionChainQuery.isError
        ? "Ошибка загрузки"
        : decisionChainMutation.isError
          ? "Ошибка сохранения"
          : decisionSaveNotice
            ? "Сохранено"
            : "Backend";
  const riskStatusLabel = riskLimitsQuery.isLoading
    ? "Загрузка"
    : riskLimitsMutation.isPending
      ? "Сохранение"
      : riskLimitsQuery.isError
        ? "Ошибка загрузки"
        : riskLimitsMutation.isError
          ? "Ошибка сохранения"
          : riskSaveNotice
            ? "Сохранено"
            : "Backend";
  const trailingStatusLabel = trailingPolicyQuery.isLoading
    ? "Загрузка"
    : trailingPolicyMutation.isPending
      ? "Сохранение"
      : trailingPolicyQuery.isError
        ? "Ошибка загрузки"
        : trailingPolicyMutation.isError
          ? "Ошибка сохранения"
          : trailingSaveNotice
            ? "Сохранено"
            : "Backend";
  const correlationStatusLabel = correlationPolicyQuery.isLoading
    ? "Загрузка"
    : correlationPolicyMutation.isPending
      ? "Сохранение"
      : correlationPolicyQuery.isError
        ? "Ошибка загрузки"
        : correlationPolicyMutation.isError
          ? "Ошибка сохранения"
          : correlationSaveNotice
            ? "Сохранено"
            : "Backend";
  const protectionStatusLabel = protectionPolicyQuery.isLoading
    ? "Загрузка"
    : protectionPolicyMutation.isPending
      ? "Сохранение"
      : protectionPolicyQuery.isError
        ? "Ошибка загрузки"
        : protectionPolicyMutation.isError
          ? "Ошибка сохранения"
          : protectionSaveNotice
            ? "Сохранено"
            : "Backend";
  const fundingStatusLabel = fundingPolicyQuery.isLoading
    ? "Загрузка"
    : fundingPolicyMutation.isPending
      ? "Сохранение"
      : fundingPolicyQuery.isError
        ? "Ошибка загрузки"
        : fundingPolicyMutation.isError
          ? "Ошибка сохранения"
          : fundingSaveNotice
            ? "Сохранено"
            : "Backend";
  const healthStatusLabel = healthPolicyQuery.isLoading
    ? "Загрузка"
    : healthPolicyMutation.isPending
      ? "Сохранение"
      : healthPolicyQuery.isError
        ? "Ошибка загрузки"
        : healthPolicyMutation.isError
          ? "Ошибка сохранения"
          : healthSaveNotice
            ? "Сохранено"
            : "Backend";
  const eventBusStatusLabel = eventBusPolicyQuery.isLoading
    ? "Загрузка"
    : eventBusPolicyMutation.isPending
      ? "Сохранение"
      : eventBusPolicyQuery.isError
        ? "Ошибка загрузки"
        : eventBusPolicyMutation.isError
          ? "Ошибка сохранения"
          : eventBusSaveNotice
            ? "Сохранено"
            : "Backend";
  const manualApprovalStatusLabel = manualApprovalPolicyQuery.isLoading
    ? "Загрузка"
    : manualApprovalPolicyMutation.isPending
      ? "Сохранение"
      : manualApprovalPolicyQuery.isError
        ? "Ошибка загрузки"
        : manualApprovalPolicyMutation.isError
          ? "Ошибка сохранения"
          : manualApprovalSaveNotice
            ? "Сохранено"
            : "Backend";
  const workflowTimeoutStatusLabel = workflowTimeoutQuery.isLoading
    ? "Загрузка"
    : workflowTimeoutMutation.isPending
      ? "Сохранение"
      : workflowTimeoutQuery.isError
        ? "Ошибка загрузки"
        : workflowTimeoutMutation.isError
          ? "Ошибка сохранения"
          : workflowTimeoutSaveNotice
            ? "Сохранено"
            : "Backend";
  const reliabilityStatusLabel = reliabilityPolicyQuery.isLoading
    ? "Загрузка"
    : reliabilityPolicyMutation.isPending
      ? "Сохранение"
      : reliabilityPolicyQuery.isError
        ? "Ошибка загрузки"
        : reliabilityPolicyMutation.isError
          ? "Ошибка сохранения"
          : reliabilitySaveNotice
            ? "Сохранено"
            : "Backend";
  const systemStateStatusLabel = systemStatePolicyQuery.isLoading
    ? "Загрузка"
    : systemStatePolicyMutation.isPending
      ? "Сохранение"
      : systemStatePolicyQuery.isError
        ? "Ошибка загрузки"
        : systemStatePolicyMutation.isError
          ? "Ошибка сохранения"
          : systemStateSaveNotice
          ? "Сохранено"
            : "Backend";
  const systemStateTimeoutStatusLabel = systemStateTimeoutQuery.isLoading
    ? "Загрузка"
    : systemStateTimeoutMutation.isPending
      ? "Сохранение"
      : systemStateTimeoutQuery.isError
        ? "Ошибка загрузки"
        : systemStateTimeoutMutation.isError
          ? "Ошибка сохранения"
          : systemStateTimeoutSaveNotice
            ? "Сохранено"
            : "Backend";

  function updateDraftField(key: UniversePolicyFieldKey, value: string) {
    setUniverseSaveNotice(null);
    setUniverseDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]: value,
      };
    });
  }
  function updateDecisionDraftField(key: DecisionChainFieldKey, value: string) {
    setDecisionSaveNotice(null);
    setDecisionDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]: value,
      };
    });
  }
  function updateRiskDraftField(key: RiskLimitsFieldKey, value: string) {
    setRiskSaveNotice(null);
    setRiskDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]: value,
      };
    });
  }
  function updateTrailingDraftField(key: TrailingPolicyFieldKey, value: string) {
    setTrailingSaveNotice(null);
    setTrailingDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]: value,
      };
    });
  }
  function updateCorrelationDraftField(key: CorrelationPolicyFieldKey, value: string) {
    setCorrelationSaveNotice(null);
    setCorrelationDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]: value,
      };
    });
  }
  function updateProtectionDraftField(key: ProtectionPolicyFieldKey, value: string) {
    setProtectionSaveNotice(null);
    setProtectionDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]: value,
      };
    });
  }
  function updateFundingDraftField(key: FundingPolicyFieldKey, value: string) {
    setFundingSaveNotice(null);
    setFundingDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]: value,
      };
    });
  }
  function updateSystemStateDraftField(key: SystemStatePolicyFieldKey, value: string) {
    setSystemStateSaveNotice(null);
    setSystemStateDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]: value,
      };
    });
  }
  function updateSystemStateTimeoutDraftField(key: SystemStateTimeoutFieldKey, value: string) {
    setSystemStateTimeoutSaveNotice(null);
    setSystemStateTimeoutDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]: value,
      };
    });
  }
  function updateReliabilityDraftField(key: ReliabilityPolicyFieldKey, value: string) {
    setReliabilitySaveNotice(null);
    setReliabilityDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]: value,
      };
    });
  }
  function updateHealthDraftField(key: HealthPolicyFieldKey, value: string) {
    setHealthSaveNotice(null);
    setHealthDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]: value,
      };
    });
  }
  function updateEventBusDraftField(key: EventBusPolicyFieldKey, value: string) {
    setEventBusSaveNotice(null);
    setEventBusDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]: value,
      };
    });
  }
  function updateManualApprovalDraftField(key: ManualApprovalPolicyFieldKey, value: string) {
    setManualApprovalSaveNotice(null);
    setManualApprovalDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]: value,
      };
    });
  }
  function updateWorkflowTimeoutDraftField(key: WorkflowTimeoutFieldKey, value: string) {
    setWorkflowTimeoutSaveNotice(null);
    setWorkflowTimeoutDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]: value,
      };
    });
  }
  async function handleUniversePolicySave() {
    if (!universePayload) {
      return;
    }
    await universePolicyMutation.mutateAsync(universePayload);
  }
  async function handleDecisionChainSave() {
    if (!decisionPayload) {
      return;
    }
    await decisionChainMutation.mutateAsync(decisionPayload);
  }
  async function handleRiskLimitsSave() {
    if (!riskPayload) {
      return;
    }
    await riskLimitsMutation.mutateAsync(riskPayload);
  }
  async function handleTrailingPolicySave() {
    if (!trailingPayload) {
      return;
    }
    await trailingPolicyMutation.mutateAsync(trailingPayload);
  }
  async function handleCorrelationPolicySave() {
    if (!correlationPayload) {
      return;
    }
    await correlationPolicyMutation.mutateAsync(correlationPayload);
  }
  async function handleProtectionPolicySave() {
    if (!protectionPayload) {
      return;
    }
    await protectionPolicyMutation.mutateAsync(protectionPayload);
  }
  async function handleFundingPolicySave() {
    if (!fundingPayload) {
      return;
    }
    await fundingPolicyMutation.mutateAsync(fundingPayload);
  }
  async function handleSystemStatePolicySave() {
    if (!systemStatePayload) {
      return;
    }
    await systemStatePolicyMutation.mutateAsync(systemStatePayload);
  }
  async function handleSystemStateTimeoutSave() {
    if (!systemStateTimeoutPayload) {
      return;
    }
    await systemStateTimeoutMutation.mutateAsync(systemStateTimeoutPayload);
  }
  async function handleReliabilityPolicySave() {
    if (!reliabilityPayload) {
      return;
    }
    await reliabilityPolicyMutation.mutateAsync(reliabilityPayload);
  }
  async function handleHealthPolicySave() {
    if (!healthPayload) {
      return;
    }
    await healthPolicyMutation.mutateAsync(healthPayload);
  }
  async function handleEventBusPolicySave() {
    if (!eventBusPayload) {
      return;
    }
    await eventBusPolicyMutation.mutateAsync(eventBusPayload);
  }
  async function handleManualApprovalPolicySave() {
    if (!manualApprovalPayload) {
      return;
    }
    await manualApprovalPolicyMutation.mutateAsync(manualApprovalPayload);
  }
  async function handleWorkflowTimeoutSave() {
    if (!workflowTimeoutPayload) {
      return;
    }
    await workflowTimeoutMutation.mutateAsync(workflowTimeoutPayload);
  }
  return (
    <div className={pageRoot}>
      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Ручной контроль</div>
            <h2 className={sectionTitle}>Ручное подтверждение действий</h2>
          </div>
          <TerminalBadge tone={manualApprovalStatusTone}>{manualApprovalStatusLabel}</TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={localStateNote}>
            Эти параметры читаются из backend-настроек ручного подтверждения и сохраняются
            обратно в canonical runtime settings path.
          </div>

          {manualApprovalPolicyQuery.isLoading ? (
            <div className={settingsErrorState}>
              Загружаю настройки ручного подтверждения действий...
            </div>
          ) : null}

          {manualApprovalPolicyQuery.isError ? (
            <div className={settingsErrorState}>
              Не удалось загрузить настройки ручного подтверждения действий.
            </div>
          ) : null}

          {manualApprovalPolicyMutation.isError ? (
            <div className={settingsErrorState}>
              Не удалось сохранить изменения. Проверь значения и повтори сохранение.
            </div>
          ) : null}

          {manualApprovalDraft ? (
            <div className={settingsForm}>
              <div className={settingsFieldGrid}>
                {manualApprovalPolicyFieldDefinitions.map((field) => (
                  <div key={field.key} className={settingsFieldCard}>
                    <div className={settingsFieldHeader}>
                      <div className={fieldLabel}>{field.label}</div>
                      <div className={settingsFieldMeta}>Рекомендация: {field.recommended}</div>
                    </div>
                    <div className={fieldDescription}>{field.description}</div>
                    <input
                      type="number"
                      inputMode={field.inputMode}
                      step={field.step}
                      className={fieldInput}
                      value={manualApprovalDraft[field.key]}
                      onChange={(event) =>
                        updateManualApprovalDraftField(field.key, event.target.value)
                      }
                    />
                  </div>
                ))}
              </div>

              <div className={modeControls}>
                <button
                  type="button"
                  className={`${modeButton} ${!isManualApprovalDirty || !manualApprovalPayload || manualApprovalPolicyMutation.isPending ? saveButtonDisabled : saveButton}`}
                  disabled={
                    !isManualApprovalDirty ||
                    !manualApprovalPayload ||
                    manualApprovalPolicyMutation.isPending
                  }
                  onClick={() => void handleManualApprovalPolicySave()}
                >
                  {manualApprovalPolicyMutation.isPending ? "Сохраняю..." : settingsSaveButtonLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Служебные контуры</div>
            <h2 className={sectionTitle}>Сроки жизни workflow и проверок</h2>
          </div>
          <TerminalBadge tone={workflowTimeoutStatusTone}>{workflowTimeoutStatusLabel}</TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={localStateNote}>
            Эти параметры читаются из backend-настроек сроков жизни workflow и сохраняются
            обратно в canonical runtime settings path.
          </div>

          {workflowTimeoutQuery.isLoading ? (
            <div className={settingsErrorState}>
              Загружаю сроки жизни workflow и служебных контуров...
            </div>
          ) : null}

          {workflowTimeoutQuery.isError ? (
            <div className={settingsErrorState}>
              Не удалось загрузить сроки жизни workflow и служебных контуров.
            </div>
          ) : null}

          {workflowTimeoutMutation.isError ? (
            <div className={settingsErrorState}>
              Не удалось сохранить изменения. Проверь значения и повтори сохранение.
            </div>
          ) : null}

          {workflowTimeoutDraft ? (
            <div className={settingsForm}>
              <div className={settingsFieldGrid}>
                {workflowTimeoutFieldDefinitions.map((field) => (
                  <div key={field.key} className={settingsFieldCard}>
                    <div className={settingsFieldHeader}>
                      <div className={fieldLabel}>{field.label}</div>
                      <div className={settingsFieldMeta}>Рекомендация: {field.recommended}</div>
                    </div>
                    <div className={fieldDescription}>{field.description}</div>
                    <input
                      type="number"
                      inputMode={field.inputMode}
                      step={field.step}
                      className={fieldInput}
                      value={workflowTimeoutDraft[field.key]}
                      onChange={(event) =>
                        updateWorkflowTimeoutDraftField(field.key, event.target.value)
                      }
                    />
                  </div>
                ))}
              </div>

              <div className={modeControls}>
                <button
                  type="button"
                  className={`${modeButton} ${!isWorkflowTimeoutDirty || !workflowTimeoutPayload || workflowTimeoutMutation.isPending ? saveButtonDisabled : saveButton}`}
                  disabled={
                    !isWorkflowTimeoutDirty ||
                    !workflowTimeoutPayload ||
                    workflowTimeoutMutation.isPending
                  }
                  onClick={() => void handleWorkflowTimeoutSave()}
                >
                  {workflowTimeoutMutation.isPending ? "Сохраняю..." : settingsSaveButtonLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Рынок</div>
            <h2 className={sectionTitle}>Фильтр рынка и допуск инструментов</h2>
          </div>
          <TerminalBadge tone={universeStatusTone}>{universeStatusLabel}</TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={localStateNote}>
            Эти параметры читаются из backend-настроек фильтра рынка и сохраняются обратно в
            canonical runtime settings path.
          </div>

          {universePolicyQuery.isLoading ? (
            <div className={settingsErrorState}>Загружаю текущие пороги фильтра рынка...</div>
          ) : null}

          {universePolicyQuery.isError ? (
            <div className={settingsErrorState}>
              Не удалось загрузить настройки фильтра рынка.
            </div>
          ) : null}

          {universePolicyMutation.isError ? (
            <div className={settingsErrorState}>
              Не удалось сохранить изменения. Проверь значения и повтори сохранение.
            </div>
          ) : null}

          {universeDraft ? (
            <div className={settingsForm}>
              <div className={settingsFieldGrid}>
                {universePolicyFieldDefinitions.map((field) => (
                  <label key={field.key} className={settingsFieldCard}>
                    <div className={settingsFieldHeader}>
                      <span className={fieldLabel}>{field.label}</span>
                      <span className={settingsFieldMeta}>Рекомендация: {field.recommended}</span>
                    </div>
                    <div className={fieldDescription}>{field.description}</div>
                    <input
                      type="number"
                      inputMode={field.inputMode}
                      step={field.step}
                      className={fieldInput}
                      value={universeDraft[field.key]}
                      onChange={(event) => updateDraftField(field.key, event.target.value)}
                    />
                  </label>
                ))}
              </div>

              <div className={modeControls}>
                <button
                  type="button"
                  className={`${modeButton} ${!isUniverseDirty || !universePayload || universePolicyMutation.isPending ? saveButtonDisabled : saveButton}`}
                  disabled={!isUniverseDirty || !universePayload || universePolicyMutation.isPending}
                  onClick={() => void handleUniversePolicySave()}
                >
                  {universePolicyMutation.isPending ? "Сохраняю..." : settingsSaveButtonLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Принятие решений</div>
            <h2 className={sectionTitle}>Пороги сигналов и принятия решений</h2>
          </div>
          <TerminalBadge tone={decisionStatusTone}>{decisionStatusLabel}</TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={localStateNote}>
            Эти параметры читаются из backend-настроек цепочки решений и сохраняются обратно в
            canonical runtime settings path.
          </div>

          {decisionChainQuery.isLoading ? (
            <div className={settingsErrorState}>Загружаю текущие пороги цепочки решений...</div>
          ) : null}

          {decisionChainQuery.isError ? (
            <div className={settingsErrorState}>
              Не удалось загрузить настройки сигналов и принятия решений.
            </div>
          ) : null}

          {decisionChainMutation.isError ? (
            <div className={settingsErrorState}>
              Не удалось сохранить изменения. Проверь значения и повтори сохранение.
            </div>
          ) : null}

          {decisionDraft ? (
            <div className={settingsForm}>
              <div className={settingsFieldGrid}>
                {decisionChainFieldDefinitions.map((field) => (
                  <label key={field.key} className={settingsFieldCard}>
                    <div className={settingsFieldHeader}>
                      <span className={fieldLabel}>{field.label}</span>
                      <span className={settingsFieldMeta}>Рекомендация: {field.recommended}</span>
                    </div>
                    <div className={fieldDescription}>{field.description}</div>
                    <input
                      type="number"
                      inputMode={field.inputMode}
                      step={field.step}
                      className={fieldInput}
                      value={decisionDraft[field.key]}
                      onChange={(event) =>
                        updateDecisionDraftField(field.key, event.target.value)
                      }
                    />
                  </label>
                ))}
              </div>

              <div className={modeControls}>
                <button
                  type="button"
                  className={`${modeButton} ${!isDecisionDirty || !decisionPayload || decisionChainMutation.isPending ? saveButtonDisabled : saveButton}`}
                  disabled={!isDecisionDirty || !decisionPayload || decisionChainMutation.isPending}
                  onClick={() => void handleDecisionChainSave()}
                >
                  {decisionChainMutation.isPending ? "Сохраняю..." : settingsSaveButtonLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Риск</div>
            <h2 className={sectionTitle}>Базовые лимиты риска</h2>
          </div>
          <TerminalBadge tone={riskStatusTone}>{riskStatusLabel}</TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={localStateNote}>
            Эти параметры читаются из backend risk settings и сохраняются обратно в canonical
            runtime settings path.
          </div>

          {riskLimitsQuery.isLoading ? (
            <div className={settingsErrorState}>Загружаю текущие базовые лимиты риска...</div>
          ) : null}

          {riskLimitsQuery.isError ? (
            <div className={settingsErrorState}>
              Не удалось загрузить настройки базовых лимитов риска.
            </div>
          ) : null}

          {riskLimitsMutation.isError ? (
            <div className={settingsErrorState}>
              Не удалось сохранить изменения. Проверь значения и повтори сохранение.
            </div>
          ) : null}

          {riskDraft ? (
            <div className={settingsForm}>
              <div className={settingsFieldGrid}>
                {riskLimitsFieldDefinitions.map((field) => (
                  <label key={field.key} className={settingsFieldCard}>
                    <div className={settingsFieldHeader}>
                      <span className={fieldLabel}>{field.label}</span>
                      <span className={settingsFieldMeta}>Рекомендация: {field.recommended}</span>
                    </div>
                    <div className={fieldDescription}>{field.description}</div>
                    <input
                      type="number"
                      inputMode={field.inputMode}
                      step={field.step}
                      className={fieldInput}
                      value={riskDraft[field.key]}
                      onChange={(event) => updateRiskDraftField(field.key, event.target.value)}
                    />
                  </label>
                ))}
              </div>

              <div className={modeControls}>
                <button
                  type="button"
                  className={`${modeButton} ${!isRiskDirty || !riskPayload || riskLimitsMutation.isPending ? saveButtonDisabled : saveButton}`}
                  disabled={!isRiskDirty || !riskPayload || riskLimitsMutation.isPending}
                  onClick={() => void handleRiskLimitsSave()}
                >
                  {riskLimitsMutation.isPending ? "Сохраняю..." : settingsSaveButtonLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Сопровождение позиции</div>
            <h2 className={sectionTitle}>Трейлинг-стоп и сопровождение позиции</h2>
          </div>
          <TerminalBadge tone={trailingStatusTone}>{trailingStatusLabel}</TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={localStateNote}>
            Эти параметры читаются из backend trailing policy settings и сохраняются обратно в
            canonical runtime settings path.
          </div>

          {trailingPolicyQuery.isLoading ? (
            <div className={settingsErrorState}>
              Загружаю текущие настройки трейлинга и сопровождения позиции...
            </div>
          ) : null}

          {trailingPolicyQuery.isError ? (
            <div className={settingsErrorState}>
              Не удалось загрузить настройки трейлинга и сопровождения позиции.
            </div>
          ) : null}

          {trailingPolicyMutation.isError ? (
            <div className={settingsErrorState}>
              Не удалось сохранить изменения. Проверь значения и повтори сохранение.
            </div>
          ) : null}

          {trailingDraft ? (
            <div className={settingsForm}>
              <div className={settingsFieldGrid}>
                {trailingPolicyFieldDefinitions.map((field) => (
                  <label key={field.key} className={settingsFieldCard}>
                    <div className={settingsFieldHeader}>
                      <span className={fieldLabel}>{field.label}</span>
                      <span className={settingsFieldMeta}>Рекомендация: {field.recommended}</span>
                    </div>
                    <div className={fieldDescription}>{field.description}</div>
                    <input
                      type="number"
                      inputMode={field.inputMode}
                      step={field.step}
                      className={fieldInput}
                      value={trailingDraft[field.key]}
                      onChange={(event) =>
                        updateTrailingDraftField(field.key, event.target.value)
                      }
                    />
                  </label>
                ))}
              </div>

              <div className={modeControls}>
                <button
                  type="button"
                  className={`${modeButton} ${!isTrailingDirty || !trailingPayload || trailingPolicyMutation.isPending ? saveButtonDisabled : saveButton}`}
                  disabled={
                    !isTrailingDirty || !trailingPayload || trailingPolicyMutation.isPending
                  }
                  onClick={() => void handleTrailingPolicySave()}
                >
                  {trailingPolicyMutation.isPending ? "Сохраняю..." : settingsSaveButtonLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Диверсификация</div>
            <h2 className={sectionTitle}>Корреляция и диверсификация портфеля</h2>
          </div>
          <TerminalBadge tone={correlationStatusTone}>{correlationStatusLabel}</TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={localStateNote}>
            Эти параметры читаются из backend correlation policy settings и сохраняются обратно в
            canonical runtime settings path.
          </div>

          {correlationPolicyQuery.isLoading ? (
            <div className={settingsErrorState}>
              Загружаю текущие настройки корреляции и диверсификации...
            </div>
          ) : null}

          {correlationPolicyQuery.isError ? (
            <div className={settingsErrorState}>
              Не удалось загрузить настройки корреляции и диверсификации.
            </div>
          ) : null}

          {correlationPolicyMutation.isError ? (
            <div className={settingsErrorState}>
              Не удалось сохранить изменения. Проверь значения и повтори сохранение.
            </div>
          ) : null}

          {correlationDraft ? (
            <div className={settingsForm}>
              <div className={settingsFieldGrid}>
                {correlationPolicyFieldDefinitions.map((field) => (
                  <label key={field.key} className={settingsFieldCard}>
                    <div className={settingsFieldHeader}>
                      <span className={fieldLabel}>{field.label}</span>
                      <span className={settingsFieldMeta}>Рекомендация: {field.recommended}</span>
                    </div>
                    <div className={fieldDescription}>{field.description}</div>
                    <input
                      type="number"
                      inputMode={field.inputMode}
                      step={field.step}
                      className={fieldInput}
                      value={correlationDraft[field.key]}
                      onChange={(event) =>
                        updateCorrelationDraftField(field.key, event.target.value)
                      }
                    />
                  </label>
                ))}
              </div>

              <div className={modeControls}>
                <button
                  type="button"
                  className={`${modeButton} ${!isCorrelationDirty || !correlationPayload || correlationPolicyMutation.isPending ? saveButtonDisabled : saveButton}`}
                  disabled={
                    !isCorrelationDirty ||
                    !correlationPayload ||
                    correlationPolicyMutation.isPending
                  }
                  onClick={() => void handleCorrelationPolicySave()}
                >
                  {correlationPolicyMutation.isPending ? "Сохраняю..." : settingsSaveButtonLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Защита</div>
            <h2 className={sectionTitle}>Аварийная защита и заморозка</h2>
          </div>
          <TerminalBadge tone={protectionStatusTone}>{protectionStatusLabel}</TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={localStateNote}>
            Эти параметры читаются из backend protection policy settings и сохраняются обратно в
            canonical runtime settings path.
          </div>

          {protectionPolicyQuery.isLoading ? (
            <div className={settingsErrorState}>
              Загружаю текущие настройки аварийной защиты и заморозки...
            </div>
          ) : null}

          {protectionPolicyQuery.isError ? (
            <div className={settingsErrorState}>
              Не удалось загрузить настройки аварийной защиты и заморозки.
            </div>
          ) : null}

          {protectionPolicyMutation.isError ? (
            <div className={settingsErrorState}>
              Не удалось сохранить изменения. Проверь значения и повтори сохранение.
            </div>
          ) : null}

          {protectionDraft ? (
            <div className={settingsForm}>
              <div className={settingsFieldGrid}>
                {protectionPolicyFieldDefinitions.map((field) => (
                  <label key={field.key} className={settingsFieldCard}>
                    <div className={settingsFieldHeader}>
                      <span className={fieldLabel}>{field.label}</span>
                      <span className={settingsFieldMeta}>Рекомендация: {field.recommended}</span>
                    </div>
                    <div className={fieldDescription}>{field.description}</div>
                    <input
                      type="number"
                      inputMode={field.inputMode}
                      step={field.step}
                      className={fieldInput}
                      value={protectionDraft[field.key]}
                      onChange={(event) =>
                        updateProtectionDraftField(field.key, event.target.value)
                      }
                    />
                  </label>
                ))}
              </div>

              <div className={modeControls}>
                <button
                  type="button"
                  className={`${modeButton} ${!isProtectionDirty || !protectionPayload || protectionPolicyMutation.isPending ? saveButtonDisabled : saveButton}`}
                  disabled={
                    !isProtectionDirty || !protectionPayload || protectionPolicyMutation.isPending
                  }
                  onClick={() => void handleProtectionPolicySave()}
                >
                  {protectionPolicyMutation.isPending ? "Сохраняю..." : settingsSaveButtonLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Funding-возможности</div>
            <h2 className={sectionTitle}>Межбиржевые funding-возможности</h2>
          </div>
          <TerminalBadge tone={fundingStatusTone}>{fundingStatusLabel}</TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={localStateNote}>
            Эти параметры читаются из backend-настроек funding-возможностей и сохраняются
            обратно в canonical runtime settings path.
          </div>

          {fundingPolicyQuery.isLoading ? (
            <div className={settingsErrorState}>
              Загружаю текущие настройки funding-возможностей...
            </div>
          ) : null}

          {fundingPolicyQuery.isError ? (
            <div className={settingsErrorState}>
              Не удалось загрузить настройки funding-возможностей.
            </div>
          ) : null}

          {fundingPolicyMutation.isError ? (
            <div className={settingsErrorState}>
              Не удалось сохранить изменения. Проверь значения и повтори сохранение.
            </div>
          ) : null}

          {fundingDraft ? (
            <div className={settingsForm}>
              <div className={settingsFieldGrid}>
                {fundingPolicyFieldDefinitions.map((field) => (
                  <label key={field.key} className={settingsFieldCard}>
                    <div className={settingsFieldHeader}>
                      <span className={fieldLabel}>{field.label}</span>
                      <span className={settingsFieldMeta}>Рекомендация: {field.recommended}</span>
                    </div>
                    <div className={fieldDescription}>{field.description}</div>
                    <input
                      type="number"
                      inputMode={field.inputMode}
                      step={field.step}
                      className={fieldInput}
                      value={fundingDraft[field.key]}
                      onChange={(event) =>
                        updateFundingDraftField(field.key, event.target.value)
                      }
                    />
                  </label>
                ))}
              </div>

              <div className={modeControls}>
                <button
                  type="button"
                  className={`${modeButton} ${!isFundingDirty || !fundingPayload || fundingPolicyMutation.isPending ? saveButtonDisabled : saveButton}`}
                  disabled={!isFundingDirty || !fundingPayload || fundingPolicyMutation.isPending}
                  onClick={() => void handleFundingPolicySave()}
                >
                  {fundingPolicyMutation.isPending ? "Сохраняю..." : settingsSaveButtonLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Надёжность</div>
            <h2 className={sectionTitle}>Надёжность и восстановление системы</h2>
          </div>
          <TerminalBadge tone={reliabilityStatusTone}>{reliabilityStatusLabel}</TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={localStateNote}>
            Эти параметры читаются из backend reliability policy settings и сохраняются обратно в
            canonical runtime settings path.
          </div>

          {reliabilityPolicyQuery.isLoading ? (
            <div className={settingsErrorState}>Загружаю параметры надёжности и восстановления...</div>
          ) : null}

          {reliabilityPolicyQuery.isError ? (
            <div className={settingsErrorState}>
              Не удалось загрузить настройки надёжности и восстановления.
            </div>
          ) : null}

          {reliabilityPolicyMutation.isError ? (
            <div className={settingsErrorState}>
              Не удалось сохранить изменения. Проверь значения и повтори сохранение.
            </div>
          ) : null}

          {reliabilityDraft ? (
            <div className={settingsForm}>
              <div className={sectionBody}>
                <div>
                  <div className={sectionCaption}>Защитный контур</div>
                  <div className={fieldDescription}>
                    Порог открытия защиты и условия безопасного возврата в нормальный режим.
                  </div>
                </div>
                <div className={settingsFieldGrid}>
                  {reliabilityCircuitBreakerFieldDefinitions.map((field) => (
                    <div key={field.key} className={settingsFieldCard}>
                      <div className={settingsFieldHeader}>
                        <div className={fieldLabel}>{field.label}</div>
                        <div className={settingsFieldMeta}>Рекомендация: {field.recommended}</div>
                      </div>
                      <div className={fieldDescription}>{field.description}</div>
                      <input
                        type="number"
                        inputMode={field.inputMode}
                        step={field.step}
                        className={fieldInput}
                        value={reliabilityDraft[field.key]}
                        onChange={(event) =>
                          updateReliabilityDraftField(field.key, event.target.value)
                        }
                      />
                    </div>
                  ))}
                </div>
              </div>

              <div className={sectionBody}>
                <div>
                  <div className={sectionCaption}>Сторожевой контроль</div>
                  <div className={fieldDescription}>
                    Ритм проверок и параметры recovery-повторов для автоматического восстановления.
                  </div>
                </div>
                <div className={settingsFieldGrid}>
                  {reliabilityWatchdogFieldDefinitions.map((field) => (
                    <div key={field.key} className={settingsFieldCard}>
                      <div className={settingsFieldHeader}>
                        <div className={fieldLabel}>{field.label}</div>
                        <div className={settingsFieldMeta}>Рекомендация: {field.recommended}</div>
                      </div>
                      <div className={fieldDescription}>{field.description}</div>
                      <input
                        type="number"
                        inputMode={field.inputMode}
                        step={field.step}
                        className={fieldInput}
                        value={reliabilityDraft[field.key]}
                        onChange={(event) =>
                          updateReliabilityDraftField(field.key, event.target.value)
                        }
                      />
                    </div>
                  ))}
                </div>
              </div>

              <div className={modeControls}>
                <button
                  type="button"
                  className={`${modeButton} ${!isReliabilityDirty || !reliabilityPayload || reliabilityPolicyMutation.isPending ? saveButtonDisabled : saveButton}`}
                  disabled={
                    !isReliabilityDirty ||
                    !reliabilityPayload ||
                    reliabilityPolicyMutation.isPending
                  }
                  onClick={() => void handleReliabilityPolicySave()}
                >
                  {reliabilityPolicyMutation.isPending ? "Сохраняю..." : settingsSaveButtonLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Готовность системы</div>
            <h2 className={sectionTitle}>Здоровье системы и проверки готовности</h2>
          </div>
          <TerminalBadge tone={healthStatusTone}>{healthStatusLabel}</TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={localStateNote}>
            Эти параметры читаются из backend-настроек здоровья системы и сохраняются обратно в
            canonical runtime settings path.
          </div>

          {healthPolicyQuery.isLoading ? (
            <div className={settingsErrorState}>
              Загружаю настройки здоровья системы и проверок готовности...
            </div>
          ) : null}

          {healthPolicyQuery.isError ? (
            <div className={settingsErrorState}>
              Не удалось загрузить настройки здоровья системы и готовности.
            </div>
          ) : null}

          {healthPolicyMutation.isError ? (
            <div className={settingsErrorState}>
              Не удалось сохранить изменения. Проверь значения и повтори сохранение.
            </div>
          ) : null}

          {healthDraft ? (
            <div className={settingsForm}>
              <div className={settingsFieldGrid}>
                {healthPolicyFieldDefinitions.map((field) => (
                  <div key={field.key} className={settingsFieldCard}>
                    <div className={settingsFieldHeader}>
                      <div className={fieldLabel}>{field.label}</div>
                      <div className={settingsFieldMeta}>Рекомендация: {field.recommended}</div>
                    </div>
                    <div className={fieldDescription}>{field.description}</div>
                    <input
                      type="number"
                      inputMode={field.inputMode}
                      step={field.step}
                      className={fieldInput}
                      value={healthDraft[field.key]}
                      onChange={(event) => updateHealthDraftField(field.key, event.target.value)}
                    />
                  </div>
                ))}
              </div>

              <div className={modeControls}>
                <button
                  type="button"
                  className={`${modeButton} ${!isHealthDirty || !healthPayload || healthPolicyMutation.isPending ? saveButtonDisabled : saveButton}`}
                  disabled={!isHealthDirty || !healthPayload || healthPolicyMutation.isPending}
                  onClick={() => void handleHealthPolicySave()}
                >
                  {healthPolicyMutation.isPending ? "Сохраняю..." : settingsSaveButtonLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Очереди событий</div>
            <h2 className={sectionTitle}>Очереди событий и защита от перегрузки</h2>
          </div>
          <TerminalBadge tone={eventBusStatusTone}>{eventBusStatusLabel}</TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={localStateNote}>
            Эти параметры читаются из backend-настроек очередей событий и сохраняются обратно в
            canonical runtime settings path.
          </div>

          {eventBusPolicyQuery.isLoading ? (
            <div className={settingsErrorState}>
              Загружаю настройки очередей событий и защиты от перегрузки...
            </div>
          ) : null}

          {eventBusPolicyQuery.isError ? (
            <div className={settingsErrorState}>
              Не удалось загрузить настройки очередей событий и защиты от перегрузки.
            </div>
          ) : null}

          {eventBusPolicyMutation.isError ? (
            <div className={settingsErrorState}>
              Не удалось сохранить изменения. Проверь значения и повтори сохранение.
            </div>
          ) : null}

          {eventBusDraft ? (
            <div className={settingsForm}>
              <div className={settingsFieldGrid}>
                {eventBusPolicyFieldDefinitions.map((field) => (
                  <div key={field.key} className={settingsFieldCard}>
                    <div className={settingsFieldHeader}>
                      <div className={fieldLabel}>{field.label}</div>
                      <div className={settingsFieldMeta}>Рекомендация: {field.recommended}</div>
                    </div>
                    <div className={fieldDescription}>{field.description}</div>
                    <input
                      type="number"
                      inputMode={field.inputMode}
                      step={field.step}
                      className={fieldInput}
                      value={eventBusDraft[field.key]}
                      onChange={(event) => updateEventBusDraftField(field.key, event.target.value)}
                    />
                  </div>
                ))}
              </div>

              <div className={modeControls}>
                <button
                  type="button"
                  className={`${modeButton} ${!isEventBusDirty || !eventBusPayload || eventBusPolicyMutation.isPending ? saveButtonDisabled : saveButton}`}
                  disabled={
                    !isEventBusDirty || !eventBusPayload || eventBusPolicyMutation.isPending
                  }
                  onClick={() => void handleEventBusPolicySave()}
                >
                  {eventBusPolicyMutation.isPending ? "Сохраняю..." : settingsSaveButtonLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Режимы системы</div>
            <h2 className={sectionTitle}>Режимы системы и ограничения</h2>
          </div>
          <TerminalBadge tone={systemStateStatusTone}>{systemStateStatusLabel}</TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={localStateNote}>
            Эти параметры читаются из backend system state policy settings и сохраняются обратно в
            canonical runtime settings path.
          </div>

          {systemStatePolicyQuery.isLoading ? (
            <div className={settingsErrorState}>Загружаю текущие ограничения по режимам...</div>
          ) : null}

          {systemStatePolicyQuery.isError ? (
            <div className={settingsErrorState}>
              Не удалось загрузить настройки режимов системы.
            </div>
          ) : null}

          {systemStatePolicyMutation.isError ? (
            <div className={settingsErrorState}>
              Не удалось сохранить изменения. Проверь значения и повтори сохранение.
            </div>
          ) : null}

          {systemStateDraft ? (
            <div className={settingsForm}>
              <div className={comparisonTableWrap}>
                <table className={comparisonTable}>
                  <thead>
                    <tr>
                      <th className={comparisonHeadCell}>Режим</th>
                      <th className={comparisonHeadCell}>Множитель риска</th>
                      <th className={comparisonHeadCell}>Макс. позиций</th>
                      <th className={comparisonHeadCell}>Макс. новая позиция</th>
                      <th className={comparisonHeadCell}>Рекомендация</th>
                    </tr>
                  </thead>
                  <tbody>
                    {systemStatePolicyGroups.map((group) => {
                      const riskField = systemStatePolicyFieldDefinitions.find(
                        (item) => item.key === group.keys[0],
                      );
                      const positionsField = systemStatePolicyFieldDefinitions.find(
                        (item) => item.key === group.keys[1],
                      );
                      const orderSizeField = systemStatePolicyFieldDefinitions.find(
                        (item) => item.key === group.keys[2],
                      );
                      if (!riskField || !positionsField || !orderSizeField) {
                        return null;
                      }
                      return (
                        <tr key={group.caption}>
                          <td className={comparisonBodyCell}>
                            <div className={comparisonRowHeader}>
                              <span className={comparisonRowCaption}>{group.caption}</span>
                              <span className={comparisonRowTitle}>{group.title}</span>
                              <span className={comparisonRowDescription}>{group.description}</span>
                            </div>
                          </td>
                          <td className={comparisonBodyCell}>
                            <input
                              type="number"
                              inputMode={riskField.inputMode}
                              step={riskField.step}
                              className={comparisonInput}
                              value={systemStateDraft[riskField.key]}
                              onChange={(event) =>
                                updateSystemStateDraftField(riskField.key, event.target.value)
                              }
                            />
                          </td>
                          <td className={comparisonBodyCell}>
                            <input
                              type="number"
                              inputMode={positionsField.inputMode}
                              step={positionsField.step}
                              className={comparisonInput}
                              value={systemStateDraft[positionsField.key]}
                              onChange={(event) =>
                                updateSystemStateDraftField(
                                  positionsField.key,
                                  event.target.value,
                                )
                              }
                            />
                          </td>
                          <td className={comparisonBodyCell}>
                            <input
                              type="number"
                              inputMode={orderSizeField.inputMode}
                              step={orderSizeField.step}
                              className={comparisonInput}
                              value={systemStateDraft[orderSizeField.key]}
                              onChange={(event) =>
                                updateSystemStateDraftField(
                                  orderSizeField.key,
                                  event.target.value,
                                )
                              }
                            />
                          </td>
                          <td className={comparisonBodyCell}>
                            <div className={comparisonRecommendation}>
                              {riskField.recommended} / {positionsField.recommended} /{" "}
                              {orderSizeField.recommended}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className={modeControls}>
                <button
                  type="button"
                  className={`${modeButton} ${!isSystemStateDirty || !systemStatePayload || systemStatePolicyMutation.isPending ? saveButtonDisabled : saveButton}`}
                  disabled={
                    !isSystemStateDirty ||
                    !systemStatePayload ||
                    systemStatePolicyMutation.isPending
                  }
                  onClick={() => void handleSystemStatePolicySave()}
                >
                  {systemStatePolicyMutation.isPending ? "Сохраняю..." : settingsSaveButtonLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Таймауты состояний</div>
            <h2 className={sectionTitle}>Таймауты состояний системы</h2>
          </div>
          <TerminalBadge tone={systemStateTimeoutStatusTone}>
            {systemStateTimeoutStatusLabel}
          </TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={localStateNote}>
            Эти параметры читаются из backend system state timeout settings и сохраняются обратно
            в canonical runtime settings path.
          </div>

          {systemStateTimeoutQuery.isLoading ? (
            <div className={settingsErrorState}>Загружаю текущие таймауты состояний...</div>
          ) : null}

          {systemStateTimeoutQuery.isError ? (
            <div className={settingsErrorState}>
              Не удалось загрузить таймауты состояний системы.
            </div>
          ) : null}

          {systemStateTimeoutMutation.isError ? (
            <div className={settingsErrorState}>
              Не удалось сохранить изменения. Проверь значения и повтори сохранение.
            </div>
          ) : null}

          {systemStateTimeoutDraft ? (
            <div className={settingsForm}>
              <div className={comparisonTableWrap}>
                <table className={`${comparisonTable} ${comparisonTableCompact}`}>
                  <thead>
                    <tr>
                      <th className={comparisonHeadCell}>Состояние</th>
                      <th className={comparisonHeadCell}>Максимальное время</th>
                      <th className={comparisonHeadCell}>Рекомендация</th>
                    </tr>
                  </thead>
                  <tbody>
                    {systemStateTimeoutGroups.map((group) => {
                      const field = systemStateTimeoutFieldDefinitions.find(
                        (item) => item.key === group.keys[0],
                      );
                      if (!field) {
                        return null;
                      }
                      return (
                        <tr key={group.caption}>
                          <td className={comparisonBodyCell}>
                            <div className={comparisonRowHeader}>
                              <span className={comparisonRowCaption}>{group.caption}</span>
                              <span className={comparisonRowTitle}>{group.title}</span>
                              <span className={comparisonRowDescription}>{group.description}</span>
                            </div>
                          </td>
                          <td className={comparisonBodyCell}>
                            <input
                              type="number"
                              inputMode={field.inputMode}
                              step={field.step}
                              className={comparisonInput}
                              value={systemStateTimeoutDraft[field.key]}
                              onChange={(event) =>
                                updateSystemStateTimeoutDraftField(field.key, event.target.value)
                              }
                            />
                          </td>
                          <td className={comparisonBodyCell}>
                            <div className={comparisonRecommendation}>{field.recommended}</div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className={modeControls}>
                <button
                  type="button"
                  className={`${modeButton} ${!isSystemStateTimeoutDirty || !systemStateTimeoutPayload || systemStateTimeoutMutation.isPending ? saveButtonDisabled : saveButton}`}
                  disabled={
                    !isSystemStateTimeoutDirty ||
                    !systemStateTimeoutPayload ||
                    systemStateTimeoutMutation.isPending
                  }
                  onClick={() => void handleSystemStateTimeoutSave()}
                >
                  {systemStateTimeoutMutation.isPending ? "Сохраняю..." : settingsSaveButtonLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Виджеты</div>
            <h2 className={sectionTitle}>Состав рабочей области</h2>
          </div>
          <TerminalBadge tone="neutral">
            {widgets.filter((widget) => widget.visible).length} активны
          </TerminalBadge>
        </div>

        <div className={widgetSettingsGrid}>
          {widgets.map((widget) => (
            <div key={widget.id} className={widgetSettingsCard}>
              <div className={widgetSettingsRow}>
                <div>
                  <div className={stateValue}>{widget.title}</div>
                  <div className={widgetSettingsMeta}>
                    {widget.visible ? "Показывается на главной" : "Скрыт с главной"} · {widget.layout.w}×
                    {widget.layout.h}
                  </div>
                </div>

                <label className={widgetVisibilityControl}>
                  <input
                    type="checkbox"
                    className={widgetVisibilityCheckbox}
                    checked={widget.visible}
                    onChange={(event) => setWidgetVisible(widget.id, event.target.checked)}
                  />
                  <span>{widget.visible ? "Включен" : "Выключен"}</span>
                </label>
              </div>
            </div>
          ))}
        </div>

        <div className={localStateNote}>
          Видимость, позиции и размеры widget-area сохраняются локально и сразу синхронизируются
          между главной страницей терминала и настройками.
        </div>
      </section>
    </div>
  );
}
