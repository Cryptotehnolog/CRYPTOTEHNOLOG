import { style, styleVariants } from "@vanilla-extract/css";

import { vars } from "../../shared/styles/theme.css";
import { terminalTheme as palette } from "../../modules/terminal/styles/terminalTheme.css";

export const shellRoot = style({
  position: "relative",
  display: "grid",
  gridTemplateColumns: "88px minmax(0, 1fr)",
  minHeight: "100vh",
  overflow: "hidden",
  "@media": {
    "screen and (max-width: 900px)": {
      gridTemplateColumns: "72px minmax(0, 1fr)",
    },
  },
});

export const shellTone = styleVariants({
  dark: {
    background: palette.dark.shell,
    color: palette.dark.text,
  },
  light: {
    background: palette.light.shell,
    color: palette.light.text,
  },
});

export const rail = style({
  position: "relative",
  zIndex: 3,
  display: "flex",
  flexDirection: "column",
  justifyContent: "flex-start",
  alignItems: "center",
  padding: `${vars.space[4]} ${vars.space[3]}`,
  borderRight: `1px solid ${palette.dark.border}`,
  background: palette.dark.rail,
  backdropFilter: "blur(22px)",
  selectors: {
    [`${shellTone.light} &`]: {
      borderRight: `1px solid ${palette.light.border}`,
      background: palette.light.rail,
    },
  },
});

export const railSection = style({
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: vars.space[2],
});

export const railButton = style({
  width: "3rem",
  height: "3rem",
  display: "grid",
  placeItems: "center",
  borderRadius: vars.radius.card,
  border: `1px solid ${palette.dark.border}`,
  background: "rgba(255, 255, 255, 0.03)",
  color: palette.dark.text,
  cursor: "pointer",
  transition:
    "transform 160ms ease, background 160ms ease, border-color 160ms ease",
  selectors: {
    "&:hover": {
      transform: "translateY(-1px)",
      background: palette.dark.accentSoft,
      borderColor: palette.dark.accent,
    },
    [`${shellTone.light} &`]: {
      border: `1px solid ${palette.light.border}`,
      background: palette.light.panelRaised,
      color: palette.light.text,
      boxShadow: "0 6px 18px rgba(152, 170, 193, 0.12)",
    },
    [`${shellTone.light} &:hover`]: {
      background: palette.light.accentSoft,
      borderColor: palette.light.accent,
    },
  },
});

export const tooltipContent = style({
  borderRadius: vars.radius.panel,
  padding: `${vars.space[2]} ${vars.space[3]}`,
  background: "rgba(5, 10, 16, 0.96)",
  color: "#edf3fb",
  border: `1px solid ${palette.dark.borderStrong}`,
  fontSize: vars.font.size[2],
  boxShadow: palette.dark.shadow,
  selectors: {
    [`${shellTone.light} &`]: {
      background: palette.light.panelRaised,
      color: palette.light.text,
      border: `1px solid ${palette.light.border}`,
      boxShadow: palette.light.shadow,
    },
  },
});

export const tooltipTone = styleVariants({
  dark: {},
  light: {},
});

export const shellSurface = style({
  position: "relative",
  display: "grid",
  gridTemplateRows: "auto minmax(0, 1fr)",
  minWidth: 0,
  minHeight: "100vh",
});

export const topBar = style({
  position: "sticky",
  top: 0,
  zIndex: 2,
  display: "grid",
  gridTemplateColumns: "auto minmax(140px, 1fr) auto",
  alignItems: "center",
  gap: vars.space[3],
  padding: `${vars.space[3]} ${vars.space[5]}`,
  borderBottom: `1px solid ${palette.dark.border}`,
  background: palette.dark.topBar,
  backdropFilter: "blur(20px)",
  minHeight: "84px",
  boxShadow: "inset 0 -1px 0 rgba(255,255,255,0.02)",
  selectors: {
    [`${shellTone.light} &`]: {
      borderBottom: `1px solid ${palette.light.border}`,
      background: palette.light.topBar,
      boxShadow:
        "inset 0 -1px 0 rgba(255,255,255,0.55), 0 10px 30px rgba(132, 150, 176, 0.08)",
    },
  },
  "@media": {
    "screen and (max-width: 1260px)": {
      gridTemplateColumns: "auto auto",
      rowGap: vars.space[3],
    },
    "screen and (max-width: 1040px)": {
      gridTemplateColumns: "1fr",
      padding: `${vars.space[4]} ${vars.space[5]}`,
    },
    "screen and (max-width: 820px)": {
      padding: `${vars.space[4]} ${vars.space[4]}`,
    },
  },
});

