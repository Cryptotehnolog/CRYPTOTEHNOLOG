import { style } from "@vanilla-extract/css";

import { vars } from "../../shared/styles/theme.css";

export const statusBar = style({
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: vars.space[4],
  padding: `${vars.space[4]} ${vars.space[6]}`,
  borderBottom: `1px solid ${vars.color.border}`,
  background: vars.color.surface,
  position: "sticky",
  top: 0,
  zIndex: 10,
  "@media": {
    "screen and (max-width: 720px)": {
      flexDirection: "column",
      alignItems: "flex-start",
      padding: vars.space[4],
    },
  },
});

export const titleCluster = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[1],
  minWidth: 0,
});

export const barMeta = style({
  fontSize: vars.font.size[1],
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: vars.color.textMuted,
});

export const barTitle = style({
  margin: 0,
  fontSize: vars.font.size[6],
  lineHeight: 1.1,
  color: vars.color.textPrimary,
});

export const barSubtitle = style({
  margin: 0,
  color: vars.color.textMuted,
  fontSize: vars.font.size[3],
  lineHeight: 1.5,
  maxWidth: "68ch",
});

export const statusCluster = style({
  display: "flex",
  flexWrap: "wrap",
  gap: vars.space[2],
});
