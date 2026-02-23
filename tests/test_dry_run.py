"""
Dry-run mode tests for ProtonFetcher.

Tests for the --dry-run/-n flag that shows what would be downloaded/extracted/linked
without making any changes.
"""

from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from protonfetcher.common import ForkName
from protonfetcher.github_fetcher import GitHubReleaseFetcher


@pytest.fixture
def mock_fetcher(
    mock_network_client: Any, mock_filesystem_client: Any
) -> GitHubReleaseFetcher:
    """Create a fetcher with mocked dependencies for dry-run testing."""
    return GitHubReleaseFetcher(
        network_client=mock_network_client,
        file_system_client=mock_filesystem_client,
    )


class TestDryRunCLI:
    """Tests for CLI --dry-run flag parsing and validation."""

    def test_dry_run_flag_parsing(self, mocker: Any) -> None:
        """Test that --dry-run flag is correctly parsed."""
        from protonfetcher.cli import parse_arguments

        # Mock sys.argv to simulate --dry-run flag
        mocker.patch(
            "protonfetcher.cli.sys.argv",
            ["protonfetcher", "--fork", "GE-Proton", "--dry-run"],
        )

        args = parse_arguments()
        assert args.dry_run is True

    def test_dry_run_short_flag_parsing(self, mocker: Any) -> None:
        """Test that -n short flag is correctly parsed."""
        from protonfetcher.cli import parse_arguments

        mocker.patch(
            "protonfetcher.cli.sys.argv",
            ["protonfetcher", "-f", "GE-Proton", "-n"],
        )

        args = parse_arguments()
        assert args.dry_run is True

    def test_dry_run_conflicts_with_list(self, mocker: Any) -> None:
        """Test that --dry-run cannot be used with --list."""
        from protonfetcher.cli import parse_arguments

        mocker.patch(
            "protonfetcher.cli.sys.argv",
            ["protonfetcher", "--dry-run", "--list"],
        )

        with pytest.raises(SystemExit):
            parse_arguments()

    def test_dry_run_conflicts_with_ls(self, mocker: Any) -> None:
        """Test that --dry-run cannot be used with --ls."""
        from protonfetcher.cli import parse_arguments

        mocker.patch(
            "protonfetcher.cli.sys.argv",
            ["protonfetcher", "--dry-run", "--ls"],
        )

        with pytest.raises(SystemExit):
            parse_arguments()

    def test_dry_run_conflicts_with_rm(self, mocker: Any) -> None:
        """Test that --dry-run cannot be used with --rm."""
        from protonfetcher.cli import parse_arguments

        mocker.patch(
            "protonfetcher.cli.sys.argv",
            ["protonfetcher", "--dry-run", "--rm", "GE-Proton10-20"],
        )

        with pytest.raises(SystemExit):
            parse_arguments()

    def test_dry_run_conflicts_with_relink(self, mocker: Any) -> None:
        """Test that --dry-run cannot be used with --relink."""
        from protonfetcher.cli import parse_arguments

        mocker.patch(
            "protonfetcher.cli.sys.argv",
            ["protonfetcher", "--dry-run", "--relink", "--fork", "GE-Proton"],
        )

        with pytest.raises(SystemExit):
            parse_arguments()


