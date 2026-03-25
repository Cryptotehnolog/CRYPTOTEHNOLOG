import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";
import { useOverviewSnapshot } from "../../overview/hooks/useOverviewSnapshot";
import { mapHealthObservability } from "../mappers/mapHealthObservability";
import {
  list,
  listItem,
  listLabel,
  listValue,
  pageStack,
  sectionGrid,
  topBanner,
} from "./HealthObservabilityPage.css";

export function HealthObservabilityPage() {
  const overviewQuery = useOverviewSnapshot();

  if (overviewQuery.isLoading) {
    return <LoadingState />;
  }

  if (overviewQuery.isError) {
    const message =
      overviewQuery.error instanceof Error
        ? overviewQuery.error.message
        : "Не удалось загрузить снимок здоровья.";

    return <ErrorState message={message} />;
  }

  if (!overviewQuery.data) {
    return (
      <EmptyState
        title="Контур здоровья и наблюдаемости недоступен"
        message="Сервер панели не вернул снимок здоровья для операторской страницы."
      />
    );
  }

  const model = mapHealthObservability(overviewQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Здоровье и наблюдаемость"
        status="inactive"
        message="Страница здоровья и наблюдаемости предусмотрена в dashboard foundation, но снимок только для чтения для неё ещё не подключён."
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
          title="Снимок здоровья"
          caption="Сводка по состоянию системы в режиме только чтения без платформы метрик и сценариев инцидентов."
        >
          <KeyValueList items={model.healthSummary} />
        </Panel>

        <Panel
          title="Нездоровые компоненты"
          caption="Показываются только компоненты, которые уже честно выведены текущим серверным снимком."
          aside={
            <Badge tone={model.unhealthyComponents.length > 0 ? "warning" : "success"}>
              {model.unhealthyComponents.length > 0 ? "есть деградации" : "деградаций нет"}
            </Badge>
          }
        >
          {model.unhealthyComponents.length > 0 ? (
            <div className={list}>
              {model.unhealthyComponents.map((item) => (
                <div key={item} className={listItem}>
                  <span className={listLabel}>Компонент</span>
                  <span className={listValue}>{item}</span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="Нездоровых компонентов нет"
              message="Текущий снимок здоровья не содержит нездоровых компонентов."
            />
          )}
        </Panel>
      </div>

      <Panel
        title="Сводка по защитным выключателям"
        caption="Снимок защитных выключателей в режиме только чтения, если он уже есть в текущем серверном контуре панели."
        aside={
          <Badge tone={model.circuitBreakers.length > 0 ? "warning" : "neutral"}>
            {model.circuitBreakers.length > 0
              ? `зарегистрировано: ${model.circuitBreakers.length}`
              : "не зарегистрированы"}
          </Badge>
        }
      >
        {model.circuitBreakers.length > 0 ? (
          <div className={list}>
            {model.circuitBreakers.map((item) => (
              <div key={item.name} className={listItem}>
                <div>
                  <div>{item.name}</div>
                  <div className={listLabel}>
                    ошибок: {item.failureCount} / порог: {item.failureThreshold}
                  </div>
                </div>
                <div className={listValue}>
                  {item.state}, успехов: {item.successCount}, восстановление: {item.recoveryTimeout} с
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="Защитные выключатели не зарегистрированы"
            message="Текущий снимок здоровья не содержит сводки по защитным выключателям."
          />
        )}
      </Panel>
    </div>
  );
}
