import { AbsoluteFill, Img, Sequence, useCurrentFrame, useVideoConfig, staticFile, spring, interpolate } from "remotion";
import React from "react";

export type ShortsProps = {
  backgroundUrl: string;
};

export const ShortsTemplate: React.FC<ShortsProps> = ({ backgroundUrl }) => {
  const { fps, durationInFrames } = useVideoConfig();
  const frame = useCurrentFrame();

  const imgSrc = backgroundUrl.startsWith("http") ? backgroundUrl : staticFile(backgroundUrl);

  // Background slow pan
  const scale = 1 + (frame / durationInFrames) * 0.15;

  return (
    <AbsoluteFill style={{ backgroundColor: "#0b0b0f", color: "white", fontFamily: "sans-serif" }}>
      <AbsoluteFill>
        <Img src={imgSrc} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})`, opacity: 0.3 }} />
      </AbsoluteFill>

      {/* Intro Scene */}
      <Sequence from={0} durationInFrames={100}>
        <IntroScene />
      </Sequence>
      
      {/* Features Showcase */}
      <Sequence from={90} durationInFrames={130}>
        <FeaturesScene />
      </Sequence>
      
      {/* Outro */}
      <Sequence from={210} durationInFrames={90}>
        <OutroScene />
      </Sequence>
    </AbsoluteFill>
  );
};

const IntroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  
  const textScale = spring({ fps, frame, config: { damping: 12 } });
  const opacity = interpolate(frame, [80, 95], [1, 0], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", opacity }}>
      <h1 style={{ fontSize: "110px", fontWeight: "900", transform: `scale(${textScale})`, textShadow: "0px 0px 30px rgba(0, 255, 255, 0.6)", color: "#ffffff" }}>
        DAILYDEX
      </h1>
      <p style={{ fontSize: "40px", marginTop: "20px", opacity: Math.min(1, frame / 30), color: "#00ffff" }}>
        The Agentic Creator Factory
      </p>
    </AbsoluteFill>
  );
};

const FeaturesScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const slideY = spring({ fps, frame, config: { damping: 14 } });
  const opacity = interpolate(frame, [110, 130], [1, 0], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", opacity, transform: `translateY(${100 - slideY * 100}px)` }}>
      <h2 style={{ fontSize: "80px", fontWeight: "bold", color: "#00ffff", textShadow: "0px 0px 20px rgba(0, 255, 255, 0.4)" }}>Capabilities</h2>
      <div style={{ display: "flex", flexDirection: "column", gap: "30px", marginTop: "50px", fontSize: "45px", width: "80%" }}>
        <FeatureItem delay={15} text="📰 AI Signal Cockpit" />
        <FeatureItem delay={30} text="🏆 Title Tournaments" />
        <FeatureItem delay={45} text="🎬 Automated Shorts" />
      </div>
    </AbsoluteFill>
  );
};

const FeatureItem: React.FC<{ delay: number, text: string }> = ({ delay, text }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ fps, frame: frame - delay, config: { damping: 10 } });
  
  return (
    <div style={{ 
      transform: `scale(${pop})`, 
      padding: "30px 40px", 
      backgroundColor: "rgba(0, 20, 40, 0.6)", 
      borderRadius: "20px", 
      border: "2px solid rgba(0, 255, 255, 0.5)",
      backdropFilter: "blur(10px)",
      boxShadow: "0px 10px 30px rgba(0,0,0,0.5)",
      textAlign: "center",
      fontWeight: "bold"
    }}>
      {text}
    </div>
  );
};

const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ fps, frame, config: { damping: 12 } });

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <h1 style={{ fontSize: "80px", fontWeight: "bold", transform: `scale(${pop})`, textAlign: "center", lineHeight: "1.2", textShadow: "0px 0px 20px rgba(0,255,255,0.4)" }}>
        Build your audience.<br/><span style={{color: "#00ffff"}}>On Autopilot.</span>
      </h1>
    </AbsoluteFill>
  );
};
