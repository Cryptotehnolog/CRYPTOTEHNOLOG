import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { useBacktestSummary } from "../hooks/useBacktestSummary";
import { mapBacktest } from "../mappers/mapBacktest";
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
} from "./BacktestPage.css";

export function BacktestPage() {
  const backtestQuery = useBacktestSummary();

  if (backtestQuery.isLoading) {
    return (
      <LoadingState
        title="Загрузка сводки по бэктест-контуру"
        caption="Панель запрашивает узкий снимок бэктест-контура в режиме только чтения без ручного управления прогонами, средств оптимизации и исследовательских поверхностей."
        message="Интерфейс ожидает сводку по бэктест-контуру из серверного контура панели."
      />
    );
  }

  if (backtestQuery.isError) {
    const message =
      backtestQuery.error instanceof Error
        ? backtestQuery.error.message
        : "Не удалось загрузить сводку по бэктест-контуру.";

    return (
      <ErrorState
        title="Ошибка загрузки сводки по бэктест-контуру"
        caption="Страница бэктест-контура остаётся поддерживающей поверхностью только для чтения и зависит только от узкой сводки диагностики бэктест-контура."
        message={message}
      />
    );
  }

  if (!backtestQuery.data) {
    return (
      <EmptyState
        title="Сводка по бэктест-контуру недоступна"
        message="Сервер панели не вернул модель чтения сводки по бэктест-контуру."
      />
    );
  }

  const model = mapBacktest(backtestQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Бэктест"
        status="inactive"
        message="Страница бэктест-контура предусмотрена в основе панели, но снимок только для чтения для неё ещё не подключён."
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
          title="Состояние бэктест-контура"
          caption="Глобальный снимок бэктест-контура в режиме только чтения без ручного управления прогонами и без исследовательских или отчётных поверхностей."
        >
          <KeyValueList items={model.summary} />
        </Panel>

        <Panel
          title="Последний выведенный снимок бэктеста"
          caption="Показывается только то, что уже честно выведено текущими диагностическими данными бэктест-контура."
        >
          <KeyValueList items={model.freshness} />
        </Panel>
      </div>

      <Panel
        title="Доступность и счётчики"
        caption="Короткий список выведенных счётчиков и флагов доступности без обозревателя прогонов и без исследовательской поверхности."
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
            title="Доступность бэктест-контура не выведена"
            message="Текущий серверный контур не вернул ни одного элемента доступности для страницы бэктест-контура только для чтения."
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
