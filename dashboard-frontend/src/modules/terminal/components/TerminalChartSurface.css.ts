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

export const chartDrawingToolbar = style({
  position: "absolute",
  left: "12px",
  top: "14px",
  zIndex: 4,
  display: "grid",
  gap: "6px",
  padding: "8px",
  borderRadius: "14px",
  background: "rgba(8, 14, 23, 0.88)",
  border: `1px solid ${terminalTheme.dark.divider}`,
  boxShadow: "0 10px 30px rgba(0, 0, 0, 0.24)",
  selectors: {
    [`${shellTone.light} &`]: {
      background: "rgba(255, 255, 255, 0.9)",
      borderColor: terminalTheme.light.divider,
      boxShadow: "0 10px 24px rgba(36, 60, 92, 0.12)",
    },
  },
});

export const chartDrawingToolButton = style({
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: "34px",
  height: "34px",
  borderRadius: "10px",
  border: `1px solid ${terminalTheme.dark.border}`,
  background: "rgba(14, 24, 36, 0.92)",
  color: terminalTheme.dark.textSecondary,
  fontSize: "0.73rem",
  fontWeight: vars.font.weight.semibold,
  letterSpacing: "0.06em",
  cursor: "pointer",
  transition: "background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease",
  selectors: {
    "&:hover": {
      borderColor: terminalTheme.dark.accent,
      color: terminalTheme.dark.text,
    },
    "&:disabled": {
      opacity: 0.42,
      cursor: "default",
    },
    [`${shellTone.light} &`]: {
      background: "rgba(246, 249, 252, 0.98)",
      borderColor: terminalTheme.light.border,
      color: terminalTheme.light.textSecondary,
    },
    [`${shellTone.light} &:hover`]: {
      borderColor: terminalTheme.light.accent,
      color: terminalTheme.light.text,
    },
  },
});

export const chartDrawingToolButtonActive = style({
  background: "rgba(35, 68, 104, 0.88)",
  borderColor: terminalTheme.dark.accent,
  color: terminalTheme.dark.text,
  selectors: {
    [`${shellTone.light} &`]: {
      background: "rgba(214, 238, 255, 0.94)",
      borderColor: terminalTheme.light.accent,
      color: terminalTheme.light.text,
    },
  },
});

export const chartDrawingLayer = style({
  position: "absolute",
  inset: 0,
  zIndex: 3,
  pointerEvents: "none",
});

export const chartDrawingSvg = style({
  width: "100%",
  height: "100%",
  overflow: "visible",
  pointerEvents: "none",
});

export const chartDrawingCapture = style({
  position: "absolute",
  inset: 0,
  zIndex: 4,
  cursor: "crosshair",
  background: "transparent",
});

export const chartDrawingEditor = style({
  position: "absolute",
  zIndex: 6,
  display: "inline-flex",
  alignItems: "center",
  gap: "8px",
  padding: "8px 10px",
  borderRadius: "12px",
  background: "rgba(8, 14, 23, 0.94)",
  border: `1px solid ${terminalTheme.dark.divider}`,
  boxShadow: "0 10px 24px rgba(0, 0, 0, 0.24)",
  pointerEvents: "auto",
  selectors: {
    [`${shellTone.light} &`]: {
      background: "rgba(255, 255, 255, 0.96)",
      borderColor: terminalTheme.light.divider,
      boxShadow: "0 10px 20px rgba(36, 60, 92, 0.14)",
    },
  },
});

export const chartDrawingHandle = style({
  cursor: "nwse-resize",
  pointerEvents: "auto",
});

export const chartDrawingEditorGroup = style({
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
});

export const chartDrawingField = style({
  display: "grid",
  gap: "4px",
  minWidth: "88px",
});

export const chartDrawingFieldLabel = style({
  fontSize: "0.62rem",
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const chartDrawingFieldInput = style({
  width: "100%",
  minWidth: 0,
  height: "26px",
  padding: "0 8px",
  borderRadius: "8px",
  border: `1px solid ${terminalTheme.dark.border}`,
  background: "rgba(14, 24, 36, 0.92)",
  color: terminalTheme.dark.text,
  fontSize: "0.75rem",
  fontVariantNumeric: "tabular-nums",
  outline: "none",
  selectors: {
    "&:focus": {
      borderColor: terminalTheme.dark.accent,
      boxShadow: `0 0 0 1px ${terminalTheme.dark.accentSoft}`,
    },
    [`${shellTone.light} &`]: {
      background: "rgba(246, 249, 252, 0.98)",
      borderColor: terminalTheme.light.border,
      color: terminalTheme.light.text,
    },
    [`${shellTone.light} &:focus`]: {
      borderColor: terminalTheme.light.accent,
      boxShadow: `0 0 0 1px ${terminalTheme.light.accentSoft}`,
    },
  },
});

export const chartDrawingSwatch = style({
  width: "14px",
  height: "14px",
  borderRadius: "999px",
  border: `1px solid ${terminalTheme.dark.textMuted}`,
  cursor: "pointer",
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.textMuted,
    },
  },
});

export const chartDrawingSwatchActive = style({
  transform: "scale(1.12)",
  boxShadow: `0 0 0 2px ${terminalTheme.dark.accentSoft}`,
  selectors: {
    [`${shellTone.light} &`]: {
      boxShadow: `0 0 0 2px ${terminalTheme.light.accentSoft}`,
    },
  },
});

export const chartDrawingWidthButton = style({
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minWidth: "24px",
  height: "24px",
  padding: "0 6px",
  borderRadius: "8px",
  border: `1px solid ${terminalTheme.dark.border}`,
  background: "rgba(14, 24, 36, 0.92)",
  color: terminalTheme.dark.textSecondary,
  fontSize: "0.7rem",
  cursor: "pointer",
  selectors: {
    [`${shellTone.light} &`]: {
      background: "rgba(246, 249, 252, 0.98)",
      borderColor: terminalTheme.light.border,
      color: terminalTheme.light.textSecondary,
    },
  },
});

export const chartDrawingWidthButtonActive = style({
  borderColor: terminalTheme.dark.accent,
  color: terminalTheme.dark.text,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.accent,
      color: terminalTheme.light.text,
    },
  },
});

export const chartDrawingDeleteButton = style([
  chartDrawingWidthButton,
  {
    color: terminalTheme.dark.error,
    selectors: {
      [`${shellTone.light} &`]: {
        color: terminalTheme.light.error,
      },
    },
  },
]);

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