class TestDryRunWorkflow:
    """Tests for dry-run workflow execution."""

    def test_dry_run_does_not_download(
        self,
        mock_fetcher: GitHubReleaseFetcher,
        mock_network_client: Any,
        mock_filesystem_client: Any,
        mocker: Any,
    ) -> None:
        """Test that dry-run mode does not perform actual downloads."""
        # Mock the release manager to return a valid asset
        mocker.patch.object(
            mock_fetcher.release_manager,
            "fetch_latest_tag",
            return_value="GE-Proton10-20",
        )
        mocker.patch.object(
            mock_fetcher.release_manager,
            "find_asset_by_name",
            return_value="GE-Proton10-20.tar.gz",
        )
        mocker.patch.object(
            mock_fetcher.release_manager,
            "get_remote_asset_size",
            return_value=1048576,
        )
        mocker.patch.object(
            mock_fetcher.link_manager,
            "find_version_candidates",
            return_value=[],
        )
        mocker.patch(
            "protonfetcher.github_fetcher.parse_version",
            return_value=("GE-Proton", 10, 20, 0),
        )
        mocker.patch.object(
            mock_fetcher.link_manager,
            "get_link_names_for_fork",
            return_value=(
                Path("/tmp/GE-Proton"),
                Path("/tmp/GE-Proton-Fallback"),
                Path("/tmp/GE-Proton-Fallback2"),
            ),
        )

        # Call fetch_and_extract with dry_run=True
        result = mock_fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=Path("/tmp/downloads"),
            extract_dir=Path("/tmp/extract"),
            dry_run=True,
        )

        # Verify no download was performed
        assert mock_network_client.download.call_count == 0
        # Verify result is None (dry-run doesn't return a path)
        assert result is None

    def test_dry_run_resolves_asset_info(
        self,
        mock_fetcher: GitHubReleaseFetcher,
        mocker: Any,
    ) -> None:
        """Test that dry-run mode still resolves asset information."""
        # Mock the release manager to return a valid asset
        mocker.patch.object(
            mock_fetcher.release_manager,
            "fetch_latest_tag",
            return_value="GE-Proton10-20",
        )
        mocker.patch.object(
            mock_fetcher.release_manager,
            "find_asset_by_name",
            return_value="GE-Proton10-20.tar.gz",
        )
        mocker.patch.object(
            mock_fetcher.release_manager,
            "get_remote_asset_size",
            return_value=1048576,
        )
        mocker.patch.object(
            mock_fetcher.link_manager,
            "find_version_candidates",
            return_value=[],
        )
        mocker.patch(
            "protonfetcher.github_fetcher.parse_version",
            return_value=("GE-Proton", 10, 20, 0),
        )
        mocker.patch.object(
            mock_fetcher.link_manager,
            "get_link_names_for_fork",
            return_value=(
                Path("/tmp/GE-Proton"),
                Path("/tmp/GE-Proton-Fallback"),
                Path("/tmp/GE-Proton-Fallback2"),
            ),
        )

        # Call fetch_and_extract with dry_run=True
        mock_fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=Path("/tmp/downloads"),
            extract_dir=Path("/tmp/extract"),
            dry_run=True,
        )

        # Verify asset info was resolved
        cast(
            MagicMock, mock_fetcher.release_manager.find_asset_by_name
        ).assert_called_once()
        cast(
            MagicMock, mock_fetcher.release_manager.get_remote_asset_size
        ).assert_called_once()

    @pytest.mark.parametrize(
        "fork,expected_extract_path",
        [
            (ForkName.GE_PROTON, "GE-Proton10-20"),
            (ForkName.PROTON_EM, "proton-EM-10.0-30"),
            (ForkName.CACHYOS, "proton-cachyos-10.0-20260207-slr-x86_64"),
        ],
    )
    def test_dry_run_all_forks(
        self,
        mock_fetcher: GitHubReleaseFetcher,
        fork: ForkName,
        expected_extract_path: str,
        test_data: dict[str, Any],
        mocker: Any,
    ) -> None:
        """Test dry-run mode works for all supported forks."""
        repo = test_data["FORKS"][fork]["repo"]
        example_tag = test_data["FORKS"][fork]["example_tag"]
        example_asset = test_data["FORKS"][fork]["example_asset"]

        # Mock the release manager
        mocker.patch.object(
            mock_fetcher.release_manager,
            "fetch_latest_tag",
            return_value=example_tag,
        )
        mocker.patch.object(
            mock_fetcher.release_manager,
            "find_asset_by_name",
            return_value=example_asset,
        )
        mocker.patch.object(
            mock_fetcher.release_manager,
            "get_remote_asset_size",
            return_value=1048576,
        )
        mocker.patch.object(
            mock_fetcher.link_manager,
            "find_version_candidates",
            return_value=[],
        )
        mocker.patch(
            "protonfetcher.github_fetcher.parse_version",
            return_value=("GE-Proton", 10, 20, 0),
        )
        mocker.patch.object(
            mock_fetcher.link_manager,
            "get_link_names_for_fork",
            return_value=(
                Path(f"/tmp/{fork.value}"),
                Path(f"/tmp/{fork.value}-Fallback"),
                Path(f"/tmp/{fork.value}-Fallback2"),
            ),
        )

        # Call fetch_and_extract with dry_run=True
        result = mock_fetcher.fetch_and_extract(
            repo=repo,
            output_dir=Path("/tmp/downloads"),
            extract_dir=Path("/tmp/extract"),
            fork=fork,
            dry_run=True,
        )

        # Verify no filesystem modifications
        assert result is None


