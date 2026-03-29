import { style } from "@vanilla-extract/css";

import { vars } from "../../../shared/styles/theme.css";
import { shellTone } from "../../../app/layout/TerminalShell.css";
import { terminalTheme } from "../styles/terminalTheme.css";

export const chartRoot = style({
  position: "relative",
  display: "grid",
  gridTemplateRows: "auto minmax(0, 1fr)",
  minHeight: 0,
  height: "100%",
  borderRadius: "22px",
  overflow: "hidden",
  background:
    "linear-gradient(180deg, rgba(12, 20, 31, 0.88) 0%, rgba(8, 14, 23, 0.96) 100%)",
  border: `1px solid ${terminalTheme.dark.border}`,
  selectors: {
    [`${shellTone.light} &`]: {
      background:
        "linear-gradient(180deg, rgba(245, 248, 252, 0.96) 0%, rgba(235, 241, 247, 0.96) 100%)",
      borderColor: terminalTheme.light.border,
    },
  },
});

export const chartCrosshairBar = style({
  display: "flex",
  alignItems: "center",
  flexWrap: "wrap",
  gap: "8px 12px",
  minHeight: "34px",
  padding: "8px 14px 6px",
  borderBottom: `1px solid ${terminalTheme.dark.divider}`,
  selectors: {
    [`${shellTone.light} &`]: {
      borderBottomColor: terminalTheme.light.divider,
    },
  },
});

export const chartCrosshairItem = style({
  display: "inline-flex",
  alignItems: "baseline",
  gap: "4px",
  minWidth: 0,
  fontVariantNumeric: "tabular-nums",
});

export const chartCrosshairLabel = style({
  fontSize: "0.68rem",
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const chartCrosshairValue = style({
  fontSize: vars.font.size[1],
  fontWeight: vars.font.weight.semibold,
  color: terminalTheme.dark.textSecondary,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textSecondary,
    },
  },
});

export const chartCrosshairMoveUp = style([
  chartCrosshairValue,
  {
    color: terminalTheme.dark.success,
    selectors: {
      [`${shellTone.light} &`]: {
        color: terminalTheme.light.success,
      },
    },
  },
]);

export const chartCrosshairMoveDown = style([
  chartCrosshairValue,
  {
    color: terminalTheme.dark.error,
    selectors: {
      [`${shellTone.light} &`]: {
        color: terminalTheme.light.error,
      },
    },
  },
]);

export const chartCanvas = style({
  display: "block",
  width: "100%",
  height: "100%",
  minHeight: 0,
});

export const chartViewport = style({
  position: "relative",
  minWidth: 0,
  minHeight: 0,
  height: "100%",
  overflow: "hidden",
});

export const chartOverlay = style({
  position: "absolute",
  left: "18px",
  top: "18px",
  display: "grid",
  gap: "6px",
  pointerEvents: "none",
  padding: `${vars.space[1]} ${vars.space[2]}`,
  borderRadius: "14px",
  background: "rgba(7, 14, 23, 0.16)",
  border: `1px solid rgba(137, 168, 199, 0.14)`,
  backdropFilter: "blur(10px)",
  selectors: {
    [`${shellTone.light} &`]: {
      background: "rgba(255, 255, 255, 0.72)",
      borderColor: "rgba(127, 153, 184, 0.18)",
    },
  },
});

export const chartOverlayStrip = style({
  display: "flex",
  alignItems: "baseline",
  flexWrap: "wrap",
  gap: vars.space[2],
  rowGap: vars.space[1],
});

export const chartOverlayMeta = style({
  fontSize: vars.font.size[1],
  textTransform: "uppercase",
  letterSpacing: "0.12em",
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

const overlayMoveBase = style({
  fontSize: vars.font.size[2],
  fontWeight: vars.font.weight.semibold,
  fontVariantNumeric: "tabular-nums",
});

export const chartOverlayMoveUp = style([
  overlayMoveBase,
  {
    color: terminalTheme.dark.success,
    selectors: {
      [`${shellTone.light} &`]: {
        color: terminalTheme.light.success,
      },
    },
  },
]);

export const chartOverlayMoveDown = style([
  overlayMoveBase,
  {
    color: terminalTheme.dark.error,
    selectors: {
      [`${shellTone.light} &`]: {
        color: terminalTheme.light.error,
      },
    },
  },
]);

export const chartOverlayStatus = style({
  fontSize: vars.font.size[1],
  letterSpacing: "0.04em",
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textSecondary,
    },
  },
});
