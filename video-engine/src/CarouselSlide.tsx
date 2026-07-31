import { AbsoluteFill, useCurrentFrame } from "remotion";
import { loadFont as loadDisplayFont } from "@remotion/google-fonts/Inter";
import React from "react";

const { fontFamily: displayFont } = loadDisplayFont("normal", {
  weights: ["400", "600", "700", "800", "900"],
  subsets: ["latin"],
});

// Shared with BreakoutShort so a carousel and a short read as one channel.
const COLORS = {
  bg: "#090B0E",
  text: "#F8FAFC",
  body: "#CBD5E1",
  dim: "#64748B",
  rule: "#283244",
};

export type CarouselSlideProps = {
  slides: string[];
  brandLabel: string;
  handle?: string;
  accentColor?: string;
  topic?: string;
};

/**
 * One LinkedIn carousel page per frame.
 *
 * Rendered as an image sequence (fps 1, durationInFrames = slides.length) so
 * all pages come out of a single Remotion bundle, then assembled into the PDF
 * LinkedIn expects for a document post.
 */
export const CarouselSlide: React.FC<CarouselSlideProps> = ({
  slides,
  brandLabel,
  handle = "",
  accentColor = "#F0B72F",
  topic = "",
}) => {
  const frame = useCurrentFrame();
  const total = Math.max(1, slides.length);
  const index = Math.min(frame, total - 1);
  const raw = (slides[index] ?? "").trim();

  const isCover = index === 0;
  const isLast = index === total - 1;

  // "Heading — body" and "Heading: body" both read as a lede plus detail; a
  // slide without either is shown whole rather than split at an arbitrary point.
  const splitAt = raw.search(/\s[—:]\s/);
  const heading = splitAt > 0 && !isCover ? raw.slice(0, splitAt).trim() : "";
  const tail = splitAt > 0 && !isCover ? raw.slice(splitAt + 3).trim() : raw;
  // "The core development — two independent timelines..." leaves the body
  // starting mid-sentence, which reads as a typo once the dash is gone.
  const body = heading && tail ? tail.charAt(0).toUpperCase() + tail.slice(1) : tail;

  // Long slides need to step down or they overflow the page.
  const bodyLength = body.length;
  const bodySize = isCover
    ? bodyLength > 120 ? 68 : 82
    : bodyLength > 320 ? 36 : bodyLength > 180 ? 42 : 48;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: COLORS.bg,
        fontFamily: displayFont,
        padding: 84,
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <div style={{ width: 46, height: 6, backgroundColor: accentColor, borderRadius: 3 }} />
        <div
          style={{
            fontSize: 22,
            fontWeight: 700,
            letterSpacing: 2.4,
            color: COLORS.dim,
            textTransform: "uppercase",
          }}
        >
          {brandLabel}
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 26 }}>
        {topic && isCover ? (
          <div
            style={{
              fontSize: 24,
              fontWeight: 700,
              letterSpacing: 1.6,
              color: accentColor,
              textTransform: "uppercase",
            }}
          >
            {topic}
          </div>
        ) : null}

        {heading ? (
          <div style={{ fontSize: 52, fontWeight: 800, color: COLORS.text, lineHeight: 1.15 }}>
            {heading}
          </div>
        ) : null}

        <div
          style={{
            fontSize: bodySize,
            fontWeight: isCover ? 900 : 500,
            color: heading ? COLORS.body : COLORS.text,
            lineHeight: 1.32,
          }}
        >
          {body}
        </div>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderTop: `2px solid ${COLORS.rule}`,
          paddingTop: 26,
        }}
      >
        <div style={{ display: "flex", gap: 9 }}>
          {slides.map((_, dot) => (
            <div
              key={dot}
              style={{
                width: dot === index ? 30 : 10,
                height: 10,
                borderRadius: 5,
                backgroundColor: dot === index ? accentColor : COLORS.rule,
              }}
            />
          ))}
        </div>
        <div style={{ fontSize: 24, fontWeight: 600, color: isLast ? accentColor : COLORS.dim }}>
          {isLast ? handle || "→" : `${index + 1} / ${total}`}
        </div>
      </div>
    </AbsoluteFill>
  );
};
