"use client";

import { useState } from "react";

/**
 * Optional background video for the hero band.
 *
 * Drop a clip at `public/videos/hero.mp4` and set
 * `NEXT_PUBLIC_HERO_VIDEO_URL=/videos/hero.mp4` in `.env.local` to enable.
 * If no video is configured (or it fails to load), a gradient backdrop
 * with the global grain texture is shown instead.
 *
 * Performance notes:
 *   - muted + playsinline + autoplay required for mobile inline playback
 *   - preload="metadata" keeps initial bandwidth low (we let the user
 *     decide whether to ship a real video at all)
 *   - prefers-reduced-motion users get the static fallback
 */
export function HeroBackdrop() {
  const src = process.env.NEXT_PUBLIC_HERO_VIDEO_URL;
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return <StaticBackdrop />;
  }

  return (
    <div className="absolute inset-0 overflow-hidden">
      <video
        src={src}
        autoPlay
        muted
        loop
        playsInline
        preload="metadata"
        onError={() => setFailed(true)}
        className="absolute inset-0 h-full w-full object-cover opacity-30 motion-reduce:hidden"
        aria-hidden
      />
      {/* Top fade for header readability */}
      <div className="absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-background to-transparent" />
      {/* Bottom fade into the rest of the page */}
      <div className="absolute inset-x-0 bottom-0 h-48 bg-gradient-to-t from-background to-transparent" />
      <StaticBackdrop className="motion-reduce:opacity-100 opacity-0" />
    </div>
  );
}

function StaticBackdrop({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={["absolute inset-0 pointer-events-none", className].filter(Boolean).join(" ")}
      style={{
        backgroundImage:
          "radial-gradient(80% 60% at 75% 20%, rgb(var(--accent) / 0.10), transparent 70%), " +
          "radial-gradient(70% 60% at 15% 80%, rgb(var(--fg) / 0.05), transparent 70%)",
      }}
    />
  );
}
