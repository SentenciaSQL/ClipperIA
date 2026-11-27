# Phases 5–7

## Phase 5 — Automatic clip generation

- Generate clips from ranked highlights
- Duration presets: 12/15/20/30/45/60/90s
- Aspect ratios: 9:16, 16:9, 1:1
- FFmpeg encoding with NVENC when available, libx264 fallback
- Export presets: TikTok, Instagram Reels, YouTube Shorts, landscape, square
- Export Center UI

## Phase 6 — Advanced editing

- Clip timeline start/end + aspect + zoom
- Caption generation from transcripts (SRT/ASS)
- Smart reframing via OpenCV Haar face tracking (center fallback)
- Optional Demucs stem separation (`pip install demucs`)
- Render alternate clip versions without modifying originals

## Phase 7 — Live integrations

Independent adapters:

- YouTube Data API OAuth + live status + live chat when broadcast is active
- Twitch Helix OAuth + stream status (chat via IRC/EventSub not Helix history)
- Kick OAuth/API adapter with configurable endpoints

Important limitation (by design):

Platform metadata/chat APIs do **not** provide authorized raw AV.
The app supports an **OBS / local authorized capture** rolling buffer, then runs the existing highlight → clip pipeline on buffer segments.

Configure credentials with `ACP_YOUTUBE_*`, `ACP_TWITCH_*`, `ACP_KICK_*`.
