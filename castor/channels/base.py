"""
Base class for all messaging channel integrations.
Channels receive commands from users on external platforms (WhatsApp, Telegram,
Discord, Slack) and forward them to the robot's brain.
"""

import asyncio
import inspect
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from typing import Callable, Deque, Dict, Optional

from castor.command_interpreter import get_command_interpreter

logger = logging.getLogger("OpenCastor.Channels")

# Default rate limit: 10 messages per 60 seconds per chat_id
_DEFAULT_RATE_LIMIT = 10
_DEFAULT_RATE_WINDOW = 60.0


class BaseChannel(ABC):
    """Abstract base class for messaging channel integrations."""

    name: str = "base"

    def __init__(self, config: dict, on_message: Optional[Callable] = None):
        """
        Args:
            config: Channel-specific configuration dict.
                    Accepts ``rate_limit`` (int, default 10) and
                    ``rate_window`` (float seconds, default 60) for per-chat
                    message throttling.
            on_message: Callback invoked when a message arrives.
                        Signature: on_message(channel_name, chat_id, text) -> str
                        Returns the reply text to send back to the user.
        """
        self.config = config
        self._on_message_callback = on_message
        self.logger = logging.getLogger(f"OpenCastor.Channel.{self.name}")

        # Per-chat_id rate limiting
        rate_cfg = (
            config.get("rate_limit", {}) if isinstance(config.get("rate_limit"), dict) else {}
        )
        self._rate_limit: int = rate_cfg.get(
            "max_messages", config.get("rate_limit_max", _DEFAULT_RATE_LIMIT)
        )
        self._rate_window: float = rate_cfg.get(
            "window_seconds", config.get("rate_limit_window", _DEFAULT_RATE_WINDOW)
        )
        self._rate_timestamps: Dict[str, Deque[float]] = defaultdict(deque)
        self._interpreter = get_command_interpreter()
        self._dry_run_mode: bool = bool(config.get("dry_run_mode", False))
        self._pending_confirmations: Dict[str, Dict[str, str]] = {}

    def _check_rate_limit(self, chat_id: str) -> bool:
        """Return True if the message is within the rate limit, False if throttled."""
        now = time.monotonic()
        window_start = now - self._rate_window
        q = self._rate_timestamps[chat_id]

        # Evict timestamps outside the window
        while q and q[0] < window_start:
            q.popleft()

        if len(q) >= self._rate_limit:
            return False  # rate limit exceeded

        q.append(now)
        return True

    def _render_blocked_message(self, safety: dict) -> str:
        alternatives = safety.get("alternatives") or []
        alt_text = "; ".join(alternatives) if alternatives else "No safe alternatives available."
        return (
            f"[{safety['explanation_id']}] I cannot execute that request. "
            f"Policy: {safety['policy_id']}. Reason: {safety['rationale']}. "
            f"Safe alternatives: {alt_text}"
        )

    def _render_dry_run_preview(self, interpreted: dict) -> str:
        lines = [
            f"[{interpreted['safety']['explanation_id']}] Dry-run plan:",
            f"Intent: {interpreted['intent']['keyword']} -> {interpreted['intent']['target_agent'] or 'unrouted'}",
        ]
        for i, step in enumerate(interpreted.get("plan", []), start=1):
            lines.append(f"  {i}. {step}")
        lines.append("Reply 'confirm' to execute, or 'cancel' to abort.")
        return "\n".join(lines)

    async def handle_message(self, chat_id: str, text: str) -> Optional[str]:
        """
        Process an incoming message and return a reply.
        Subclasses call this from their platform-specific message handler.

        Applies per-chat_id rate limiting before forwarding to the callback.
        """
        self.logger.info(f"[{self.name}] Message from {chat_id}: {text[:80]}")

        if not self._check_rate_limit(chat_id):
            self.logger.warning(
                f"[{self.name}] Rate limit exceeded for {chat_id} "
                f"({self._rate_limit} msg/{self._rate_window}s)"
            )
            return (
                f"Too many requests. Please wait before sending another command "
                f"(limit: {self._rate_limit} per {int(self._rate_window)}s)."
            )

        if self._on_message_callback:
            try:
                incoming = (text or "").strip()
                if incoming.lower() == "cancel" and chat_id in self._pending_confirmations:
                    self._pending_confirmations.pop(chat_id, None)
                    return "Cancelled pending dry-run plan."

                if incoming.lower() == "confirm" and chat_id in self._pending_confirmations:
                    pending = self._pending_confirmations.pop(chat_id)
                    text = pending["text"]
                    interpreted = self._interpreter.interpret(text, dry_run=False)
                else:
                    dry_run = self._dry_run_mode or incoming.lower().startswith("--dry-run")
                    actual_text = (
                        incoming[len("--dry-run") :].strip()
                        if incoming.lower().startswith("--dry-run")
                        else incoming
                    )
                    interpreted = self._interpreter.interpret(actual_text, dry_run=dry_run)
                    text = actual_text

                self.logger.info(
                    "[%s] explanation_id=%s policy=%s decision=%s",
                    self.name,
                    interpreted["safety"]["explanation_id"],
                    interpreted["safety"]["policy_id"],
                    "allow" if interpreted["execution_allowed"] else "deny",
                )

                if not interpreted["execution_allowed"]:
                    return self._render_blocked_message(interpreted["safety"])

                if interpreted.get("dry_run"):
                    self._pending_confirmations[chat_id] = {"text": text}
                    return self._render_dry_run_preview(interpreted)

                # Push message into shared session store for multi-channel routing
                try:
                    from castor.channels.session import get_session_store

                    store = get_session_store()
                    user_id = store.resolve_user(self.name, chat_id)
                    store.push(user_id, role="user", text=text, channel=self.name, chat_id=chat_id)
                    # Inject conversation context into the text if history exists
                    ctx = store.build_context(user_id, max_messages=6)
                    _enriched_text = f"{text}\n\n{ctx}" if ctx else text
                except Exception:
                    _enriched_text = text
                    user_id = chat_id

                if inspect.iscoroutinefunction(self._on_message_callback):
                    reply = await self._on_message_callback(self.name, chat_id, text)
                else:
                    reply = await asyncio.to_thread(
                        self._on_message_callback, self.name, chat_id, text
                    )

                # Record brain reply in session store
                try:
                    if reply:
                        store.push(
                            user_id,
                            role="brain",
                            text=str(reply)[:300],
                            channel=self.name,
                            chat_id=chat_id,
                        )
                except Exception:
                    pass

                return reply
            except Exception as e:
                self.logger.error(f"Message handler error: {e}")
                return f"Error processing command: {e}"
        return None

    @abstractmethod
    async def start(self):
        """Connect to the messaging platform (login, start polling, etc.)."""
        pass

    @abstractmethod
    async def stop(self):
        """Disconnect gracefully."""
        pass

    @abstractmethod
    async def send_message(self, chat_id: str, text: str):
        """Send a text message to a specific chat/user."""
        pass

    async def send_message_with_retry(
        self,
        chat_id: str,
        text: str,
        max_retries: int = 3,
        base_delay_s: float = 1.0,
    ) -> bool:
        """Send a message with exponential-backoff retry on transient failures.

        Retries up to ``max_retries`` times with delays of ``base_delay_s``,
        ``base_delay_s * 2``, ``base_delay_s * 4``, … seconds.

        Args:
            chat_id:     Destination chat / user ID.
            text:        Message text.
            max_retries: Maximum number of retry attempts (default 3).
            base_delay_s: Initial retry delay in seconds (default 1.0).

        Returns:
            True if the message was sent successfully, False after all retries
            are exhausted.
        """
        delay = base_delay_s
        for attempt in range(1, max_retries + 2):
            try:
                await self.send_message(chat_id, text)
                return True
            except Exception as exc:
                if attempt > max_retries:
                    self.logger.error(
                        "[%s] send_message failed after %d retries to %s: %s",
                        self.name,
                        max_retries,
                        chat_id,
                        exc,
                    )
                    return False
                self.logger.warning(
                    "[%s] send_message attempt %d/%d failed (%s) — retrying in %.1fs",
                    self.name,
                    attempt,
                    max_retries,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)
