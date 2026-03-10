# Episode Store — Multi-Vector Schema Design

## Overview

The episode store is the on-device semantic memory for OpenCastor's EmbeddingInterpreter.
It persists robot experiences as embedding vectors plus metadata, enabling retrieval-augmented
generation (RAG) during planning and similarity-based episode replay.

## Storage Format

The store uses two files in the configured `episode_store` directory
(default: `~/.opencastor/episodes/`):

| File | Format | Purpose |
|---|---|---|
| `embeddings.npy` | float32 ndarray, shape `(N, D)` | All episode embedding vectors |
| `meta.json` | JSON array of objects | Episode metadata (one entry per row) |

Both files are kept in sync. The numpy array is row-indexed to match the JSON array.

## Metadata Schema

Each entry in `meta.json` follows this schema:

```json
{
  "timestamp": "2026-03-10T12:34:56.789+00:00",
  "instruction": "navigate to the kitchen table",
  "action_type": "nav_waypoint",
  "outcome": "success",
  "goal_similarity": 0.8712,
  "tick_id": 42,
  "backend": "clip"
}
```

| Field | Type | Description |
|---|---|---|
| `timestamp` | ISO 8601 UTC | When the episode was recorded |
| `instruction` | str (max 200 chars) | The task instruction at the time |
| `action_type` | str | The action type from `Thought.action.type` |
| `outcome` | str | Human-readable outcome tag (e.g. `"success"`, `"collision"`) |
| `goal_similarity` | float [-1, 1] | Cosine similarity to mission goal at episode time |
| `tick_id` | int | Monotonically increasing tick counter |
| `backend` | str | Name of the embedding backend used |

## Embedding Dimensions by Backend

| Backend | Dimensions | Notes |
|---|---|---|
| CLIP (Tier 0) | 512 | Default, CPU-only, free |
| ImageBind (Tier 1) | 1024 | CC BY-NC, 6 modalities |
| CLAP (Tier 1) | 512 | Audio+text only |
| Gemini (Tier 2) | 768 / 1536 / 3072 | Paid API, MRL |

## FIFO Eviction

When the store exceeds `max_episodes` (default: 2000), the oldest episodes are
removed first (FIFO). The numpy array is sliced from index `excess:` and the
metadata list is sliced identically.

## Dimension Mismatch Handling

If a new episode's embedding has a different dimension than the existing store
(e.g. the backend was changed), the store is reset: all previous episodes are
discarded and the new episode becomes episode 0. A debug log message is emitted.

## Multi-Vector Extension (Future)

The current design stores a single vector per episode. A future version may store
multiple vectors per episode (one per modality), enabling modality-specific retrieval:

```
Proposed multi-vector schema:
  embeddings_text.npy   — text-only vectors (D_text,)
  embeddings_image.npy  — image-only vectors (D_image,)
  embeddings_fused.npy  — fused vectors (D_fused,)
  meta.json             — unchanged
```

This would require a migration step. The current `EmbeddingInterpreter` stores only
fused vectors to keep the schema simple and backward-compatible.

## Migration Path

When upgrading from single-vector to multi-vector:
1. Rename `embeddings.npy` → `embeddings_fused.npy`
2. Re-embed all episodes with modality-specific encoders (offline batch job)
3. Write `embeddings_text.npy` and `embeddings_image.npy`
4. Update `meta.json` to add a `schema_version: 2` field

The `EmbeddingInterpreter` checks `schema_version` on load and handles both formats.

## Disk Usage Estimates

| Episodes | Backend | Approx disk usage |
|---|---|---|
| 2000 | CLIP (512-dim) | ~4 MB (embeddings) + ~1 MB (meta) |
| 2000 | Gemini (1536-dim) | ~12 MB (embeddings) + ~1 MB (meta) |
| 2000 | ImageBind (1024-dim) | ~8 MB (embeddings) + ~1 MB (meta) |

All embeddings are stored as float32 (4 bytes per dimension).
