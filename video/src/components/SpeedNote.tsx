import React from "react";
import {AbsoluteFill} from "remotion";
import {FONT} from "./TitleCard";

export const SpeedNote: React.FC<{text: string}> = ({text}) => {
  return (
    <AbsoluteFill style={{justifyContent: "flex-end", alignItems: "flex-end"}}>
      <div
        style={{
          marginRight: 32,
          marginBottom: 32,
          backgroundColor: "rgba(0,0,0,0.45)",
          borderRadius: 999,
          padding: "6px 16px",
          fontFamily: FONT,
          color: "rgba(255,255,255,0.85)",
          fontSize: 22,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
