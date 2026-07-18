"""Platform-specific URL and header builders for ProtonFetcher."""

import logging

from .common import DEFAULT_USER_AGENT, Headers, PlatformAdapter

logger = logging.getLogger(__name__)


class PlatformAdapterImpl:
    """Parameterized platform adapter for GitHub/Forgejo-hosted releases."""

    def __init__(
        self,
        api_base: str,
        host_base: str,
        accept_header: str,
    ) -> None:
        self.api_base = api_base
        self.host_base = host_base
        self.default_headers: Headers = {
            "Accept": accept_header,
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


# ponytail: single parameterized class replaces two identical ones; swap to config dict if >2 platforms
github_adapter: PlatformAdapter = PlatformAdapterImpl(
    api_base="https://api.github.com",
    host_base="https://github.com",
    accept_header="application/vnd.github.v3+json",
)
forgejo_adapter: PlatformAdapter = PlatformAdapterImpl(
    api_base="https://dawn.wine/api/v1",
    host_base="https://dawn.wine",
    accept_header="application/json",
)
