import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { useOmsSummary } from "../hooks/useOmsSummary";
import { mapOms } from "../mappers/mapOms";
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
} from "./OmsPage.css";

export function OmsPage() {
  const omsQuery = useOmsSummary();

  if (omsQuery.isLoading) {
    return (
      <LoadingState
        title="Загрузка сводки по OMS"
        caption="Панель запрашивает узкий снимок OMS-контура в режиме только чтения без действий над ордерами, без управления площадками и без execution-мутаторов."
        message="Интерфейс ожидает сводку по OMS из серверного контура панели."
      />
    );
  }

  if (omsQuery.isError) {
    const message =
      omsQuery.error instanceof Error
        ? omsQuery.error.message
        : "Не удалось загрузить сводку по OMS.";

    return (
      <ErrorState
        title="Ошибка загрузки сводки по OMS"
        caption="Страница OMS остаётся поддерживающей поверхностью только для чтения и зависит только от узкой сводки диагностики OMS-контура."
        message={message}
      />
    );
  }

  if (!omsQuery.data) {
    return (
      <EmptyState
        title="Сводка по OMS недоступна"
        message="Сервер панели не вернул модель чтения сводки по OMS."
      />
    );
  }

  const model = mapOms(omsQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="OMS"
        status="inactive"
        message="Страница OMS предусмотрена в dashboard foundation, но снимок только для чтения для неё ещё не подключён."
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
          title="Состояние OMS-контура"
          caption="Глобальный снимок OMS-контура в режиме только чтения без действий cancel или replace и без управления ордерами."
        >
          <KeyValueList items={model.summary} />
        </Panel>

        <Panel
          title="Последний выведенный снимок OMS"
          caption="Показывается только то, что уже честно выведено текущими диагностическими данными OMS-контура."
        >
          <KeyValueList items={model.freshness} />
        </Panel>
      </div>

      <Panel
        title="Доступность и счётчики"
        caption="Короткий список выведенных счётчиков и флагов доступности без обозревателя истории ордеров."
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
            title="Доступность OMS не выведена"
            message="Текущий серверный контур не вернул ни одного элемента доступности для страницы OMS только для чтения."
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