export const topBarLeftCluster = style({
  display: "flex",
  alignItems: "center",
  gap: vars.space[3],
  minWidth: 0,
  "@media": {
    "screen and (max-width: 680px)": {
      flexWrap: "wrap",
    },
  },
});

export const topBarBrandBlock = style({
  display: "flex",
  alignItems: "center",
  flex: "0 0 auto",
  minWidth: 0,
  minHeight: "44px",
});

export const topBarBrandTitle = style({
  fontSize: "clamp(1.74rem, 2.1vw, 2.38rem)",
  lineHeight: 1,
  letterSpacing: "-0.05em",
  fontWeight: vars.font.weight.bold,
  margin: 0,
});

export const topBarMetaLabel = style({
  fontSize: "0.68rem",
  lineHeight: 1,
  letterSpacing: "0.14em",
  textTransform: "uppercase",
  color: palette.dark.textDim,
  whiteSpace: "nowrap",
  selectors: {
    [`${shellTone.light} &`]: {
      color: palette.light.textDim,
    },
  },
});

export const topBarCluster = style({
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: vars.space[3],
  minWidth: 0,
  "@media": {
    "screen and (max-width: 1260px)": {
      justifyContent: "flex-start",
      gridColumn: "1 / -1",
    },
    "screen and (max-width: 1040px)": {
      justifyContent: "flex-start",
    },
  },
});

export const topBarStatusBlock = style({
  display: "grid",
  alignItems: "center",
  alignContent: "center",
  gap: vars.space[1],
  minHeight: "40px",
  minWidth: 0,
  selectors: {
    "&:empty": {
      display: "none",
    },
  },
});

export const topBarActionCluster = style({
  display: "flex",
  alignItems: "center",
  justifyContent: "flex-end",
  gap: vars.space[2],
  flexWrap: "nowrap",
  minHeight: "44px",
  paddingLeft: vars.space[3],
  borderLeft: `1px solid ${palette.dark.border}`,
  selectors: {
    [`${shellTone.light} &`]: {
      borderLeft: `1px solid ${palette.light.border}`,
    },
  },
  "@media": {
    "screen and (max-width: 1260px)": {
      gridColumn: "1 / -1",
      justifyContent: "space-between",
      paddingLeft: 0,
      borderLeft: "none",
      paddingTop: vars.space[2],
      borderTop: `1px solid ${palette.dark.border}`,
    },
    "screen and (max-width: 1040px)": {
      justifyContent: "flex-start",
    },
    "screen and (max-width: 980px)": {
      flexWrap: "wrap",
      justifyContent: "flex-start",
    },
  },
});

export const topBarStatusZone = style({
  display: "flex",
  alignItems: "center",
  flexWrap: "nowrap",
  overflow: "hidden",
  gap: vars.space[3],
  minWidth: 0,
  "@media": {
    "screen and (max-width: 860px)": {
      flexWrap: "wrap",
    },
  },
});

export const topBarExchangeCapsule = style({
  display: "inline-flex",
  alignItems: "center",
  gap: vars.space[2],
  padding: `0 ${vars.space[2]}`,
  minHeight: "26px",
  borderRadius: "7px",
  border: `1px solid ${palette.dark.borderStrong}`,
  background: "rgba(255, 255, 255, 0.015)",
  color: palette.dark.text,
  minWidth: 0,
  selectors: {
    "&[data-exchange-state='connected']": {
      borderColor: "rgba(74, 222, 164, 0.58)",
    },
    "&[data-exchange-state='offline']": {
      borderColor: "rgba(255, 105, 95, 0.52)",
    },
    [`${shellTone.light} &`]: {
      background: "rgba(255, 255, 255, 0.7)",
      color: palette.light.text,
      border: `1px solid ${palette.light.borderStrong}`,
    },
    [`${shellTone.light} &[data-exchange-state='connected']`]: {
      borderColor: "rgba(15, 139, 95, 0.5)",
    },
    [`${shellTone.light} &[data-exchange-state='offline']`]: {
      borderColor: "rgba(216, 61, 61, 0.46)",
    },
  },
});

export const topBarExchangeName = style({
  fontSize: "0.8rem",
  fontWeight: vars.font.weight.semibold,
  lineHeight: 1.1,
  color: palette.dark.textSoft,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  selectors: {
    [`${shellTone.light} &`]: {
      color: palette.light.textSoft,
    },
  },
});

