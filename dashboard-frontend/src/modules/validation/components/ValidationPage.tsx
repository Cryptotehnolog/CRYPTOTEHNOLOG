import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { useValidationSummary } from "../hooks/useValidationSummary";
import { mapValidation } from "../mappers/mapValidation";
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
} from "./ValidationPage.css";

export function ValidationPage() {
  const validationQuery = useValidationSummary();

  if (validationQuery.isLoading) {
    return (
      <LoadingState
        title="Загрузка сводки по валидации"
        caption="Панель запрашивает узкий снимок контура валидации в режиме только чтения без действий над проверками, подтверждений и редакторов правил валидации."
        message="Интерфейс ожидает сводку по валидации из серверного контура панели."
      />
    );
  }

  if (validationQuery.isError) {
    const message =
      validationQuery.error instanceof Error
        ? validationQuery.error.message
        : "Не удалось загрузить сводку по валидации.";

    return (
      <ErrorState
        title="Ошибка загрузки сводки по валидации"
        caption="Страница валидации остаётся поддерживающей поверхностью только для чтения и зависит только от узкой сводки диагностики контура валидации."
        message={message}
      />
    );
  }

  if (!validationQuery.data) {
    return (
      <EmptyState
        title="Сводка по валидации недоступна"
        message="Сервер панели не вернул модель чтения сводки по валидации."
      />
    );
  }

  const model = mapValidation(validationQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Валидация"
        status="inactive"
        message="Страница валидации предусмотрена в основе панели, но снимок только для чтения для неё ещё не подключён."
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
          title="Состояние контура валидации"
          caption="Глобальный снимок контура валидации в режиме только чтения без действий над проверками и без редакторов правил валидации."
        >
          <KeyValueList items={model.summary} />
        </Panel>

        <Panel
          title="Последний выведенный снимок валидации"
          caption="Показывается только то, что уже честно выведено текущими диагностическими данными контура валидации."
        >
          <KeyValueList items={model.freshness} />
        </Panel>
      </div>

      <Panel
        title="Доступность и счётчики"
        caption="Короткий список выведенных счётчиков и флагов доступности без обозревателя истории проверок."
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
            title="Доступность валидации не выведена"
            message="Текущий серверный контур не вернул ни одного элемента доступности для страницы валидации только для чтения."
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
