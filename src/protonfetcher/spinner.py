"""Spinner implementation for ProtonFetcher."""

import time
from typing import (
    Any,
    Iterator,
    Optional,
    Self,  # type: ignore
)


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
        """Initialize the spinner.

        Args:
            iterable: Optional iterable to wrap with progress indication
            total: Total number of items/units for progress calculation
            desc: Description text to display before the spinner
            unit: Unit of measurement (e.g., 'B' for bytes)
            unit_scale: Whether to scale units (KB, MB, GB) when unit is 'B'
            disable: Disable all display output
            fps_limit: Maximum frames per second for display updates
            width: Width of progress bar in characters
            show_progress: Show progress bar when total is known
        """
        self._iterable = iterable
        self.total = total
        self.desc = desc
        self.unit = unit
        self.unit_scale = unit_scale if unit_scale is not None else (unit == "B")
        self.disable = disable
        self.current = 0
        self.width = max(1, width)  # Ensure minimum width of 1
        self.show_progress = show_progress

        # Braille spinner characters for smooth animation
        self.spinner_chars = "⠟⠯⠷⠾⠽⠻"
        self.spinner_idx = 0
        self.start_time = time.time()
        self.fps_limit = fps_limit
        self._last_update_time = 0.0
        self._current_line = ""
        self._completed = False

    def __enter__(self) -> Self:
        """Enter context manager - display initial state."""
        if not self.disable:
            self._update_display()
        return self

    def __exit__(self, *args: object):
        """Exit context manager - clear display."""
        if not self.disable:
            self._clear_display()

    def _should_update_display(self, current_time: float) -> bool:
        """Check if display update should happen based on FPS limit.

        Args:
            current_time: Current timestamp

        Returns:
            True if display should be updated, False if FPS limit prevents update
        """
        if self.fps_limit is None or self.fps_limit <= 0:
            return True

        min_interval = 1.0 / self.fps_limit
        return current_time - self._last_update_time >= min_interval

    def _get_spinner_char(self) -> str:
        """Get the current spinner character and advance to next character.

        Returns:
            Current spinner character from the animation sequence
        """
        char = self.spinner_chars[self.spinner_idx % len(self.spinner_chars)]
        self.spinner_idx += 1
        return char

    def _calculate_progress_percentage(self) -> float:
        """Calculate current progress as percentage.

        Returns:
            Progress percentage (0.0 to 1.0)
        """
        if self.total is None or self.total <= 0:
            return 0.0
        return min(self.current / self.total, 1.0)

    def _format_progress_bar(self, percent: float) -> str:
        """Format progress bar visualization.

        Args:
            percent: Progress percentage (0.0 to 1.0)

        Returns:
            Formatted progress bar string
        """
        filled_length = int(self.width * percent)
        bar = "█" * filled_length + "-" * (self.width - filled_length)
        return f" |{bar}| {percent * 100:.1f}%"

    def _format_rate(self, current_time: float, mode: str = "progress") -> str:
        """Format data transfer rate.

        Args:
            current_time: Current timestamp for rate calculation
            mode: Formatting mode ('progress' or 'spinner')

        Returns:
            Formatted rate string with appropriate units
        """
        elapsed = current_time - self.start_time
        if elapsed <= 0:
            # When elapsed time is 0, return appropriate format based on unit
            if self.unit == "B" and self.unit_scale:
                return " (0.00B/s)"
            elif self.unit:
                return f" (0.0{self.unit}/s)"
            else:
                return " (0.0/s)"

        rate = self.current / elapsed

        if self.unit == "B" and self.unit_scale:
            return self._format_bytes_rate(rate, mode)
        elif self.unit:
            return f" ({rate:.1f}{self.unit}/s)"
        else:
            return ""

    def _format_bytes_rate(self, rate: float, mode: str = "progress") -> str:
        """Format byte rate with appropriate scale (B/s, KB/s, MB/s, GB/s).

        Args:
            rate: Rate in bytes per second
            mode: Formatting mode ('progress' or 'spinner')

        Returns:
            Formatted rate string
        """
        if rate <= 1024:
            return f" ({rate:.2f}B/s)"
        elif rate < 1024**2:
            return f" ({rate / 1024:.2f}KB/s)"
        elif mode == "progress":
            return f" ({rate / 1024**2:.2f}MB/s)"
        else:
            # Spinner mode: use GB/s for rates >= 1024^2
            return f" ({rate / 1024**3:.2f}GB/s)"

    def _build_display_parts(self, spinner_char: str, current_time: float) -> list[str]:
        """Build display components based on current state.

        Args:
            spinner_char: Current spinner character
            current_time: Current timestamp

        Returns:
            List of display components to join
        """
        display_parts = [self.desc, ":"]

        if self._should_show_progress():
            return self._build_progress_display(
                spinner_char, current_time, display_parts
            )
        else:
            return self._build_spinner_display(
                spinner_char, current_time, display_parts
            )

    def _should_show_progress(self) -> bool:
        """Determine if progress bar should be displayed.

        Returns:
            True if progress bar should be shown, False otherwise
        """
        return self.show_progress and self.total is not None and self.total > 0

    def _build_progress_display(
        self, spinner_char: str, current_time: float, display_parts: list[str]
    ) -> list[str]:
        """Build progress bar display components.

        Args:
            spinner_char: Current spinner character
            current_time: Current timestamp
            display_parts: Base display components

        Returns:
            Complete display components with progress bar
        """
        percent = self._calculate_progress_percentage()
        bar = self._format_progress_bar(percent)
        display_parts.append(f" {spinner_char} {bar}")

        if self.unit:
            display_parts.append(self._format_rate(current_time, "progress"))

        return display_parts

    def _build_spinner_display(
        self, spinner_char: str, current_time: float, display_parts: list[str]
    ) -> list[str]:
        """Build spinner-only display components.

        Args:
            spinner_char: Current spinner character
            current_time: Current timestamp
            display_parts: Base display components

        Returns:
            Complete display components with spinner
        """
        if self.unit:
            display_parts.append(f" {spinner_char} {self.current}{self.unit}")
        else:
            display_parts.append(f" {spinner_char}")

        if self.unit:
            display_parts.append(self._format_rate(current_time, "spinner"))

        return display_parts

    def _update_display(self) -> None:
        """Update the display with current state."""
        if self.disable:
            return

        current_time = time.time()

        if not self._should_update_display(current_time):
            return

        self._last_update_time = current_time
        spinner_char = self._get_spinner_char()
        display_parts = self._build_display_parts(spinner_char, current_time)

        line = "".join(display_parts)
        self._current_line = line

        print(f"\r{line}", end="", flush=True)

    def _clear_display(self) -> None:
        """Clear the current display line."""
        if self.disable:
            return

        print("\r" + " " * len(self._current_line) + "\r", end="")

    def update(self, n: int = 1) -> None:
        """Update progress by n units.

        Args:
            n: Number of units to advance progress
        """
        self.current += n
        self._update_display()

    def update_progress(
        self, current: int, total: int, prefix: str = "", suffix: str = ""
    ) -> None:
        """Update progress with explicit values.

        Args:
            current: Current progress value
            total: Total progress value
            prefix: Optional description prefix
            suffix: Optional description suffix (unused)
        """
        self.current = current
        self.total = total

        if prefix and not self.desc.startswith("Extracting"):
            self.desc = prefix

        self._update_display()

    def close(self) -> None:
        """Close the spinner and clear display."""
        self._clear_display()
        if not self.disable:
            print()

    def finish(self) -> None:
        """Complete the spinner and show final state."""
        if self._completed or not self.total:
            return

        self._completed = True
        self.current = self.total

        if self.disable:
            return

        current_time = time.time()
        spinner_char = self._get_spinner_char()

        # Build final display with 100% progress
        display_parts = [self.desc, ":"]

        percent = 1.0
        filled_length = int(self.width * percent)
        bar = "█" * filled_length
        display_parts.append(f" {spinner_char} |{bar}| {percent * 100:.1f}%")

        if self.unit:
            elapsed = current_time - self.start_time
            rate = self.current / elapsed if elapsed > 0 else 0
            display_parts.append(self._format_bytes_rate(rate, "progress"))

        line = "".join(display_parts)
        print(f"\r{line}", end="", flush=True)
        self._current_line = line
        print()

    def __iter__(self) -> Iterator[Any]:
        """Iterate through wrapped iterable with progress updates."""
        if self._iterable is not None:
            for item in self._iterable:
                yield item
                self.update(1)
        elif self.total:
            for i in range(self.total):
                yield i
                self.update(1)
