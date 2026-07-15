import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { TransitionSeries, linearTiming, springTiming } from "@remotion/transitions";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { useAudioData, visualizeAudio } from "@remotion/media-utils";
import { noise2D } from "@remotion/noise";
import { loadFont as loadDisplayFont } from "@remotion/google-fonts/Inter";
import { loadFont as loadMonoFont } from "@remotion/google-fonts/JetBrainsMono";
import React from "react";

const { fontFamily: displayFont } = loadDisplayFont("normal", { weights: ["700", "800", "900"], subsets: ["latin"] });
const { fontFamily: monoFont } = loadMonoFont("normal", { weights: ["400", "500", "700"], subsets: ["latin"] });

export type BreakoutShortProps = {
  brandLabel: string;
  title: string;
  demoCmd: string;
  demoLogs: string[];
  metricLabel: string;
  metricVal: number;
  metricUnit: string;
  words: string[];
  voiceSrc: string;
  bgMusicSrc?: string;
  demoVideoSrc?: string;
  durationInFrames: number;
  fps: number;
};

const COLORS = {
  bg: "#090B0E",
  amber: "#F0B72F",
  text: "#F8FAFC",
  mono: "#CBD5E1",
  green: "#22C55E",
  cardBg: "#141822",
  cardBorder: "#334155",
  termBg: "#11151C",
  termBorder: "#283244",
  dim: "#64748B",
  label: "#94A3B8",
};

const dotStyle = (color: string): React.CSSProperties => ({
  width: 20,
  height: 20,
  borderRadius: "50%",
  backgroundColor: color,
});

