import { globalStyle, style } from "@vanilla-extract/css";

import { vars } from "../../../shared/styles/theme.css";
import { shellTone } from "../../../app/layout/TerminalShell.css";
import { terminalTheme } from "../styles/terminalTheme.css";

export const pageRoot = style({
  display: "grid",
  gap: vars.space[4],
  padding: "18px 20px 20px",
  minHeight: "calc(100vh - 106px)",
  "@media": {
    "screen and (max-width: 720px)": {
      padding: "14px",
    },
  },
});

export const layoutGrid = style({
  display: "grid",
  gridTemplateColumns: "minmax(0, 1.8fr) minmax(320px, 0.9fr)",
  gap: vars.space[4],
  alignItems: "stretch",
  "@media": {
    "screen and (max-width: 1180px)": {
      gridTemplateColumns: "minmax(0, 1fr)",
    },
  },
});

const cardBase = {
  borderRadius: "24px",
  background: terminalTheme.dark.panelBackground,
  border: `1px solid ${terminalTheme.dark.border}`,
  boxShadow: terminalTheme.dark.shadow,
  backdropFilter: "blur(18px)",
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.panelBackground,
      borderColor: terminalTheme.light.border,
      boxShadow: terminalTheme.light.shadow,
    },
  },
};

export const workspaceCard = style({
  ...cardBase,
  padding: "20px",
  display: "grid",
  gap: vars.space[3],
  height: "100%",
  alignContent: "stretch",
  overflow: "hidden",
});

export const card = style({
  ...cardBase,
  padding: "20px",
  display: "grid",
  gap: vars.space[4],
  height: "100%",
  alignContent: "start",
  overflow: "hidden",
});

export const compactCard = style({
  ...cardBase,
  padding: "18px",
  display: "grid",
  gap: vars.space[2],
  height: "100%",
  alignContent: "start",
  overflow: "hidden",
});

export const secondaryStack = style({
  display: "grid",
  gap: vars.space[4],
  alignContent: "start",
});

export const sectionHeader = style({
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: vars.space[3],
  flexWrap: "wrap",
});

export const chartHeader = style({
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) auto",
  gap: vars.space[2],
  alignItems: "start",
  minWidth: 0,
  "@media": {
    "screen and (max-width: 1080px)": {
      gridTemplateColumns: "1fr",
      gap: vars.space[2],
    },
  },
});

export const chartHeaderLead = style({
  display: "grid",
  gap: "4px",
  minWidth: 0,
  alignContent: "start",
});

export const chartHeaderControlsColumn = style({
  display: "grid",
  justifyItems: "end",
  alignContent: "start",
  gap: "6px",
  minWidth: 0,
  "@media": {
    "screen and (max-width: 1080px)": {
      justifyItems: "start",
      width: "100%",
    },
  },
});

export const sectionCaption = style({
  marginBottom: vars.space[1],
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
  margin: 0,
  fontSize: "clamp(1.2rem, 2vw, 1.85rem)",
  lineHeight: 1.04,
  letterSpacing: "-0.03em",
  color: terminalTheme.dark.textPrimary,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const chartToolbar = style({
  display: "grid",
  gap: "2px",
  justifyItems: "end",
  minWidth: 0,
  alignContent: "start",
  "@media": {
    "screen and (max-width: 1080px)": {
      justifyItems: "start",
      minWidth: 0,
    },
  },
});

export const chartToolbarGroup = style({
  display: "flex",
  alignItems: "center",
  flexWrap: "wrap",
  gap: "6px",
  justifyContent: "flex-end",
  "@media": {
    "screen and (max-width: 1080px)": {
      justifyContent: "flex-start",
    },
  },
});

export const chartToolbarMenuAnchor = style({
  position: "relative",
});

export const chartToolbarTimeframes = style({
  display: "flex",
  alignItems: "center",
  flexWrap: "wrap",
  gap: "6px",
  justifyContent: "flex-end",
  "@media": {
    "screen and (max-width: 1080px)": {
      justifyContent: "flex-start",
    },
  },
});

const timeframeControlBase = style({
  minHeight: "34px",
  padding: `0 ${vars.space[2]}`,
  borderRadius: "12px",
  border: `1px solid ${terminalTheme.dark.border}`,
  background: terminalTheme.dark.nestedSurface,
  color: terminalTheme.dark.textSecondary,
  fontSize: vars.font.size[2],
  fontWeight: vars.font.weight.semibold,
  letterSpacing: "0.04em",
  appearance: "none",
  cursor: "pointer",
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.border,
      background: terminalTheme.light.nestedSurface,
      color: terminalTheme.light.textSecondary,
    },
  },
});

export const displayModeButton = style([
  timeframeControlBase,
  {
    cursor: "pointer",
    transition: "border-color 160ms ease, background 160ms ease, color 160ms ease",
  },
]);

export const displayModeButtonActive = style({
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

export const chartToolbarMenuTrigger = style([
  timeframeControlBase,
  {
    minWidth: "36px",
    justifyContent: "center",
    cursor: "pointer",
    fontSize: vars.font.size[3],
    lineHeight: 1,
    transition: "border-color 160ms ease, background 160ms ease, color 160ms ease",
  },
]);

export const chartToolbarMenu = style({
  position: "absolute",
  top: "calc(100% + 10px)",
  right: 0,
  zIndex: 4,
  display: "grid",
  gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
  gap: vars.space[1],
  minWidth: "264px",
  padding: vars.space[2],
  borderRadius: "18px",
  border: `1px solid ${terminalTheme.dark.borderStrong}`,
  background: terminalTheme.dark.panelRaised,
  boxShadow: terminalTheme.dark.shadow,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.borderStrong,
      background: terminalTheme.light.panelRaised,
      boxShadow: terminalTheme.light.shadow,
    },
  },
  "@media": {
    "screen and (max-width: 720px)": {
      left: 0,
      right: "auto",
      gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
      minWidth: "228px",
    },
  },
});

