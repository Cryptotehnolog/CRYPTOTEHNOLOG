import { style, styleVariants } from "@vanilla-extract/css";

import { vars } from "../../../shared/styles/theme.css";
import { shellTone } from "../../../app/layout/TerminalShell.css";
import { terminalTheme } from "../styles/terminalTheme.css";

const base = style({
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "26px",
  padding: `0 ${vars.space[3]}`,
  borderRadius: "10px",
  border: `1px solid ${terminalTheme.dark.border}`,
  background: terminalTheme.dark.nestedSurface,
  color: terminalTheme.dark.textSecondary,
  fontSize: vars.font.size[1],
  fontWeight: vars.font.weight.semibold,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  whiteSpace: "nowrap",
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.border,
      background: terminalTheme.light.nestedSurface,
      color: terminalTheme.light.textSecondary,
    },
  },
});

export const terminalBadgeTone = styleVariants({
  neutral: [base],
  accent: [
    base,
    {
      borderColor: terminalTheme.dark.accentSoft,
      background: terminalTheme.dark.accentSoft,
      color: terminalTheme.dark.accent,
      selectors: {
        [`${shellTone.light} &`]: {
          borderColor: terminalTheme.light.accentSoft,
          background: terminalTheme.light.accentSoft,
          color: terminalTheme.light.accent,
        },
      },
    },
  ],
  success: [
    base,
    {
      borderColor: terminalTheme.dark.successSoft,
      background: terminalTheme.dark.successSoft,
      color: terminalTheme.dark.success,
      selectors: {
        [`${shellTone.light} &`]: {
          borderColor: terminalTheme.light.successSoft,
          background: terminalTheme.light.successSoft,
          color: terminalTheme.light.success,
        },
      },
    },
  ],
  warning: [
    base,
    {
      borderColor: terminalTheme.dark.warningSoft,
      background: terminalTheme.dark.warningSoft,
      color: terminalTheme.dark.warning,
      selectors: {
        [`${shellTone.light} &`]: {
          borderColor: terminalTheme.light.warningSoft,
          background: terminalTheme.light.warningSoft,
          color: terminalTheme.light.warning,
        },
      },
    },
  ],
  danger: [
    base,
    {
      borderColor: terminalTheme.dark.errorSoft,
      background: terminalTheme.dark.errorSoft,
      color: terminalTheme.dark.error,
      selectors: {
        [`${shellTone.light} &`]: {
          borderColor: terminalTheme.light.errorSoft,
          background: terminalTheme.light.errorSoft,
          color: terminalTheme.light.error,
        },
      },
    },
  ],
});
