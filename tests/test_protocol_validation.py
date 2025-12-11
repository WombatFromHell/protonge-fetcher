"""Tests for protocol validation utility and protocol improvements."""

from pathlib import Path

import pytest

from protonfetcher.common import FileSystemClientProtocol, NetworkClientProtocol
from protonfetcher.filesystem import FileSystemClient
from protonfetcher.network import NetworkClient
from protonfetcher.utils import validate_protocol_instance


class TestProtocolValidation:
    """Test protocol validation utility function."""

    def test_network_client_implements_protocol(self):
        """Test that NetworkClient implements NetworkClientProtocol."""
        client = NetworkClient(timeout=30)
        assert validate_protocol_instance(client, NetworkClientProtocol)

    def test_filesystem_client_implements_protocol(self):
        """Test that FileSystemClient implements FileSystemClientProtocol."""
        client = FileSystemClient()
        assert validate_protocol_instance(client, FileSystemClientProtocol)

    def test_protocol_version_constants(self):
        """Test that protocols and implementations have version constants."""
        # Test protocol versions
        assert hasattr(NetworkClientProtocol, "PROTOCOL_VERSION")
        assert NetworkClientProtocol.PROTOCOL_VERSION == "1.0"

        assert hasattr(FileSystemClientProtocol, "PROTOCOL_VERSION")
        assert FileSystemClientProtocol.PROTOCOL_VERSION == "1.0"

        # Test implementation versions
        network_client = NetworkClient()
        assert hasattr(network_client, "PROTOCOL_VERSION")
        assert network_client.PROTOCOL_VERSION == "1.0"

        filesystem_client = FileSystemClient()
        assert hasattr(filesystem_client, "PROTOCOL_VERSION")
        assert filesystem_client.PROTOCOL_VERSION == "1.0"

    def test_protocol_methods_present(self):
        """Test that protocol methods are present in implementations."""
        network_client = NetworkClient(timeout=30)

        # Check NetworkClientProtocol methods
        assert hasattr(network_client, "get")
        assert hasattr(network_client, "head")
        assert hasattr(network_client, "download")
        assert hasattr(network_client, "timeout")

        filesystem_client = FileSystemClient()

        # Check FileSystemClientProtocol methods
        assert hasattr(filesystem_client, "exists")
        assert hasattr(filesystem_client, "is_dir")
        assert hasattr(filesystem_client, "is_symlink")
        assert hasattr(filesystem_client, "mkdir")
        assert hasattr(filesystem_client, "write")
        assert hasattr(filesystem_client, "read")
        assert hasattr(filesystem_client, "size")
        assert hasattr(filesystem_client, "mtime")
        assert hasattr(filesystem_client, "symlink_to")
        assert hasattr(filesystem_client, "resolve")
        assert hasattr(filesystem_client, "unlink")
        assert hasattr(filesystem_client, "rmtree")
        assert hasattr(filesystem_client, "iterdir")

    def test_invalid_protocol_implementation(self):
        """Test that objects not implementing protocols are detected."""

        class FakeClient:
            pass

        fake_client = FakeClient()
        assert not validate_protocol_instance(fake_client, NetworkClientProtocol)
        assert not validate_protocol_instance(fake_client, FileSystemClientProtocol)

    def test_partial_protocol_implementation(self):
        """Test that partial implementations are detected."""

        class PartialNetworkClient:
            def __init__(self):
                self.timeout = 30

            def get(self, url, headers=None, stream=False):
                return None

            # Missing head() and download() methods

        partial_client = PartialNetworkClient()
        assert not validate_protocol_instance(partial_client, NetworkClientProtocol)


class TestProtocolDocumentation:
    """Test that protocol documentation is comprehensive."""

    def test_network_protocol_has_docstring(self):
        """Test that NetworkClientProtocol has comprehensive docstring."""
        assert NetworkClientProtocol.__doc__ is not None
        assert "network operations" in NetworkClientProtocol.__doc__.lower()
        assert "timeout" in NetworkClientProtocol.__doc__.lower()

    def test_filesystem_protocol_has_docstring(self):
        """Test that FileSystemClientProtocol has comprehensive docstring."""
        assert FileSystemClientProtocol.__doc__ is not None
        assert "filesystem" in FileSystemClientProtocol.__doc__.lower()

    def test_protocol_methods_have_docstrings(self):
        """Test that all protocol methods have docstrings."""
        # Test NetworkClientProtocol methods
        assert NetworkClientProtocol.get.__doc__ is not None
        assert NetworkClientProtocol.head.__doc__ is not None
        assert NetworkClientProtocol.download.__doc__ is not None

        # Test FileSystemClientProtocol methods
        assert FileSystemClientProtocol.exists.__doc__ is not None
        assert FileSystemClientProtocol.is_dir.__doc__ is not None
        assert FileSystemClientProtocol.is_symlink.__doc__ is not None
        assert FileSystemClientProtocol.mkdir.__doc__ is not None
        assert FileSystemClientProtocol.write.__doc__ is not None
        assert FileSystemClientProtocol.read.__doc__ is not None
        assert FileSystemClientProtocol.size.__doc__ is not None
        assert FileSystemClientProtocol.mtime.__doc__ is not None
        assert FileSystemClientProtocol.symlink_to.__doc__ is not None
        assert FileSystemClientProtocol.resolve.__doc__ is not None
        assert FileSystemClientProtocol.unlink.__doc__ is not None
        assert FileSystemClientProtocol.rmtree.__doc__ is not None
        assert FileSystemClientProtocol.iterdir.__doc__ is not None


class TestProtocolImplementationDocumentation:
    """Test that protocol implementations document their conformance."""

    def test_network_client_documents_protocol_conformance(self):
        """Test that NetworkClient documents its protocol conformance."""
        assert NetworkClient.__doc__ is not None
        assert "NetworkClientProtocol" in NetworkClient.__doc__
        assert "v1.0" in NetworkClient.__doc__

    def test_filesystem_client_documents_protocol_conformance(self):
        """Test that FileSystemClient documents its protocol conformance."""
        assert FileSystemClient.__doc__ is not None
        assert "FileSystemClientProtocol" in FileSystemClient.__doc__
        assert "v1.0" in FileSystemClient.__doc__
