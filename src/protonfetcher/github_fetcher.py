"""GitHub release fetcher implementation for ProtonFetcher.

Handles GE-Proton, Proton-EM, and CachyOS forks hosted on GitHub.
All platform-specific behavior is delegated to GitHubPlatformAdapter.
"""

import logging
from typing import Any, Optional

from .base_release_fetcher import BaseReleaseFetcher
from .common import DEFAULT_TIMEOUT, FileSystemClientProtocol, NetworkClientProtocol

logger = logging.getLogger(__name__)


class GitHubReleaseFetcher(BaseReleaseFetcher):
    """Marker subclass for GitHub-hosted Proton forks.

    Platform-specific behavior is entirely handled by GitHubPlatformAdapter.
    """

    platform = "github"

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        network_client: Optional[NetworkClientProtocol] = None,
        file_system_client: Optional[FileSystemClientProtocol] = None,
        spinner_cls: Optional[Any] = None,
    ) -> None:
        super().__init__(
            timeout=timeout,
            network_client=network_client,
            file_system_client=file_system_client,
            spinner_cls=spinner_cls,
        )
