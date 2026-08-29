"""Forgejo release fetcher for ProtonFetcher.

Handles DW-Proton and other forks hosted on Forgejo instances.
All platform-specific behavior is delegated to ForgejoPlatformAdapter.
"""

from .base_release_fetcher import BaseReleaseFetcher


class ForgejoReleaseFetcher(BaseReleaseFetcher):
    """Forgejo-hosted Proton forks; platform is entirely adapter-driven."""

    platform = "forgejo"
