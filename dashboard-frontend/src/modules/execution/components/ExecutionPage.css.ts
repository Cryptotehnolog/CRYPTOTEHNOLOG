import { style } from "@vanilla-extract/css";

import { vars } from "../../../shared/styles/theme.css";

export const pageStack = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[5],
});

export const topBanner = style({
  display: "flex",
  flexWrap: "wrap",
  gap: vars.space[3],
  alignItems: "center",
});

export const sectionGrid = style({
  display: "grid",
  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
  gap: vars.space[4],
  "@media": {
    "screen and (max-width: 980px)": {
      gridTemplateColumns: "1fr",
    },
  },
});

export const availabilityList = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[3],
});

export const availabilityItem = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[2],
  padding: vars.space[3],
  borderRadius: vars.radius.panel,
  border: `1px solid ${vars.color.border}`,
  background: vars.color.surfaceInteractive,
});

export const availabilityHeader = style({
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: vars.space[3],
});

export const availabilityMeta = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[1],
});

export const availabilityLabel = style({
  color: vars.color.textMuted,
});

export const availabilityNote = style({
  margin: 0,
  color: vars.color.textMuted,
});
