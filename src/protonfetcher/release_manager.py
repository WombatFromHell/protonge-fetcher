"""Release manager implementation for ProtonFetcher."""

import hashlib
import json
import logging
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

from .common import (
    FORKS,
    GITHUB_URL_PATTERN,
    FileSystemClientProtocol,
    ForkName,
    NetworkClientProtocol,
    ProcessResult,
    ReleaseTagsList,
)
from .exceptions import NetworkError
from .utils import get_proton_asset_name

logger = logging.getLogger(__name__)


class ReleaseManager:
    """Manages release discovery and selection."""

    def __init__(
        self,
        network_client: NetworkClientProtocol,
        file_system_client: FileSystemClientProtocol,
        timeout: int = 30,
    ) -> None:
        self.network_client = network_client
        self.file_system_client = file_system_client
        self.timeout = timeout

        # Initialize cache directory
        xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
        if xdg_cache_home:
            self._cache_dir = Path(xdg_cache_home) / "protonfetcher"
        else:
            self._cache_dir = Path.home() / ".cache" / "protonfetcher"

        # Create cache directory if it doesn't exist
        self.file_system_client.mkdir(self._cache_dir, parents=True, exist_ok=True)

    def _parse_redirect_location(self, response_stdout: str) -> Optional[str]:
        """Parse redirect URL from Location header in response.

        Args:
            response_stdout: stdout from the HEAD request

        Returns:
            Extracted redirect path if found, None otherwise
        """
        location_match = re.search(
            r"Location: [^\r\n]*?(/releases/tag/[^/?#\r\n]+)",
            response_stdout,
            re.IGNORECASE,
        )
        if location_match:
            return location_match.group(1)
        return None

    def _parse_redirect_url_fallback(
        self, response_stdout: str, original_url: str
    ) -> str:
        """Fallback URL parsing when Location header not found.

        Tries to extract URL from response and parse its path portion.

        Args:
            response_stdout: stdout from the HEAD request
            original_url: Original URL as fallback

        Returns:
            Extracted redirect path or original URL
        """
        url_match = re.search(
            r"URL:\s*(https?://[^\s\r\n]+)", response_stdout, re.IGNORECASE
        )
        if url_match:
            full_url = url_match.group(1).strip()
            parsed_url = urllib.parse.urlparse(full_url)
            return parsed_url.path
        return original_url

    def _extract_redirected_url(self, response_stdout: str, original_url: str) -> str:
        """Extract the redirected URL from response headers.

        Args:
            response_stdout: stdout from the HEAD request
            original_url: Original URL as fallback

        Returns:
            Redirected URL path or original URL
        """
        redirected_url = self._parse_redirect_location(response_stdout)
        if redirected_url is None:
            return self._parse_redirect_url_fallback(response_stdout, original_url)
        return redirected_url

    def _extract_tag_from_url(self, url_path: str) -> str:
        """Extract tag name from GitHub releases URL path.

        Args:
            url_path: URL path containing /releases/tag/{tag}

        Returns:
            Extracted tag name

        Raises:
            NetworkError: If tag cannot be extracted
        """
        match = re.search(GITHUB_URL_PATTERN, url_path)
        if not match:
            raise NetworkError(f"Could not determine latest tag from URL: {url_path}")
        return match.group(1)

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
            response = self.network_client.head(url)
            if response.returncode != 0:
                raise NetworkError(
                    f"Failed to fetch latest tag for {repo}: {response.stderr}"
                )
        except Exception as e:
            raise NetworkError(f"Failed to fetch latest tag for {repo}: {e}")

        # Extract redirected URL from response
        redirected_url = self._extract_redirected_url(response.stdout, url)

        # Extract tag from URL
        tag = self._extract_tag_from_url(redirected_url)
        logger.info(f"Found latest tag: {tag}")
        return tag

    def _get_cache_key(self, repo: str, tag: str, asset_name: str) -> str:
        """Generate a cache key for the given asset."""
        key_data = f"{repo}_{tag}_{asset_name}_size"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the cache file path for a given key."""
        return self._cache_dir / cache_key

    def _is_cache_valid(self, cache_path: Path, max_age: int = 3600) -> bool:
        """Check if cached data is still valid (not expired)."""
        if not self.file_system_client.exists(cache_path):
            return False

        age = time.time() - self.file_system_client.mtime(cache_path)
        return age < max_age

    def _get_cached_asset_size(
        self, repo: str, tag: str, asset_name: str
    ) -> Optional[int]:
        """Get cached asset size if available and not expired."""
        cache_key = self._get_cache_key(repo, tag, asset_name)
        cache_path = self._get_cache_path(cache_key)

        if self._is_cache_valid(cache_path):
            try:
                cached_data_bytes = self.file_system_client.read(cache_path)
                cached_data = json.loads(cached_data_bytes.decode("utf-8"))
                size = cached_data.get("size")
                # Validate that size is an integer
                if isinstance(size, int):
                    return size
            except (json.JSONDecodeError, KeyError, IOError):
                # If cache file is invalid, return None to force a fresh fetch
                pass
        return None

    def _cache_asset_size(
        self, repo: str, tag: str, asset_name: str, size: int
    ) -> None:
        """Cache the asset size."""
        cache_key = self._get_cache_key(repo, tag, asset_name)
        cache_path = self._get_cache_path(cache_key)

        try:
            cache_data = {
                "size": size,
                "timestamp": time.time(),
                "repo": repo,
                "tag": tag,
                "asset_name": asset_name,
            }
            cache_data_bytes = json.dumps(cache_data).encode("utf-8")
            self.file_system_client.write(cache_path, cache_data_bytes)
        except IOError as e:
            logger.debug(f"Failed to write to cache: {e}")

    def _get_expected_extension(self, fork: ForkName | str) -> str:
        """Get the expected archive extension based on the fork."""
        # Convert string to ForkName if necessary, then check if it's valid
        if isinstance(fork, str):
            try:
                fork = ForkName(fork)
            except ValueError:
                # Invalid fork string, return default extension
                return ".tar.gz"
        return FORKS[fork].archive_format if fork in FORKS else ".tar.gz"

    def _find_matching_assets(
        self, assets: list[dict[str, Any]], expected_extension: str
    ) -> list[dict[str, Any]]:
        """Find assets that match the expected extension."""
        return [
            asset
            for asset in assets
            if asset["name"].lower().endswith(expected_extension)
        ]

    def _find_asset_for_cachyos(
        self, assets: list[dict[str, Any]], tag: str
    ) -> Optional[str]:
        """Find the x86_64 asset for CachyOS releases.

        CachyOS releases have multiple architecture variants (arm64, x86_64, x86_64_v2, etc.).
        This method specifically looks for the x86_64 variant.

        Args:
            assets: List of asset dictionaries from GitHub API
            tag: Release tag (e.g., 'cachyos-10.0-20260207-slr')

        Returns:
            Asset name if found, None otherwise
        """
        # Generate the expected asset name for x86_64 architecture
        expected_name = f"proton-{tag}-x86_64.tar.xz"

        for asset in assets:
            if asset["name"] == expected_name:
                return asset["name"]

        return None

    def _handle_api_response(
        self,
        assets: list[dict[str, Any]],
        expected_extension: str,
        fork: Optional[ForkName] = None,
        tag: Optional[str] = None,
    ) -> str:
        """Handle the API response to find the appropriate asset."""
        # For CachyOS, specifically look for the x86_64 asset
        if fork == ForkName.CACHYOS and tag is not None:
            cachyos_asset = self._find_asset_for_cachyos(assets, tag)
            if cachyos_asset:
                logger.info(f"Found CachyOS x86_64 asset via API: {cachyos_asset}")
                return cachyos_asset

        matching_assets = self._find_matching_assets(assets, expected_extension)

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

    def _try_api_approach(self, repo: str, tag: str, fork: ForkName) -> str:
        """Try to find the asset using the GitHub API."""
        api_url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
        logger.info(f"Fetching release info from API: {api_url}")

        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/vnd.github.v3+json",
        }
        response = self.network_client.get(api_url, headers=headers)
        if response.returncode != 0:
            logger.debug(f"API request failed: {response.stderr}")
            raise Exception(
                f"API request failed with return code {response.returncode}"
            )

        try:
            release_data: dict[str, Any] = json.loads(response.stdout)
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse JSON response: {e}")
            raise Exception(f"Failed to parse JSON: {e}")

        # Look for assets (attachments) in the release data
        if "assets" not in release_data:
            raise Exception("No assets found in release API response")

        assets: list[dict[str, Any]] = release_data["assets"]
        expected_extension = self._get_expected_extension(fork)
        return self._handle_api_response(assets, expected_extension, fork, tag)

    def _try_html_fallback(self, repo: str, tag: str, fork: ForkName) -> str:
        """Try to find the asset by HTML parsing if API fails."""
        # Generate the expected asset name using the appropriate naming convention
        expected_asset_name = get_proton_asset_name(tag, fork)
        url = f"https://github.com/{repo}/releases/tag/{tag}"
        logger.info(f"Fetching release page: {url}")

        try:
            response = self.network_client.get(url)
            if response.returncode != 0:
                raise NetworkError(
                    f"Failed to fetch release page for {repo}/{tag}: {response.stderr}"
                )
        except Exception as e:
            raise NetworkError(f"Failed to fetch release page for {repo}/{tag}: {e}")

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

        raise NetworkError(f"Asset '{expected_asset_name}' not found in {repo}/{tag}")

    def find_asset_by_name(
        self, repo: str, tag: str, fork: ForkName = ForkName.GE_PROTON
    ) -> str | None:
        """Find the Proton asset in a GitHub release using the GitHub API first,
        falling back to HTML parsing if API fails.

        Args:
            repo: Repository in format 'owner/repo'
            tag: Release tag
            fork: The fork name to determine asset naming convention

        Returns:
            The asset name, or None if no matching asset is found

        Raises:
            FetchError: If an error occurs during the fetch process
        """
        # First, try to use GitHub API (most reliable method)
        try:
            return self._try_api_approach(repo, tag, fork)
        except Exception as api_error:
            # If API approach fails, fall back to HTML parsing for backward compatibility
            logger.debug(
                f"API approach failed: {api_error}. Falling back to HTML parsing."
            )
            try:
                return self._try_html_fallback(repo, tag, fork)
            except NetworkError as e:
                # Check if this is specifically a "not found" error vs other network errors
                if "not found" in str(e).lower():
                    # If the asset is not found, return None
                    logger.debug(f"Asset not found for {repo}/{tag}, returning None")
                    return None
                else:
                    # If it's a different network error (connection, timeout, etc.), re-raise it
                    raise e
            except Exception as fallback_error:
                # Re-raise other errors
                raise fallback_error

    def _check_for_error_in_response(
        self, result: ProcessResult, asset_name: str
    ) -> None:
        """Check if the response contains an error (404, not found, etc.) and raise exception if found."""
        stdout_content = getattr(result, "stdout", "")
        stderr_content = getattr(result, "stderr", "")

        if isinstance(stdout_content, str) and (
            "404" in stdout_content or "not found" in stdout_content.lower()
        ):
            raise NetworkError(f"Remote asset not found: {asset_name}")
        if isinstance(stderr_content, str) and (
            "404" in stderr_content or "not found" in stderr_content.lower()
        ):
            raise NetworkError(f"Remote asset not found: {asset_name}")

    def _extract_size_from_response(self, response_text: str) -> Optional[int]:
        """Extract content-length from response headers.

        Args:
            response_text: Response text from the HEAD request

        Returns:
            Size in bytes if found and greater than 0, otherwise None
        """
        # Split the response into lines and search each one for content-length
        for line in response_text.splitlines():
            # Look for content-length in the line, case insensitive
            if "content-length" in line.lower():
                # Extract the numeric value after the colon
                length_match = re.search(r":\s*(\d+)", line, re.IGNORECASE)
                if length_match:
                    size = int(length_match.group(1))
                    if size > 0:  # Only return if size is greater than 0
                        return size

        # If not found in individual lines, try regex on full response
        content_length_match = re.search(r"(?i)content-length:\s*(\d+)", response_text)
        if content_length_match:
            size = int(content_length_match.group(1))
            if size > 0:  # Only return if size is greater than 0
                return size
        return None

    def _follow_redirect_and_get_size(
        self,
        initial_result: ProcessResult,
        url: str,
        repo: str,
        tag: str,
        asset_name: str,
        in_test: bool,
    ) -> Optional[int]:
        """Follow redirect if present in the response and attempt to get the content size from the redirected URL.

        Args:
            initial_result: The initial HEAD request response
            url: Original URL that was requested
            repo: Repository in format 'owner/repo'
            tag: Release tag
            asset_name: Asset filename
            in_test: Whether we are in a test environment

        Returns:
            Size in bytes if found and greater than 0, otherwise None
        """
        location_match = re.search(r"(?i)location:\s*(.+)", initial_result.stdout)
        if location_match:
            redirect_url = location_match.group(1).strip()
            if redirect_url and redirect_url != url:
                logger.debug(f"Following redirect to: {redirect_url}")
                # Make another HEAD request to the redirect URL
                result = self.network_client.head(redirect_url, follow_redirects=False)
                if result.returncode == 0:
                    # Check for 404 or similar errors in redirect response too
                    self._check_for_error_in_response(result, asset_name)

                    size = self._extract_size_from_response(result.stdout)
                    if size:
                        logger.info(f"Remote asset size: {size} bytes")
                        # Cache the result for future use (if not testing)
                        if not in_test:
                            self._cache_asset_size(repo, tag, asset_name, size)
                        return size
        return None

    def _is_in_test(self) -> bool:
        """Check if running in a test environment."""
        return "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ

    def _try_get_cached_size(
        self, repo: str, tag: str, asset_name: str
    ) -> Optional[int]:
        """Try to get cached asset size.

        Returns:
            Cached size if available and not in test mode, None otherwise
        """
        if self._is_in_test():
            return None

        cached_size = self._get_cached_asset_size(repo, tag, asset_name)
        if cached_size is not None:
            logger.debug(f"Using cached size for {asset_name}: {cached_size} bytes")
            return cached_size
        return None

    def _fetch_size_with_head_request(self, url: str, asset_name: str) -> ProcessResult:
        """Execute HEAD request to fetch asset size.

        Raises:
            NetworkError: If the request fails
        """
        result = self.network_client.head(url, follow_redirects=True)
        if result.returncode != 0:
            stderr_content = getattr(result, "stderr", "")
            if isinstance(stderr_content, str) and (
                "404" in stderr_content or "not found" in stderr_content.lower()
            ):
                raise NetworkError(f"Remote asset not found: {asset_name}")
            raise NetworkError(
                f"Failed to get remote asset size for {asset_name}: {stderr_content}"
            )

        # Check for 404 or similar errors even if returncode is 0
        self._check_for_error_in_response(result, asset_name)
        return result

    def _extract_and_cache_size(
        self,
        result: ProcessResult,
        url: str,
        repo: str,
        tag: str,
        asset_name: str,
    ) -> Optional[int]:
        """Extract size from response and cache it.

        Returns:
            Size in bytes if found, None otherwise
        """
        size = self._extract_size_from_response(result.stdout)
        if size:
            logger.info(f"Remote asset size: {size} bytes")
            if not self._is_in_test():
                self._cache_asset_size(repo, tag, asset_name, size)
            return size

        # If content-length not available, try following redirects
        size = self._follow_redirect_and_get_size(
            result, url, repo, tag, asset_name, self._is_in_test()
        )
        return size

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
        # Try cache first
        cached_size = self._try_get_cached_size(repo, tag, asset_name)
        if cached_size is not None:
            return cached_size

        url = f"https://github.com/{repo}/releases/download/{tag}/{asset_name}"
        logger.info(f"Getting remote asset size from: {url}")

        try:
            # Fetch size with HEAD request
            result = self._fetch_size_with_head_request(url, asset_name)

            # Extract and cache size
            size = self._extract_and_cache_size(result, url, repo, tag, asset_name)
            if size:
                return size

            # If we still can't find the content-length, log the response for debugging
            logger.debug(f"Response headers received: {result.stdout}")
            raise NetworkError(
                f"Could not determine size of remote asset: {asset_name}"
            )
        except Exception as e:
            raise NetworkError(f"Failed to get remote asset size for {asset_name}: {e}")

    def list_recent_releases(self, repo: str) -> ReleaseTagsList:
        """Fetch and return a list of recent release tags from the GitHub API.

        Args:
            repo: Repository in format 'owner/repo'

        Returns:
            List of the 20 most recent tag names

        Raises:
            FetchError: If unable to fetch or parse the releases
        """
        url = f"https://api.github.com/repos/{repo}/releases"

        try:
            response = self.network_client.get(url)
            if response.returncode != 0:
                # Check if it's a rate limit error (HTTP 403) or contains rate limit message
                if "403" in response.stderr or "rate limit" in response.stderr.lower():
                    raise NetworkError(
                        "API rate limit exceeded. Please wait a few minutes before trying again."
                    )
                raise NetworkError(
                    f"Failed to fetch releases for {repo}: {response.stderr}"
                )
        except Exception as e:
            raise NetworkError(f"Failed to fetch releases for {repo}: {e}")

        # Check for rate limiting in stdout as well
        if "rate limit" in response.stdout.lower():
            raise NetworkError(
                "API rate limit exceeded. Please wait a few minutes before trying again."
            )

        try:
            releases_data: list[dict[str, Any]] = json.loads(response.stdout)
        except json.JSONDecodeError as e:
            raise NetworkError(f"Failed to parse JSON response: {e}")

        # Extract tag_name from each release and limit to first 20
        tag_names: list[str] = []
        for release in releases_data:
            if "tag_name" in release:
                tag_names.append(release["tag_name"])

        return tag_names[:20]
