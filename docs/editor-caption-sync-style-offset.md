# Editor improvements — caption sync, style preview, text corrections, audio offset

## Changes

| Area | Behavior |
|------|----------|
| Caption ↔ audio | Captions store `style.source` (track id/kind/path). Voice-track changes mark `captions_stale`. Music/sfx do **not**. |
| Regenerate flow | `POST …/captions/regenerate-preview` → review draft → `…/regenerate-apply` (optional keep manual corrections). Styles preserved. |
| Text corrections | `POST …/subtitles/{id}/correct` replaces words/phrases; stores `original_text` + `manually_corrected`. Restore via `…/restore`. Style untouched. |
| Style preview | Flutter `CaptionStylePreview` renders ASS fields (font, colour, outline, shadow, box) over a video-like backdrop. |
| Audio offset | `offset_seconds` alias of `start_seconds`. UI slider + numeric field + Reset. Applied via `adelay` in FFmpeg (incl. original track). |

## No new migration

Uses existing `clip_audio_tracks.start_seconds` / `sync_offset_seconds` and JSON on `editor_json` / subtitle `style_json` / cue objects.

## Windows validation

```powershell
cd C:\Users\PC\Documents\python\ClipperIA
git pull
cd backend
.\.venv\Scripts\Activate.ps1
# no alembic step required for this change set
cd ..
.\scripts\run_backend.ps1
# other terminal
cd apps\desktop
flutter pub get
flutter run -d windows
```

1. Mute/replace voice → Captions shows stale banner.
2. Preview from voice track → compare → Apply (styles kept).
3. Open style gallery → live preview updates on selection.
4. Correct a misspelled word → Save → reopen → correction persists; Restore works.
5. Import music, set Offset = 5 → export → music starts at 5s.
