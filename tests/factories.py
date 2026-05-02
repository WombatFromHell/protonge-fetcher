"""
Factory fixtures for creating mock objects and test data in the ProtonFetcher test suite.

Contains:
- mock_network_factory — NetworkClientProtocol mock factory
- mock_filesystem_factory — FileSystemClientProtocol mock factory
- sample_archive_factory — Sample archive creation factory
"""

import subprocess
import tarfile
from pathlib import Path
from typing import Any, Callable

import pytest

from protonfetcher.common import (
    DEFAULT_TIMEOUT,
    FileSystemClientProtocol,
    NetworkClientProtocol,
)

# =============================================================================
# Factory Fixtures (Network, Filesystem, Archive)
# =============================================================================


@pytest.fixture
def mock_network_factory(mocker: Any) -> Callable[..., Any]:
    """
    Factory for creating configured NetworkClientProtocol mocks.

    Usage:
        def test_with_custom_response(mock_network_factory):
            mock_network = mock_network_factory(
                get_response={"assets": [{"name": "test.tar.gz", "size": 1024}]},
                rate_limit=False,
            )

        def test_rate_limit(mock_network_factory):
            mock_network = mock_network_factory(rate_limit=True)
    """

    def _create_mock(
        get_response: dict | str | None = None,
        head_response: dict | str | None = None,
        download_response: dict | None = None,
        rate_limit: bool = False,
        not_found: bool = False,
        custom_returncode: int | None = None,
    ) -> Any:
        mock_network = mocker.MagicMock(spec=NetworkClientProtocol)
        mock_network.timeout = DEFAULT_TIMEOUT

        if rate_limit:
            mock_network.get.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='{"message": "API rate limit exceeded"}',
                stderr="403 Forbidden",
            )
        elif not_found:
            mock_response = subprocess.CompletedProcess(
                args=[], returncode=22, stdout="", stderr="404 Not Found"
            )
            mock_network.get.return_value = mock_response
            mock_network.head.return_value = mock_response
        else:
            import json

            if get_response is None:
                get_response = {"assets": [{"name": "test.tar.gz", "size": 1048576}]}
            if isinstance(get_response, dict):
                get_response = json.dumps(get_response)

            mock_network.get.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=get_response, stderr=""
            )

            if head_response is None:
                head_response = "Location: https://github.com/repo/releases/tag/v1.0"
            if isinstance(head_response, dict):
                head_response = "\n".join(f"{k}: {v}" for k, v in head_response.items())

            mock_network.head.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=head_response, stderr=""
            )

        if download_response:
            mock_network.download.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=download_response.get("returncode", 0),
                stdout=download_response.get("stdout", ""),
                stderr=download_response.get("stderr", ""),
            )
        else:
            mock_network.download.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        return mock_network

    return _create_mock


@pytest.fixture
def mock_filesystem_factory(mocker: Any, tmp_path: Path) -> Callable[..., Any]:
    """
    Factory for creating configured FileSystemClientProtocol mocks.

    Usage:
        def test_with_custom_structure(mock_filesystem_factory):
            mock_fs = mock_filesystem_factory(
                exists_map={"/dir": True, "/file": True},
                is_dir_map={"/dir": True, "/file": False},
                read_map={"/file": b"content"},
            )

        def test_with_real_tmp(mock_filesystem_factory):
            mock_fs = mock_filesystem_factory(use_tmp_path=True)
    """

    def _create_mock(
        exists_map: dict[str, bool] | None = None,
        is_dir_map: dict[str, bool] | None = None,
        is_symlink_map: dict[str, bool] | None = None,
        read_map: dict[str, bytes] | None = None,
        size_map: dict[str, int] | None = None,
        use_tmp_path: bool = False,
    ) -> Any:
        mock_fs = mocker.MagicMock(spec=FileSystemClientProtocol)
        mock_fs.PROTOCOL_VERSION = "1.0"

        if use_tmp_path:
            mock_fs.exists.side_effect = lambda p: p.exists()
            mock_fs.is_dir.side_effect = lambda p: p.is_dir()
            mock_fs.is_symlink.side_effect = lambda p: p.is_symlink()
            mock_fs.read.side_effect = lambda p: p.read_bytes()
            mock_fs.write.side_effect = lambda p, d: p.write_bytes(d)
            mock_fs.size.side_effect = lambda p: p.stat().st_size
            mock_fs.mtime.side_effect = lambda p: p.stat().st_mtime
            mock_fs.mkdir.side_effect = lambda p, **kwargs: p.mkdir(**kwargs)
            mock_fs.iterdir.side_effect = lambda p: p.iterdir()
            mock_fs.symlink_to.side_effect = lambda p, t, **kwargs: p.symlink_to(t)
            mock_fs.resolve.side_effect = lambda p: p.resolve()
            mock_fs.unlink.side_effect = lambda p: p.unlink()
            mock_fs.rmtree.side_effect = lambda p: (
                p.rmdir() if p.is_dir() else p.unlink()
            )
        else:
            # Default: return True for exists/is_dir unless explicitly overridden
            exists_map = exists_map or {}
            mock_fs.exists.side_effect = lambda p: exists_map.get(str(p), True)

            is_dir_map = is_dir_map or {}
            mock_fs.is_dir.side_effect = lambda p: is_dir_map.get(str(p), True)

            is_symlink_map = is_symlink_map or {}
            mock_fs.is_symlink.side_effect = lambda p: is_symlink_map.get(str(p), False)

            read_map = read_map or {}
            mock_fs.read.side_effect = lambda p: read_map.get(str(p), b"test content")

            size_map = size_map or {}
            mock_fs.size.side_effect = lambda p: size_map.get(str(p), 1048576)

            mock_fs.mkdir.return_value = None
            mock_fs.iterdir.return_value = iter([])
            mock_fs.symlink_to.return_value = None
            mock_fs.resolve.side_effect = lambda p: p
            mock_fs.unlink.return_value = None
            mock_fs.rmtree.return_value = None

        return mock_fs

    return _create_mock


@pytest.fixture
def sample_archive_factory(tmp_path: Path) -> Callable[..., Path]:
    """
    Factory for creating sample archives.

    Usage:
        def test_extraction(sample_archive_factory):
            archive = sample_archive_factory(
                format="gz",
                tag="GE-Proton10-20",
                files=[
                    ("version", "GE-Proton10-20"),
                    ("lib/libwine.so", "fake libwine"),
                ],
            )
    """

    def _create_archive(
        format: str = "gz",
        tag: str = "GE-Proton10-20",
        files: list[tuple[str, str]] | None = None,
    ) -> Path:
        if format == "gz":
            archive_path = tmp_path / f"{tag}.tar.gz"
            mode = "w:gz"
        else:
            archive_path = tmp_path / f"proton-{tag}.tar.xz"
            mode = "w:xz"

        content_dir = tmp_path / "content" / tag
        content_dir.mkdir(parents=True)

        if files is None:
            files = [("version", tag), ("file.txt", "test content")]

        for filename, content in files:
            file_path = content_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)

        with tarfile.open(archive_path, mode) as tar:
            tar.add(content_dir, arcname=tag)

        return archive_path

    return _create_archive
