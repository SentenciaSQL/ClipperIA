# Phases 8–9 — Hybrid AI, automation, optimization & distribution

## Phase 8 deliverables

- **Provider registry** (`app/ai/providers/registry.py`) with local Ollama and OpenAI-compatible cloud adapters
- Modes: `local` | `cloud` | `auto` (local-first fallback)
- **Content metadata**: AI titles, descriptions, hashtags, hooks, CTA (`POST /clips/{id}/metadata`)
- **Processing profiles**: balanced / fast / quality / cloud_assist (`/profiles`)
- **Batch automation**: end-to-end pipeline job (`POST /batch/process`)
- **Alternative clip versions**: multi aspect-ratio renders (`POST /clips/{id}/versions`)
- Desktop Settings + Clip Editor + Library batch controls

## Phase 9 deliverables

- Resource snapshot + recommendations (`GET /system/resources`)
- Storage usage + cache cleanup (`/storage/*`)
- Whisper model inventory / ensure / delete (`/models/*`)
- Job recovery toggle (`ACP_JOB_RECOVERY_ENABLED`) and concurrency caps
- Startup cache auto-cleanup when over budget
- Windows packaging:
  - `scripts/build_windows.ps1` — Flutter release + staged backend
  - `scripts/package_windows_installer.ps1` + `packaging/windows/ai_clipping_platform.iss`

## Manual validation checklist

1. Start backend + desktop; confirm Settings → AI providers status.
2. Switch mode local/auto/cloud (cloud needs `ACP_CLOUD_LLM_API_KEY`).
3. Import a short video → Batch process with `balanced` profile.
4. Open a clip → AI description + Alt ratios.
5. Settings → Ensure Whisper `tiny`, Cleanup cache, review storage usage.
6. On Windows: `.\scripts\build_windows.ps1` then package with Inno Setup.

## Environment additions

```text
ACP_AI_PROVIDER=local
ACP_CLOUD_LLM_API_KEY=
ACP_CLOUD_LLM_BASE_URL=https://api.openai.com/v1
ACP_CLOUD_LLM_MODEL=gpt-4o-mini
ACP_STORAGE_CACHE_MAX_MB=4096
ACP_STORAGE_AUTO_CLEANUP=true
ACP_JOB_RECOVERY_ENABLED=true
```
