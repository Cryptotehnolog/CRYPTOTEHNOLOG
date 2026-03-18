import { globalStyle } from "@vanilla-extract/css";

import { vars } from "./theme.css";

globalStyle("html, body, #root", {
  margin: 0,
  minHeight: "100%",
});

globalStyle("body", {
  fontFamily: vars.font.family.base,
  background: vars.color.canvas,
  color: vars.color.textPrimary,
  lineHeight: 1.5,
  textRendering: "optimizeLegibility",
});

globalStyle("*", {
  boxSizing: "border-box",
});

globalStyle("button, input, textarea, select", {
  font: "inherit",
});

globalStyle("a", {
  color: "inherit",
});
