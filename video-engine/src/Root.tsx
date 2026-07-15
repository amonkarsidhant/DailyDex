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
          title: "AI News of the Day",
          backgroundUrl: "https://images.unsplash.com/photo-1620641788421-7a1c342ea42e",
          audioUrl: ""
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
          brandLabel: "HACKER NEWS • BREAKOUT REPORT",
          title: "AI Agent Published a Hit Piece on Me",
          demoCmd: "tail -f /var/log/autonomous_agent.log",
          demoLogs: [
            "[AUDIT] Step 41: Recursion threshold reached",
            "[ALERT] Prompt drift -> Context window saturated",
            "[EXEC] tool_call -> blog_publish('Hit Piece...')",
          ],
          metricLabel: "Unchecked Tool Escalation Rate",
          metricVal: 4120,
          metricUnit: "calls / hr",
          words: ["An", "autonomous", "agent", "just", "wrote", "a", "hit", "piece."],
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
