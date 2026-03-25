import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { usePortfolioGovernorSummary } from "../hooks/usePortfolioGovernorSummary";
import { mapPortfolioGovernor } from "../mappers/mapPortfolioGovernor";
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
} from "./PortfolioGovernorPage.css";

export function PortfolioGovernorPage() {
  const governorQuery = usePortfolioGovernorSummary();

  if (governorQuery.isLoading) {
    return (
      <LoadingState
        title="Загрузка сводки по портфельному контуру"
        caption="Панель запрашивает узкий снимок портфельного контура в режиме только чтения без действий по распределению капитала, без перераспределения капитала и без связи с мутациями исполнения."
        message="Интерфейс ожидает сводку по портфельному контуру из серверного контура панели."
      />
    );
  }

  if (governorQuery.isError) {
    const message =
      governorQuery.error instanceof Error
        ? governorQuery.error.message
        : "Не удалось загрузить сводку по портфельному контуру.";

    return (
      <ErrorState
        title="Ошибка загрузки сводки по портфельному контуру"
        caption="Страница портфельного контура остаётся поддерживающей поверхностью только для чтения и зависит только от узкой сводки диагностики портфельного контура."
        message={message}
      />
    );
  }

  if (!governorQuery.data) {
    return (
      <EmptyState
        title="Сводка по портфельному контуру недоступна"
        message="Сервер панели не вернул модель чтения сводки по портфельному контуру."
      />
    );
  }

  const model = mapPortfolioGovernor(governorQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Портфельный контур"
        status="inactive"
        message="Страница портфельного контура предусмотрена в dashboard foundation, но снимок только для чтения для неё ещё не подключён."
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
          title="Состояние портфельного контура"
          caption="Глобальный снимок портфельного контура в режиме только чтения без действий по распределению капитала, без перераспределения капитала и без связи с мутациями исполнения."
        >
          <KeyValueList items={model.summary} />
        </Panel>

        <Panel
          title="Последний выведенный снимок портфельного контура"
          caption="Показывается только то, что уже честно выведено текущими диагностическими данными портфельного контура."
        >
          <KeyValueList items={model.freshness} />
        </Panel>
      </div>

      <Panel
        title="Доступность и счётчики"
        caption="Короткий список выведенных счётчиков и флагов доступности без широкого обозревателя портфельного контура."
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
            title="Доступность портфельного контура не выведена"
            message="Текущий серверный контур не вернул ни одного элемента доступности для страницы портфельного контура только для чтения."
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
            { label: "Примечание контура", value: model.note.summaryNote },
            { label: "Причина сводки", value: model.note.message },
          ]}
        />
      </Panel>
    </div>
  );
}
