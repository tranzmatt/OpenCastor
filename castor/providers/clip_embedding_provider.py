"""
CLIP/SigLIP2 local embedding provider — Tier 0 (default, free, CPU-only).

Encodes text and images into a shared 512-dim embedding space using
openai/clip-vit-base-patch32 (or any HuggingFace CLIP checkpoint).

Falls back to zero-vector mock mode when transformers/Pillow is not installed.
CPU-only — never calls .cuda().

Install:  pip install transformers pillow torch
Model:    openai/clip-vit-base-patch32  (~340 MB, cached to ~/.cache/huggingface)
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from .embedding_backend import EmbeddingBackend

logger = logging.getLogger("OpenCastor.CLIPEmbedding")

HAS_TRANSFORMERS = False
HAS_PIL = False
HAS_TORCH = False

try:
    import torch as _torch  # noqa: F401

    HAS_TORCH = True
except ImportError:
    pass

try:
    from PIL import Image as _PILImage  # noqa: F401

    HAS_PIL = True
except ImportError:
    pass

try:
    from transformers import CLIPModel as _CLIPModel  # noqa: F401
    from transformers import CLIPProcessor as _CLIPProcessor  # noqa: F401

    HAS_TRANSFORMERS = True
except ImportError:
    pass

_DEFAULT_MODEL = "openai/clip-vit-base-patch32"
_DEFAULT_DIMS = 512

# Module-level singleton
_instance: Optional[CLIPEmbeddingProvider] = None


class CLIPEmbeddingProvider(EmbeddingBackend):
    """Local CLIP embedding provider — Tier 0.

    Encodes text and/or images to unit-normalised 512-dim float32 vectors.
    Uses a module-level singleton to avoid repeated model loads.

    Args:
        config: Dict with optional keys:
            - ``model``  (str): HuggingFace model id (default ``openai/clip-vit-base-patch32``)
    """

    def __init__(self, config: dict | None = None):
        cfg = config or {}
        model_id = cfg.get("model", _DEFAULT_MODEL)
        self._model_id = model_id
        self._model = None
        self._processor = None
        self._mock = model_id == "mock"

        if not self._mock:
            self._load_model()

    def _load_model(self) -> None:
        """Lazy-load the CLIP model (called at construction time)."""
        if not (HAS_TRANSFORMERS and HAS_PIL and HAS_TORCH):
            missing = []
            if not HAS_TRANSFORMERS:
                missing.append("transformers")
            if not HAS_PIL:
                missing.append("pillow")
            if not HAS_TORCH:
                missing.append("torch")
            logger.warning(
                "CLIPEmbeddingProvider: missing packages %s — running in mock mode. "
                "Install with: pip install %s",
                missing,
                " ".join(missing),
            )
            self._mock = True
            return
        try:
            import torch  # noqa: F401
            from transformers import CLIPModel, CLIPProcessor

            self._processor = CLIPProcessor.from_pretrained(self._model_id)
            self._model = CLIPModel.from_pretrained(self._model_id)
            self._model.eval()
            # CPU only — never call .cuda()
            logger.info("CLIPEmbeddingProvider loaded model=%s (CPU)", self._model_id)
        except Exception as exc:
            logger.warning("CLIPEmbeddingProvider: model load failed (%s) — mock mode", exc)
            self._mock = True

    # ── EmbeddingBackend interface ─────────────────────────────────────────────

    @property
    def dimensions(self) -> int:
        """Output embedding dimensions."""
        return _DEFAULT_DIMS

    @property
    def backend_name(self) -> str:
        """Backend identifier."""
        return "clip-mock" if self._mock else "clip"

    @property
    def available(self) -> bool:
        """True when the CLIP model is loaded and ready."""
        return not self._mock

    def embed(
        self,
        text: str | None = None,
        image_bytes: bytes | None = None,
        audio_bytes: bytes | None = None,
    ) -> np.ndarray:
        """Embed text and/or image into a unit-norm 512-dim float32 vector.

        Args:
            text:        Text string to embed (optional).
            image_bytes: Raw JPEG/PNG image bytes (optional).
            audio_bytes: Ignored — CLIP does not support audio. Logs debug msg.

        Returns:
            float32 ndarray of shape ``(512,)``.  Returns zeros in mock mode or on error.
        """
        if audio_bytes is not None:
            logger.debug("CLIPEmbeddingProvider: audio not supported, ignoring audio_bytes")

        if self._mock:
            return np.zeros(_DEFAULT_DIMS, dtype=np.float32)

        try:
            import torch  # noqa: F401

            text_vec: np.ndarray | None = None
            image_vec: np.ndarray | None = None

            if text is not None:
                text_vec = self._encode_text(text)

            if image_bytes is not None:
                image_vec = self._encode_image(image_bytes)

            if text_vec is not None and image_vec is not None:
                combined = text_vec + image_vec
                norm = float(np.linalg.norm(combined))
                if norm < 1e-9:
                    return np.zeros(_DEFAULT_DIMS, dtype=np.float32)
                return (combined / norm).astype(np.float32)
            elif text_vec is not None:
                return text_vec
            elif image_vec is not None:
                return image_vec
            else:
                return np.zeros(_DEFAULT_DIMS, dtype=np.float32)
        except Exception as exc:
            logger.warning("CLIPEmbeddingProvider.embed error: %s", exc)
            return np.zeros(_DEFAULT_DIMS, dtype=np.float32)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _encode_text(self, text: str) -> np.ndarray:
        """Encode text to unit-norm 512-dim vector."""
        import torch

        inputs = self._processor(text=[text], return_tensors="pt", padding=True)
        with torch.no_grad():
            feats = self._model.get_text_features(**inputs)
        vec = feats[0].numpy().astype(np.float32)
        return _l2_norm(vec)

    def _encode_image(self, image_bytes: bytes) -> np.ndarray:
        """Decode JPEG/PNG bytes and encode to unit-norm 512-dim vector."""
        import io

        import torch
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = self._processor(images=img, return_tensors="pt")
        with torch.no_grad():
            feats = self._model.get_image_features(**inputs)
        vec = feats[0].numpy().astype(np.float32)
        return _l2_norm(vec)


def _l2_norm(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm < 1e-9:
        return vec
    return (vec / norm).astype(np.float32)


def get_clip_provider(config: dict | None = None) -> CLIPEmbeddingProvider:
    """Return the module-level CLIPEmbeddingProvider singleton."""
    global _instance
    if _instance is None:
        _instance = CLIPEmbeddingProvider(config)
    return _instance