export const chartToolbarMenuButton = style([
  timeframeControlBase,
  {
    minWidth: 0,
    width: "100%",
    justifyContent: "center",
    cursor: "pointer",
    transition: "border-color 160ms ease, background 160ms ease, color 160ms ease",
  },
]);

export const chartToolbarMenuItem = style({
  opacity: 0.86,
});

export const chartToolbarMenuItemActive = style({
  borderColor: terminalTheme.dark.accent,
  background: terminalTheme.dark.accentSoft,
  color: terminalTheme.dark.accent,
  opacity: 1,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.accent,
      background: terminalTheme.light.accentSoft,
      color: terminalTheme.light.accent,
    },
  },
});

export const chartToolbarMenuDivider = style({
  gridColumn: "1 / -1",
  height: "1px",
  margin: `${vars.space[1]} 0`,
  background: terminalTheme.dark.divider,
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.divider,
    },
  },
});

export const chartToolbarMenuItemWrap = style({
  position: "relative",
});

export const chartToolbarMenuRemoveButton = style({
  position: "absolute",
  top: "4px",
  right: "4px",
  width: "18px",
  height: "18px",
  display: "grid",
  placeItems: "center",
  padding: 0,
  borderRadius: "999px",
  border: `1px solid ${terminalTheme.dark.borderStrong}`,
  background: terminalTheme.dark.panelRaised,
  color: terminalTheme.dark.textMuted,
  cursor: "pointer",
  fontSize: "12px",
  lineHeight: 1,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.borderStrong,
      background: terminalTheme.light.panelRaised,
      color: terminalTheme.light.textMuted,
    },
  },
});

export const chartToolbarMenuForm = style({
  gridColumn: "1 / -1",
  display: "grid",
  gap: vars.space[2],
  paddingTop: vars.space[1],
});

export const chartToolbarMenuFormLabel = style({
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

export const chartToolbarMenuFormRow = style({
  display: "grid",
  gridTemplateColumns: "minmax(0, 1.45fr) minmax(0, 0.75fr)",
  gap: vars.space[1],
  alignItems: "center",
});

export const chartToolbarMenuFormField = style([
  timeframeControlBase,
  {
    minWidth: 0,
  },
]);

export const chartToolbarMenuFormInput = style([
  timeframeControlBase,
  {
    minWidth: 0,
    width: "100%",
  },
]);

export const chartToolbarMenuFormAction = style([
  timeframeControlBase,
  {
    justifyContent: "center",
    transition: "border-color 160ms ease, background 160ms ease, color 160ms ease",
  },
]);

export const marketPriceCluster = style({
  display: "flex",
  alignItems: "center",
  flexWrap: "wrap",
  gap: "8px 12px",
  minHeight: "34px",
});

export const marketInstrumentLabel = style({
  fontSize: vars.font.size[2],
  fontWeight: vars.font.weight.semibold,
  lineHeight: 1.05,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: terminalTheme.dark.textSecondary,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textSecondary,
    },
  },
});

export const marketPrimaryValue = style({
  fontSize: "1.68rem",
  fontWeight: vars.font.weight.bold,
  lineHeight: 1.02,
  letterSpacing: "-0.03em",
  color: terminalTheme.dark.textPrimary,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const marketChangeUpStrong = style({
  fontSize: vars.font.size[3],
  fontWeight: vars.font.weight.semibold,
  lineHeight: 1,
  color: terminalTheme.dark.success,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.success,
    },
  },
});

export const marketHeaderMeta = style({
  display: "flex",
  alignItems: "center",
  flexWrap: "wrap",
  gap: vars.space[1],
  minHeight: "18px",
  paddingLeft: "36px",
  marginTop: "2px",
  color: terminalTheme.dark.textMuted,
  fontSize: vars.font.size[1],
  letterSpacing: "0.04em",
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
  "@media": {
    "screen and (max-width: 720px)": {
      paddingLeft: 0,
    },
  },
});

export const workspaceFooter = style({
  display: "grid",
  gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
  gap: vars.space[3],
  "@media": {
    "screen and (max-width: 860px)": {
      gridTemplateColumns: "1fr",
    },
  },
});

export const chartStat = style({
  minHeight: 0,
  height: "100%",
  padding: "14px 16px",
  borderRadius: "16px",
  background: terminalTheme.dark.nestedSurface,
  border: `1px solid ${terminalTheme.dark.border}`,
  display: "flex",
  alignItems: "center",
  justifyContent: "flex-start",
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.nestedSurface,
      borderColor: terminalTheme.light.border,
    },
  },
});

export const chartStatLabel = style({
  display: "block",
  fontSize: vars.font.size[1],
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
  marginBottom: vars.space[1],
});