const BackgroundDrift: React.FC<{ frame: number }> = ({ frame }) => {
  const nx = noise2D("bg-drift-x", frame * 0.004, 0);
  const ny = noise2D("bg-drift-y", 0, frame * 0.004);
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(circle at ${50 + nx * 10}% ${36 + ny * 8}%, rgba(240,183,47,0.14), rgba(9,11,14,0) 55%)`,
      }}
    />
  );
};

const IntroScene: React.FC<{ brandLabel: string; title: string }> = ({ brandLabel, title }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ fps, frame, config: { damping: 14, mass: 0.6 } });
  const eyebrowOpacity = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" });
  const jitterX = noise2D("intro-jitter", frame * 0.05, 0) * 4;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg, justifyContent: "center", alignItems: "center", padding: "0 70px" }}>
      <div style={{ opacity: eyebrowOpacity, color: COLORS.amber, fontFamily: monoFont, fontSize: 30, fontWeight: 700, letterSpacing: 2, marginBottom: 24 }}>
        {brandLabel}
      </div>
      <div
        style={{
          fontFamily: displayFont,
          fontWeight: 900,
          fontSize: 68,
          textAlign: "center",
          color: COLORS.text,
          lineHeight: 1.15,
          transform: `scale(${pop}) translateX(${jitterX}px)`,
          textShadow: "0 0 40px rgba(240,183,47,0.25)",
        }}
      >
        {title.toUpperCase()}
      </div>
    </AbsoluteFill>
  );
};

const EvidenceScene: React.FC<{
  demoCmd: string;
  demoLogs: string[];
  metricLabel: string;
  metricVal: number;
  metricUnit: string;
  bars: number[];
  middleFrames: number;
  demoVideoSrc?: string;
}> = ({ demoCmd, demoLogs, metricLabel, metricVal, metricUnit, bars, middleFrames, demoVideoSrc }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progressRatio = frame / Math.max(1, middleFrames);

  const cmdCharsShow = Math.floor(demoCmd.length * Math.min(1, progressRatio * 3.5));
  const typedCmd = demoCmd.slice(0, Math.min(cmdCharsShow, 48));
  const cursorOn = Math.floor(frame / 12) % 2 === 0;
  const shownLogCount =
    progressRatio > 0.2
      ? Math.max(1, Math.floor(demoLogs.length * Math.min(1, (progressRatio - 0.2) * 1.5)))
      : 0;

  const metricProgress = spring({
    fps,
    frame,
    config: { damping: 18, mass: 0.9 },
    durationInFrames: Math.max(10, Math.floor(middleFrames * 0.7)),
  });
  const currentVal = metricVal * Math.min(1, metricProgress);
  const barFillPct = Math.min(1, metricProgress) * 100;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg, justifyContent: "center", padding: "0 60px" }}>
      <div style={{ borderRadius: 24, backgroundColor: COLORS.termBg, border: `3px solid ${COLORS.termBorder}`, overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "22px 25px 0" }}>
          <div style={dotStyle("#FF5F56")} />
          <div style={dotStyle("#FFBD2E")} />
          <div style={dotStyle("#27C93F")} />
          <div style={{ marginLeft: 15, color: COLORS.dim, fontSize: 22, fontFamily: monoFont }}>
            EMPIRICAL DEBATE PROOF • LIVE
          </div>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "flex-end", gap: 3, height: 26 }}>
            {bars.map((b, i) => (
              <div
                key={i}
                style={{
                  width: 4,
                  borderRadius: 2,
                  backgroundColor: COLORS.green,
                  height: Math.max(3, Math.min(26, Math.sqrt(Math.abs(b)) * 130)),
                }}
              />
            ))}
          </div>
        </div>
        <div style={{ borderTop: `2px solid ${COLORS.termBorder}`, marginTop: 18 }} />

        {demoVideoSrc ? (
          // Real VHS-recorded terminal session — actual commands, actual output.
          <OffthreadVideo
            src={staticFile(demoVideoSrc)}
            muted
            style={{ width: "100%", height: 470, objectFit: "cover", display: "block" }}
          />
        ) : (
          <>
            <div style={{ padding: "25px 30px 0", color: COLORS.green, fontSize: 27, fontFamily: monoFont }}>
              {`$ ${typedCmd}`}
              {cursorOn ? "█" : ""}
            </div>

            <div style={{ padding: "20px 30px 30px", display: "flex", flexDirection: "column", gap: 18 }}>
              {demoLogs.slice(0, shownLogCount).map((l, i) => (
                <div key={i} style={{ color: COLORS.mono, fontSize: 22, fontFamily: monoFont }}>
                  {l}
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      <div
        style={{
          marginTop: 40,
          borderRadius: 28,
          backgroundColor: COLORS.cardBg,
          border: `3px solid ${COLORS.cardBorder}`,
          padding: "30px 40px",
        }}
      >
        <div style={{ color: COLORS.label, fontSize: 30, fontWeight: 700, fontFamily: displayFont, textTransform: "uppercase" }}>
          {metricLabel}
        </div>
        <div style={{ color: COLORS.amber, fontSize: 70, fontWeight: 900, fontFamily: displayFont, marginTop: 20 }}>
          {`${currentVal.toFixed(1)} ${metricUnit}`}
        </div>
        <div style={{ marginTop: 45, height: 38, borderRadius: 19, backgroundColor: "#1E293B", overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${barFillPct}%`, borderRadius: 19, backgroundColor: COLORS.amber }} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

const OutroScene: React.FC<{ words: string[] }> = ({ words }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ fps, frame, config: { damping: 12 } });
  const ctaOpacity = interpolate(frame, [10, 25], [0, 1], { extrapolateRight: "clamp" });
  const lastPhrase = words.slice(-8).join(" ");

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg, justifyContent: "center", alignItems: "center", padding: "0 80px" }}>
      <div
        style={{
          fontFamily: displayFont,
          fontWeight: 900,
          fontSize: 54,
          color: COLORS.text,
          textAlign: "center",
          lineHeight: 1.3,
          transform: `scale(${pop})`,
        }}
      >
        {lastPhrase}
      </div>
      <div
        style={{
          marginTop: 40,
          color: COLORS.amber,
          fontFamily: monoFont,
          fontSize: 28,
          fontWeight: 700,
          letterSpacing: 1,
          opacity: ctaOpacity,
        }}
      >
        MORE BREAKOUT REPORTS DAILY →
      </div>
    </AbsoluteFill>
  );
};

