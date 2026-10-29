import React from "react";
import {Composition} from "remotion";
import {totalFrames} from "./timeline";
import type {Content, Timeline} from "./types";
import {Video} from "./Video";
import ruJson from "../content/ru.json";
import timelineJson from "../public/recordings/timeline.json";

export const CONTENT: Record<string, Content> = {
  ru: ruJson as unknown as Content,
};

export const TIMELINE: Timeline = timelineJson as unknown as Timeline;

export const FPS = 30;

export type VideoProps = {
  lang: string;
};

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="MedinaDemo"
        component={Video}
        width={1920}
        height={1080}
        fps={FPS}
        defaultProps={{lang: "ru"}}
        calculateMetadata={({props}) => {
          const content = CONTENT[props.lang] ?? CONTENT.ru;
          return {
            durationInFrames: totalFrames(content, TIMELINE, FPS),
          };
        }}
      />
    </>
  );
};