export const chartStatValue = style({
  display: "block",
  fontSize: vars.font.size[3],
  color: terminalTheme.dark.textPrimary,
  fontWeight: vars.font.weight.medium,
  lineHeight: 1.25,
  maxWidth: "18ch",
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const marketGrid = style({
  display: "grid",
  gridAutoRows: "max-content",
  gap: vars.space[1],
  height: "100%",
  alignContent: "start",
});

export const marketPair = style({
  display: "grid",
  minHeight: "84px",
  flexShrink: 0,
  padding: "12px 13px",
  borderRadius: "15px",
  background: terminalTheme.dark.nestedSurface,
  border: `1px solid ${terminalTheme.dark.border}`,
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.nestedSurface,
      borderColor: terminalTheme.light.border,
    },
    "&:focus-visible": {
      outline: `1px solid ${terminalTheme.dark.accent}`,
      outlineOffset: "2px",
    },
    [`${shellTone.light} &:focus-visible`]: {
      outline: `1px solid ${terminalTheme.light.accent}`,
      outlineOffset: "2px",
    },
  },
  cursor: "pointer",
});

export const marketPairActive = style({
  borderColor: terminalTheme.dark.accent,
  boxShadow: `inset 0 0 0 1px ${terminalTheme.dark.accentSoft}`,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.accent,
      boxShadow: `inset 0 0 0 1px ${terminalTheme.light.accentSoft}`,
    },
  },
});

export const marketPairBody = style({
  minWidth: 0,
  display: "grid",
  gap: "6px",
});

export const marketPairHeader = style({
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) auto",
  alignItems: "start",
  gap: vars.space[2],
  minWidth: 0,
});

export const marketPairMain = style({
  minWidth: 0,
  display: "flex",
  alignItems: "center",
  flexWrap: "wrap",
  gap: "6px 8px",
});

export const marketPairPrice = style({
  color: terminalTheme.dark.textPrimary,
  fontWeight: vars.font.weight.medium,
  lineHeight: 1.15,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const marketPairMeta = style({
  fontSize: vars.font.size[2],
  marginTop: "4px",
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const marketPairContext = style({
  display: "flex",
  alignItems: "center",
  flexWrap: "wrap",
  gap: "4px 8px",
  minWidth: 0,
  fontSize: vars.font.size[1],
  letterSpacing: "0.04em",
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const marketPairExchange = style({
  textTransform: "uppercase",
  fontSize: vars.font.size[1],
  letterSpacing: "0.08em",
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const marketPairSignal = style({
  color: terminalTheme.dark.textSecondary,
  fontSize: vars.font.size[2],
  fontWeight: vars.font.weight.medium,
  lineHeight: 1.3,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textSecondary,
    },
  },
});

export const marketPairDetails = style({
  minWidth: 0,
});

export const marketPairQuote = style({
  minWidth: "96px",
  display: "grid",
  justifyItems: "end",
  gap: "4px",
});

export const marketPairPriceMain = style({
  fontSize: vars.font.size[3],
  fontWeight: vars.font.weight.semibold,
  lineHeight: 1.1,
  color: terminalTheme.dark.textPrimary,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

const marketMoveBase = style({
  fontSize: vars.font.size[2],
  fontWeight: vars.font.weight.semibold,
});

export const marketPairMoveUp = style([
  marketMoveBase,
  {
    color: terminalTheme.dark.success,
    selectors: {
      [`${shellTone.light} &`]: {
        color: terminalTheme.light.success,
      },
    },
  },
]);

export const marketPairMoveDown = style([
  marketMoveBase,
  {
    color: terminalTheme.dark.error,
    selectors: {
      [`${shellTone.light} &`]: {
        color: terminalTheme.light.error,
      },
    },
  },
]);

export const attentionList = style({
  display: "grid",
  gridAutoRows: "max-content",
  gap: vars.space[1],
  height: "100%",
  alignContent: "start",
});

export const attentionItem = style({
  minHeight: "104px",
  padding: "12px 14px",
  borderRadius: "16px",
  background: terminalTheme.dark.warningSoft,
  border: `1px solid ${terminalTheme.dark.warning}`,
  color: terminalTheme.dark.textPrimary,
  display: "grid",
  alignContent: "start",
  gap: "6px",
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.warningSoft,
      borderColor: terminalTheme.light.warning,
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const attentionHeader = style({
  display: "grid",
  gridTemplateColumns: "auto minmax(0, 1fr) auto",
  alignItems: "center",
  gap: "8px",
  minWidth: 0,
});

export const attentionSeverity = style({
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "22px",
  padding: "0 8px",
  borderRadius: "999px",
  border: `1px solid ${terminalTheme.dark.warning}`,
  background: "rgba(245, 158, 11, 0.12)",
  fontSize: vars.font.size[1],
  fontWeight: vars.font.weight.semibold,
  letterSpacing: "0.04em",
  color: terminalTheme.dark.warning,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.warning,
      color: terminalTheme.light.warning,
    },
  },
});

export const attentionSeverityHigh = style({
  borderColor: terminalTheme.dark.error,
  background: "rgba(239, 68, 68, 0.12)",
  color: terminalTheme.dark.error,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.error,
      color: terminalTheme.light.error,
    },
  },
});

export const attentionSeverityMedium = style({});

export const attentionStatus = style({
  minWidth: 0,
  fontSize: vars.font.size[1],
  lineHeight: 1.25,
  letterSpacing: "0.04em",
  color: terminalTheme.dark.textSecondary,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textSecondary,
    },
  },
});

export const attentionTimestamp = style({
  fontSize: vars.font.size[1],
  lineHeight: 1.2,
  whiteSpace: "nowrap",
  color: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const attentionSummary = style({
  fontSize: vars.font.size[3],
  fontWeight: vars.font.weight.semibold,
  lineHeight: 1.28,
  color: terminalTheme.dark.textPrimary,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const attentionMeta = style({
  fontSize: vars.font.size[2],
  lineHeight: 1.42,
  color: terminalTheme.dark.textSecondary,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textSecondary,
    },
  },
});

export const positionsTable = style({
  display: "grid",
  gridTemplateRows: "auto auto minmax(0, 1fr)",
  gap: "1px",
  borderRadius: "20px",
  width: "max-content",
  minWidth: "100%",
  overflow: "hidden",
  background: terminalTheme.dark.border,
  boxShadow: `0 0 0 1px ${terminalTheme.dark.border}, 0 16px 32px rgba(5, 10, 24, 0.18)`,
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.border,
      boxShadow: `0 0 0 1px ${terminalTheme.light.border}, 0 14px 28px rgba(15, 23, 42, 0.08)`,
    },
  },
});

export const positionsHistoryControls = style({
  display: "flex",
  justifyContent: "flex-start",
  flexWrap: "wrap",
  gap: "8px",
  alignItems: "center",
  minHeight: "56px",
  padding: "12px 16px 11px",
  background: terminalTheme.dark.nestedSurface,
  boxShadow: `inset 0 -1px 0 ${terminalTheme.dark.border}`,
  borderBottom: `1px solid ${terminalTheme.dark.border}`,
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.nestedSurface,
      boxShadow: `inset 0 -1px 0 ${terminalTheme.light.border}`,
      borderBottom: `1px solid ${terminalTheme.light.border}`,
    },
  },
});

export const positionsHistoryControlsGroup = style({
  display: "flex",
  alignItems: "center",
  justifyContent: "flex-start",
  flexWrap: "wrap",
  gap: "8px",
});

const historyControlBase = style({
  minHeight: "34px",
  padding: "0 12px",
  borderRadius: "10px",
  border: `1px solid ${terminalTheme.dark.border}`,
  background: terminalTheme.dark.panelRaised,
  color: terminalTheme.dark.textSecondary,
  fontSize: vars.font.size[2],
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.border,
      background: terminalTheme.light.panelRaised,
      color: terminalTheme.light.textSecondary,
    },
  },
});

