import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { useManagerSummary } from "../hooks/useManagerSummary";
import { mapManager } from "../mappers/mapManager";
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
} from "./ManagerPage.css";

export function ManagerPage() {
  const managerQuery = useManagerSummary();

  if (managerQuery.isLoading) {
    return (
      <LoadingState
        title="Загрузка сводки по менеджеру"
        caption="Панель запрашивает узкий снимок контура менеджера в режиме только чтения без действий над рабочими процессами, подтверждений и координационных контролов."
        message="Интерфейс ожидает сводку по менеджеру из серверного контура панели."
      />
    );
  }

  if (managerQuery.isError) {
    const message =
      managerQuery.error instanceof Error
        ? managerQuery.error.message
        : "Не удалось загрузить сводку по менеджеру.";

    return (
      <ErrorState
        title="Ошибка загрузки сводки по менеджеру"
        caption="Страница менеджера остаётся поддерживающей поверхностью только для чтения и зависит только от узкой сводки диагностики контура менеджера."
        message={message}
      />
    );
  }

  if (!managerQuery.data) {
    return (
      <EmptyState
        title="Сводка по менеджеру недоступна"
        message="Сервер панели не вернул модель чтения сводки по менеджеру."
      />
    );
  }

  const model = mapManager(managerQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Менеджер"
        status="inactive"
        message="Страница менеджера предусмотрена в основе панели, но снимок только для чтения для неё ещё не подключён."
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
          title="Состояние контура менеджера"
          caption="Глобальный снимок контура менеджера в режиме только чтения без координационных действий и без редакторов рабочих процессов."
        >
          <KeyValueList items={model.summary} />
        </Panel>

        <Panel
          title="Последний выведенный снимок менеджера"
          caption="Показывается только то, что уже честно выведено текущими диагностическими данными контура менеджера."
        >
          <KeyValueList items={model.freshness} />
        </Panel>
      </div>

      <Panel
        title="Доступность и счётчики"
        caption="Короткий список выведенных счётчиков и флагов доступности без обозревателя истории рабочих процессов."
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
            title="Доступность менеджера не выведена"
            message="Текущий серверный контур не вернул ни одного элемента доступности для страницы менеджера только для чтения."
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
