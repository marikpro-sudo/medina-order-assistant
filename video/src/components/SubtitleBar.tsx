import React from "react";
import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {FONT} from "./TitleCard";

export const SubtitleBar: React.FC<{text: string; durationInFrames: number}> = ({
  text,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const opacity = Math.min(
    interpolate(frame, [0, 6], [0, 1], {extrapolateRight: "clamp"}),
    interpolate(frame, [durationInFrames - 6, durationInFrames], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  );
  return (
    <AbsoluteFill style={{justifyContent: "flex-end", alignItems: "center", paddingBottom: 72}}>
      <div
        style={{
          maxWidth: 1500,
          backgroundColor: "rgba(0,0,0,0.72)",
          borderRadius: 14,
          padding: "14px 28px",
          opacity,
          fontFamily: FONT,
        }}
      >
        <div
          style={{
            color: "#fff",
            fontSize: 40,
            lineHeight: 1.3,
            textAlign: "center",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {text}
        </div>
      </div>
    </AbsoluteFill>
  );
};