export const positionsHistorySearchInput = style([
  historyControlBase,
  {
    width: "100%",
    minWidth: 0,
    maxWidth: "160px",
    flex: "0 1 160px",
  },
]);

export const positionsHistorySelect = style([
  historyControlBase,
  {
    minWidth: "156px",
  },
]);

const tableGrid = {
  display: "grid",
  gridTemplateColumns: "0.8fr 1fr 1fr 0.85fr 1.05fr 0.9fr 0.95fr 0.9fr",
  gap: "12px",
  alignItems: "center",
  "@media": {
    "screen and (max-width: 1240px)": {
      gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    },
    "screen and (max-width: 980px)": {
      gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    },
    "screen and (max-width: 820px)": {
      gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    },
  },
} as const;

export const tableHeader = style({
  ...tableGrid,
  minHeight: "52px",
  padding: "10px 16px 11px",
  background: terminalTheme.dark.nestedSurface,
  color: terminalTheme.dark.textMuted,
  fontSize: vars.font.size[1],
  fontWeight: vars.font.weight.semibold,
  textAlign: "center",
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  boxShadow: `inset 0 -1px 0 ${terminalTheme.dark.border}`,
  overflow: "hidden",
  alignItems: "start",
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.nestedSurface,
      color: terminalTheme.light.textMuted,
      boxShadow: `inset 0 -1px 0 ${terminalTheme.light.border}`,
    },
  },
});

export const positionsTableBodyViewport = style({
  display: "block",
  minHeight: 0,
  height: "100%",
  overflowY: "auto",
  overflowX: "visible",
  paddingRight: "2px",
  background: terminalTheme.dark.panelRaised,
  scrollbarWidth: "thin",
  scrollbarColor: `${terminalTheme.dark.borderStrong} transparent`,
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.panelRaised,
      scrollbarColor: `${terminalTheme.light.borderStrong} transparent`,
    },
  },
});

export const positionsEmptyState = style({
  display: "grid",
  gap: "6px",
  alignContent: "start",
  justifyItems: "stretch",
  minHeight: "152px",
  padding: "16px 18px 18px",
  background: terminalTheme.dark.panelRaised,
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.panelRaised,
    },
  },
});

export const positionsEmptyStateCentered = style({
  width: "100%",
  justifyItems: "start",
  alignItems: "start",
  alignContent: "start",
  textAlign: "left",
});

export const positionsCompactHeaderCell = style({
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "32px",
  padding: "2px 6px",
  textAlign: "center",
  lineHeight: 1.35,
  whiteSpace: "normal",
  minWidth: 0,
});

export const positionsCompactHeaderDragHandle = style({
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "32px",
  width: "100%",
  minWidth: 0,
  padding: "2px 8px",
  borderRadius: "10px",
  cursor: "grab",
  userSelect: "none",
  transition: "background 140ms ease, color 140ms ease, opacity 140ms ease",
  selectors: {
    "&:hover": {
      background: terminalTheme.dark.nestedSurface,
      color: terminalTheme.dark.textPrimary,
    },
    "&:active": {
      cursor: "grabbing",
    },
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
    [`${shellTone.light} &:hover`]: {
      background: terminalTheme.light.nestedSurface,
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const positionsCompactHeaderDragging = style({
  opacity: 0.48,
});

export const positionsCompactHeaderDropTarget = style({
  background: terminalTheme.dark.accentSoft,
  color: terminalTheme.dark.accent,
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.accentSoft,
      color: terminalTheme.light.accent,
    },
  },
});

export const positionsCompactCenteredValueCell = style({
  justifyItems: "center",
  textAlign: "center",
});

export const positionsCompactCenteredSimpleCell = style({
  justifyContent: "center",
  textAlign: "center",
});

export const tableRow = style({
  ...tableGrid,
  minHeight: "78px",
  padding: "16px",
  background: terminalTheme.dark.panelRaised,
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.panelRaised,
    },
  },
});

