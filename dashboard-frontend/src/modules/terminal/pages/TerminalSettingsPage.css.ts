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

export const settingsForm = style({
  display: "grid",
  gap: vars.space[3],
});

export const settingsFieldGrid = style({
  display: "grid",
  gap: vars.space[3],
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 340px))",
  justifyContent: "start",
  alignItems: "start",
});

export const comparisonTableWrap = style({
  overflowX: "auto",
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

export const comparisonTable = style({
  width: "100%",
  minWidth: "720px",
  borderCollapse: "separate",
  borderSpacing: 0,
});

export const comparisonTableCompact = style({
  minWidth: "560px",
});

export const comparisonHeadCell = style({
  padding: `${vars.space[3]} ${vars.space[4]}`,
  borderBottom: `1px solid ${terminalTheme.dark.border}`,
  background: terminalTheme.dark.panelRaised,
  fontSize: vars.font.size[1],
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: terminalTheme.dark.textMuted,
  textAlign: "left",
  whiteSpace: "nowrap",
  selectors: {
    [`${shellTone.light} &`]: {
      borderBottomColor: terminalTheme.light.border,
      background: terminalTheme.light.panelRaised,
      color: terminalTheme.light.textMuted,
    },
  },
});

export const comparisonBodyCell = style({
  padding: vars.space[4],
  borderBottom: `1px solid ${terminalTheme.dark.border}`,
  verticalAlign: "top",
  selectors: {
    [`${shellTone.light} &`]: {
      borderBottomColor: terminalTheme.light.border,
    },
    "&:last-child": {
      borderBottom: "none",
    },
  },
});

export const comparisonRowHeader = style({
  display: "grid",
  gap: vars.space[1],
  minWidth: "180px",
});

export const comparisonRowTitle = style({
  fontSize: vars.font.size[3],
  fontWeight: vars.font.weight.semibold,
  color: terminalTheme.dark.textPrimary,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const comparisonRowDescription = style({
  fontSize: vars.font.size[2],
  lineHeight: 1.45,
  color: terminalTheme.dark.textMuted,
  maxWidth: "34ch",
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const comparisonRowCaption = style({
  fontSize: vars.font.size[1],
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const comparisonInput = style({
  width: "100%",
  minWidth: "110px",
  minHeight: "40px",
  padding: `0 ${vars.space[3]}`,
  borderRadius: "10px",
  border: `1px solid ${terminalTheme.dark.borderStrong}`,
  background: terminalTheme.dark.panelRaised,
  color: terminalTheme.dark.textPrimary,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.borderStrong,
      background: terminalTheme.light.panelRaised,
      color: terminalTheme.light.textPrimary,
    },
    "&:focus": {
      outline: `1px solid ${terminalTheme.dark.accent}`,
      borderColor: terminalTheme.dark.accent,
    },
    [`${shellTone.light} &:focus`]: {
      outline: `1px solid ${terminalTheme.light.accent}`,
      borderColor: terminalTheme.light.accent,
    },
  },
});

export const comparisonRecommendation = style({
  fontSize: vars.font.size[2],
  lineHeight: 1.5,
  color: terminalTheme.dark.textMuted,
  whiteSpace: "nowrap",
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const settingsFieldCard = style({
  display: "grid",
  gap: vars.space[2],
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

export const settingsFieldHeader = style({
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: vars.space[2],
  flexWrap: "wrap",
});

export const fieldLabel = style({
  fontSize: vars.font.size[3],
  fontWeight: vars.font.weight.semibold,
  color: terminalTheme.dark.textPrimary,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const settingsFieldMeta = style({
  fontSize: vars.font.size[1],
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const fieldDescription = style({
  fontSize: vars.font.size[2],
  lineHeight: 1.5,
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const fieldInput = style({
  minHeight: "42px",
  padding: `0 ${vars.space[3]}`,
  borderRadius: "10px",
  border: `1px solid ${terminalTheme.dark.borderStrong}`,
  background: terminalTheme.dark.panelRaised,
  color: terminalTheme.dark.textPrimary,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.borderStrong,
      background: terminalTheme.light.panelRaised,
      color: terminalTheme.light.textPrimary,
    },
    "&:focus": {
      outline: `1px solid ${terminalTheme.dark.accent}`,
      borderColor: terminalTheme.dark.accent,
    },
    [`${shellTone.light} &:focus`]: {
      outline: `1px solid ${terminalTheme.light.accent}`,
      borderColor: terminalTheme.light.accent,
    },
  },
});

export const settingsErrorState = style({
  padding: vars.space[3],
  borderRadius: "10px",
  border: `1px solid ${terminalTheme.dark.errorSoft}`,
  background: terminalTheme.dark.errorSoft,
  color: terminalTheme.dark.error,
  fontSize: vars.font.size[2],
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.errorSoft,
      background: terminalTheme.light.errorSoft,
      color: terminalTheme.light.error,
    },
  },
});

export const saveButton = style({
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
});

export const saveButtonDisabled = style({
  opacity: 0.55,
  cursor: "not-allowed",
});
