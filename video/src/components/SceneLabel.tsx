import React from "react";
import {AbsoluteFill} from "remotion";
import {FONT} from "./TitleCard";

export const SceneLabel: React.FC<{label: string}> = ({label}) => {
  return (
    <AbsoluteFill style={{justifyContent: "flex-start", alignItems: "flex-start"}}>
      <div
        style={{
          marginLeft: 32,
          marginTop: 32,
          backgroundColor: "#0E7C66",
          borderRadius: 10,
          padding: "8px 18px",
          fontFamily: FONT,
          color: "#fff",
          fontSize: 28,
        }}
      >
        {label}
      </div>
    </AbsoluteFill>
  );
};
