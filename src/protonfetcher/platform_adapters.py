"""Platform-specific URL and header builders for ProtonFetcher."""

import logging

from .common import DEFAULT_USER_AGENT, Headers, PlatformAdapter

logger = logging.getLogger(__name__)


class GitHubPlatformAdapter:
    """Platform adapter for GitHub-hosted releases."""

    api_base: str = "https://api.github.com"
    host_base: str = "https://github.com"
    default_headers: Headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": DEFAULT_USER_AGENT,
    }

    def build_api_url(self, repo: str, *parts: str) -> str:
        """Build an API URL for the given repo and path parts."""
        base = f"{self.api_base}/repos/{repo}"
        suffix = "/".join(parts) if parts else ""
        return f"{base}/{suffix}" if suffix else base

    def build_download_url(self, repo: str, tag: str, asset_name: str) -> str:
        """Build a download URL for a release asset."""
        return f"{self.host_base}/{repo}/releases/download/{tag}/{asset_name}"

    def build_host_url(self, repo: str, *parts: str) -> str:
        """Build a host page URL (e.g., release tag page)."""
        suffix = "/".join(parts) if parts else ""
        return (
            f"{self.host_base}/{repo}/{suffix}"
            if suffix
            else f"{self.host_base}/{repo}"
        )


class ForgejoPlatformAdapter:
    """Platform adapter for Forgejo-hosted releases (e.g., DW-Proton)."""

    api_base: str = "https://dawn.wine/api/v1"
    host_base: str = "https://dawn.wine"
    default_headers: Headers = {
        "Accept": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
    }

    def build_api_url(self, repo: str, *parts: str) -> str:
        """Build an API URL for the given repo and path parts."""
        base = f"{self.api_base}/repos/{repo}"
        suffix = "/".join(parts) if parts else ""
        return f"{base}/{suffix}" if suffix else base

    def build_download_url(self, repo: str, tag: str, asset_name: str) -> str:
        """Build a download URL for a release asset."""
        return f"{self.host_base}/{repo}/releases/download/{tag}/{asset_name}"

    def build_host_url(self, repo: str, *parts: str) -> str:
        """Build a host page URL (e.g., release tag page)."""
        suffix = "/".join(parts) if parts else ""
        return (
            f"{self.host_base}/{repo}/{suffix}"
            if suffix
            else f"{self.host_base}/{repo}"
        )


# Singleton instances for convenience
github_adapter: PlatformAdapter = GitHubPlatformAdapter()
forgejo_adapter: PlatformAdapter = ForgejoPlatformAdapter()
