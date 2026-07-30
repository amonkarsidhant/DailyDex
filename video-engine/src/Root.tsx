import "./index.css";
import { Composition } from "remotion";
import { MyComposition } from "./Composition";
import { ShortsTemplate } from "./ShortsTemplate";
import { BreakoutShort } from "./BreakoutShort";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="MyComp"
        component={MyComposition}
        durationInFrames={60}
        fps={30}
        width={1280}
        height={720}
      />
      <Composition
        id="ShortsTemplate"
        component={ShortsTemplate}
        durationInFrames={300}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          backgroundUrl: "https://images.unsplash.com/photo-1620641788421-7a1c342ea42e"
        }}
      />
      <Composition
        id="BreakoutShort"
        component={BreakoutShort}
        durationInFrames={300}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{
          brandLabel: "DAILYDEX • AI REPORT",
          accentColor: "#F0B72F",
          ctaLabel: "FOLLOW FOR MORE AI REPORTS",
          demoMode: "illustrative" as const,
          title: "Source-Backed AI Signal",
          demoCmd: "dailydex inspect --evidence",
          demoLogs: [
            "[SOURCE] Waiting for source evidence",
            "[SIGNAL] DailyDex score: 0.0 / 100",
            "[COVERAGE] 0 source families observed",
          ],
          metricLabel: "DailyDex Signal Score",
          metricVal: 0,
          metricUnit: "/ 100",
          words: ["Source-backed", "AI", "signal", "report."],
          voiceSrc: "",
          bgMusicSrc: "bg_music.wav",
          durationInFrames: 300,
          fps: 30,
        }}
        calculateMetadata={async ({ props }) => {
          const p = props as Record<string, unknown>;
          return {
            durationInFrames: (typeof p.durationInFrames === "number" && p.durationInFrames > 0) ? p.durationInFrames : 300,
            fps: (typeof p.fps === "number" && p.fps > 0) ? p.fps : 30,
          };
        }}
      />
    </>
  );
};