export const tableRowInteractive = style({
  cursor: "pointer",
  selectors: {
    "&:focus-visible": {
      outline: `1px solid ${terminalTheme.dark.accent}`,
      outlineOffset: "-1px",
    },
    [`${shellTone.light} &:focus-visible`]: {
      outline: `1px solid ${terminalTheme.light.accent}`,
      outlineOffset: "-1px",
    },
  },
});

export const tableRowActive = style({
  boxShadow: `inset 0 0 0 1px ${terminalTheme.dark.accentSoft}`,
  borderLeft: `1px solid ${terminalTheme.dark.accent}`,
  selectors: {
    [`${shellTone.light} &`]: {
      boxShadow: `inset 0 0 0 1px ${terminalTheme.light.accentSoft}`,
      borderLeft: `1px solid ${terminalTheme.light.accent}`,
    },
  },
});

export const tableCell = style({
  minWidth: 0,
  color: terminalTheme.dark.textPrimary,
  fontSize: vars.font.size[3],
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const positionPairCell = style([
  tableCell,
  {
    display: "grid",
    gap: "4px",
  },
]);

export const positionInstrumentActive = style({
  color: terminalTheme.dark.accent,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.accent,
    },
  },
});

export const positionPrimaryValue = style({
  color: terminalTheme.dark.textPrimary,
  fontSize: vars.font.size[3],
  fontWeight: vars.font.weight.semibold,
  lineHeight: 1.2,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const positionSecondaryValue = style({
  color: terminalTheme.dark.textMuted,
  fontSize: vars.font.size[2],
  lineHeight: 1.35,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

const positionSideBadgeBase = style({
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "28px",
  padding: "0 10px",
  borderRadius: "999px",
  border: `1px solid ${terminalTheme.dark.borderStrong}`,
  background: terminalTheme.dark.nestedSurface,
  fontSize: vars.font.size[2],
  fontWeight: vars.font.weight.semibold,
  letterSpacing: "0.04em",
  whiteSpace: "nowrap",
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.borderStrong,
      background: terminalTheme.light.nestedSurface,
    },
  },
});

export const positionSideLong = style([
  positionSideBadgeBase,
  {
    color: terminalTheme.dark.success,
    selectors: {
      [`${shellTone.light} &`]: {
        color: terminalTheme.light.success,
      },
    },
  },
]);

export const positionSideShort = style([
  positionSideBadgeBase,
  {
    color: terminalTheme.dark.error,
    selectors: {
      [`${shellTone.light} &`]: {
        color: terminalTheme.light.error,
      },
    },
  },
]);

export const positionMetricCell = style([
  tableCell,
  {
    display: "grid",
    gap: "4px",
  },
]);

export const positionStrategyCell = style([
  tableCell,
  {
    display: "grid",
    gap: "4px",
  },
]);

export const positionStatusCell = style([
  tableCell,
  {
    display: "grid",
    gap: "4px",
  },
]);

export const positionStatusValue = style({
  color: terminalTheme.dark.textPrimary,
  fontSize: vars.font.size[2],
  fontWeight: vars.font.weight.medium,
  lineHeight: 1.3,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const positionStatusMeta = style({
  color: terminalTheme.dark.textMuted,
  fontSize: vars.font.size[2],
  lineHeight: 1.35,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const positionTimestampCell = style([
  tableCell,
  {
    display: "grid",
    gap: "4px",
  },
]);

export const positionPnlPositiveText = style({
  color: terminalTheme.dark.success,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.success,
    },
  },
});

export const positionPnlNegativeText = style({
  color: terminalTheme.dark.error,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.error,
    },
  },
});

export const positionActionsCell = style({
  position: "relative",
  display: "grid",
  gridTemplateColumns: "minmax(0, 1fr) auto",
  alignItems: "center",
  gap: vars.space[2],
  minWidth: 0,
});

export const positionActionsAnchor = style({
  position: "relative",
  display: "inline-flex",
  justifySelf: "end",
  alignItems: "center",
});

export const positionActionsTrigger = style({
  width: "30px",
  height: "30px",
  display: "grid",
  placeItems: "center",
  padding: 0,
  borderRadius: "11px",
  border: `1px solid ${terminalTheme.dark.border}`,
  background: terminalTheme.dark.nestedSurface,
  color: terminalTheme.dark.textMuted,
  fontSize: "18px",
  fontWeight: vars.font.weight.semibold,
  lineHeight: 1,
  cursor: "pointer",
  transition: "border-color 140ms ease, background 140ms ease, color 140ms ease, box-shadow 140ms ease",
  selectors: {
    "&:hover": {
      borderColor: terminalTheme.dark.borderStrong,
      color: terminalTheme.dark.textSecondary,
    },
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.border,
      background: terminalTheme.light.nestedSurface,
      color: terminalTheme.light.textMuted,
    },
    [`${shellTone.light} &:hover`]: {
      borderColor: terminalTheme.light.borderStrong,
      color: terminalTheme.light.textSecondary,
    },
  },
});

export const positionActionsMenu = style({
  display: "grid",
  gap: "4px",
  width: "100%",
  minWidth: 0,
  padding: "6px",
  borderRadius: "14px",
  border: `1px solid ${terminalTheme.dark.borderStrong}`,
  background: terminalTheme.dark.panelRaised,
  boxShadow: terminalTheme.dark.shadow,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.borderStrong,
      background: terminalTheme.light.panelRaised,
      boxShadow: terminalTheme.light.shadow,
    },
  },
});

