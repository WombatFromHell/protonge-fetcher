"""Network client implementation for ProtonFetcher."""

import subprocess
from pathlib import Path
from typing import Optional

from .common import Headers, ProcessResult


class NetworkClient:
    """Concrete implementation of network operations using subprocess and urllib."""

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def get(
        self, url: str, headers: Optional[Headers] = None, stream: bool = False
    ) -> ProcessResult:
        cmd = [
            "curl",
            "-L",  # Follow redirects
            "-s",  # Silent mode
            "-S",  # Show errors
            "-f",  # Fail on HTTP error
            "--max-time",
            str(self.timeout),
        ]

        # Add headers if provided explicitly (not None)
        if headers is not None:
            for key, value in headers.items():
                cmd.extend(["-H", f"{key}: {value}"])
        # When headers is None (default), we don't add any headers for backward compatibility

        if stream:
            # For streaming, we'll handle differently
            pass

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result

    def head(
        self,
        url: str,
        headers: Optional[Headers] = None,
        follow_redirects: bool = False,
    ) -> ProcessResult:
        cmd = [
            "curl",
            "-I",  # Header only
            "-s",  # Silent mode
            "-S",  # Show errors
            "-f",  # Fail on HTTP error
            "--max-time",
            str(self.timeout),
        ]

        if follow_redirects:
            cmd.insert(1, "-L")  # Follow redirects

        if headers:
            for key, value in headers.items():
                cmd.extend(["-H", f"{key}: {value}"])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result

    def download(
        self, url: str, output_path: Path, headers: Optional[Headers] = None
    ) -> ProcessResult:
        cmd = [
            "curl",
            "-L",  # Follow redirects
            "-s",  # Silent mode
            "-S",  # Show errors
            "-f",  # Fail on HTTP error
            "--max-time",
            str(self.timeout),
            "-o",
            str(output_path),  # Output file
        ]

        if headers:
            for key, value in headers.items():
                cmd.extend(["-H", f"{key}: {value}"])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result
