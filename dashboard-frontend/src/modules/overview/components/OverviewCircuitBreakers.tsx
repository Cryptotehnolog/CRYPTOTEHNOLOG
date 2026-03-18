import { Badge } from "../../../shared/ui/primitives/Badge";
import { formatCircuitBreakerState } from "../../../shared/lib/dashboardText";
import { Panel } from "../../../shared/ui/primitives/Panel";
import { EmptyState } from "../../../shared/ui/states/EmptyState";
import type { OverviewViewModel } from "../mappers/mapOverview";
import {
  list,
  listItem,
  listLabel,
  listValue,
} from "./OverviewPage.css";

type OverviewCircuitBreakersProps = {
  items: OverviewViewModel["circuitBreakers"];
};

export function OverviewCircuitBreakers({
  items,
}: OverviewCircuitBreakersProps) {
  if (items.length === 0) {
    return (
      <Panel
        title="Сводка по circuit breaker"
        caption="Критические снимки circuit breaker пока не зарегистрированы."
      >
        <EmptyState
          title="Circuit breaker не зарегистрированы"
          message="Сервер панели не вернул ни одного снимка circuit breaker."
        />
      </Panel>
    );
  }

  return (
    <Panel
      title="Сводка по circuit breaker"
      caption="Состояние защитных circuit breaker без mutating-действий."
    >
      <div className={list}>
        {items.map((item) => (
          <div key={item.name} className={listItem}>
            <div>
              <div>{item.name}</div>
              <div className={listLabel}>
                ошибок={item.failure_count} / порог={item.failure_threshold}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <Badge tone={item.state === "closed" ? "success" : "warning"}>
                {formatCircuitBreakerState(item.state)}
              </Badge>
              <span className={listValue}>{item.recovery_timeout} с</span>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}
