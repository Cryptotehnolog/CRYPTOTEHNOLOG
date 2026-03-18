import { style } from "@vanilla-extract/css";

import { vars } from "../../styles/theme.css";

export const keyValueList = style({
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
  gap: vars.space[4],
});

export const keyValueItem = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[1],
  padding: vars.space[3],
  borderRadius: vars.radius.panel,
  background: vars.color.surfaceInteractive,
  border: `1px solid ${vars.color.border}`,
});

export const keyLabel = style({
  color: vars.color.textMuted,
  fontSize: vars.font.size[1],
  textTransform: "uppercase",
  letterSpacing: "0.06em",
});

export const keyValue = style({
  fontSize: vars.font.size[5],
  fontWeight: vars.font.weight.semibold,
  lineHeight: 1.1,
});
