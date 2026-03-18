import { style } from "@vanilla-extract/css";

import { vars } from "../../shared/styles/theme.css";

export const shellLayout = style({
  display: "grid",
  gridTemplateColumns: "284px minmax(0, 1fr)",
  minHeight: "100vh",
  background: vars.color.canvas,
  "@media": {
    "screen and (max-width: 920px)": {
      gridTemplateColumns: "1fr",
    },
  },
});

export const sideRail = style({
  borderRight: `1px solid ${vars.color.borderStrong}`,
  background: vars.color.surfaceSidebar,
  position: "sticky",
  top: 0,
  height: "100vh",
  "@media": {
    "screen and (max-width: 920px)": {
      position: "static",
      height: "auto",
      borderRight: "none",
      borderBottom: `1px solid ${vars.color.borderStrong}`,
    },
  },
});

export const contentArea = style({
  display: "grid",
  gridTemplateRows: "72px minmax(0, 1fr)",
  minWidth: 0,
});

export const contentViewport = style({
  padding: vars.space[6],
  display: "flex",
  flexDirection: "column",
  gap: vars.space[6],
  minWidth: 0,
  "@media": {
    "screen and (max-width: 720px)": {
      padding: vars.space[4],
    },
  },
});
