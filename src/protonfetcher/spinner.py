"""Spinner implementation for ProtonFetcher."""

import time
from typing import (
    Any,
    Iterator,
    Optional,
    Self,
)

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


def format_bytes_rate(rate: float) -> str:
    """Format a byte rate with appropriate SI prefix.

    Args:
        rate: Rate in bytes per second.

    Returns:
        e.g. `` (2.45MB/s) ``
    """
    if rate <= 1024:
        return f" ({rate:.2f}B/s)"
    elif rate < 1024**2:
        return f" ({rate / 1024:.2f}KB/s)"
    elif rate < 1024**3:
        return f" ({rate / 1024**2:.2f}MB/s)"
    else:
        return f" ({rate / 1024**3:.2f}GB/s)"


def format_rate(
    current: int,
    start_time: float,
    unit: Optional[str],
    unit_scale: bool,
    mode: str = "progress",
) -> str:
    """Format a data-transfer rate string.

    Args:
        current: Current count (bytes, items, …).
        start_time: Spinner start timestamp.
        unit: Unit suffix (e.g. ``"B"``).
        unit_scale: Scale bytes to KB/MB/GB.
        mode: ``"progress"`` for full bar display, ``"spinner"`` for compact.

    Returns:
        e.g. `` (1.23MB/s) `` or `` (0.0B/s) `` or ```` (empty).
    """
    elapsed = time.time() - start_time
    if elapsed <= 0:
        if unit == "B" and unit_scale:
            return " (0.00B/s)"
        if unit:
            return f" (0.0{unit}/s)"
        return " (0.0/s)"

    rate = current / elapsed

    if unit == "B" and unit_scale:
        return format_bytes_rate(rate)
    if unit:
        return f" ({rate:.1f}{unit}/s)"
    return ""


def build_display_line(
    desc: str,
    spinner_char: str,
    current: int,
    total: Optional[int],
    unit: Optional[str],
    unit_scale: bool,
    show_progress: bool,
    width: int,
    start_time: float,
) -> str:
    """Build the full display string for one spinner frame.

    Returns the string to print after ``\\r``.
    """
    parts = [desc, ":"]

    if show_progress and total and total > 0:
        percent = min(current / total, 1.0)
        parts.append(f" {spinner_char} {format_progress_bar(percent, width)}")
        if unit:
            parts.append(format_rate(current, start_time, unit, unit_scale, "progress"))
    else:
        parts.append(f" {spinner_char}")
        if unit:
            parts.append(f" {current}{unit}")
            parts.append(format_rate(current, start_time, unit, unit_scale, "spinner"))

    return "".join(parts)


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
        iterable: Optional[Iterator[Any]] = None,
        total: Optional[int] = None,
        desc: str = "",
        unit: Optional[str] = None,
        unit_scale: Optional[bool] = None,
        disable: bool = False,
        fps_limit: Optional[float] = None,
        width: int = 10,
        show_progress: bool = False,
    ):
        self._iterable = iterable
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
        if not self.disable:
            self._clear()

    # -- internal helpers ---------------------------------------------------

    def _calculate_progress_percentage(self) -> float:
        """Calculate current progress as percentage (kept for test compat)."""
        if self.total is None or self.total <= 0:
            return 0.0
        return min(self.current / self.total, 1.0)

    def _should_update(self, now: float) -> bool:
        if self.fps_limit is None or self.fps_limit <= 0:
            return True
        return now - self._last_update_time >= 1.0 / self.fps_limit

    def _next_char(self) -> str:
        ch = SPINNER_CHARS[self._spinner_idx % len(SPINNER_CHARS)]
        self._spinner_idx += 1
        return ch

    # -- public API --------------------------------------------------------

    def _update(self) -> None:
        """Redraw the spinner line (respects FPS limit and disable flag)."""
        if self.disable:
            return
        now = time.time()
        if not self._should_update(now):
            return
        self._last_update_time = now
        line = build_display_line(
            self.desc,
            self._next_char(),
            self.current,
            self.total,
            self.unit,
            self.unit_scale,
            self.show_progress,
            self.width,
            self.start_time,
        )
        self._current_line = line
        print(f"\r{line}", end="", flush=True)

    def _clear(self) -> None:
        print("\r" + " " * len(self._current_line) + "\r", end="")

    def update(self, n: int = 1) -> None:
        """Advance progress by *n* units."""
        self.current += n
        self._update()

    def update_progress(
        self, current: int, total: int, prefix: str = "", suffix: str = ""
    ) -> None:
        """Set explicit progress values."""
        self.current = current
        self.total = total
        if prefix and not self.desc.startswith("Extracting"):
            self.desc = prefix
        self._update()

    def close(self) -> None:
        """Clear the spinner and emit a trailing newline."""
        self._clear()
        if not self.disable:
            print()

    def finish(self) -> None:
        """Show 100 % progress and clear."""
        if self._completed or not self.total:
            return
        self._completed = True
        self.current = self.total
        if self.disable:
            return
        line = build_display_line(
            self.desc,
            self._next_char(),
            self.current,
            self.total,
            self.unit,
            self.unit_scale,
            True,
            self.width,
            self.start_time,
        )
        print(f"\r{line}", end="", flush=True)
        self._current_line = line
        print()

    def __iter__(self) -> Iterator[Any]:
        if self._iterable is not None:
            for item in self._iterable:
                yield item
                self.update(1)
        elif self.total:
            for i in range(self.total):
                yield i
                self.update(1)
