import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { useOpportunitySummary } from "../hooks/useOpportunitySummary";
import { mapOpportunity } from "../mappers/mapOpportunity";
import {
  availabilityHeader,
  availabilityItem,
  availabilityLabel,
  availabilityList,
  availabilityMeta,
  availabilityNote,
  pageStack,
  sectionGrid,
  topBanner,
} from "./OpportunityPage.css";

export function OpportunityPage() {
  const opportunityQuery = useOpportunitySummary();

  if (opportunityQuery.isLoading) {
    return (
      <LoadingState
        title="Загрузка сводки по возможностям"
        caption="Панель запрашивает узкий снимок контура возможностей в режиме только чтения без действий над отбором, без ранжирования и без связи с оркестрацией."
        message="Интерфейс ожидает сводку по возможностям из серверного контура панели."
      />
    );
  }

  if (opportunityQuery.isError) {
    const message =
      opportunityQuery.error instanceof Error
        ? opportunityQuery.error.message
        : "Не удалось загрузить сводку по возможностям.";

    return (
      <ErrorState
        title="Ошибка загрузки сводки по возможностям"
        caption="Страница возможностей остаётся поддерживающей поверхностью только для чтения и зависит только от узкой сводки диагностики контура возможностей."
        message={message}
      />
    );
  }

  if (!opportunityQuery.data) {
    return (
      <EmptyState
        title="Сводка по возможностям недоступна"
        message="Сервер панели не вернул модель чтения сводки по возможностям."
      />
    );
  }

  const model = mapOpportunity(opportunityQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Возможности"
        status="inactive"
        message="Страница возможностей предусмотрена в dashboard foundation, но снимок только для чтения для неё ещё не подключён."
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
          title="Состояние контура возможностей"
          caption="Глобальный снимок контура возможностей в режиме только чтения без действий над отбором, без ранжирования и без связи с оркестрацией."
        >
          <KeyValueList items={model.summary} />
        </Panel>

        <Panel
          title="Последний выведенный снимок возможностей"
          caption="Показывается только то, что уже честно выведено текущими диагностическими данными контура возможностей."
        >
          <KeyValueList items={model.freshness} />
        </Panel>
      </div>

      <Panel
        title="Доступность и счётчики"
        caption="Короткий список выведенных счётчиков и флагов доступности без широкого обозревателя возможностей."
        aside={
          <Badge tone={model.availability.length > 0 ? "warning" : "neutral"}>
            {model.availability.length > 0
              ? `выведено: ${model.availability.length}`
              : "доступность не выведена"}
          </Badge>
        }
      >
        {model.availability.length > 0 ? (
          <div className={availabilityList}>
            {model.availability.map((item) => (
              <div key={item.key} className={availabilityItem}>
                <div className={availabilityHeader}>
                  <div className={availabilityMeta}>
                    <span className={availabilityLabel}>{item.label}</span>
                    <span>{item.value}</span>
                  </div>
                  <Badge tone={item.tone}>{item.value}</Badge>
                </div>
                {item.note ? <p className={availabilityNote}>{item.note}</p> : null}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="Доступность возможностей не выведена"
            message="Текущий серверный контур не вернул ни одного элемента доступности для страницы возможностей только для чтения."
          />
        )}
      </Panel>

      <Panel
        title="Примечание и причина"
        caption="Показываются только выведенные примечание и причина или честно фиксируется отсутствие дополнительного пояснения."
        aside={
          <Badge tone={model.note.hasReason ? "warning" : "neutral"}>
            {model.note.hasReason ? "причина выведена" : "причина отсутствует"}
          </Badge>
        }
      >
        <KeyValueList
          items={[
            {
              label: "Примечание контура",
              value: model.note.summaryNote,
            },
            {
              label: "Причина сводки",
              value: model.note.message,
            },
          ]}
        />
      </Panel>
    </div>
  );
}
