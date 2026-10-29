import React from "react";
import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import type {Metric} from "../types";
import {FONT} from "./TitleCard";

export const MetricsCard: React.FC<{title: string; metrics: Metric[]}> = ({title, metrics}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0B1F1A",
        fontFamily: FONT,
        alignItems: "center",
        paddingTop: 90,
      }}
    >
      <div style={{fontSize: 56, fontWeight: 700, color: "#F4FBF8", textAlign: "center", padding: "0 100px"}}>
        {title}
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: "36px 48px",
          marginTop: 64,
          width: 1560,
        }}
      >
        {metrics.map((metric, i) => {
          const start = i * 8;
          const opacity = interpolate(frame, [start, start + 10], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const dy = interpolate(frame, [start, start + 10], [20, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          return (
            <div key={i} style={{opacity, transform: `translateY(${dy}px)`}}>
              <div style={{fontSize: 88, fontWeight: 800, color: "#3FD6AE"}}>{metric.value}</div>
              <div style={{fontSize: 30, color: "#F4FBF8", marginTop: 8}}>{metric.label}</div>
              {metric.note ? (
                <div style={{fontSize: 24, color: "rgba(244,251,248,0.6)", marginTop: 6}}>{metric.note}</div>
              ) : null}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
