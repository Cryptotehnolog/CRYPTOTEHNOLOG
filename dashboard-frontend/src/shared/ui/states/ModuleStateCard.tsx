import type { ModuleStatus } from "../../types/dashboard";
import { Badge } from "../primitives/Badge";
import { formatModuleStatus } from "../../lib/dashboardText";
import {
  stateCaption,
  stateCard,
  stateHintList,
  stateMeta,
  stateText,
  stateTitle,
} from "./StateCard.css";

type ModuleStateCardProps = {
  title: string;
  status: ModuleStatus;
  message: string;
  caption?: string;
  hints?: string[];
  metaBadges?: Array<{
    label: string;
    tone?: "neutral" | "accent" | "success" | "warning" | "danger";
  }>;
};

export function ModuleStateCard({
  title,
  status,
  message,
  caption,
  hints = [],
  metaBadges = [],
}: ModuleStateCardProps) {
  const tone =
    status === "read-only"
      ? "accent"
      : status === "restricted"
        ? "warning"
        : "neutral";

  return (
    <div className={stateCard}>
      <div className={stateMeta}>
        <Badge tone={tone}>{formatModuleStatus(status)}</Badge>
        {metaBadges.map((badge) => (
          <Badge key={`${badge.label}-${badge.tone ?? "neutral"}`} tone={badge.tone ?? "neutral"}>
            {badge.label}
          </Badge>
        ))}
      </div>
      <h2 className={stateTitle}>{title}</h2>
      {caption ? <p className={stateCaption}>{caption}</p> : null}
      <p className={stateText}>{message}</p>
      {hints.length > 0 ? (
        <ul className={stateHintList}>
          {hints.map((hint) => (
            <li key={hint}>{hint}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