export const topBarExchangePing = style({
  fontSize: "0.74rem",
  fontWeight: vars.font.weight.semibold,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  lineHeight: 1,
  fontVariantNumeric: "tabular-nums",
  minWidth: "5.6ch",
  textAlign: "right",
  whiteSpace: "nowrap",
  selectors: {
    "&[data-ping-tone='good']": {
      color: palette.dark.success,
    },
    "&[data-ping-tone='warn']": {
      color: "#ffca76",
    },
    "&[data-ping-tone='bad']": {
      color: palette.dark.danger,
    },
    [`${shellTone.light} &[data-ping-tone='good']`]: {
      color: palette.light.success,
    },
    [`${shellTone.light} &[data-ping-tone='warn']`]: {
      color: "#a86a14",
    },
    [`${shellTone.light} &[data-ping-tone='bad']`]: {
      color: palette.light.danger,
    },
  },
});

export const topBarStatusValue = style({
  display: "inline-flex",
  alignItems: "center",
  minHeight: "24px",
  gap: vars.space[2],
  fontSize: "0.94rem",
  fontWeight: vars.font.weight.semibold,
  whiteSpace: "nowrap",
  color: palette.dark.text,
  selectors: {
    [`${shellTone.light} &`]: {
      color: palette.light.text,
    },
  },
});

export const topBarSignalDot = style({
  width: "0.42rem",
  height: "0.42rem",
  borderRadius: vars.radius.pill,
  background: palette.dark.success,
  boxShadow: "0 0 0 3px rgba(74, 222, 164, 0.08)",
  selectors: {
    [`${shellTone.light} &`]: {
      background: palette.light.success,
      boxShadow: "0 0 0 3px rgba(15, 139, 95, 0.06)",
    },
  },
});

export const topBarTimeBlock = style({
  display: "grid",
  gap: vars.space[1],
  minWidth: "9rem",
});

export const topBarTimeLabel = style({
  fontSize: vars.font.size[1],
  color: palette.dark.textDim,
  textTransform: "uppercase",
  letterSpacing: "0.12em",
  selectors: {
    [`${shellTone.light} &`]: {
      color: palette.light.textDim,
    },
  },
});

export const topBarTimeValue = style({
  fontSize: "0.92rem",
  fontWeight: vars.font.weight.semibold,
  fontVariantNumeric: "tabular-nums",
  whiteSpace: "nowrap",
  color: palette.dark.textSoft,
  selectors: {
    [`${shellTone.light} &`]: {
      color: palette.light.textSoft,
    },
  },
});

export const topBarThemeSwitch = style({
  width: "2.3rem",
  height: "2.3rem",
  display: "grid",
  placeItems: "center",
  padding: 0,
  borderRadius: "8px",
  border: `1px solid ${palette.dark.border}`,
  background: "rgba(255,255,255,0.02)",
  color: palette.dark.textSoft,
  cursor: "pointer",
  transition:
    "transform 160ms ease, border-color 160ms ease, background 160ms ease, color 160ms ease",
  selectors: {
    "&:hover": {
      transform: "translateY(-1px)",
      borderColor: "rgba(108, 214, 255, 0.22)",
      background: "rgba(108, 214, 255, 0.06)",
      color: palette.dark.text,
    },
    [`${shellTone.light} &`]: {
      border: `1px solid ${palette.light.border}`,
      background: palette.light.panelRaised,
      color: palette.light.textSoft,
    },
    [`${shellTone.light} &:hover`]: {
      borderColor: "rgba(10, 121, 221, 0.22)",
      background: "rgba(10, 121, 221, 0.08)",
      color: palette.light.text,
    },
  },
});

export const topBarEmergency = style({
  border: `1px solid rgba(255, 105, 95, 0.22)`,
  borderRadius: "8px",
  background: "rgba(255, 105, 95, 0.08)",
  color: "#ffd7d5",
  minHeight: "2.5rem",
  padding: `0 ${vars.space[2]}`,
  fontSize: "0.78rem",
  fontWeight: vars.font.weight.bold,
  letterSpacing: "0.14em",
  cursor: "pointer",
  transition:
    "transform 160ms ease, border-color 160ms ease, background 160ms ease, color 160ms ease",
  selectors: {
    "&:hover": {
      transform: "translateY(-1px)",
      borderColor: "rgba(255, 105, 95, 0.34)",
      background: "rgba(255, 105, 95, 0.12)",
    },
    [`${shellTone.light} &`]: {
      color: palette.light.danger,
      background: palette.light.errorSoft,
      borderColor: "rgba(212, 81, 69, 0.22)",
    },
  },
});

