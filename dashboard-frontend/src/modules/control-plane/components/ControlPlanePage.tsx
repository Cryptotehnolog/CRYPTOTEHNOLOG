import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";
import { useOverviewSnapshot } from "../../overview/hooks/useOverviewSnapshot";
import { mapControlPlane } from "../mappers/mapControlPlane";
import { errorMessage, pageStack, sectionGrid, topBanner } from "./ControlPlanePage.css";

export function ControlPlanePage() {
  const overviewQuery = useOverviewSnapshot();

  if (overviewQuery.isLoading) {
    return <LoadingState />;
  }

  if (overviewQuery.isError) {
    const message =
      overviewQuery.error instanceof Error
        ? overviewQuery.error.message
        : "Не удалось загрузить снимок контура управления.";

    return <ErrorState message={message} />;
  }

  if (!overviewQuery.data) {
    return (
      <EmptyState
        title="Контур управления недоступен"
        message="Сервер панели не вернул модель чтения контура управления."
      />
    );
  }

  const model = mapControlPlane(overviewQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Контур управления"
        status="inactive"
        message="Страница контура управления предусмотрена в dashboard foundation, но снимок только для чтения для неё ещё не подключён."
      />
    );
  }

  return (
    <div className={pageStack}>
      <div className={topBanner}>
        <Badge tone="accent">{formatModuleStatus(model.moduleState)}</Badge>
        {model.statusBadges.map((badge) => (
          <Badge key={`${badge.label}-${badge.tone}`} tone={badge.tone}>
            {badge.label}
          </Badge>
        ))}
      </div>

      <div className={sectionGrid}>
        <Panel
          title="Снимок жизненного цикла"
          caption="Снимок текущего состояния системы и фаз жизненного цикла контура управления в режиме только чтения."
        >
          <KeyValueList items={model.lifecycle} />
        </Panel>

        <Panel
          title="Текущее состояние исполнения"
          caption="Базовые признаки того, как контур управления выглядит для оператора в текущем серверном снимке."
        >
          <KeyValueList items={model.runtimeFlags} />
        </Panel>
      </div>

      <Panel
        title="Последняя ошибка"
        caption="Показывается только то, что уже честно доступно в текущем серверном контуре панели."
        aside={
          <Badge tone={model.errorState.hasError ? "warning" : "success"}>
            {model.errorState.hasError ? "ошибка есть" : "ошибок нет"}
          </Badge>
        }
      >
        <p className={errorMessage}>{model.errorState.message}</p>
      </Panel>
    </div>
  );
}
