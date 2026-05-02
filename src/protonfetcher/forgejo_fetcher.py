"""Forgejo release fetcher implementation for ProtonFetcher.

Handles DW-Proton and other forks hosted on Forgejo instances.
All platform-specific behavior is delegated to ForgejoPlatformAdapter.
"""

import logging
from typing import Any, Optional

from .base_release_fetcher import BaseReleaseFetcher
from .common import DEFAULT_TIMEOUT, FileSystemClientProtocol, NetworkClientProtocol

logger = logging.getLogger(__name__)


class ForgejoReleaseFetcher(BaseReleaseFetcher):
    """Marker subclass for Forgejo-hosted Proton forks.

    Platform-specific behavior is entirely handled by ForgejoPlatformAdapter.
    """

    platform = "forgejo"

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
