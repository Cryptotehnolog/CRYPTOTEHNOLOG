import { style } from "@vanilla-extract/css";

import { vars } from "../../../shared/styles/theme.css";
import { shellTone } from "../../../app/layout/TerminalShell.css";
import { terminalTheme } from "../styles/terminalTheme.css";

export const exchangeSelector = style({
  display: "flex",
  gap: vars.space[2],
  flexWrap: "wrap",
});

export const exchangeSelectorButton = style({
  padding: `${vars.space[2]} ${vars.space[3]}`,
  borderRadius: "999px",
  border: `1px solid ${terminalTheme.dark.border}`,
  background: terminalTheme.dark.nestedSurface,
  color: terminalTheme.dark.textPrimary,
  cursor: "pointer",
  transition: "border-color 160ms ease, background 160ms ease, color 160ms ease",
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.border,
      background: terminalTheme.light.nestedSurface,
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const exchangeSelectorButtonActive = style({
  borderColor: terminalTheme.dark.accent,
  background: terminalTheme.dark.accentSoft,
  color: terminalTheme.dark.accent,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.accent,
      background: terminalTheme.light.accentSoft,
      color: terminalTheme.light.accent,
    },
  },
});

export const connectorPanels = style({
  display: "grid",
  gap: vars.space[4],
});

export const connectorConfigGrid = style({
  display: "grid",
  gap: vars.space[4],
});

export const connectorControlGrid = style({
  alignItems: "stretch",
});

export const connectorControlCard = style({
  height: "100%",
  gridTemplateRows: "auto auto 1fr auto",
});

export const connectorControlInput = style({
  alignSelf: "end",
});

export const connectorConfigSection = style({
  display: "grid",
  gap: vars.space[3],
  padding: vars.space[4],
  borderRadius: vars.radius.card,
  border: `1px solid ${terminalTheme.dark.border}`,
  background: terminalTheme.dark.nestedSurface,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.border,
      background: terminalTheme.light.nestedSurface,
    },
  },
});

export const connectorConfigColumns = style({
  display: "grid",
  gap: vars.space[3],
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
});

export const connectorPanel = style({
  display: "grid",
  gap: vars.space[4],
  padding: vars.space[5],
  borderRadius: vars.radius.card,
  border: `1px solid ${terminalTheme.dark.border}`,
  background: terminalTheme.dark.nestedSurface,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.border,
      background: terminalTheme.light.nestedSurface,
    },
  },
});

export const connectorPanelFuture = style({
  boxShadow: `inset 0 3px 0 ${terminalTheme.dark.accent}`,
  selectors: {
    [`${shellTone.light} &`]: {
      boxShadow: `inset 0 3px 0 ${terminalTheme.light.accent}`,
    },
  },
});

export const connectorPanelSpot = style({
  boxShadow: `inset 0 3px 0 ${terminalTheme.dark.warning}`,
  selectors: {
    [`${shellTone.light} &`]: {
      boxShadow: `inset 0 3px 0 ${terminalTheme.light.warning}`,
    },
  },
});

export const connectorPanelHeader = style({
  display: "flex",
  justifyContent: "space-between",
  gap: vars.space[3],
  alignItems: "flex-start",
  flexWrap: "wrap",
});

export const connectorPanelIntro = style({
  display: "grid",
  gap: vars.space[2],
});

export const connectorStatusCard = style({
  display: "grid",
  gap: vars.space[1],
  padding: vars.space[4],
  borderRadius: vars.radius.card,
  border: `1px solid ${terminalTheme.dark.border}`,
  background: terminalTheme.dark.panelRaised,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.border,
      background: terminalTheme.light.panelRaised,
    },
  },
});

export const connectorStatusLabel = style({
  fontSize: vars.font.size[1],
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const connectorStatusValue = style({
  fontSize: vars.font.size[6],
  lineHeight: 1.1,
  color: terminalTheme.dark.textPrimary,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const connectorStatusDetail = style({
  fontSize: vars.font.size[2],
  lineHeight: 1.5,
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const connectorStatsGrid = style({
  display: "grid",
  gap: vars.space[2],
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
});

export const connectorTableWrap = style({
  overflowX: "auto",
  borderRadius: vars.radius.card,
  border: `1px solid ${terminalTheme.dark.border}`,
  background: terminalTheme.dark.panelRaised,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.border,
      background: terminalTheme.light.panelRaised,
    },
  },
});

export const connectorTable = style({
  width: "100%",
  minWidth: "680px",
  borderCollapse: "separate",
  borderSpacing: 0,
});

export const connectorTableHeadCell = style({
  padding: `${vars.space[3]} ${vars.space[4]}`,
  borderBottom: `1px solid ${terminalTheme.dark.border}`,
  background: terminalTheme.dark.nestedSurface,
  fontSize: vars.font.size[1],
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  textAlign: "left",
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      borderBottomColor: terminalTheme.light.border,
      background: terminalTheme.light.nestedSurface,
      color: terminalTheme.light.textMuted,
    },
  },
});

export const connectorTableBodyCell = style({
  padding: `${vars.space[3]} ${vars.space[4]}`,
  borderBottom: `1px solid ${terminalTheme.dark.border}`,
  verticalAlign: "top",
  color: terminalTheme.dark.textPrimary,
  selectors: {
    [`${shellTone.light} &`]: {
      borderBottomColor: terminalTheme.light.border,
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const connectorFlowPill = style({
  display: "inline-flex",
  alignItems: "center",
  padding: `${vars.space[1]} ${vars.space[2]}`,
  borderRadius: "999px",
  border: `1px solid ${terminalTheme.dark.border}`,
  background: terminalTheme.dark.nestedSurface,
  fontSize: vars.font.size[1],
  color: terminalTheme.dark.textPrimary,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.border,
      background: terminalTheme.light.nestedSurface,
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const connectorEmptyState = style({
  display: "grid",
  gap: vars.space[2],
  padding: vars.space[5],
  borderRadius: vars.radius.card,
  border: `1px dashed ${terminalTheme.dark.border}`,
  background: terminalTheme.dark.nestedSurface,
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.border,
      background: terminalTheme.light.nestedSurface,
      color: terminalTheme.light.textMuted,
    },
  },
});
