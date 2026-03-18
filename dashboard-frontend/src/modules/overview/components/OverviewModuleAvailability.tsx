import { Badge } from "../../../shared/ui/primitives/Badge";
import { formatModuleStatus } from "../../../shared/lib/dashboardText";
import { Panel } from "../../../shared/ui/primitives/Panel";
import type { OverviewViewModel } from "../mappers/mapOverview";
import {
  list,
  listItem,
  listLabel,
  listValue,
} from "./OverviewPage.css";

type OverviewModuleAvailabilityProps = {
  modules: OverviewViewModel["modules"];
};

export function OverviewModuleAvailability({
  modules,
}: OverviewModuleAvailabilityProps) {
  return (
    <Panel
      title="Доступность модулей"
      caption="Фазовая карта разделов панели и текущий статус подключения."
    >
      <div className={list}>
        {modules.map((module) => (
          <div key={module.key} className={listItem}>
            <div>
              <div>{module.title}</div>
              <div className={listLabel}>{module.description}</div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <Badge tone={module.status === "read-only" ? "accent" : "neutral"}>
                {formatModuleStatus(module.status)}
              </Badge>
              <span className={listValue}>{module.phase}</span>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}
