import React from "react";
import {AbsoluteFill} from "remotion";
import {FONT} from "./TitleCard";

export const SceneLabel: React.FC<{label: string}> = ({label}) => {
  return (
    <AbsoluteFill style={{justifyContent: "flex-start", alignItems: "flex-start"}}>
      <div
        style={{
          // Sits in the empty left part of the demo banner, clear of the portal logo.
          marginLeft: 24,
          marginTop: 4,
          backgroundColor: "#0E7C66",
          borderRadius: 8,
          padding: "3px 14px",
          fontFamily: FONT,
          color: "#fff",
          fontSize: 22,
        }}
      >
        {label}
      </div>
    </AbsoluteFill>
  );
};