export const mainFrame = style({
  minWidth: 0,
  minHeight: 0,
});

export const dialogOverlay = style({
  position: "fixed",
  inset: 0,
  background: palette.dark.overlay,
  zIndex: 5,
});

export const dialogOverlayTone = styleVariants({
  dark: {},
  light: {
    background: palette.light.overlay,
  },
});

export const dialogTone = styleVariants({
  dark: {},
  light: {},
});

export const dialogA11yHidden = style({
  position: "absolute",
  width: "1px",
  height: "1px",
  padding: 0,
  margin: "-1px",
  overflow: "hidden",
  clip: "rect(0, 0, 0, 0)",
  whiteSpace: "nowrap",
  border: 0,
});

export const dialogContent = style({
  position: "fixed",
  top: 0,
  left: 0,
  bottom: 0,
  zIndex: 6,
  width: "min(420px, calc(100vw - 32px))",
  display: "block",
  padding: `${vars.space[5]} ${vars.space[4]}`,
  borderRight: `1px solid ${palette.dark.borderStrong}`,
  background: palette.dark.drawer,
  boxShadow: palette.dark.shadow,
  outline: "none",
  overflow: "hidden",
});

export const dialogContentTone = styleVariants({
  dark: {},
  light: {
    borderRight: `1px solid ${palette.light.border}`,
    background: palette.light.drawer,
    boxShadow: palette.light.shadow,
  },
});

export const dialogListViewport = style({
  height: "100%",
  overflowY: "auto",
  overflowX: "hidden",
  paddingRight: vars.space[1],
});

export const navDrawerList = style({
  display: "grid",
  gap: vars.space[2],
  alignContent: "start",
  paddingBottom: vars.space[6],
});

export const navDrawerItem = style({
  display: "grid",
  gridTemplateColumns: "52px minmax(0, 1fr)",
  alignItems: "center",
  gap: vars.space[3],
  border: `1px solid transparent`,
  borderRadius: vars.radius.card,
  background: "transparent",
  color: palette.dark.text,
  padding: `${vars.space[3]} ${vars.space[3]}`,
  textAlign: "left",
  cursor: "pointer",
  transition:
    "transform 160ms ease, background 160ms ease, border-color 160ms ease",
  selectors: {
    "&:hover": {
      transform: "translateX(2px)",
      background: palette.dark.accentSoft,
      borderColor: palette.dark.borderStrong,
    },
    [`${dialogTone.light} &`]: {
      color: palette.light.text,
      background: "rgba(255,255,255,0.24)",
    },
    [`${dialogTone.light} &:hover`]: {
      background: "rgba(23, 109, 196, 0.06)",
      borderColor: palette.light.border,
    },
  },
});

export const navDrawerItemActive = style({
  background:
    "linear-gradient(135deg, rgba(108, 214, 255, 0.18), rgba(141, 187, 255, 0.14))",
  borderColor: palette.dark.accentStrong,
  selectors: {
    [`${dialogTone.light} &`]: {
      background:
        "linear-gradient(135deg, rgba(23, 109, 196, 0.10), rgba(23, 109, 196, 0.04))",
      borderColor: "rgba(23, 109, 196, 0.16)",
    },
  },
});

export const navDrawerItemIcon = style({
  width: "3.25rem",
  height: "3.25rem",
  display: "grid",
  placeItems: "center",
  borderRadius: vars.radius.card,
  background: "rgba(255, 255, 255, 0.04)",
  color: palette.dark.accentStrong,
  selectors: {
    [`${dialogTone.light} &`]: {
      background: "rgba(23, 109, 196, 0.06)",
      color: palette.light.accentStrong,
    },
  },
});

export const navDrawerItemText = style({
  display: "grid",
  gap: vars.space[1],
  fontSize: vars.font.size[4],
  fontWeight: vars.font.weight.semibold,
});

export const navDrawerItemMeta = style({
  fontSize: vars.font.size[2],
  fontWeight: vars.font.weight.regular,
  color: palette.dark.textDim,
  selectors: {
    [`${dialogTone.light} &`]: {
      color: palette.light.textDim,
    },
  },
});
