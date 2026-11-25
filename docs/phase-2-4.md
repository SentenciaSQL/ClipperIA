# Phases 2–4

## Phase 2 — Media Ingestion & Library

- Local import of MP4 / MKV / MOV (path import + multipart upload)
- FFmpeg/ffprobe metadata extraction
- Thumbnail generation
- Managed copies under `Documents/AIClippingPlatform/media/originals/`
- Project CRUD
- Library search/filter, reprocess, delete (originals outside library are never mutated)

## Phase 3 — AI Transcription & Analysis

- Job manager with SQLite persistence, concurrency limits, GPU semaphore, restart recovery
- faster-whisper transcription (CPU/CUDA auto)
- Silero VAD speech segments
- Transcript persistence
- Ollama + Qwen3 semantic analysis when available
- Explicit `local_heuristic` fallback when Ollama is offline (not presented as Qwen)

## Phase 4 — Highlight Detection

Configurable weighted scoring:

| Signal | Default weight |
|--------|----------------|
| Audio intensity | 20% |
| Voice / emotion | 20% |
| Semantic | 25% |
| Chat activity | 15% (reserved; 0 until Phase 7) |
| Visual changes | 10% |
| Narrative quality | 10% |

Includes candidate generation, IoU-based deduplication, and highlight review (accept/reject) in the desktop UI.

## Manual validation

1. Import a local video in Video Library.
2. Queue transcription (library action or Highlights pipeline button).
3. Confirm transcript text + VAD segments via API or UI jobs panel.
4. Run semantic analysis (uses Ollama if present).
5. Detect highlights and review ranked moments.