export const positionActionsMenuItem = style({
  minHeight: "32px",
  display: "flex",
  alignItems: "center",
  width: "100%",
  padding: "0 10px",
  border: "none",
  borderRadius: "10px",
  background: "transparent",
  color: terminalTheme.dark.textSecondary,
  fontSize: vars.font.size[2],
  fontWeight: vars.font.weight.medium,
  textAlign: "left",
  cursor: "pointer",
  transition: "background 140ms ease, color 140ms ease",
  selectors: {
    "&:hover": {
      background: terminalTheme.dark.nestedSurface,
      color: terminalTheme.dark.textPrimary,
    },
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textSecondary,
    },
    [`${shellTone.light} &:hover`]: {
      background: terminalTheme.light.nestedSurface,
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const positionActionPanel = style({
  display: "grid",
  gap: "8px",
  width: "100%",
  padding: "10px 12px",
  borderRadius: "14px",
  border: `1px solid ${terminalTheme.dark.borderStrong}`,
  background: terminalTheme.dark.panelRaised,
  boxShadow: terminalTheme.dark.shadow,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.borderStrong,
      background: terminalTheme.light.panelRaised,
      boxShadow: terminalTheme.light.shadow,
    },
  },
});

export const positionActionPanelUp = style({
  transformOrigin: "bottom right",
});

export const positionActionPanelMeta = style({
  display: "grid",
  gap: "2px",
  minWidth: 0,
});

export const positionActionPanelTitle = style({
  color: terminalTheme.dark.textPrimary,
  fontSize: vars.font.size[2],
  fontWeight: vars.font.weight.semibold,
  lineHeight: 1.3,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const positionActionPanelText = style({
  color: terminalTheme.dark.textMuted,
  fontSize: vars.font.size[1],
  lineHeight: 1.4,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textMuted,
    },
  },
});

export const positionActionPanelActions = style({
  display: "flex",
  alignItems: "center",
  justifyContent: "flex-end",
  gap: vars.space[1],
});

const positionActionPanelButtonBase = style({
  minHeight: "32px",
  padding: "0 12px",
  borderRadius: "10px",
  fontSize: vars.font.size[2],
  fontWeight: vars.font.weight.semibold,
  cursor: "pointer",
  transition: "border-color 140ms ease, background 140ms ease, color 140ms ease",
});

export const positionActionPanelCancel = style([
  positionActionPanelButtonBase,
  {
    border: `1px solid ${terminalTheme.dark.border}`,
    background: terminalTheme.dark.nestedSurface,
    color: terminalTheme.dark.textSecondary,
    selectors: {
      [`${shellTone.light} &`]: {
        borderColor: terminalTheme.light.border,
        background: terminalTheme.light.nestedSurface,
        color: terminalTheme.light.textSecondary,
      },
    },
  },
]);

export const positionActionPanelConfirm = style([
  positionActionPanelButtonBase,
  {
    border: `1px solid ${terminalTheme.dark.accent}`,
    background: terminalTheme.dark.accentSoft,
    color: terminalTheme.dark.accent,
    selectors: {
      [`${shellTone.light} &`]: {
        borderColor: terminalTheme.light.accent,
        background: terminalTheme.light.accentSoft,
        color: terminalTheme.light.accent,
      },
    },
  },
]);

export const widgetCanvas = style({
  minHeight: "calc(100vh - 148px)",
});

export const widgetShell = style({
  height: "100%",
});

export const widgetHeaderRow = style({
  display: "flex",
  alignItems: "center",
  gap: vars.space[2],
  minHeight: "34px",
  paddingBottom: vars.space[2],
  borderBottom: `1px solid ${terminalTheme.dark.divider}`,
  selectors: {
    [`${shellTone.light} &`]: {
      borderBottomColor: terminalTheme.light.divider,
    },
  },
});

export const widgetDragHandle = style({
  width: "24px",
  height: "24px",
  flex: "0 0 24px",
  display: "grid",
  gridTemplateColumns: "repeat(3, 1fr)",
  gridTemplateRows: "repeat(3, 1fr)",
  gap: "2px",
  alignItems: "center",
  justifyItems: "center",
  padding: "4px",
  border: "none",
  background: "transparent",
  borderRadius: "8px",
  cursor: "grab",
  userSelect: "none",
  outline: "none",
  selectors: {
    "&:active": {
      cursor: "grabbing",
    },
  },
});

export const widgetDragDots = style({
  width: "3px",
  height: "3px",
  borderRadius: "999px",
  background: terminalTheme.dark.textMuted,
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.textMuted,
    },
  },
});

export const widgetHeaderMeta = style({
  minWidth: 0,
  flex: 1,
});

export const widgetHeaderControls = style({
  display: "inline-flex",
  alignItems: "center",
  gap: vars.space[1],
});

export const widgetFrame = style({
  display: "flex",
  flexDirection: "column",
  height: "100%",
  minHeight: 0,
  overflow: "hidden",
});

const widgetControlBase = style({
  width: "28px",
  height: "28px",
  display: "grid",
  placeItems: "center",
  padding: 0,
  borderRadius: "10px",
  border: `1px solid ${terminalTheme.dark.border}`,
  background: terminalTheme.dark.nestedSurface,
  color: terminalTheme.dark.textMuted,
  fontSize: vars.font.size[2],
  lineHeight: 1,
  cursor: "pointer",
  transition: "border-color 140ms ease, background 140ms ease, color 140ms ease, box-shadow 140ms ease",
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.border,
      background: terminalTheme.light.nestedSurface,
      color: terminalTheme.light.textMuted,
    },
  },
});

