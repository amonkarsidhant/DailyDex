import "./index.css";
import { Composition } from "remotion";
import { MyComposition } from "./Composition";
import { ShortsTemplate } from "./ShortsTemplate";

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
    </>
  );
};
