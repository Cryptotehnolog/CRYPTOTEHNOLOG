import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { usePositionExpansionSummary } from "../hooks/usePositionExpansionSummary";
import { mapPositionExpansion } from "../mappers/mapPositionExpansion";
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
} from "./PositionExpansionPage.css";

export function PositionExpansionPage() {
  const positionExpansionQuery = usePositionExpansionSummary();

  if (positionExpansionQuery.isLoading) {
    return (
      <LoadingState
        title="Загрузка сводки по расширению позиции"
        caption="Панель запрашивает узкий снимок контура расширения позиции в режиме только чтения без действий по набору позиции, без управляющих элементов наращивания позиции и без связи с мутациями исполнения."
        message="Интерфейс ожидает сводку по расширению позиции из серверного контура панели."
      />
    );
  }

  if (positionExpansionQuery.isError) {
    const message =
      positionExpansionQuery.error instanceof Error
        ? positionExpansionQuery.error.message
        : "Не удалось загрузить сводку по расширению позиции.";

    return (
      <ErrorState
        title="Ошибка загрузки сводки по расширению позиции"
        caption="Страница расширения позиции остаётся поддерживающей поверхностью только для чтения и зависит только от узкой сводки диагностики контура расширения позиции."
        message={message}
      />
    );
  }

  if (!positionExpansionQuery.data) {
    return (
      <EmptyState
        title="Сводка по расширению позиции недоступна"
        message="Сервер панели не вернул модель чтения сводки по расширению позиции."
      />
    );
  }

  const model = mapPositionExpansion(positionExpansionQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Расширение позиции"
        status="inactive"
        message="Страница расширения позиции предусмотрена в dashboard foundation, но снимок только для чтения для неё ещё не подключён."
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
          title="Состояние контура расширения позиции"
          caption="Глобальный снимок контура расширения позиции в режиме только чтения без действий по набору позиции, без управляющих элементов наращивания позиции и без связи с мутациями исполнения."
        >
          <KeyValueList items={model.summary} />
        </Panel>

        <Panel
          title="Последний выведенный снимок расширения позиции"
          caption="Показывается только то, что уже честно выведено текущими диагностическими данными контура расширения позиции."
        >
          <KeyValueList items={model.freshness} />
        </Panel>
      </div>

      <Panel
        title="Доступность и счётчики"
        caption="Короткий список выведенных счётчиков и флагов доступности без широкого обозревателя расширения позиции."
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
            title="Доступность расширения позиции не выведена"
            message="Текущий серверный контур не вернул ни одного элемента доступности для страницы расширения позиции только для чтения."
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
