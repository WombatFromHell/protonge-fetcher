"""Base release fetcher abstract class for ProtonFetcher.

Defines the common interface and shared logic for GitHub and Forgejo release fetchers.
Concrete subclasses implement platform-specific methods.
"""

import logging
from pathlib import Path
from typing import Any

from .archive_extractor import ArchiveExtractor
from .asset_downloader import AssetDownloader
from .candidate_selection import select_top_3_candidates
from .common import (
    DEFAULT_TIMEOUT,
    FORKS,
    FileSystemClientProtocol,
    ForkName,
    NetworkClientProtocol,
    PlatformAdapter,
    ReleaseTagsList,
)
from .dirs import (
    get_link_names,
    resolve_directory,
    resolve_directory_candidates,
)
from .exceptions import LinkManagementError, ProtonFetcherError
from .filesystem import FileSystemClient
from .link_manager import LinkManager
from .network import NetworkClient
from .platform_adapters import forgejo_adapter, github_adapter
from .release_manager import ReleaseManager
from .utils import format_bytes

logger = logging.getLogger(__name__)


class BaseReleaseFetcher:
    """Base class for release fetchers.

    Provides shared infrastructure (directory management, symlink handling,
    extraction, download orchestration) and delegates all platform-specific
    behavior to `PlatformAdapter` instances.

    Subclasses are marker classes that only set the `platform` attribute:
        - GitHubReleaseFetcher: GitHub-hosted forks (GE-Proton, Proton-EM, CachyOS)
        - ForgejoReleaseFetcher: Forgejo-hosted forks (DW-Proton)
    """

    platform: str = "github"

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        network_client: NetworkClientProtocol | None = None,
        file_system_client: FileSystemClientProtocol | None = None,
    ) -> None:
        self.timeout = timeout
        self.network_client = network_client or NetworkClient(timeout=timeout)
        self.file_system_client = file_system_client or FileSystemClient()

        # Initialize the smaller, focused classes
        # Select platform adapter based on subclass platform attribute
        adapter: PlatformAdapter = (
            github_adapter if self.platform == "github" else forgejo_adapter
        )
        self.release_manager = ReleaseManager(
            self.network_client,
            self.file_system_client,
            timeout,
            platform_adapter=adapter,
        )
        self.asset_downloader = AssetDownloader(
            self.network_client, self.file_system_client, timeout
        )
        self.archive_extractor = ArchiveExtractor(self.file_system_client, timeout)
        self.link_manager = LinkManager(self.file_system_client, timeout)

    # ------------------------------------------------------------------
    # Shared infrastructure (identical across platforms)
    # ------------------------------------------------------------------

    def _ensure_directory_is_writable(self, directory: Path) -> None:
        """Ensure the directory exists and is writable, creating it if needed."""
        try:
            self.file_system_client.mkdir(directory, parents=True, exist_ok=True)
        except FileExistsError as e:
            raise ProtonFetcherError(
                f"{directory} exists but is not a directory"
            ) from e
        except OSError as e:
            raise ProtonFetcherError(
                f"Failed to create directory {directory}: {e}"
            ) from e

        try:
            test_file = directory / ".write_test"
            self.file_system_client.write(test_file, b"")
            self.file_system_client.unlink(test_file)
        except OSError as e:
            raise ProtonFetcherError(
                f"Directory {directory} is not writable: {e}"
            ) from e

    def _ensure_directories_writable(self, output_dir: Path, extract_dir: Path) -> None:
        """Validate directories are writable."""
        self._ensure_directory_is_writable(output_dir)
        self._ensure_directory_is_writable(extract_dir)

    def _handle_already_extracted(
        self,
        extract_dir: Path,
        tag: str,
        fork: ForkName,
        is_manual_release: bool,
    ) -> None:
        """Ensure symlinks are current for an already-extracted directory."""
        if self.link_manager.are_links_up_to_date(
            extract_dir, tag, fork, is_manual_release=is_manual_release
        ):
            logger.info("Symlinks are already up-to-date, skipping link management")
        else:
            self.link_manager.manage_proton_links(
                extract_dir, tag, fork, is_manual_release=is_manual_release
            )

    def relink_fork(
        self,
        extract_dir: Path,
        fork: ForkName = ForkName.GE_PROTON,
    ) -> bool:
        """Force recreation of symbolic links for a specific fork."""
        self._ensure_directory_is_writable(extract_dir)

        top_3 = select_top_3_candidates(
            extract_dir, fork, None, self.file_system_client
        )

        if not top_3:
            raise LinkManagementError(
                f"No valid {fork} versions found in {extract_dir} to relink"
            )

        main, fb1, fb2 = get_link_names(extract_dir, fork)
        logger.info(f"Relinking {fork} symlinks...")
        self.link_manager.create_symlinks(main, fb1, fb2, top_3)
        logger.info(f"Successfully relinked {fork} symlinks")
        return True

    def prune_releases(
        self,
        extract_dir: Path,
        fork: ForkName,
        keep: int = 3,
        dry_run: bool = False,
    ) -> tuple[list[str], list[str]]:
        """Remove old unmanaged Proton releases.

        Keeps all versions referenced by symlinks, plus the N newest unlinked versions."""
        return self.link_manager.prune_releases(extract_dir, fork, keep, dry_run)

    def list_links(
        self, extract_dir: Path, fork: ForkName = ForkName.GE_PROTON
    ) -> dict[str, str | None]:
        """List recognized symbolic links and their associated Proton fork folders."""
        return self.link_manager.list_links(extract_dir, fork)

    def remove_release(
        self, extract_dir: Path, tag: str, fork: ForkName = ForkName.GE_PROTON
    ) -> bool:
        """Remove a specific Proton fork release folder and its associated symbolic links."""
        return self.link_manager.remove_release(extract_dir, tag, fork)

    def update_all_managed_forks(
        self,
        output_dir: Path,
        extract_dir: Path,
        dry_run: bool = False,
    ) -> dict[ForkName, Path | None]:
        """Update all forks that have managed symbolic links."""
        if not dry_run:
            self._ensure_directories_writable(output_dir, extract_dir)

        results: dict[ForkName, Path | None] = {}
        first_fork = True

        for fork in FORKS.keys():
            if FORKS[fork].platform != self.platform:
                logger.debug(f"Skipping {fork}: platform mismatch")
                continue
            if not self.link_manager.has_managed_links(extract_dir, fork):
                logger.debug(f"Skipping {fork}: no managed links found")
                continue

            if not first_fork:
                print()
            first_fork = False

            logger.info(f"Updating {fork}: fetching latest release...")
            repo = FORKS[fork].repo

            try:
                result = self.fetch_and_extract(
                    repo,
                    output_dir,
                    extract_dir,
                    fork=fork,
                    dry_run=dry_run,
                )
                results[fork] = result
                logger.debug(f"Successfully updated {fork}")
            except ProtonFetcherError as e:
                logger.error(f"Failed to update {fork}: {e}")
                results[fork] = None
                continue

        if not results:
            logger.warning("No managed forks found to update")

        return results

    def check_for_updates(self, extract_dir: Path, fork: ForkName) -> str | None:
        """Check if a newer release is available for the specified fork."""
        installed_versions = self.link_manager.get_installed_versions(extract_dir, fork)
        repo = FORKS[fork].repo

        try:
            return self.release_manager.check_for_newer_release(
                repo, installed_versions, fork
            )
        except Exception as e:
            raise ProtonFetcherError(f"Failed to check for updates for {fork}: {e}")

    # ------------------------------------------------------------------
    # Platform-agnostic directory helpers (identical across platforms)
    # ------------------------------------------------------------------

    def _find_existing_release(
        self,
        extract_dir: Path,
        release_tag: str,
        fork: ForkName,
    ) -> Path | None:
        """Return the extracted directory if it already exists, else None.

        Tries fork directory-name templates in priority order (preferred first).
        """
        for candidate in resolve_directory_candidates(extract_dir, release_tag, fork):
            if candidate.exists() and candidate.is_dir():
                return candidate
        return None

    # ------------------------------------------------------------------
    # Platform-agnostic methods (delegated to ReleaseManager)
    # ------------------------------------------------------------------

    def fetch_latest_tag(self, repo: str) -> str:
        """Get the latest release tag for the given repo.

        Args:
            repo: Repository in format 'owner/repo'

        Returns:
            The latest release tag
        """
        return self.release_manager.fetch_latest_tag(repo)

    def find_asset_by_name(
        self, repo: str, tag: str, fork: ForkName = ForkName.GE_PROTON
    ) -> str | None:
        """Find the Proton asset in a release.

        Args:
            repo: Repository in format 'owner/repo'
            tag: Release tag
            fork: The fork name

        Returns:
            The asset name, or None if not found
        """
        return self.release_manager.find_asset_by_name(repo, tag, fork)

    def get_remote_asset_size(self, repo: str, tag: str, asset_name: str) -> int:
        """Get the size of a remote asset.

        Args:
            repo: Repository in format 'owner/repo'
            tag: Release tag
            asset_name: Asset filename

        Returns:
            Size in bytes
        """
        return self.release_manager.get_remote_asset_size(repo, tag, asset_name)

    def list_recent_releases(self, repo: str) -> ReleaseTagsList:
        """Fetch and return a list of recent release tags.

        Args:
            repo: Repository in format 'owner/repo'

        Returns:
            List of the 20 most recent tag names
        """
        return self.release_manager.list_recent_releases(repo)

    def _build_download_url(self, repo: str, tag: str, asset_name: str) -> str:
        """Build a download URL for an asset.

        Args:
            repo: Repository in format 'owner/repo'
            tag: Release tag
            asset_name: Asset filename

        Returns:
            Full download URL
        """
        return self.release_manager.platform_adapter.build_download_url(
            repo, tag, asset_name
        )

    # ------------------------------------------------------------------
    # Shared workflow methods
    # ------------------------------------------------------------------

    def _determine_release_tag(
        self, repo: str, release_tag: str | None = None, **kwargs: Any
    ) -> str:
        """Determine the release tag to use."""
        manual_release_tag = kwargs.get("manual_release_tag", release_tag)
        if manual_release_tag is None:
            return self.fetch_latest_tag(repo)
        return manual_release_tag

    def _resolve_asset(self, repo: str, release_tag: str, fork: ForkName) -> str:
        """Resolve the asset name for a release, raising if it cannot be found."""
        try:
            asset_name = self.find_asset_by_name(repo, release_tag, fork)
        except ProtonFetcherError as e:
            raise ProtonFetcherError(
                f"Could not find asset for release {release_tag} in {repo}: {e}"
            )
        if asset_name is None:
            raise ProtonFetcherError(
                f"Could not find asset for release {release_tag} in {repo}"
            )
        return asset_name

    def _download_asset(
        self, repo: str, release_tag: str, fork: ForkName, output_dir: Path
    ) -> Path:
        """Download the asset and return the archive path."""
        asset_name = self._resolve_asset(repo, release_tag, fork)

        archive_path = output_dir / asset_name
        download_url = self._build_download_url(repo, release_tag, asset_name)
        remote_size = self.release_manager.get_remote_asset_size(
            repo, release_tag, asset_name
        )
        self.asset_downloader.download_asset(
            repo,
            release_tag,
            asset_name,
            archive_path,
            download_url=download_url,
            remote_size=remote_size,
        )
        return archive_path

    def _dry_run_workflow(
        self,
        repo: str,
        output_dir: Path,
        extract_dir: Path,
        release_tag: str,
        fork: ForkName,
    ) -> None:
        """Execute dry-run workflow: show what would be done without making changes."""
        asset_name = self._resolve_asset(repo, release_tag, fork)

        try:
            remote_size = self.get_remote_asset_size(repo, release_tag, asset_name)
            size_str = f" ({format_bytes(remote_size)})"
        except Exception:
            size_str = ""

        download_url = self._build_download_url(repo, release_tag, asset_name)
        logger.info(f"Would download: {asset_name}{size_str}")
        logger.info(f"  URL: {download_url}")
        logger.info(f"  Destination: {output_dir / asset_name}")

        # Show what would be extracted
        unpacked = resolve_directory_candidates(extract_dir, release_tag, fork)[0]
        logger.info(f"Would extract to: {unpacked}")

        # Show what symlinks would be created
        top_3 = select_top_3_candidates(
            extract_dir, fork, unpacked, self.file_system_client
        )

        if top_3:
            main, fb1, fb2 = get_link_names(extract_dir, fork)
            logger.info("Would create/update symlinks:")
            if len(top_3) >= 1:
                logger.info(f"  {main.name} -> {top_3[0][1].name}")
            if len(top_3) >= 2:
                logger.info(f"  {fb1.name} -> {top_3[1][1].name}")
            if len(top_3) >= 3:
                logger.info(f"  {fb2.name} -> {top_3[2][1].name}")

        logger.info("Dry run complete - no changes made")
        return None

    def _extract_and_manage_links(
        self,
        archive_path: Path,
        extract_dir: Path,
        release_tag: str,
        fork: ForkName,
        is_manual_release: bool,
        show_progress: bool,
    ) -> Path:
        """Extract the archive and manage symbolic links."""
        self.archive_extractor.extract_archive(archive_path, extract_dir, show_progress)

        # Find where the archive extracted to
        unpacked = resolve_directory(
            extract_dir, release_tag, fork, self.file_system_client
        )

        # Manage symbolic links
        self.link_manager.manage_proton_links(
            extract_dir, release_tag, fork, is_manual_release=is_manual_release
        )

        return unpacked

    def fetch_and_extract(
        self,
        repo: str,
        output_dir: Path,
        extract_dir: Path,
        release_tag: str | None = None,
        fork: ForkName = ForkName.GE_PROTON,
        show_progress: bool = True,
        dry_run: bool = False,
    ) -> Path | None:
        """Fetch and extract a Proton release.

        Args:
            repo: Repository in format 'owner/repo'
            output_dir: Directory to download the asset to
            extract_dir: Directory to extract to
            release_tag: Release tag to fetch (if None, fetches latest)
            fork: The ProtonGE fork name
            show_progress: Whether to show the progress bar
            dry_run: If True, only show what would be done without making changes

        Returns:
            Path to the extract directory, or None in dry-run mode
        """

        if not dry_run:
            self._ensure_directories_writable(output_dir, extract_dir)

        is_manual_release = release_tag is not None
        release_tag = self._determine_release_tag(repo, release_tag)

        # Dry-run
        if dry_run:
            return self._dry_run_workflow(
                repo, output_dir, extract_dir, release_tag, fork
            )

        # Fast path: already extracted (templates in priority order)
        existing = self._find_existing_release(extract_dir, release_tag, fork)
        if existing is not None:
            logger.info(
                f"Unpacked directory already exists: {existing}, "
                "skipping download and extraction"
            )
            self._handle_already_extracted(
                extract_dir, release_tag, fork, is_manual_release
            )
            return existing

        # Download + extract
        archive_path = self._download_asset(repo, release_tag, fork, output_dir)
        return self._extract_and_manage_links(
            archive_path,
            extract_dir,
            release_tag,
            fork,
            is_manual_release,
            show_progress,
        )
