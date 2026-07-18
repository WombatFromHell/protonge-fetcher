"""Archive extractor implementation for ProtonFetcher."""

import gzip
import logging
import lzma
import os
import subprocess
import tarfile
from pathlib import Path
from typing import IO, cast

from .common import DEFAULT_TIMEOUT, FileSystemClientProtocol
from .exceptions import ExtractionError, ProtonFetcherError
from .spinner import Spinner

logger = logging.getLogger(__name__)


class _CountingReader:
    """Wraps a file object; reports compressed bytes consumed to a callback.

    ponytail: seekable=False forces tarfile into streaming mode (r|), which
    avoids the double-open of a pre-scan while tracking progress.
    """

    def __init__(self, fp: IO[bytes], on_read) -> None:
        self._fp = fp
        self._on_read = on_read

    def read(self, size: int = -1) -> bytes:
        chunk = self._fp.read(size)
        self._on_read(len(chunk))
        return chunk

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def seek(self, offset: int, whence: int = 0) -> int:
        raise OSError("seek not supported on CountingReader")

    def close(self) -> None:
        self._fp.close()


class ArchiveExtractor:
    """Handles archive extraction."""

    def __init__(
        self,
        file_system_client: FileSystemClientProtocol,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.file_system_client = file_system_client
        self.timeout = timeout

    def _get_archive_format(self, archive_path: Path) -> str:
        """Determine archive format from filename.

        Returns:
            Format string: 'tar.gz', 'tar.xz', 'tar.zst', or 'other'
        """
        name = archive_path.name
        if name.endswith((".tar.gz", ".tgz")):
            return "tar.gz"
        elif name.endswith((".tar.xz", ".txz")):
            return "tar.xz"
        elif name.endswith((".tar.zst", ".tzst")):
            return "tar.zst"
        else:
            return "other"

    def _try_tarfile_extraction(
        self,
        archive_path: Path,
        target_dir: Path,
        show_progress: bool,
        show_file_details: bool,
    ) -> Path:
        """Try extraction using tarfile library.

        Raises:
            ProtonFetcherError: If extraction fails
        """
        return self.extract_with_tarfile(
            archive_path, target_dir, show_progress, show_file_details
        )

    def _extract_with_fallback(
        self,
        archive_path: Path,
        target_dir: Path,
        show_progress: bool,
        show_file_details: bool,
        fallback_method,
    ) -> Path:
        """Try tarfile extraction, fall back to alternative method if it fails.

        Args:
            archive_path: Path to the archive
            target_dir: Directory to extract into
            show_progress: Whether to show progress
            show_file_details: Whether to show file details
            fallback_method: Alternative extraction method to try if tarfile fails

        Returns:
            Path to the target directory where archive was extracted
        """
        try:
            return self._try_tarfile_extraction(
                archive_path, target_dir, show_progress, show_file_details
            )
        except ProtonFetcherError:
            return fallback_method(archive_path, target_dir)

    # Format → fallback method name mapping (resolved at runtime via getattr)
    _EXTRACT_METHODS: dict[str, str] = {
        "tar.gz": "extract_gz_archive",
        "tar.xz": "extract_xz_archive",
        "tar.zst": "extract_zst_archive",
    }

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
        format_type = self._get_archive_format(archive_path)
        method_name = self._EXTRACT_METHODS.get(format_type)
        if method_name:
            fallback = getattr(self, method_name)
        else:
            fallback = self._extract_with_system_tar
        return self._extract_with_fallback(
            archive_path,
            target_dir,
            show_progress,
            show_file_details,
            fallback,
        )

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
        except tarfile.ReadError, FileNotFoundError, OSError:
            return False

    def extract_with_tarfile(
        self,
        archive_path: Path,
        target_dir: Path,
        show_progress: bool = True,
        show_file_details: bool = True,
    ) -> Path:
        """Extract archive using tarfile library with streaming progress.

        ponytail: CountingReader tracks compressed bytes consumed in a single
        pass — no pre-scan, no double-open. Uses r| streaming mode via
        seekable() returning False on the counting wrapper.
        """
        self.file_system_client.mkdir(target_dir, parents=True, exist_ok=True)

        try:
            total_size = os.path.getsize(archive_path)

            spinner = Spinner(
                desc=f"Extracting {archive_path.name}",
                total=total_size,
                unit="B",
                unit_scale=True,
                disable=not show_progress,
                fps_limit=10.0,
                show_progress=show_progress,
            )

            with spinner:
                raw = open(archive_path, "rb")
                counting = _CountingReader(raw, spinner.update)

                decompressor = self._open_decompressor(archive_path, counting)

                with tarfile.open(fileobj=decompressor, mode="r|") as tar:
                    for member in tar:
                        tar.extract(member, path=target_dir, filter="data")

                decompressor.close()
                raw.close()

                spinner.finish()

            logger.info(f"Extracted {archive_path} to {target_dir}")
        except Exception as e:
            logger.error(f"Error extracting archive: {e}")
            raise ExtractionError(f"Failed to extract archive {archive_path}: {e}")

        return target_dir

    @staticmethod
    def _open_decompressor(archive_path: Path, counting: _CountingReader):
        """Open the appropriate decompressor for the archive format."""
        name = archive_path.name
        if name.endswith((".tar.gz", ".tgz")):
            return gzip.GzipFile(fileobj=counting)
        elif name.endswith((".tar.xz", ".txz")):
            return lzma.LZMAFile(cast(IO[bytes], counting))
        elif name.endswith((".tar.zst", ".tzst")):
            from compression.zstd import ZstdFile

            return ZstdFile(counting)
        raise ExtractionError(f"Unsupported archive format: {archive_path}")

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

    def extract_zst_archive(self, archive_path: Path, target_dir: Path) -> Path:
        """Extract .tar.zst archive using system tar with --zstd filter.

        Args:
            archive_path: Path to the .tar.zst archive
            target_dir: Directory to extract to

        Returns:
            Path to the target directory where archive was extracted

        Raises:
            ExtractionError: If extraction fails
        """
        self.file_system_client.mkdir(target_dir, parents=True, exist_ok=True)

        cmd = [
            "tar",
            "--checkpoint=1",
            "--checkpoint-action=dot",
            "--zstd",
            "-xf",
            str(archive_path),
            "-C",
            str(target_dir),
        ]

        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode != 0:
            raise ExtractionError(result.stderr)

        return target_dir
