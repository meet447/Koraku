"""Split OpenAI-style text deltas into Bud/Anthropic-shaped thinking + visible text streams.

Models are instructed (see ``THINKING_BLOCK_INSTRUCTION``) to wrap scratch reasoning in
``<koraku_thinking>...</koraku_thinking>`` so we can emit ``thinking_delta`` events while
streaming; visible answer and tool JSON live after the closing tag.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

OPEN_TAG = "<koraku_thinking>"
CLOSE_TAG = "</koraku_thinking>"

THINKING_BLOCK_INSTRUCTION = (
    "\n\n## Private reasoning (required for streaming)\n"
    "Use **at most one** block per assistant turn, before any user-visible text or tool JSON:\n"
    f"{OPEN_TAG}\n"
    "Your step-by-step plans, caveats, and tool-choice reasoning here (can be several lines).\n"
    f"{CLOSE_TAG}\n"
    "After that closing tag, write **only** the user-facing answer and/or tool call JSON. "
    "Never put `<koraku_thinking>` tags in the user-visible part, and do not repeat the scratch prose outside the block.\n"
)


StreamKind = Literal[
    "thinking_block_start",
    "thinking_delta",
    "thinking_block_stop",
    "text_block_start",
    "text_delta",
]


@dataclass
class TaggedStreamParser:
    """Incremental parser: OpenAI ``content`` chunks → ordered stream kinds + text payloads."""

    mode: Literal["detect", "think", "text"] = "detect"
    buf: str = ""
    thinking_emitted: bool = False
    text_block_started: bool = False
    max_detect_hold: int = field(default=96)
    #: Second+ ``<koraku_thinking>`` blocks (model echo) — consume but do not emit thinking SSE.
    suppress_thinking_output: bool = False

    def _emit_text(self, out: list[tuple[StreamKind, str]], s: str) -> None:
        if not s:
            return
        if not self.text_block_started:
            out.append(("text_block_start", ""))
            self.text_block_started = True
        out.append(("text_delta", s))

    def feed(self, chunk: str) -> list[tuple[StreamKind, str]]:
        """Returns (kind, text) where *text* is delta payload (may be empty for structural kinds)."""
        if not chunk:
            return []
        self.buf += chunk
        out: list[tuple[StreamKind, str]] = []

        while True:
            if self.mode == "detect":
                if not self.buf:
                    break
                p = self.buf.find(OPEN_TAG)
                if p >= 0:
                    if p > 0:
                        self._emit_text(out, self.buf[:p])
                    self.buf = self.buf[p + len(OPEN_TAG) :]
                    out.append(("thinking_block_start", ""))
                    self.thinking_emitted = True
                    self.mode = "think"
                    continue

                if not self.buf.startswith("<"):
                    self._emit_text(out, self.buf)
                    self.buf = ""
                    self.mode = "text"
                    break

                if len(self.buf) < len(OPEN_TAG):
                    if OPEN_TAG.startswith(self.buf):
                        break
                    self._emit_text(out, self.buf)
                    self.buf = ""
                    self.mode = "text"
                    break

                if self.buf.startswith(OPEN_TAG):
                    continue

                if OPEN_TAG.startswith(self.buf[: len(OPEN_TAG)]):
                    if len(self.buf) > self.max_detect_hold:
                        self._emit_text(out, self.buf)
                        self.buf = ""
                        self.mode = "text"
                    break

                self._emit_text(out, self.buf)
                self.buf = ""
                self.mode = "text"
                break

            if self.mode == "think":
                if not self.buf:
                    break
                cpos = self.buf.find(CLOSE_TAG)
                if cpos >= 0:
                    before = self.buf[:cpos]
                    if before and not self.suppress_thinking_output:
                        out.append(("thinking_delta", before))
                    if not self.suppress_thinking_output:
                        out.append(("thinking_block_stop", ""))
                    self.buf = self.buf[cpos + len(CLOSE_TAG) :]
                    self.mode = "text"
                    self.suppress_thinking_output = False
                    continue

                hold = len(CLOSE_TAG) - 1
                if len(self.buf) > hold:
                    emit_len = len(self.buf) - hold
                    piece = self.buf[:emit_len]
                    self.buf = self.buf[emit_len:]
                    if piece and not self.suppress_thinking_output:
                        out.append(("thinking_delta", piece))
                break

            if self.mode == "text":
                if not self.buf:
                    break
                p = self.buf.find(OPEN_TAG)
                if p >= 0:
                    if p > 0:
                        self._emit_text(out, self.buf[:p])
                    self.buf = self.buf[p + len(OPEN_TAG) :]
                    if self.thinking_emitted:
                        self.suppress_thinking_output = True
                    else:
                        out.append(("thinking_block_start", ""))
                        self.thinking_emitted = True
                    self.mode = "think"
                    continue
                self._emit_text(out, self.buf)
                self.buf = ""
                break

        return out

    def flush_eof(self) -> list[tuple[StreamKind, str]]:
        """At end of HTTP stream: flush held buffer."""
        out: list[tuple[StreamKind, str]] = []
        if self.mode == "detect" and self.buf:
            self._emit_text(out, self.buf)
            self.buf = ""
            self.mode = "text"
        elif self.mode == "think" and self.buf:
            if not self.suppress_thinking_output:
                out.append(("thinking_delta", self.buf))
                out.append(("thinking_block_stop", ""))
            self.buf = ""
            self.suppress_thinking_output = False
            self.mode = "text"
        return out
