# How the demo video was made

`unlock-demo.mp4` (1 min 38 s, 1920×1080, H.264 + AAC, −16 LUFS) is published on the v0.1.0 release.

1. **Screen**: `frontend/scripts/record-demo.mjs` drives the real app with Playwright (real engine, committed
   snapshot `sncf_lift_status@2273b7c1cb17`, no mocked data) and records the browser. Captions, the pointer
   ring and the two title cards are overlays injected into the page during recording. The script logs the start
   time of every narration segment to `marks.json`.
2. **Narration**: `video/narration.json`, synthesised locally with the open-weight **Kokoro** TTS model
   (Apache-2.0), voice `af_heart`. No voice actor, music or stock footage is used.
3. **Mux**: ffmpeg places each clip at its logged start (`adelay`), normalises loudness (`loudnorm I=-16`),
   encodes H.264 (CRF 20) with `+faststart`.

Every number shown or spoken is produced live by the engine during recording. After a data refresh the
numbers can differ — re-record rather than edit.
