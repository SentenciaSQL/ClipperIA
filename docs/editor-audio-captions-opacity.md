# Editor expansion — audio, captions, opacity

## Existing components reused

- `Clip` / `ClipVersion` / `Subtitle` / `Export`
- `SubtitleService` ASS/SRT writers
- `MediaEncoder` + NVENC fallback
- `ClipService.render_clip` / `ExportService.export_clip`
- `DemucsSeparator` (optional)
- Flutter `ClipEditorPage` + `LocalVideoPreview`

## Added

| Area | Change |
|------|--------|
| Schema | `clips.editor_json`, table `clip_audio_tracks` (migration `a1b2c3d4e5f6`) |
| Encoder | Video opacity **before** captions; multi-track `amix`; volume/fade/delay |
| Services | `EditorService`, `AudioTrackService`, caption presets + word overrides |
| API | `/clips/{id}/editor`, audio-tracks CRUD/import, Demucs job, caption advanced routes |
| Flutter | Editor tabs: Timeline / Audio / Captions / Opacity |

## Fundamental opacity rule

FFmpeg composition applies video opacity on a black base, **then** burns ASS captions. Captions are never multiplied by video opacity.

## Demucs 501

Install in the backend venv:

```powershell
pip install demucs
```

Separation is a background job (`separate_audio`); stems become audio tracks.

## Manual validation (Windows)

1. Restart backend (`alembic upgrade head` once).
2. Open a clip in Clip Editor.
3. Audio: mute original, import MP3, adjust volumes.
4. Captions: generate, edit text, apply word override, pick preset.
5. Opacity: set 40% (or example keyframes) — captions remain readable.
6. Render version + Export Center export.
7. Reopen clip — editor state and tracks persist.
