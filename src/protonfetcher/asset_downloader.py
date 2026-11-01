"""Asset downloader implementation for ProtonFetcher."""

import hashlib
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path

from .common import (
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    FileSystemClientProtocol,
    Headers,
    NetworkClientProtocol,
)
from .exceptions import ChecksumError, NetworkError
from .spinner import Spinner
from .utils import friendly_os_error, format_bytes

logger = logging.getLogger(__name__)


def _checksum_of(path: Path, digest: str) -> str | None:
    """Hash `path` with the algorithm named in `digest` ('sha256:<hex>').

    None means 'we cannot verify this' (unknown algorithm), which must never
    fail a download. Streaming via file_digest keeps a 500 MB archive out of RAM.
    """
    algorithm = digest.partition(":")[0]
    if algorithm not in hashlib.algorithms_available:
        logger.debug(f"Unknown checksum algorithm {algorithm!r}, skipping verification")
        return None

    try:
        with open(path, "rb") as f:
            return hashlib.file_digest(f, algorithm).hexdigest()
    except OSError as e:
        raise friendly_os_error("checksum of", path, e) from e


class AssetDownloader:
    """Manages asset downloads."""

    def __init__(
        self,
        network_client: NetworkClientProtocol,
        file_system_client: FileSystemClientProtocol,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.network_client = network_client
        self.file_system_client = file_system_client
        self.timeout = timeout

    def download_with_spinner(
        self,
        url: str,
        output_path: Path,
        headers: Headers | None = None,
        resume_from: int | None = None,
    ) -> None:
        """Download a file with progress spinner using urllib.

        Args:
            resume_from: byte offset to continue from. The server must answer
                206; any other status means it ignored the Range and we rewrite
                the file from byte 0.
        """

        # Create a request with headers
        request_headers = dict(headers or {})
        offset = resume_from or 0
        if offset:
            request_headers["Range"] = f"bytes={offset}-"
        req = urllib.request.Request(url, headers=request_headers)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                resumed = offset > 0 and response.status == 206
                remaining = int(response.headers.get("Content-Length", 0))
                total = offset + remaining if resumed else remaining

                if resumed:
                    logger.info(
                        f"Resuming {output_path.name} from {format_bytes(offset)}"
                    )

                with open(output_path, "ab" if resumed else "wb") as f:
                    chunk_size = 8192

                    # Create spinner with total size if available
                    with (
                        Spinner(
                            desc=f"Downloading {output_path.name}",
                            total=total,
                            unit="B",
                            unit_scale=True,
                            disable=False,
                            fps_limit=10.0,  # Limit to 10 FPS during download to prevent excessive terminal updates
                            show_progress=True,
                        ) as spinner
                    ):
                        if resumed:
                            # The bar starts at the bytes we already hold.
                            spinner.update(offset)

                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break

                            f.write(chunk)
                            # Update spinner with the amount downloaded since last call
                            spinner.update(len(chunk))

        except urllib.error.HTTPError as e:
            if e.code == 416 and offset:
                raise NetworkError(
                    f"{url} rejected the resume range (bytes {resume_from}-): the local "
                    f"file does not match the remote asset. Delete {output_path} and "
                    "run again."
                ) from e
            raise NetworkError(f"Failed to download {url}: {str(e)}") from e
        except urllib.error.URLError as e:
            raise NetworkError(f"Failed to download {url}: {str(e)}") from e
        except OSError as e:
            # A full disk or a denied open is a filesystem problem, not a
            # network one — naming it as one sends users hunting for proxies.
            raise friendly_os_error("download to", output_path, e) from e
        except Exception as e:
            raise NetworkError(f"Failed to download {url}: {str(e)}")

    def download_asset(
        self,
        repo: str,
        tag: str,
        asset_name: str,
        out_path: Path,
        download_url: str,
        remote_size: int | None = None,
        digest: str | None = None,
    ) -> Path:
        """Download a release asset, staged as '<name>.partial' and renamed once verified.

        `out_path` only ever holds a complete archive: it is renamed into place
        after the size and (when a digest is known) the checksum match, so a
        present `out_path` means 'usable'. An interrupted download leaves
        '<name>.partial' behind, which is what the next run resumes from.

        Args:
            repo: Repository in format 'owner/repo'
            tag: Release tag
            asset_name: Asset filename to download
            out_path: Path where the asset will be saved
            download_url: Full download URL (built by the platform adapter)
            remote_size: Pre-fetched remote file size; if None, size checks are skipped
            digest: 'algo:hex' from the release listing or checksum asset;
                None means there is nothing to verify against

        Returns:
            Path to the downloaded file

        Raises:
            NetworkError: If download fails, the asset is not found, or the
                archive does not match its checksum
        """
        logger.info(f"Checking if asset needs download from: {download_url}")

        partial = out_path.with_name(f"{out_path.name}.partial")

        if self.file_system_client.exists(out_path) and remote_size is not None:
            local_size = self.file_system_client.size(out_path)
            if local_size == remote_size and self._verify(out_path, digest):
                logger.info(
                    f"Local asset {out_path} already exists with matching size "
                    f"({format_bytes(local_size)}), skipping download"
                )
                if self.file_system_client.exists(partial):
                    # The archive is complete and verified, so a leftover prefix is junk.
                    self.file_system_client.unlink(partial)
                return out_path
            if local_size == remote_size:
                logger.info(
                    f"Local asset {out_path} matches the remote size but fails its "
                    "checksum, redownloading"
                )
                self.file_system_client.unlink(out_path)
            else:
                logger.info(
                    f"Local size ({format_bytes(local_size)}) differs from remote size "
                    f"({format_bytes(remote_size)}), downloading new version"
                )
        else:
            logger.info("Local asset does not exist, proceeding with download")

        # A .partial of remote_size or more cannot be a prefix of the asset.
        resume_from = (
            self.file_system_client.size(partial)
            if self.file_system_client.exists(partial)
            else 0
        )
        if remote_size is not None and resume_from >= remote_size:
            resume_from = 0

        self.file_system_client.mkdir(out_path.parent, parents=True, exist_ok=True)
        headers = {"User-Agent": DEFAULT_USER_AGENT}

        self._fetch(download_url, partial, headers, resume_from or None, remote_size)

        if not self._verify(partial, digest):
            logger.info(
                f"{asset_name} does not match its checksum — the resumed prefix was "
                "not ours. Redownloading from byte 0."
            )
            self.file_system_client.unlink(partial)
            self._fetch(download_url, partial, headers, None, remote_size)
            if not self._verify(partial, digest):
                # A checksum mismatch is not resumable — the bytes are not ours.
                self.file_system_client.unlink(partial)
                raise ChecksumError(
                    f"Checksum mismatch for {asset_name} (expected {digest}): the "
                    "downloaded archive is not the upstream asset and our cached "
                    "metadata may be stale — run again to re-check it"
                )

        try:
            os.replace(partial, out_path)
        except OSError as e:
            raise friendly_os_error("rename", out_path, e) from e

        logger.info(f"Downloaded asset to: {out_path}")
        return out_path

    def _fetch(
        self,
        download_url: str,
        partial: Path,
        headers: Headers,
        resume_from: int | None,
        remote_size: int | None,
    ) -> None:
        """Download into the .partial target and gate on the expected size."""
        self.download_with_spinner(download_url, partial, headers, resume_from)

        if remote_size is not None:
            final_size = self.file_system_client.size(partial)
            if final_size != remote_size:
                raise NetworkError(
                    f"Download of {partial.name} ended early: {format_bytes(final_size)} "
                    f"of {format_bytes(remote_size)} written "
                    "(partial file kept — run again to resume)"
                )

    def _verify(self, path: Path, digest: str | None) -> bool:
        """True when there is nothing to check or the file matches the digest."""
        if digest is None:
            return True

        # Published hex can be uppercase; file_digest always returns lowercase.
        expected = digest.partition(":")[2].lower()
        actual = _checksum_of(path, digest)
        if actual is None:
            return True
        if actual != expected:
            logger.info(
                f"Checksum mismatch for {path.name}: expected {expected}, got {actual}"
            )
            return False
        return True
