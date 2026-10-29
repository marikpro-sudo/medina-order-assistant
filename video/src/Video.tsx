import React from "react";
import {AbsoluteFill, Series, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {CONTENT, TIMELINE} from "./Root";
import {sceneLayout} from "./timeline";
import type {Card, Content} from "./types";
import type {VideoProps} from "./Root";
import {BulletsCard} from "./components/BulletsCard";
import {MetricsCard} from "./components/MetricsCard";
import {SceneClip} from "./components/SceneClip";
import {TitleCard} from "./components/TitleCard";

const CROSSFADE_FRAMES = 12;

const CardTransition: React.FC<{durationInFrames: number; children: React.ReactNode}> = ({
  durationInFrames,
  children,
}) => {
  const frame = useCurrentFrame();
  const fadeIn = interpolate(frame, [0, CROSSFADE_FRAMES], [0, 1], {extrapolateRight: "clamp"});
  const fadeOut = interpolate(frame, [durationInFrames - CROSSFADE_FRAMES, durationInFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return <AbsoluteFill style={{opacity: Math.min(fadeIn, fadeOut)}}>{children}</AbsoluteFill>;
};

const renderCard = (card: Card): React.ReactNode => {
  if (card.kind === "title") {
    return <TitleCard title={card.title} subtitle={card.subtitle} footer={card.footer} />;
  }
  if (card.kind === "bullets") {
    return <BulletsCard title={card.title} bullets={card.bullets} />;
  }
  return <MetricsCard title={card.title} metrics={card.metrics} />;
};

export const Video: React.FC<VideoProps> = ({lang}) => {
  const {fps} = useVideoConfig();
  const content: Content = CONTENT[lang] ?? CONTENT.ru;
  return (
    <AbsoluteFill style={{backgroundColor: "#0B1F1A"}}>
      <Series>
        {content.intro.map((card, i) => {
          const duration = Math.round(card.seconds * fps);
          return (
            <Series.Sequence key={`intro-${i}`} durationInFrames={duration} name={`intro-${i}`}>
              <CardTransition durationInFrames={duration}>{renderCard(card)}</CardTransition>
            </Series.Sequence>
          );
        })}
        {content.scenes.map((scene) => {
          const entry = TIMELINE[scene.scene];
          if (!entry) {
            throw new Error(`[video] no timeline entry for scene "${scene.scene}"`);
          }
          const layout = sceneLayout(scene, entry, fps);
          return (
            <Series.Sequence key={scene.scene} durationInFrames={layout.totalFrames} name={scene.scene}>
              <SceneClip scene={scene} entry={entry} speedNote={content.speedNote} />
            </Series.Sequence>
          );
        })}
        {content.outro.map((card, i) => {
          const duration = Math.round(card.seconds * fps);
          return (
            <Series.Sequence key={`outro-${i}`} durationInFrames={duration} name={`outro-${i}`}>
              <CardTransition durationInFrames={duration}>{renderCard(card)}</CardTransition>
            </Series.Sequence>
          );
        })}
      </Series>
    </AbsoluteFill>
  );
};
