import { style, styleVariants } from "@vanilla-extract/css";

import { vars } from "../../styles/theme.css";

const badgeBase = style({
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "26px",
  padding: `0 ${vars.space[3]}`,
  borderRadius: vars.radius.pill,
  fontSize: vars.font.size[1],
  fontWeight: vars.font.weight.semibold,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
  border: "1px solid transparent",
});

export const badgeTone = styleVariants({
  neutral: [
    badgeBase,
    {
      background: vars.color.neutralSoft,
      color: vars.color.neutral,
      borderColor: vars.color.border,
    },
  ],
  accent: [
    badgeBase,
    {
      background: vars.color.accentSoft,
      color: vars.color.accent,
      borderColor: vars.color.accent,
    },
  ],
  success: [
    badgeBase,
    {
      background: vars.color.successSoft,
      color: vars.color.success,
      borderColor: vars.color.success,
    },
  ],
  warning: [
    badgeBase,
    {
      background: vars.color.warningSoft,
      color: vars.color.warning,
      borderColor: vars.color.warning,
    },
  ],
  danger: [
    badgeBase,
    {
      background: vars.color.dangerSoft,
      color: vars.color.danger,
      borderColor: vars.color.danger,
    },
  ],
});