export const BreakoutShort: React.FC<BreakoutShortProps> = (props) => {
  const {
    brandLabel,
    title,
    demoCmd,
    demoLogs,
    metricLabel,
    metricVal,
    metricUnit,
    words,
    voiceSrc,
    bgMusicSrc,
    demoVideoSrc,
    durationInFrames,
  } = props;

  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const D = durationInFrames;

  const transitionFrames = Math.min(12, Math.max(4, Math.floor(fps * 0.35)));
  const introFrames = Math.max(20, Math.min(Math.round(fps * 1.6), Math.floor(D * 0.22)));
  const outroFrames = Math.max(20, Math.min(Math.round(fps * 2.1), Math.floor(D * 0.28)));
  const middleFrames = Math.max(30, D - introFrames - outroFrames + transitionFrames * 2);

  // visualizeAudio needs a valid src every render (rules of hooks) -- fall back to the
  // bg music file so the hook call itself never branches, even though only the voice
  // track's amplitude is meaningful for the terminal's live waveform.
  const audioData = useAudioData(staticFile(voiceSrc || bgMusicSrc || "bg_music.wav"));
  const fft = audioData
    ? visualizeAudio({ audioData, frame, fps, numberOfSamples: 32 })
    : new Array(32).fill(0);
  const bars = voiceSrc ? fft.slice(0, 14) : new Array(14).fill(0);

  const wordIdx = Math.min(words.length - 1, Math.floor((frame / Math.max(1, D)) * words.length));
  const windowStart = Math.max(0, wordIdx - 4);
  const windowWords = words.slice(windowStart, windowStart + 10);
  const activeWordStartFrame = Math.floor((wordIdx / Math.max(1, words.length)) * D);
  const wordPop = spring({ fps, frame: frame - activeWordStartFrame, config: { damping: 10, mass: 0.5 } });
  const captionsOpacity = interpolate(frame, [introFrames - 10, introFrames + 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const topBarPct = Math.min(1, frame / Math.max(1, D)) * 100;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg, fontFamily: displayFont }}>
      {voiceSrc ? <Audio src={staticFile(voiceSrc)} /> : null}
      {bgMusicSrc ? <Audio src={staticFile(bgMusicSrc)} volume={0.18} loop /> : null}

      <BackgroundDrift frame={frame} />

      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={introFrames}>
          <IntroScene brandLabel={brandLabel} title={title} />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={slide({ direction: "from-bottom" })}
          timing={springTiming({ config: { damping: 200 } })}
        />
        <TransitionSeries.Sequence durationInFrames={middleFrames}>
          <EvidenceScene
            demoCmd={demoCmd}
            demoLogs={demoLogs}
            metricLabel={metricLabel}
            metricVal={metricVal}
            metricUnit={metricUnit}
            bars={bars}
            middleFrames={middleFrames}
            demoVideoSrc={demoVideoSrc}
          />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition
          presentation={wipe({ direction: "from-right" })}
          timing={linearTiming({ durationInFrames: transitionFrames })}
        />
        <TransitionSeries.Sequence durationInFrames={outroFrames}>
          <OutroScene words={words} />
        </TransitionSeries.Sequence>
      </TransitionSeries>

      {/* Persistent top progress bar -- survives scene transitions */}
      <div style={{ position: "absolute", top: 0, left: 0, height: 8, width: `${topBarPct}%`, backgroundColor: COLORS.amber }} />

      {/* Persistent kinetic subtitles -- survives scene transitions, hidden during the intro hero beat */}
      <div
        style={{
          position: "absolute",
          bottom: 90,
          left: 60,
          width: 960,
          opacity: captionsOpacity,
          display: "flex",
          flexWrap: "wrap",
          gap: "0 14px",
          fontFamily: displayFont,
          fontSize: 46,
          fontWeight: 800,
          lineHeight: 1.5,
          textShadow: "0 4px 18px rgba(0,0,0,0.85)",
        }}
      >
        {windowWords.map((w, i) => {
          const absIdx = windowStart + i;
          const isActive = absIdx === wordIdx;
          return (
            <span
              key={absIdx}
              style={{
                color: isActive ? COLORS.amber : COLORS.text,
                display: "inline-block",
                transform: isActive ? `scale(${0.7 + wordPop * 0.3})` : "scale(1)",
              }}
            >
              {w}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