export const widgetFocusControl = style([
  widgetControlBase,
  {
    selectors: {
      "&:hover": {
        borderColor: terminalTheme.dark.borderStrong,
        color: terminalTheme.dark.textSecondary,
      },
      [`${shellTone.light} &:hover`]: {
        borderColor: terminalTheme.light.borderStrong,
        color: terminalTheme.light.textSecondary,
      },
    },
  },
]);

export const widgetFocusControlActive = style({
  borderColor: terminalTheme.dark.accent,
  background: terminalTheme.dark.accentSoft,
  color: terminalTheme.dark.accent,
  boxShadow: `0 0 0 1px ${terminalTheme.dark.accentSoft}`,
  selectors: {
    [`${shellTone.light} &`]: {
      borderColor: terminalTheme.light.accent,
      background: terminalTheme.light.accentSoft,
      color: terminalTheme.light.accent,
      boxShadow: `0 0 0 1px ${terminalTheme.light.accentSoft}`,
    },
  },
});

export const widgetTitle = style({
  margin: 0,
  minWidth: 0,
  fontSize: vars.font.size[4],
  lineHeight: 1.1,
  letterSpacing: "-0.02em",
  fontWeight: vars.font.weight.semibold,
  color: terminalTheme.dark.textPrimary,
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const widgetFrameContent = style({
  minHeight: 0,
  minWidth: 0,
  flex: 1,
  display: "grid",
  alignContent: "stretch",
  gap: vars.space[3],
  overflow: "hidden",
});

export const compactListContent = style([
  widgetFrameContent,
  {
    gap: vars.space[2],
    alignContent: "start",
  },
]);

export const compactStatContent = style([
  widgetFrameContent,
  {
    gap: vars.space[2],
    alignContent: "stretch",
  },
]);

export const scrollableWidgetContent = style([
  widgetFrameContent,
  {
    display: "block",
    overflowY: "auto",
    overflowX: "hidden",
    paddingRight: "4px",
    scrollbarWidth: "thin",
    scrollbarColor: `${terminalTheme.dark.borderStrong} transparent`,
    selectors: {
      [`${shellTone.light} &`]: {
        scrollbarColor: `${terminalTheme.light.borderStrong} transparent`,
      },
    },
  },
]);

export const positionsWidgetContent = style([
  widgetFrameContent,
  {
    gridTemplateRows: "auto minmax(0, 1fr)",
    gap: vars.space[2],
  },
]);

export const positionsWidgetHeader = style({
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: vars.space[2],
  minHeight: "34px",
  minWidth: 0,
});

export const positionsWidgetHeaderMain = style({
  display: "flex",
  alignItems: "center",
  gap: vars.space[2],
  minWidth: 0,
  flex: 1,
});

export const positionModeSwitch = style({
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
  padding: "4px",
  borderRadius: "14px",
  background: terminalTheme.dark.nestedSurface,
  border: `1px solid ${terminalTheme.dark.border}`,
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.nestedSurface,
      borderColor: terminalTheme.light.border,
    },
  },
});

export const positionModeButton = style({
  minHeight: "34px",
  padding: "0 14px",
  border: "none",
  borderRadius: "10px",
  background: "transparent",
  color: terminalTheme.dark.textSecondary,
  fontSize: vars.font.size[2],
  fontWeight: vars.font.weight.semibold,
  cursor: "pointer",
  selectors: {
    [`${shellTone.light} &`]: {
      color: terminalTheme.light.textSecondary,
    },
  },
});

export const positionModeButtonActive = style({
  background: terminalTheme.dark.panelRaised,
  color: terminalTheme.dark.textPrimary,
  selectors: {
    [`${shellTone.light} &`]: {
      background: terminalTheme.light.panelRaised,
      color: terminalTheme.light.textPrimary,
    },
  },
});

export const positionsTableViewport = style([
  {
    display: "grid",
    position: "relative",
    minHeight: 0,
    height: "100%",
    overflowX: "auto",
    overflowY: "hidden",
    scrollbarGutter: "stable",
  },
]);

export const positionActionOverlayLayer = style({
  position: "fixed",
  zIndex: 60,
  maxWidth: "calc(100vw - 24px)",
  display: "grid",
  pointerEvents: "auto",
});

export const chartWidgetContent = style([
  widgetFrameContent,
  {
    gridTemplateRows: "auto minmax(0, 1fr)",
    gap: "4px",
  },
]);

export const chartSurfaceSlot = style({
  minHeight: 0,
  height: "100%",
  display: "grid",
});

globalStyle(`${widgetCanvas} .react-grid-layout`, {
  minHeight: "calc(100vh - 148px)",
});

globalStyle(`${widgetCanvas} .react-grid-item`, {
  transition: "box-shadow 160ms ease",
  overflow: "visible",
});

globalStyle(`${widgetCanvas} .react-grid-item > div`, {
  height: "100%",
  minHeight: 0,
  minWidth: 0,
});

globalStyle(`${widgetFrameContent} > *`, {
  minWidth: 0,
  maxWidth: "100%",
});

globalStyle(`${scrollableWidgetContent}::-webkit-scrollbar`, {
  width: "8px",
});

globalStyle(`${positionsTableBodyViewport}::-webkit-scrollbar`, {
  width: "8px",
});

globalStyle(`${scrollableWidgetContent} > *`, {
  minWidth: 0,
  width: "100%",
});

