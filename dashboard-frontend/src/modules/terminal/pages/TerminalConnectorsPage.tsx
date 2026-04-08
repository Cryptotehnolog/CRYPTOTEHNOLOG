import { type ReactNode, useEffect, useMemo, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { TerminalBadge } from "../components/TerminalBadge";
import { getBybitConnectorDiagnostics } from "../api/getBybitConnectorDiagnostics";
import { getBybitSpotConnectorDiagnostics } from "../api/getBybitSpotConnectorDiagnostics";
import { getLiveFeedPolicySettings } from "../api/getLiveFeedPolicySettings";
import { updateLiveFeedPolicySettings } from "../api/updateLiveFeedPolicySettings";
import { updateBybitConnectorEnabled } from "../api/updateBybitConnectorEnabled";
import { updateBybitSpotConnectorEnabled } from "../api/updateBybitSpotConnectorEnabled";
import type {
  BybitConnectorDiagnosticsResponse,
  BybitConnectorSymbolSnapshotResponse,
  LiveFeedPolicySettingsResponse,
} from "../../../shared/types/dashboard";
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
  connectorPanelSpot,
  connectorPanels,
  connectorStatsGrid,
  connectorStatusCard,
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
type LiveFeedPolicyFieldKey = keyof LiveFeedPolicySettingsResponse;
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
      "Дополнительный фильтр для автоматического отбора. Значение 0 отключает фильтр по числу сделок.",
    recommended: "200 000 или 0, если фильтр не нужен",
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
    bybit_universe_min_quote_volume_24h_usd: formatGroupedInteger(
      String(values.bybit_universe_min_quote_volume_24h_usd),
    ),
    bybit_universe_min_trade_count_24h: formatGroupedInteger(
      String(values.bybit_universe_min_trade_count_24h),
    ),
    bybit_universe_max_symbols_per_scope: String(values.bybit_universe_max_symbols_per_scope),
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
    notation: parsed >= 1_000_000 ? "compact" : "standard",
    maximumFractionDigits: parsed >= 1_000_000 ? 1 : 0,
  }).format(parsed);
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

