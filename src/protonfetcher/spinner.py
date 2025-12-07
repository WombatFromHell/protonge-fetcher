"""Spinner implementation for ProtonFetcher."""

import time
from typing import (
    Any,
    Iterator,
    Optional,
    Self,  # type: ignore
)


class Spinner:
    """A simple native spinner progress indicator without external dependencies."""

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
        show_progress: bool = False,  # New parameter to control progress display
        show_file_details: bool = False,  # New parameter to control file details display
        **kwargs: Any,
    ):
        self._iterable = iterable
        self.total = total
        self.desc = desc
        self.unit = unit
        self.unit_scale = unit_scale if unit_scale is not None else (unit == "B")
        self.disable = disable
        self.current = 0
        self.width = width
        self.show_progress = show_progress
        self.show_file_details = show_file_details

        # Keep your original braille spinner characters
        self.spinner_chars = "⠟⠯⠷⠾⠽⠻"
        self.spinner_idx = 0
        self.start_time = time.time()
        self.fps_limit = fps_limit
        self._last_update_time = 0.0
        self._current_line = ""
        self._completed = False  # Track if the spinner has completed

    def __enter__(self) -> Self:
        if not self.disable:
            # Display initial state if needed
            self._update_display()
        return self

    def __exit__(self, *args: object):
        if not self.disable:
            # Clear the line when exiting and add a newline to prevent clobbering
            print("\r" + " " * len(self._current_line) + "\r", end="")

    def _should_update_display(self, current_time: float) -> bool:
        """Check if display update should happen based on FPS limit."""
        if self.fps_limit is not None and self.fps_limit > 0:
            min_interval = 1.0 / self.fps_limit
            if current_time - self._last_update_time < min_interval:
                return False
        return True

    def _get_spinner_char(self) -> str:
        """Get the current spinner character and update the index."""
        spinner_char = self.spinner_chars[self.spinner_idx % len(self.spinner_chars)]
        self.spinner_idx += 1
        return spinner_char

    def _calculate_progress_percentage(self) -> float:
        """Calculate the progress percentage."""
        if self.total is None or self.total == 0:
            return 0.0
        return min(self.current / self.total, 1.0)  # Ensure percent doesn't exceed 1.0

    def _format_progress_bar(self, percent: float) -> str:
        """Format the progress bar based on the percentage."""
        filled_length = int(self.width * percent)
        bar = "█" * filled_length + "-" * (self.width - filled_length)
        return f" |{bar}| {percent * 100:.1f}%"

    def _format_rate_for_bytes_progress(self, rate: float) -> str:
        """Format the rate when unit is bytes and unit_scale is enabled for progress bar."""
        if rate <= 1024:
            return f"{rate:.2f}B/s"
        elif rate < 1024**2:
            return f"{rate / 1024:.2f}KB/s"
        else:
            return f"{rate / (1024**2):.2f}MB/s"  # Progress bar uses up to MB

    def _format_rate_for_bytes_spinner(self, rate: float) -> str:
        """Format the rate when unit is bytes and unit_scale is enabled for spinner mode."""
        if rate <= 1024:
            return f"{rate:.2f}B/s"
        elif rate < 1024**2:
            return f"{rate / 1024:.2f}KB/s"
        else:
            return f"{rate / (1024**3):.2f}GB/s"  # Spinner can go up to GB

    def _format_rate(self, current_time: float, mode: str = "progress") -> str:
        """Format the rate based on configuration.

        Args:
            current_time: Current time for calculating elapsed time
            mode: Either "progress" for progress bar mode or "spinner" for spinner-only mode
        """
        elapsed = current_time - self.start_time
        rate = self.current / elapsed if elapsed > 0 else 0

        if self.unit_scale and self.unit == "B":
            if mode == "progress":
                rate_str = self._format_rate_for_bytes_progress(rate)
            else:  # spinner mode
                rate_str = self._format_rate_for_bytes_spinner(rate)
        else:
            rate_str = f"{rate:.1f}{self.unit}/s"

        return f" ({rate_str})"

    def _build_progress_display(
        self, spinner_char: str, current_time: float
    ) -> list[str]:
        """Build display parts for progress bar mode."""
        display_parts = [self.desc, ":"]

        percent = self._calculate_progress_percentage()
        bar = self._format_progress_bar(percent)
        display_parts.append(f" {spinner_char} {bar}")

        # Add rate if unit is provided
        if self.unit:
            rate_str = self._format_rate(current_time, mode="progress")
            display_parts.append(rate_str)

        return display_parts

    def _build_spinner_display(
        self, spinner_char: str, current_time: float
    ) -> list[str]:
        """Build display parts for spinner-only mode."""
        display_parts = [self.desc, ":"]

        if self.unit:
            display_parts.append(f" {spinner_char} {self.current}{self.unit}")
        else:
            display_parts.append(f" {spinner_char}")

        # Add rate information if unit is provided (even if not showing progress bar)
        if self.unit:
            rate_str = self._format_rate(current_time, mode="spinner")
            display_parts.append(rate_str)

        return display_parts

    def _update_display(self) -> None:
        """Update the display immediately."""
        current_time = time.time()

        # Check if we should display based on FPS limit
        if not self._should_update_display(current_time):
            return

        self._last_update_time = current_time
        spinner_char = self._get_spinner_char()

        # Build the display string
        if self.total and self.total > 0 and self.show_progress:
            # Show progress bar when total is known
            display_parts = self._build_progress_display(spinner_char, current_time)
        else:
            # Just show spinner with current count
            display_parts = self._build_spinner_display(spinner_char, current_time)

        # Join all parts and print
        line = "".join(display_parts)
        self._current_line = line

        if not self.disable:
            print(f"\r{line}", end="", flush=True)

    def update(self, n: int = 1) -> None:
        """Update the spinner progress by n units."""
        self.current += n

        # Update display immediately (subject to FPS limit)
        if not self.disable:
            self._update_display()

    def update_progress(
        self, current: int, total: int, prefix: str = "", suffix: str = ""
    ) -> None:
        """Update the spinner with explicit progress values."""
        self.current = current
        self.total = total

        # Only update the description if it's not empty and not already containing "Extracting"
        if prefix and not self.desc.startswith("Extracting"):
            self.desc = prefix

        # Update display immediately (subject to FPS limit)
        if not self.disable:
            self._update_display()

    def close(self) -> None:
        """Stop the spinner and clean up."""
        if not self.disable:
            # Clear the line when closing and add a newline
            print("\r" + " " * len(self._current_line) + "\r", end="")
            print()

    def finish(self) -> None:
        """Mark the spinner as finished and update to 100%."""
        if not self._completed and self.total:
            self._completed = True
            self.current = self.total  # Ensure we reach 100%

            # Force a final update to show 100%
            if not self.disable:
                _ = time.time()
                spinner_char = self.spinner_chars[
                    self.spinner_idx % len(self.spinner_chars)
                ]

                # Build the display string with 100% progress
                display_parts = [self.desc, ":"]
                percent = 1.0
                filled_length = int(self.width * percent)
                bar = "█" * filled_length  # No dashes for 100%

                display_parts.append(f" {spinner_char} |{bar}| {percent * 100:.1f}%")

                if self.unit:
                    elapsed = time.time() - self.start_time
                    rate = self.current / elapsed if elapsed > 0 else 0

                    if self.unit_scale and self.unit == "B":
                        rate_str = (
                            f"{rate:.2f}B/s"
                            if rate <= 1024
                            else f"{rate / 1024:.2f}KB/s"
                            if rate < 1024**2
                            else f"{rate / 1024**2:.2f}MB/s"
                        )
                    else:
                        rate_str = f"{rate:.1f}{self.unit}/s"

                    display_parts.append(f" ({rate_str})")

                line = "".join(display_parts)
                print(f"\r{line}", end="", flush=True)
                self._current_line = line

                # Move to beginning of next line without adding extra blank line
                # print("\r", end="", flush=True)
                print()

    def __iter__(self) -> Iterator[Any]:
        if self._iterable is not None:
            for item in self._iterable:
                yield item
                self.update(1)
        else:
            # When no iterable provided, yield nothing or a range if total is specified
            if self.total:
                for i in range(self.total):
                    yield i
                    self.update(1)