globalStyle(`${scrollableWidgetContent}::-webkit-scrollbar-track`, {
  background: "transparent",
});

globalStyle(`${positionsTableBodyViewport}::-webkit-scrollbar-track`, {
  background: "transparent",
});

globalStyle(`${scrollableWidgetContent}::-webkit-scrollbar-thumb`, {
  background: terminalTheme.dark.borderStrong,
  borderRadius: "999px",
  border: "2px solid transparent",
  backgroundClip: "padding-box",
});

globalStyle(`${positionsTableBodyViewport}::-webkit-scrollbar-thumb`, {
  background: terminalTheme.dark.borderStrong,
  borderRadius: "999px",
  border: "2px solid transparent",
  backgroundClip: "padding-box",
});

globalStyle(`${shellTone.light} ${scrollableWidgetContent}::-webkit-scrollbar-thumb`, {
  background: terminalTheme.light.borderStrong,
  borderRadius: "999px",
  border: "2px solid transparent",
  backgroundClip: "padding-box",
});

globalStyle(`${shellTone.light} ${positionsTableBodyViewport}::-webkit-scrollbar-thumb`, {
  background: terminalTheme.light.borderStrong,
  borderRadius: "999px",
  border: "2px solid transparent",
  backgroundClip: "padding-box",
});

globalStyle(`${chartWidgetContent} > *`, {
  minWidth: 0,
  minHeight: 0,
});

globalStyle(`${widgetCanvas} .react-grid-item.react-draggable-dragging`, {
  zIndex: "48",
  boxShadow: terminalTheme.dark.shadow,
  pointerEvents: "none",
});

globalStyle(`${widgetCanvas} .terminal-widget-grid-item-focused`, {
  zIndex: "32",
});

globalStyle(`${widgetCanvas} .terminal-widget-grid-item-focused > div section`, {
  borderColor: terminalTheme.dark.borderStrong,
  boxShadow: "0 18px 44px rgba(7, 12, 18, 0.32)",
});

globalStyle(`${shellTone.light} ${widgetCanvas} .terminal-widget-grid-item-focused > div section`, {
  borderColor: terminalTheme.light.borderStrong,
  boxShadow: "0 18px 36px rgba(102, 128, 154, 0.18)",
});

globalStyle(`${shellTone.light} ${widgetCanvas} .react-grid-item.react-draggable-dragging`, {
  boxShadow: terminalTheme.light.shadow,
});

globalStyle(`${widgetCanvas} .react-grid-item.react-resizable-resizing`, {
  zIndex: "42",
});

globalStyle(`${widgetCanvas} .react-grid-item.react-grid-placeholder`, {
  borderRadius: "24px",
  background: terminalTheme.dark.accentSoft,
  border: `1px dashed ${terminalTheme.dark.accent}`,
});

globalStyle(`${shellTone.light} ${widgetCanvas} .react-grid-item.react-grid-placeholder`, {
  background: terminalTheme.light.accentSoft,
  border: `1px dashed ${terminalTheme.light.accent}`,
});

globalStyle(`${widgetCanvas} .react-grid-item.react-resizable`, {
  overflow: "visible",
});

globalStyle(`${widgetCanvas} .react-resizable-handle`, {
  position: "absolute",
  display: "block",
  background: "transparent",
  border: "none",
  opacity: "1",
  zIndex: "6",
});

globalStyle(`${widgetCanvas} .react-resizable-handle::after`, {
  content: "\"\"",
  display: "none",
});

globalStyle(`${widgetCanvas} .terminal-widget-resize-handle.react-resizable-handle-e`, {
  top: "50%",
  right: "-9px",
  width: "18px",
  height: "calc(100% - 28px)",
  transform: "translateY(-50%)",
  cursor: "ew-resize",
});

globalStyle(`${widgetCanvas} .terminal-widget-resize-handle.react-resizable-handle-w`, {
  top: "50%",
  left: "-9px",
  width: "18px",
  height: "calc(100% - 28px)",
  transform: "translateY(-50%)",
  cursor: "ew-resize",
});

globalStyle(`${widgetCanvas} .terminal-widget-resize-handle.react-resizable-handle-s`, {
  left: "50%",
  bottom: "-9px",
  width: "calc(100% - 28px)",
  height: "18px",
  transform: "translateX(-50%)",
  cursor: "ns-resize",
});

globalStyle(`${widgetCanvas} .terminal-widget-resize-handle.react-resizable-handle-n`, {
  left: "50%",
  top: "-9px",
  width: "calc(100% - 28px)",
  height: "18px",
  transform: "translateX(-50%)",
  cursor: "ns-resize",
});

globalStyle(`${widgetCanvas} .terminal-widget-resize-handle.react-resizable-handle-se`, {
  right: "-10px",
  bottom: "-10px",
  width: "20px",
  height: "20px",
  cursor: "nwse-resize",
});

globalStyle(`${widgetCanvas} .terminal-widget-resize-handle.react-resizable-handle-sw`, {
  left: "-10px",
  bottom: "-10px",
  width: "20px",
  height: "20px",
  cursor: "nesw-resize",
});

globalStyle(`${widgetCanvas} .terminal-widget-resize-handle.react-resizable-handle-ne`, {
  right: "-10px",
  top: "-10px",
  width: "20px",
  height: "20px",
  cursor: "nesw-resize",
});

globalStyle(`${widgetCanvas} .terminal-widget-resize-handle.react-resizable-handle-nw`, {
  left: "-10px",
  top: "-10px",
  width: "20px",
  height: "20px",
  cursor: "nwse-resize",
});
