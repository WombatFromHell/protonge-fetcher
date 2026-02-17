"""GitHub release fetcher implementation for ProtonFetcher."""

import logging
import shutil
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

logger = logging.getLogger(__name__)


class GitHubReleaseFetcher:
    """Handles fetching and extracting GitHub release assets."""

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        network_client: Optional[NetworkClientProtocol] = None,
        file_system_client: Optional[FileSystemClientProtocol] = None,
        spinner_cls: Optional[
            Any
        ] = None,  # Add spinner_cls parameter for backward compatibility with tests
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

    def _ensure_directory_is_writable(self, directory: Path) -> None:
        """
        Ensure that the directory exists and is writable.

        Args:
            directory: Path to the directory to check

        Raises:
            FetchError: If the directory doesn't exist, isn't a directory, or isn't writable
        """
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

            # Verify that directory exists after potential creation
            if not self.file_system_client.exists(directory):
                raise ProtonFetcherError(
                    f"Directory does not exist and could not be created: {directory}"
                )

            if not self.file_system_client.is_dir(directory):
                raise LinkManagementError(f"{directory} exists but is not a directory")

            # Test if directory is writable by trying to create a temporary file
            test_file = directory / ".write_test"
            try:
                self.file_system_client.write(test_file, b"")  # Create empty file
                self.file_system_client.unlink(test_file)  # Remove the test file
            except (OSError, AttributeError) as e:
                raise LinkManagementError(f"Directory {directory} is not writable: {e}")
        except PermissionError as e:
            # Handle the case where Path operations raise PermissionError (like mocked exists)
            raise ProtonFetcherError(f"Failed to create {directory}: {str(e)}")
        except Exception as e:
            # Handle the case where directory is mocked and operations raise exceptions
            raise ProtonFetcherError(f"Failed to create {directory}: {str(e)}")

    def list_recent_releases(self, repo: str) -> ReleaseTagsList:
        """Fetch and return a list of recent release tags from the GitHub API."""
        return self.release_manager.list_recent_releases(repo)

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

    def _validate_environment(self) -> None:
        """Validate that required tools and directories are available."""
        # Validate that curl is available
        if shutil.which("curl") is None:
            raise NetworkError("curl is not available")

    def _ensure_directories_writable(self, output_dir: Path, extract_dir: Path) -> None:
        """Validate directories are writable."""
        self._ensure_directory_is_writable(output_dir)
        self._ensure_directory_is_writable(extract_dir)

    def _determine_release_tag(
        self, repo: str, release_tag: str | None = None, **kwargs: Any
    ) -> str:
        """Determine the release tag to use.

        Supports both internal calling convention (repo, release_tag)
        and test calling convention that may include additional kwargs.
        """
        # Handle the case where tests pass 'manual_release_tag' as a keyword argument
        manual_release_tag = kwargs.get("manual_release_tag", release_tag)
        if manual_release_tag is None:
            return self.release_manager.fetch_latest_tag(repo)
        return manual_release_tag

    def _get_expected_directories(
        self, extract_dir: Path, release_tag: str, fork: ForkName
    ) -> DirectoryTuple:
        """Get the expected unpack directories based on fork type."""
        unpacked = extract_dir / release_tag
        if fork == ForkName.PROTON_EM:
            unpacked_with_prefix = extract_dir / f"proton-{release_tag}"
            return unpacked, unpacked_with_prefix
        elif fork == ForkName.CACHYOS:
            # CachyOS archives extract to directory with -x86_64 suffix
            # e.g., tag 'cachyos-10.0-20260207-slr' extracts to 'proton-cachyos-10.0-20260207-slr-x86_64'
            unpacked_with_prefix = extract_dir / f"proton-{release_tag}-x86_64"
            return unpacked, unpacked_with_prefix
        else:
            return unpacked, None

    def _check_proton_em_directory(
        self, unpacked: Path, unpacked_for_em: Path | None
    ) -> ExistenceCheckResult:
        """Check if Proton-EM directory exists (with or without prefix).

        Args:
            unpacked: Standard path (without proton- prefix)
            unpacked_for_em: Path with proton- prefix

        Returns:
            Tuple of (exists, actual_path)
        """
        if unpacked_for_em and unpacked_for_em.exists() and unpacked_for_em.is_dir():
            return True, unpacked_for_em
        if unpacked.exists() and unpacked.is_dir():
            return True, unpacked
        return False, None

    def _check_cachyos_directory(
        self, unpacked: Path, unpacked_with_prefix: Path | None
    ) -> ExistenceCheckResult:
        """Check if CachyOS directory exists (with or without prefix).

        Args:
            unpacked: Standard path (without proton- prefix)
            unpacked_with_prefix: Path with proton- prefix

        Returns:
            Tuple of (exists, actual_path)
        """
        if (
            unpacked_with_prefix
            and unpacked_with_prefix.exists()
            and unpacked_with_prefix.is_dir()
        ):
            return True, unpacked_with_prefix
        if unpacked.exists() and unpacked.is_dir():
            return True, unpacked
        return False, None

    def _check_ge_proton_directory(self, unpacked: Path) -> ExistenceCheckResult:
        """Check if GE-Proton directory exists.

        Args:
            unpacked: Path to check

        Returns:
            Tuple of (exists, actual_path)
        """
        if unpacked.exists() and unpacked.is_dir():
            return True, unpacked
        return False, None

    def _check_existing_directory(
        self, unpacked: Path, unpacked_for_em: Path | None, fork: ForkName
    ) -> ExistenceCheckResult:
        """Check if the unpacked directory already exists and return the actual path.

        Args:
            unpacked: Standard path (without proton- prefix)
            unpacked_for_em: Path with proton- prefix (for Proton-EM and CachyOS)
            fork: Proton fork name

        Returns:
            Tuple of (exists, actual_path)
        """
        if fork == ForkName.PROTON_EM:
            return self._check_proton_em_directory(unpacked, unpacked_for_em)
        elif fork == ForkName.CACHYOS:
            return self._check_cachyos_directory(unpacked, unpacked_for_em)
        else:
            return self._check_ge_proton_directory(unpacked)

    def _handle_existing_directory(
        self,
        extract_dir: Path,
        release_tag: str,
        fork: ForkName,
        actual_directory: Path,
        is_manual_release: bool,
    ) -> ProcessingResult:
        """Handle case where directory already exists and return whether to skip further processing."""
        # Add this check:
        if not self.file_system_client.exists(actual_directory):
            return False, None

        logger.info(
            f"Unpacked directory already exists: {actual_directory}, skipping download and extraction"
        )

        # Check if links are already up-to-date to avoid unnecessary recreation
        if self.link_manager.are_links_up_to_date(
            extract_dir, release_tag, fork, is_manual_release=is_manual_release
        ):
            logger.info("Symlinks are already up-to-date, skipping link management")
            return True, actual_directory

        # Only manage links if they need updating
        self.link_manager.manage_proton_links(
            extract_dir, release_tag, fork, is_manual_release=is_manual_release
        )
        return True, actual_directory

    def _download_asset(
        self, repo: str, release_tag: str, fork: ForkName, output_dir: Path
    ) -> Path:
        """Download the asset and return the archive path."""
        try:
            asset_name = self.release_manager.find_asset_by_name(
                repo, release_tag, fork
            )
        except ProtonFetcherError as e:
            raise ProtonFetcherError(
                f"Could not find asset for release {release_tag} in {repo}: {e}"
            )

        if asset_name is None:
            raise ProtonFetcherError(
                f"Could not find asset for release {release_tag} in {repo}"
            )

        archive_path = output_dir / asset_name
        self.asset_downloader.download_asset(
            repo, release_tag, asset_name, archive_path, self.release_manager
        )
        return archive_path

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

            # Check if links are already up-to-date to avoid unnecessary recreation
            if self.link_manager.are_links_up_to_date(
                extract_dir, release_tag, fork, is_manual_release=is_manual_release
            ):
                logger.info("Symlinks are already up-to-date, skipping link management")
                return True, unpacked

            # Only manage links if they need updating
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
        """
        Force recreation of symbolic links for a specific fork without downloading or extracting.

        This method finds all existing version directories for the specified fork and
        recreates the symlinks to ensure they point to the correct targets.

        Args:
            extract_dir: Directory containing the Proton installations
            fork: The Proton fork name to relink

        Returns:
            True if relinking was successful

        Raises:
            LinkManagementError: If no valid versions are found for the fork
        """
        self._ensure_directory_is_writable(extract_dir)

        # Find all version candidates for this fork
        candidates = self.link_manager.find_version_candidates(extract_dir, fork)

        if not candidates:
            raise LinkManagementError(
                f"No valid {fork} versions found in {extract_dir} to relink"
            )

        # Remove duplicate versions, preferring standard naming
        candidates = self.link_manager._deduplicate_candidates(candidates)

        # Sort by version (newest first)
        candidates.sort(key=lambda t: t[0], reverse=True)

        # Take top 3 versions for symlinks
        top_3 = candidates[:3]

        if not top_3:
            raise LinkManagementError(
                f"No valid {fork} versions found in {extract_dir} to relink"
            )

        # Get link names for this fork
        main, fb1, fb2 = self.link_manager.get_link_names_for_fork(extract_dir, fork)

        logger.info(f"Relinking {fork} symlinks...")

        # Force recreation of symlinks (bypass the optimization)
        self.link_manager.create_symlinks(main, fb1, fb2, top_3)

        logger.info(f"Successfully relinked {fork} symlinks")
        return True

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
        # Extract the archive
        self.archive_extractor.extract_archive(
            archive_path, extract_dir, show_progress, show_file_details
        )

        # Check if unpacked directory exists after extraction
        unpacked = extract_dir / release_tag
        if unpacked.exists() and unpacked.is_dir():
            logger.info(f"Unpacked directory exists after extraction: {unpacked}")
        else:
            # For Proton-EM, check if directory with "proton-" prefix exists
            proton_em_path = extract_dir / f"proton-{release_tag}"
            if proton_em_path.exists() and proton_em_path.is_dir():
                unpacked = proton_em_path
                logger.info(f"Unpacked directory exists after extraction: {unpacked}")
            # For CachyOS, check if directory with "proton-" prefix and "-x86_64" suffix exists
            elif fork == ForkName.CACHYOS:
                cachyos_path = extract_dir / f"proton-{release_tag}-x86_64"
                if cachyos_path.exists() and cachyos_path.is_dir():
                    unpacked = cachyos_path
                    logger.info(
                        f"Unpacked directory exists after extraction: {unpacked}"
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
        show_file_details: bool = True,
    ) -> Path | None:
        """Fetch and extract a Proton release.

        Args:
            repo: Repository in format 'owner/repo'
            output_dir: Directory to download the asset to
            extract_dir: Directory to extract to
            release_tag: Release tag to fetch (if None, fetches latest)
            fork: The ProtonGE fork name for appropriate asset naming
            show_progress: Whether to show the progress bar
            show_file_details: Whether to show file details during extraction

        Returns:
            Path to the extract directory

        Raises:
            FetchError: If fetching or extraction fails
        """
        self._validate_environment()
        self._ensure_directories_writable(output_dir, extract_dir)

        # Track whether this is a manual release
        is_manual_release = release_tag is not None

        release_tag = self._determine_release_tag(repo, release_tag)

        # Check if unpacked directory already exists
        unpacked, unpacked_for_em = self._get_expected_directories(
            extract_dir, release_tag, fork
        )
        directory_exists, actual_directory = self._check_existing_directory(
            unpacked, unpacked_for_em, fork
        )

        if directory_exists and actual_directory is not None:
            skip_processing, result = self._handle_existing_directory(
                extract_dir, release_tag, fork, actual_directory, is_manual_release
            )
            if skip_processing:
                return result

        archive_path = self._download_asset(repo, release_tag, fork, output_dir)

        # Check if unpacked directory exists after download (might have been created by another process)
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
