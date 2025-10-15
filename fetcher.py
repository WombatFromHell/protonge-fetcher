#!/usr/bin/env python3
"""
fetcher.py

Fetch and extract the latest ProtonGE GitHub release asset
"""

from __future__ import annotations

import argparse
import logging
import re
import time
import tarfile
import subprocess
from pathlib import Path
from typing import NoReturn

from typing import Iterator, Optional


class Spinner:
    """A simple native spinner progress indicator without external dependencies."""

    def __init__(
        self,
        iterable: Iterator | None = None,
        total: Optional[int] = None,
        desc: str = "",
        unit: str = "it",
        unit_scale: bool = False,
        disable: bool = False,
        **kwargs,
    ):
        self._iterable = iterable
        self.total = total
        self.desc = desc
        self.unit = unit
        self.unit_scale = unit_scale
        self.disable = disable
        self.current = 0
        self.spinner_chars = "|/-\\"
        self.spinner_idx = 0
        self.start_time = time.time()

    def __enter__(self):
        if not self.disable and self.desc:
            print(f"{self.desc}: ", end="", flush=True)
        return self

    def __exit__(self, *args):
        if not self.disable:
            print()  # New line at the end

    def update(self, n: int = 1) -> None:
        if self.disable:
            return

        self.current += n
        if self.total:
            # Show progress bar with percentage
            percent = self.current / self.total * 100
            bar_size = 20
            filled_size = (
                int(bar_size * self.current // self.total) if self.total > 0 else 0
            )
            bar = "=" * filled_size + " " * (bar_size - filled_size)
            elapsed = time.time() - self.start_time
            rate = self.current / elapsed if elapsed > 0 else 0

            # Format rate based on unit_scale
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

            print(
                f"\r{self.desc}: [{bar}] {percent:.1f}% ({rate_str})",
                end="",
                flush=True,
            )
        else:
            # Just show spinner
            spinner_char = self.spinner_chars[self.spinner_idx % 4]
            print(f"\r{self.desc}: {spinner_char}", end="", flush=True)
            self.spinner_idx += 1

    def close(self) -> None:
        if not self.disable:
            print()  # New line when closing

    def __iter__(self) -> Iterator:
        if self._iterable is not None:
            yield from self._iterable
        else:
            # When no iterable provided, yield nothing or a range if total is specified
            if self.total:
                for i in range(self.total):
                    yield i
                    self.update(1)


logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
GITHUB_URL_PATTERN = r"/releases/tag/([^/?#]+)"

# Constants for ProtonGE forks
FORKS = {
    "GE-Proton": {
        "repo": "GloriousEggroll/proton-ge-custom",
        "archive_format": ".tar.gz",
    },
    "Proton-EM": {"repo": "Etaash-mathamsetty/Proton", "archive_format": ".tar.xz"},
}
DEFAULT_FORK = "GE-Proton"


class FetchError(Exception):
    """Raised when fetching or extracting a release fails."""


def get_proton_asset_name(tag: str, fork: str = "GE-Proton") -> str:
    """
    Generate the expected Proton asset name from a tag and fork.

    Args:
        tag: The release tag (e.g., 'GE-Proton10-20' for GE-Proton, 'EM-10.0-30' for Proton-EM)
        fork: The fork name (default: 'GE-Proton')

    Returns:
        The expected asset name (e.g., 'GE-Proton10-20.tar.gz' or 'proton-EM-10.0-30.tar.xz')
    """
    if fork == "Proton-EM":
        # For Proton-EM, the asset name follows pattern: proton-<tag>.tar.xz
        # e.g., tag 'EM-10.0-30' becomes 'proton-EM-10.0-30.tar.xz'
        return f"proton-{tag}.tar.xz"
    else:
        # For GE-Proton, the asset name follows pattern: <tag>.tar.gz
        # e.g., tag 'GE-Proton10-20' becomes 'GE-Proton10-20.tar.gz'
        return f"{tag}.tar.gz"


class GitHubReleaseFetcher:
    """Handles fetching and extracting GitHub release assets."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    def _curl_get(
        self, url: str, headers: Optional[dict] = None, stream: bool = False
    ) -> subprocess.CompletedProcess:
        """Make a GET request using curl.

        Args:
            url: URL to make request to
            headers: Optional headers to include
            stream: Whether to stream the response

        Returns:
            CompletedProcess result from subprocess
        """
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

        return subprocess.run(cmd, capture_output=True, text=True)

    def _curl_head(
        self, url: str, headers: Optional[dict] = None, follow_redirects: bool = False
    ) -> subprocess.CompletedProcess:
        """Make a HEAD request using curl.

        Args:
            url: URL to make request to
            headers: Optional headers to include
            follow_redirects: Whether to follow redirects (useful for getting final content size)

        Returns:
            CompletedProcess result from subprocess
        """
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

        return subprocess.run(cmd, capture_output=True, text=True)

    def _curl_download(
        self, url: str, output_path: Path, headers: Optional[dict] = None
    ) -> subprocess.CompletedProcess:
        """Download a file using curl.

        Args:
            url: URL to download from
            output_path: Path to save the file
            headers: Optional headers to include

        Returns:
            CompletedProcess result from subprocess
        """
        cmd = [
            "curl",
            "-L",  # Follow redirects
            "-s",  # Silent mode (will show progress)
            "-S",  # Show errors
            "-f",  # Fail on HTTP error
            "--max-time",
            str(self.timeout),
            "-o",
            str(output_path),  # Output file
            "--progress-bar",  # Show progress bar
        ]

        if headers:
            for key, value in headers.items():
                cmd.extend(["-H", f"{key}: {value}"])

        cmd.append(url)

        return subprocess.run(cmd, capture_output=True, text=True)

    def fetch_latest_tag(self, repo: str) -> str:
        """Get the latest release tag by following the redirect from /releases/latest.

        Args:
            repo: Repository in format 'owner/repo'

        Returns:
            The latest release tag

        Raises:
            FetchError: If unable to determine the tag from the redirect
        """
        url = f"https://github.com/{repo}/releases/latest"
        try:
            response = self._curl_head(url)
            if response.returncode != 0:
                self._raise(f"Failed to fetch latest tag for {repo}: {response.stderr}")
        except Exception as e:
            self._raise(f"Failed to fetch latest tag for {repo}: {e}")

        # Parse the redirect URL from curl response headers
        location_match = re.search(
            r"Location: [^\r\n]*?(/releases/tag/[^/?#\r\n]+)",
            response.stdout,
            re.IGNORECASE,
        )
        if not location_match:
            # Try another pattern for the redirect - extract URL and then get path portion
            # Handle both "Location:" and "URL:" patterns that might appear in curl output
            url_match = re.search(
                r"URL:\s*(https?://[^\s\r\n]+)", response.stdout, re.IGNORECASE
            )
            if url_match:
                full_url = url_match.group(1).strip()
                # Extract the path portion from the full URL to match pattern
                import urllib.parse

                parsed_url = urllib.parse.urlparse(full_url)
                redirected_url = parsed_url.path
            else:
                # If no Location header found, use the original URL
                redirected_url = url
        else:
            redirected_url = location_match.group(1)

        match = re.search(GITHUB_URL_PATTERN, redirected_url)
        if not match:
            self._raise(f"Could not determine latest tag from URL: {redirected_url}")

        tag = match.group(1)
        logger.info(f"Found latest tag: {tag}")
        return tag

    def find_asset_by_name(self, repo: str, tag: str, fork: str = "GE-Proton") -> str:
        """Find the Proton asset in a GitHub release using the GitHub API first,
        falling back to HTML parsing if API fails.

        Args:
            repo: Repository in format 'owner/repo'
            tag: Release tag
            fork: The fork name to determine asset naming convention

        Returns:
            The asset name

        Raises:
            FetchError: If no matching asset is found
        """
        # First, try to use GitHub API (most reliable method)
        try:
            api_url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
            logger.info(f"Fetching release info from API: {api_url}")

            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "application/vnd.github.v3+json",
            }
            response = self._curl_get(api_url, headers=headers)
            if response.returncode != 0:
                logger.debug(f"API request failed: {response.stderr}")
                raise Exception(
                    f"API request failed with return code {response.returncode}"
                )

            # Import json to parse the API response
            import json

            try:
                release_data = json.loads(response.stdout)
            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse JSON response: {e}")
                raise Exception(f"Failed to parse JSON: {e}")

            # Look for assets (attachments) in the release data
            if "assets" not in release_data:
                raise Exception("No assets found in release API response")

            assets = release_data["assets"]

            # Determine the expected extension based on fork
            expected_extension = (
                FORKS[fork]["archive_format"] if fork in FORKS else ".tar.gz"
            )

            # Find assets with the expected extension
            matching_assets = [
                asset
                for asset in assets
                if asset["name"].lower().endswith(expected_extension)
            ]

            if matching_assets:
                # Return the name of the first matching asset
                asset_name = matching_assets[0]["name"]
                logger.info(f"Found asset via API: {asset_name}")
                return asset_name
            else:
                # If no matching extension assets found, use the first available asset as fallback
                if assets:
                    asset_name = assets[0]["name"]
                    logger.info(
                        f"Found asset (non-matching extension) via API: {asset_name}"
                    )
                    return asset_name
                else:
                    raise Exception("No assets found in release")

        except Exception as api_error:
            # If API approach fails, fall back to HTML parsing for backward compatibility
            logger.debug(
                f"API approach failed: {api_error}. Falling back to HTML parsing."
            )

            # Generate the expected asset name using the appropriate naming convention
            expected_asset_name = get_proton_asset_name(tag, fork)
            url = f"https://github.com/{repo}/releases/tag/{tag}"
            logger.info(f"Fetching release page: {url}")

            try:
                response = self._curl_get(url)
                if response.returncode != 0:
                    self._raise(
                        f"Failed to fetch release page for {repo}/{tag}: {response.stderr}"
                    )
            except Exception as e:
                self._raise(f"Failed to fetch release page for {repo}/{tag}: {e}")

            # Look for the expected asset name in the page
            if expected_asset_name in response.stdout:
                logger.info(f"Found asset: {expected_asset_name}")
                return expected_asset_name

            # Log a snippet of the HTML for debugging
            html_snippet = (
                response.stdout[:500] + "..."
                if len(response.stdout) > 500
                else response.stdout
            )
            logger.debug(f"HTML snippet: {html_snippet}")

            self._raise(f"Asset '{expected_asset_name}' not found in {repo}/{tag}")

    def get_remote_asset_size(self, repo: str, tag: str, asset_name: str) -> int:
        """Get the size of a remote asset using HEAD request.

        Args:
            repo: Repository in format 'owner/repo'
            tag: Release tag
            asset_name: Asset filename

        Returns:
            Size of the asset in bytes

        Raises:
            FetchError: If unable to get asset size
        """
        url = f"https://github.com/{repo}/releases/download/{tag}/{asset_name}"
        logger.info(f"Getting remote asset size from: {url}")

        try:
            # First try with HEAD request following redirects
            result = self._curl_head(url, follow_redirects=True)
            if result.returncode != 0:
                if "404" in result.stderr or "not found" in result.stderr.lower():
                    self._raise(f"Remote asset not found: {asset_name}")
                self._raise(
                    f"Failed to get remote asset size for {asset_name}: {result.stderr}"
                )

            # Extract Content-Length from headers - look for it in various formats
            # Split the response into lines and search each one for content-length
            for line in result.stdout.splitlines():
                # Look for content-length in the line, case insensitive
                if "content-length" in line.lower():
                    # Extract the numeric value after the colon
                    length_match = re.search(r":\s*(\d+)", line, re.IGNORECASE)
                    if length_match:
                        size = int(length_match.group(1))
                        if size > 0:  # Only return if size is greater than 0
                            logger.info(f"Remote asset size: {size} bytes")
                            return size

            # If not found in individual lines, try regex on full response
            content_length_match = re.search(
                r"(?i)content-length:\s*(\d+)", result.stdout
            )
            if content_length_match:
                size = int(content_length_match.group(1))
                if size > 0:  # Only return if size is greater than 0
                    logger.info(f"Remote asset size: {size} bytes")
                    return size

            # If content-length is not available or is 0, we'll try a different approach
            # by looking for redirect location and getting size from there
            location_match = re.search(r"(?i)location:\s*(.+)", result.stdout)
            if location_match:
                redirect_url = location_match.group(1).strip()
                if redirect_url and redirect_url != url:
                    logger.debug(f"Following redirect to: {redirect_url}")
                    # Make another HEAD request to the redirect URL
                    result = self._curl_head(redirect_url, follow_redirects=False)
                    if result.returncode == 0:
                        for line in result.stdout.splitlines():
                            if "content-length" in line.lower():
                                length_match = re.search(
                                    r":\s*(\d+)", line, re.IGNORECASE
                                )
                                if length_match:
                                    size = int(length_match.group(1))
                                    if size > 0:
                                        logger.info(f"Remote asset size: {size} bytes")
                                        return size
                        # Try regex on full response as backup
                        content_length_match = re.search(
                            r"(?i)content-length:\s*(\d+)", result.stdout
                        )
                        if content_length_match:
                            size = int(content_length_match.group(1))
                            if size > 0:
                                logger.info(f"Remote asset size: {size} bytes")
                                return size

            # If we still can't find the content-length, log the response for debugging
            logger.debug(f"Response headers received: {result.stdout}")
            self._raise(f"Could not determine size of remote asset: {asset_name}")
        except Exception as e:
            self._raise(f"Failed to get remote asset size for {asset_name}: {e}")

    def download_asset(
        self, repo: str, tag: str, asset_name: str, out_path: Path
    ) -> Path:
        """Download a specific asset from a GitHub release with progress bar.
        If a local file with the same name and size already exists, skip download.

        Args:
            repo: Repository in format 'owner/repo'
            tag: Release tag
            asset_name: Asset filename to download
            out_path: Path where the asset will be saved

        Returns:
            Path to the downloaded file

        Raises:
            FetchError: If download fails or asset not found
        """
        url = f"https://github.com/{repo}/releases/download/{tag}/{asset_name}"
        logger.info(f"Checking if asset needs download from: {url}")

        # Check if local file already exists and has the same size as remote
        if out_path.exists():
            local_size = out_path.stat().st_size
            remote_size = self.get_remote_asset_size(repo, tag, asset_name)

            if local_size == remote_size:
                logger.info(
                    f"Local asset {out_path} already exists with matching size ({local_size} bytes), skipping download"
                )
                return out_path
            else:
                logger.info(
                    f"Local size ({local_size} bytes) differs from remote size ({remote_size} bytes), downloading new version"
                )
        else:
            logger.info("Local asset does not exist, proceeding with download")

        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            result = self._curl_download(url, out_path)
            if result.returncode != 0:
                if "404" in result.stderr or "not found" in result.stderr.lower():
                    self._raise(f"Asset not found: {asset_name}")
                self._raise(f"Failed to download {asset_name}: {result.stderr}")
        except Exception as e:
            self._raise(f"Failed to download {asset_name}: {e}")

        logger.info(f"Downloaded asset to: {out_path}")
        return out_path

    def _ensure_xz_available(self) -> None:
        """Check if xz is available in the environment for .tar.xz extraction.

        Raises:
            FetchError: If xz is not found in PATH
        """
        import shutil

        if shutil.which("xz") is None:
            self._raise(
                "xz is not available in PATH. Please install xz-utils or equivalent for .tar.xz archive support."
            )

    def extract_xz_archive(self, archive_path: Path, target_dir: Path) -> None:
        """Extract tar.xz archive to the target directory using system tar command.

        Args:
            archive_path: Path to the tar.xz archive
            target_dir: Directory to extract into

        Raises:
            FetchError: If extraction fails
        """
        target_dir.mkdir(parents=True, exist_ok=True)

        # Check that xz is available before attempting extraction
        self._ensure_xz_available()

        try:
            cmd = [
                "tar",
                "-xJf",  # Extract .tar.xz
                str(archive_path),  # Archive file
                "-C",  # Extract to directory
                str(target_dir),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self._raise(
                    f"Failed to extract .tar.xz archive {archive_path}: {result.stderr}"
                )

            logger.info(f"Extracted {archive_path} to {target_dir}")
        except subprocess.CalledProcessError as e:
            self._raise(f"Failed to extract .tar.xz archive {archive_path}: {e}")

    def extract_archive(self, archive_path: Path, target_dir: Path) -> None:
        """Extract archive to the target directory with progress bar.
        Supports both .tar.gz and .tar.xz formats.

        Args:
            archive_path: Path to the archive
            target_dir: Directory to extract into

        Raises:
            FetchError: If extraction fails
        """
        if archive_path.suffix == ".xz":
            self.extract_xz_archive(archive_path, target_dir)
        else:
            # Original .tar.gz extraction
            target_dir.mkdir(parents=True, exist_ok=True)

            try:
                with tarfile.open(archive_path) as tar:
                    members = tar.getmembers()
                    # Wrap the list of members directly with spinner
                    spinner = Spinner(
                        iterable=iter(members),  # Convert list to iterator
                        desc=f"Extracting {archive_path.name}",
                        unit="file",
                        disable=False,  # Always show spinner since we implemented it natively
                        total=len(members),
                    )
                    for member in spinner:
                        tar.extract(member, path=target_dir, filter=tarfile.data_filter)

                logger.info(f"Extracted {archive_path} to {target_dir}")
            except (tarfile.TarError, EOFError) as e:
                self._raise(f"Failed to extract archive {archive_path}: {e}")

    def _manage_proton_links(
        self, extract_dir: Path, tag: str, fork: str = "GE-Proton"
    ) -> None:
        """Manage symbolic links for Proton forks after extraction.

        This method:
        1. For GE-Proton: Manages GE-Proton (latest), GE-Proton-Fallback, and GE-Proton-Fallback2
        2. For Proton-EM: Manages Proton-EM (latest), Proton-EM-Fallback, and Proton-EM-Fallback2
        3. Shifts links down the chain appropriately
        4. Creates new main link to the latest extracted version

        Args:
            extract_dir: Directory where the archive was extracted
            tag: The tag name of the release (e.g., 'GE-Proton10-20' or 'EM-10.0-30')
            fork: The ProtonGE fork name for appropriate link naming
        """
        # Define link names based on the fork
        if fork == "Proton-EM":
            main_link = extract_dir / "Proton-EM"
            fallback_link = extract_dir / "Proton-EM-Fallback"
            fallback2_link = extract_dir / "Proton-EM-Fallback2"
        else:  # Default to GE-Proton links
            main_link = extract_dir / "GE-Proton"
            fallback_link = extract_dir / "GE-Proton-Fallback"
            fallback2_link = extract_dir / "GE-Proton-Fallback2"

        # The extracted directory name is typically based on the archive name without extension
        # For example: proton-EM-10.0-30.tar.xz extracts to proton-EM-10.0-30/
        asset_name = get_proton_asset_name(tag, fork)
        # Remove the extension to get the directory name
        if asset_name.endswith(".tar.xz"):
            extracted_dir = extract_dir / asset_name[:-7]  # Remove '.tar.xz'
        elif asset_name.endswith(".tar.gz"):
            extracted_dir = extract_dir / asset_name[:-7]  # Remove '.tar.gz'
        else:
            # Fallback to tag name if the extension pattern doesn't match
            extracted_dir = extract_dir / tag

        # Verify that the extracted directory actually exists
        if not extracted_dir.exists() or not extracted_dir.is_dir():
            logger.warning(
                f"Expected extracted directory does not exist: {extracted_dir}"
            )
            # Fallback to finding any directory that matches the expected pattern
            for item in extract_dir.iterdir():
                if item.is_dir() and not item.is_symlink():
                    # Check if it matches either the tag or the archive-based directory name
                    if item.name == tag or item.name == extracted_dir.name:
                        extracted_dir = item
                        break
            else:
                logger.warning(
                    f"Could not find extracted directory matching the tag: {tag} or expected name: {extracted_dir.name}"
                )
                return

        # Check if main link exists and is a real directory (not a link)
        if main_link.exists() and main_link.is_dir() and not main_link.is_symlink():
            logger.info(f"{main_link.name} exists as a real directory, bailing early")
            return

        # Shift the fallback links down the chain:
        # Current fallback2 target should be removed
        # Current fallback becomes fallback2
        # Current main becomes fallback
        # New version becomes main

        # First, handle fallback2 (remove its target directory)
        if fallback2_link.exists() and fallback2_link.is_symlink():
            try:
                fallback2_target = fallback2_link.resolve()
                if fallback2_target.exists() and fallback2_target.is_dir():
                    import shutil

                    shutil.rmtree(fallback2_target)
                    logger.info(f"Removed old fallback2 directory: {fallback2_target}")
            except (FileNotFoundError, OSError) as e:
                logger.warning(f"Could not remove old fallback2 target: {e}")

        # Then move fallback to fallback2
        if fallback_link.exists():
            try:
                fallback_link.rename(fallback2_link)
                logger.info(f"Moved {fallback_link.name} to {fallback2_link.name}")
            except OSError as e:
                logger.warning(
                    f"Could not move {fallback_link.name} to {fallback2_link.name}: {e}"
                )
                # If we can't rename, try removing the old fallback2 and continuing
                if fallback2_link.exists():
                    try:
                        fallback2_link.unlink()
                    except OSError:
                        pass

        # Then move main to fallback
        if main_link.exists() and main_link.is_symlink():
            try:
                current_target = main_link.resolve()
                if current_target.exists():
                    # Move current main link to fallback
                    main_link.rename(fallback_link)
                    logger.info(
                        f"Moved old {main_link.name} link to {fallback_link.name}"
                    )
                else:
                    logger.warning(
                        f"{main_link.name} link points to non-existent target, removing it"
                    )
                    main_link.unlink()
            except (OSError, RuntimeError) as e:
                logger.warning(
                    f"Error resolving {main_link.name} link: {e}. Removing and recreating."
                )
                main_link.unlink()
        elif main_link.exists():
            # If it's not a symlink, it's a real directory, just remove it
            try:
                main_link.unlink()
            except OSError:
                import shutil

                shutil.rmtree(main_link)

        # Handle cases where fallback directories exist as real directories rather than links
        if (
            fallback_link.exists()
            and fallback_link.is_dir()
            and not fallback_link.is_symlink()
        ):
            import shutil

            shutil.rmtree(fallback_link)
            logger.info(f"Removed real directory {fallback_link.name} to create link")

        if (
            fallback2_link.exists()
            and fallback2_link.is_dir()
            and not fallback2_link.is_symlink()
        ):
            import shutil

            shutil.rmtree(fallback2_link)
            logger.info(f"Removed real directory {fallback2_link.name} to create link")

        # Validate that the target directory exists before creating the symlink
        if not extracted_dir.exists() or not extracted_dir.is_dir():
            logger.error(
                f"Target directory does not exist or is not a directory: {extracted_dir}"
            )
            return

        # Create new main link pointing to the extracted directory using relative path
        relative_target = None
        try:
            if main_link.exists():
                main_link.unlink()  # Remove any existing link/file first
            # Use relative path instead of absolute path for the symlink target
            relative_target = extracted_dir.relative_to(extract_dir)
            main_link.symlink_to(relative_target)
            logger.info(
                f"Created new {main_link.name} link pointing to {relative_target}"
            )
        except (OSError, RuntimeError) as e:
            logger.error(
                f"Failed to create symlink {main_link} -> {relative_target}: {e}"
            )

    def _ensure_directory_is_writable(self, path: Path) -> None:
        """Check if a directory is accessible and writable.

        Args:
            path: Directory path to check

        Raises:
            FetchError: If directory is not accessible or not writable
        """
        # Check if path exists and is not a directory first
        if path.exists() and not path.is_dir():
            self._raise(f"Path exists but is not a directory: {path}")

        # Create the directory if it doesn't exist
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            self._raise(f"Directory is not writable: {path}")

        # Check if path is a directory (should be after mkdir)
        if not path.is_dir():
            self._raise(f"Path exists but is not a directory: {path}")

        # Check if directory is writable
        try:
            # Try to create a temporary file to check write permissions
            import tempfile

            with tempfile.TemporaryFile(dir=path) as _:
                pass  # Just test that we can create a file
        except OSError:
            self._raise(f"Directory is not writable: {path}")

    def _ensure_curl_available(self) -> None:
        """Check if curl is available in the environment.

        Raises:
            FetchError: If curl is not found in PATH
        """
        import shutil

        if shutil.which("curl") is None:
            self._raise("curl is not available in PATH. Please install curl.")

    def fetch_and_extract(
        self,
        repo: str,
        output_dir: Path,
        extract_dir: Path,
        release_tag: Optional[str] = None,
        fork: str = "GE-Proton",
    ) -> Path:
        """Fetch the latest release asset and extract it to the target directory.

        Args:
            repo: Repository in format 'owner/repo'
            output_dir: Directory to download the asset to
            extract_dir: Directory to extract the asset to
            release_tag: Optional specific release tag to use instead of the latest
            fork: The ProtonGE fork name to determine asset naming

        Returns:
            Path to the extracted directory
        """
        # Early validation checks
        self._ensure_curl_available()
        self._ensure_directory_is_writable(output_dir)
        self._ensure_directory_is_writable(extract_dir)

        if release_tag:
            tag = release_tag
            logger.info(f"Using manually specified release tag: {tag}")
        else:
            tag = self.fetch_latest_tag(repo)
            logger.info(f"Fetching from {fork} ({repo}) tag {tag}")

        # Find the asset name based on the tag and fork
        try:
            asset_name = self.find_asset_by_name(repo, tag, fork)
            logger.info(f"Found asset: {asset_name}")
        except FetchError as e:
            if release_tag is not None:  # Explicit None check to satisfy type checker
                logger.error(
                    f"Failed to find asset for manually specified release tag '{release_tag}'. Please verify the tag exists and is correct."
                )
            raise e

        # Download to the output directory
        output_path = output_dir / asset_name
        try:
            self.download_asset(repo, tag, asset_name, output_path)
        except FetchError as e:
            if release_tag is not None:  # Explicit None check to satisfy type checker
                logger.error(
                    f"Failed to download asset for manually specified release tag '{release_tag}'. Please verify the tag exists and is correct."
                )
            raise e

        # Check if the unpacked proton version directory already exists for this release
        unpacked_dir = extract_dir / tag
        if unpacked_dir.exists() and unpacked_dir.is_dir():
            logger.info(
                f"Unpacked proton version directory already exists: {unpacked_dir}, bailing early"
            )
            return extract_dir

        # Extract to the extract directory
        self.extract_archive(output_path, extract_dir)

        # Manage symbolic links after successful extraction
        # Skip link management when manually specifying a release to prevent any link changes
        # This ensures that potentially older releases won't change an existing links
        if release_tag is None:
            # When fetching latest, manage links as normal
            self._manage_proton_links(extract_dir, tag, fork)
        else:
            # When manually specifying a release, always skip link management
            logger.info(
                f"Manual release specified ({release_tag}). Disengaging link management behavior to prevent changes to existing links."
            )

        return extract_dir

    @staticmethod
    def _raise(message: str) -> NoReturn:
        """Raise FetchError without logging."""
        raise FetchError(message)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch and extract the latest ProtonGE release asset."
    )
    parser.add_argument(
        "--extract-dir",
        "-x",
        default="~/.steam/steam/compatibilitytools.d/",
        help="Directory to extract the asset to (default: ~/.steam/steam/compatibilitytools.d/)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="~/Downloads/",
        help="Directory to download the asset to (default: ~/Downloads/)",
    )
    parser.add_argument(
        "--release",
        "-r",
        help="Manually specify a release tag (e.g., GE-Proton10-11) to download instead of the latest",
    )
    parser.add_argument(
        "--fork",
        "-f",
        default=DEFAULT_FORK,
        choices=list(FORKS.keys()),
        help=f"ProtonGE fork to download (default: {DEFAULT_FORK}, available: {', '.join(FORKS.keys())})",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Expand user home directory (~) in paths
    extract_dir = Path(args.extract_dir).expanduser()
    output_dir = Path(args.output).expanduser()

    # Set up logging
    log_level = logging.DEBUG if args.debug else logging.INFO

    # Configure logging but ensure it works with pytest caplog
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s",
    )

    # For pytest compatibility, also ensure the root logger has the right level
    logging.getLogger().setLevel(log_level)

    # Log if debug mode is enabled
    if args.debug:
        # Check if we're in a test environment (pytest would have certain characteristics)
        # If running test, log to make sure it's captured by caplog
        logger.debug("Debug logging enabled")

    # Get the repo based on selected fork
    repo = FORKS[args.fork]["repo"]
    logger.info(f"Using fork: {args.fork} ({repo})")

    try:
        fetcher = GitHubReleaseFetcher()
        fetcher.fetch_and_extract(
            repo, output_dir, extract_dir, release_tag=args.release, fork=args.fork
        )
        print("Success")
    except FetchError as e:
        print(f"Error: {e}")
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
