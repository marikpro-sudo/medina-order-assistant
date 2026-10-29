import React from "react";
import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {FONT} from "./TitleCard";

export const BulletsCard: React.FC<{title: string; bullets: string[]}> = ({title, bullets}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{backgroundColor: "#0B1F1A", fontFamily: FONT}}>
      <div
        style={{
          position: "absolute",
          left: 140,
          top: 120,
          fontSize: 64,
          fontWeight: 700,
          color: "#F4FBF8",
        }}
      >
        {title}
      </div>
      <div style={{position: "absolute", left: 140, top: 270, maxWidth: 1500}}>
        {bullets.map((bullet, i) => {
          const start = i * 10;
          const opacity = interpolate(frame, [start, start + 10], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const dy = interpolate(frame, [start, start + 10], [20, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          return (
            <div key={i} style={{display: "flex", flexDirection: "row", marginBottom: 28, opacity, transform: `translateY(${dy}px)`}}>
              <div style={{color: "#0E7C66", fontSize: 38, lineHeight: 1.35, marginRight: 20}}>●</div>
              <div style={{color: "#F4FBF8", fontSize: 38, lineHeight: 1.35}}>{bullet}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
