import React from "react";
import {AbsoluteFill, Freeze, OffthreadVideo, Sequence, staticFile, useVideoConfig} from "remotion";
import {sceneLayout} from "../timeline";
import type {Scene, TimelineEntry} from "../types";
import {SceneLabel} from "./SceneLabel";
import {SpeedNote} from "./SpeedNote";
import {SubtitleBar} from "./SubtitleBar";

const FILL: React.CSSProperties = {width: "100%", height: "100%", objectFit: "cover"};

export const SceneClip: React.FC<{scene: Scene; entry: TimelineEntry; speedNote: string}> = ({
  scene,
  entry,
  speedNote,
}) => {
  const {fps} = useVideoConfig();
  const layout = sceneLayout(scene, entry, fps);
  const src = staticFile(`recordings/${entry.file}`);
  return (
    <AbsoluteFill style={{backgroundColor: "#000"}}>
      {layout.segments.map((seg, i) =>
        seg.kind === "play" ? (
          <Sequence key={i} from={seg.outStartFrame} durationInFrames={seg.lengthFrames}>
            <AbsoluteFill>
              <OffthreadVideo muted src={src} startFrom={seg.srcStartFrame} style={FILL} />
            </AbsoluteFill>
          </Sequence>
        ) : (
          <Sequence key={i} from={seg.outStartFrame} durationInFrames={seg.lengthFrames}>
            <AbsoluteFill>
              <Freeze frame={0}>
                <OffthreadVideo muted src={src} startFrom={seg.srcFrame} style={FILL} />
              </Freeze>
            </AbsoluteFill>
          </Sequence>
        ),
      )}
      {layout.subtitles.map((sub, i) => (
        <Sequence
          key={`sub-${i}`}
          from={sub.startFrame}
          durationInFrames={sub.endFrame - sub.startFrame}
        >
          <SubtitleBar text={sub.text} durationInFrames={sub.endFrame - sub.startFrame} />
        </Sequence>
      ))}
      <SceneLabel label={scene.label} />
      <SpeedNote text={speedNote} />
    </AbsoluteFill>
  );
};
