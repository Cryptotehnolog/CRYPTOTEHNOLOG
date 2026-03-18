import { style } from "@vanilla-extract/css";

import { vars } from "../../styles/theme.css";

export const stateCard = style({
  display: "flex",
  flexDirection: "column",
  gap: vars.space[3],
  padding: vars.space[5],
  borderRadius: vars.radius.card,
  background: vars.color.surface,
  border: `1px dashed ${vars.color.borderStrong}`,
});

export const stateTitle = style({
  margin: 0,
  fontSize: vars.font.size[5],
});

export const stateText = style({
  margin: 0,
  color: vars.color.textMuted,
});
