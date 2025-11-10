"""
Unit tests for NetworkClient and NetworkClientProtocol in protonfetcher.py
"""

import subprocess
from pathlib import Path

import pytest

from protonfetcher import NetworkClient, NetworkClientProtocol


class TestNetworkClient:
    """Tests for NetworkClient class."""

    def test_init(self):
        """Test NetworkClient initialization."""
        client = NetworkClient(timeout=60)
        assert client.timeout == 60

    def test_get_method(self, mock_subprocess_success):
        """Test GET method."""
        client = NetworkClient(timeout=30)
        _result = client.get("https://example.com")

        mock_subprocess_success.assert_called_once()
        # Verify the command includes the timeout
        args, kwargs = mock_subprocess_success.call_args
        cmd = args[0]
        assert str(30) in cmd  # timeout value should be in the command

    def test_get_method_with_headers(self, mock_subprocess_success):
        """Test GET method with headers."""
        client = NetworkClient(timeout=30)
        headers = {"User-Agent": "Test-Agent"}
        _result = client.get("https://example.com", headers=headers)

        mock_subprocess_success.assert_called_once()
        args, kwargs = mock_subprocess_success.call_args
        cmd = args[0]
        assert "-H" in cmd
        assert "User-Agent: Test-Agent" in cmd

    def test_head_method(self, mock_subprocess_success):
        """Test HEAD method."""
        client = NetworkClient(timeout=30)
        _result = client.head("https://example.com")

        mock_subprocess_success.assert_called_once()
        args, kwargs = mock_subprocess_success.call_args
        cmd = args[0]
        assert "-I" in cmd  # Verify it's a HEAD request

    def test_download_method(self, mock_subprocess_success):
        """Test download method."""
        client = NetworkClient(timeout=30)
        output_path = Path("/tmp/test.tar.gz")
        _result = client.download("https://example.com/file.tar.gz", output_path)

        mock_subprocess_success.assert_called_once()
        args, kwargs = mock_subprocess_success.call_args
        cmd = args[0]
        assert str(output_path) in cmd  # Verify output path is in command
        assert "-o" in cmd  # Verify download flag is in command


class TestNetworkClientProtocol:
    """Tests for NetworkClientProtocol using shared fixtures."""

    def test_protocol_compliance(self, mock_network_client):
        """Test that mock network client complies with protocol."""
        # Test that all required methods exist
        assert hasattr(mock_network_client, "get")
        assert hasattr(mock_network_client, "head")
        assert hasattr(mock_network_client, "download")
        assert hasattr(mock_network_client, "timeout")