function formatTradeCount(snapshot: BybitConnectorSymbolSnapshotResponse): string {
  if (typeof snapshot.derived_trade_count_24h === "number") {
    return formatNumber(snapshot.derived_trade_count_24h);
  }
  if (snapshot.observed_trade_count_since_reset > 0) {
    return `Собираем · ${formatNumber(snapshot.observed_trade_count_since_reset)}`;
  }
  return "Собираем";
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

function formatFlowStatus(snapshot: BybitConnectorSymbolSnapshotResponse): string {
  if (snapshot.trade_seen && snapshot.orderbook_seen) {
    return "Сделки и стакан";
  }
  if (snapshot.trade_seen) {
    return "Только сделки";
  }
  if (snapshot.orderbook_seen) {
    return "Только стакан";
  }
  return "Поток ещё не пришёл";
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
    diagnostics.derived_trade_count_ready &&
    diagnostics.trade_count_filter_ready &&
    diagnostics.universe_admission_state === "ready_for_selection"
  ) {
    return {
      headline: "Данные собраны полностью",
      detail: "История загружена, свежие сделки добраны, и итоговый отбор опирается на непрерывные данные без неподтверждённого разрыва.",
      tone: "success",
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
              <th className={connectorTableHeadCell}>Поток данных</th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {diagnostics.symbol_snapshots.map((snapshot, index) => (
            <tr key={snapshot.symbol}>
              <td className={connectorTableBodyCell}>{snapshot.symbol}</td>
              <td className={connectorTableBodyCell}>{formatUsdVolume(snapshot.volume_24h_usd)}</td>
              <td className={connectorTableBodyCell}>{formatTradeCount(snapshot)}</td>
              {shouldShowFlowColumn ? (
                <td className={connectorTableBodyCell}>
                  <span className={connectorFlowPill}>{flowStatuses[index]}</span>
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderConnectorPanel(args: {
  title: string;
  diagnostics: BybitConnectorDiagnosticsResponse;
  enabledByPolicy: boolean;
  onToggle: () => void;
  isPending: boolean;
  accentClassName: string;
}) {
  const { diagnostics } = args;
  const humanStatus = getConnectorHumanStatus(diagnostics);
  const toggleLabel = diagnostics.enabled ? "Отключить" : "Подключить";

  return (
    <section className={`${connectorPanel} ${args.accentClassName}`}>
      <div className={connectorPanelHeader}>
        <div className={connectorPanelIntro}>
          <div className={stateValue}>{args.title}</div>
        </div>
        <button
          type="button"
          className={exchangeToggle}
          disabled={!args.enabledByPolicy || args.isPending}
          onClick={args.onToggle}
        >
          {args.isPending ? "Переключаю..." : toggleLabel}
        </button>
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
            {diagnostics.trade_count_filter_ready ? "Подтверждена" : "Ещё идёт"}
          </div>
          <div className={exchangeMeta}>
            Финальный отбор:{" "}
            {diagnostics.universe_admission_state === "ready_for_selection"
              ? "готов"
              : diagnostics.universe_admission_state === "waiting_for_live_tail"
                ? "ждёт последние сделки"
              : "ещё не готов"}
          </div>
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
          <div className={connectorStatusLabel}>Повторные попытки</div>
          <div className={stateValue}>{formatNumber(diagnostics.retry_count)}</div>
          <div className={exchangeMeta}>
            Сколько раз контур заново подключался после разрыва связи в текущем окне.
          </div>
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
      </div>
      {renderInstrumentTable(diagnostics)}
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
  const bybitSpotConnectorDiagnosticsQuery = useQuery({
    queryKey: ["dashboard", "settings", "bybit-spot-connector-diagnostics"],
    queryFn: getBybitSpotConnectorDiagnostics,
    refetchInterval: 5000,
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
        queryKey: ["dashboard", "settings", "bybit-spot-connector-diagnostics"],
      });
    },
  });

  const bybitConnectorToggleMutation = useMutation({
    mutationFn: updateBybitConnectorEnabled,
    onSuccess: (data) => {
      queryClient.setQueryData(["dashboard", "settings", "bybit-connector-diagnostics"], data);
    },
  });
  const bybitSpotConnectorToggleMutation = useMutation({
    mutationFn: updateBybitSpotConnectorEnabled,
    onSuccess: (data) => {
      queryClient.setQueryData(
        ["dashboard", "settings", "bybit-spot-connector-diagnostics"],
        data,
      );
    },
  });

  const liveFeedPayload = useMemo<LiveFeedPolicySettingsResponse | null>(() => {
    if (!liveFeedDraft) {
      return null;
    }

    const retryDelaySeconds = Number.parseInt(liveFeedDraft.retry_delay_seconds, 10);
    const bybitUniverseMinTradeCount24h = parseGroupedNumber(
      liveFeedDraft.bybit_universe_min_trade_count_24h,
    );
    const bybitUniverseMaxSymbolsPerScope = Number.parseInt(
      liveFeedDraft.bybit_universe_max_symbols_per_scope,
      10,
    );

    const payload: LiveFeedPolicySettingsResponse = {
      retry_delay_seconds: retryDelaySeconds,
      bybit_universe_min_quote_volume_24h_usd: parseGroupedNumber(
        liveFeedDraft.bybit_universe_min_quote_volume_24h_usd,
      ),
      bybit_universe_min_trade_count_24h: bybitUniverseMinTradeCount24h,
      bybit_universe_max_symbols_per_scope: bybitUniverseMaxSymbolsPerScope,
    };

    const hasInvalidNumber = [
      retryDelaySeconds,
      bybitUniverseMinTradeCount24h,
      bybitUniverseMaxSymbolsPerScope,
      payload.bybit_universe_min_quote_volume_24h_usd,
    ].some((value) => Number.isNaN(value));

    return hasInvalidNumber ? null : payload;
  }, [liveFeedDraft]);

  const isLiveFeedDirty =
    !!liveFeedPolicyQuery.data &&
    !!liveFeedDraft &&
    JSON.stringify(toLiveFeedPolicyDraft(liveFeedPolicyQuery.data)) !==
      JSON.stringify(liveFeedDraft);

  const connectorsLoading =
    liveFeedPolicyQuery.isLoading ||
    bybitConnectorDiagnosticsQuery.isLoading ||
    bybitSpotConnectorDiagnosticsQuery.isLoading;
  const connectorsError =
    liveFeedPolicyQuery.isError ||
    bybitConnectorDiagnosticsQuery.isError ||
    bybitSpotConnectorDiagnosticsQuery.isError;

  function updateLiveFeedDraftField(key: LiveFeedPolicyFieldKey, value: string) {
    setLiveFeedSaveNotice(null);
    setLiveFeedDraft((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        [key]:
          key === "bybit_universe_min_quote_volume_24h_usd" ||
          key === "bybit_universe_min_trade_count_24h"
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
                  <div className={sectionCaption}>Параметры биржи</div>
                  <div className={stateValue}>Подключение и переподключение Bybit</div>
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
                            value={liveFeedDraft.bybit_universe_min_quote_volume_24h_usd}
                            onChange={(event) =>
                              updateLiveFeedDraftField(
                                "bybit_universe_min_quote_volume_24h_usd",
                                event.target.value,
                              )
                            }
                          />
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
                            value={liveFeedDraft.bybit_universe_min_trade_count_24h}
                            onChange={(event) =>
                              updateLiveFeedDraftField(
                                "bybit_universe_min_trade_count_24h",
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
                        disabled={
                          !isLiveFeedDirty ||
                          !liveFeedPayload ||
                          liveFeedPolicyMutation.isPending
                        }
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
            </div>

            {connectorsLoading ? (
              <div className={settingsErrorState}>Загружаю текущее состояние коннекторов...</div>
            ) : null}

            {connectorsError ? (
              <div className={settingsErrorState}>
                Не удалось загрузить текущее состояние коннекторов.
              </div>
            ) : null}

            {!connectorsLoading &&
            !connectorsError &&
            bybitConnectorDiagnosticsQuery.data &&
            bybitSpotConnectorDiagnosticsQuery.data ? (
              <div className={connectorPanels}>
                {renderConnectorPanel({
                  title: "Бессрочные фьючерсы",
                  diagnostics: bybitConnectorDiagnosticsQuery.data,
                  enabledByPolicy: true,
                  isPending: bybitConnectorToggleMutation.isPending,
                  accentClassName: connectorPanelFuture,
                  onToggle: () => {
                    void bybitConnectorToggleMutation.mutateAsync({
                      enabled: !bybitConnectorDiagnosticsQuery.data.enabled,
                    });
                  },
                })}

                {renderConnectorPanel({
                  title: "Спотовый рынок",
                  diagnostics: bybitSpotConnectorDiagnosticsQuery.data,
                  enabledByPolicy: true,
                  isPending: bybitSpotConnectorToggleMutation.isPending,
                  accentClassName: connectorPanelSpot,
                  onToggle: () => {
                    void bybitSpotConnectorToggleMutation.mutateAsync({
                      enabled: !bybitSpotConnectorDiagnosticsQuery.data.enabled,
                    });
                  },
                })}
              </div>
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}
