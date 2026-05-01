"""Base release fetcher abstract class for ProtonFetcher.

Defines the common interface and shared logic for GitHub and Forgejo release fetchers.
Concrete subclasses implement platform-specific methods.
"""

import logging
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from .archive_extractor import ArchiveExtractor
from .asset_downloader import AssetDownloader
from .common import (
    DEFAULT_TIMEOUT,
    DirectoryTuple,
    ExistenceCheckResult,
    FileSystemClientProtocol,
    ForkName,
    NetworkClientProtocol,
    ProcessingResult,
    ReleaseTagsList,
)
from .exceptions import LinkManagementError, NetworkError, ProtonFetcherError
from .filesystem import FileSystemClient
from .link_manager import LinkManager
from .network import NetworkClient
from .release_manager import ReleaseManager
from .utils import format_bytes, parse_version

logger = logging.getLogger(__name__)


class BaseReleaseFetcher(ABC):
    """Abstract base class for release fetchers.

    Provides shared infrastructure (directory management, symlink handling,
    extraction, download orchestration) while delegating platform-specific
    behavior (URL construction, API calls) to subclasses.

    Concrete subclasses:
        - GitHubReleaseFetcher: GitHub-hosted forks (GE-Proton, Proton-EM, CachyOS)
        - ForgejoReleaseFetcher: Forgejo-hosted forks (DW-Proton)
    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        network_client: Optional[NetworkClientProtocol] = None,
        file_system_client: Optional[FileSystemClientProtocol] = None,
        spinner_cls: Optional[Any] = None,
    ) -> None:
        self.timeout = timeout
        self.network_client = network_client or NetworkClient(timeout=timeout)
        self.file_system_client = file_system_client or FileSystemClient()

        # Initialize the smaller, focused classes
        self.release_manager = ReleaseManager(
            self.network_client, self.file_system_client, timeout
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
        """Ensure that the directory exists and is writable."""
        try:
            if not self.file_system_client.exists(directory):
                try:
                    self.file_system_client.mkdir(
                        directory, parents=True, exist_ok=True
                    )
                except OSError as e:
                    raise ProtonFetcherError(
                        f"Failed to create directory {directory}: {e}"
                    )

            if not self.file_system_client.exists(directory):
                raise ProtonFetcherError(
                    f"Directory does not exist and could not be created: {directory}"
                )

            if not self.file_system_client.is_dir(directory):
                raise LinkManagementError(f"{directory} exists but is not a directory")

            test_file = directory / ".write_test"
            try:
                self.file_system_client.write(test_file, b"")
                self.file_system_client.unlink(test_file)
            except (OSError, AttributeError) as e:
                raise LinkManagementError(f"Directory {directory} is not writable: {e}")
        except PermissionError as e:
            raise ProtonFetcherError(f"Failed to create {directory}: {str(e)}")
        except Exception as e:
            raise ProtonFetcherError(f"Failed to create {directory}: {e}")

    def _validate_environment(self) -> None:
        """Validate that required tools and directories are available."""
        if shutil.which("curl") is None:
            raise NetworkError("curl is not available")

    def _ensure_directories_writable(self, output_dir: Path, extract_dir: Path) -> None:
        """Validate directories are writable."""
        self._ensure_directory_is_writable(output_dir)
        self._ensure_directory_is_writable(extract_dir)

    def _handle_existing_directory(
        self,
        extract_dir: Path,
        release_tag: str,
        fork: ForkName,
        actual_directory: Path,
        is_manual_release: bool,
    ) -> ProcessingResult:
        """Handle case where directory already exists and return whether to skip further processing."""
        if not self.file_system_client.exists(actual_directory):
            return False, None

        logger.info(
            f"Unpacked directory already exists: {actual_directory}, skipping download and extraction"
        )

        if self.link_manager.are_links_up_to_date(
            extract_dir, release_tag, fork, is_manual_release=is_manual_release
        ):
            logger.info("Symlinks are already up-to-date, skipping link management")
            return True, actual_directory

        self.link_manager.manage_proton_links(
            extract_dir, release_tag, fork, is_manual_release=is_manual_release
        )
        return True, actual_directory

    def _check_post_download_directory(
        self,
        extract_dir: Path,
        release_tag: str,
        fork: ForkName,
        is_manual_release: bool,
    ) -> ProcessingResult:
        """Check if unpacked directory exists after download, and handle if it does."""
        unpacked = extract_dir / release_tag
        if unpacked.exists() and unpacked.is_dir():
            logger.info(
                f"Unpacked directory exists after download: {unpacked}, skipping extraction"
            )

            if self.link_manager.are_links_up_to_date(
                extract_dir, release_tag, fork, is_manual_release=is_manual_release
            ):
                logger.info("Symlinks are already up-to-date, skipping link management")
                return True, unpacked

            self.link_manager.manage_proton_links(
                extract_dir, release_tag, fork, is_manual_release=is_manual_release
            )
            return True, unpacked
        return False, extract_dir

    def relink_fork(
        self,
        extract_dir: Path,
        fork: ForkName = ForkName.GE_PROTON,
    ) -> bool:
        """Force recreation of symbolic links for a specific fork."""
        self._ensure_directory_is_writable(extract_dir)

        candidates = self.link_manager.find_version_candidates(extract_dir, fork)

        if not candidates:
            raise LinkManagementError(
                f"No valid {fork} versions found in {extract_dir} to relink"
            )

        candidates = self.link_manager._deduplicate_candidates(candidates)
        candidates.sort(key=lambda t: t[0], reverse=True)
        top_3 = candidates[:3]

        if not top_3:
            raise LinkManagementError(
                f"No valid {fork} versions found in {extract_dir} to relink"
            )

        main, fb1, fb2 = self.link_manager.get_link_names_for_fork(extract_dir, fork)
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
        """Remove old unmanaged Proton releases, keeping the N newest versions."""
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
        from .common import FORKS

        self._validate_environment()

        if not dry_run:
            self._ensure_directories_writable(output_dir, extract_dir)

        results: dict[ForkName, Path | None] = {}
        first_fork = True

        for fork in FORKS.keys():
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
        from .common import FORKS

        installed_versions = self.link_manager.get_installed_versions(extract_dir, fork)
        repo = FORKS[fork].repo

        try:
            return self.release_manager.check_for_newer_release(
                repo, installed_versions, fork
            )
        except Exception as e:
            raise ProtonFetcherError(f"Failed to check for updates for {fork}: {e}")

    # ------------------------------------------------------------------
    # Platform-specific abstract methods (must be implemented by subclasses)
    # ------------------------------------------------------------------

    @abstractmethod
    def fetch_latest_tag(self, repo: str) -> str:
        """Get the latest release tag for the given repo.

        Args:
            repo: Repository in format 'owner/repo'

        Returns:
            The latest release tag
        """
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    def get_remote_asset_size(self, repo: str, tag: str, asset_name: str) -> int:
        """Get the size of a remote asset.

        Args:
            repo: Repository in format 'owner/repo'
            tag: Release tag
            asset_name: Asset filename

        Returns:
            Size in bytes
        """
        ...

    @abstractmethod
    def list_recent_releases(self, repo: str) -> ReleaseTagsList:
        """Fetch and return a list of recent release tags.

        Args:
            repo: Repository in format 'owner/repo'

        Returns:
            List of the 20 most recent tag names
        """
        ...

    @abstractmethod
    def _build_download_url(self, repo: str, tag: str, asset_name: str) -> str:
        """Build a download URL for an asset.

        Args:
            repo: Repository in format 'owner/repo'
            tag: Release tag
            asset_name: Asset filename

        Returns:
            Full download URL
        """
        ...

    @abstractmethod
    def _get_expected_directories(
        self, extract_dir: Path, release_tag: str, fork: ForkName
    ) -> DirectoryTuple:
        """Get expected unpack directories based on fork type.

        Args:
            extract_dir: Directory to extract to
            release_tag: Release tag
            fork: Proton fork name

        Returns:
            Tuple of (standard_path, alternative_path_or_None)
        """
        ...

    @abstractmethod
    def _check_existing_directory(
        self,
        unpacked: Path,
        alternative: Path | None,
        fork: ForkName,
    ) -> ExistenceCheckResult:
        """Check if the unpacked directory already exists.

        Args:
            unpacked: Standard path (without platform-specific prefix/suffix)
            alternative: Alternative path (with platform-specific prefix/suffix)
            fork: Proton fork name

        Returns:
            Tuple of (exists, actual_path)
        """
        ...

    @abstractmethod
    def _find_extracted_directory(
        self,
        extract_dir: Path,
        release_tag: str,
        fork: ForkName,
    ) -> Path:
        """Find the actual extracted directory after archive extraction.

        Args:
            extract_dir: Directory to search
            release_tag: Release tag
            fork: Proton fork name

        Returns:
            Path to the extracted directory
        """
        ...

    # ------------------------------------------------------------------
    # Shared workflow methods (use abstract methods internally)
    # ------------------------------------------------------------------

    def _determine_release_tag(
        self, repo: str, release_tag: str | None = None, **kwargs: Any
    ) -> str:
        """Determine the release tag to use."""
        manual_release_tag = kwargs.get("manual_release_tag", release_tag)
        if manual_release_tag is None:
            return self.fetch_latest_tag(repo)
        return manual_release_tag

    def _download_asset(
        self, repo: str, release_tag: str, fork: ForkName, output_dir: Path
    ) -> Path:
        """Download the asset and return the archive path."""
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

        archive_path = output_dir / asset_name
        download_url = self._build_download_url(repo, release_tag, asset_name)
        self.asset_downloader.download_asset(
            repo,
            release_tag,
            asset_name,
            archive_path,
            self.release_manager,
            download_url=download_url,
        )
        return archive_path

    def _dry_run_workflow(
        self,
        repo: str,
        output_dir: Path,
        extract_dir: Path,
        release_tag: str,
        fork: ForkName,
        is_manual_release: bool,
    ) -> None:
        """Execute dry-run workflow: show what would be done without making changes."""
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
        unpacked = self._get_expected_directories(extract_dir, release_tag, fork)[0]
        logger.info(f"Would extract to: {unpacked}")

        # Show what symlinks would be created
        candidates = self.link_manager.find_version_candidates(extract_dir, fork)
        candidates.append((parse_version(release_tag, fork), unpacked))
        candidates = self.link_manager._deduplicate_candidates(candidates)
        candidates.sort(key=lambda t: t[0], reverse=True)
        top_3 = candidates[:3]

        if top_3:
            main, fb1, fb2 = self.link_manager.get_link_names_for_fork(
                extract_dir, fork
            )
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
        show_file_details: bool,
    ) -> Path:
        """Extract the archive and manage symbolic links."""
        self.archive_extractor.extract_archive(
            archive_path, extract_dir, show_progress, show_file_details
        )

        # Find where the archive extracted to
        unpacked = self._find_extracted_directory(extract_dir, release_tag, fork)

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
        show_file_details: bool = True,
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
            show_file_details: Whether to show file details during extraction
            dry_run: If True, only show what would be done without making changes

        Returns:
            Path to the extract directory, or None in dry-run mode
        """
        self._validate_environment()

        if not dry_run:
            self._ensure_directories_writable(output_dir, extract_dir)

        is_manual_release = release_tag is not None
        release_tag = self._determine_release_tag(repo, release_tag)

        # Dry-run
        if dry_run:
            return self._dry_run_workflow(
                repo, output_dir, extract_dir, release_tag, fork, is_manual_release
            )

        # Check if already extracted
        unpacked, alternative = self._get_expected_directories(
            extract_dir, release_tag, fork
        )
        directory_exists, actual_directory = self._check_existing_directory(
            unpacked, alternative, fork
        )

        if directory_exists and actual_directory is not None:
            skip_processing, result = self._handle_existing_directory(
                extract_dir, release_tag, fork, actual_directory, is_manual_release
            )
            if skip_processing:
                return result

        # Download
        archive_path = self._download_asset(repo, release_tag, fork, output_dir)

        # Check if extracted during download (race condition)
        skip_processing, result = self._check_post_download_directory(
            extract_dir, release_tag, fork, is_manual_release
        )
        if skip_processing:
            return result

        return self._extract_and_manage_links(
            archive_path,
            extract_dir,
            release_tag,
            fork,
            is_manual_release,
            show_progress,
            show_file_details,
        )
