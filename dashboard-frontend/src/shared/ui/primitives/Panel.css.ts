import { style } from "@vanilla-extract/css";

import { vars } from "../../styles/theme.css";

export const panel = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[4],
  padding: vars.space[5],
  borderRadius: vars.radius.card,
  background: vars.color.surface,
  border: `1px solid ${vars.color.border}`,
  boxShadow: vars.shadow.card,
  minWidth: 0,
});

export const panelHeader = style({
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: vars.space[3],
});

export const panelTitle = style({
  margin: 0,
  fontSize: vars.font.size[5],
  lineHeight: 1.2,
});

export const panelCaption = style({
  margin: 0,
  color: vars.color.textMuted,
  fontSize: vars.font.size[2],
});