class TestDryRunOutput:
    """Tests for dry-run output messages."""

    def test_dry_run_logs_what_would_be_downloaded(
        self,
        mock_fetcher: GitHubReleaseFetcher,
        caplog: pytest.LogCaptureFixture,
        mocker: Any,
    ) -> None:
        """Test that dry-run mode logs what would be downloaded."""
        import logging

        caplog.set_level(logging.INFO)

        # Mock the release manager
        mocker.patch.object(
            mock_fetcher.release_manager,
            "fetch_latest_tag",
            return_value="GE-Proton10-20",
        )
        mocker.patch.object(
            mock_fetcher.release_manager,
            "find_asset_by_name",
            return_value="GE-Proton10-20.tar.gz",
        )
        mocker.patch.object(
            mock_fetcher.release_manager,
            "get_remote_asset_size",
            return_value=1048576,
        )
        mocker.patch.object(
            mock_fetcher.link_manager,
            "find_version_candidates",
            return_value=[],
        )
        mocker.patch(
            "protonfetcher.github_fetcher.parse_version",
            return_value=("GE-Proton", 10, 20, 0),
        )
        mocker.patch.object(
            mock_fetcher.link_manager,
            "get_link_names_for_fork",
            return_value=(
                Path("/tmp/GE-Proton"),
                Path("/tmp/GE-Proton-Fallback"),
                Path("/tmp/GE-Proton-Fallback2"),
            ),
        )

        # Call fetch_and_extract with dry_run=True
        mock_fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=Path("/tmp/downloads"),
            extract_dir=Path("/tmp/extract"),
            dry_run=True,
        )

        # Verify output messages
        assert "Would download: GE-Proton10-20.tar.gz" in caplog.text
        assert "(1.00 MiB)" in caplog.text
        assert "Would extract to:" in caplog.text

    def test_dry_run_logs_symlink_plan(
        self,
        mock_fetcher: GitHubReleaseFetcher,
        caplog: pytest.LogCaptureFixture,
        mocker: Any,
    ) -> None:
        """Test that dry-run mode logs planned symlink changes."""
        import logging

        caplog.set_level(logging.INFO)

        # Mock the release manager
        mocker.patch.object(
            mock_fetcher.release_manager,
            "fetch_latest_tag",
            return_value="GE-Proton10-20",
        )
        mocker.patch.object(
            mock_fetcher.release_manager,
            "find_asset_by_name",
            return_value="GE-Proton10-20.tar.gz",
        )
        mocker.patch.object(
            mock_fetcher.release_manager,
            "get_remote_asset_size",
            return_value=1048576,
        )
        mocker.patch.object(
            mock_fetcher.link_manager,
            "find_version_candidates",
            return_value=[],
        )
        mocker.patch(
            "protonfetcher.github_fetcher.parse_version",
            return_value=("GE-Proton", 10, 20, 0),
        )
        mocker.patch.object(
            mock_fetcher.link_manager,
            "get_link_names_for_fork",
            return_value=(
                Path("/tmp/extract/GE-Proton"),
                Path("/tmp/extract/GE-Proton-Fallback"),
                Path("/tmp/extract/GE-Proton-Fallback2"),
            ),
        )

        # Call fetch_and_extract with dry_run=True
        mock_fetcher.fetch_and_extract(
            repo="GloriousEggroll/proton-ge-custom",
            output_dir=Path("/tmp/downloads"),
            extract_dir=Path("/tmp/extract"),
            dry_run=True,
        )

        # Verify symlink planning output
        assert "Would create/update symlinks:" in caplog.text
        assert "GE-Proton ->" in caplog.text
        assert "Dry run complete - no changes made" in caplog.text


class TestDryRunIntegration:
    """Integration tests for dry-run mode with CLI."""

    def test_cli_dry_run_with_fork(
        self,
        capsys: pytest.CaptureFixture[str],
        mocker: Any,
    ) -> None:
        """Test CLI --dry-run flag with --fork works end-to-end."""
        # Mock the fetcher to avoid actual network calls
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.fetch_and_extract.return_value = None

        # Mock GitHubReleaseFetcher constructor
        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        # Mock curl availability check
        mocker.patch("shutil.which", return_value="/usr/bin/curl")

        # Mock sys.argv
        mocker.patch(
            "protonfetcher.cli.sys.argv",
            ["protonfetcher", "--fork", "GE-Proton", "--dry-run"],
        )

        from protonfetcher.cli import main

        # Should not raise - dry-run completes successfully
        main()

        # Verify fetch_and_extract was called with dry_run=True
        mock_fetcher.fetch_and_extract.assert_called_once()
        call_kwargs = mock_fetcher.fetch_and_extract.call_args.kwargs
        assert call_kwargs.get("dry_run") is True

        # Verify no output message (dry-run message is logged, not printed)
        captured = capsys.readouterr()
        # Dry run doesn't print Success, message is logged instead
        assert "Success" not in captured.out

    def test_cli_dry_run_with_release(
        self,
        capsys: pytest.CaptureFixture[str],
        mocker: Any,
    ) -> None:
        """Test CLI --dry-run flag with --release works end-to-end."""
        # Mock the fetcher
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.fetch_and_extract.return_value = None

        mocker.patch(
            "protonfetcher.cli.GitHubReleaseFetcher",
            return_value=mock_fetcher,
        )

        mocker.patch("shutil.which", return_value="/usr/bin/curl")

        mocker.patch(
            "protonfetcher.cli.sys.argv",
            [
                "protonfetcher",
                "--fork",
                "GE-Proton",
                "--release",
                "GE-Proton10-20",
                "--dry-run",
            ],
        )

        from protonfetcher.cli import main

        # Should not raise - dry-run completes successfully
        main()

        # Verify release tag was passed
        call_kwargs = mock_fetcher.fetch_and_extract.call_args.kwargs
        assert call_kwargs.get("release_tag") == "GE-Proton10-20"
        assert call_kwargs.get("dry_run") is True
