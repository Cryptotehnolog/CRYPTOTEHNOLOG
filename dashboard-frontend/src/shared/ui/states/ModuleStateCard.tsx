import type { ModuleStatus } from "../../types/dashboard";
import { Badge } from "../primitives/Badge";
import { formatModuleStatus } from "../../lib/dashboardText";
import { stateCard, stateText, stateTitle } from "./StateCard.css";

type ModuleStateCardProps = {
  title: string;
  status: ModuleStatus;
  message: string;
};

export function ModuleStateCard({
  title,
  status,
  message,
}: ModuleStateCardProps) {
  const tone =
    status === "read-only"
      ? "accent"
      : status === "restricted"
        ? "warning"
        : "neutral";

  return (
    <div className={stateCard}>
      <Badge tone={tone}>{formatModuleStatus(status)}</Badge>
      <h2 className={stateTitle}>{title}</h2>
      <p className={stateText}>{message}</p>
    </div>
  );
}
