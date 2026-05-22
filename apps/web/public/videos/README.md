# Hero background videos

Drop a video file here (recommend `hero.mp4` and optionally `hero.webm`) and
point the app at it via `apps/web/.env.local`:

```
NEXT_PUBLIC_HERO_VIDEO_URL=/videos/hero.mp4
```

If the variable is unset (or the file fails to load), the hero falls back to a
gradient + grain backdrop — no broken UI.

## Specs

- Container: H.264 MP4 (best Safari compatibility) or VP9 WebM
- Resolution: 1920x1080 max; 1280x720 is fine for hero use
- Length: 6–12 seconds, designed to loop seamlessly
- Bitrate target: ≤ 3 Mbps, total file size ≤ 5 MB
- Audio: strip it (`-an` in ffmpeg) — autoplay requires `muted` anyway

Quick compress with ffmpeg:

```bash
ffmpeg -i input.mov -vcodec libx264 -crf 26 -preset slow -movflags +faststart -an -vf "scale=1280:-2" hero.mp4
```

## Free sources (commercial use OK)

- **Pexels Videos** — pexels.com/videos — no attribution required.
  Search: "fashion", "fabric", "model", "minimalist", "runway".
- **Coverr** — coverr.co — curated, designer-friendly, no attribution.
- **Mixkit** — mixkit.co — large fashion + lifestyle catalog, no attribution
  required for individual videos used in your own projects (check per-clip).
- **Pixabay** — pixabay.com/videos — Pixabay License (similar to CC0).
- **Mazwai** — mazwai.com — CC BY 3.0; needs attribution credit somewhere.
- **Videvo** — videvo.net — mixed licenses; filter to "Free for commercial".

## Tone suggestions that fit Clothist's aesthetic

Slow, abstract, fabric/material focused works better than literal models:
- macro slow-mo of fabric folding
- silk or linen ripple in soft light
- long pan over a sewing machine, threads, scissors
- close-up of brushed cotton texture
- aerial / drone over neutral linen sheets
- minimalist still life with slow camera drift

Avoid: fast cuts, color-graded "social-ready" footage, branded clips.
