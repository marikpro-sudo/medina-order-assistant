import React from "react";
import {Composition} from "remotion";
import {totalFrames} from "./timeline";
import type {Content, Timeline} from "./types";
import {Video} from "./Video";
import ruJson from "../content/ru.json";
import timelineRu from "../public/recordings/timeline.json";
import timelineEn from "../public/recordings/en/timeline.json";
import enJson from "../content/en.json";

export const CONTENT: Record<string, Content> = {
  ru: ruJson as unknown as Content,
  en: enJson as unknown as Content,
};

// Each language has its own recordings; non-Russian ones live in public/recordings/<lang>/.
const inDir = (t: Timeline, dir: string): Timeline =>
  Object.fromEntries(Object.entries(t).map(([k, v]) => [k, {...v, file: `${dir}/${v.file}`}])) as Timeline;

export const TIMELINES: Record<string, Timeline> = {
  ru: timelineRu as unknown as Timeline,
  en: inDir(timelineEn as unknown as Timeline, "en"),
};

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
            durationInFrames: totalFrames(content, TIMELINES[props.lang] ?? TIMELINES.ru, FPS),
          };
        }}
      />
    </>
  );
};
