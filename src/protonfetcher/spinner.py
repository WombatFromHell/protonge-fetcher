"""Spinner implementation for ProtonFetcher."""

import time
from typing import (
    Self,
)

from .utils import format_rate as _format_bytes_rate

# ---------------------------------------------------------------------------
# Pure formatting functions — standalone, testable, no Spinner dependency
# ---------------------------------------------------------------------------

SPINNER_CHARS = "⠟⠯⠷⠾⠽⠻"


def format_progress_bar(percent: float, width: int) -> str:
    """Format a progress bar string.

    Args:
        percent: Progress percentage (0.0 to 1.0).
        width: Number of character slots for the bar.

    Returns:
        e.g. `` |██████----| 60.0% ``
    """
    filled = int(width * percent)
    return f" |{'█' * filled}{'-' * (width - filled)}| {percent * 100:.1f}%"


def format_rate(
    current: int,
    start_time: float,
    unit: str | None,
    unit_scale: bool,
    now: float,
) -> str:
    """Format a data-transfer rate string.

    Args:
        current: Current count (bytes, items, …).
        start_time: Spinner start timestamp.
        unit: Unit suffix (e.g. ``"B"``).
        unit_scale: Scale bytes to KB/MB/GB.
        now: Current timestamp (injected for testability).

    Returns:
        e.g. `` (1.23MB/s) `` or `` (0.0B/s) `` or ```` (empty).
    """
    elapsed = now - start_time
    if elapsed <= 0:
        if unit == "B" and unit_scale:
            return " (0.00B/s)"
        if unit:
            return f" (0.0{unit}/s)"
        return " (0.0/s)"

    rate = current / elapsed

    if unit == "B" and unit_scale:
        return f" ({_format_bytes_rate(rate)})"
    if unit:
        return f" ({rate:.1f}{unit}/s)"
    return ""


# ---------------------------------------------------------------------------
# Spinner class
# ---------------------------------------------------------------------------


class Spinner:
    """A simple native spinner progress indicator without external dependencies.

    This spinner provides progress indication with optional progress bars, rate
    calculations, and FPS limiting for smooth display updates.
    """

    def __init__(
        self,
        total: int | None = None,
        desc: str = "",
        unit: str | None = None,
        unit_scale: bool | None = None,
        disable: bool = False,
        fps_limit: float | None = None,
        width: int = 10,
        show_progress: bool = False,
    ):
        self.total = total
        self.desc = desc
        self.unit = unit
        self.unit_scale = unit_scale if unit_scale is not None else (unit == "B")
        self.disable = disable
        self.current = 0
        self.width = max(1, width)
        self.show_progress = show_progress

        self._spinner_idx = 0
        self.start_time = time.time()
        self.fps_limit = fps_limit
        self._last_update_time = 0.0
        self._current_line = ""
        self._completed = False

    def __enter__(self) -> Self:
        if not self.disable:
            self._update()
        return self

    def __exit__(self, *args: object) -> None:
        if self._completed:
            return  # finish() already printed the final line
        if not self.disable:
            self._clear()

    # -- internal helpers ---------------------------------------------------

    def _should_update(self, now: float) -> bool:
        if self.fps_limit is None or self.fps_limit <= 0:
            return True
        return now - self._last_update_time >= 1.0 / self.fps_limit

    def _next_char(self) -> str:
        ch = SPINNER_CHARS[self._spinner_idx % len(SPINNER_CHARS)]
        self._spinner_idx += 1
        return ch

    def _build_line(
        self, spinner_char: str, now: float, show_progress: bool | None = None
    ) -> str:
        """Build the full display string for one spinner frame."""
        if show_progress is None:
            show_progress = self.show_progress
        parts = [self.desc, ":"]
        if show_progress and self.total and self.total > 0:
            percent = min(self.current / self.total, 1.0)
            parts.append(f" {spinner_char} {format_progress_bar(percent, self.width)}")
            if self.unit:
                parts.append(
                    format_rate(
                        self.current, self.start_time, self.unit, self.unit_scale, now
                    )
                )
        else:
            parts.append(f" {spinner_char}")
            if self.unit:
                parts.append(f" {self.current}{self.unit}")
                parts.append(
                    format_rate(
                        self.current, self.start_time, self.unit, self.unit_scale, now
                    )
                )
        return "".join(parts)

    # -- public API --------------------------------------------------------

    def _update(self) -> None:
        """Redraw the spinner line (respects FPS limit and disable flag)."""
        if self.disable:
            return
        now = time.time()
        if not self._should_update(now):
            return
        self._last_update_time = now
        line = self._build_line(self._next_char(), now)
        self._current_line = line
        print(f"\r{line}", end="", flush=True)

    def _clear(self) -> None:
        print("\r" + " " * len(self._current_line) + "\r", end="")

    def update(self, n: int = 1) -> None:
        """Advance progress by *n* units."""
        self.current += n
        self._update()

    def finish(self) -> None:
        """Show 100 % progress and clear."""
        if self._completed or not self.total:
            return
        self._completed = True
        self.current = self.total
        if self.disable:
            return
        now = time.time()
        line = self._build_line(self._next_char(), now, True)
        print(f"\r{line}", end="", flush=True)
        self._current_line = line
        print()
