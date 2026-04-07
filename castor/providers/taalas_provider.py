"""Taalas HC1 provider for OpenCastor.

Connects to a Taalas HC1 ASIC inference device via its OpenAI-compatible
API endpoint (default: ``http://localhost:8000``).  Designed for high-Hz
closed-loop motor control with ultra-fast inference (~17K tokens/second
on Llama 3.1 8B).

No API key is required — the HC1 runs on your local network.

Environment variables:
    TAALAS_ENDPOINT  — Override the default base URL (e.g. ``http://taalas-hc1:8000``)

Features:
    - OpenAI-compatible /v1/chat/completions API
    - Sub-10ms inference latency for motor commands
    - Vision support via base64 image payloads
    - Streaming support for real-time feedback
"""

import base64
import json
import logging
import os
import time
from typing import Any, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from .base import BaseProvider, Thought

logger = logging.getLogger("OpenCastor.Taalas")

DEFAULT_ENDPOINT = "http://localhost:8000"
DEFAULT_MODEL = "llama-3.1-8b"
DEFAULT_TIMEOUT = 5  # Low timeout — HC1 inference is ~3-6ms


def _http_request(
    url: str,
    data: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """Make an HTTP request to the Taalas API."""
    try:
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            req = Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
        else:
            req = Request(url)

        resp = urlopen(req, timeout=timeout)
        raw = resp.read().decode("utf-8")
        if not raw.strip():
            return {}
        return json.loads(raw)
    except (URLError, OSError, ConnectionRefusedError) as exc:
        host = "/".join(url.split("/")[:3])
        raise ConnectionError(
            f"Cannot connect to Taalas HC1 at {host}. "
            f"Check that the device is powered on and reachable. Error: {exc}"
        ) from exc


class TaalasProvider(BaseProvider):
    """Taalas HC1 ASIC inference adapter.

    Connects to the HC1 via its OpenAI-compatible ``/v1/chat/completions``
    endpoint.  Optimised for high-Hz operation — the HC1 delivers ~17K
    tokens/second on Llama 3.1 8B, enabling sub-10ms motor command
    generation.

    Config options:
        - ``endpoint_url``: Taalas API URL (default: http://localhost:8000)
        - ``model``: Model name (default: llama-3.1-8b)
        - ``timeout``: Request timeout in seconds (default: 5)
        - ``vision_enabled``: Enable vision/multimodal mode (default: False)
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.endpoint = (
            os.getenv("TAALAS_ENDPOINT") or config.get("endpoint_url") or DEFAULT_ENDPOINT
        ).rstrip("/")
        self.model_name = config.get("model", DEFAULT_MODEL)
        self.timeout = config.get("timeout", DEFAULT_TIMEOUT)
        self.is_vision = config.get("vision_enabled", False)
        logger.info(
            "Taalas HC1: endpoint=%s model=%s timeout=%ds",
            self.endpoint,
            self.model_name,
            self.timeout,
        )

    def think(
        self,
        image_bytes: bytes,
        instruction: str,
        surface: str = "whatsapp",
    ) -> Thought:
        """Generate a response from the Taalas HC1."""
        safety_block = self._check_instruction_safety(instruction)
        if safety_block is not None:
            return safety_block

        try:
            if self.is_vision and image_bytes:
                return self._think_vision(image_bytes, instruction)
            else:
                return self._think_text(instruction, surface=surface)
        except ConnectionError:
            raise
        except Exception as e:
            logger.error("Taalas inference error: %s", e)
            return Thought(f"Error: {e}", None)

    def _think_vision(self, image_bytes: bytes, instruction: str) -> Thought:
        """Send image + instruction via OpenAI-compatible vision API."""
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        t0 = time.time()

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                        },
                    ],
                },
            ],
        }

        response = _http_request(
            f"{self.endpoint}/v1/chat/completions",
            data=payload,
            timeout=self.timeout,
        )

        latency_ms = round((time.time() - t0) * 1000, 1)
        text = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        action = self._clean_json(text)
        self._log_usage(response)
        thought = Thought(text, action, provider="taalas", model=self.model_name)
        thought.latency_ms = latency_ms
        return thought

    def _think_text(self, instruction: str, surface: str = "whatsapp") -> Thought:
        """Text-only inference via OpenAI-compatible chat API."""
        t0 = time.time()

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": self.build_messaging_prompt(surface=surface),
                },
                {"role": "user", "content": instruction},
            ],
        }

        response = _http_request(
            f"{self.endpoint}/v1/chat/completions",
            data=payload,
            timeout=self.timeout,
        )

        latency_ms = round((time.time() - t0) * 1000, 1)
        text = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        action = self._clean_json(text)
        self._log_usage(response)
        thought = Thought(text, action, provider="taalas", model=self.model_name)
        thought.latency_ms = latency_ms
        return thought

    def _log_usage(self, response: dict) -> None:
        """Log token usage from the OpenAI-compatible response."""
        try:
            from castor.usage import get_tracker

            usage = response.get("usage", {})
            get_tracker().log_usage(
                provider="taalas",
                model=self.model_name,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )
        except Exception:
            pass

    def health_check(self) -> dict:
        """Ping the Taalas HC1 models endpoint."""
        t0 = time.time()
        try:
            _http_request(
                f"{self.endpoint}/v1/models",
                timeout=min(self.timeout, 3),
            )
            return {
                "ok": True,
                "latency_ms": round((time.time() - t0) * 1000, 1),
                "error": None,
            }
        except Exception as exc:
            return {
                "ok": False,
                "latency_ms": round((time.time() - t0) * 1000, 1),
                "error": str(exc),
            }
