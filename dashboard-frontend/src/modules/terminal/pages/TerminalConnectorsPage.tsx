import { type ReactNode, useEffect, useMemo, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { TerminalBadge } from "../components/TerminalBadge";
import { getBybitConnectorDiagnostics } from "../api/getBybitConnectorDiagnostics";
import { getBybitSpotProductSnapshot } from "../api/getBybitSpotProductSnapshot";
import { getLiveFeedPolicySettings } from "../api/getLiveFeedPolicySettings";
import { updateLiveFeedPolicySettings } from "../api/updateLiveFeedPolicySettings";
import { updateBybitConnectorEnabled } from "../api/updateBybitConnectorEnabled";
import { updateBybitSpotRuntimeState } from "../api/updateBybitSpotRuntimeState";
import type {
  BybitConnectorDiagnosticsResponse,
  BybitConnectorSymbolSnapshotResponse,
  BybitSpotProductSnapshotResponse,
  BybitSpotRuntimeStatusResponse,
  BybitSpotV2DiagnosticsResponse,
  LiveFeedPolicySettingsResponse,
} from "../../../shared/types/connectors";
import {
  exchangeMeta,
  exchangeToggle,
  fieldDescription,
  fieldInput,
  fieldLabel,
  localStateNote,
  modeButton,
  modeControls,
  pageRoot,
  saveButton,
  saveButtonDisabled,
  sectionBody,
  sectionCaption,
  sectionHeader,
  sectionTitle,
  settingsCard,
  settingsErrorState,
  settingsFieldCard,
  settingsFieldGrid,
  settingsFieldHeader,
  settingsFieldMeta,
  settingsForm,
  stateValue,
} from "./TerminalSettingsPage.css";
import {
  connectorConfigGrid,
  connectorControlCard,
  connectorControlGrid,
  connectorControlInput,
  connectorConfigSection,
  connectorEmptyState,
  connectorFlowPill,
  connectorPanel,
  connectorPanelFuture,
  connectorPanelHeader,
  connectorPanelIntro,
  connectorPanelV2,
  connectorSemanticNote,
  connectorPanelSpot,
  connectorPanels,
  connectorStatsGrid,
  connectorStatusCard,
  connectorStatusHero,
  connectorStatusHeroNeutral,
  connectorStatusHeroSuccess,
  connectorStatusDetail,
  connectorStatusLabel,
  connectorStatusValue,
  connectorTable,
  connectorTableBodyCell,
  connectorTableHeadCell,
  connectorTableWrap,
  exchangeSelector,
  exchangeSelectorButton,
  exchangeSelectorButtonActive,
} from "./TerminalConnectorsPage.css";

type SupportedExchange = "Bybit" | "Binance" | "OKX";
type LiveFeedPolicyFieldKey =
  | "retry_delay_seconds"
  | "bybit_spot_universe_min_quote_volume_24h_usd"
  | "bybit_spot_universe_min_trade_count_24h"
  | "bybit_spot_quote_asset_filter";
type LiveFeedPolicyDraft = Record<LiveFeedPolicyFieldKey, string>;

const liveFeedControlFieldDefinitions = {
  retryDelaySeconds: {
    label: "Базовая задержка перед повторным подключением",
    description: "Сколько секунд система ждёт перед новой попыткой подключиться к рынку после разрыва.",
    recommended: "5 сек",
  },
  minVolume: {
    label: "Минимальный объём за 24 часа",
    description: "Инструменты с меньшим оборотом не попадут в автоматический рабочий список.",
    recommended: "100 000 000 USD",
  },
  minTradeCount: {
    label: "Минимальное число сделок за 24 часа",
    description:
      "Монета попадает в рабочий список только если проходит этот порог и порог по объёму. Значение 0 отключает фильтр по числу сделок.",
    recommended: "200 000 или 0, если фильтр не нужен",
  },
  quoteAssetFilter: {
    label: "Котируемая валюта пары",
    description: "Ограничивает spot universe только парами с нужной котируемой валютой.",
    recommended: "USDT + USDC",
  },
} as const;

function formatGroupedInteger(value: string): string {
  const digits = value.replace(/\D+/g, "");
  if (!digits) {
    return "";
  }
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

function parseGroupedNumber(value: string): number {
  return Number(value.replace(/\s+/g, ""));
}

function toLiveFeedPolicyDraft(values: LiveFeedPolicySettingsResponse): LiveFeedPolicyDraft {
  return {
    retry_delay_seconds: String(values.retry_delay_seconds),
    bybit_spot_universe_min_quote_volume_24h_usd: formatGroupedInteger(
      String(values.bybit_spot_universe_min_quote_volume_24h_usd),
    ),
    bybit_spot_universe_min_trade_count_24h: formatGroupedInteger(
      String(values.bybit_spot_universe_min_trade_count_24h),
    ),
    bybit_spot_quote_asset_filter: values.bybit_spot_quote_asset_filter,
  };
}

function formatDiagnosticsTimestamp(value: string | null): string {
  if (!value) {
    return "Нет данных";
  }
  const parsedDate = new Date(value);
  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(parsedDate);
}

function formatTransportStatus(value: string): string {
  switch (value) {
    case "connected":
      return "Подключено";
    case "connecting":
      return "Подключаемся";
    case "disconnected":
      return "Нет соединения";
    case "idle":
      return "Ожидает запуска";
    case "disabled":
      return "Отключено";
    default:
      return value;
  }
}

function isWaitingForScopeDueToDiscovery(
  diagnostics: BybitConnectorDiagnosticsResponse,
): boolean {
  return (
    diagnostics.transport_status === "idle" &&
    diagnostics.recovery_status === "waiting_for_scope" &&
    diagnostics.degraded_reason === "discovery_unavailable"
  );
}

function formatRecoveryStatus(value: string): string {
  switch (value) {
    case "recovered":
      return "Восстановлено";
    case "recovering":
      return "Восстанавливается";
    case "recovery_required":
      return "Нужно восстановление";
    case "waiting_for_scope":
      return "Ждёт список инструментов";
    case "idle":
      return "Без восстановления";
    default:
      return value;
  }
}

function formatScopeMode(value: string | null): string {
  if (value === "universe") {
    return "Автоматический отбор";
  }
  return "Нет данных";
}

function formatNumber(value: number | null | undefined): string {
  return typeof value === "number" ? new Intl.NumberFormat("ru-RU").format(value) : "Нет данных";
}

function formatUsdVolume(value: string | null): string {
  if (!value) {
    return "Нет данных";
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Intl.NumberFormat("ru-RU", {
    useGrouping: true,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(parsed);
}

function formatSpotProductTradeCount(
  value: number | null | undefined,
  archiveCoveragePending: boolean,
): string {
  if (typeof value === "number") {
    return formatNumber(value);
  }
  return archiveCoveragePending ? "Уточняется" : "Нет данных";
}

function formatApplyStatus(value: string | null): string {
  switch (value) {
    case "applied":
      return "Уже действует";
    case "deferred":
      return "Сохранено, применяется позже";
    case "waiting_for_scope":
      return "Ждёт список инструментов";
    case "not_running":
      return "Вступит в силу при запуске";
    default:
      return value ?? "Нет данных";
  }
}

function formatConnectorProblemReason(value: string | null): string {
  switch (value) {
    case null:
      return "Нет данных";
    case "ping_timeout":
      return "Соединение не ответило на проверку связи";
    case "transport_lost":
      return "Соединение оборвалось во время закрытия или передачи данных";
    case "remote_close":
      return "Биржа закрыла соединение";
    case "transport_closed":
      return "Соединение закрыто";
    case "transport_reconnect_pending":
      return "Соединение переподключается";
    case "discovery_unavailable":
      return "Не удалось получить список инструментов";
    default:
      return value;
  }
}

function getReconnectHistoryDetail(diagnostics: BybitConnectorDiagnosticsResponse): string {
  if (typeof diagnostics.retry_count !== "number") {
    return "Нет данных о переподключениях в текущем lifecycle runtime."
  }
  if (diagnostics.retry_count === 0) {
    return "С начала текущего запуска переподключений не было."
  }
  if (diagnostics.transport_status === "connected" && !diagnostics.degraded_reason) {
    return "Исторический счётчик за текущий запуск. Сам по себе не означает текущую аварийность."
  }
  return "Исторический счётчик за текущий запуск. Текущее состояние смотрите в карточках «Подключение» и «Текущая проблема»."
}

function formatTradeCount(snapshot: BybitConnectorSymbolSnapshotResponse): string {
  if (
    snapshot.product_trade_count_state === "partial_ledger_coverage" &&
    typeof snapshot.product_trade_count_24h === "number"
  ) {
    return `${formatNumber(snapshot.product_trade_count_24h)} · частично`;
  }
  if (typeof snapshot.product_trade_count_24h === "number") {
    return formatNumber(snapshot.product_trade_count_24h);
  }
  if (snapshot.product_trade_count_state === "reconciliation_mismatch") {
    return "Требует сверки";
  }
  if (snapshot.product_trade_count_state === "ledger_unavailable") {
    return "Нет подтверждения";
  }
  if (snapshot.product_trade_count_state === "partial_ledger_coverage") {
    return "Частичное покрытие";
  }
  if (snapshot.observed_trade_count_since_reset > 0) {
    return `Собираем · ${formatNumber(snapshot.observed_trade_count_since_reset)}`;
  }
  return "Собираем";
}

function formatTradeCountVerificationLabel(diagnostics: BybitConnectorDiagnosticsResponse): string {
  switch (diagnostics.trade_count_product_truth_state) {
    case "ledger_confirmed":
      return "Подтверждена";
    case "partial_ledger_coverage":
      return "Частичное покрытие";
    case "reconciliation_mismatch":
      return "Требует сверки";
    case "ledger_unavailable":
      return "Нет подтверждения";
    default:
      return "Ещё идёт";
  }
}

function formatTradeCountTruthModelLabel(
  diagnostics: BybitConnectorDiagnosticsResponse,
): string {
  switch (diagnostics.trade_count_product_truth_state) {
    case "ledger_confirmed":
      return "Подтверждённое число экрана";
    case "partial_ledger_coverage":
      return "Частичное 24ч покрытие";
    case "reconciliation_mismatch":
      return "Число экрана требует сверки";
    case "ledger_unavailable":
      return "Подтверждение недоступно";
    default:
      return "Идёт подтверждение";
  }
}

function getTradeCountTruthModelDetail(
  diagnostics: BybitConnectorDiagnosticsResponse,
): string {
  switch (diagnostics.trade_count_product_truth_state) {
    case "ledger_confirmed":
      return "Колонка «Сделок за 24ч» показывает подтверждённое число из trade ledger за последние 24 часа.";
    case "partial_ledger_coverage":
      return "Колонка «Сделок за 24ч» показывает только live-covered часть окна. Полный rolling 24h truth ещё не подтверждён.";
    case "reconciliation_mismatch":
      return "Колонка «Сделок за 24ч» не подменяет подтверждённое число расчётным контуром, пока ledger и runtime не согласованы.";
    case "ledger_unavailable":
      return "Колонка «Сделок за 24ч» ждёт подтверждение из trade ledger и не подменяет его расчётным контуром.";
    default:
      return "Колонка «Сделок за 24ч» ждёт подтверждённое число из trade ledger.";
  }
}

function formatTradeCountAdmissionLabel(
  diagnostics: BybitConnectorDiagnosticsResponse,
): string {
  switch (diagnostics.trade_count_admission_basis) {
    case "derived_operational_truth":
      return "Расчётный контур admission";
    default:
      return "Не применяется";
  }
}

function getTradeCountAdmissionDetail(
  diagnostics: BybitConnectorDiagnosticsResponse,
): string {
  if (diagnostics.trade_count_admission_basis === "derived_operational_truth") {
    return "Текущий minTradeCount-фильтр пока опирается на отдельный расчётный контур admission. Это другая модель, чем число «Сделок за 24ч» на экране.";
  }
  return "Отдельный trade-count admission path сейчас не активен.";
}

function getTradeCountVerificationDetail(diagnostics: BybitConnectorDiagnosticsResponse): string {
  const admissionUsesDerived =
    diagnostics.trade_count_admission_basis === "derived_operational_truth";
  switch (diagnostics.trade_count_product_truth_state) {
    case "ledger_confirmed":
      return diagnostics.universe_admission_state === "ready_for_selection"
        ? "Подтверждённое число готово, и отбор по trade-count больше не противоречит показанному числу."
        : "Подтверждённое число уже готово, но контур admission ещё не дошёл до финального состояния.";
    case "partial_ledger_coverage":
      return "Trade ledger уже собирает live-сделки, но полное rolling 24h окно ещё не покрыто. Число на экране не считается финальным truth.";
    case "reconciliation_mismatch":
      return admissionUsesDerived
        ? "Подтверждённое число и расчётный trade-count расходятся. Текущий minTradeCount-фильтр всё ещё живёт на отдельном расчётном контуре."
        : "Ledger и operational trade-count расходятся. Пользовательское число не считается финально подтверждённым.";
    case "ledger_unavailable":
      return admissionUsesDerived
        ? "Подтверждение из trade ledger сейчас недоступно. Текущий minTradeCount-фильтр всё ещё опирается на отдельный расчётный контур."
        : "Ledger truth сейчас недоступна, поэтому финальная 24ч truth по сделкам не подтверждена.";
    default:
      return admissionUsesDerived
        ? "Подтверждённое число по сделкам ещё проверяется. Текущий minTradeCount-фильтр пока остаётся на отдельном расчётном контуре."
        : "Финальная truth по сделкам ещё проверяется.";
  }
}

function getTradeCountSemanticSummary(
  diagnostics: BybitConnectorDiagnosticsResponse,
): string {
  if (diagnostics.trade_count_admission_basis === "derived_operational_truth") {
    return diagnostics.trade_count_product_truth_state === "partial_ledger_coverage"
      ? "На экране «Сделок за 24ч» сейчас показывается только live-covered часть окна trade ledger, а minTradeCount использует отдельный расчётный контур admission."
      : "На экране «Сделок за 24ч» показывается подтверждённое число из trade ledger, а minTradeCount использует отдельный расчётный контур admission. Эти модели сейчас намеренно разведены и могут временно не совпадать.";
  }
  return diagnostics.trade_count_product_truth_state === "partial_ledger_coverage"
    ? "На экране «Сделок за 24ч» сейчас показывается только live-covered часть окна trade ledger. Полный 24ч truth ещё не подтверждён."
    : "На экране «Сделок за 24ч» показывается подтверждённое число из trade ledger. Отдельный minTradeCount admission path сейчас не активен.";
}

function getRecoveryDetail(diagnostics: BybitConnectorDiagnosticsResponse): string {
  if (diagnostics.degraded_reason === "discovery_unavailable") {
    return "Ждём, пока discovery снова отдаст список инструментов.";
  }
  if (diagnostics.historical_recovery_state === "backfilling") {
    return "Идёт загрузка истории.";
  }
  if (diagnostics.historical_recovery_state === "retry_scheduled") {
    return "Повтор загрузки уже запланирован.";
  }
  if (
    diagnostics.operator_runtime_state === "waiting_for_live_tail" ||
    diagnostics.derived_trade_count_state === "live_tail_pending_after_gap"
  ) {
    return "Добираем последние сделки после переподключения.";
  }
  if (diagnostics.recovery_status === "waiting_for_scope") {
    return "Контур ждёт рабочий список инструментов.";
  }
  if (diagnostics.recovery_status === "recovered") {
    return "Активной загрузки сейчас нет.";
  }
  return "Восстановление запустится автоматически, если понадобится.";
}

function formatOperatorRuntimeState(value: string | null | undefined): string {
  switch (value) {
    case "ready_for_operation":
      return "Готов к работе";
    case "waiting_for_live_tail":
      return "Ждёт live tail";
    case "recovering":
      return "Восстанавливается";
    case "not_applicable":
      return "Не применяется";
    default:
      return value ?? "Нет данных";
  }
}

function formatLedgerSyncState(value: string | null | undefined): string {
  switch (value) {
    case "ledger_sync_in_progress":
      return "Ledger sync догоняет";
    case "ledger_sync_completed":
      return "Ledger sync завершён";
    case "ledger_sync_pending":
      return "Ledger sync ожидает запуск";
    case "ledger_sync_failed":
      return "Ledger sync не завершён";
    case "not_configured":
      return "Ledger sync не настроен";
    case "not_applicable":
      return "Не применяется";
    default:
      return value ?? "Нет данных";
  }
}

function formatSpotV2OperatorStatus(value: string): string {
  switch (value) {
    case "ready":
      return "Spot v2 готов";
    case "recovering":
      return "Spot v2 восстанавливается";
    case "legacy_baseline_frozen":
      return "Legacy baseline заморожен";
    case "transport_degraded":
      return "Transport деградирован";
    case "derived_unavailable":
      return "Derived недоступен";
    case "attention_required":
      return "Требует внимания";
    case "disabled":
      return "Отключено";
    default:
      return value;
  }
}

function formatSpotV2ReconciliationVerdict(value: string | null | undefined): string {
  switch (value) {
    case "matched":
      return "Совпадает";
    case "mismatch":
      return "Есть расхождение";
    case "retired_baseline":
      return "Legacy baseline frozen";
    case "unavailable":
      return "Недоступно";
    default:
      return value ?? "Нет данных";
  }
}

function formatSpotV2ReconciliationReason(value: string | null | undefined): string {
  switch (value) {
    case "legacy_baseline_frozen_after_primary_switch":
      return "Legacy baseline заморожен после primary switch и больше не используется как активный truth owner.";
    case "legacy_derived_snapshot_stale_after_primary_switch":
      return "Legacy derived snapshot устарел после primary switch и больше не является активным baseline.";
    case "symbol_mismatch_present":
      return "Есть расхождение между persisted state и legacy comparison baseline.";
    case "all_symbols_match":
      return "По всем символам counts совпадают.";
    case "exact_count_match":
      return "Counts совпадают точно.";
    case "persisted_exceeds_derived":
      return "Persisted count выше legacy comparison baseline.";
    case "derived_exceeds_persisted":
      return "Legacy comparison baseline выше persisted count.";
    case "derived_trade_count_unavailable":
      return "Derived comparison snapshot сейчас недоступен.";
    default:
      return value ?? "Нет данных";
  }
}

function formatSpotV2PersistenceWindowContract(value: string | null | undefined): string {
  switch (value) {
    case "rolling_24h_exact":
      return "Точное скользящее 24ч окно без minute-alignment: каждая метрика пересчитывается по текущему observed_at.";
    default:
      return value ?? "Нет данных";
  }
}

function formatSpotV2PersistenceSplitContract(value: string | null | undefined): string {
  switch (value) {
    case "archive_origin_plus_live_residual_inside_same_window":
      return "Archive считает все archive-origin trades внутри текущего окна, Live считает только live-origin trades того же окна, которые ещё не покрыты archive внутри этого же окна.";
    default:
      return value ?? "Нет данных";
  }
}

function getSpotV2WorkingStatus(diagnostics: BybitSpotV2DiagnosticsResponse): string {
  if (
    diagnostics.transport.transport_status === "connected" &&
    diagnostics.transport.subscription_alive &&
    diagnostics.ingest.trade_seen &&
    diagnostics.ingest.orderbook_seen
  ) {
    return "Работает";
  }
  if (
    diagnostics.transport.transport_status === "connected" &&
    diagnostics.transport.subscription_alive
  ) {
    return "Подключён";
  }
  return "Проверить подключение";
}

function getSpotRuntimeWorkingStatus(status: BybitSpotRuntimeStatusResponse): string {
  switch (status.lifecycle_state) {
    case "connected_live":
      return "Работает";
    case "connected_no_flow":
      return "Запускается";
    case "starting":
      return "Запускается";
    case "stopped":
      return "Ожидает запуска";
    case "degraded":
      return "Требует проверки";
    default:
      return "Проверить подключение";
  }
}

function getSpotRuntimeConnectionLabel(status: BybitSpotRuntimeStatusResponse): string {
  switch (status.lifecycle_state) {
    case "stopped":
      return "Отключено";
    case "starting":
      return "Подключаемся";
    case "connected_no_flow":
      return "Работа не подтверждена";
    case "connected_live":
      return "Подключено";
    case "degraded":
      return "Нужна проверка";
    default:
      return formatTransportStatus(status.transport_status);
  }
}

function getOperatorStateSurfaceSummary(
  diagnostics: BybitConnectorDiagnosticsResponse,
): {
  runtimeLabel: string;
  runtimeReason: string;
  ledgerLabel: string;
  ledgerReason: string;
} {
  const runtimeState =
    diagnostics.operator_state_surface?.runtime?.state ??
    diagnostics.operational_recovery_state;
  const runtimeReason =
    diagnostics.operator_state_surface?.runtime?.reason ??
    diagnostics.operational_recovery_reason;
  const ledgerState =
    diagnostics.operator_state_surface?.ledger_sync?.state ??
    diagnostics.canonical_ledger_sync_state;
  const ledgerReason =
    diagnostics.operator_state_surface?.ledger_sync?.reason ??
    diagnostics.canonical_ledger_sync_reason;

  return {
    runtimeLabel: formatOperatorRuntimeState(runtimeState),
    runtimeReason: runtimeReason ?? "Операционный статус ещё уточняется.",
    ledgerLabel: formatLedgerSyncState(ledgerState),
    ledgerReason: ledgerReason ?? "Состояние синхронизации ledger ещё уточняется.",
  };
}

function formatFlowStatus(snapshot: BybitConnectorSymbolSnapshotResponse): string {
  if (snapshot.trade_ingest_seen && snapshot.orderbook_ingest_seen) {
    return "Видели сделки и стакан";
  }
  if (snapshot.trade_ingest_seen) {
    return "Видели только сделки";
  }
  if (snapshot.orderbook_ingest_seen) {
    return "Видели только стакан";
  }
  return "В этой сессии ещё не видели";
}

function getConnectorHumanStatus(
  diagnostics: BybitConnectorDiagnosticsResponse,
): { headline: string; detail: string; tone: "neutral" | "accent" | "success" | "warning" | "danger" } {
  if (!diagnostics.enabled) {
    return {
      headline: "Подключение выключено",
      detail: "Сейчас этот контур не получает данные. После включения система снова начнёт подключение и восстановление.",
      tone: "neutral",
    };
  }
  if (isWaitingForScopeDueToDiscovery(diagnostics)) {
    return {
      headline: "Ждём список инструментов",
      detail:
        "Bybit временно не отдал список рынка, поэтому контур пока не может собрать рабочий список и начать подключение. После восстановления discovery подключение продолжится автоматически.",
      tone: "warning",
    };
  }
  if (diagnostics.transport_status !== "connected") {
    return {
      headline: diagnostics.transport_status === "connecting" ? "Подключаемся" : "Нет соединения",
      detail:
        diagnostics.transport_status === "connecting"
          ? "Система устанавливает соединение и готовит поток данных."
          : "Связь с рынком временно потеряна. После возврата соединения восстановление продолжится автоматически.",
      tone: diagnostics.transport_status === "connecting" ? "warning" : "danger",
    };
  }
  if (diagnostics.historical_recovery_state === "backfilling") {
    return {
      headline: "Загружаем историю",
      detail: "Система подтягивает исторические сделки, чтобы собрать полную картину за последние 24 часа.",
      tone: "warning",
    };
  }
  if (
    diagnostics.universe_admission_state === "waiting_for_live_tail" ||
    diagnostics.derived_trade_count_state === "live_tail_pending_after_gap" ||
    (diagnostics.derived_trade_count_backfill_status === "backfilled" &&
      diagnostics.trade_count_filter_ready === false)
  ) {
    return {
      headline: "История загружена, ждём свежие сделки",
      detail: "Архив уже подгружен. Осталось добрать последние сделки из текущего потока, чтобы закрыть хвост без пропуска.",
      tone: "accent",
    };
  }
  if (
    diagnostics.operator_confidence_state === "streams_recovering" ||
    diagnostics.operator_confidence_state === "preserved_after_gap"
  ) {
    return {
      headline: "Данные восстанавливаются после переподключения",
      detail: "Прошлый контекст уже сохранён. Система добирает только свежие данные и не начинает всё с нуля.",
      tone: "warning",
    };
  }
  if (
    diagnostics.trade_count_product_truth_state === "ledger_confirmed" &&
    diagnostics.derived_trade_count_ready &&
    diagnostics.trade_count_filter_ready &&
    diagnostics.universe_admission_state === "ready_for_selection"
  ) {
    return {
      headline: "Контур в рабочем состоянии",
      detail:
        "Подтверждённое число по сделкам уже собрано, свежие сделки добраны, и колонка «Сделок за 24ч» согласована со своей продуктовой моделью. Основа для minTradeCount при этом остаётся отдельной.",
      tone: "success",
    };
  }
  if (diagnostics.trade_count_product_truth_state === "partial_ledger_coverage") {
    return {
      headline: "24ч truth ещё неполная",
      detail:
        "Trade ledger уже собрал live-часть окна, но полное rolling 24h покрытие ещё не доказано. Экран не считает это финальным truth.",
      tone: "warning",
    };
  }
  if (diagnostics.trade_count_product_truth_state === "reconciliation_mismatch") {
    return {
      headline: "Сделки требуют сверки",
      detail:
        "Число «Сделок за 24ч» пока не подтверждено: trade ledger и расчётный контур расходятся. Экран не выдаёт расчётное число за финальное.",
      tone: "danger",
    };
  }
  if (diagnostics.trade_count_product_truth_state === "ledger_unavailable") {
    return {
      headline: "Подтверждение недоступно",
      detail:
        "Показанное число сделок за 24 часа пока не подтверждено trade ledger. Если trade-count filter активен, admission всё ещё живёт на отдельном расчётном контуре.",
      tone: "warning",
    };
  }
  if (diagnostics.trade_count_product_truth_state === "pending_validation") {
    return {
      headline: "Проверяем 24ч trade count",
      detail:
        "Admission уже может продолжаться по своему контуру, но подтверждённое число для колонки «Сделок за 24ч» ещё не готово.",
      tone: "warning",
    };
  }
  const missingAutomaticSelectionTruth =
    diagnostics.scope_mode !== "universe" ||
    diagnostics.total_instruments_discovered === null ||
    diagnostics.instruments_passed_coarse_filter === null;
  if (missingAutomaticSelectionTruth) {
    return {
      headline: "Ждём состояние отбора",
      detail:
        "Подключение уже живо, но данные discovery и отбора ещё не подтверждены. Контур продолжает синхронизацию автоматически.",
      tone: "warning",
    };
  }
  return {
    headline: "Данные обновляются",
    detail: "Подключение активно, система поддерживает рабочее состояние и следит за целостностью данных.",
    tone: "accent",
  };
}

function renderControlCard(args: {
  label: string;
  description: string;
  recommended: string;
  children: ReactNode;
}) {
  return (
    <div className={`${settingsFieldCard} ${connectorControlCard}`}>
      <div className={settingsFieldHeader}>
        <div className={fieldLabel}>{args.label}</div>
        <div className={settingsFieldMeta}>Рекомендация: {args.recommended}</div>
      </div>
      <div className={fieldDescription}>{args.description}</div>
      {args.children}
    </div>
  );
}

function renderInstrumentTable(
  diagnostics: BybitConnectorDiagnosticsResponse,
  options?: {
    persistedTradeCountBySymbol?: Map<string, number>;
  },
) {
  if (diagnostics.symbol_snapshots.length === 0) {
    return (
      <div className={connectorEmptyState}>
        <div className={stateValue}>Инструменты ещё не появились</div>
        <div className={exchangeMeta}>
          Как только подключение соберёт рабочий список, здесь появится таблица по каждому инструменту.
        </div>
      </div>
    );
  }

  const flowStatuses = diagnostics.symbol_snapshots.map((snapshot) => formatFlowStatus(snapshot));
  const shouldShowFlowColumn = new Set(flowStatuses).size > 1;

  return (
    <div className={connectorTableWrap}>
      <table className={connectorTable}>
        <thead>
          <tr>
            <th className={connectorTableHeadCell}>Инструмент</th>
            <th className={connectorTableHeadCell}>Объём за 24ч</th>
            <th className={connectorTableHeadCell}>Сделок за 24ч</th>
            {shouldShowFlowColumn ? (
            <th className={connectorTableHeadCell}>Ingest в сессии</th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {diagnostics.symbol_snapshots.map((snapshot, index) => {
            const persistedTradeCount =
              options?.persistedTradeCountBySymbol?.get(snapshot.symbol) ?? null;
            return (
              <tr key={snapshot.symbol}>
                <td className={connectorTableBodyCell}>{snapshot.symbol}</td>
                <td className={connectorTableBodyCell}>{formatUsdVolume(snapshot.volume_24h_usd)}</td>
                <td className={connectorTableBodyCell}>
                  {persistedTradeCount !== null
                    ? formatNumber(persistedTradeCount)
                    : formatTradeCount(snapshot)}
                </td>
                {shouldShowFlowColumn ? (
                  <td className={connectorTableBodyCell}>
                    <span className={connectorFlowPill}>{flowStatuses[index]}</span>
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function renderConnectorPanel(args: {
  title: string;
  diagnostics: BybitConnectorDiagnosticsResponse;
  enabledByPolicy: boolean;
  onToggle?: () => void;
  isPending?: boolean;
  accentClassName: string;
  testId: string;
}) {
  const { diagnostics } = args;
  const humanStatus = getConnectorHumanStatus(diagnostics);
  const toggleLabel = diagnostics.enabled ? "Отключить" : "Подключить";
  const operatorStateSurface = getOperatorStateSurfaceSummary(diagnostics);

  return (
    <section
      className={`${connectorPanel} ${args.accentClassName}`}
      data-testid={`connector-panel-${args.testId}`}
    >
      <div className={connectorPanelHeader}>
        <div className={connectorPanelIntro}>
          <div className={stateValue}>{args.title}</div>
        </div>
        {args.onToggle ? (
          <button
            type="button"
            className={exchangeToggle}
            disabled={!args.enabledByPolicy || args.isPending}
            onClick={args.onToggle}
          >
            {args.isPending ? "Переключаю..." : toggleLabel}
          </button>
        ) : null}
      </div>

      <div className={connectorStatusCard}>
        <div className={connectorStatusLabel}>Главный статус</div>
        <div className={connectorStatusValue}>{humanStatus.headline}</div>
        <div className={connectorStatusDetail}>{humanStatus.detail}</div>
        <div>
          <TerminalBadge tone={humanStatus.tone}>{humanStatus.headline}</TerminalBadge>
        </div>
      </div>

      <div className={connectorStatsGrid}>
        <div
          className={connectorStatusCard}
          data-testid={`connector-operator-state-${args.testId}`}
        >
          <div className={connectorStatusLabel}>Операционный статус</div>
          <div className={stateValue}>
            {operatorStateSurface.runtimeLabel} · {operatorStateSurface.ledgerLabel}
          </div>
          <div className={exchangeMeta}>
            Runtime: {operatorStateSurface.runtimeReason} Ledger: {operatorStateSurface.ledgerReason}
          </div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Подключение</div>
          <div className={stateValue}>
            {isWaitingForScopeDueToDiscovery(diagnostics)
              ? "Ждёт список инструментов"
              : formatTransportStatus(diagnostics.transport_status)}
          </div>
          <div className={exchangeMeta}>
            {isWaitingForScopeDueToDiscovery(diagnostics)
              ? "Подключение начнётся автоматически."
              : `Последнее сообщение: ${formatDiagnosticsTimestamp(diagnostics.last_message_at)}`}
          </div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Восстановление</div>
          <div className={stateValue}>{formatRecoveryStatus(diagnostics.recovery_status)}</div>
          <div className={exchangeMeta}>{getRecoveryDetail(diagnostics)}</div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Режим работы</div>
          <div className={stateValue}>{formatScopeMode(diagnostics.scope_mode)}</div>
          <div className={exchangeMeta}>
            Инструментов в работе: {formatNumber(diagnostics.active_subscribed_scope_count)}
          </div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Отбор инструментов</div>
          <div className={stateValue}>
            {formatNumber(diagnostics.total_instruments_discovered)}
          </div>
          <div className={exchangeMeta}>
            Найдено всего: {formatNumber(diagnostics.total_instruments_discovered)} · После фильтра:{" "}
            {formatNumber(diagnostics.instruments_passed_coarse_filter)} · В работе:{" "}
            {formatNumber(diagnostics.active_subscribed_scope_count)}
          </div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Проверка данных</div>
          <div className={stateValue}>
            {formatTradeCountVerificationLabel(diagnostics)}
          </div>
          <div className={exchangeMeta}>{getTradeCountVerificationDetail(diagnostics)}</div>
        </div>
        <div
          className={connectorStatusCard}
          data-testid={`connector-product-truth-${args.testId}`}
          data-truth-surface="product"
          data-truth-basis="ledger"
        >
          <div className={connectorStatusLabel}>Truth колонки «Сделок за 24ч»</div>
          <div className={stateValue}>
            {formatTradeCountTruthModelLabel(diagnostics)}
          </div>
          <div className={exchangeMeta}>{getTradeCountTruthModelDetail(diagnostics)}</div>
        </div>
        <div
          className={connectorStatusCard}
          data-testid={`connector-admission-basis-${args.testId}`}
          data-truth-surface="admission"
          data-truth-basis={
            diagnostics.trade_count_admission_basis === "derived_operational_truth"
              ? "derived-operational"
              : "inactive"
          }
        >
          <div className={connectorStatusLabel}>Основа admission по minTradeCount</div>
          <div className={stateValue}>{formatTradeCountAdmissionLabel(diagnostics)}</div>
          <div className={exchangeMeta}>{getTradeCountAdmissionDetail(diagnostics)}</div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>RTT</div>
          <div className={stateValue}>
            {typeof diagnostics.transport_rtt_ms === "number"
              ? `${diagnostics.transport_rtt_ms} мс`
              : diagnostics.transport_status === "connected" &&
                  typeof diagnostics.application_heartbeat_latency_ms === "number"
                ? "Временно недоступен"
                : "Нет данных"}
          </div>
          <div className={exchangeMeta}>
            {diagnostics.transport_status === "connected" &&
            diagnostics.transport_rtt_ms === null &&
            typeof diagnostics.application_heartbeat_latency_ms === "number"
              ? "Поток жив, но RTT сейчас без числа."
              : "Transport ping/pong."}
          </div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Ответ heartbeat биржи</div>
          <div className={stateValue}>
            {typeof diagnostics.application_heartbeat_latency_ms === "number"
              ? `${diagnostics.application_heartbeat_latency_ms} мс`
              : "Нет данных"}
          </div>
          <div className={exchangeMeta}>Ответ Bybit на application ping.</div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Переподключения за запуск</div>
          <div className={stateValue}>{formatNumber(diagnostics.retry_count)}</div>
          <div className={exchangeMeta}>{getReconnectHistoryDetail(diagnostics)}</div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Последнее сообщение</div>
          <div className={stateValue}>{formatDiagnosticsTimestamp(diagnostics.last_message_at)}</div>
          <div className={exchangeMeta}>Последний входящий пакет данных.</div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Настройки</div>
          <div className={stateValue}>{formatApplyStatus(diagnostics.policy_apply_status)}</div>
          <div className={exchangeMeta}>
            {diagnostics.policy_apply_reason
              ? formatConnectorProblemReason(diagnostics.policy_apply_reason)
              : "Сохранённые настройки и текущее поведение синхронизированы."}
          </div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Потоки данных</div>
          <div className={stateValue}>
            {formatNumber(diagnostics.live_trade_streams_count)} / {formatNumber(diagnostics.live_orderbook_count)}
          </div>
          <div className={exchangeMeta}>Сделки / стаканы.</div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Последнее отключение</div>
          <div className={stateValue}>
            {diagnostics.last_disconnect_reason
              ? formatConnectorProblemReason(diagnostics.last_disconnect_reason)
              : "Отключений не было"}
          </div>
          <div className={exchangeMeta}>
            Последняя зафиксированная причина разрыва соединения.
          </div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Текущая проблема</div>
          <div className={stateValue}>
            {diagnostics.degraded_reason
              ? formatConnectorProblemReason(diagnostics.degraded_reason)
              : "Явной проблемы сейчас нет"}
          </div>
          <div className={exchangeMeta}>
            {diagnostics.degraded_reason
              ? "То, что мешает контуру работать в нормальном режиме прямо сейчас."
              : "Контур сейчас не сообщает о явной деградации."}
          </div>
        </div>
      </div>

      <div className={connectorPanelIntro}>
        <div className={stateValue}>Текущий список инструментов</div>
        <div
          className={connectorSemanticNote}
          data-testid={`connector-semantic-note-${args.testId}`}
          data-truth-split-visible="true"
        >
          {getTradeCountSemanticSummary(diagnostics)}
        </div>
      </div>
      {renderInstrumentTable(diagnostics)}
    </section>
  );
}

function renderSpotV2Panel(args: {
  diagnostics: BybitSpotV2DiagnosticsResponse;
}) {
  const { diagnostics } = args;

  return (
    <section
      className={`${connectorPanel} ${connectorPanelV2}`}
      data-testid="connector-panel-spot-v2"
    >
      <div className={connectorPanelHeader}>
        <div className={connectorPanelIntro}>
          <div className={stateValue}>Bybit Spot V2</div>
          <div className={exchangeMeta}>Основной рабочий spot-контур.</div>
        </div>
        <TerminalBadge tone="accent">{diagnostics.generation.toUpperCase()}</TerminalBadge>
      </div>

      <div className={connectorStatusCard}>
        <div className={connectorStatusLabel}>Состояние контура</div>
        <div className={connectorStatusValue}>{getSpotV2WorkingStatus(diagnostics)}</div>
        <div className={connectorStatusDetail}>
          Подключение {formatTransportStatus(diagnostics.transport.transport_status ?? "idle")} ·
          поток {diagnostics.transport.subscription_alive ? " активен" : " неактивен"}
        </div>
      </div>

      <div className={connectorStatsGrid}>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Transport</div>
          <div className={stateValue}>
            {formatTransportStatus(diagnostics.transport.transport_status ?? "idle")}
          </div>
          <div className={exchangeMeta}>
            RTT:{" "}
            {typeof diagnostics.transport.transport_rtt_ms === "number"
              ? `${diagnostics.transport.transport_rtt_ms} мс`
              : "Нет данных"}{" "}
            · Последнее сообщение: {formatDiagnosticsTimestamp(diagnostics.transport.last_message_at)}
          </div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Ingest</div>
          <div className={stateValue}>
            {diagnostics.ingest.trade_seen ? "Trade seen" : "Trade pending"} ·{" "}
            {diagnostics.ingest.orderbook_seen ? "Orderbook seen" : "Orderbook pending"}
          </div>
          <div className={exchangeMeta}>
            Best bid / ask: {diagnostics.ingest.best_bid ?? "Нет данных"} /{" "}
            {diagnostics.ingest.best_ask ?? "Нет данных"}
          </div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Persistence 24ч</div>
          <div className={stateValue}>
            {formatNumber(diagnostics.persistence.live_trade_count_24h)} /{" "}
            {formatNumber(diagnostics.persistence.archive_trade_count_24h)} /{" "}
            {formatNumber(diagnostics.persistence.persisted_trade_count_24h)}
          </div>
          <div className={exchangeMeta}>
            Live / Archive / Total · окно count contract:{" "}
            {formatDiagnosticsTimestamp(diagnostics.persistence.count_window_started_at)} →{" "}
            {formatDiagnosticsTimestamp(diagnostics.persistence.window_ended_at)}
          </div>
          <div className={exchangeMeta}>
            Первая / последняя persisted trade внутри окна:{" "}
            {formatDiagnosticsTimestamp(diagnostics.persistence.first_persisted_trade_at)} /{" "}
            {formatDiagnosticsTimestamp(diagnostics.persistence.last_persisted_trade_at)}
          </div>
          <div className={exchangeMeta}>
            Левая граница raw 24ч окна:{" "}
            {formatDiagnosticsTimestamp(diagnostics.persistence.requested_window_started_at)}
          </div>
        </div>
        <div className={connectorStatusCard}>
          <div className={connectorStatusLabel}>Поток сообщений</div>
          <div className={stateValue}>
            {formatNumber(diagnostics.transport.messages_received_count)}
          </div>
          <div className={exchangeMeta}>
            Trade ingest: {formatNumber(diagnostics.ingest.trade_ingest_count)} · Orderbook ingest:{" "}
            {formatNumber(diagnostics.ingest.orderbook_ingest_count)}
          </div>
        </div>
      </div>

      <div className={connectorPanelIntro}>
        <div className={stateValue}>Инструменты</div>
      </div>

      <div className={connectorTableWrap}>
        <table className={connectorTable}>
          <thead>
            <tr>
              <th className={connectorTableHeadCell}>Инструмент</th>
              <th className={connectorTableHeadCell}>Persisted 24ч</th>
              <th className={connectorTableHeadCell}>Покрытие 24ч</th>
            </tr>
          </thead>
          <tbody>
            {diagnostics.reconciliation.symbols.map((snapshot) => (
              <tr key={snapshot.normalized_symbol}>
                <td className={connectorTableBodyCell}>{snapshot.normalized_symbol}</td>
                <td className={connectorTableBodyCell}>
                  {formatNumber(snapshot.persisted_trade_count_24h)}
                </td>
                <td className={connectorTableBodyCell}>
                  {diagnostics.persistence.symbols_covered.includes(snapshot.normalized_symbol)
                    ? "Есть данные"
                    : "Нет данных"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function renderPrimarySpotPanel(args: {
  snapshot: BybitSpotProductSnapshotResponse;
  onToggle: () => void;
  isPending?: boolean;
  settingsContent?: ReactNode;
}) {
  const { snapshot } = args;
  const status = snapshot;
  const workingStatus = getSpotRuntimeWorkingStatus(status);
  const toggleLabel = status.desired_running ? "Отключить" : "Подключить";
  const lifecycleState = status.lifecycle_state ?? (status.desired_running ? "starting" : "stopped");
  const isLive = lifecycleState === "connected_live";
  const isStopped = lifecycleState === "stopped";
  const liveSymbolsCount = lifecycleState === "stopped" ? 0 : snapshot.instrument_rows.length;
  const filteredSymbolsCount =
    typeof status.filtered_symbols_count === "number"
      ? status.filtered_symbols_count
      : status.selected_symbols_count;
  const volumeFilteredSymbolsCount =
    typeof status.volume_filtered_symbols_count === "number"
      ? status.volume_filtered_symbols_count
      : filteredSymbolsCount;
  const modeLabel = status.scope_mode === "universe" ? "Автоматический отбор" : "Нет данных";
  const persistenceCoverageStatus = snapshot.persistence_24h.coverage_status;
  const archiveCoveragePending =
    persistenceCoverageStatus === "pending_archive" ||
    persistenceCoverageStatus === "pending_exact:pending_archive";
  const streamStatus =
    lifecycleState === "stopped"
      ? "Остановлен"
      : lifecycleState === "connected_live"
        ? "Данные поступают"
        : lifecycleState === "degraded"
          ? "Нужна проверка"
          : "Ещё не работает";
  const currentProblem =
    lifecycleState === "stopped"
      ? "Коннектор остановлен оператором"
      : archiveCoveragePending
        ? "Archive coverage ещё достраивается"
      : lifecycleState === "starting" || lifecycleState === "connected_no_flow"
        ? "Коннектор ещё не вышел в рабочее состояние"
        : lifecycleState === "degraded"
          ? "Состояние контура требует проверки"
          : "Явной проблемы сейчас нет";
  const persistenceCaption =
    archiveCoveragePending
      ? "Live / Archive / Total · archive pending"
      : lifecycleState === "connected_live"
        ? "Live / Archive / Total"
      : lifecycleState === "stopped"
        ? "Исторический снимок за последние 24ч"
        : "Подтверждённый снимок 24ч, live-поток ещё не подтверждён";
  const statusToneClass =
    lifecycleState === "connected_live"
      ? connectorStatusHeroSuccess
      : connectorStatusHeroNeutral;
  const instrumentSummary =
    typeof status.total_instruments_discovered === "number"
      ? `Найдено всего: ${formatNumber(status.total_instruments_discovered)} · После объёма: ${formatNumber(volumeFilteredSymbolsCount)} · После сделок: ${formatNumber(filteredSymbolsCount)}`
      : `После объёма: ${formatNumber(volumeFilteredSymbolsCount)} · После сделок: ${formatNumber(filteredSymbolsCount)}`;
  const instrumentTableTitle =
    lifecycleState === "connected_live" ? "Инструменты в работе" : "Рабочий список инструментов";

  return (
    <section
      className={`${connectorPanel} ${connectorPanelSpot}`}
      data-testid="connector-panel-spot-primary"
    >
      <div className={connectorPanelHeader}>
        <div className={connectorPanelIntro}>
          <div className={stateValue}>Спотовый рынок</div>
        </div>
        <button
          type="button"
          className={exchangeToggle}
          disabled={args.isPending}
          onClick={args.onToggle}
        >
          {args.isPending ? "Переключаю..." : toggleLabel}
        </button>
      </div>

      {args.settingsContent ? args.settingsContent : null}

      <div className={`${connectorStatusCard} ${connectorStatusHero} ${statusToneClass}`}>
        <div>
          <TerminalBadge tone={isLive ? "success" : lifecycleState === "degraded" ? "danger" : "neutral"}>
            {workingStatus}
          </TerminalBadge>
        </div>
      </div>

      {!isLive ? (
        <div className={connectorEmptyState}>
          <div className={stateValue}>
            {isStopped ? "Спотовый коннектор остановлен" : "Коннектор ещё не вышел в рабочее состояние"}
          </div>
          <div className={exchangeMeta}>
            {isStopped
              ? "Коннектор сейчас не работает. Основные рабочие данные появятся только после запуска и подтверждения live-потока."
              : lifecycleState === "degraded"
                ? "Контур требует проверки и ещё не может считаться рабочим."
                : "Коннектор ещё не работает: рабочая таблица, persistence и runtime-метрики появятся только после подтверждения live-потока."}
          </div>
        </div>
      ) : null}

      {isLive ? (
        <>
          <div className={connectorStatsGrid}>
            <div className={connectorStatusCard}>
              <div className={connectorStatusLabel}>Подключение</div>
              <div className={stateValue}>{getSpotRuntimeConnectionLabel(status)}</div>
              <div className={exchangeMeta}>
                Последнее сообщение: {formatDiagnosticsTimestamp(status.last_message_at)}
              </div>
            </div>
            <div className={connectorStatusCard}>
              <div className={connectorStatusLabel}>Живой поток</div>
              <div className={stateValue}>{streamStatus}</div>
              <div className={exchangeMeta}>
                Инструментов в работе: {formatNumber(liveSymbolsCount)}
              </div>
            </div>
            <div className={connectorStatusCard}>
              <div className={connectorStatusLabel}>Инструменты</div>
              <div className={stateValue}>{formatNumber(liveSymbolsCount)}</div>
              <div className={exchangeMeta}>
                Режим: {modeLabel}
                {instrumentSummary ? ` · ${instrumentSummary}` : ""}
              </div>
            </div>
            <div className={connectorStatusCard}>
              <div className={connectorStatusLabel}>RTT</div>
              <div className={stateValue}>
                {typeof status.transport_rtt_ms === "number"
                  ? `${status.transport_rtt_ms} мс`
                  : "Нет данных"}
              </div>
              <div className={exchangeMeta}>Transport ping/pong.</div>
            </div>
            <div className={connectorStatusCard}>
              <div className={connectorStatusLabel}>Последнее сообщение</div>
              <div className={stateValue}>{formatDiagnosticsTimestamp(status.last_message_at)}</div>
              <div className={exchangeMeta}>Последний входящий пакет данных.</div>
            </div>
            <div className={connectorStatusCard}>
              <div className={connectorStatusLabel}>Потоки данных</div>
              <div className={stateValue}>
                {formatNumber(status.trade_ingest_count)} / {formatNumber(status.orderbook_ingest_count)}
              </div>
              <div className={exchangeMeta}>Сделки / стаканы.</div>
            </div>
            <div className={connectorStatusCard}>
              <div className={connectorStatusLabel}>Переподключения за запуск</div>
              <div className={stateValue}>{formatNumber(status.retry_count)}</div>
              <div className={exchangeMeta}>
                {status.retry_count === 0
                  ? "С начала текущего запуска переподключений не было."
                  : "Исторический счётчик переподключений за текущий запуск."}
              </div>
            </div>
            <div className={connectorStatusCard}>
              <div className={connectorStatusLabel}>Persistence 24ч</div>
              <div className={stateValue}>
                {formatNumber(snapshot.persistence_24h.live_trade_count_24h)} /{" "}
                {formatNumber(snapshot.persistence_24h.archive_trade_count_24h)} /{" "}
                {formatNumber(snapshot.persistence_24h.persisted_trade_count_24h)}
              </div>
              <div className={exchangeMeta}>
                {persistenceCaption} · Последняя запись:{" "}
                {formatDiagnosticsTimestamp(snapshot.persistence_24h.last_persisted_trade_at)}
              </div>
            </div>
            <div className={connectorStatusCard}>
              <div className={connectorStatusLabel}>Текущая проблема</div>
              <div className={stateValue}>{currentProblem}</div>
              <div className={exchangeMeta}>
                {status.recovery_reason
                  ? "Если поток прервётся, система попробует восстановить подключение автоматически."
                  : status.desired_running
                    ? "Если поток остановится, восстановление запустится автоматически."
                    : "Live-runtime остановлен и не должен восприниматься как активный поток."}
              </div>
            </div>
          </div>

          <div className={connectorPanelIntro}>
            <div className={stateValue}>{instrumentTableTitle}</div>
          </div>

          {snapshot.instrument_rows.length === 0 ? (
            <div className={connectorEmptyState}>
              {snapshot.selected_symbols_count === 0 ? (
                <>
                  <div className={stateValue}>По текущим фильтрам инструменты не прошли</div>
                  <div className={exchangeMeta}>
                    Canonical product snapshot уже подтвердил пустой рабочий список для текущих spot-параметров. Измените фильтры, если нужен непустой набор инструментов.
                  </div>
                </>
              ) : (
                <>
                  <div className={stateValue}>Live scope ещё не появился</div>
                  <div className={exchangeMeta}>
                    Основной статус уже берётся из canonical product snapshot. Таблица появится, как только рабочий список закрепится в spot runtime.
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className={connectorTableWrap}>
              <table className={connectorTable}>
                <thead>
                  <tr>
                    <th className={connectorTableHeadCell}>Инструмент</th>
                    <th className={connectorTableHeadCell}>Объём за 24ч</th>
                    <th className={connectorTableHeadCell}>Сделок за 24ч</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.instrument_rows.map((row) => (
                    <tr key={row.symbol}>
                      <td className={connectorTableBodyCell}>{row.symbol}</td>
                      <td className={connectorTableBodyCell}>{formatUsdVolume(row.volume_24h_usd)}</td>
                      <td className={connectorTableBodyCell}>
                        {formatSpotProductTradeCount(row.trade_count_24h, archiveCoveragePending)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}

export function TerminalConnectorsPage() {
  const queryClient = useQueryClient();
  const [selectedExchange, setSelectedExchange] = useState<SupportedExchange>("Bybit");
  const [liveFeedDraft, setLiveFeedDraft] = useState<LiveFeedPolicyDraft | null>(null);
  const [liveFeedSaveNotice, setLiveFeedSaveNotice] = useState<string | null>(null);

  const liveFeedPolicyQuery = useQuery({
    queryKey: ["dashboard", "settings", "live-feed-policy"],
    queryFn: getLiveFeedPolicySettings,
  });
  const bybitConnectorDiagnosticsQuery = useQuery({
    queryKey: ["dashboard", "settings", "bybit-connector-diagnostics"],
    queryFn: getBybitConnectorDiagnostics,
    refetchInterval: 5000,
  });
  const bybitSpotProductSnapshotQuery = useQuery({
    queryKey: ["dashboard", "settings", "bybit-spot-product-snapshot"],
    queryFn: getBybitSpotProductSnapshot,
    refetchInterval: 2000,
    enabled: selectedExchange === "Bybit",
  });
  useEffect(() => {
    if (liveFeedPolicyQuery.data) {
      setLiveFeedDraft(toLiveFeedPolicyDraft(liveFeedPolicyQuery.data));
    }
  }, [liveFeedPolicyQuery.data]);

  const liveFeedPolicyMutation = useMutation({
    mutationFn: updateLiveFeedPolicySettings,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "live-feed-policy"], data);
      setLiveFeedDraft(toLiveFeedPolicyDraft(data));
      setLiveFeedSaveNotice("Настройки подключения сохранены");
      void queryClient.invalidateQueries({
        queryKey: ["dashboard", "settings", "bybit-connector-diagnostics"],
      });
      void queryClient.invalidateQueries({
        queryKey: ["dashboard", "settings", "bybit-spot-product-snapshot"],
      });
    },
  });

  const bybitConnectorToggleMutation = useMutation({
    mutationFn: updateBybitConnectorEnabled,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "bybit-connector-diagnostics"], data);
    },
  });
  const bybitSpotRuntimeStateMutation = useMutation({
    mutationFn: updateBybitSpotRuntimeState,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["dashboard", "settings", "bybit-spot-product-snapshot"],
      });
    },
  });

  const liveFeedPayload = useMemo<LiveFeedPolicySettingsResponse | null>(() => {
    if (!liveFeedDraft) {
      return null;
    }

    const retryDelaySeconds = Number.parseInt(liveFeedDraft.retry_delay_seconds, 10);
    const bybitUniverseMinTradeCount24h = parseGroupedNumber(
      liveFeedDraft.bybit_spot_universe_min_trade_count_24h,
    );
    const payload: LiveFeedPolicySettingsResponse = {
      retry_delay_seconds: retryDelaySeconds,
      bybit_spot_universe_min_quote_volume_24h_usd: parseGroupedNumber(
        liveFeedDraft.bybit_spot_universe_min_quote_volume_24h_usd,
      ),
      bybit_spot_universe_min_trade_count_24h: bybitUniverseMinTradeCount24h,
      bybit_spot_quote_asset_filter: liveFeedDraft.bybit_spot_quote_asset_filter as
        | "usdt"
        | "usdc"
        | "usdt_usdc",
    };

    const hasInvalidNumber = [
      retryDelaySeconds,
      bybitUniverseMinTradeCount24h,
      payload.bybit_spot_universe_min_quote_volume_24h_usd,
    ].some((value) => Number.isNaN(value));

    return hasInvalidNumber ? null : payload;
  }, [liveFeedDraft]);

  const isLiveFeedDirty =
    !!liveFeedPolicyQuery.data &&
    !!liveFeedDraft &&
    JSON.stringify(toLiveFeedPolicyDraft(liveFeedPolicyQuery.data)) !==
      JSON.stringify(liveFeedDraft);

  const spotLoading =
    liveFeedPolicyQuery.isLoading || bybitSpotProductSnapshotQuery.isLoading;
  const spotError =
    liveFeedPolicyQuery.isError || bybitSpotProductSnapshotQuery.isError;
  const futuresLoading = bybitConnectorDiagnosticsQuery.isLoading;
  const futuresError = bybitConnectorDiagnosticsQuery.isError;

  const spotSettingsContent = (
    <div className={connectorConfigSection}>
      <div>
        <div className={sectionCaption}>Настройки spot</div>
      </div>

      {liveFeedPolicyQuery.isLoading ? (
        <div className={settingsErrorState}>Загружаю параметры подключения Bybit...</div>
      ) : null}

      {liveFeedPolicyQuery.isError ? (
        <div className={settingsErrorState}>
          Не удалось загрузить параметры подключения Bybit.
        </div>
      ) : null}

      {liveFeedPolicyMutation.isError ? (
        <div className={settingsErrorState}>
          Не удалось сохранить параметры подключения Bybit.
        </div>
      ) : null}

      {liveFeedDraft ? (
        <div className={settingsForm}>
          <div className={`${settingsFieldGrid} ${connectorControlGrid}`}>
            {renderControlCard({
              label: liveFeedControlFieldDefinitions.retryDelaySeconds.label,
              description: liveFeedControlFieldDefinitions.retryDelaySeconds.description,
              recommended: liveFeedControlFieldDefinitions.retryDelaySeconds.recommended,
              children: (
                <input
                  type="number"
                  inputMode="numeric"
                  step="1"
                  className={`${fieldInput} ${connectorControlInput}`}
                  value={liveFeedDraft.retry_delay_seconds}
                  onChange={(event) =>
                    updateLiveFeedDraftField("retry_delay_seconds", event.target.value)
                  }
                />
              ),
            })}
            {renderControlCard({
              label: liveFeedControlFieldDefinitions.minVolume.label,
              description: liveFeedControlFieldDefinitions.minVolume.description,
              recommended: liveFeedControlFieldDefinitions.minVolume.recommended,
              children: (
                <input
                  type="text"
                  inputMode="numeric"
                  className={`${fieldInput} ${connectorControlInput}`}
                  value={liveFeedDraft.bybit_spot_universe_min_quote_volume_24h_usd}
                  onChange={(event) =>
                    updateLiveFeedDraftField(
                      "bybit_spot_universe_min_quote_volume_24h_usd",
                      event.target.value,
                    )
                  }
                />
              ),
            })}
            {renderControlCard({
              label: liveFeedControlFieldDefinitions.quoteAssetFilter.label,
              description: liveFeedControlFieldDefinitions.quoteAssetFilter.description,
              recommended: liveFeedControlFieldDefinitions.quoteAssetFilter.recommended,
              children: (
                <select
                  className={`${fieldInput} ${connectorControlInput}`}
                  value={liveFeedDraft.bybit_spot_quote_asset_filter}
                  onChange={(event) =>
                    updateLiveFeedDraftField("bybit_spot_quote_asset_filter", event.target.value)
                  }
                >
                  <option value="usdt">USDT</option>
                  <option value="usdc">USDC</option>
                  <option value="usdt_usdc">USDT + USDC</option>
                </select>
              ),
            })}
            {renderControlCard({
              label: liveFeedControlFieldDefinitions.minTradeCount.label,
              description: liveFeedControlFieldDefinitions.minTradeCount.description,
              recommended: liveFeedControlFieldDefinitions.minTradeCount.recommended,
              children: (
                <input
                  type="text"
                  inputMode="numeric"
                  className={`${fieldInput} ${connectorControlInput}`}
                  value={liveFeedDraft.bybit_spot_universe_min_trade_count_24h}
                  onChange={(event) =>
                    updateLiveFeedDraftField(
                      "bybit_spot_universe_min_trade_count_24h",
                      event.target.value,
                    )
                  }
                />
              ),
            })}
          </div>

          <div className={modeControls}>
            <button
              type="button"
              className={`${modeButton} ${!isLiveFeedDirty || !liveFeedPayload || liveFeedPolicyMutation.isPending ? saveButtonDisabled : saveButton}`}
              disabled={!isLiveFeedDirty || !liveFeedPayload || liveFeedPolicyMutation.isPending}
              onClick={() => void handleLiveFeedPolicySave()}
            >
              {liveFeedPolicyMutation.isPending ? "Сохраняю..." : "Сохранить параметры Bybit"}
            </button>
          </div>

          {liveFeedSaveNotice ? (
            <div className={localStateNote}>{liveFeedSaveNotice}</div>
          ) : null}
        </div>
      ) : null}
    </div>
  );

  function updateLiveFeedDraftField(key: LiveFeedPolicyFieldKey, value: string) {
    setLiveFeedSaveNotice(null);
    setLiveFeedDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]:
          key === "bybit_spot_universe_min_quote_volume_24h_usd" ||
          key === "bybit_spot_universe_min_trade_count_24h"
            ? formatGroupedInteger(value)
            : value,
      };
    });
  }

  async function handleLiveFeedPolicySave() {
    if (!liveFeedPayload) {
      return;
    }
    await liveFeedPolicyMutation.mutateAsync(liveFeedPayload);
  }

  return (
    <div className={pageRoot}>
      <section className={settingsCard}>
        <div className={sectionHeader}>
          <div>
            <div className={sectionCaption}>Runtime-мониторинг</div>
            <h2 className={sectionTitle}>Коннекторы</h2>
          </div>
          <TerminalBadge tone="accent">{selectedExchange}</TerminalBadge>
        </div>

        <div className={sectionBody}>
          <div className={exchangeSelector}>
            {(["Bybit", "Binance", "OKX"] as const).map((exchange) => (
              <button
                key={exchange}
                type="button"
                className={`${exchangeSelectorButton} ${selectedExchange === exchange ? exchangeSelectorButtonActive : ""}`}
                onClick={() => setSelectedExchange(exchange)}
              >
                {exchange}
              </button>
            ))}
          </div>
        </div>
      </section>

      {selectedExchange !== "Bybit" ? (
        <section className={settingsCard}>
          <div className={sectionHeader}>
            <div>
              <div className={sectionCaption}>Биржа</div>
              <h2 className={sectionTitle}>{selectedExchange}</h2>
            </div>
          </div>
          <div className={connectorEmptyState}>
            <div className={stateValue}>Экран коннекторов для этой биржи появится позже</div>
            <div className={exchangeMeta}>Параметры и мониторинг появятся позже.</div>
          </div>
        </section>
      ) : null}

      {selectedExchange === "Bybit" ? (
        <section className={settingsCard}>
          <div className={sectionHeader}>
            <div>
              <div className={sectionCaption}>Биржа</div>
              <h2 className={sectionTitle}>Bybit</h2>
            </div>
          </div>

          <div className={sectionBody}>
            <div className={connectorConfigGrid}>
              <div className={connectorConfigSection}>
                <div>
                  <div className={sectionCaption}>Параметры futures</div>
                  <div className={stateValue}>Управление futures вынесено в панель ниже</div>
                </div>
                <div className={exchangeMeta}>
                  Для бессрочных фьючерсов используется отдельный рабочий блок. Спотовые параметры выше относятся только к spot-контуру.
                </div>
              </div>
            </div>

            <div className={connectorPanels}>
              {futuresLoading ? (
                <div className={settingsErrorState}>Загружаю состояние futures-контура...</div>
              ) : null}

              {futuresError ? (
                <div className={settingsErrorState}>
                  Не удалось загрузить текущее состояние futures-контура.
                </div>
              ) : null}

              {!futuresLoading && !futuresError && bybitConnectorDiagnosticsQuery.data
                ? renderConnectorPanel({
                    title: "Бессрочные фьючерсы",
                    diagnostics: bybitConnectorDiagnosticsQuery.data,
                    testId: "futures",
                    enabledByPolicy: true,
                    isPending: bybitConnectorToggleMutation.isPending,
                    accentClassName: connectorPanelFuture,
                    onToggle: () => {
                      void bybitConnectorToggleMutation.mutateAsync({
                        enabled: !bybitConnectorDiagnosticsQuery.data.enabled,
                      });
                    },
                  })
                : null}

              {spotLoading ? (
                <div className={settingsErrorState}>Загружаю текущее состояние spot-контура...</div>
              ) : null}

              {spotError ? (
                <div className={settingsErrorState}>
                  Не удалось загрузить текущее состояние spot-контура.
                </div>
              ) : null}

              {!spotLoading && !spotError && bybitSpotProductSnapshotQuery.data
                ? renderPrimarySpotPanel({
                    snapshot: bybitSpotProductSnapshotQuery.data,
                    onToggle: () => {
                      void bybitSpotRuntimeStateMutation.mutateAsync({
                        enabled: !bybitSpotProductSnapshotQuery.data.desired_running,
                      });
                    },
                    isPending: bybitSpotRuntimeStateMutation.isPending,
                    settingsContent: spotSettingsContent,
                  })
                : null}
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}
