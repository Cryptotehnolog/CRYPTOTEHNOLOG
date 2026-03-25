import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { useRiskSummary } from "../hooks/useRiskSummary";
import { mapRisk } from "../mappers/mapRisk";
import {
  constraintHeader,
  constraintItem,
  constraintLabel,
  constraintList,
  constraintMeta,
  constraintNote,
  pageStack,
  reasonText,
  sectionGrid,
  topBanner,
} from "./RiskPage.css";

export function RiskPage() {
  const riskQuery = useRiskSummary();

  if (riskQuery.isLoading) {
    return (
      <LoadingState
        title="Загрузка сводки по риску"
        caption="Панель собирает узкий срез риск-границ в режиме только чтения без редактора политик и действий по сценариям."
        message="Интерфейс ожидает снимок сводки по риску из серверного контура панели."
      />
    );
  }

  if (riskQuery.isError) {
    const message =
      riskQuery.error instanceof Error
        ? riskQuery.error.message
        : "Не удалось загрузить сводку по риску.";

    return (
      <ErrorState
        title="Ошибка загрузки сводки по риску"
        caption="Страница риска остаётся поверхностью только для чтения и зависит от узкой серверной поверхности сводки по риску."
        message={message}
      />
    );
  }

  if (!riskQuery.data) {
    return (
      <EmptyState
        title="Сводка по риску недоступна"
        message="Сервер панели не вернул модель чтения сводки по риску."
      />
    );
  }

  const model = mapRisk(riskQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Риск"
        status="inactive"
        message="Страница риска предусмотрена в dashboard foundation, но снимок только для чтения для неё ещё не подключён."
      />
    );
  }

  return (
    <div className={pageStack}>
      <div className={topBanner}>
        {model.statusBadges.map((badge) => (
          <Badge key={`${badge.label}-${badge.tone}`} tone={badge.tone}>
            {badge.label}
          </Badge>
        ))}
      </div>

      <div className={sectionGrid}>
        <Panel
          title="Состояние риска"
          caption="Глобальный снимок состояния риска в режиме только чтения без обозревателя экспозиций и ручных переопределений."
        >
          <KeyValueList items={model.summary} />
        </Panel>

        <Panel
          title="Блокирующее и лимитирующее состояние"
          caption="Текущее честное состояние исполнения про ограничение торговли и операторское пояснение."
        >
          <KeyValueList items={model.runtimeBoundary} />
        </Panel>
      </div>

      <Panel
        title="Активные ограничения риска"
        caption="Краткий список выведенных ограничений из состояния исполнения и пути настроек без редактора политик."
        aside={
          <Badge tone={model.constraints.length > 0 ? "warning" : "neutral"}>
            {model.constraints.length > 0
              ? `выведено: ${model.constraints.length}`
              : "ограничения не выведены"}
          </Badge>
        }
      >
        {model.constraints.length > 0 ? (
          <div className={constraintList}>
            {model.constraints.map((item) => (
              <div key={item.key} className={constraintItem}>
                <div className={constraintHeader}>
                  <div className={constraintMeta}>
                    <span className={constraintLabel}>{item.label}</span>
                    <span>{item.value}</span>
                  </div>
                  <Badge tone={item.tone}>{item.value}</Badge>
                </div>
                {item.note ? <p className={constraintNote}>{item.note}</p> : null}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="Ограничения риска не выведены"
            message="Текущий серверный контур не вернул ни одного ограничения риска для страницы только для чтения."
          />
        )}
      </Panel>

      <Panel
        title="Причина сводки"
        caption="Показывается только выведенная причина или честное отсутствие дополнительного пояснения."
        aside={
          <Badge tone={model.reason.hasReason ? "warning" : "neutral"}>
            {model.reason.hasReason ? "причина выведена" : "причина отсутствует"}
          </Badge>
        }
      >
        <p className={reasonText}>{model.reason.message}</p>
      </Panel>
    </div>
  );
}
