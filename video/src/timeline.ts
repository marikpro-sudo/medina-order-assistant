import type {Content, Scene, Timeline, TimelineEntry} from "./types";

export type PlaySegment = {
  kind: "play";
  srcStartMs: number;
  srcEndMs: number;
  srcStartFrame: number;
  outStartMs: number;
  outEndMs: number;
  outStartFrame: number;
  lengthFrames: number;
};

export type FreezeSegment = {
  kind: "freeze";
  srcMs: number;
  srcFrame: number;
  holdSeconds: number;
  outStartMs: number;
  outEndMs: number;
  outStartFrame: number;
  lengthFrames: number;
};

export type Segment = PlaySegment | FreezeSegment;

export type Subtitle = {
  text: string;
  startMs: number;
  endMs: number;
  startFrame: number;
  endFrame: number;
};

export type SceneLayout = {
  totalFrames: number;
  totalMs: number;
  segments: Segment[];
  subtitles: Subtitle[];
};

const msToFrames = (ms: number, fps: number): number =>
  Math.round((ms / 1000) * fps);

const eventTime = (
  entry: TimelineEntry,
  sceneName: string,
  key: string,
): number | null => {
  const ev = entry.events.find((e) => e.key === key);
  if (!ev) {
    console.warn(`[timeline] scene "${sceneName}": missing event "${key}", skipping`);
    return null;
  }
  return ev.t;
};

export const sceneLayout = (
  scene: Scene,
  timelineEntry: TimelineEntry,
  fps: number,
): SceneLayout => {
  const duration = timelineEntry.duration;

  // Resolve holds to source freeze points T = event(at).t + offset.
  // Same-T holds are summed; holds at/after the recording end are ignored.
  const holdByT = new Map<number, number>();
  for (const h of scene.holds) {
    const t = eventTime(timelineEntry, scene.scene, h.at);
    if (t === null) {
      continue;
    }
    const T = t + h.offset;
    if (T >= duration) {
      continue;
    }
    const clamped = Math.max(0, T);
    holdByT.set(clamped, (holdByT.get(clamped) ?? 0) + h.seconds);
  }
  const points = [...holdByT.entries()].sort((a, b) => a[0] - b[0]);

  // Output time of a source time t: holds with T < t already elapsed.
  // A hold exactly at T counts for t > T, so a subtitle anchored at T
  // appears when the freeze starts.
  const out = (t: number): number => {
    let bonus = 0;
    for (const [T, secs] of points) {
      if (T < t) {
        bonus += secs * 1000;
      }
    }
    return t + bonus;
  };

  // Segments in source-time order: play [prev, T] then freeze at T.
  const raw: Array<
    | {kind: "play"; srcStartMs: number; srcEndMs: number; outStartMs: number; outEndMs: number}
    | {kind: "freeze"; srcMs: number; holdSeconds: number; outStartMs: number; outEndMs: number}
  > = [];
  let prev = 0;
  let cursor = 0;
  for (const [T, secs] of points) {
    if (T > prev) {
      raw.push({kind: "play", srcStartMs: prev, srcEndMs: T, outStartMs: cursor, outEndMs: cursor + (T - prev)});
    }
    cursor += T - prev;
    raw.push({kind: "freeze", srcMs: T, holdSeconds: secs, outStartMs: cursor, outEndMs: cursor + secs * 1000});
    cursor += secs * 1000;
    prev = T;
  }
  if (duration > prev) {
    raw.push({kind: "play", srcStartMs: prev, srcEndMs: duration, outStartMs: cursor, outEndMs: cursor + (duration - prev)});
  }
  cursor += duration - prev;

  const totalMs = cursor;
  const totalFrames = Math.ceil((totalMs / 1000) * fps);

  const segments: Segment[] = [];
  for (const r of raw) {
    const outStartFrame = msToFrames(r.outStartMs, fps);
    const lengthFrames = msToFrames(r.outEndMs, fps) - outStartFrame;
    if (lengthFrames <= 0) {
      continue;
    }
    if (r.kind === "play") {
      segments.push({
        kind: "play",
        srcStartMs: r.srcStartMs,
        srcEndMs: r.srcEndMs,
        srcStartFrame: msToFrames(r.srcStartMs, fps),
        outStartMs: r.outStartMs,
        outEndMs: r.outEndMs,
        outStartFrame,
        lengthFrames,
      });
    } else {
      segments.push({
        kind: "freeze",
        srcMs: r.srcMs,
        srcFrame: msToFrames(r.srcMs, fps),
        holdSeconds: r.holdSeconds,
        outStartMs: r.outStartMs,
        outEndMs: r.outEndMs,
        outStartFrame,
        lengthFrames,
      });
    }
  }
  // Absorb ms->frame rounding drift in the last segment so the
  // segments always add up to exactly totalFrames.
  const drift = totalFrames - segments.reduce((sum, s) => sum + s.lengthFrames, 0);
  if (segments.length > 0) {
    segments[segments.length - 1].lengthFrames += drift;
  }

  // Subtitles sorted by start; each runs until its duration ends or the
  // next subtitle starts (never overlapping), clamped to the scene end.
  const starts: Array<{text: string; startMs: number; durMs: number}> = [];
  for (const s of scene.subtitles) {
    const t = eventTime(timelineEntry, scene.scene, s.at);
    if (t === null) {
      continue;
    }
    starts.push({text: s.text, startMs: out(t + s.offset), durMs: s.seconds * 1000});
  }
  starts.sort((a, b) => a.startMs - b.startMs);

  const subtitles: Subtitle[] = [];
  for (let i = 0; i < starts.length; i++) {
    const r = starts[i];
    const nextStart = i + 1 < starts.length ? starts[i + 1].startMs : Number.POSITIVE_INFINITY;
    const endMs = Math.min(r.startMs + r.durMs, nextStart, totalMs);
    const startFrame = msToFrames(r.startMs, fps);
    const endFrame = Math.min(msToFrames(endMs, fps), totalFrames);
    if (endFrame > startFrame && r.startMs < totalMs) {
      subtitles.push({text: r.text, startMs: r.startMs, endMs, startFrame, endFrame});
    }
  }

  return {totalFrames, totalMs, segments, subtitles};
};

export const totalFrames = (
  content: Content,
  timeline: Timeline,
  fps: number,
): number => {
  let total = 0;
  for (const card of [...content.intro, ...content.outro]) {
    total += Math.round(card.seconds * fps);
  }
  for (const scene of content.scenes) {
    const entry = timeline[scene.scene];
    if (!entry) {
      throw new Error(`[timeline] no timeline entry for scene "${scene.scene}"`);
    }
    total += sceneLayout(scene, entry, fps).totalFrames;
  }
  return total;
};
