"""GitHub release fetcher for ProtonFetcher.

Handles Proton-GE, Proton-EM, Proton-CachyOS, and Proton-Wineland forks hosted on GitHub.
All platform-specific behavior is delegated to GitHubPlatformAdapter.
"""

from .base_release_fetcher import BaseReleaseFetcher


class GitHubReleaseFetcher(BaseReleaseFetcher):
    """GitHub-hosted Proton forks; platform is entirely adapter-driven."""

    platform = "github"
