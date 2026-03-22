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

export const stateMeta = style({
  display: "flex",
  flexWrap: "wrap",
  gap: vars.space[2],
  alignItems: "center",
});

export const stateCaption = style({
  margin: 0,
  color: vars.color.textPrimary,
  fontSize: vars.font.size[3],
  lineHeight: 1.5,
  maxWidth: "64ch",
});

export const stateText = style({
  margin: 0,
  color: vars.color.textMuted,
  lineHeight: 1.6,
});

export const stateHintList = style({
  margin: 0,
  paddingLeft: vars.space[4],
  color: vars.color.textMuted,
  display: "flex",
  flexDirection: "column",
  gap: vars.space[1],
  lineHeight: 1.5,
});
