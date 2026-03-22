import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import {
  formatBooleanWord,
  formatConnectionState,
  formatHealthStatus,
  formatModuleStatus,
} from "../../../shared/lib/dashboardText";
import { useOverviewSnapshot } from "../hooks/useOverviewSnapshot";
import { mapOverview } from "../mappers/mapOverview";
import { OverviewCircuitBreakers } from "./OverviewCircuitBreakers";
import { OverviewModuleAvailability } from "./OverviewModuleAvailability";
import {
  overviewStack,
  sectionGrid,
  topBanner,
} from "./OverviewPage.css";

export function OverviewPage() {
  const overviewQuery = useOverviewSnapshot();

  if (overviewQuery.isLoading) {
    return <LoadingState />;
  }

  if (overviewQuery.isError) {
    const message =
      overviewQuery.error instanceof Error
        ? overviewQuery.error.message
        : "Не удалось загрузить снимок обзора.";

    return <ErrorState message={message} />;
  }

  if (!overviewQuery.data) {
    return (
      <EmptyState
        title="Обзор недоступен"
        message="Сервер панели не вернул снимок обзора."
      />
    );
  }

  const model = mapOverview(overviewQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Обзор"
        status="inactive"
        message="Модуль обзора предусмотрен в каркасе панели, но backend для него ещё не подключён."
      />
    );
  }

  return (
    <div className={overviewStack}>
      <div className={topBanner}>
        <Badge tone="accent">{formatModuleStatus(model.moduleState)}</Badge>
        <Badge tone={model.unhealthyComponents.length > 0 ? "warning" : "success"}>
          здоровье: {formatHealthStatus(overviewQuery.data.health_summary.overall_status)}
        </Badge>
        <Badge tone="neutral">
          уведомления: {formatConnectionState(model.alertsPlaceholder.connected)}
        </Badge>
      </div>

      <div className={sectionGrid}>
        <Panel
          title="Состояние системы"
          caption="Текущее состояние control plane и runtime discipline платформы."
          aside={
            <Badge tone={overviewQuery.data.system_state.trade_allowed ? "success" : "danger"}>
              {overviewQuery.data.system_state.trade_allowed
                ? "торговля разрешена"
                : "торговля заблокирована"}
            </Badge>
          }
        >
          <KeyValueList items={model.system} />
        </Panel>

      <Panel
        title="Сводка по здоровью"
        caption="Агрегированное состояние backend foundation и serving truth после sync с mainline."
      >
        <KeyValueList items={model.health} />
      </Panel>

        <Panel
          title="Ожидающие подтверждения"
          caption="Снимок операторских процессов в режиме только чтения."
        >
          <KeyValueList items={model.approvals} />
        </Panel>

        <Panel title="Сводка по событиям" caption="Системные счётчики шины событий для обзора.">
          <KeyValueList items={model.events} />
        </Panel>
      </div>

      <OverviewCircuitBreakers items={model.circuitBreakers} />
      <OverviewModuleAvailability modules={model.modules} />

      <Panel
        title="Заглушка уведомлений"
        caption="Уведомления остаются отдельной supporting line и не входят в текущий dashboard scope."
      >
        <KeyValueList
          items={[
            {
              label: "Подключено",
              value: formatBooleanWord(model.alertsPlaceholder.connected),
            },
            {
              label: "Примечание",
              value: model.alertsPlaceholder.note,
            },
          ]}
        />
      </Panel>
    </div>
  );
}
