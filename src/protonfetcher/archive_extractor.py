"""Archive extractor implementation for ProtonFetcher."""

import gzip
import logging
import lzma
import os
import subprocess
import tarfile
from functools import partial
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
    ) -> Path:
        """Try extraction using tarfile library.

        Raises:
            ProtonFetcherError: If extraction fails
        """
        return self.extract_with_tarfile(archive_path, target_dir, show_progress)

    def _extract_with_fallback(
        self,
        archive_path: Path,
        target_dir: Path,
        show_progress: bool,
        fallback_method,
    ) -> Path:
        """Try tarfile extraction, fall back to alternative method if it fails.

        Args:
            archive_path: Path to the archive
            target_dir: Directory to extract into
            show_progress: Whether to show progress
            fallback_method: Alternative extraction method to try if tarfile fails

        Returns:
            Path to the target directory where archive was extracted
        """
        try:
            return self._try_tarfile_extraction(archive_path, target_dir, show_progress)
        except ProtonFetcherError:
            return fallback_method(archive_path, target_dir)

    # Format → extra tar args for the system-tar fallback
    _TAR_ARGS: dict[str, list[str]] = {
        "tar.gz": ["-xzf"],
        "tar.xz": ["-xJf"],
        "tar.zst": ["--zstd", "-xf"],
    }

    def extract_archive(
        self,
        archive_path: Path,
        target_dir: Path,
        show_progress: bool = True,
    ) -> Path:
        """Extract archive to the target directory with progress bar.

        Raises:
            ExtractionError: If extraction fails
        """
        tar_args = self._TAR_ARGS.get(self._get_archive_format(archive_path), [])
        fallback = partial(self._extract_with_system_tar, *tar_args)
        return self._extract_with_fallback(
            archive_path,
            target_dir,
            show_progress,
            fallback,
        )

    def _extract_with_system_tar(
        self, archive_path: Path, target_dir: Path, *tar_args: str
    ) -> Path:
        """Extract archive using the system tar command."""
        self.file_system_client.mkdir(target_dir, parents=True, exist_ok=True)

        cmd = [
            "tar",
            "--checkpoint=1",  # Show progress every 1 record
            "--checkpoint-action=dot",  # Show dot for progress
            *tar_args,
            "-f",
            str(archive_path),
            "-C",  # Extract to target directory
            str(target_dir),
        ]

        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode != 0:
            raise ExtractionError(
                f"Failed to extract archive {archive_path}: {result.stderr}"
            )

        return target_dir

    def extract_with_tarfile(
        self,
        archive_path: Path,
        target_dir: Path,
        show_progress: bool = True,
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
                with open(archive_path, "rb") as raw:
                    counting = _CountingReader(raw, spinner.update)
                    decompressor = self._open_decompressor(archive_path, counting)
                    with tarfile.open(fileobj=decompressor, mode="r|") as tar:
                        for member in tar:
                            tar.extract(member, path=target_dir, filter="data")
                spinner.finish()

            logger.info(f"Extracted {archive_path} to {target_dir}")
        except Exception as e:
            logger.error(f"Error extracting archive: {e}")
            raise ExtractionError(f"Failed to extract archive {archive_path}: {e}")

        return target_dir

    @staticmethod
    def _open_decompressor(archive_path: Path, counting: _CountingReader):
        """Open the appropriate decompressor for the archive format.

        zstd has no stdlib support, so it is handled by the system-tar fallback.
        """
        name = archive_path.name
        if name.endswith((".tar.gz", ".tgz")):
            return gzip.GzipFile(fileobj=counting)
        elif name.endswith((".tar.xz", ".txz")):
            return lzma.LZMAFile(cast(IO[bytes], counting))
        raise ExtractionError(f"Unsupported archive format: {archive_path}")
