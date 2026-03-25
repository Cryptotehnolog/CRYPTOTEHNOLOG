import { style } from "@vanilla-extract/css";

import { vars } from "../../../shared/styles/theme.css";

export const pageStack = style({
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
