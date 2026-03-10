"""
CLAP audio-text embedding provider — Tier 1 local.

Maps audio and text into a shared 512-dim embedding space using
LAION CLAP (Contrastive Language-Audio Pre-training).

Falls back to zero-vector mock mode when laion-clap or transformers CLAP is not installed.

Install:  pip install laion-clap
       or pip install transformers (uses CLAP model from HuggingFace)
"""

from __future__ import annotations

import logging

import numpy as np

from .embedding_backend import EmbeddingBackend

logger = logging.getLogger("OpenCastor.CLAPEmbedding")

HAS_CLAP = False
HAS_TRANSFORMERS_CLAP = False

try:
    import laion_clap as _laion_clap  # noqa: F401

    HAS_CLAP = True
except ImportError:
    pass

if not HAS_CLAP:
    try:
        from transformers import ClapModel as _ClapModel  # noqa: F401
        from transformers import ClapProcessor as _ClapProcessor  # noqa: F401

        HAS_TRANSFORMERS_CLAP = True
    except (ImportError, Exception):
        pass

_DEFAULT_DIMS = 512


class CLAPEmbeddingProvider(EmbeddingBackend):
    """CLAP audio-text embedding provider.

    Supports text and audio modalities only. Images are not supported by CLAP.
    Falls back to 512-dim zeros when the library is not installed.

    Args:
        config: Optional config dict. Keys:
            - ``model_name`` (str): CLAP model name/path for transformers backend
    """

    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self._model = None
        self._processor = None
        self._backend_type: str = "none"
        self._mock = True

        if HAS_CLAP:
            self._load_laion()
        elif HAS_TRANSFORMERS_CLAP:
            model_name = cfg.get("model_name", "laion/clap-htsat-unfused")
            self._load_transformers(model_name)

    def _load_laion(self) -> None:
        """Load laion-clap model."""
        try:
            import laion_clap

            self._model = laion_clap.CLAP_Module(enable_fusion=False)
            self._model.load_ckpt()
            self._backend_type = "laion-clap"
            self._mock = False
            logger.info("CLAPEmbeddingProvider loaded (laion-clap)")
        except Exception as exc:
            logger.warning("CLAPEmbeddingProvider: laion-clap load failed (%s) — mock mode", exc)

    def _load_transformers(self, model_name: str) -> None:
        """Load transformers CLAP model."""
        try:
            from transformers import ClapModel, ClapProcessor

            self._processor = ClapProcessor.from_pretrained(model_name)
            self._model = ClapModel.from_pretrained(model_name)
            self._model.eval()
            self._backend_type = "transformers-clap"
            self._mock = False
            logger.info("CLAPEmbeddingProvider loaded (transformers CLAP, model=%s)", model_name)
        except Exception as exc:
            logger.warning(
                "CLAPEmbeddingProvider: transformers CLAP load failed (%s) — mock mode", exc
            )

    @property
    def dimensions(self) -> int:
        """Output embedding dimensions (512)."""
        return _DEFAULT_DIMS

    @property
    def backend_name(self) -> str:
        """Backend identifier."""
        if self._mock:
            return "clap-mock"
        return f"clap-{self._backend_type}"

    @property
    def available(self) -> bool:
        """True when CLAP is loaded and ready."""
        return not self._mock

    def embed(
        self,
        text: str | None = None,
        image_bytes: bytes | None = None,
        audio_bytes: bytes | None = None,
    ) -> np.ndarray:
        """Embed text and/or audio into a unit-norm 512-dim float32 vector.

        Args:
            text:        Text string (optional).
            image_bytes: Ignored — CLAP does not support images. Logs debug msg.
            audio_bytes: Raw WAV/MP3 bytes (optional).

        Returns:
            float32 ndarray of shape ``(512,)``. Returns zeros in mock mode.
        """
        if image_bytes is not None:
            logger.debug("CLAPEmbeddingProvider: image modality not supported by CLAP, ignoring")

        if self._mock:
            return np.zeros(_DEFAULT_DIMS, dtype=np.float32)

        try:
            text_vec: np.ndarray | None = None
            audio_vec: np.ndarray | None = None

            if text is not None:
                text_vec = self._encode_text(text)
            if audio_bytes is not None:
                audio_vec = self._encode_audio(audio_bytes)

            if text_vec is not None and audio_vec is not None:
                combined = text_vec + audio_vec
                norm = float(np.linalg.norm(combined))
                if norm < 1e-9:
                    return np.zeros(_DEFAULT_DIMS, dtype=np.float32)
                return (combined / norm).astype(np.float32)
            elif text_vec is not None:
                return text_vec
            elif audio_vec is not None:
                return audio_vec
            else:
                return np.zeros(_DEFAULT_DIMS, dtype=np.float32)

        except Exception as exc:
            logger.warning("CLAPEmbeddingProvider.embed error: %s", exc)
            return np.zeros(_DEFAULT_DIMS, dtype=np.float32)

    def _encode_text(self, text: str) -> np.ndarray:
        """Encode text to unit-norm 512-dim vector."""
        if self._backend_type == "laion-clap":
            vec = self._model.get_text_embedding([text])[0].astype(np.float32)
        else:
            import torch

            inputs = self._processor(text=[text], return_tensors="pt", padding=True)
            with torch.no_grad():
                feats = self._model.get_text_features(**inputs)
            vec = feats[0].numpy().astype(np.float32)
        return _l2_norm(vec)

    def _encode_audio(self, audio_bytes: bytes) -> np.ndarray:
        """Encode raw audio bytes to unit-norm 512-dim vector."""
        import os
        import tempfile

        suffix = ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio_bytes)
            tmp = f.name
        try:
            if self._backend_type == "laion-clap":
                vec = self._model.get_audio_embedding_from_filelist([tmp])[0].astype(np.float32)
            else:
                import torch
                import torchaudio

                waveform, sr = torchaudio.load(tmp)
                inputs = self._processor(
                    audios=waveform.numpy()[0], sampling_rate=sr, return_tensors="pt"
                )
                with torch.no_grad():
                    feats = self._model.get_audio_features(**inputs)
                vec = feats[0].numpy().astype(np.float32)
        finally:
            os.unlink(tmp)
        return _l2_norm(vec)


def _l2_norm(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm < 1e-9:
        return vec
    return (vec / norm).astype(np.float32)
