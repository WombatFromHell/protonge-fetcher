"""Archive extractor implementation for ProtonFetcher."""

import logging
import subprocess
import tarfile
from pathlib import Path
from typing import Dict

from .common import DEFAULT_TIMEOUT, FileSystemClientProtocol
from .exceptions import ExtractionError, ProtonFetcherError
from .spinner import Spinner
from .utils import format_bytes

logger = logging.getLogger(__name__)


class ArchiveExtractor:
    """Handles archive extraction."""

    def __init__(
        self,
        file_system_client: FileSystemClientProtocol,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.file_system_client = file_system_client
        self.timeout = timeout

    def get_archive_info(self, archive_path: Path) -> Dict[str, int]:
        """
        Get information about the archive without fully extracting it.

        Returns:
            Dictionary with archive info: {"file_count": int, "total_size": int}
        """
        try:
            with tarfile.open(archive_path, "r:*") as tar:
                members = tar.getmembers()
                total_files = len(members)
                total_size = sum(m.size for m in members)
                return {"file_count": total_files, "total_size": total_size}
        except Exception as e:
            raise ExtractionError(f"Error reading archive: {e}")

    def extract_archive(
        self,
        archive_path: Path,
        target_dir: Path,
        show_progress: bool = True,
        show_file_details: bool = True,
    ) -> Path:
        """Extract archive to the target directory with progress bar.
        Supports both .tar.gz and .tar.xz formats using system tar command.

        Args:
            archive_path: Path to the archive
            target_dir: Directory to extract into
            show_progress: Whether to show the progress bar
            show_file_details: Whether to show file details during extraction

        Returns:
            Path to the target directory where archive was extracted

        Raises:
            FetchError: If extraction fails
        """
        # Determine the archive format and dispatch to the appropriate method
        # Try tarfile extraction first for all formats to ensure progress indication, then fall back to system tar
        if archive_path.name.endswith(".tar.gz"):
            # For .tar.gz files, try tarfile extraction first (for progress indication), then system tar fallback
            try:
                if show_progress and show_file_details:
                    # Use default values to maintain backward compatibility with tests
                    result = self.extract_with_tarfile(archive_path, target_dir)
                else:
                    result = self.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                return result
            except ProtonFetcherError:
                # If tarfile fails, fall back to system tar
                result = self.extract_gz_archive(archive_path, target_dir)
                return result
        elif archive_path.name.endswith(".tar.xz"):
            # For .tar.xz files, try tarfile extraction first (for progress indication), then system tar fallback
            try:
                if show_progress and show_file_details:
                    # Use default values to maintain backward compatibility with tests
                    result = self.extract_with_tarfile(archive_path, target_dir)
                else:
                    result = self.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                return result
            except ProtonFetcherError:
                # If tarfile fails, fall back to system tar
                result = self.extract_xz_archive(archive_path, target_dir)
                return result
        else:
            # For other formats, try tarfile extraction first (primary method with progress indication)
            # If it fails, fall back to system tar for compatibility
            try:
                if show_progress and show_file_details:
                    # Use default values to maintain backward compatibility with tests
                    result = self.extract_with_tarfile(archive_path, target_dir)
                else:
                    result = self.extract_with_tarfile(
                        archive_path, target_dir, show_progress, show_file_details
                    )
                return result
            except ProtonFetcherError:
                # If tarfile extraction fails, fall back to system tar command
                result = self._extract_with_system_tar(archive_path, target_dir)
                return result

        return target_dir

    def _extract_with_system_tar(self, archive_path: Path, target_dir: Path) -> Path:
        """Extract archive using system tar command."""
        self.file_system_client.mkdir(target_dir, parents=True, exist_ok=True)

        # Use tar command for general case as well, but with different flags for different formats
        # If it's not .tar.gz or .tar.xz, try a generic approach
        cmd = [
            "tar",
            "--checkpoint=1",  # Show progress every 1 record
            "--checkpoint-action=dot",  # Show dot for progress
            "-xf",  # Extract tar (uncompressed, gz, or xz)
            str(archive_path),
            "-C",  # Extract to target directory
            str(target_dir),
        ]

        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode != 0:
            # If tar command fails, raise ExtractionError directly without fallback
            raise ExtractionError(
                f"Failed to extract archive {archive_path}: {result.stderr}"
            )

        return target_dir

    def is_tar_file(self, archive_path: Path) -> bool:
        """Check if the file is a tar file."""
        # First check if it's a directory - directories are not tar files
        if archive_path.is_dir():
            return False
        try:
            with tarfile.open(archive_path, "r:*") as _:
                return True
        except (tarfile.ReadError, FileNotFoundError, OSError):
            return False

    def extract_with_tarfile(
        self,
        archive_path: Path,
        target_dir: Path,
        show_progress: bool = True,
        show_file_details: bool = True,
    ) -> Path:
        """Extract archive using tarfile library."""
        self.file_system_client.mkdir(target_dir, parents=True, exist_ok=True)

        # Get archive info
        try:
            archive_info = self.get_archive_info(archive_path)
            total_files = archive_info["file_count"]
            total_size = archive_info["total_size"]
            logger.info(
                f"Archive contains {total_files} files, total size: {format_bytes(total_size)}"
            )
        except Exception as e:
            logger.error(f"Error reading archive: {e}")
            raise ExtractionError(f"Failed to read archive {archive_path}: {e}")

        # Initialize spinner
        spinner = Spinner(
            desc=f"Extracting {archive_path.name}",
            disable=False,
            fps_limit=30.0,  # Match your existing FPS limit
            show_progress=show_progress,
        )

        try:
            with spinner:
                with tarfile.open(archive_path, "r:*") as tar:
                    extracted_files = 0
                    extracted_size = 0

                    for member in tar:
                        # Extract the file
                        tar.extract(member, path=target_dir, filter="data")
                        extracted_files += 1
                        extracted_size += member.size

                        # Format file name to fit in terminal
                        filename = member.name
                        if len(filename) > 30:
                            filename = "..." + filename[-27:]

                        # Update the spinner with current progress
                        if show_file_details:
                            spinner.update_progress(
                                extracted_files,
                                total_files,
                                prefix=filename,  # Just show the filename, not "Extracting: ..."
                                suffix=f"({extracted_files}/{total_files}) [{format_bytes(extracted_size)}/{format_bytes(total_size)}]",
                            )
                        else:
                            spinner.update_progress(
                                extracted_files,
                                total_files,
                            )

                # Ensure the spinner shows 100% completion
                spinner.finish()

            logger.info(f"Extracted {archive_path} to {target_dir}")
        except Exception as e:
            logger.error(f"Error extracting archive: {e}")
            raise ExtractionError(f"Failed to extract archive {archive_path}: {e}")

        return target_dir

    def extract_gz_archive(self, archive_path: Path, target_dir: Path) -> Path:
        """Extract .tar.gz archive using system tar command with checkpoint features.

        Args:
            archive_path: Path to the .tar.gz archive
            target_dir: Directory to extract to

        Returns:
            Path to the target directory where archive was extracted

        Raises:
            FetchError: If extraction fails
        """
        self.file_system_client.mkdir(target_dir, parents=True, exist_ok=True)

        # Use tar command with checkpoint features for progress indication
        cmd = [
            "tar",
            "--checkpoint=1",  # Show progress every 1 record
            "--checkpoint-action=dot",  # Show dot for progress
            "-xzf",  # Extract gzipped tar
            str(archive_path),
            "-C",  # Extract to target directory
            str(target_dir),
        ]

        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode != 0:
            raise ExtractionError(result.stderr)

        return target_dir

    def extract_xz_archive(self, archive_path: Path, target_dir: Path) -> Path:
        """Extract .tar.xz archive using system tar command with checkpoint features.

        Args:
            archive_path: Path to the .tar.xz archive
            target_dir: Directory to extract to

        Returns:
            Path to the target directory where archive was extracted

        Raises:
            FetchError: If extraction fails
        """
        self.file_system_client.mkdir(target_dir, parents=True, exist_ok=True)

        # Use tar command with checkpoint features for progress indication
        cmd = [
            "tar",
            "--checkpoint=1",  # Show progress every 1 record
            "--checkpoint-action=dot",  # Show dot for progress
            "-xJf",  # Extract xzipped tar
            str(archive_path),
            "-C",  # Extract to target directory
            str(target_dir),
        ]

        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode != 0:
            raise ExtractionError(result.stderr)

        return target_dir
