"""Asset downloader implementation for ProtonFetcher."""

import logging
import urllib.request
from pathlib import Path
from typing import Optional

from .common import (
    DEFAULT_TIMEOUT,
    FileSystemClientProtocol,
    Headers,
    NetworkClientProtocol,
    ProcessResult,
)
from .exceptions import NetworkError
from .release_manager import ReleaseManager
from .spinner import Spinner

logger = logging.getLogger(__name__)


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

    def curl_get(
        self, url: str, headers: Optional[Headers] = None, stream: bool = False
    ) -> ProcessResult:
        """Make a GET request using curl."""
        return self.network_client.get(url, headers, stream)

    def curl_head(
        self,
        url: str,
        headers: Headers | None = None,
        follow_redirects: bool = False,
    ) -> ProcessResult:
        """Make a HEAD request using curl."""
        return self.network_client.head(url, headers, follow_redirects)

    def curl_download(
        self, url: str, output_path: Path, headers: Headers | None = None
    ) -> ProcessResult:
        """Download a file using curl."""
        return self.network_client.download(url, output_path, headers)

    def download_with_spinner(
        self, url: str, output_path: Path, headers: Optional[Headers] = None
    ) -> None:
        """Download a file with progress spinner using urllib."""

        # Create a request with headers
        req = urllib.request.Request(url, headers=headers or {})

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                total_size = int(response.headers.get("Content-Length", 0))

                with open(output_path, "wb") as f:
                    chunk_size = 8192
                    downloaded = 0

                    # Create spinner with total size if available
                    with (
                        Spinner(
                            desc=f"Downloading {output_path.name}",
                            total=total_size,
                            unit="B",
                            unit_scale=True,
                            disable=False,
                            fps_limit=30.0,  # Limit to 15 FPS during download to prevent excessive terminal updates
                            show_progress=True,
                        ) as spinner
                    ):
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break

                            f.write(chunk)
                            downloaded += len(chunk)
                            # Update spinner with the amount downloaded since last call
                            spinner.update(len(chunk))

        except Exception as e:
            raise NetworkError(f"Failed to download {url}: {str(e)}")

    def download_asset(
        self,
        repo: str,
        tag: str,
        asset_name: str,
        out_path: Path,
        release_manager: ReleaseManager,
    ) -> Path:
        """Download a specific asset from a GitHub release with progress bar.
        If a local file with the same name and size already exists, skip download.

        Args:
            repo: Repository in format 'owner/repo'
            tag: Release tag
            asset_name: Asset filename to download
            out_path: Path where the asset will be saved
            release_manager: ReleaseManager instance to get remote asset size

        Returns:
            Path to the downloaded file

        Raises:
            FetchError: If download fails or asset not found
        """
        url = f"https://github.com/{repo}/releases/download/{tag}/{asset_name}"
        logger.info(f"Checking if asset needs download from: {url}")

        # Check if local file already exists and has the same size as remote
        if self.file_system_client.exists(out_path):
            local_size = (
                out_path.stat().st_size
            )  # Note: .stat() is still a Path method; we can't fully abstract this
            remote_size = release_manager.get_remote_asset_size(repo, tag, asset_name)

            if local_size == remote_size:
                logger.info(
                    f"Local asset {out_path} already exists with matching size ({local_size} bytes), skipping download"
                )
                return out_path
            else:
                logger.info(
                    f"Local size ({local_size} bytes) differs from remote size ({remote_size} bytes), downloading new version"
                )
        else:
            logger.info("Local asset does not exist, proceeding with download")

        self.file_system_client.mkdir(out_path.parent, parents=True, exist_ok=True)

        # Prepare headers for download
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            # Use the new spinner-based download method
            self.download_with_spinner(url, out_path, headers)
        except Exception as e:
            # Fallback to original curl method for compatibility
            logger.warning(f"Spinner download failed: {e}, falling back to curl")
            try:
                result = self.curl_download(url, out_path, headers)
                if result.returncode != 0:
                    if "404" in result.stderr or "not found" in result.stderr.lower():
                        raise NetworkError(f"Asset not found: {asset_name}")
                    raise NetworkError(
                        f"Failed to download {asset_name}: {result.stderr}"
                    )
            except Exception as fallback_error:
                raise NetworkError(f"Failed to download {asset_name}: {fallback_error}")

        logger.info(f"Downloaded asset to: {out_path}")
        return out_path
