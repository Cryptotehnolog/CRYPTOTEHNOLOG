import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { useExecutionSummary } from "../hooks/useExecutionSummary";
import { mapExecution } from "../mappers/mapExecution";
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
} from "./ExecutionPage.css";

export function ExecutionPage() {
  const executionQuery = useExecutionSummary();

  if (executionQuery.isLoading) {
    return (
      <LoadingState
        title="Загрузка сводки по исполнению"
        caption="Панель запрашивает узкий снимок контура исполнения в режиме только чтения без действий над заявками и без связи с OMS-операциями."
        message="Интерфейс ожидает сводку по исполнению из серверного контура панели."
      />
    );
  }

  if (executionQuery.isError) {
    const message =
      executionQuery.error instanceof Error
        ? executionQuery.error.message
        : "Не удалось загрузить сводку по исполнению.";

    return (
      <ErrorState
        title="Ошибка загрузки сводки по исполнению"
        caption="Страница исполнения остаётся поддерживающей поверхностью только для чтения и зависит только от узкой сводки диагностики контура исполнения."
        message={message}
      />
    );
  }

  if (!executionQuery.data) {
    return (
      <EmptyState
        title="Сводка по исполнению недоступна"
        message="Сервер панели не вернул модель чтения сводки по исполнению."
      />
    );
  }

  const model = mapExecution(executionQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Исполнение"
        status="inactive"
        message="Страница исполнения предусмотрена в dashboard foundation, но снимок только для чтения для неё ещё не подключён."
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
          title="Состояние контура исполнения"
          caption="Глобальный снимок контура исполнения в режиме только чтения без действий над ордерами и без связи с OMS-экранами."
        >
          <KeyValueList items={model.summary} />
        </Panel>

        <Panel
          title="Последний выведенный снимок исполнения"
          caption="Показывается только то, что уже честно выведено текущими диагностическими данными контура исполнения."
        >
          <KeyValueList items={model.freshness} />
        </Panel>
      </div>

      <Panel
        title="Доступность и счётчики"
        caption="Короткий список выведенных счётчиков и флагов доступности без обозревателя истории исполнения."
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
            title="Доступность исполнения не выведена"
            message="Текущий серверный контур не вернул ни одного элемента доступности для страницы исполнения только для чтения."
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
