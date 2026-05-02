"""Tests for CLI dispatch logic.

Tests for dispatch(), resolve_default_operation(), and related helpers
in protonfetcher.cli.dispatch.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from protonfetcher.cli.dispatch import (
    CLIContext,
    dispatch,
    get_explicit_flags,
    get_operation_from_args,
    has_explicit_fork,
    resolve_default_operation,
)

# =============================================================================
# get_explicit_flags Tests
# =============================================================================


class TestGetExplicitFlags:
    """Test explicit flag detection."""

    def test_ls_flag_detected(self) -> None:
        """Test --ls flag is detected."""
        flags = get_explicit_flags(["--ls"])
        assert flags["ls"] is True
        assert flags["list"] is False

    def test_list_flag_detected(self) -> None:
        """Test --list and -l flags are detected."""
        assert get_explicit_flags(["--list"])["list"] is True
        assert get_explicit_flags(["-l"])["list"] is True

    def test_rm_flag_detected(self) -> None:
        """Test --rm flag is detected."""
        assert get_explicit_flags(["--rm"])["rm"] is True
        assert get_explicit_flags(["--rm", "--release", "v1"])["rm"] is True
        # -r is --release, not --rm
        assert get_explicit_flags(["-r", "v1"])["rm"] is False

    def test_fork_flag_detected(self) -> None:
        """Test --fork flag is detected."""
        assert get_explicit_flags(["--fork", "GE-Proton"])["fork"] is True
        assert get_explicit_flags(["-f", "GE-Proton"])["fork"] is True

    def test_release_flag_detected(self) -> None:
        """Test --release flag is detected."""
        assert get_explicit_flags(["--release", "v1"])["release"] is True
        assert get_explicit_flags(["-r", "v1"])["release"] is True

    def test_no_explicit_flags(self) -> None:
        """Test no explicit flags when only positional args present."""
        flags = get_explicit_flags(["some_arg"])
        assert all(v is False for v in flags.values())

    def test_flag_with_equals(self) -> None:
        """Test flag with = syntax is detected."""
        assert get_explicit_flags(["--fork=GE-Proton"])["fork"] is True
        assert get_explicit_flags(["--release=v1"])["release"] is True


# =============================================================================
# has_explicit_fork Tests
# =============================================================================


class TestHasExplicitFork:
    """Test fork flag detection."""

    def test_fork_flag_present(self) -> None:
        """Test --fork flag is detected."""
        assert has_explicit_fork(["--fork", "GE-Proton"]) is True

    def test_short_fork_flag_present(self) -> None:
        """Test -f flag is detected."""
        assert has_explicit_fork(["-f", "GE-Proton"]) is True

    def test_fork_flag_with_equals(self) -> None:
        """Test --fork= value syntax."""
        assert has_explicit_fork(["--fork=GE-Proton"]) is True

    def test_no_fork_flag(self) -> None:
        """Test absence of fork flag."""
        assert has_explicit_fork(["--list"]) is False
        assert has_explicit_fork([]) is False


# =============================================================================
# get_operation_from_args Tests
# =============================================================================


class TestGetOperationFromArgs:
    """Test operation detection from parsed args."""

    def test_ls_operation(self) -> None:
        """Test --ls returns 'ls'."""
        args = MagicMock(
            ls=True, list=False, relink=False, rm=False, prune=False, check=False
        )
        assert get_operation_from_args(args) == "ls"

    def test_list_operation(self) -> None:
        """Test --list returns 'list'."""
        args = MagicMock(
            ls=False, list=True, relink=False, rm=False, prune=False, check=False
        )
        assert get_operation_from_args(args) == "list"

    def test_relink_operation(self) -> None:
        """Test --relink returns 'relink'."""
        args = MagicMock(
            ls=False, list=False, relink=True, rm=False, prune=False, check=False
        )
        assert get_operation_from_args(args) == "relink"

    def test_rm_operation(self) -> None:
        """Test --rm returns 'rm'."""
        args = MagicMock(
            ls=False, list=False, relink=False, rm=True, prune=False, check=False
        )
        assert get_operation_from_args(args) == "rm"

    def test_prune_operation(self) -> None:
        """Test --prune returns 'prune'."""
        args = MagicMock(
            ls=False, list=False, relink=False, rm=False, prune=True, check=False
        )
        assert get_operation_from_args(args) == "prune"

    def test_check_operation(self) -> None:
        """Test --check returns 'check'."""
        args = MagicMock(
            ls=False, list=False, relink=False, rm=False, prune=False, check=True
        )
        assert get_operation_from_args(args) == "check"

    def test_no_operation(self) -> None:
        """Test no operation returns None."""
        args = MagicMock(
            ls=False, list=False, relink=False, rm=False, prune=False, check=False
        )
        assert get_operation_from_args(args) is None


# =============================================================================
# CLIContext Tests
# =============================================================================


class TestCLIContext:
    """Test CLIContext dataclass."""

    def test_context_is_frozen(self) -> None:
        """Test CLIContext is immutable."""
        ctx = CLIContext(
            fetcher=MagicMock(),
            forgejo_fetcher=MagicMock(),
            args=MagicMock(),
            extract_dir=Path("/tmp"),
            output_dir=Path("/tmp"),
            explicit_flags={},
        )
        with pytest.raises(Exception):
            ctx.fetcher = MagicMock()  # type: ignore[assignment]


# =============================================================================
# dispatch Tests
# =============================================================================


class TestDispatch:
    """Test dispatch function routing."""

    def test_dispatch_ls(self, mocker: Any) -> None:
        """Test dispatch routes to ls handler."""
        mock_handler = mocker.patch("protonfetcher.cli.dispatch.handle_ls_operation")
        ctx = CLIContext(
            fetcher=MagicMock(),
            forgejo_fetcher=MagicMock(),
            args=MagicMock(
                ls=True, list=False, relink=False, rm=False, prune=False, check=False
            ),
            extract_dir=Path("/tmp"),
            output_dir=Path("/tmp"),
            explicit_flags={},
        )
        result = dispatch(ctx, ["--ls"])
        assert result == 0
        mock_handler.assert_called_once()

    def test_dispatch_list(self, mocker: Any) -> None:
        """Test dispatch routes to list handler."""
        mock_handler = mocker.patch("protonfetcher.cli.dispatch.handle_list_operation")
        ctx = CLIContext(
            fetcher=MagicMock(),
            forgejo_fetcher=MagicMock(),
            args=MagicMock(
                ls=False, list=True, relink=False, rm=False, prune=False, check=False
            ),
            extract_dir=Path("/tmp"),
            output_dir=Path("/tmp"),
            explicit_flags={},
        )
        result = dispatch(ctx, ["--list"])
        assert result == 0
        mock_handler.assert_called_once()

    def test_dispatch_relink(self, mocker: Any) -> None:
        """Test dispatch routes to relink handler."""
        mock_handler = mocker.patch(
            "protonfetcher.cli.dispatch.handle_relink_operation"
        )
        ctx = CLIContext(
            fetcher=MagicMock(),
            forgejo_fetcher=MagicMock(),
            args=MagicMock(
                ls=False, list=False, relink=True, rm=False, prune=False, check=False
            ),
            extract_dir=Path("/tmp"),
            output_dir=Path("/tmp"),
            explicit_flags={},
        )
        result = dispatch(ctx, ["--relink"])
        assert result == 0
        mock_handler.assert_called_once()

    def test_dispatch_rm(self, mocker: Any) -> None:
        """Test dispatch routes to rm handler."""
        mock_handler = mocker.patch("protonfetcher.cli.dispatch.handle_rm_operation")
        ctx = CLIContext(
            fetcher=MagicMock(),
            forgejo_fetcher=MagicMock(),
            args=MagicMock(
                ls=False, list=False, relink=False, rm=True, prune=False, check=False
            ),
            extract_dir=Path("/tmp"),
            output_dir=Path("/tmp"),
            explicit_flags={},
        )
        result = dispatch(ctx, ["--rm", "--release", "v1"])
        assert result == 0
        mock_handler.assert_called_once()

    def test_dispatch_prune(self, mocker: Any) -> None:
        """Test dispatch routes to prune handler."""
        mock_handler = mocker.patch("protonfetcher.cli.dispatch.handle_prune_operation")
        ctx = CLIContext(
            fetcher=MagicMock(),
            forgejo_fetcher=MagicMock(),
            args=MagicMock(
                ls=False, list=False, relink=False, rm=False, prune=True, check=False
            ),
            extract_dir=Path("/tmp"),
            output_dir=Path("/tmp"),
            explicit_flags={},
        )
        result = dispatch(ctx, ["--prune"])
        assert result == 0
        mock_handler.assert_called_once()

    def test_dispatch_check(self, mocker: Any) -> None:
        """Test dispatch routes to check handler."""
        mock_handler = mocker.patch("protonfetcher.cli.dispatch.handle_check_operation")
        ctx = CLIContext(
            fetcher=MagicMock(),
            forgejo_fetcher=MagicMock(),
            args=MagicMock(
                ls=False, list=False, relink=False, rm=False, prune=False, check=True
            ),
            extract_dir=Path("/tmp"),
            output_dir=Path("/tmp"),
            explicit_flags={},
        )
        result = dispatch(ctx, ["--check"])
        assert result == 0
        mock_handler.assert_called_once()

    def test_dispatch_no_operation_calls_resolve_default(self, mocker: Any) -> None:
        """Test dispatch calls resolve_default_operation when no operation flag is set."""
        mock_resolve = mocker.patch(
            "protonfetcher.cli.dispatch.resolve_default_operation"
        )
        ctx = CLIContext(
            fetcher=MagicMock(),
            forgejo_fetcher=MagicMock(),
            args=MagicMock(
                ls=False, list=False, relink=False, rm=False, prune=False, check=False
            ),
            extract_dir=Path("/tmp"),
            output_dir=Path("/tmp"),
            explicit_flags={},
        )
        result = dispatch(ctx, [])
        assert result == 0
        mock_resolve.assert_called_once()


# =============================================================================
# resolve_default_operation Tests
# =============================================================================


class TestResolveDefaultOperation:
    """Test default operation resolution."""

    def test_fork_flag_without_value_triggers_multi_fork_update(
        self, mocker: Any
    ) -> None:
        """Test -f without value triggers multi-fork update."""
        mock_handler = mocker.patch(
            "protonfetcher.cli.dispatch.handle_multi_fork_update"
        )
        args = MagicMock(fork=None, dry_run=False)
        ctx = CLIContext(
            fetcher=MagicMock(),
            forgejo_fetcher=MagicMock(),
            args=args,
            extract_dir=Path("/tmp"),
            output_dir=Path("/tmp"),
            explicit_flags={"fork": True},
        )
        resolve_default_operation(ctx, ["-f"])
        mock_handler.assert_called_once()

    def test_fork_flag_with_value_triggers_fetch(self, mocker: Any) -> None:
        """Test -f with value triggers fetch for that fork."""
        mock_handler = mocker.patch("protonfetcher.cli.dispatch.handle_fetch_with_fork")
        args = MagicMock(fork="GE-Proton", dry_run=False)
        ctx = CLIContext(
            fetcher=MagicMock(),
            forgejo_fetcher=MagicMock(),
            args=args,
            extract_dir=Path("/tmp"),
            output_dir=Path("/tmp"),
            explicit_flags={"fork": True},
        )
        resolve_default_operation(ctx, ["-f", "GE-Proton"])
        mock_handler.assert_called_once()

    def test_release_flag_triggers_fetch(self, mocker: Any) -> None:
        """Test --release flag triggers fetch."""
        mock_handler = mocker.patch("protonfetcher.cli.dispatch.handle_fetch_with_fork")
        args = MagicMock(fork="GE-Proton", dry_run=False)
        ctx = CLIContext(
            fetcher=MagicMock(),
            forgejo_fetcher=MagicMock(),
            args=args,
            extract_dir=Path("/tmp"),
            output_dir=Path("/tmp"),
            explicit_flags={"release": True},
        )
        resolve_default_operation(ctx, ["--release", "v1"])
        mock_handler.assert_called_once()

    def test_no_flags_triggers_ls(self, mocker: Any) -> None:
        """Test no flags triggers ls operation."""
        mock_handler = mocker.patch("protonfetcher.cli.dispatch.handle_ls_operation")
        args = MagicMock(fork=None)
        ctx = CLIContext(
            fetcher=MagicMock(),
            forgejo_fetcher=MagicMock(),
            args=args,
            extract_dir=Path("/tmp"),
            output_dir=Path("/tmp"),
            explicit_flags={
                "ls": False,
                "list": False,
                "rm": False,
                "fork": False,
                "release": False,
            },
        )
        resolve_default_operation(ctx, [])
        mock_handler.assert_called_once()
