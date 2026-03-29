import type { PropsWithChildren } from "react";

import { terminalBadgeTone } from "./TerminalBadge.css";

type TerminalBadgeProps = PropsWithChildren<{
  tone?: keyof typeof terminalBadgeTone;
}>;

export function TerminalBadge({
  tone = "neutral",
  children,
}: TerminalBadgeProps) {
  return <span className={terminalBadgeTone[tone]}>{children}</span>;
}
