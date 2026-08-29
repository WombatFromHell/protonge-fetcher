"""GitHub release fetcher for ProtonFetcher.

Handles GE-Proton, Proton-EM, and CachyOS forks hosted on GitHub.
All platform-specific behavior is delegated to GitHubPlatformAdapter.
"""

from .base_release_fetcher import BaseReleaseFetcher


class GitHubReleaseFetcher(BaseReleaseFetcher):
    """GitHub-hosted Proton forks; platform is entirely adapter-driven."""

    platform = "github"
