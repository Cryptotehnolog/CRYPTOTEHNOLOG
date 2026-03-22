import { style, styleVariants } from "@vanilla-extract/css";

import { vars } from "../../shared/styles/theme.css";

export const sideFrame = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[5],
  padding: vars.space[5],
});

export const brandBlock = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[1],
  paddingBottom: vars.space[4],
  borderBottom: `1px solid ${vars.color.border}`,
});

export const brandCaption = style({
  fontSize: vars.font.size[1],
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: vars.color.textMuted,
});

export const brandTitle = style({
  fontSize: vars.font.size[5],
  color: vars.color.textPrimary,
  fontWeight: vars.font.weight.semibold,
});

export const navSection = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[4],
});

export const navSectionHeader = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[1],
  marginBottom: vars.space[2],
});

export const groupTitle = style({
  fontSize: vars.font.size[2],
  fontWeight: vars.font.weight.semibold,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  color: vars.color.textMuted,
});

export const groupCaption = style({
  fontSize: vars.font.size[1],
  color: vars.color.textMuted,
  lineHeight: 1.4,
});

export const groupList = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[2],
  listStyle: "none",
  margin: 0,
  padding: 0,
});

export const navItem = style({
  minWidth: 0,
});

const navLinkBase = style({
  display: "flex",
  justifyContent: "space-between",
  gap: vars.space[3],
  padding: vars.space[3],
  borderRadius: vars.radius.panel,
  textDecoration: "none",
  border: `1px solid ${vars.color.border}`,
  color: vars.color.textPrimary,
  background: vars.color.surface,
  transition: "border-color 120ms ease, background 120ms ease, box-shadow 120ms ease",
});

export const navDescription = style({
  display: "block",
  marginTop: vars.space[1],
  color: vars.color.textMuted,
  lineHeight: 1.35,
});

export const navLink = styleVariants({
  active: [
    navLinkBase,
    {
      background: vars.color.surfaceInteractive,
      borderColor: vars.color.borderStrong,
      boxShadow: vars.shadow.focus,
    },
  ],
  inactive: [navLinkBase],
});

export const itemBadge = style({
  display: "flex",
  alignItems: "flex-start",
  flexShrink: 0,
});
