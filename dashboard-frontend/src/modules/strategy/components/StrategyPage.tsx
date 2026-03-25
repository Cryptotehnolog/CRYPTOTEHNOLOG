import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { useStrategySummary } from "../hooks/useStrategySummary";
import { mapStrategy } from "../mappers/mapStrategy";
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
} from "./StrategyPage.css";

export function StrategyPage() {
  const strategyQuery = useStrategySummary();

  if (strategyQuery.isLoading) {
    return (
      <LoadingState
        title="Загрузка сводки по стратегии"
        caption="Панель запрашивает узкий снимок стратегического контура в режиме только чтения без действий над стратегией и без coupling с исполнением."
        message="Интерфейс ожидает сводку по стратегии из серверного контура панели."
      />
    );
  }

  if (strategyQuery.isError) {
    const message =
      strategyQuery.error instanceof Error
        ? strategyQuery.error.message
        : "Не удалось загрузить сводку по стратегии.";

    return (
      <ErrorState
        title="Ошибка загрузки сводки по стратегии"
        caption="Страница стратегии остаётся поддерживающей поверхностью только для чтения и зависит только от узкой сводки диагностики стратегического контура."
        message={message}
      />
    );
  }

  if (!strategyQuery.data) {
    return (
      <EmptyState
        title="Сводка по стратегии недоступна"
        message="Сервер панели не вернул модель чтения сводки по стратегии."
      />
    );
  }

  const model = mapStrategy(strategyQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Стратегия"
        status="inactive"
        message="Страница стратегии предусмотрена в dashboard foundation, но снимок только для чтения для неё ещё не подключён."
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
          title="Состояние стратегического контура"
          caption="Глобальный снимок стратегического контура в режиме только чтения без обозревателя оркестрации и без связи с исполнением."
        >
          <KeyValueList items={model.summary} />
        </Panel>

        <Panel
          title="Последний выведенный снимок стратегии"
          caption="Показывается только то, что уже честно выведено текущими диагностическими данными стратегического контура."
        >
          <KeyValueList items={model.freshness} />
        </Panel>
      </div>

      <Panel
        title="Доступность и счётчики"
        caption="Короткий список выведенных счётчиков и флагов доступности без широкого обозревателя истории стратегии."
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
            title="Доступность стратегии не выведена"
            message="Текущий серверный контур не вернул ни одного элемента доступности для страницы стратегии только для чтения."
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
