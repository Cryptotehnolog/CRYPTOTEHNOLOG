import { style } from "@vanilla-extract/css";

import { vars } from "../../../shared/styles/theme.css";

export const overviewStack = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[6],
});

export const topBanner = style({
  display: "flex",
  flexWrap: "wrap",
  gap: vars.space[2],
  alignItems: "center",
});

export const sectionGrid = style({
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  gap: vars.space[5],
  "@media": {
    "screen and (max-width: 980px)": {
      gridTemplateColumns: "1fr",
    },
  },
});

export const list = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[2],
});

export const listSection = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[3],
});

export const listHeader = style({
  display: "flex",
  justifyContent: "space-between",
  gap: vars.space[3],
  alignItems: "flex-start",
});

export const listCaption = style({
  color: vars.color.textMuted,
  fontSize: vars.font.size[2],
  maxWidth: "70ch",
});

export const listItem = style({
  display: "flex",
  justifyContent: "space-between",
  gap: vars.space[4],
  padding: vars.space[3],
  borderRadius: vars.radius.panel,
  border: `1px solid ${vars.color.border}`,
  background: vars.color.surfaceInteractive,
});

export const listLabel = style({
  color: vars.color.textMuted,
});

export const listReason = style({
  color: vars.color.textPrimary,
  fontSize: vars.font.size[2],
  marginTop: vars.space[2],
  maxWidth: "60ch",
});

export const listMeta = style({
  color: vars.color.textMuted,
  fontSize: vars.font.size[1],
  marginTop: vars.space[1],
});

export const listValue = style({
  fontFamily: vars.font.family.mono,
  fontWeight: vars.font.weight.semibold,
});
