import type { PropsWithChildren } from "react";

import { badgeTone } from "./Badge.css";

type BadgeProps = PropsWithChildren<{
  tone?: keyof typeof badgeTone;
}>;

export function Badge({ tone = "neutral", children }: BadgeProps) {
  return <span className={badgeTone[tone]}>{children}</span>;
}
