"""Forgejo release fetcher implementation for ProtonFetcher.

Handles DW-Proton and other forks hosted on Forgejo instances.
Forgejo's API is Gitea-compatible and returns nearly identical JSON
structures to GitHub's API, but URL construction differs:

  - API base: /api/v1/repos/{owner}/{repo}/ (not /repos/{owner}/{repo}/)
  - No /releases/latest redirect; must use the API endpoint directly
  - Download URL: /{owner}/{repo}/releases/download/{tag}/{filename}
"""

import logging
import re
from pathlib import Path
from typing import Any, Optional

from .base_release_fetcher import BaseReleaseFetcher
from .common import (
    DEFAULT_TIMEOUT,
    DirectoryTuple,
    ExistenceCheckResult,
    FileSystemClientProtocol,
    ForkName,
    NetworkClientProtocol,
    ReleaseTagsList,
)
from .exceptions import NetworkError
from .utils import format_bytes, get_proton_asset_name

logger = logging.getLogger(__name__)


class ForgejoReleaseFetcher(BaseReleaseFetcher):
    """Handles fetching and extracting Forgejo release assets (e.g. DW-Proton)."""

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        network_client: Optional[NetworkClientProtocol] = None,
        file_system_client: Optional[FileSystemClientProtocol] = None,
        spinner_cls: Optional[Any] = None,
    ) -> None:
        super().__init__(
            timeout=timeout,
            network_client=network_client,
            file_system_client=file_system_client,
            spinner_cls=spinner_cls,
        )

    # ------------------------------------------------------------------
    # URL construction helpers
    # ------------------------------------------------------------------

    def _api_url(self, repo: str, *paths: str) -> str:
        """Build an API URL for the given repo."""
        owner, name = repo.split("/", 1)
        return f"https://dawn.wine/api/v1/repos/{owner}/{name}" + (
            "/" + "/".join(paths) if paths else ""
        )

    def _host_url(self, repo: str, *paths: str) -> str:
        """Build a web/download URL for the given repo."""
        owner, name = repo.split("/", 1)
        return f"https://dawn.wine/{owner}/{name}" + (
            "/" + "/".join(paths) if paths else ""
        )

    # ------------------------------------------------------------------
    # Platform-specific implementations
    # ------------------------------------------------------------------

    def fetch_latest_tag(self, repo: str) -> str:
        """Get the latest release tag using the Forgejo API."""
        url = self._api_url(repo, "releases", "latest")
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json",
        }
        try:
            response = self.network_client.get(url, headers=headers)
            if response.returncode != 0:
                raise NetworkError(
                    f"Failed to fetch latest tag for {repo}: {response.stderr}"
                )
        except Exception as e:
            raise NetworkError(f"Failed to fetch latest tag for {repo}: {e}")

        try:
            data: dict[str, Any] = __import__("json").loads(response.stdout)
        except __import__("json").JSONDecodeError as e:
            raise NetworkError(f"Failed to parse JSON response: {e}")

        tag = data.get("tag_name")
        if not tag:
            raise NetworkError(f"Could not determine latest tag from {url}")

        logger.debug(f"Found latest tag via Forgejo API: {tag}")
        return tag

    def find_asset_by_name(
        self, repo: str, tag: str, fork: ForkName = ForkName.DW_PROTON
    ) -> str | None:
        """Find the Proton asset in a Forgejo release.

        Tries the Forgejo API first, falls back to HTML parsing.
        """
        try:
            return self._try_forgejo_api(repo, tag, fork)
        except Exception as api_error:
            logger.debug(f"Forgejo API failed: {api_error}. Falling back to HTML.")
            try:
                return self._try_html_fallback(repo, tag, fork)
            except NetworkError as e:
                if "not found" in str(e).lower():
                    return None
                raise

    def _try_forgejo_api(self, repo: str, tag: str, fork: ForkName) -> str:
        """Find asset using the Forgejo API."""
        url = self._api_url(repo, "releases", "tags", tag)
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json",
        }
        logger.debug(f"Fetching release info from Forgejo API: {url}")

        response = self.network_client.get(url, headers=headers)
        if response.returncode != 0:
            raise NetworkError(f"API request failed: {response.stderr}")

        try:
            data: dict[str, Any] = __import__("json").loads(response.stdout)
        except __import__("json").JSONDecodeError as e:
            raise NetworkError(f"Failed to parse JSON: {e}")

        assets = data.get("assets")
        if not assets:
            raise Exception("No assets found in release API response")

        archive_format = ".tar.xz"
        for asset in assets:
            if asset["name"].lower().endswith(archive_format):
                logger.debug(f"Found asset via Forgejo API: {asset['name']}")
                return asset["name"]

        if assets:
            return assets[0]["name"]

        raise Exception("No assets found in release")

    def _try_html_fallback(self, repo: str, tag: str, fork: ForkName) -> str:
        """Find asset by HTML parsing if API fails."""
        expected_asset_name = get_proton_asset_name(tag, fork)
        url = self._host_url(repo, "releases", "tag", tag)
        logger.info(f"Fetching release page: {url}")

        response = self.network_client.get(url)
        if response.returncode != 0:
            raise NetworkError(
                f"Failed to fetch release page for {repo}/{tag}: {response.stderr}"
            )

        if expected_asset_name in response.stdout:
            logger.info(f"Found asset: {expected_asset_name}")
            return expected_asset_name

        raise NetworkError(f"Asset '{expected_asset_name}' not found in {repo}/{tag}")

    def get_remote_asset_size(self, repo: str, tag: str, asset_name: str) -> int:
        """Get the size of a remote asset using HEAD request."""
        url = self._host_url(repo, "releases", "download", tag, asset_name)
        logger.debug(f"Getting remote asset size from: {url}")

        result = self.network_client.head(url, follow_redirects=True)
        if result.returncode != 0:
            stderr = getattr(result, "stderr", "")
            if "404" in stderr or "not found" in stderr.lower():
                raise NetworkError(f"Remote asset not found: {asset_name}")
            raise NetworkError(
                f"Failed to get remote asset size for {asset_name}: {stderr}"
            )

        for line in result.stdout.splitlines():
            if "content-length" in line.lower():
                m = re.search(r":\s*(\d+)", line, re.IGNORECASE)
                if m:
                    size = int(m.group(1))
                    if size > 0:
                        logger.debug(f"Remote asset size: {format_bytes(size)}")
                        return size

        raise NetworkError(f"Could not determine size of remote asset: {asset_name}")

    def list_recent_releases(self, repo: str) -> ReleaseTagsList:
        """Fetch and return a list of recent release tags from the Forgejo API."""
        url = self._api_url(repo, "releases")
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json",
        }
        try:
            response = self.network_client.get(url, headers=headers)
            if response.returncode != 0:
                raise NetworkError(
                    f"Failed to fetch releases for {repo}: {response.stderr}"
                )
        except Exception as e:
            raise NetworkError(f"Failed to fetch releases for {repo}: {e}")

        try:
            releases: list[dict[str, Any]] = __import__("json").loads(response.stdout)
        except __import__("json").JSONDecodeError as e:
            raise NetworkError(f"Failed to parse JSON response: {e}")

        return [r["tag_name"] for r in releases if "tag_name" in r][:20]

    def _build_download_url(self, repo: str, tag: str, asset_name: str) -> str:
        """Build a Forgejo download URL."""
        return self._host_url(repo, "releases", "download", tag, asset_name)

    def _get_expected_directories(
        self, extract_dir: Path, release_tag: str, fork: ForkName
    ) -> DirectoryTuple:
        """Get expected unpack directories for DW-Proton."""
        unpacked = extract_dir / release_tag
        unpacked_with_suffix = extract_dir / f"{release_tag}-x86_64"
        return unpacked, unpacked_with_suffix

    def _check_existing_directory(
        self,
        unpacked: Path,
        alternative: Path | None,
        fork: ForkName,
    ) -> ExistenceCheckResult:
        """Check if the unpacked directory already exists."""
        if fork == ForkName.DW_PROTON:
            if alternative and alternative.exists() and alternative.is_dir():
                return True, alternative
            if unpacked.exists() and unpacked.is_dir():
                return True, unpacked
            return False, None
        if unpacked.exists() and unpacked.is_dir():
            return True, unpacked
        return False, None

    def _find_extracted_directory(
        self,
        extract_dir: Path,
        release_tag: str,
        fork: ForkName,
    ) -> Path:
        """Find the actual extracted directory after archive extraction."""
        unpacked = extract_dir / release_tag
        unpacked_with_suffix = extract_dir / f"{release_tag}-x86_64"

        if unpacked_with_suffix.exists() and unpacked_with_suffix.is_dir():
            return unpacked_with_suffix
        if unpacked.exists() and unpacked.is_dir():
            return unpacked

        return unpacked
