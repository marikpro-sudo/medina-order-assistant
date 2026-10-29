import React from "react";
import {AbsoluteFill} from "remotion";
import {FONT} from "./TitleCard";

export const SpeedNote: React.FC<{text: string}> = ({text}) => {
  return (
    // Bottom-left under the subtitles; bottom-right is where the minimized widget sits.
    <AbsoluteFill style={{justifyContent: "flex-end", alignItems: "flex-start"}}>
      <div
        style={{
          marginLeft: 40,
          marginBottom: 12,
          backgroundColor: "rgba(0,0,0,0.45)",
          borderRadius: 999,
          padding: "4px 14px",
          fontFamily: FONT,
          color: "rgba(255,255,255,0.85)",
          fontSize: 19,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
