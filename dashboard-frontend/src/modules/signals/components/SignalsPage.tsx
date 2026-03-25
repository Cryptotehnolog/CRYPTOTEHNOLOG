import { Badge } from "../../../shared/ui/primitives/Badge";
import { KeyValueList } from "../../../shared/ui/primitives/KeyValueList";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import { ErrorState } from "../../../shared/ui/states/ErrorState";
import { LoadingState } from "../../../shared/ui/states/LoadingState";
import { ModuleStateCard } from "../../../shared/ui/states/ModuleStateCard";
import { useSignalsSummary } from "../hooks/useSignalsSummary";
import { mapSignals } from "../mappers/mapSignals";
import {
  availabilityHeader,
  availabilityItem,
  availabilityLabel,
  availabilityList,
  availabilityMeta,
  availabilityNote,
  pageStack,
  reasonText,
  sectionGrid,
  topBanner,
} from "./SignalsPage.css";

export function SignalsPage() {
  const signalsQuery = useSignalsSummary();

  if (signalsQuery.isLoading) {
    return (
      <LoadingState
        title="Загрузка сводки по сигналам"
        caption="Панель запрашивает узкий снимок сигнального контура в режиме только чтения без обозревателя кандидатов и действий над сигналами."
        message="Интерфейс ожидает сводку по сигналам из серверного контура панели."
      />
    );
  }

  if (signalsQuery.isError) {
    const message =
      signalsQuery.error instanceof Error
        ? signalsQuery.error.message
        : "Не удалось загрузить сводку по сигналам.";

    return (
      <ErrorState
        title="Ошибка загрузки сводки по сигналам"
        caption="Страница сигналов остаётся поддерживающей поверхностью только для чтения и зависит только от узкой сводки диагностик сигналов."
        message={message}
      />
    );
  }

  if (!signalsQuery.data) {
    return (
      <EmptyState
        title="Сводка по сигналам недоступна"
        message="Сервер панели не вернул модель чтения сводки по сигналам."
      />
    );
  }

  const model = mapSignals(signalsQuery.data);

  if (model.moduleState === "inactive") {
    return (
      <ModuleStateCard
        title="Сигналы"
        status="inactive"
        message="Страница сигналов предусмотрена в dashboard foundation, но снимок только для чтения для неё ещё не подключён."
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
          title="Состояние сигнального контура"
          caption="Глобальный снимок сигнального контура в режиме только чтения без связи со стратегией и ручных запусков."
        >
          <KeyValueList items={model.summary} />
        </Panel>

        <Panel
          title="Последний выведенный снимок сигнала"
          caption="Показывается только то, что уже честно выведено текущими диагностическими данными сигналов."
        >
          <KeyValueList items={model.freshness} />
        </Panel>
      </div>

      <Panel
        title="Доступность и счётчики"
        caption="Короткий список выведенных счётчиков и флагов доступности без обозревателя истории."
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
            title="Доступность сигналов не выведена"
            message="Текущий серверный контур не вернул ни одного элемента доступности для страницы сигналов только для чтения."
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
