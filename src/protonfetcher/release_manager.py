"""Release manager implementation for ProtonFetcher."""

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from .common import (
    FORKS,
    GITHUB_URL_PATTERN,
    FileSystemClientProtocol,
    ForkName,
    NetworkClientProtocol,
    PlatformAdapter,
    ReleaseTagsList,
    VersionTuple,
)
from .exceptions import NetworkError
from .platform_adapters import github_adapter
from .utils import format_bytes, get_proton_asset_name, parse_version

logger = logging.getLogger(__name__)


class ReleaseManager:
    """Manages release discovery and selection."""

    def __init__(
        self,
        network_client: NetworkClientProtocol,
        file_system_client: FileSystemClientProtocol,
        timeout: int = 30,
        cache_enabled: bool = True,
        platform_adapter: PlatformAdapter | None = None,
    ) -> None:
        self.network_client = network_client
        self.file_system_client = file_system_client
        self.timeout = timeout
        self._cache_enabled = cache_enabled
        self.platform_adapter: PlatformAdapter = (
            platform_adapter if platform_adapter is not None else github_adapter
        )

        # Cache directory path (created lazily on first write)
        xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
        if xdg_cache_home:
            self._cache_dir = Path(xdg_cache_home) / "protonfetcher"
        else:
            self._cache_dir = Path.home() / ".cache" / "protonfetcher"

    def _extract_tag_from_url(self, url: str) -> str:
        """Extract tag name from a GitHub releases URL.

        Args:
            url: URL containing /releases/tag/{tag}

        Returns:
            Extracted tag name

        Raises:
            NetworkError: If tag cannot be extracted
        """
        match = re.search(GITHUB_URL_PATTERN, url)
        if not match:
            raise NetworkError(f"Could not determine latest tag from URL: {url}")
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
        url = self.platform_adapter.build_host_url(repo, "releases", "latest")
        try:
            response = self.network_client.head(url)
            if response.status >= 400:
                raise NetworkError(
                    f"Failed to fetch latest tag for {repo}: HTTP {response.status}"
                )
        except NetworkError as e:
            raise NetworkError(f"Failed to fetch latest tag for {repo}: {e}")

        tag = self._extract_tag_from_url(response.final_url)
        logger.debug(f"Found latest tag: {tag}")
        return tag

    def _get_cache_path(self, repo: str, tag: str, asset_name: str) -> Path:
        """Get the cache file path for a given asset.

        Args:
            repo: Repository in format 'owner/repo'
            tag: Release tag
            asset_name: Asset filename

        Returns:
            Path to the cache file
        """
        key_data = f"{repo}_{tag}_{asset_name}_size"
        cache_key = hashlib.md5(key_data.encode()).hexdigest()
        return self._cache_dir / cache_key

    def _is_cache_valid(self, cache_path: Path, max_age: int = 3600) -> bool:
        """Check if cached data is still valid (not expired)."""
        if not self.file_system_client.exists(cache_path):
            return False

        age = time.time() - self.file_system_client.mtime(cache_path)
        return age < max_age

    def _get_cached_asset_size(
        self, repo: str, tag: str, asset_name: str
    ) -> int | None:
        """Get cached asset size if available and not expired."""
        cache_path = self._get_cache_path(repo, tag, asset_name)

        if self._is_cache_valid(cache_path):
            try:
                cached_data_bytes = self.file_system_client.read(cache_path)
                cached_data = json.loads(cached_data_bytes.decode("utf-8"))
                size = cached_data.get("size")
                # Validate that size is an integer
                if isinstance(size, int):
                    return size
            except (json.JSONDecodeError, IOError):
                # If cache file is invalid, return None to force a fresh fetch
                pass
        return None

    def _cache_asset_size(
        self, repo: str, tag: str, asset_name: str, size: int
    ) -> None:
        """Cache the asset size."""
        cache_path = self._get_cache_path(repo, tag, asset_name)

        try:
            self.file_system_client.mkdir(self._cache_dir, parents=True, exist_ok=True)
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

    def _find_matching_assets(
        self, assets: list[dict[str, Any]], expected_extension: str
    ) -> list[dict[str, Any]]:
        """Find assets that match the expected extension."""
        return [
            asset
            for asset in assets
            if asset["name"].lower().endswith(expected_extension)
        ]

    def _handle_api_response(
        self,
        assets: list[dict[str, Any]],
        expected_extension: str,
        fork: ForkName | None = None,
        tag: str | None = None,
    ) -> str:
        """Handle the API response to find the appropriate asset.

        When multiple architecture variants exist, the x86_64 build is
        preferred (our supported architecture).
        """
        matching_assets = self._find_matching_assets(assets, expected_extension)

        if matching_assets:
            # When multiple architecture variants exist, prefer x86_64
            for asset in matching_assets:
                if "x86_64" in asset["name"]:
                    logger.debug(f"Found x86_64 asset via API: {asset['name']}")
                    return asset["name"]
            # Return the name of the first matching asset
            asset_name = matching_assets[0]["name"]
            logger.debug(f"Found asset via API: {asset_name}")
            return asset_name
        else:
            # If no matching extension assets found, use the first available asset as fallback
            if assets:
                asset_name = assets[0]["name"]
                logger.debug(
                    f"Found asset (non-matching extension) via API: {asset_name}"
                )
                return asset_name
            else:
                raise NetworkError("No assets found in release")

    def _try_api_approach(self, repo: str, tag: str, fork: ForkName) -> str:
        """Try to find the asset using the platform API."""
        api_url = self.platform_adapter.build_api_url(repo, "releases", "tags", tag)
        logger.debug(f"Fetching release info from API: {api_url}")

        headers = dict(self.platform_adapter.default_headers)
        response = self.network_client.get(api_url, headers=headers)
        if response.status >= 400:
            raise NetworkError(f"API request failed with status {response.status}")

        try:
            release_data: dict[str, Any] = json.loads(response.body)
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse JSON response: {e}")
            raise NetworkError(f"Failed to parse JSON: {e}")

        # Look for assets (attachments) in the release data
        if "assets" not in release_data:
            raise NetworkError("No assets found in release API response")

        assets: list[dict[str, Any]] = release_data["assets"]
        return self._handle_api_response(assets, FORKS[fork].archive_format, fork, tag)

    def _try_html_fallback(self, repo: str, tag: str, fork: ForkName) -> str:
        """Try to find the asset by HTML parsing if API fails."""
        # Generate the expected asset name using the appropriate naming convention
        expected_asset_name = get_proton_asset_name(tag, fork)
        url = self.platform_adapter.build_host_url(repo, "releases", "tag", tag)
        logger.info(f"Fetching release page: {url}")

        response = self.network_client.get(url)
        if response.status >= 400:
            raise NetworkError(
                f"Failed to fetch release page for {repo}/{tag}: HTTP {response.status}"
            )

        # Look for the expected asset name in the page
        if expected_asset_name in response.body:
            logger.info(f"Found asset: {expected_asset_name}")
            return expected_asset_name

        # Log a snippet of the HTML for debugging
        html_snippet = (
            response.body[:500] + "..." if len(response.body) > 500 else response.body
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

    def get_remote_asset_size(self, repo: str, tag: str, asset_name: str) -> int:
        """Get the size of a remote asset using HEAD request.

        Args:
            repo: Repository in format 'owner/repo'
            tag: Release tag
            asset_name: Asset filename

        Returns:
            Size of the asset in bytes

        Raises:
            NetworkError: If unable to get asset size
        """
        # Try cache first (skip when caching is disabled)
        if self._cache_enabled:
            cached_size = self._get_cached_asset_size(repo, tag, asset_name)
            if cached_size is not None:
                logger.debug(
                    f"Using cached size for {asset_name}: {format_bytes(cached_size)}"
                )
                return cached_size

        url = self.platform_adapter.build_download_url(repo, tag, asset_name)
        logger.debug(f"Getting remote asset size from: {url}")

        response = self.network_client.head(url)
        if response.status == 404:
            raise NetworkError(f"Remote asset not found: {asset_name}")
        if response.status >= 400:
            raise NetworkError(
                f"Failed to get remote asset size for {asset_name}: HTTP {response.status}"
            )

        size = self._parse_content_length(response.headers.get("content-length"))
        if not size:
            raise NetworkError(
                f"Could not determine size of remote asset: {asset_name}"
            )

        logger.debug(f"Remote asset size: {format_bytes(size)}")
        if self._cache_enabled:
            self._cache_asset_size(repo, tag, asset_name, size)
        return size

    @staticmethod
    def _parse_content_length(value: str | None) -> int | None:
        """Parse a content-length header value into a positive size."""
        if not value:
            return None
        try:
            size = int(value)
        except ValueError:
            return None
        return size if size > 0 else None

    def list_recent_releases(self, repo: str) -> ReleaseTagsList:
        """Fetch and return a list of recent release tags from the GitHub API.

        Args:
            repo: Repository in format 'owner/repo'

        Returns:
            List of the 20 most recent tag names

        Raises:
            FetchError: If unable to fetch or parse the releases
        """
        url = self.platform_adapter.build_api_url(repo, "releases")

        response = self.network_client.get(url)
        if response.status == 403:
            logger.error("API rate limit exceeded")
            raise NetworkError(
                "API rate limit exceeded. Please wait a few minutes before trying again."
            )
        if response.status >= 400:
            raise NetworkError(
                f"Failed to fetch releases for {repo}: HTTP {response.status}"
            )

        try:
            releases_data: list[dict[str, Any]] = json.loads(response.body)
        except json.JSONDecodeError as e:
            raise NetworkError(f"Failed to parse JSON response: {e}")

        # Extract tag_name from each release and limit to first 20
        tag_names: list[str] = []
        for release in releases_data:
            if "tag_name" in release:
                tag_names.append(release["tag_name"])

        return tag_names[:20]

    def check_for_newer_release(
        self, repo: str, current_versions: list[str], fork: ForkName
    ) -> str | None:
        """
        Check if a newer release is available than the currently installed versions.

        This method fetches the latest release tag from GitHub and compares it
        with the currently installed versions to determine if an update is available.

        Args:
            repo: Repository in format 'owner/repo'
            current_versions: List of currently installed version tags
            fork: The Proton fork name for version parsing

        Returns:
            Latest release tag if newer than installed versions, None otherwise
        """
        if not current_versions:
            # No versions installed, latest is "newer"
            return self.fetch_latest_tag(repo)

        # Fetch the latest tag
        latest_tag = self.fetch_latest_tag(repo)

        # parse_version returns a fallback tuple on non-match; it never raises.
        latest_version = parse_version(latest_tag, fork)

        # Parse all current versions and find the newest one
        current_parsed: list[tuple[VersionTuple, str]] = [
            (parse_version(tag, fork), tag) for tag in current_versions
        ]

        # Find the newest current version
        current_parsed.sort(key=lambda t: t[0], reverse=True)
        newest_current_version = current_parsed[0][0]

        # Compare: if latest > newest current, return latest
        if latest_version > newest_current_version:
            logger.debug(
                f"New release available: {latest_tag} (current: {current_parsed[0][1]})"
            )
            return latest_tag

        logger.debug(f"Already up-to-date: {latest_tag} <= {current_parsed[0][1]}")
        return None
