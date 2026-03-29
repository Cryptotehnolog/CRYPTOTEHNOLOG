import { style } from "@vanilla-extract/css";

import { vars } from "../../../shared/styles/theme.css";
import { shellTone } from "../../../app/layout/TerminalShell.css";
import { terminalTheme } from "../styles/terminalTheme.css";

export const pageRoot = style({
  display: "grid",
  gap: vars.space[5],
  padding: `${vars.space[5]} ${vars.space[6]} ${vars.space[6]}`,
  "@media": {
    "screen and (max-width: 900px)": {
      padding: `${vars.space[4]}`,
    },
  },
});

export const settingsCard = style({
  display: "grid",
  gap: vars.space[4],
  padding: vars.space[5],
  borderRadius: vars.radius.card,
  border: `1px solid ${terminalTheme.dark.border}`,
  background: terminalTheme.dark.panelBackground,
  boxShadow: terminalTheme.dark.shadow,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.border,
      background: terminalTheme.light.panelBackground,
      boxShadow: terminalTheme.light.shadow,
    },
  },
});

export const sectionHeader = style({
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: vars.space[3],
  flexWrap: "wrap",
});

export const sectionCaption = style({
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

export const sectionTitle = style({
  margin: `${vars.space[1]} 0 0`,
  fontSize: vars.font.size[7],
  lineHeight: 1.1,
  color: terminalTheme.dark.textPrimary,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const sectionBody = style({
  display: "grid",
  gap: vars.space[3],
});

export const stateValue = style({
  fontSize: vars.font.size[4],
  fontWeight: vars.font.weight.semibold,
  color: terminalTheme.dark.textPrimary,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const modeControls = style({
  display: "flex",
  gap: vars.space[2],
  flexWrap: "wrap",
});

export const modeButton = style({
  padding: `${vars.space[2]} ${vars.space[3]}`,
  borderRadius: "10px",
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

export const modeButtonActive = style({
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

export const localStateNote = style({
  fontSize: vars.font.size[2],
  lineHeight: 1.5,
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const exchangeGrid = style({
  display: "grid",
  gap: vars.space[3],
});

export const exchangeCard = style({
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

export const exchangeRow = style({
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: vars.space[3],
  flexWrap: "wrap",
});

export const exchangeMeta = style({
  marginTop: vars.space[1],
  fontSize: vars.font.size[2],
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const exchangeToggle = style({
  padding: `${vars.space[2]} ${vars.space[3]}`,
  borderRadius: "10px",
  border: `1px solid ${terminalTheme.dark.borderStrong}`,
  background: terminalTheme.dark.panelRaised,
  color: terminalTheme.dark.textPrimary,
  cursor: "pointer",
  transition: "border-color 160ms ease, background 160ms ease, color 160ms ease",
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.borderStrong,
      background: terminalTheme.light.panelRaised,
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const widgetSettingsGrid = style({
  display: "grid",
  gap: vars.space[3],
});

export const widgetSettingsCard = style({
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

export const widgetSettingsRow = style({
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: vars.space[3],
  flexWrap: "wrap",
});

export const widgetSettingsMeta = style({
  marginTop: vars.space[1],
  fontSize: vars.font.size[2],
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const widgetVisibilityControl = style({
  display: "inline-flex",
  alignItems: "center",
  gap: vars.space[2],
});

export const widgetVisibilityCheckbox = style({
  width: "18px",
  height: "18px",
  accentColor: terminalTheme.dark.accent,
  selectors: {
    [`${shellTone.light} &`]: {
      accentColor: terminalTheme.light.accent,
    },
  },
});
