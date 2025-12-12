"""
Tests for CLI argument validation and error handling in protonfetcher.py
"""

import argparse

import pytest

from protonfetcher.cli import _validate_mutually_exclusive_args


class TestCLIValidation:
    """Tests for CLI argument validation functions."""

    def test_validate_mutually_exclusive_args_list_and_release(self):
        """Test validation fails when --list and --release are used together."""
        args = argparse.Namespace()
        args.list = True
        args.release = "test-tag"
        args.ls = False
        args.rm = False

        with pytest.raises(SystemExit) as exc_info:
            _validate_mutually_exclusive_args(args)

        assert exc_info.value.code == 1

    def test_validate_mutually_exclusive_args_ls_with_release(self):
        """Test validation fails when --ls is used with --release."""
        args = argparse.Namespace()
        args.list = False
        args.release = "test-tag"
        args.ls = True
        args.rm = False

        with pytest.raises(SystemExit) as exc_info:
            _validate_mutually_exclusive_args(args)

        assert exc_info.value.code == 1

    def test_validate_mutually_exclusive_args_ls_with_list(self):
        """Test validation fails when --ls is used with --list."""
        args = argparse.Namespace()
        args.list = True
        args.release = None
        args.ls = True
        args.rm = False

        with pytest.raises(SystemExit) as exc_info:
            _validate_mutually_exclusive_args(args)

        assert exc_info.value.code == 1

    def test_validate_mutually_exclusive_args_rm_with_release(self):
        """Test validation fails when --rm is used with --release."""
        args = argparse.Namespace()
        args.list = False
        args.release = "test-tag"
        args.ls = False
        args.rm = "test-release"

        with pytest.raises(SystemExit) as exc_info:
            _validate_mutually_exclusive_args(args)

        assert exc_info.value.code == 1

    def test_validate_mutually_exclusive_args_rm_with_list(self):
        """Test validation fails when --rm is used with --list."""
        args = argparse.Namespace()
        args.list = True
        args.release = None
        args.ls = False
        args.rm = "test-release"

        with pytest.raises(SystemExit) as exc_info:
            _validate_mutually_exclusive_args(args)

        assert exc_info.value.code == 1

    def test_validate_mutually_exclusive_args_rm_with_ls(self):
        """Test validation fails when --rm is used with --ls."""
        args = argparse.Namespace()
        args.list = False
        args.release = None
        args.ls = True
        args.rm = "test-release"

        with pytest.raises(SystemExit) as exc_info:
            _validate_mutually_exclusive_args(args)

        assert exc_info.value.code == 1

    def test_validate_mutually_exclusive_args_valid_combinations(self):
        """Test validation passes for valid argument combinations."""
        # Test with no conflicting args
        args = argparse.Namespace()
        args.list = False
        args.release = None
        args.ls = False
        args.rm = False
        args.relink = False

        # This should not raise an exception
        _validate_mutually_exclusive_args(args)

        # Test with only --list
        args.list = True
        args.release = None
        args.ls = False
        args.rm = False
        _validate_mutually_exclusive_args(args)

        # Test with only --release
        args.list = False
        args.release = "test-tag"
        args.ls = False
        args.rm = False
        _validate_mutually_exclusive_args(args)

        # Test with only --ls
        args.list = False
        args.release = None
        args.ls = True
        args.rm = False
        _validate_mutually_exclusive_args(args)

        # Test with only --rm
        args.list = False
        args.release = None
        args.ls = False
        args.rm = "test-release"
        _validate_mutually_exclusive_args(args)
