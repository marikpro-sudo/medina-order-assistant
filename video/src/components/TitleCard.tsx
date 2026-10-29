import React from "react";
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";

export const FONT = 'Inter, "Segoe UI", Roboto, Arial, sans-serif';

export const TitleCard: React.FC<{title: string; subtitle: string; footer: string}> = ({
  title,
  subtitle,
  footer,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const scale = interpolate(spring({frame, fps}), [0, 1], [0.96, 1]);
  const opacity = interpolate(frame, [0, 15], [0, 1], {extrapolateRight: "clamp"});
  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(135deg, #0B1F1A 0%, #0E3B31 100%)",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: FONT,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
          padding: "0 120px",
          transform: `scale(${scale})`,
          opacity,
        }}
      >
        <div style={{fontSize: 120, fontWeight: 800, color: "#F4FBF8"}}>{title}</div>
        <div style={{fontSize: 44, color: "#F4FBF8", marginTop: 24, opacity: 0.92}}>{subtitle}</div>
        <div style={{fontSize: 28, color: "rgba(244,251,248,0.6)", marginTop: 48}}>{footer}</div>
      </div>
    </AbsoluteFill>
  );
};
