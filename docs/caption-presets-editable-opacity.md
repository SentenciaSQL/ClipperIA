# Editable caption presets + independent video opacity

## What changed

### Editable presets
- System presets are **starting points**; every property can be edited after selection.
- Custom presets: save / duplicate / delete / restore system defaults.
- Stored in `app_settings` key `caption_presets_custom` (no Alembic migration).
- Style schema includes typography, position (`pos_x`/`pos_y` + margins), max width, text/background opacity, outline, shadow, animations.
- ASS writer maps these fields (incl. `\pos`, `\fad`, pop scale) with PlayRes 1080×1920.

### Preview layers
Flutter preview `Stack`:
1. Black plate
2. **Video** wrapped in `Opacity` (video opacity only)
3. **Captions** as `CaptionOverlayLayer` (draggable) — never inside the video Opacity

### Export
Unchanged compose rule: video opacity on black **before** `subtitles=` burn-in.

## Validate (Windows)

```powershell
git pull
.\start-backend.cmd
# other terminal
cd apps\desktop
flutter run -d windows
```

1. Captions tab → pick Classic → change font size / margins / colors → Apply style.
2. Drag caption on preview → Save caption position → Render.
3. Save as custom preset → reopen clip → custom still listed.
4. Opacity tab → 30% → captions stay solid; keyframes example → captions unchanged.
5. Export and compare.
