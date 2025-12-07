"""Network client implementation for ProtonFetcher."""

import subprocess
from pathlib import Path
from typing import Optional

from .common import Headers, ProcessResult


class NetworkClient:
    """Concrete implementation of network operations using subprocess and urllib."""

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def _build_curl_cmd(self, base_cmd: list[str]) -> list[str]:
        """Build a curl command with common performance options."""
        cmd = ["curl"] + base_cmd
        # Add common performance and reliability options
        cmd.extend(
            [
                "--http2",  # Use HTTP/2 for better performance
                "--compressed",  # Request compressed response
                "--max-time",
                str(self.timeout),
            ]
        )
        return cmd

    def get(
        self, url: str, headers: Optional[Headers] = None, stream: bool = False
    ) -> ProcessResult:
        base_cmd = [
            "-L",  # Follow redirects
            "-s",  # Silent mode
            "-S",  # Show errors
            "-f",  # Fail on HTTP error
        ]

        # Add headers if provided explicitly (not None)
        if headers is not None:
            for key, value in headers.items():
                base_cmd.extend(["-H", f"{key}: {value}"])
        # When headers is None (default), we don't add any headers for backward compatibility

        if stream:
            # For streaming, we'll handle differently
            pass

        base_cmd.append(url)
        cmd = self._build_curl_cmd(base_cmd)

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result

    def head(
        self,
        url: str,
        headers: Optional[Headers] = None,
        follow_redirects: bool = False,
    ) -> ProcessResult:
        base_cmd = [
            "-I",  # Header only
            "-s",  # Silent mode
            "-S",  # Show errors
            "-f",  # Fail on HTTP error
        ]

        if follow_redirects:
            base_cmd.insert(0, "-L")  # Follow redirects

        if headers:
            for key, value in headers.items():
                base_cmd.extend(["-H", f"{key}: {value}"])

        base_cmd.append(url)
        cmd = self._build_curl_cmd(base_cmd)

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result

    def download(
        self, url: str, output_path: Path, headers: Optional[Headers] = None
    ) -> ProcessResult:
        base_cmd = [
            "-L",  # Follow redirects
            "-s",  # Silent mode
            "-S",  # Show errors
            "-f",  # Fail on HTTP error
            "-o",
            str(output_path),  # Output file
        ]

        if headers:
            for key, value in headers.items():
                base_cmd.extend(["-H", f"{key}: {value}"])

        base_cmd.append(url)
        cmd = self._build_curl_cmd(base_cmd)

        result = subprocess.run(cmd, capture_output=True, text=True)
        return result
