import { Badge } from "../../../shared/ui/primitives/Badge";
import {
  formatModuleGroup,
  formatModuleStatus,
  getModuleGroupCaption,
} from "../../../shared/lib/dashboardText";
import { Panel } from "../../../shared/ui/primitives/Panel";
import type { OverviewViewModel } from "../mappers/mapOverview";
import {
  listCaption,
  listHeader,
  list,
  listItem,
  listLabel,
  listMeta,
  listReason,
  listSection,
  listValue,
} from "./OverviewPage.css";

type OverviewModuleAvailabilityProps = {
  modules: OverviewViewModel["modules"];
};

export function OverviewModuleAvailability({
  modules,
}: OverviewModuleAvailabilityProps) {
  const coreModules = modules.filter((module) => module.group === "core");
  const runtimeModules = modules.filter((module) => module.group === "runtime");

  const renderModuleList = (
    group: "core" | "runtime",
    items: OverviewViewModel["modules"],
  ) => (
    <section className={listSection}>
      <div className={listHeader}>
        <div>
          <div>{formatModuleGroup(group)}</div>
          <div className={listCaption}>{getModuleGroupCaption(group)}</div>
        </div>
        <Badge tone={group === "core" ? "neutral" : "accent"}>{items.length}</Badge>
      </div>

      <div className={list}>
        {items.map((module) => (
          <div key={module.key} className={listItem}>
            <div>
              <div>{module.title}</div>
              <div className={listLabel}>{module.description}</div>
              <div className={listReason}>{module.stateReason}</div>
              <div className={listMeta}>маршрут: {module.route}</div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <Badge tone={module.group === "runtime" ? "accent" : "neutral"}>
                {formatModuleGroup(module.group)}
              </Badge>
              <Badge
                tone={
                  module.status === "read-only"
                    ? "accent"
                    : module.status === "restricted"
                      ? "warning"
                      : module.status === "active"
                        ? "success"
                        : "neutral"
                }
              >
                {formatModuleStatus(module.status)}
              </Badge>
              <span className={listValue}>{module.phase}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );

  return (
    <Panel
      title="Доступность модулей"
      caption="Карта текущих dashboard surfaces и runtime contours без расширения backend/API scope."
    >
      {renderModuleList("core", coreModules)}
      {renderModuleList("runtime", runtimeModules)}
    </Panel>
  );
}
