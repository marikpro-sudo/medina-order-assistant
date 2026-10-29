export type Hold = {
  at: string;
  offset: number;
  seconds: number;
};

export type SubtitleSpec = {
  at: string;
  offset: number;
  seconds: number;
  text: string;
};

export type TitleCardData = {
  kind: "title";
  seconds: number;
  title: string;
  subtitle: string;
  footer: string;
};

export type BulletsCardData = {
  kind: "bullets";
  seconds: number;
  title: string;
  bullets: string[];
};

export type Metric = {
  value: string;
  label: string;
  note: string;
};

export type MetricsCardData = {
  kind: "metrics";
  seconds: number;
  title: string;
  metrics: Metric[];
};

export type Card = TitleCardData | BulletsCardData | MetricsCardData;

export type Scene = {
  scene: string;
  label: string;
  holds: Hold[];
  subtitles: SubtitleSpec[];
};

export type Content = {
  lang: string;
  speedNote: string;
  intro: Card[];
  scenes: Scene[];
  outro: Card[];
};

export type TimelineEvent = {
  key: string;
  t: number;
};

export type TimelineEntry = {
  file: string;
  duration: number;
  events: TimelineEvent[];
};

export type Timeline = Record<string, TimelineEntry>;
