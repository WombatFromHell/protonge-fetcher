"""GitHub release fetcher implementation for ProtonFetcher."""

import logging
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

logger = logging.getLogger(__name__)


class GitHubReleaseFetcher(BaseReleaseFetcher):
    """Handles fetching and extracting GitHub release assets."""

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
    # Platform-specific implementations
    # ------------------------------------------------------------------

    def fetch_latest_tag(self, repo: str) -> str:
        """Get the latest release tag using GitHub's redirect-based approach."""
        return self.release_manager.fetch_latest_tag(repo)

    def find_asset_by_name(
        self, repo: str, tag: str, fork: ForkName = ForkName.GE_PROTON
    ) -> str | None:
        """Find the Proton asset in a GitHub release."""
        return self.release_manager.find_asset_by_name(repo, tag, fork)

    def get_remote_asset_size(self, repo: str, tag: str, asset_name: str) -> int:
        """Get the size of a remote asset using HEAD request."""
        return self.release_manager.get_remote_asset_size(repo, tag, asset_name)

    def list_recent_releases(self, repo: str) -> ReleaseTagsList:
        """Fetch and return a list of recent release tags from the GitHub API."""
        return self.release_manager.list_recent_releases(repo)

    def _build_download_url(self, repo: str, tag: str, asset_name: str) -> str:
        """Build a GitHub download URL."""
        return f"https://github.com/{repo}/releases/download/{tag}/{asset_name}"

    def _get_expected_directories(
        self, extract_dir: Path, release_tag: str, fork: ForkName
    ) -> DirectoryTuple:
        """Get expected unpack directories based on fork type."""
        unpacked = extract_dir / release_tag
        if fork == ForkName.PROTON_EM:
            unpacked_with_prefix = extract_dir / f"proton-{release_tag}"
            return unpacked, unpacked_with_prefix
        elif fork == ForkName.CACHYOS:
            unpacked_with_prefix = extract_dir / f"proton-{release_tag}-x86_64"
            return unpacked, unpacked_with_prefix
        else:
            return unpacked, None

    def _check_existing_directory(
        self,
        unpacked: Path,
        alternative: Path | None,
        fork: ForkName,
    ) -> ExistenceCheckResult:
        """Check if the unpacked directory already exists."""
        if fork == ForkName.PROTON_EM:
            if alternative and alternative.exists() and alternative.is_dir():
                return True, alternative
            if unpacked.exists() and unpacked.is_dir():
                return True, unpacked
            return False, None
        elif fork == ForkName.CACHYOS:
            if alternative and alternative.exists() and alternative.is_dir():
                return True, alternative
            if unpacked.exists() and unpacked.is_dir():
                return True, unpacked
            return False, None
        else:
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
        if unpacked.exists() and unpacked.is_dir():
            return unpacked

        # For Proton-EM, check with proton- prefix
        proton_em_path = extract_dir / f"proton-{release_tag}"
        if proton_em_path.exists() and proton_em_path.is_dir():
            return proton_em_path

        # For CachyOS, check with proton- prefix and -x86_64 suffix
        if fork == ForkName.CACHYOS:
            cachyos_path = extract_dir / f"proton-{release_tag}-x86_64"
            if cachyos_path.exists() and cachyos_path.is_dir():
                return cachyos_path

        return unpacked
