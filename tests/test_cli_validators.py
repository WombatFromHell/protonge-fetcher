"""Tests for CLI validation functions.

Tests for set_default_fork(), validate_mutually_exclusive_args(), and
related validation functions in protonfetcher.cli.validators.
"""

import argparse
import sys
from typing import Any
from unittest.mock import patch

import pytest

from protonfetcher.cli.argparse_builder import build_parser, parse_args
from protonfetcher.cli.validators import (
    set_default_fork,
    validate_mutually_exclusive_args,
)
from protonfetcher.common import ForkName

# =============================================================================
# set_default_fork Tests
# =============================================================================


def _make_args(**kwargs: Any) -> argparse.Namespace:
    """Create an argparse.Namespace with the given attributes.

    Uses argparse.SUPPRESS for fork to match the parser behavior
    (fork attribute only exists when --fork is explicitly passed).
    """
    defaults = {
        "ls": False,
        "list": False,
        "relink": False,
        "rm": False,
        "prune": False,
        "check": False,
        "dry_run": False,
    }
    defaults.update(kwargs)
    ns = argparse.Namespace(**defaults)
    # If fork was not provided, delete it to match SUPPRESS behavior
    if hasattr(ns, "fork") and "fork" not in kwargs:
        delattr(ns, "fork")
    return ns


class TestSetDefaultFork:
    """Test set_default_fork()."""

    def test_default_fork_set_when_not_provided(self) -> None:
        """Test default fork is set when fork attribute doesn't exist (SUPPRESS behavior)."""
        args = _make_args()  # fork not provided, attribute doesn't exist
        result = set_default_fork(args)
        assert result.fork == ForkName.GE_PROTON

    def test_existing_fork_preserved(self) -> None:
        """Test existing fork value is preserved."""
        args = _make_args(fork=ForkName.PROTON_EM)
        result = set_default_fork(args)
        assert result.fork == ForkName.PROTON_EM

    def test_string_fork_preserved(self) -> None:
        """Test string fork value is preserved."""
        args = _make_args(fork="GE-Proton")
        result = set_default_fork(args)
        assert result.fork == "GE-Proton"

    def test_read_only_op_no_default_fork(self) -> None:
        """Test read-only operations don't get a default fork."""
        args = _make_args(ls=True, fork=None)
        result = set_default_fork(args)
        assert result.fork is None


# =============================================================================
# validate_mutually_exclusive_args Tests
# =============================================================================


class TestValidateMutuallyExclusiveArgs:
    """Test mutually exclusive argument validation."""

    @pytest.mark.parametrize(
        "argv",
        [
            ["protonfetcher", "--list", "--release", "GE-Proton10-20"],
            ["protonfetcher", "--ls", "--release", "GE-Proton10-20"],
            ["protonfetcher", "--ls", "--list"],
            ["protonfetcher", "--rm", "GE-Proton10-20", "--release", "GE-Proton10-19"],
            ["protonfetcher", "--rm", "GE-Proton10-20", "--list"],
            ["protonfetcher", "--rm", "GE-Proton10-20", "--ls"],
        ],
    )
    def test_mutually_exclusive_flags(self, argv: list[str]) -> None:
        """Test that mutually exclusive flags cannot be used together."""
        with patch.object(sys, "argv", argv):
            with pytest.raises(SystemExit):
                parse_args(build_parser())

    def test_relink_without_fork_fails(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that --relink requires --fork."""
        with patch.object(sys, "argv", ["protonfetcher", "--relink"]):
            args = parse_args(build_parser())
            args = set_default_fork(args)
            with pytest.raises(SystemExit):
                validate_mutually_exclusive_args(args)

        captured = capsys.readouterr()
        assert "--relink requires --fork" in captured.out

    @pytest.mark.parametrize(
        "argv",
        [
            [
                "protonfetcher",
                "--relink",
                "--fork",
                "GE-Proton",
                "--release",
                "GE-Proton10-20",
            ],
            ["protonfetcher", "--relink", "--fork", "GE-Proton", "--list"],
            ["protonfetcher", "--relink", "--fork", "GE-Proton", "--ls"],
            [
                "protonfetcher",
                "--relink",
                "--fork",
                "GE-Proton",
                "--rm",
                "GE-Proton10-20",
            ],
            ["protonfetcher", "--fork", "GE-Proton", "--check", "--dry-run"],
            ["protonfetcher", "--fork", "GE-Proton", "--check", "--list"],
            ["protonfetcher", "--dry-run", "--list"],
            ["protonfetcher", "--dry-run", "--ls"],
            ["protonfetcher", "--dry-run", "--rm", "GE-Proton10-20"],
            ["protonfetcher", "--dry-run", "--relink", "--fork", "GE-Proton"],
        ],
    )
    def test_check_and_dry_run_conflicts(self, argv: list[str]) -> None:
        """Test that --check and --dry-run conflict with other flags."""
        with patch.object(sys, "argv", argv):
            with pytest.raises(SystemExit):
                args = parse_args(build_parser())
                args = set_default_fork(args)
                validate_mutually_exclusive_args(args)
