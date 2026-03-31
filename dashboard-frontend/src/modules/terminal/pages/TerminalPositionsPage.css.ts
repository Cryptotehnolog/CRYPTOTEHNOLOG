import { style } from "@vanilla-extract/css";

import { vars } from "../../../shared/styles/theme.css";
import { shellTone } from "../../../app/layout/TerminalShell.css";
import { terminalTheme } from "../styles/terminalTheme.css";

export const positionsPageRoot = style({
  display: "grid",
  gap: vars.space[2],
  minHeight: "100%",
  padding: "4px 22px 16px",
  alignContent: "start",
});

export const positionsPageHeader = style({
  display: "grid",
  gap: 0,
});

export const positionsPageSection = style({
  padding: "0 20px 20px",
  gap: vars.space[1],
});

export const positionsPageWideViewport = style({
  position: "relative",
  display: "block",
  maxWidth: "100%",
  minWidth: 0,
  overflowX: "auto",
  overflowY: "hidden",
  scrollbarGutter: "stable",
  paddingBottom: "6px",
});

export const positionsPageWideTable = style({
  gridTemplateRows: "auto auto auto",
  width: "max-content",
  minWidth: "100%",
});

export const positionsPageBodyViewport = style({
  display: "grid",
  minHeight: "auto",
  height: "auto",
  overflow: "visible",
  paddingRight: 0,
  background: terminalTheme.dark.panelRaised,
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.panelRaised,
    },
  },
});

export const positionsPageControlsRow = style({
  gridTemplateColumns: "1fr",
  "@media": {
    "screen and (max-width: 1080px)": {
      gridTemplateColumns: "1fr",
    },
  },
});

export const positionsPageControlsCluster = style({
  display: "flex",
  alignItems: "center",
  justifyContent: "flex-start",
  flexWrap: "wrap",
  gap: "8px",
});

export const positionsPageSearchCompact = style({
  width: "100%",
  maxWidth: "160px",
  "@media": {
    "screen and (max-width: 1080px)": {
      maxWidth: "100%",
    },
  },
});

const projectionHeaderToggleBase = style({
  minHeight: "38px",
  width: "100%",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "flex-start",
  textAlign: "left",
  padding: "4px 10px",
  border: "none",
  background: "transparent",
  color: terminalTheme.dark.textSecondary,
  fontSize: vars.font.size[1],
  fontWeight: vars.font.weight.semibold,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  lineHeight: 1.35,
  whiteSpace: "normal",
  minWidth: 0,
  cursor: "pointer",
  borderRadius: "8px",
  transition: "color 140ms ease, opacity 140ms ease, background 140ms ease",
  selectors: {
    "&:hover": {
      color: terminalTheme.dark.textPrimary,
      background: terminalTheme.dark.nestedSurface,
    },
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textSecondary,
    },
    [`${shellTone.light} &:hover`]: {
      color: terminalTheme.light.textPrimary,
      background: terminalTheme.light.nestedSurface,
    },
  },
});

export const positionsHeaderToggle = style([projectionHeaderToggleBase]);

export const positionsHeaderCell = style({
  minWidth: 0,
  display: "flex",
  alignItems: "stretch",
  boxSizing: "border-box",
});

export const positionsHeaderCellCentered = style({
  justifyContent: "center",
});

export const positionsHeaderToggleActive = style({
  color: terminalTheme.dark.accent,
  background: terminalTheme.dark.accentSoft,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.accent,
      background: terminalTheme.light.accentSoft,
    },
  },
});

export const positionsHeaderToggleInactive = style({
  opacity: 0.82,
});

export const positionsHeaderToggleLocked = style({
  opacity: 0.9,
  cursor: "default",
});

export const positionsHeaderStaticLabel = style({
  display: "inline-flex",
  alignItems: "center",
  width: "100%",
  minHeight: "38px",
  padding: "4px 10px",
  color: terminalTheme.dark.textMuted,
  fontSize: vars.font.size[1],
  fontWeight: vars.font.weight.semibold,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  lineHeight: 1.35,
  whiteSpace: "normal",
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const positionsHeaderContentCentered = style({
  justifyContent: "center",
  textAlign: "center",
});

export const positionsPageTableRow = style({
  minHeight: "70px",
  padding: "13px 16px",
});

export const positionsPageInteractiveRow = style({
  transition: "background 140ms ease, box-shadow 140ms ease",
  selectors: {
    "&:hover": {
      background: terminalTheme.dark.nestedSurface,
    },
    [`${shellTone.light} &:hover`]: {
      background: terminalTheme.light.nestedSurface,
    },
  },
});

export const positionsPageCenteredValueCell = style({
  justifyItems: "center",
  textAlign: "center",
});

export const positionsPageCenteredSimpleCell = style({
  justifyContent: "center",
  textAlign: "center",
});

export const positionsPageEmptyState = style({
  width: "100%",
  justifyItems: "start",
  alignItems: "start",
  alignContent: "start",
  minHeight: "172px",
  padding: "18px 18px 20px",
});

export const positionsPageTitle = style({
  color: terminalTheme.dark.textPrimary,
  fontSize: vars.font.size[7],
  fontWeight: vars.font.weight.semibold,
  letterSpacing: "-0.02em",
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const positionsPageMeta = style({});
